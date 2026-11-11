import pandas as pd
from ta.trend import EMAIndicator


def calculate_ema(close_prices, period=50):

    series = pd.Series(close_prices)

    ema = EMAIndicator(
        close=series,
        window=period
    ).ema_indicator()

    return ema.iloc[-1]