# Adaptive strategy research prototype

The classifier uses ADX, ATR, EMA, prior range and relative volume from closed candles.
It selects among breakout, mean reversion, trend pullback, and momentum hypotheses.
Every strategy can return HOLD (0). The rules are hypotheses, not validated alpha.

```python
from app.backtesting.engine import run_backtest
from app.strategies.adaptive import backtest_signal

result = run_backtest(candles, backtest_signal)
print(result["summary"])
```

**Important:** Risk policy is a separate research precheck and is not yet wired
into the existing backtester or a trading engine. The backtester has its own
risk-based position sizing; a future integration must avoid bypassing either.
Do not interpret this module as an autonomous execution bot. No live orders.
Test with separate training/validation/test periods, funding, spread, realistic
fees and exchange rules before drawing performance conclusions.
