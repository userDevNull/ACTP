import numpy as np
import pandas as pd
import pytest

from app.backtesting.futures_simulator import FuturesConfig

from app.backtesting.strategy_lab import (
    BARS_PER_YEAR,
    _regime_attribution,
    _regime_labels,
    _spot_buy_and_hold_segment,
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


def test_spot_buy_and_hold_uses_next_open_and_has_no_futures_funding():
    candles = sample_candles(10)
    curve, trades = _spot_buy_and_hold_segment(
        candles, 0, 10,
        FuturesConfig(
            initial_equity=500.0, leverage=1.0,
            taker_fee_rate=0.001, slippage_rate=0.001,
        ),
    )
    assert len(curve) == 10
    assert len(trades) == 1
    assert trades[0]["entry_time"] == candles.iloc[1]["timestamp"].isoformat()
    assert trades[0]["funding_paid"] == 0.0
    assert trades[0]["reason"] == "end_of_data"
    assert curve[-1]["equity"] == trades[0]["net_pnl"] + 500.0


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
    assert len(report["monte_carlo"]) == 5 * 3 * 2
    assert len(report["benchmarks"]) == 2 * 3 * 2
    assert len(report["sensitivity"]) == 5 * 4 * 4
    assert {row["benchmark"] for row in report["benchmarks"]} == {
        "buy_and_hold_spot", "cash_no_trade"
    }
    assert {row["segment"] for row in report["benchmarks"]} == {
        "train", "validation", "test"
    }
    assert {row["segment"] for row in report["sensitivity"]} == {"validation"}
    assert all("excess_return_vs_spot_pct" in row for row in report["results"])
    assert all("excess_return_vs_cash_pct" in row for row in report["results"])
    validation_strategy = next(
        row for row in report["results"]
        if row["segment"] == "validation" and row["cost_scenario"] == "base_cost"
    )
    validation_spot = next(
        row for row in report["benchmarks"]
        if row["benchmark"] == "buy_and_hold_spot"
        and row["segment"] == "validation"
        and row["cost_scenario"] == "base_cost"
    )
    assert validation_strategy["excess_return_vs_spot_pct"] == round(
        validation_strategy["net_return_pct"] - validation_spot["net_return_pct"], 4
    )
    assert {row["parameter"] for row in report["sensitivity"]} == {
        "risk_fraction", "leverage", "taker_fee_rate", "slippage_rate"
    }
    cash = next(
        row for row in report["benchmarks"]
        if row["benchmark"] == "cash_no_trade"
        and row["segment"] == "validation"
        and row["cost_scenario"] == "base_cost"
    )
    assert cash["final_equity"] == cash["initial_equity"]
    assert cash["trades"] == 0
    assert all(row["simulations"] == 1000 for row in report["monte_carlo"])
    assert all(row["method"] == "trade_pnl_bootstrap_with_replacement" for row in report["monte_carlo"])
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
    labels = _regime_labels(features(candles))
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
