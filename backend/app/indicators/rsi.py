import pandas as pd
from ta.momentum import RSIIndicator


def calculate_rsi(close_prices, period=14):
    series = pd.Series(close_prices)

    rsi = RSIIndicator(
        close=series,
        window=period
    ).rsi()

    return rsi.iloc[-1]