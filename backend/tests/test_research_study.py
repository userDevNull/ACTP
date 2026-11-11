import pandas as pd

from app.backtesting.research_study import (
    audit_market_dataset,
    build_cross_market_validation,
)


def candles():
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=120, freq="1h", tz="UTC"),
        "open": [100.0] * 120,
        "high": [102.0] * 120,
        "low": [98.0] * 120,
        "close": [101.0] * 120,
        "volume": [10.0] * 120,
    })


def test_dataset_audit_passes_valid_hourly_ohlcv():
    report = audit_market_dataset(candles(), "1h")
    assert report["status"] == "pass"
    assert report["rows"] == 120
    assert report["gap_count"] == 0
    assert report["errors"] == []


def test_dataset_audit_reports_gaps_and_zero_volume_as_warnings():
    frame = candles().drop(index=50).reset_index(drop=True)
    frame.loc[0, "volume"] = 0
    report = audit_market_dataset(frame, "1h")
    assert report["status"] == "warn"
    assert report["gap_count"] == 1
    assert any("zero volume" in warning for warning in report["warnings"])


def test_dataset_audit_fails_duplicate_timestamps_and_invalid_ohlc():
    frame = candles()
    frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
    frame.loc[2, "high"] = 90.0
    report = audit_market_dataset(frame, "1h")
    assert report["status"] == "fail"
    assert any("duplicate timestamps" in error for error in report["errors"])
    assert any("OHLC high/low" in error for error in report["errors"])


def test_dataset_audit_checks_funding_schema_and_finite_rates():
    funding = pd.DataFrame({
        "funding_time": [pd.Timestamp("2024-01-01", tz="UTC")],
        "funding_rate": [float("nan")],
    })
    report = audit_market_dataset(candles(), "1h", funding)
    assert report["status"] == "fail"
    assert any("Funding contains invalid" in error for error in report["errors"])


def test_cross_market_summary_uses_test_base_cost_and_benchmark_matched_edges():
    results = []
    benchmarks = []
    for symbol, strategy_returns in {
        "BTCUSDT": {"adaptive": 12.0, "trend_crossover": 8.0},
        "ETHUSDT": {"adaptive": -2.0, "trend_crossover": 5.0},
        "SOLUSDT": {"adaptive": 7.0, "trend_crossover": 1.0},
    }.items():
        for strategy, ret in strategy_returns.items():
            results.append({
                "symbol": symbol, "timeframe": "1h", "strategy": strategy,
                "segment": "test", "cost_scenario": "base_cost",
                "net_return_pct": ret, "max_drawdown_pct": -10.0, "trades": 10,
            })
            results.append({
                "symbol": symbol, "timeframe": "1h", "strategy": strategy,
                "segment": "validation", "cost_scenario": "base_cost",
                "net_return_pct": 999.0, "max_drawdown_pct": -1.0, "trades": 99,
            })
        benchmarks.append({
            "symbol": symbol, "timeframe": "1h", "segment": "test",
            "cost_scenario": "base_cost", "benchmark": "buy_and_hold_spot",
            "net_return_pct": 4.0,
        })
    summary = {row["strategy"]: row for row in build_cross_market_validation(results, benchmarks)}
    adaptive = summary["adaptive"]
    assert adaptive["test_datasets"] == 3
    assert adaptive["positive_test_datasets"] == 2
    assert adaptive["beat_spot_datasets"] == 2
    assert adaptive["median_test_return_pct"] == 7.0
    assert adaptive["median_excess_vs_spot_pct"] == 3.0
    assert adaptive["median_rank_within_dataset"] == 1.0
    assert summary["trend_crossover"]["median_rank_within_dataset"] == 2.0


def test_cross_market_summary_flags_insufficient_coverage():
    summary = build_cross_market_validation(
        [{
            "symbol": "BTCUSDT", "timeframe": "1h", "strategy": "adaptive",
            "segment": "test", "cost_scenario": "base_cost",
            "net_return_pct": 1.0, "max_drawdown_pct": -2.0, "trades": 1,
        }],
        [],
    )
    assert summary[0]["interpretation"] == "Insufficient dataset coverage"
    assert summary[0]["beat_spot_pct"] is None


def test_dataset_audit_accepts_native_binance_funding_csv_schema():
    funding = pd.DataFrame({
        "funding_time": [pd.Timestamp("2024-01-01", tz="UTC")],
        "funding_rate": [0.0001],
        "symbol": ["BTCUSDT"],
    })
    report = audit_market_dataset(candles(), "1h", funding)
    assert report["status"] == "pass"
    assert report["funding_rows"] == 1

def test_dataset_audit_accepts_mixed_precision_funding_timestamps():
    funding = pd.DataFrame({
        "funding_time": [
            "2024-01-01 00:00:00.006000+00:00",
            "2024-01-01 08:00:00+00:00",
            "2024-01-01 16:00:00.009000+00:00",
        ],
        "funding_rate": [0.0001, -0.00005, 0.00008],
        "symbol": ["BTCUSDT"] * 3,
    })

    report = audit_market_dataset(candles(), "1h", funding)

    assert report["status"] == "pass"
    assert report["funding_rows"] == 3
    assert report["errors"] == []
