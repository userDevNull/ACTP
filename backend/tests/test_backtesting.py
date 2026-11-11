import pandas as pd
import pytest

from app.backtesting.engine import BacktestConfig, run_backtest


def test_backtest_returns_metrics_and_closes_at_end():
    data = pd.DataFrame({
        "open": [100, 100, 101, 102, 103],
        "high": [101, 102, 103, 104, 104],
        "low": [99, 99, 100, 101, 102],
        "close": [100, 101, 102, 103, 103],
    })

    def always_long(history, index):
        return 1

    result = run_backtest(
        data, always_long,
        BacktestConfig(initial_cash=500, stop_loss_pct=0.10, take_profit_pct=0.20,
                       fee_rate=0, slippage_rate=0, risk_per_trade=0.01)
    )
    assert result["summary"]["trades"] >= 1
    assert result["trades"][-1]["reason"] == "end_of_data"
    assert result["summary"]["final_equity"] > 500


def test_rejects_invalid_signal():
    data = pd.DataFrame({"open":[1,1,1], "high":[1,1,1], "low":[1,1,1], "close":[1,1,1]})
    with pytest.raises(ValueError):
        run_backtest(data, lambda history, index: 2)
