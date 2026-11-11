"""Dataset preflight and cross-market generalization summaries for ACTP research."""
from __future__ import annotations

from statistics import median

import numpy as np
import pandas as pd

TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480,
    "12h": 720, "1d": 1440, "1w": 10080,
}
CANDLE_COLUMNS = ("timestamp", "open", "high", "low", "close", "volume")


def audit_market_dataset(
    candles: pd.DataFrame,
    timeframe: str,
    funding: pd.DataFrame | None = None,
) -> dict:
    """Audit candle/funding integrity without silently repairing source data.

    Gaps and zero-volume bars are warnings; duplicate timestamps, invalid OHLCV,
    missing columns and non-finite values are errors that should block research.
    """
    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    errors: list[str] = []
    warnings: list[str] = []
    missing = sorted(set(CANDLE_COLUMNS) - set(candles.columns))
    if missing:
        errors.append(f"Missing candle columns: {', '.join(missing)}")
        return {"status": "fail", "rows": len(candles), "errors": errors,
                "warnings": warnings}

    frame = candles.loc[:, CANDLE_COLUMNS].copy()
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        errors.append(f"{int(timestamps.isna().sum())} invalid timestamps")
    valid_ts = timestamps.dropna()
    if valid_ts.duplicated().any():
        errors.append(f"{int(valid_ts.duplicated(keep=False).sum())} rows have duplicate timestamps")
    if len(valid_ts) > 1 and not valid_ts.is_monotonic_increasing:
        warnings.append("Source timestamps are not ascending; the lab sorts them before simulation")

    numeric = frame.loc[:, ("open", "high", "low", "close", "volume")].apply(
        pd.to_numeric, errors="coerce"
    )
    values = numeric.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        errors.append("OHLCV contains missing or non-finite numeric values")
    else:
        positive = (numeric.loc[:, ("open", "high", "low", "close")] > 0).all(axis=1)
        if not positive.all():
            errors.append(f"{int((~positive).sum())} rows contain non-positive prices")
        valid_ohlc = (
            (numeric["high"] >= numeric[["open", "close", "low"]].max(axis=1))
            & (numeric["low"] <= numeric[["open", "close", "high"]].min(axis=1))
            & (numeric["high"] >= numeric["low"])
        )
        if not valid_ohlc.all():
            errors.append(f"{int((~valid_ohlc).sum())} rows violate OHLC high/low constraints")
        if (numeric["volume"] < 0).any():
            errors.append(f"{int((numeric['volume'] < 0).sum())} rows contain negative volume")
        if (numeric["volume"] == 0).any():
            warnings.append(f"{int((numeric['volume'] == 0).sum())} rows have zero volume")

    gaps = 0
    largest_gap_minutes = 0.0
    if len(valid_ts) > 1:
        ordered = valid_ts.sort_values().drop_duplicates()
        delta_minutes = ordered.diff().dt.total_seconds().div(60).dropna()
        expected = TIMEFRAME_MINUTES[timeframe]
        gap_mask = delta_minutes > expected * 1.5
        gaps = int(gap_mask.sum())
        largest_gap_minutes = float(delta_minutes.max())
        if gaps:
            warnings.append(
                f"{gaps} timestamp gaps exceed 1.5x the expected {timeframe} interval"
            )

    funding_rows = 0
    if funding is not None and not funding.empty:
        missing_funding = sorted({"timestamp", "funding_rate"} - set(funding.columns))
        if missing_funding:
            errors.append(f"Missing funding columns: {', '.join(missing_funding)}")
        else:
            funding_rows = len(funding)
            funding_ts = pd.to_datetime(funding["timestamp"], utc=True, errors="coerce")
            rates = pd.to_numeric(funding["funding_rate"], errors="coerce")
            if funding_ts.isna().any() or not np.isfinite(rates.to_numpy(dtype=float)).all():
                errors.append("Funding contains invalid timestamps or non-finite rates")
            if funding_ts.dropna().duplicated().any():
                errors.append("Funding contains duplicate timestamps")

    start = valid_ts.min().isoformat() if not valid_ts.empty else None
    end = valid_ts.max().isoformat() if not valid_ts.empty else None
    if len(frame) < 100:
        errors.append("At least 100 candles are required")
    return {
        "status": "fail" if errors else ("warn" if warnings else "pass"),
        "rows": len(frame),
        "start": start,
        "end": end,
        "timeframe": timeframe,
        "funding_rows": funding_rows,
        "duplicate_timestamps": int(valid_ts.duplicated(keep=False).sum()),
        "gap_count": gaps,
        "largest_gap_minutes": round(largest_gap_minutes, 4),
        "errors": errors,
        "warnings": warnings,
    }


