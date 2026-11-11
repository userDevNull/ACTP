import pandas as pd

from app.intelligence.regime import classify_regime, features
from app.risk.policy import assess_signal
from app.strategies.adaptive import backtest_signal, decide


def make_candles(n=120):
    close = [100 + 0.15 * i for i in range(n)]
    return pd.DataFrame({
        "open": close,
        "high": [v + 0.5 for v in close],
        "low": [v - 0.5 for v in close],
        "close": close,
        "volume": [100] * n,
    })


def test_warmup_returns_hold():
    decision = decide(make_candles(30))
    assert decision.signal == 0
    assert decision.regime == "UNCERTAIN"


def test_no_future_data_in_feature_prefix():
    candles = make_candles()
    before = features(candles.iloc[:90]).iloc[-1]["ema_fast"]
    after = features(candles).iloc[89]["ema_fast"]
    assert before == after


def test_backtest_adapter_matches_decision():
    candles = make_candles()
    assert backtest_signal(candles, len(candles) - 1) == decide(candles).signal


def test_risk_breakers():
    assert not assess_signal(1, equity=480, starting_day_equity=500,
                             peak_equity=500, open_positions=0,
                             requested_risk_fraction=0.005, requested_leverage=1).allowed
    assert assess_signal(1, equity=500, starting_day_equity=500,
                         peak_equity=500, open_positions=0,
                         requested_risk_fraction=0.005, requested_leverage=1).allowed


def test_regime_returns_known_value():
    assert classify_regime(make_candles()).regime in {
        "TREND_UP", "TREND_DOWN", "RANGE", "BREAKOUT_UP",
        "BREAKOUT_DOWN", "UNCERTAIN"
    }
