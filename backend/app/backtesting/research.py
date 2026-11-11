"""Chronological research evaluation helpers.

No hyperparameter search is performed here. The final test segment must remain
untouched until strategy choices are frozen.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.backtesting.engine import BacktestConfig, run_backtest
from app.strategies.adaptive import backtest_signal


@dataclass(frozen=True)
class DataSplits:
    train_end: int
    validation_end: int
    total: int


def chronological_splits(
    length: int,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
) -> DataSplits:
    if length < 100:
        raise ValueError("At least 100 candles are required for research splits")
    if not 0.5 <= train_fraction < 0.9:
        raise ValueError("train_fraction must be between 0.5 and 0.9")
    if not 0.05 <= validation_fraction < 0.4:
        raise ValueError("validation_fraction must be between 0.05 and 0.4")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("A non-empty final test segment is required")
    train_end = int(length * train_fraction)
    validation_end = int(length * (train_fraction + validation_fraction))
    if train_end < 70 or validation_end - train_end < 10 or length - validation_end < 10:
        raise ValueError("Splits are too small for warm-up and evaluation")
    return DataSplits(train_end, validation_end, length)


def _run_segment(
    data: pd.DataFrame,
    start: int,
    end: int,
    config: BacktestConfig,
) -> dict:
    segment = data.iloc[:end].reset_index(drop=True)

    def gated_strategy(history: pd.DataFrame, index: int) -> int:
        # Preserve pre-segment history for indicator warm-up, but do not trade
        # until the requested segment begins.
        if index < start:
            return 0
        return backtest_signal(history, index)

    result = run_backtest(segment, gated_strategy, config)
    segment_trades = [
        trade for trade in result["trades"]
        if trade["entry_index"] >= start and trade["exit_index"] <= end - 1
    ]
    # A trade opened before the segment or closed outside it is not counted
    # in the segment metrics; the gate prevents new entries before start.
    return {
        "start_index": start,
        "end_index_exclusive": end,
        "summary": result["summary"],
        "trades": segment_trades,
    }


def evaluate_adaptive(
    data: pd.DataFrame,
    config: BacktestConfig | None = None,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
) -> dict:
    """Evaluate adaptive rules on chronological train/validation/test windows."""
    cfg = config or BacktestConfig()
    splits = chronological_splits(len(data), train_fraction, validation_fraction)
    return {
        "warning": (
            "Research only. Do not tune against the final test segment. "
            "Fees, slippage and funding assumptions may not match live fills."
        ),
        "splits": {
            "train": _run_segment(data, 0, splits.train_end, cfg),
            "validation": _run_segment(data, splits.train_end, splits.validation_end, cfg),
            "test": _run_segment(data, splits.validation_end, splits.total, cfg),
        },
    }
