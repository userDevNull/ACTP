# Research backtester (Phase 1)

This module is an offline simulator only. It cannot connect to Binance or place orders.

## Contract
- Input: chronological OHLCV candles with `open`, `high`, `low`, `close`.
- The strategy sees candles only through the current close.
- A signal is filled at the next candle open, not the same candle close.
- Stop and target are checked against subsequent candle ranges; when both are hit in one candle, stop loss is assumed first.
- Fees and slippage are applied on entry and exit.
- Position size is based on a fixed fraction of current cash and the configured stop distance, then capped by notional leverage.
- Open position is closed at the final close.

## Limitations before research conclusions
This is a deliberately small baseline, not a production Futures simulator. It does not yet model exchange precision/minimums, order-book depth, partial fills, liquidation, maintenance margin tiers, mark-price triggers, funding timestamps, multi-symbol portfolio exposure, or latency. Funding is an optional per-bar approximation. Do not use its output to justify live trading.

## Example
Run from `backend/` after installing requirements and pytest:

```python
import pandas as pd
from app.backtesting.engine import run_backtest, BacktestConfig
from app.backtesting.example_strategy import sma_crossover

candles = pd.read_csv("candles.csv")
result = run_backtest(candles, sma_crossover, BacktestConfig())
print(result["summary"])
```
