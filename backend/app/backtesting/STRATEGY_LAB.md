# Phase 7 — Strategy Performance Laboratory

The laboratory compares five fixed strategy implementations:
- `adaptive`: the current market-regime-aware adaptive router
- `trend_crossover`: EMA 20/50 crossover with an ADX filter
- `breakout`: prior 20-bar high/low break with relative-volume confirmation
- `momentum`: EMA alignment, RSI and relative-volume confirmation
- `mean_reversion`: Bollinger-band/RSI extremes gated by low ADX

## Experiment design

Each dataset is split chronologically:
- Train: first 60%
- Validation: next 20%
- Test: final 20%

Indicators are allowed to warm up on the preceding candles, but new entries are gated until the segment begins. Each segment starts with a fresh virtual account. Do not tune strategy rules against the final test segment.

Two execution-cost scenarios are evaluated:
- Base: configured taker fee and slippage
- 2x cost stress: twice the configured taker fee and slippage, plus 1.5x funding rates

Metrics include net return, maximum drawdown, trade count, win rate, profit factor, expectancy, average win/loss, annualized Sharpe/Sortino, recovery factor, estimated liquidations, funding and fees.

Sharpe/Sortino annualization assumes continuous crypto trading (365 days) at the supplied candle timeframe. They are descriptive estimates, not guarantees or standalone selection criteria.

## Download example data

Run from `backend/`:

```powershell
python download_futures_history.py --symbol BTCUSDT --interval 15m --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol ETHUSDT --interval 15m --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol BTCUSDT --interval 1h --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol ETHUSDT --interval 1h --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol BTCUSDT --interval 4h --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol ETHUSDT --interval 4h --start 2023-01-01 --end 2025-01-01 --output data
```

Use a period long enough to include different market regimes. The end date is exclusive and the downloader excludes incomplete candles.

## Run the experiment matrix

```powershell
python run_strategy_lab.py --dataset "BTCUSDT,1h,data/BTCUSDT_1h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "ETHUSDT,1h,data/ETHUSDT_1h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --dataset "BTCUSDT,4h,data/BTCUSDT_4h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "ETHUSDT,4h,data/ETHUSDT_4h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --output-dir reports/phase7
```

Optional risk/configuration flags:
- `--equity 500`
- `--leverage 1`
- `--risk 0.005`
- `--fee 0.0005`
- `--slippage 0.0005`
- `--maintenance-margin 0.005`

The run also classifies each trade by the market regime visible at the signal candle close (the candle before entry), avoiding use of the entry candle's future close. Regime attribution includes trade count, net PnL, win rate, profit factor, expectancy, fees and funding.

The run writes:
- `reports/phase7/strategy_lab_results.csv`
- `reports/phase7/strategy_lab_regime_attribution.csv`
- `reports/phase7/strategy_lab_report.json`

## How to interpret results

1. Use train only to understand behavior and diagnose strategy rules.
2. Use validation to compare candidate strategies and choose a small set for further testing.
3. Freeze all choices before looking at test results.
4. Prefer stable positive expectancy after costs across multiple symbols/timeframes and market regimes, not the single highest return.
5. Inspect trade count, drawdown, exposure, funding and liquidation events. A strategy with very few trades is not statistically persuasive.
6. Re-run with worse fees/slippage and verify the conclusion does not collapse.

## Trade-level bootstrap robustness (Phase 9)

Each strategy/segment/cost-scenario experiment also receives a reproducible trade-level bootstrap report. The default is 1,000 paths; configure it with `--monte-carlo-simulations 5000` and `--seed 123`. The report resamples the experiment's completed net trade PnL values with replacement, using the same number of trades per simulated path. It reports final-equity percentiles, a confidence interval, probability of ending below initial equity, probability of crossing zero equity, and median/95th-percentile maximum drawdown.

The output adds `strategy_lab_monte_carlo.csv` and a `monte_carlo` section in the JSON report. This is a trade-level distribution diagnostic only: it does not preserve chronological dependence, overlapping positions, changing position sizing, market regimes or bar-level stop/liquidation paths. Do not interpret it as a forecast or as a replacement for out-of-sample testing. A zero-trade experiment returns unchanged equity and zero estimated path risk because there are no outcomes to resample.

## Important simulator limitations

This laboratory uses the existing research-only isolated-margin Futures simulator. It does not reproduce Binance matching, mark-price liquidation, maintenance-margin tiers, order-book spread/depth, partial fills, precision/minimum notional, latency, ADL, insurance fund or cross-margin portfolio effects. Funding event timing is approximated at candle timestamps. No exchange orders or API credentials are used.

A positive backtest is not evidence of future profitability and does not authorize live trading.
