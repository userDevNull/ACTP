import pytest

from app.backtesting.robustness import trade_bootstrap_analysis


def sample_trades():
    return [
        {"net_pnl": 10.0},
        {"net_pnl": -5.0},
        {"net_pnl": 8.0},
        {"net_pnl": -3.0},
    ]


def test_trade_bootstrap_is_deterministic_and_reports_risk_distribution():
    first = trade_bootstrap_analysis(sample_trades(), 500.0, simulations=500, seed=17)
    second = trade_bootstrap_analysis(sample_trades(), 500.0, simulations=500, seed=17)
    assert first == second
    assert first["simulations"] == 500
    assert first["trades_resampled_per_path"] == 4
    assert first["final_equity_p05"] <= first["final_equity_median"]
    assert first["final_equity_median"] <= first["final_equity_p95"]
    assert 0 <= first["probability_of_loss_pct"] <= 100
    assert 0 <= first["probability_of_ruin_pct"] <= 100
    assert first["max_drawdown_pct_p95"] >= first["max_drawdown_pct_median"]
    assert "not a forecast" in first["interpretation"]


def test_trade_bootstrap_empty_trade_set_returns_unchanged_equity():
    result = trade_bootstrap_analysis([], 250.0, simulations=25)
    assert result["final_equity_p05"] == 250.0
    assert result["final_equity_median"] == 250.0
    assert result["probability_of_loss_pct"] == 0.0
    assert result["max_drawdown_pct_p95"] == 0.0


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"initial_equity": 0.0}, "initial_equity"),
        ({"initial_equity": -10.0}, "initial_equity"),
        ({"simulations": 0}, "simulations"),
        ({"confidence_level": 1.0}, "confidence_level"),
        ({"seed": 1.5}, "seed"),
    ],
)
def test_trade_bootstrap_rejects_invalid_configuration(kwargs, message):
    settings = {"initial_equity": 100.0}
    settings.update(kwargs)
    with pytest.raises(ValueError, match=message):
        trade_bootstrap_analysis(sample_trades(), **settings)


def test_trade_bootstrap_rejects_non_finite_trade_pnl():
    with pytest.raises(ValueError, match="finite"):
        trade_bootstrap_analysis([{"net_pnl": float("nan")}], 100.0)
