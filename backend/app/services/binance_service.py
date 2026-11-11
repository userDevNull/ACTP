import requests

BASE_URL = "https://api.binance.com"


def get_klines(symbol="BTCUSDT", interval="1h", limit=100):

    try:

        url = f"{BASE_URL}/api/v3/klines"

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException:

        return []