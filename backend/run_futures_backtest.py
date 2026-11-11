"""Run the Futures simulator on locally downloaded candle and funding CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.backtesting.futures_simulator import FuturesConfig, run_futures_backtest
from app.strategies.adaptive import backtest_signal


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Binance Futures simulation")
    parser.add_argument("--candles", required=True, type=Path)
    parser.add_argument("--funding", type=Path, default=None)
    parser.add_argument("--equity", type=float, default=500.0)
    parser.add_argument("--leverage", type=float, default=1.0)
    parser.add_argument("--risk", type=float, default=0.005)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--maintenance-margin", type=float, default=0.005)
    args = parser.parse_args()

    if not args.candles.is_file():
        parser.error(f"Candle file not found: {args.candles}")
    candles = pd.read_csv(args.candles)
    funding = None
    if args.funding:
        if not args.funding.is_file():
            parser.error(f"Funding file not found: {args.funding}")
        funding = pd.read_csv(args.funding)

    config = FuturesConfig(
        initial_equity=args.equity,
        leverage=args.leverage,
        risk_fraction=args.risk,
        taker_fee_rate=args.fee,
        slippage_rate=args.slippage,
        maintenance_margin_rate=args.maintenance_margin,
    )
    result = run_futures_backtest(candles, backtest_signal, funding, config)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
