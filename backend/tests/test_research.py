import pandas as pd
import pytest

from app.backtesting.engine import BacktestConfig
from app.backtesting.research import _run_segment, chronological_splits, evaluate_adaptive


def sample_data(n=200):
    close = [100 + i * 0.08 for i in range(n)]
    return pd.DataFrame({
        "open": close,
        "high": [v + 0.6 for v in close],
        "low": [v - 0.6 for v in close],
        "close": close,
        "volume": [100.0] * n,
    })


def test_chronological_splits_are_ordered_and_non_overlapping():
    splits = chronological_splits(200)
    assert splits.train_end < splits.validation_end < splits.total
    assert splits.train_end == 120
    assert splits.validation_end == 160


def test_rejects_small_dataset():
    with pytest.raises(ValueError):
        chronological_splits(50)


def test_evaluation_returns_all_three_periods():
    result = evaluate_adaptive(sample_data())
    assert set(result["splits"]) == {"train", "validation", "test"}
    assert result["splits"]["train"]["end_index_exclusive"] == 120
    assert result["splits"]["test"]["start_index"] == 160
    assert len(result["splits"]["validation"]["equity_curve"]) == 40
    assert "warning" in result


def test_segment_metrics_are_isolated_and_keep_only_segment_trades():
    result = _run_segment(
        sample_data(),
        120,
        160,
        BacktestConfig(
            initial_cash=500,
            risk_per_trade=0.01,
            stop_loss_pct=0.5,
            take_profit_pct=0.5,
            fee_rate=0,
            slippage_rate=0,
        ),
        strategy=lambda history, index: 1,
    )
    assert len(result["equity_curve"]) == 40
    assert result["summary"]["initial_cash"] == 500
    assert result["summary"]["final_equity"] > 500
    assert result["summary"]["trades"] == 1
    assert result["trades"][0]["entry_index"] >= 120
    assert result["trades"][0]["exit_index"] <= 159