def build_cross_market_validation(
    results: list[dict],
    benchmarks: list[dict],
) -> list[dict]:
    """Summarize per-dataset out-of-sample consistency; never pool raw returns.

    Uses only the frozen test segment at base costs. Each symbol/timeframe is one
    independent comparison unit, so long datasets do not dominate by bar count.
    """
    test_rows = [
        row for row in results
        if row.get("segment") == "test" and row.get("cost_scenario") == "base_cost"
    ]
    benchmark_lookup = {
        (row.get("symbol"), row.get("timeframe"), row.get("segment"),
         row.get("cost_scenario"), row.get("benchmark")): row
        for row in benchmarks
    }
    grouped: dict[str, list[dict]] = {}
    rank_lookup: dict[tuple[str, str, str], int] = {}
    datasets: dict[tuple[str, str], list[dict]] = {}
    for row in test_rows:
        grouped.setdefault(str(row["strategy"]), []).append(row)
        datasets.setdefault((str(row.get("symbol")), str(row.get("timeframe"))), []).append(row)
    for (symbol, timeframe), dataset_rows in datasets.items():
        ordered = sorted(dataset_rows, key=lambda item: float(item["net_return_pct"]), reverse=True)
        for rank, item in enumerate(ordered, start=1):
            rank_lookup[(symbol, timeframe, str(item["strategy"]))] = rank

    output = []
    for strategy, rows in sorted(grouped.items()):
        excess = []
        returns = []
        drawdowns = []
        ranks = []
        positive = 0
        beat_spot = 0
        comparable = 0
        trades = 0
        for row in rows:
            ret = float(row["net_return_pct"])
            returns.append(ret)
            drawdowns.append(float(row["max_drawdown_pct"]))
            positive += int(ret > 0)
            trades += int(row.get("trades", 0))
            spot = benchmark_lookup.get((
                row.get("symbol"), row.get("timeframe"), "test", "base_cost",
                "buy_and_hold_spot",
            ))
            if spot is not None:
                comparable += 1
                edge = ret - float(spot["net_return_pct"])
                excess.append(edge)
                beat_spot += int(edge > 0)

        for row in rows:
            ranks.append(rank_lookup[(str(row.get("symbol")), str(row.get("timeframe")), strategy)])

        n = len(rows)
        output.append({
            "strategy": strategy,
            "test_datasets": n,
            "positive_test_datasets": positive,
            "positive_test_pct": round(positive / n * 100, 2) if n else 0.0,
            "beat_spot_datasets": beat_spot,
            "spot_comparisons": comparable,
            "beat_spot_pct": round(beat_spot / comparable * 100, 2) if comparable else None,
            "median_test_return_pct": round(median(returns), 4) if returns else None,
            "median_excess_vs_spot_pct": round(median(excess), 4) if excess else None,
            "median_test_drawdown_pct": round(median(drawdowns), 4) if drawdowns else None,
            "median_rank_within_dataset": round(median(ranks), 2) if ranks else None,
            "total_test_trades": trades,
            "interpretation": (
                "Insufficient dataset coverage" if n < 3
                else "Consistent positive tests" if positive / n >= 0.7
                else "Mixed or weak cross-market consistency"
            ),
        })
    return output
