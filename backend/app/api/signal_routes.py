from fastapi import APIRouter
from app.services.binance_service import get_klines
from app.signals.signal_engine import generate_signal

router = APIRouter()


@router.get("/signal/{symbol}")
def get_signal(symbol: str):

    candles = get_klines(symbol=symbol)

    if not candles or not isinstance(candles, list):

        return {
            "symbol": symbol,
            "signal": "UNAVAILABLE",
            "confidence": 0,
            "rsi": 0,
            "macd": 0,
            "ema": 0,
            "price": 0,
            "reasons": [
                "Market data unavailable"
            ]
        }

    try:

        close_prices = [
            float(candle[4])
            for candle in candles
        ]

        signal = generate_signal(close_prices)

        return {
            "symbol": symbol,
            **signal
        }

    except Exception as e:

        print("Signal Engine Error:", e)

        return {
            "symbol": symbol,
            "signal": "ERROR",
            "confidence": 0,
            "rsi": 0,
            "macd": 0,
            "ema": 0,
            "price": 0,
            "reasons": [
                "Signal calculation failed"
            ]
        }