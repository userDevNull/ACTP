import numpy as np
import pandas as pd
import pytest

from app.intelligence.market_analysis import analyze_market, summarize_market


def candles(n=240):
    prices = 100 + np.arange(n) * 0.08 + np.sin(np.arange(n) / 8)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "open": prices, "high": prices + 0.7, "low": prices - 0.7,
        "close": prices, "volume": 100 + np.arange(n) % 10,
    })


def test_diagnostics_and_summary_are_serializable():
    output = analyze_market(candles())
    summary = summarize_market(output)
    assert len(output) == 240
    assert summary["candles"] == 240
    assert sum(summary["regime_counts"].values()) == 240
    assert summary["latest_regime"] in summary["regime_counts"]


def test_future_candles_cannot_change_historical_diagnostics():
    data = candles()
    earlier = analyze_market(data.iloc[:160])
    entire = analyze_market(data)
    pd.testing.assert_frame_equal(
        earlier.reset_index(drop=True),
        entire.iloc[:160].reset_index(drop=True),
    )


def test_invalid_timestamps_and_window_rejected():
    data = candles()
    with pytest.raises(ValueError, match="at least 5"):
        analyze_market(data, volatility_window=4)
    with pytest.raises(ValueError, match="unique"):
        analyze_market(data.assign(timestamp=data["timestamp"].iloc[0]))
    with pytest.raises(ValueError, match="timestamp column"):
        analyze_market(data.drop(columns="timestamp"))
