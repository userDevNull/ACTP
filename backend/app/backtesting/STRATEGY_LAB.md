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

## Benchmarks and sensitivity analysis (Phase 10)

Every train, validation and test segment is compared with two baselines under both configured cost scenarios:
- `buy_and_hold_spot`: fully funded spot exposure entered at the next candle open and held until the segment ends, with entry/exit fees and slippage
- `cash_no_trade`: no position and no trading fees

The spot benchmark uses the same starting equity and fee/slippage assumptions but does not use leverage, futures funding or liquidation; it is a fully funded spot reference, not a risk-matched futures benchmark. The cash baseline is uninvested equity with zero exposure and no transaction costs. Stress scenarios change spot entry/exit costs but funding assumptions do not apply to spot.

One-factor-at-a-time sensitivity analysis is run on the validation segment only. It varies risk fraction, leverage, taker fee and slippage at 0.5x, 1x, 1.5x and 2x the configured base value (subject to simulator safety bounds). It does not tune strategy parameters, change stop/target distances, or modify funding assumptions. Treat it as a stability diagnostic, not an optimizer. Keep the final test segment untouched when making strategy choices.

Additional output files:
- `strategy_lab_benchmarks.csv` — baseline metrics by symbol, timeframe, segment and cost scenario
- `strategy_lab_sensitivity.csv` — validation-only results by strategy, tested parameter and multiplier
- Both datasets are also included in `strategy_lab_report.json` under `benchmarks` and `sensitivity`. The main strategy results also include `excess_return_vs_spot_pct` and `excess_return_vs_cash_pct` for direct, segment-matched comparisons.

No new dependencies are required; the analysis uses the existing simulator, pandas and NumPy.

## Offline research dashboard (Phase 11)

The strategy laboratory now writes a self-contained HTML dashboard alongside the CSV and JSON reports:
- `strategy_lab_dashboard.html` — validation strategy returns, matched benchmark returns, strategy scorecard, bootstrap final-equity intervals and per-dataset sensitivity charts

The dashboard is generated with Python's standard library and embedded SVG. It has no external JavaScript, CDN, image or font dependencies and can be opened locally in a browser without internet access. It reads the combined experiment payload, so a multi-symbol/timeframe run produces corresponding comparison and sensitivity panels.

Run the normal CLI; dashboard generation is automatic:

~~~powershell
python run_strategy_lab.py --dataset "BTCUSDT,1h,data/BTCUSDT_1h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "ETHUSDT,1h,data/ETHUSDT_1h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --monte-carlo-simulations 2000 --seed 42 --output-dir reports/phase11
~~~

Open `reports/phase11/strategy_lab_dashboard.html` in a browser. The dashboard is a presentation layer for the underlying CSV/JSON outputs; use those raw files for exact numeric analysis and reproducibility.

## Important simulator limitations

This laboratory uses the existing research-only isolated-margin Futures simulator. It does not reproduce Binance matching, mark-price liquidation, maintenance-margin tiers, order-book spread/depth, partial fills, precision/minimum notional, latency, ADL, insurance fund or cross-margin portfolio effects. Funding event timing is approximated at candle timestamps. No exchange orders or API credentials are used.

A positive backtest is not evidence of future profitability and does not authorize live trading.


## Cross-symbol and multi-timeframe validation study (Phase 12)

Phase 12 adds two research outputs to every multi-dataset run:

- `dataset_quality_audit.csv` — checks required OHLCV columns, parseable/duplicate timestamps, finite numeric values, positive prices, valid OHLC high/low relationships, non-negative volume, zero-volume bars, missing candle intervals and optional funding schema/rates. Duplicate timestamps, invalid OHLCV and malformed funding are fatal; gaps and zero-volume bars are warnings. The audit does not fabricate missing candles or repair source data.
- `cross_market_validation.csv` — summarizes the untouched chronological test segment at base costs by strategy. It reports the number and percentage of datasets with positive returns, number/percentage beating the matched spot benchmark, median test return, median excess return versus spot, median drawdown, median within-dataset strategy rank and total trades.

The cross-market summary treats each symbol/timeframe as one comparison unit and reports medians rather than pooling account returns across assets. It is a consistency diagnostic, not a statistical proof. Fewer than three symbol/timeframe datasets is explicitly marked insufficient coverage. A high positive-test percentage is not enough by itself: inspect drawdown, trade count, benchmark edge, fees/funding and the raw per-dataset results.

Recommended study matrix: BTCUSDT, ETHUSDT, SOLUSDT and BNBUSDT on 15m, 1h and 4h, using the same historical date window where possible. Include the matching Futures funding CSV for each symbol (the downloader currently writes one funding file per symbol). Keep the final test split frozen; do not use its ranks to tune rules and then report the same test as independent evidence.

Example downloads from `backend/` (end date exclusive):

~~~powershell
$symbols = @("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")
$frames = @("15m", "1h", "4h")
foreach ($symbol in $symbols) {
  foreach ($frame in $frames) {
    python download_futures_history.py --symbol $symbol --interval $frame --start 2022-01-01 --end 2026-01-01 --output data
  }
}
~~~

Then run the matrix (example shown for BTC and ETH; repeat `--dataset` for each downloaded symbol/timeframe):

~~~powershell
python run_strategy_lab.py --dataset "BTCUSDT,15m,data/BTCUSDT_15m_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "BTCUSDT,1h,data/BTCUSDT_1h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "BTCUSDT,4h,data/BTCUSDT_4h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "ETHUSDT,15m,data/ETHUSDT_15m_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --dataset "ETHUSDT,1h,data/ETHUSDT_1h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --dataset "ETHUSDT,4h,data/ETHUSDT_4h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --monte-carlo-simulations 2000 --seed 42 --output-dir reports/phase12
~~~

The report folder now also contains `cross_market_validation.csv` and `dataset_quality_audit.csv`; both summaries are included in `strategy_lab_report.json`. A dataset that fails the integrity preflight stops the run with an actionable error. Warnings (for example missing intervals) remain visible in the audit so the researcher can decide whether the source is suitable.

No new Python dependency is required. The simulator remains approximate and research-only. This study does not establish future profitability or validate live exchange execution.
