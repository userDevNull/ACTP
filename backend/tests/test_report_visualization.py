from app.backtesting.report_visualization import build_research_dashboard, write_research_dashboard


def sample_report():
    return {
        "warning": "Research only.",
        "datasets": [{"symbol": "BTCUSDT", "timeframe": "1h", "candles": 250}],
        "results": [{
            "symbol": "BTCUSDT", "timeframe": "1h", "strategy": "adaptive",
            "segment": "validation", "cost_scenario": "base_cost",
            "net_return_pct": 5.0, "excess_return_vs_spot_pct": 2.0,
            "max_drawdown_pct": -3.0, "trades": 12,
        }],
        "benchmarks": [
            {"symbol": "BTCUSDT", "timeframe": "1h", "benchmark": "buy_and_hold_spot",
             "segment": "validation", "cost_scenario": "base_cost", "net_return_pct": 3.0},
            {"symbol": "BTCUSDT", "timeframe": "1h", "benchmark": "cash_no_trade",
             "segment": "validation", "cost_scenario": "base_cost", "net_return_pct": 0.0},
            {"symbol": "BTCUSDT", "timeframe": "1h", "benchmark": "buy_and_hold_spot",
             "segment": "test", "cost_scenario": "base_cost", "net_return_pct": 1.0},
        ],
        "sensitivity": [
            {"symbol": "BTCUSDT", "timeframe": "1h", "strategy": "adaptive",
             "parameter": parameter, "multiplier": multiplier, "net_return_pct": value}
            for parameter, values in {
                "risk_fraction": [2.0, 5.0, 7.0],
                "leverage": [1.0, 5.0, 8.0],
                "taker_fee_rate": [6.0, 5.0, 3.0],
                "slippage_rate": [7.0, 5.0, 2.0],
            }.items()
            for multiplier, value in zip((0.5, 1.0, 1.5), values)
        ],
        "monte_carlo": [{
            "symbol": "BTCUSDT", "timeframe": "1h", "strategy": "adaptive",
            "segment": "validation", "cost_scenario": "base_cost",
            "final_equity_p05": 480.0, "final_equity_median": 520.0,
            "final_equity_p95": 560.0,
        }],
    }


def test_dashboard_contains_offline_charts_and_scorecard():
    html = build_research_dashboard(sample_report())
    assert "ACTP Research Dashboard" in html
    assert "Validation returns" in html
    assert "Matched benchmark returns" in html
    assert "Validation bootstrap final-equity distribution" in html
    assert "Sensitivity — BTCUSDT 1h — risk_fraction" in html
    assert "Excess vs spot" in html
    assert "BTCUSDT" in html
    assert "<script" not in html
    assert "https://" not in html


def test_dashboard_escapes_user_supplied_labels():
    report = sample_report()
    report["datasets"][0]["symbol"] = "<script>alert(1)</script>"
    report["datasets"][0]["candles"] = "<img src=x onerror=alert(1)>"
    html = build_research_dashboard(report)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_dashboard_writer_creates_parent_and_file(tmp_path):
    target = tmp_path / "nested" / "research.html"
    result = write_research_dashboard(sample_report(), target)
    assert result == target
    assert target.is_file()
    assert "ACTP Research Dashboard" in target.read_text(encoding="utf-8")
