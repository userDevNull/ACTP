# Historical Futures simulation

## Download data

Run from the backend directory:

```bash
python download_futures_history.py --symbol BTCUSDT --interval 1h --start 2024-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol ETHUSDT --interval 1h --start 2024-01-01 --end 2025-01-01 --output data
```

The end date is exclusive. Candle and funding data are stored separately. Keep the CSV files local; `data/` is ignored by Git.

## Simulation contract

`run_futures_backtest` accepts timestamped OHLC candles, a causal strategy callback, and timestamped funding events. It estimates isolated margin, applies taker fees and slippage, applies funding when a position is open at a supplied funding timestamp, and reports estimated liquidation events.

Example:

```python
import pandas as pd
from app.backtesting.futures_simulator import run_futures_backtest, FuturesConfig
from app.strategies.adaptive import backtest_signal

candles = pd.read_csv("data/BTCUSDT_1h_futures_klines.csv")
funding = pd.read_csv("data/BTCUSDT_futures_funding.csv")
result = run_futures_backtest(candles, backtest_signal, funding, FuturesConfig())
print(result["summary"])
```

## Critical limitations

This is a research approximation, not an exchange-accurate liquidation engine. It uses one fixed maintenance-margin rate and candle high/low as a proxy for mark price. Binance liquidation depends on mark price, position notional tiers, maintenance margin, liquidation fees and account state. Funding event ordering within a candle is also approximated. It does not model order book depth, maker fills, partial fills, exchange filters, ADL, or cross-margin positions.

Use multiple fee/slippage/funding stress cases. Never infer live-trading readiness from a profitable backtest. Do not add live API keys to this research environment.
