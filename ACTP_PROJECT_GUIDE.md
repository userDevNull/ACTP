# ACTP — Project, Features and Setup Guide

**Repository:** https://github.com/userDevNull/ACTP  
**Current development:** Phase 8 — Offline Market Intelligence (diagnostics, regime transitions and persistence)  
**Backend:** Python 3.12, FastAPI, pandas, NumPy  
**Frontend:** React, Vite, Tailwind CSS  
**Exchange data:** Binance Spot (existing dashboard) and public Binance USDⓈ-M Futures endpoints (research data)

> **Important status:** ACTP is currently a market-analysis and research platform, not an autonomous live-trading bot. The Futures downloader and simulators use public market data and local CSV files; they do not place orders, read account balances, or need Binance API keys. A positive backtest does not guarantee future results.

---

## 1. What ACTP contains today

### A. Existing crypto dashboard

- React/Vite dashboard with a dark interface.
- CoinGecko market overview for the top market-cap coins.
- Coin search and locally persisted watchlist.
- Top gainers and losers.
- Coin price sparklines.
- BUY/SELL/HOLD-style signal display and confidence/reason fields.
- Backend API endpoints for market data, signals, Fear & Greed and trade-history display.
- RSI, MACD and EMA indicator/signal code.
- Telegram alert service and a 30-minute per-symbol/signal cooldown mechanism.
- Local JSON-based history/alert-state helpers.

**Live dashboard note:** the existing dashboard calls CoinGecko, Binance Spot and Alternative.me endpoints. Those panels need an internet connection and may be affected by provider rate limits or outages. The dashboard polls market data periodically; do not mistake a cached/old display for live market data.

### B. Futures market-data and historical-data foundation

- Read-only Binance USDⓈ-M Futures market-data client.
- Public historical OHLCV candle download using the Futures /fapi/v1/klines endpoint.
- Historical funding-rate download using /fapi/v1/fundingRate.
- UTC timestamp handling, pagination, chronological sorting and end-exclusive date ranges.
- CSV output for candles and funding events.
- No private account endpoints and no exchange order placement.

### C. Adaptive strategy research

- Market-regime classification using ADX, ATR, EMA, Bollinger Bands, RSI and relative volume.
- Regime labels include trend-up, trend-down, range, breakout-up, breakout-down and uncertain.
- Adaptive strategy hypotheses include trend pullback, breakout, momentum and mean reversion.
- HOLD/no-trade is a valid outcome.
- Separate risk-policy prechecks for daily loss, drawdown, maximum positions, trade risk and leverage.

### D. Backtesting and Futures simulation

- OHLC backtester with next-candle-open signal execution.
- Conservative stop-first assumption if stop and target are both touched in one candle.
- Research-only isolated-margin Futures simulator.
- Taker fee, slippage, funding-event and estimated liquidation calculations.
- End-of-data position closure and trade/equity reporting.
- Chronological train/validation/test split helper with segment-isolated metrics.
- Next-candle-open execution and equity marking corrected to avoid pre-entry marking.
- Automated backend tests and GitHub Actions workflow.

**Simulation limitations:** the Futures simulator is not Binance-exact. It does not fully model mark-price liquidation, maintenance-margin tiers, order-book spread/depth, partial fills, exchange precision/minimums, latency, ADL, insurance fund or cross-margin portfolio effects. Funding event ordering inside a candle is approximated. Treat all results as research estimates.

### E. Phase 7 — Strategy Performance Laboratory

The Phase 7 lab compares five fixed strategy implementations:

1. Adaptive
2. EMA trend crossover
3. Breakout
4. Momentum
5. Mean reversion

It evaluates chronological 60% train / 20% validation / 20% test windows, with prior candles used for indicator warm-up and entries gated to the active segment. Each segment starts with fresh virtual equity.

Two cost scenarios are included:
- Base taker fee, slippage and funding assumptions.
- Stress case with 2x taker fees, 2x slippage and 1.5x funding rates.

Metrics include net return, maximum drawdown, trade count, win rate, profit factor, expectancy, average win/loss, annualized Sharpe and Sortino estimates, recovery factor, estimated liquidations, funding paid and fees paid.

The CLI accepts multiple symbol/timeframe datasets (including 15m, 1h and 4h) and creates:
- strategy_lab_results.csv
- strategy_lab_regime_attribution.csv
- strategy_lab_report.json

Each completed trade is also attributed to the market regime visible at the signal candle close before entry. This helps identify whether a strategy behaves differently in trends, ranges and breakouts.

