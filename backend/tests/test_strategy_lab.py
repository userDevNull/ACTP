import numpy as np
import pandas as pd
import pytest

from app.backtesting.strategy_lab import (
    BARS_PER_YEAR,
    _regime_attribution,
    _regime_labels,
    performance_metrics,
    run_strategy_lab,
    strategy_catalog,
)
from app.intelligence.regime import features


def sample_candles(n=200):
    close = [100 + 0.08 * i + 1.5 * np.sin(i / 5) for i in range(n)]
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
        "open": close,
        "high": [value + 0.8 for value in close],
        "low": [value - 0.8 for value in close],
        "close": close,
        "volume": [100 + (i % 9) * 12 for i in range(n)],
    })


def test_strategy_catalog_contains_fixed_comparison_set():
    assert set(strategy_catalog()) == {
        "adaptive", "trend_crossover", "breakout", "momentum", "mean_reversion"
    }


def test_performance_metrics_calculates_core_statistics():
    curve = [
        {"equity": 500.0},
        {"equity": 510.0},
        {"equity": 495.0},
        {"equity": 520.0},
    ]
    trades = [
        {"net_pnl": 10.0, "reason": "take_profit", "funding_paid": 0.5, "fees": 1.0},
        {"net_pnl": -5.0, "reason": "stop_loss", "funding_paid": -0.1, "fees": 1.0},
    ]
    metrics = performance_metrics(curve, trades, 500.0, BARS_PER_YEAR["1h"])
    assert metrics["final_equity"] == 520.0
    assert metrics["trades"] == 2
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["expectancy"] == 2.5
    assert metrics["max_drawdown_pct"] < 0
    assert metrics["fees_paid"] == 2.0


def test_lab_runs_all_strategies_across_three_splits_and_cost_scenarios():
    report = run_strategy_lab(sample_candles(), timeframe="1h")
    assert report["splits"] == {
        "train_end": 120, "validation_end": 160, "total": 200
    }
    assert len(report["results"]) == 5 * 3 * 2
    assert {row["segment"] for row in report["results"]} == {
        "train", "validation", "test"
    }
    assert {row["cost_scenario"] for row in report["results"]} == {
        "base_cost", "2x_cost_stress"
    }
    assert all("sharpe_ratio_annualized" in row for row in report["results"])
    assert "regime_attribution" in report
    assert all(row["regime"] in {
        "TREND_UP", "TREND_DOWN", "RANGE", "BREAKOUT_UP",
        "BREAKOUT_DOWN", "UNCERTAIN"
    } for row in report["regime_attribution"])


def test_lab_rejects_unknown_timeframe_and_missing_volume():
    candles = sample_candles()
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        run_strategy_lab(candles, timeframe="17m")
    with pytest.raises(ValueError, match="Candles require"):
        run_strategy_lab(candles.drop(columns=["volume"]), timeframe="1h")



def test_regime_attribution_uses_signal_candle_before_entry():
    candles = sample_candles()
    labels = _regime_labels(candles)
    entry_timestamp = candles.iloc[100]["timestamp"].isoformat()
    trade = {
        "entry_time": entry_timestamp,
        "net_pnl": 3.0,
        "fees": 0.2,
        "funding_paid": 0.1,
    }
    attribution = _regime_attribution([trade], candles, labels)
    assert len(attribution) == 1
    assert attribution[0]["regime"] == labels[99]
    assert attribution[0]["trades"] == 1
    assert attribution[0]["expectancy"] == 3.0



def test_precomputed_strategy_callbacks_match_causal_reference_rules():
    candles = sample_candles()
    fast_catalog = strategy_catalog(features(candles))
    reference_catalog = strategy_catalog()
    for index in (69, 80, 120, 160, 199):
        history = candles.iloc[: index + 1]
        for name in fast_catalog:
            assert fast_catalog[name](history, index) == reference_catalog[name](history, index)
