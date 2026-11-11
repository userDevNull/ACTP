from app.services.telegram_service import send_telegram_message
from app.indicators.rsi import calculate_rsi
from app.indicators.macd import calculate_macd
from app.indicators.ema import calculate_ema
from app.services.history_service import save_trade
from app.services.alert_service import can_send_alert

def generate_signal(close_prices):

    current_price = close_prices[-1]

    rsi = calculate_rsi(close_prices)

    macd_data = calculate_macd(close_prices)

    ema = calculate_ema(close_prices)

    macd = macd_data["macd"]
    signal_line = macd_data["signal"]

    signal = "HOLD"

    confidence = 50

    reasons = []

    # RSI
    if rsi < 30:
        reasons.append("RSI Oversold")
        confidence += 10

    elif rsi > 70:
        reasons.append("RSI Overbought")
        confidence += 10

    # MACD
    if macd > signal_line:
        reasons.append("MACD Bullish")
        confidence += 10

    elif macd < signal_line:
        reasons.append("MACD Bearish")
        confidence += 10

    # EMA Trend
    if current_price > ema:
        reasons.append("Above EMA Trend")
        confidence += 15

    else:
        reasons.append("Below EMA Trend")

    # BUY Logic
    if (
        rsi < 30 and
        macd > signal_line and
        current_price > ema
    ):

        signal = "BUY"
        confidence = 90
        save_trade({
          "signal": signal,
          "confidence": confidence,
          "price": round(current_price, 2),
          "reasons": reasons
      })
        if can_send_alert("BTC", "BUY"):
            send_telegram_message(
                    f"""
                🚀 BUY SIGNAL

                Confidence: {confidence}%

                Reasons:
                {", ".join(reasons)}
                """
                )
        

    # SELL Logic
    elif (
        rsi > 70 and
        macd < signal_line and
        current_price < ema
    ):

        signal = "SELL"
        confidence = 90
        save_trade({
            "signal": signal,
            "confidence": confidence,
            "price": round(current_price, 2),
            "reasons": reasons
        })
        if can_send_alert("BTC", "SELL"):
            send_telegram_message(
                    f"""
                🚀 SELL SIGNAL

                Confidence: {confidence}%

                Reasons:
                {", ".join(reasons)}
                """
                )
        

    return {
        "signal": signal,
        "confidence": confidence,
        "rsi": round(rsi, 2),
        "macd": round(macd, 2),
        "ema": round(ema, 2),
        "price": round(current_price, 2),
        "reasons": reasons
    }