Do not tune strategies against the final test period. Compare stability across symbols, timeframes, market regimes and stressed costs; do not choose a strategy only because it has the highest historical return.

---

## 2. Repository layout

~~~text
ACTP/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI market/signal/Fear & Greed routes
│   │   ├── backtesting/          # Backtest engines, research and Phase 7 lab
│   │   ├── exchange/             # Public Binance Futures data clients
│   │   ├── indicators/           # RSI, MACD, EMA and signal indicators
│   │   ├── intelligence/         # Market regime/features
│   │   ├── risk/                 # Research risk prechecks
│   │   ├── routes/               # History API
│   │   ├── services/             # Market data, alerts, history and Telegram
│   │   └── strategies/           # Adaptive strategy rules
│   ├── tests/
│   ├── data/                     # Local CSV datasets (not committed)
│   ├── reports/                  # Local research reports (not committed)
│   ├── requirements.txt
│   ├── download_futures_history.py
│   ├── run_futures_backtest.py
│   ├── run_research.py
│   └── run_strategy_lab.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   ├── package.json
│   └── package-lock.json
├── .github/workflows/backend-tests.yml
├── .env.example
└── ACTP_PROJECT_GUIDE.md
~~~

---

## 3. Requirements

### Recommended development machine

- Windows 10/11, Linux or macOS (64-bit).
- Python 3.12.
- Node.js 22 LTS recommended for the Vite frontend.
- Git.
- At least 8 GB RAM recommended.
- SSD recommended.
- Internet is needed to clone the repository, install dependencies and download market data. Once dependencies and CSV data are present locally, historical research can run without internet.

### Backend installation (Windows PowerShell)

Clone the repository and enter the backend directory:

~~~powershell
git clone https://github.com/userDevNull/ACTP.git
cd ACTP
cd backend

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

If PowerShell blocks activation, use Command Prompt:

~~~cmd
.venv\Scripts\activate.bat
~~~

Linux/macOS activation:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

### Optional environment configuration

From the repository root:

~~~powershell
Copy-Item .env.example .env
~~~

Historical CSV research does not require a .env file. Do not put exchange secrets into this project. The current Futures research tools use public endpoints only. Telegram fields are optional; only configure them with a newly generated private token if you intentionally use Telegram alerts.

### Frontend installation

Open a second terminal at the repository root:

~~~powershell
cd frontend
npm ci
npm run dev
~~~

