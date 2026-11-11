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


from app.intelligence.regime_transitions import regime_transition_analysis


def test_regime_transition_probabilities_and_episode_persistence():
    frame = pd.DataFrame({"market_regime": [
        "RANGE", "RANGE", "TREND_UP", "TREND_UP", "RANGE", "BREAKOUT_UP"
    ]})
    result = regime_transition_analysis(frame)
    assert result["transitions_observed"] == 5
    assert result["transition_counts"]["RANGE"]["TREND_UP"] == 1
    assert result["transition_counts"]["RANGE"]["RANGE"] == 1
    assert result["transition_probabilities"]["RANGE"]["TREND_UP"] == 0.33333333
    assert sum(result["transition_probabilities"]["RANGE"].values()) == pytest.approx(1.0)
    assert result["persistence"]["RANGE"]["episodes"] == 2
    assert result["persistence"]["RANGE"]["average_duration_candles"] == 1.5
    assert result["persistence"]["TREND_UP"]["max_duration_candles"] == 2


def test_transition_analysis_rejects_empty_and_unknown_regimes():
    with pytest.raises(ValueError, match="cannot be empty"):
        regime_transition_analysis(pd.DataFrame())
    with pytest.raises(ValueError, match="Unknown market regimes"):
        regime_transition_analysis(pd.DataFrame({"market_regime": ["BULLISH"]}))
