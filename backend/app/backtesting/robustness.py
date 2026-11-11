"""Trade-level bootstrap diagnostics for research robustness.

This is a path-risk approximation, not a replay of the bar-by-bar simulator.
It resamples completed trade PnL values with replacement and does not model
trade overlap, serial dependence, changing position sizes, or market regimes.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def trade_bootstrap_analysis(
    trades: Sequence[dict],
    initial_equity: float,
    simulations: int = 1000,
    seed: int = 42,
    confidence_level: float = 0.95,
) -> dict:
    """Estimate trade-sequence outcome dispersion using deterministic bootstrap."""
    if not math.isfinite(initial_equity) or initial_equity <= 0:
        raise ValueError("initial_equity must be a finite positive number")
    if not isinstance(simulations, int) or simulations < 1:
        raise ValueError("simulations must be a positive integer")
    if not 0.5 <= confidence_level < 1:
        raise ValueError("confidence_level must be in [0.5, 1)")
    if not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    pnls = np.asarray([float(trade["net_pnl"]) for trade in trades], dtype=float)
    if not np.isfinite(pnls).all():
        raise ValueError("trade net_pnl values must be finite")

    if len(pnls) == 0:
        return {
            "method": "trade_pnl_bootstrap_with_replacement",
            "simulations": simulations,
            "trades_resampled_per_path": 0,
            "seed": seed,
            "confidence_level": confidence_level,
            "final_equity_p05": initial_equity,
            "final_equity_median": initial_equity,
            "final_equity_p95": initial_equity,
            "final_equity_confidence_low": initial_equity,
            "final_equity_confidence_high": initial_equity,
            "probability_of_loss_pct": 0.0,
            "probability_of_ruin_pct": 0.0,
            "max_drawdown_pct_median": 0.0,
            "max_drawdown_pct_p95": 0.0,
            "interpretation": "No completed trades; bootstrap outcomes equal starting equity.",
        }

    rng = np.random.default_rng(seed)
    sample_count = len(pnls)
    final_equities = np.empty(simulations, dtype=float)
    max_drawdowns = np.empty(simulations, dtype=float)
    ruined = np.zeros(simulations, dtype=bool)

    for simulation in range(simulations):
        sampled_pnl = rng.choice(pnls, size=sample_count, replace=True)
        path = np.concatenate(([initial_equity], initial_equity + np.cumsum(sampled_pnl)))
        peaks = np.maximum.accumulate(path)
        drawdowns = np.divide(
            path - peaks, peaks,
            out=np.zeros_like(path),
            where=peaks > 0,
        )
        final_equities[simulation] = path[-1]
        max_drawdowns[simulation] = max(0.0, -float(np.min(drawdowns)) * 100.0)
        ruined[simulation] = bool(np.any(path <= 0))

    tail = (1.0 - confidence_level) / 2.0
    return {
        "method": "trade_pnl_bootstrap_with_replacement",
        "simulations": simulations,
        "trades_resampled_per_path": sample_count,
        "seed": seed,
        "confidence_level": confidence_level,
        "final_equity_p05": round(float(np.quantile(final_equities, 0.05)), 8),
        "final_equity_median": round(float(np.median(final_equities)), 8),
        "final_equity_p95": round(float(np.quantile(final_equities, 0.95)), 8),
        "final_equity_confidence_low": round(float(np.quantile(final_equities, tail)), 8),
        "final_equity_confidence_high": round(float(np.quantile(final_equities, 1.0 - tail)), 8),
        "probability_of_loss_pct": round(float(np.mean(final_equities < initial_equity) * 100.0), 4),
        "probability_of_ruin_pct": round(float(np.mean(ruined) * 100.0), 4),
        "max_drawdown_pct_median": round(float(np.median(max_drawdowns)), 4),
        "max_drawdown_pct_p95": round(float(np.quantile(max_drawdowns, 0.95)), 4),
        "interpretation": (
            "Trade-level bootstrap only. Resampling completed net PnL ignores trade "
            "ordering, serial dependence, overlapping exposure, changing position "
            "sizes, regime shifts and bar-level execution paths; it is not a forecast."
        ),
    }
