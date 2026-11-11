"""Read-only Binance USDⓈ-M Futures market data client.

Uses public endpoints only. No API key, signing, account access, or order methods.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

BASE_URL = "https://fapi.binance.com"
KLINES_PATH = "/fapi/v1/klines"
TIME_PATH = "/fapi/v1/time"

SUPPORTED_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
}


class BinanceFuturesDataError(RuntimeError):
    """Raised when public Futures market data cannot be retrieved or parsed."""


def _validate_request(symbol: str, interval: str, limit: int) -> None:
    if not symbol or not symbol.isalnum() or symbol.upper() != symbol:
        raise ValueError("symbol must be uppercase alphanumeric, e.g. BTCUSDT")
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"Unsupported interval: {interval}")
    if not 1 <= limit <= 1500:
        raise ValueError("limit must be between 1 and 1500")


def get_server_time(session: Any = requests) -> int:
    """Return Binance server time in milliseconds."""
    try:
        response = session.get(f"{BASE_URL}{TIME_PATH}", timeout=10)
        response.raise_for_status()
        return int(response.json()["serverTime"])
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise BinanceFuturesDataError("Could not retrieve Binance Futures server time") from exc


def get_futures_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    limit: int = 500,
    *,
    closed_only: bool = True,
    session: Any = requests,
) -> pd.DataFrame:
    """Fetch OHLCV candles; by default exclude the still-forming last candle.

    Returned columns: open_time, open, high, low, close, volume, close_time,
    quote_volume, trades, taker_buy_base, taker_buy_quote.
    Timestamps are UTC-aware pandas datetimes.
    """
    symbol = symbol.upper()
    _validate_request(symbol, interval, limit)

    try:
        response = session.get(
            f"{BASE_URL}{KLINES_PATH}",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise BinanceFuturesDataError("Binance Futures klines request failed") from exc

    if not isinstance(payload, list):
        raise BinanceFuturesDataError("Unexpected Binance Futures kline response")

    columns = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    if not payload:
        return pd.DataFrame(columns=[
            "open_time", "open", "high", "low", "close", "volume", "close_time",
            "quote_volume", "trades", "taker_buy_base", "taker_buy_quote",
        ])

    try:
        frame = pd.DataFrame(payload, columns=columns)
        numeric = [
            "open", "high", "low", "close", "volume", "quote_volume",
            "trades", "taker_buy_base", "taker_buy_quote",
        ]
        for column in numeric:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
        frame = frame.drop(columns=["ignore"])
        frame = frame.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)
        if closed_only:
            now_ms = get_server_time(session)
            now = pd.to_datetime(now_ms, unit="ms", utc=True)
            frame = frame[frame["close_time"] < now].reset_index(drop=True)
        if (frame[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValueError("Non-positive OHLC price")
        if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
            raise ValueError("Invalid candle high")
        if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
            raise ValueError("Invalid candle low")
        return frame
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise BinanceFuturesDataError("Could not parse Binance Futures klines") from exc


def get_funding_rate(symbol: str = "BTCUSDT", *, session: Any = requests) -> dict:
    """Fetch the latest public funding-rate record for a USDⓈ-M contract."""
    symbol = symbol.upper()
    if not symbol or not symbol.isalnum():
        raise ValueError("symbol must be alphanumeric")
    try:
        response = session.get(
            f"{BASE_URL}/fapi/v1/fundingRate",
            params={"symbol": symbol, "limit": 1},
            timeout=10,
        )
        response.raise_for_status()
        records = response.json()
        if not isinstance(records, list) or not records:
            raise BinanceFuturesDataError("No funding-rate data returned")
        record = records[-1]
        return {
            "symbol": record["symbol"],
            "funding_rate": float(record["fundingRate"]),
            "funding_time": datetime.fromtimestamp(
                int(record["fundingTime"]) / 1000, tz=timezone.utc
            ).isoformat(),
        }
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, BinanceFuturesDataError):
            raise
        raise BinanceFuturesDataError("Could not retrieve Binance Futures funding rate") from exc
