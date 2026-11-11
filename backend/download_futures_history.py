"""Download public Binance USDⓈ-M Futures history to local CSV files.

Example:
  python download_futures_history.py --symbol BTCUSDT --interval 1h \
      --start 2024-01-01 --end 2025-01-01 --output data
"""
from __future__ import annotations

import argparse

from app.exchange.historical_data import (
    download_funding_rates,
    download_klines,
    save_market_history,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Binance Futures research data")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--start", required=True, help="UTC start date/time")
    parser.add_argument("--end", required=True, help="UTC end date/time (exclusive)")
    parser.add_argument("--output", default="data")
    args = parser.parse_args()

    candles = download_klines(args.symbol, args.interval, args.start, args.end)
    funding = download_funding_rates(args.symbol, args.start, args.end)
    candle_path, funding_path = save_market_history(
        candles, funding, args.output, args.symbol, args.interval
    )
    print(f"Candles: {len(candles)} -> {candle_path}")
    print(f"Funding events: {len(funding)} -> {funding_path}")


if __name__ == "__main__":
    main()
