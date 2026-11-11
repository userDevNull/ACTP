"""Adaptive strategy router; signals are next-bar research intentions only."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.intelligence.regime import MarketState, classify_regime, features

Side = Literal[-1, 0, 1]


@dataclass(frozen=True)
class Decision:
    signal: Side
    strategy: str
    regime: str
    reason: str


def decide(candles: pd.DataFrame) -> Decision:
    state = classify_regime(candles)
    if state.regime == "UNCERTAIN":
        return Decision(0, "none", state.regime, state.reason)
    df = features(candles)
    current = df.iloc[-1]
    previous = df.iloc[-2]
    required = ["close", "ema_fast", "ema_slow", "sma20", "upper_band",
                "lower_band", "rsi", "relative_volume", "atr_pct"]
    if not np.isfinite(current[required].astype(float).to_numpy()).all():
        return Decision(0, "none", state.regime, "Indicators unavailable")

    price = float(current["close"])
    rsi = float(current["rsi"])
    if state.regime in ("BREAKOUT_UP", "BREAKOUT_DOWN"):
        side = 1 if state.regime == "BREAKOUT_UP" else -1
        return Decision(side, "breakout", state.regime, "Confirmed 20-bar range breakout")

    if state.regime == "RANGE":
        if price < current["lower_band"] and rsi < 35:
            return Decision(1, "mean_reversion", state.regime, "Below lower band and RSI oversold")
        if price > current["upper_band"] and rsi > 65:
            return Decision(-1, "mean_reversion", state.regime, "Above upper band and RSI overbought")
        return Decision(0, "mean_reversion", state.regime, "No extreme within range")

    side = 1 if state.regime == "TREND_UP" else -1
    fast = float(current["ema_fast"])
    prev_close = float(previous["close"])
    prev_fast = float(previous["ema_fast"])
    # A completed-candle recross after a pullback, not a standing trend signal.
    if side == 1 and prev_close <= prev_fast and price > fast and 40 <= rsi <= 70:
        return Decision(1, "trend_pullback", state.regime, "Bullish fast-EMA recross")
    if side == -1 and prev_close >= prev_fast and price < fast and 30 <= rsi <= 60:
        return Decision(-1, "trend_pullback", state.regime, "Bearish fast-EMA recross")
    # Momentum is a separate fallback requiring fresh strength and volume.
    if side == 1 and price > float(previous["high"]) and rsi >= 60 and state.relative_volume >= 1.3:
        return Decision(1, "momentum", state.regime, "Fresh bullish momentum with volume")
    if side == -1 and price < float(previous["low"]) and rsi <= 40 and state.relative_volume >= 1.3:
        return Decision(-1, "momentum", state.regime, "Fresh bearish momentum with volume")
    return Decision(0, "trend_pullback", state.regime, "No valid trend entry")


def backtest_signal(candles: pd.DataFrame, index: int) -> Side:
    """Adapter for run_backtest; it receives only historical candles."""
    return decide(candles).signal
