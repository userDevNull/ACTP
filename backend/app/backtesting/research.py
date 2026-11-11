"""Chronological research evaluation helpers.

No hyperparameter search is performed here. The final test segment must remain
untouched until strategy choices are frozen. Every segment starts with fresh
virtual cash while retaining prior candles only for indicator warm-up.
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


def _segment_summary(
    equity_curve: list[dict],
    trades: list[dict],
    initial_cash: float,
) -> dict:
    values = pd.Series([float(point["equity"]) for point in equity_curve], dtype=float)
    if values.empty:
        final_equity = initial_cash
        max_drawdown_pct = 0.0
    else:
        final_equity = float(values.iloc[-1])
        peaks = values.cummax()
        max_drawdown_pct = float(((values / peaks) - 1.0).min() * 100.0)
    pnl = [float(trade["net_pnl"]) for trade in trades]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "initial_cash": float(initial_cash),
        "final_equity": round(final_equity, 8),
        "total_return_pct": round((final_equity / initial_cash - 1) * 100.0, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100.0, 2) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "average_trade_pnl": round(sum(pnl) / len(pnl), 8) if pnl else 0.0,
        "gross_profit": round(gross_profit, 8),
        "gross_loss": round(gross_loss, 8),
    }


def _run_segment(
    data: pd.DataFrame,
    start: int,
    end: int,
    config: BacktestConfig,
    strategy=backtest_signal,
) -> dict:
    if not 0 <= start < end <= len(data):
        raise ValueError("Invalid segment boundaries")
    segment = data.iloc[:end].reset_index(drop=True)

    def gated_strategy(history: pd.DataFrame, index: int) -> int:
        # Preserve pre-segment history for indicator warm-up, but do not trade
        # until the requested segment begins.
        if index < start:
            return 0
        return strategy(history, index)

    result = run_backtest(segment, gated_strategy, config)
    segment_trades = [
        trade for trade in result["trades"]
        if trade["entry_index"] >= start and trade["exit_index"] <= end - 1
    ]
    segment_curve = result["equity_curve"][start:end]
    return {
        "start_index": start,
        "end_index_exclusive": end,
        "summary": _segment_summary(segment_curve, segment_trades, config.initial_cash),
        "trades": segment_trades,
        "equity_curve": segment_curve,
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
            "Each segment is evaluated with fresh initial cash; prior candles "
            "are used only for indicator warm-up. Fees, slippage and funding "
            "assumptions may not match live fills."
        ),
        "splits": {
            "train": _run_segment(data, 0, splits.train_end, cfg),
            "validation": _run_segment(data, splits.train_end, splits.validation_end, cfg),
            "test": _run_segment(data, splits.validation_end, splits.total, cfg),
        },
    }
