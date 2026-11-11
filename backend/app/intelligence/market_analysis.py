"""Phase 8 causal market-intelligence diagnostics for closed historical candles.

Research-only: every row is computed from current and prior candles, never
future observations. No trading instructions or exchange order placement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.intelligence.regime import features

REGIMES = ("TREND_UP", "TREND_DOWN", "RANGE", "BREAKOUT_UP", "BREAKOUT_DOWN", "UNCERTAIN")


def analyze_market(candles: pd.DataFrame, *, volatility_window: int = 48) -> pd.DataFrame:
    """Return timestamped, causal diagnostics; no data is fetched from the network."""
    if volatility_window < 5:
        raise ValueError("volatility_window must be at least 5")
    frame = features(candles).reset_index(drop=True)
    if "timestamp" not in frame:
        raise ValueError("timestamp column required")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    if frame["timestamp"].isna().any() or not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("timestamps must be present and chronological")
    if frame["timestamp"].duplicated().any():
        raise ValueError("timestamps must be unique")

    returns = frame["close"].pct_change()
    frame["realized_volatility"] = returns.rolling(volatility_window, min_periods=volatility_window).std()
    frame["volatility_baseline"] = frame["realized_volatility"].shift(1).rolling(
        volatility_window, min_periods=volatility_window
    ).median()
    frame["volatility_ratio"] = (
        frame["realized_volatility"] / frame["volatility_baseline"].replace(0, np.nan)
    )
    frame["trend_strength"] = frame["adx"].clip(lower=0, upper=100) / 100.0
    frame["volume_pressure"] = frame["relative_volume"].clip(lower=0, upper=10)
    frame["breakout_up"] = (
        (frame["close"] > frame["prior_high"]) & (frame["relative_volume"] >= 1.5)
    )
    frame["breakout_down"] = (
        (frame["close"] < frame["prior_low"]) & (frame["relative_volume"] >= 1.5)
    )
    frame["market_regime"] = "UNCERTAIN"
    ready = frame[["adx", "atr_pct", "relative_volume", "ema_fast", "ema_slow",
                   "prior_high", "prior_low"]].notna().all(axis=1)
    calm = ready & (frame["atr_pct"] <= 0.08)
    frame.loc[calm & (frame["adx"] < 20), "market_regime"] = "RANGE"
    frame.loc[calm & (frame["adx"] >= 25) &
              (frame["ema_fast"] > frame["ema_slow"]) &
              (frame["close"] > frame["ema_slow"]), "market_regime"] = "TREND_UP"
    frame.loc[calm & (frame["adx"] >= 25) &
              (frame["ema_fast"] < frame["ema_slow"]) &
              (frame["close"] < frame["ema_slow"]), "market_regime"] = "TREND_DOWN"
    frame.loc[calm & (frame["adx"] >= 18) & frame["breakout_up"], "market_regime"] = "BREAKOUT_UP"
    frame.loc[calm & (frame["adx"] >= 18) & frame["breakout_down"], "market_regime"] = "BREAKOUT_DOWN"
    frame["volatility_state"] = "UNKNOWN"
    valid = frame["volatility_ratio"].notna()
    frame.loc[valid & (frame["volatility_ratio"] >= 1.5), "volatility_state"] = "EXPANDING"
    frame.loc[valid & (frame["volatility_ratio"] <= 0.7), "volatility_state"] = "CONTRACTING"
    frame.loc[valid & (frame["volatility_ratio"] > 0.7) &
              (frame["volatility_ratio"] < 1.5), "volatility_state"] = "NORMAL"
    return frame[["timestamp", "close", "market_regime", "volatility_state",
                  "realized_volatility", "volatility_ratio", "atr_pct", "adx",
                  "trend_strength", "relative_volume", "volume_pressure",
                  "breakout_up", "breakout_down"]].copy()


def summarize_market(diagnostics: pd.DataFrame) -> dict:
    """Summarize observed regimes, excluding warm-up UNCERTAIN from coverage."""
    if diagnostics.empty:
        raise ValueError("diagnostics cannot be empty")
    counts = diagnostics["market_regime"].value_counts()
    observed = int(len(diagnostics) - counts.get("UNCERTAIN", 0))
    last = diagnostics.iloc[-1]
    def nullable(value):
        return round(float(value), 8) if pd.notna(value) and np.isfinite(value) else None
    return {
        "candles": len(diagnostics),
        "start": diagnostics["timestamp"].iloc[0].isoformat(),
        "end": diagnostics["timestamp"].iloc[-1].isoformat(),
        "latest_regime": str(last["market_regime"]),
        "latest_volatility_state": str(last["volatility_state"]),
        "latest_atr_pct": nullable(last["atr_pct"]),
        "latest_adx": nullable(last["adx"]),
        "latest_relative_volume": nullable(last["relative_volume"]),
        "classified_candles": observed,
        "regime_counts": {key: int(counts.get(key, 0)) for key in REGIMES},
        "warning": "Historical closed-candle diagnostics only; not a trade signal.",
    }
