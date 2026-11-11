"""Causal market-regime classification from closed OHLCV candles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Regime = Literal["TREND_UP", "TREND_DOWN", "RANGE", "BREAKOUT_UP", "BREAKOUT_DOWN", "UNCERTAIN"]


@dataclass(frozen=True)
class MarketState:
    regime: Regime
    adx: float
    atr_pct: float
    relative_volume: float
    ema_fast: float
    ema_slow: float
    reason: str


def _wilder(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def features(candles: pd.DataFrame) -> pd.DataFrame:
    """Compute indicators without accessing future candles."""
    if not {"open", "high", "low", "close", "volume"}.issubset(candles.columns):
        raise ValueError("OHLCV columns required")
    df = candles.copy()
    for name in ("open", "high", "low", "close", "volume"):
        df[name] = pd.to_numeric(df[name], errors="raise")
    if df[list(("open", "high", "low", "close"))].isna().any().any():
        raise ValueError("OHLC prices cannot be null")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (df["volume"] < 0).any():
        raise ValueError("volume must be nonnegative")
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    atr = _wilder(tr, 14)
    plus_di = 100 * _wilder(plus_dm, 14) / atr.replace(0, np.nan)
    minus_di = 100 * _wilder(minus_dm, 14) / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df["adx"] = _wilder(dx, 14)
    df["atr"] = atr
    df["atr_pct"] = atr / df["close"]
    df["ema_fast"] = df["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    df["ema_slow"] = df["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    df["sma20"] = df["close"].rolling(20).mean()
    df["std20"] = df["close"].rolling(20).std()
    df["upper_band"] = df["sma20"] + 2 * df["std20"]
    df["lower_band"] = df["sma20"] - 2 * df["std20"]
    df["volume_avg"] = df["volume"].shift(1).rolling(20).mean()
    df["relative_volume"] = df["volume"] / df["volume_avg"].replace(0, np.nan)
    df["prior_high"] = df["high"].shift(1).rolling(20).max()
    df["prior_low"] = df["low"].shift(1).rolling(20).min()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = _wilder(gain, 14)
    avg_loss = _wilder(loss, 14)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    df.loc[(avg_loss == 0) & (avg_gain > 0), "rsi"] = 100.0
    df.loc[(avg_loss == 0) & (avg_gain == 0), "rsi"] = 50.0
    return df


def classify_regime(candles: pd.DataFrame) -> MarketState:
    if len(candles) < 70:
        return MarketState("UNCERTAIN", float("nan"), float("nan"), float("nan"),
                           float("nan"), float("nan"), "Need at least 70 closed candles")
    row = features(candles).iloc[-1]
    keys = ["adx", "atr_pct", "relative_volume", "ema_fast", "ema_slow",
            "prior_high", "prior_low"]
    if not np.isfinite(row[keys].astype(float).to_numpy()).all():
        return MarketState("UNCERTAIN", float("nan"), float("nan"), float("nan"),
                           float("nan"), float("nan"), "Insufficient indicator history")
    price = float(row["close"])
    adx = float(row["adx"])
    atr_pct = float(row["atr_pct"])
    rv = float(row["relative_volume"])
    fast = float(row["ema_fast"])
    slow = float(row["ema_slow"])
    if atr_pct > 0.08:
        regime, reason = "UNCERTAIN", "Extreme candle volatility"
    elif price > row["prior_high"] and rv >= 1.5 and adx >= 18:
        regime, reason = "BREAKOUT_UP", "Close above prior 20-bar high with volume"
    elif price < row["prior_low"] and rv >= 1.5 and adx >= 18:
        regime, reason = "BREAKOUT_DOWN", "Close below prior 20-bar low with volume"
    elif adx >= 25 and fast > slow and price > slow:
        regime, reason = "TREND_UP", "ADX and moving averages indicate uptrend"
    elif adx >= 25 and fast < slow and price < slow:
        regime, reason = "TREND_DOWN", "ADX and moving averages indicate downtrend"
    elif adx < 20:
        regime, reason = "RANGE", "Low ADX indicates weak directional trend"
    else:
        regime, reason = "UNCERTAIN", "No clear regime"
    return MarketState(regime, adx, atr_pct, rv, fast, slow, reason)
