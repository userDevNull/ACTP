import pandas as pd
import pytest

from app.exchange.binance_futures_market import (
    BinanceFuturesDataError,
    get_futures_klines,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payloads.pop(0))


def candle(open_ms, close_ms, close="101"):
    return [
        open_ms, "100", "102", "99", close, "12",
        close_ms, "1200", 100, "5", "500", "0"
    ]


def test_uses_futures_endpoint_and_returns_closed_candles():
    # The first candle is closed; the second is still forming at server time.
    session = FakeSession([
        [candle(0, 59_999), candle(60_000, 119_999)],
        {"serverTime": 100_000},
    ])
    frame = get_futures_klines("BTCUSDT", "1m", 2, session=session)

    assert len(frame) == 1
    assert frame.iloc[0]["close"] == 101
    assert "/fapi/v1/klines" in session.calls[0][0]
    assert "/fapi/v1/time" in session.calls[1][0]
    assert isinstance(frame.iloc[0]["open_time"], pd.Timestamp)


def test_rejects_bad_interval():
    with pytest.raises(ValueError):
        get_futures_klines("BTCUSDT", "7m", 10, closed_only=False)


def test_rejects_malformed_payload():
    session = FakeSession([{"code": -1121, "msg": "Invalid symbol"}])
    with pytest.raises(BinanceFuturesDataError):
        get_futures_klines("BTCUSDT", "1h", 10, closed_only=False, session=session)
