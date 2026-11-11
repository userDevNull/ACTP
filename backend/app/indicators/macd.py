import pandas as pd
from ta.trend import MACD


def calculate_macd(close_prices):
    series = pd.Series(close_prices)

    macd = MACD(close=series)

    return {
        "macd": macd.macd().iloc[-1],
        "signal": macd.macd_signal().iloc[-1],
    }