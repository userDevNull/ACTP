"""Historical USDⓈ-M Futures candles and funding-rate downloader.

Public endpoints only. CSV files are local research data, never trading credentials.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from app.exchange.binance_futures_market import (
    BASE_URL,
    KLINES_PATH,
    SUPPORTED_INTERVALS,
    BinanceFuturesDataError,
)

KLINE_LIMIT = 1500
FUNDING_LIMIT = 1000


def download_klines(
    symbol: str,
    interval: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    session: Any = requests,
    pause_seconds: float = 0.15,
) -> pd.DataFrame:
    """Download candles in chronological pages between UTC start and end.

    The end timestamp is exclusive. Incomplete candles are excluded.
    """
    symbol = symbol.upper()
    if not symbol.isalnum() or interval not in SUPPORTED_INTERVALS:
        raise ValueError("Invalid symbol or interval")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    else:
        start_ts = start_ts.tz_convert("UTC")
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")
    else:
        end_ts = end_ts.tz_convert("UTC")
    if start_ts >= end_ts:
        raise ValueError("start must be earlier than end")

    start_ms = int(start_ts.timestamp() * 1000)
    end_ms = int(end_ts.timestamp() * 1000)
    rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        try:
            response = session.get(
                f"{BASE_URL}{KLINES_PATH}",
                params={
                    "symbol": symbol, "interval": interval,
                    "startTime": cursor, "endTime": end_ms - 1,
                    "limit": KLINE_LIMIT,
                },
                timeout=20,
            )
            response.raise_for_status()
            batch = response.json()
        except requests.RequestException as exc:
            raise BinanceFuturesDataError("Historical kline download failed") from exc
        if not isinstance(batch, list):
            raise BinanceFuturesDataError("Unexpected historical kline response")
        if not batch:
            break
        rows.extend(batch)
        last_open = int(batch[-1][0])
        next_cursor = last_open + 1
        if next_cursor <= cursor:
            raise BinanceFuturesDataError("Historical kline pagination did not advance")
        cursor = next_cursor
        if len(batch) < KLINE_LIMIT:
            break
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    columns = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    if not rows:
        return pd.DataFrame(columns=[
            "timestamp", "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote",
        ])
    frame = pd.DataFrame(rows, columns=columns).drop_duplicates(subset=["open_time"])
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
    numeric = ["open", "high", "low", "close", "volume", "quote_volume",
               "trades", "taker_buy_base", "taker_buy_quote"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame = frame.sort_values("open_time").reset_index(drop=True)
    frame = frame[(frame["open_time"] >= start_ts) & (frame["open_time"] < end_ts)]
    frame = frame[frame["close_time"] < end_ts].reset_index(drop=True)
    frame["timestamp"] = frame["open_time"]
    return frame[[
        "timestamp", "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote",
    ]]


def download_funding_rates(
    symbol: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    session: Any = requests,
    pause_seconds: float = 0.15,
) -> pd.DataFrame:
    """Download historical funding events, timestamped in UTC."""
    symbol = symbol.upper()
    if not symbol.isalnum():
        raise ValueError("Invalid symbol")
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    start_ts = start_ts.tz_localize("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
    end_ts = end_ts.tz_localize("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
    if start_ts >= end_ts:
        raise ValueError("start must be earlier than end")
    start_ms, end_ms = int(start_ts.timestamp() * 1000), int(end_ts.timestamp() * 1000)
    cursor = start_ms
    rows: list[dict] = []
    while cursor < end_ms:
        try:
            response = session.get(
                f"{BASE_URL}/fapi/v1/fundingRate",
                params={"symbol": symbol, "startTime": cursor, "endTime": end_ms - 1,
                        "limit": FUNDING_LIMIT},
                timeout=20,
            )
            response.raise_for_status()
            batch = response.json()
        except requests.RequestException as exc:
            raise BinanceFuturesDataError("Historical funding download failed") from exc
        if not isinstance(batch, list):
            raise BinanceFuturesDataError("Unexpected funding-rate response")
        if not batch:
            break
        rows.extend(batch)
        last_time = int(batch[-1]["fundingTime"])
        if last_time < cursor:
            raise BinanceFuturesDataError("Funding pagination did not advance")
        cursor = last_time + 1
        if len(batch) < FUNDING_LIMIT:
            break
        if pause_seconds > 0:
            time.sleep(pause_seconds)

    if not rows:
        return pd.DataFrame(columns=["funding_time", "funding_rate", "symbol"])
    frame = pd.DataFrame(rows).drop_duplicates(subset=["fundingTime"])
    frame["funding_time"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True)
    frame["funding_rate"] = pd.to_numeric(frame["fundingRate"], errors="raise")
    return frame[["funding_time", "funding_rate", "symbol"]].sort_values("funding_time").reset_index(drop=True)


def save_market_history(
    candles: pd.DataFrame,
    funding: pd.DataFrame,
    output_dir: str | Path,
    symbol: str,
    interval: str,
) -> tuple[Path, Path]:
    """Persist candle and funding data as separate CSV files."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    candle_path = directory / f"{symbol}_{interval}_futures_klines.csv"
    funding_path = directory / f"{symbol}_futures_funding.csv"
    candles.to_csv(candle_path, index=False)
    funding.to_csv(funding_path, index=False)
    return candle_path, funding_path
