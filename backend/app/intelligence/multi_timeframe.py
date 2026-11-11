"""Causal multi-timeframe regime alignment using candle close times."""
from __future__ import annotations

import pandas as pd

from app.intelligence.market_analysis import REGIMES

TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360,
    "8h": 480, "12h": 720, "1d": 1440, "1w": 10080,
}


def multi_timeframe_consensus(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Align latest completed regime per timeframe onto the fastest timeframe.

    Input timestamps are candle OPEN times. A timeframe's regime is only
    available at its candle CLOSE, preventing unfinished higher-timeframe
    candles from leaking into lower-timeframe rows.
    """
    if len(frames) < 2:
        raise ValueError("At least two timeframe datasets are required")
    unknown = sorted(set(frames) - set(TIMEFRAME_MINUTES))
    if unknown:
        raise ValueError(f"Unsupported timeframe(s): {', '.join(unknown)}")
    ordered = sorted(frames, key=lambda key: TIMEFRAME_MINUTES[key])
    base = ordered[0]
    base_frame = frames[base]
    if base_frame.empty:
        raise ValueError("Timeframe datasets cannot be empty")
    if "timestamp" not in base_frame or "market_regime" not in base_frame:
        raise ValueError("Each dataset requires timestamp and market_regime columns")

    base_close = pd.to_datetime(base_frame["timestamp"], utc=True) + pd.to_timedelta(
        TIMEFRAME_MINUTES[base], unit="min"
    )
    result = pd.DataFrame({"timestamp": base_close})
    result[f"regime_{base}"] = base_frame["market_regime"].astype(str).to_numpy()

    for timeframe in ordered[1:]:
        frame = frames[timeframe]
        if frame.empty or not {"timestamp", "market_regime"}.issubset(frame.columns):
            raise ValueError(f"{timeframe} dataset must contain timestamp and market_regime")
        closes = pd.to_datetime(frame["timestamp"], utc=True) + pd.to_timedelta(
            TIMEFRAME_MINUTES[timeframe], unit="min"
        )
        right = pd.DataFrame({
            "available_at": closes,
            f"regime_{timeframe}": frame["market_regime"].astype(str).to_numpy(),
        }).sort_values("available_at")
        if right["available_at"].duplicated().any():
            raise ValueError(f"{timeframe} timestamps must be unique")
        result = pd.merge_asof(
            result.sort_values("timestamp"), right,
            left_on="timestamp", right_on="available_at", direction="backward",
            allow_exact_matches=True,
        ).drop(columns="available_at")

    regime_columns = [f"regime_{timeframe}" for timeframe in ordered]
    def consensus(row):
        values = [value for value in row if value in REGIMES and value != "UNCERTAIN"]
        if not values:
            return "UNCERTAIN"
        counts = pd.Series(values).value_counts()
        return str(counts.index[0]) if counts.iloc[0] > len(values) / 2 else "MIXED"

    result["consensus_regime"] = result[regime_columns].apply(consensus, axis=1)
    result["agreement_ratio"] = result[regime_columns].apply(
        lambda row: (
            max(pd.Series([v for v in row if v in REGIMES and v != "UNCERTAIN"]).value_counts())
            / len([v for v in row if v in REGIMES and v != "UNCERTAIN"])
        ) if any(v in REGIMES and v != "UNCERTAIN" for v in row) else None,
        axis=1,
    )
    return result