Open the local Vite address printed in the terminal (normally http://localhost:5173). The frontend API client currently points to http://127.0.0.1:8000.

### Start the FastAPI backend

Open another terminal at the repository root:

~~~powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

API health/root endpoint: http://127.0.0.1:8000/  
Interactive API docs: http://127.0.0.1:8000/docs

The local dashboard can start without internet, but its live market panels will not receive new CoinGecko/Binance/Alternative.me data while offline. The historical CSV research workflow below is the offline-capable part.

---

## 4. Run historical Futures research offline

### Step 1 — Download the data while internet is available

Run from ACTP/backend:

~~~powershell
python download_futures_history.py --symbol BTCUSDT --interval 15m --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol ETHUSDT --interval 15m --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol BTCUSDT --interval 1h --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol ETHUSDT --interval 1h --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol BTCUSDT --interval 4h --start 2023-01-01 --end 2025-01-01 --output data
python download_futures_history.py --symbol ETHUSDT --interval 4h --start 2023-01-01 --end 2025-01-01 --output data
~~~

The end date is exclusive. Candle and funding CSV files are saved in backend/data/. The data folder is intentionally excluded from Git.

### Step 2 — Transfer data to an offline computer

Copy the required CSV files to the same relative backend/data/ folder on the offline machine using a USB drive or another approved transfer method. Keep candle and funding files together and preserve their filenames.

### Step 3 — Run the lab with no network connection

From ACTP/backend:

~~~powershell
python run_strategy_lab.py --dataset "BTCUSDT,1h,data/BTCUSDT_1h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "ETHUSDT,1h,data/ETHUSDT_1h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --dataset "BTCUSDT,4h,data/BTCUSDT_4h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "ETHUSDT,4h,data/ETHUSDT_4h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --output-dir reports/phase7
~~~

Optional parameters:

~~~text
--equity 500
--leverage 1
--risk 0.005
--fee 0.0005
--slippage 0.0005
--maintenance-margin 0.005
~~~

The defaults are conservative research assumptions, not a recommendation or a promise of safety. The simulator is approximate.

### Step 4 — Open reports

- Open backend/reports/phase7/strategy_lab_results.csv in Excel or LibreOffice.
- Open backend/reports/phase7/strategy_lab_regime_attribution.csv to compare results across market regimes.
- Open backend/reports/phase7/strategy_lab_report.json in a code editor for the complete output.
- Compare train and validation results first. Keep the final test set untouched until choices are frozen.

### Run one dataset only

~~~powershell
python run_strategy_lab.py --dataset "BTCUSDT,1h,data/BTCUSDT_1h_futures_klines.csv,data/BTCUSDT_futures_funding.csv"
~~~

---

## 5. Use ACTP with GitHub

### Get the latest stable main branch

~~~bash
git clone https://github.com/userDevNull/ACTP.git
cd ACTP
git checkout main
git pull origin main
~~~

### Get the Phase 7 development branch

~~~bash
git fetch origin
git checkout feat/phase-7-strategy-lab
git pull origin feat/phase-7-strategy-lab
~~~

### Contribute changes safely

Create your own branch instead of editing main directly:

~~~bash
git checkout feat/phase-7-strategy-lab
git pull origin feat/phase-7-strategy-lab
git checkout -b feature/my-change
~~~

After making and testing changes:

~~~bash
git status
git add backend/
git commit -m "Describe the change"
git push -u origin feature/my-change
~~~

Then open a Pull Request on GitHub into the appropriate development branch. Review the diff and wait for the GitHub Actions tests to pass before merging.

### GitHub Actions

The backend workflow runs pytest for relevant pushes and pull requests. Check the Actions tab:

https://github.com/userDevNull/ACTP/actions

GitHub stores the source code and runs automated tests. It does not store your ignored local CSV datasets, generated reports, .env files or virtual environment. Keep those files backed up separately.

---

## 6. Offline dependency preparation

Python packages and Node packages must be prepared before the target computer is disconnected.

### Python wheelhouse

On an internet-connected computer with the same operating system, Python version and architecture as the offline machine:

~~~powershell
cd ACTP\backend
python -m pip download -r requirements.txt -d wheelhouse
~~~

Transfer the wheelhouse folder and project to the offline machine. Then install:

~~~powershell
python -m pip install --no-index --find-links wheelhouse -r requirements.txt
~~~

A wheelhouse should be prepared for the target OS/Python version; compiled packages may not be portable between Windows and Linux or between Python versions.

### Frontend packages

On the connected machine, run npm ci in frontend/. For a fully offline frontend installation, transfer the installed node_modules folder to a machine with the same OS/architecture and compatible Node.js version, or prepare and transfer a complete npm cache before disconnecting. The simplest offline research-only setup does not require Node.js or the frontend at all.

---

## 7. Tests

From ACTP/backend with the virtual environment active:

~~~powershell
python -m pytest -q
~~~

The same command is used by GitHub Actions. A passing test suite checks the implemented code paths; it does not prove strategy profitability or exchange-execution accuracy.

---

## 8. Security and operational cautions

- Never commit .env, API keys, bot tokens, chat IDs, private data or account exports.
- The repository's .gitignore excludes local secrets, virtual environments, caches, datasets and generated reports.
- A secret removed from the latest commit can still exist in old Git history. If a token was exposed, revoke/regenerate it and separately clean the Git history; simply deleting the file is not enough.
- Do not grant trading or withdrawal permissions to any API key for this research project.
- Do not use high leverage to compensate for weak strategy results.
- No martingale, loss-doubling or unlimited averaging down.
- No live execution is implemented in this version. Do not treat a signal as an instruction to trade.
- Preserve raw historical CSVs and record the symbol, timeframe, date range and cost assumptions for each experiment.

---

## 9. Current limitations and next work

- The live dashboard still relies on external market-data services and has no complete offline market-data cache.
- The strategy performance lab is a research CLI; it is not yet integrated as a dashboard page.
- Futures simulation approximates liquidation, funding event ordering and fills; it is not a replica of Binance's matching or margin engine.
- The risk policy is a separate precheck and is not yet integrated into a live execution engine.
- No private Binance account connection, order placement, position management or live trading is enabled.
- Next research improvements should include benchmark comparisons, sensitivity analysis and report visualizations before any execution work. Phase 9 now adds a trade-level bootstrap diagnostic; it does not replace chronological out-of-sample validation.

## 11. Phase 9 — Trade-level bootstrap robustness

Phase 9 adds a deterministic, offline bootstrap diagnostic to each Phase 7 strategy/segment/cost-scenario experiment. It uses only completed trade net PnL values from that experiment and resamples them with replacement for a configurable number of paths (default 1,000). The random seed is configurable and defaults to 42.

From ACTP/backend, run the existing Phase 7 matrix with the new robustness options:

~~~powershell
python run_strategy_lab.py --dataset "BTCUSDT,1h,data/BTCUSDT_1h_futures_klines.csv,data/BTCUSDT_futures_funding.csv" --dataset "ETHUSDT,1h,data/ETHUSDT_1h_futures_klines.csv,data/ETHUSDT_futures_funding.csv" --monte-carlo-simulations 5000 --seed 123 --output-dir reports/phase9
~~~

Additional output:
- reports/phase9/strategy_lab_monte_carlo.csv — one bootstrap summary per symbol, timeframe, strategy, segment and cost scenario
- strategy_lab_report.json — includes the same results under `monte_carlo` and records simulation count and seed

Reported fields include 5th/median/95th percentile final equity, confidence interval bounds, probability of ending below initial equity, probability of crossing zero equity, and median/95th percentile maximum drawdown. The default seed makes results reproducible for identical inputs and settings.

**Critical limitation:** this is a trade-level bootstrap approximation, not a market-path simulation or forecast. It resamples completed net PnL with replacement and ignores chronological/serial dependence, overlapping exposure, changing position sizes, regime shifts, and bar-level execution/stop/liquidation paths. It must be interpreted alongside the untouched chronological test segment, multiple symbols/timeframes and stressed transaction costs. No new Python package is required; existing NumPy and pandas are used.

**Development principle:** establish reproducible evidence, cost-aware positive expectancy and controlled drawdown before considering paper trading or real-money execution.

---

## 10. Phase 8 — Offline Market Intelligence (initial implementation)

The Phase 8 diagnostic engine uses existing pandas and NumPy dependencies (no new Python packages needed). It calculates causal, closed-candle market regime classifications, rolling realized volatility, relative volatility expansion/contraction, ADX trend strength, ATR percentage, relative volume and volume-confirmed 20-candle breakouts. Warm-up/insufficient data is classified as UNCERTAIN.

With historical candle CSVs downloaded earlier, run from ACTP/backend:

~~~powershell
python run_market_intelligence.py --candles data/BTCUSDT_1h_futures_klines.csv --output-dir reports/phase8
~~~

Outputs:
- reports/phase8/market_diagnostics.csv — one row per candle
- reports/phase8/market_summary.json — latest state, regime counts, transition probabilities and persistence summary
- reports/phase8/regime_transition_matrix.csv — counts of transitions from each regime to the next
- reports/phase8/regime_transition_probabilities.csv — row-normalized transition probabilities
- reports/phase8/multi_timeframe_consensus.csv — optional closed-candle-aligned regime agreement across timeframes
- reports/phase8/regime_persistence.csv — episode counts and average, median and maximum duration in candles

This tool works without internet once Python dependencies and historical CSVs are present. It is diagnostic research, not a BUY/SELL signal or live execution. The existing dashboard still needs internet for live prices.

**Interpretation caution:** transition probabilities and duration statistics are retrospective summaries of the entire supplied sample. They are not causal live features and must not be used as if known at the beginning of that sample. Duration is measured in candles; convert to clock time using the dataset timeframe.

### Multi-timeframe agreement

Pass at least two timeframe CSVs to the same CLI. Input candle timestamps are interpreted as candle-open times; a timeframe's regime becomes available only after that candle's close. The tool aligns the latest completed higher-timeframe regime to each lower-timeframe close, preventing unfinished 4h candles from leaking into 1h observations.

~~~powershell
python run_market_intelligence.py --timeframe-dataset "1h,data/BTCUSDT_1h_futures_klines.csv" --timeframe-dataset "4h,data/BTCUSDT_4h_futures_klines.csv" --output-dir reports/phase8
~~~

The output `multi_timeframe_consensus.csv` contains each timeframe's available regime, the majority consensus and the agreement ratio. `MIXED` means no regime has a strict majority; `UNCERTAIN` means no timeframe has a classified regime. This is historical diagnostic context, not an entry signal. The multi-timeframe alignment assumes each CSV's timestamps mark candle opens and that the source candles are complete and correctly ordered.

### Dependency and file maintenance

- backend/requirements.txt contains pandas, NumPy and pytest already needed by Phase 8; no new dependency was required.
- .gitignore excludes backend/reports/ and backend/data/ so historical datasets and reports remain local.
- Backend tests include Phase 8 causal no-lookahead checks.
