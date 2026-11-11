# Binance USDⓈ-M Futures market data

This client calls public Binance Futures endpoints:
- `GET /fapi/v1/klines` for OHLCV
- `GET /fapi/v1/time` to exclude an in-progress candle
- `GET /fapi/v1/fundingRate` for the latest published funding record

It is read-only and does not accept API credentials. It cannot access account balances,
positions, place orders, or change leverage/margin settings.

Use `closed_only=True` for indicator calculations and historical strategy evaluation.
Do not silently mix Spot candles from `api.binance.com/api/v3/klines` with Futures data.

Funding-rate history is returned as a latest-record snapshot here; a proper backtest must
align funding timestamps with position holding periods. Exchange filters, mark price,
premium index, order book, and maintenance-margin tiers are not yet implemented.
