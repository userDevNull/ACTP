import requests
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = os.getenv("COINGECKO_BASE_URL")


def get_market_data():

    try:

        url = f"{BASE_URL}/coins/markets"

        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 10,
            "page": 1,
            "sparkline": "true",
            "price_change_percentage": "24h"
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:

        print("CoinGecko API Error:", e)

        return []