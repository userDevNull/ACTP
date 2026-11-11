"""Run the adaptive strategy research pipeline on a local Futures OHLCV CSV.

Expected columns: open, high, low, close, volume. Optional timestamp column
will be sorted chronologically. Example:
    python run_research.py data/BTCUSDT_1h.csv --symbol BTCUSDT
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.backtesting.engine import BacktestConfig
from app.backtesting.research import evaluate_adaptive


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline adaptive strategy research")
    parser.add_argument("csv", type=Path, help="CSV containing chronological OHLCV candles")
    parser.add_argument("--symbol", default="UNSPECIFIED")
    parser.add_argument("--initial-cash", type=float, default=500.0)
    parser.add_argument("--fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-rate", type=float, default=0.0005)
    parser.add_argument("--funding-per-bar", type=float, default=0.0)
    args = parser.parse_args()

    if not args.csv.is_file():
        parser.error(f"CSV file not found: {args.csv}")

    frame = pd.read_csv(args.csv)
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
        frame = frame.sort_values("timestamp").reset_index(drop=True)

    config = BacktestConfig(
        initial_cash=args.initial_cash,
        fee_rate=args.fee_rate,
        slippage_rate=args.slippage_rate,
        funding_rate_per_bar=args.funding_per_bar,
    )
    report = evaluate_adaptive(frame, config)
    report["symbol"] = args.symbol
    report["source_file"] = args.csv.name
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
