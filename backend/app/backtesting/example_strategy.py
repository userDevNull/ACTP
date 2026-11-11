"""Example only: a simple moving-average crossover research baseline."""
import pandas as pd


def sma_crossover(candles: pd.DataFrame, index: int) -> int:
    closes = candles["close"]
    if len(closes) < 51:
        return 0
    fast = closes.rolling(20).mean().iloc[-1]
    slow = closes.rolling(50).mean().iloc[-1]
    if pd.isna(fast) or pd.isna(slow):
        return 0
    if fast > slow:
        return 1
    if fast < slow:
        return -1
    return 0
