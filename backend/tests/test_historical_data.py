import pandas as pd
import pytest

from app.exchange.historical_data import download_klines, download_funding_rates


class Response:
    def __init__(self, data):
        self.data = data
    def raise_for_status(self):
        return None
    def json(self):
        return self.data


class Session:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.results.pop(0))


def test_download_klines_normalizes_utc_and_columns():
    row = [1704067200000, "100", "102", "99", "101", "10",
           1704070799999, "1000", 50, "4", "400", "0"]
    session = Session([[row]])
    result = download_klines("BTCUSDT", "1h", "2024-01-01", "2024-01-02",
                             session=session, pause_seconds=0)
    assert len(result) == 1
    assert result.iloc[0]["close"] == 101
    assert result.iloc[0]["timestamp"].tz is not None
    assert "/fapi/v1/klines" in session.calls[0][0]


def test_download_funding_rates_parses_event_timestamp():
    session = Session([[{"symbol":"BTCUSDT","fundingTime":1704096000000,"fundingRate":"0.0001"}]])
    result = download_funding_rates("BTCUSDT", "2024-01-01", "2024-01-03",
                                    session=session, pause_seconds=0)
    assert len(result) == 1
    assert result.iloc[0]["funding_rate"] == pytest.approx(0.0001)
    assert result.iloc[0]["funding_time"].tz is not None
