import pandas as pd

from app.backtesting.futures_simulator import FuturesConfig, run_futures_backtest


def candles():
    ts = pd.date_range("2024-01-01", periods=5, freq="8h", tz="UTC")
    return pd.DataFrame({
        "timestamp": ts,
        "open": [100, 100, 102, 103, 104],
        "high": [101, 103, 104, 105, 105],
        "low": [99, 99, 101, 102, 103],
        "close": [100, 102, 103, 104, 104],
    })


def test_futures_simulator_applies_funding_and_closes_trade():
    funding = pd.DataFrame({
        "funding_time": [pd.Timestamp("2024-01-02T00:00:00Z")],
        "funding_rate": [0.001],
    })
    result = run_futures_backtest(
        candles(), lambda history, idx: 1 if idx == 0 else 0,
        funding,
        FuturesConfig(initial_equity=500, leverage=1, stop_loss_pct=0.10,
                      take_profit_pct=0.20, taker_fee_rate=0,
                      slippage_rate=0, maintenance_margin_rate=0.005),
    )
    assert result["summary"]["trades"] == 1
    assert result["summary"]["funding_total"] > 0
    assert result["trades"][0]["reason"] == "end_of_data"


def test_futures_simulator_reports_estimated_liquidation():
    data = candles()
    data.loc[2, "low"] = 1
    result = run_futures_backtest(
        data, lambda history, idx: 1 if idx == 0 else 0, None,
        FuturesConfig(initial_equity=500, leverage=2, stop_loss_pct=0.9,
                      take_profit_pct=0.95, taker_fee_rate=0,
                      slippage_rate=0, maintenance_margin_rate=0.005),
    )
    assert result["summary"]["liquidations"] == 1
