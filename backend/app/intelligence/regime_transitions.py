"""Descriptive transition and persistence statistics for historical regimes.

Unlike per-candle diagnostics, these summaries describe the completed sample
and are retrospective. They must not be used as live/forward-looking features.
"""
from __future__ import annotations

import pandas as pd

from app.intelligence.market_analysis import REGIMES


def regime_transition_analysis(diagnostics: pd.DataFrame) -> dict:
    """Count adjacent regime changes and contiguous run lengths."""
    if diagnostics.empty:
        raise ValueError("diagnostics cannot be empty")
    if "market_regime" not in diagnostics:
        raise ValueError("market_regime column required")
    labels = diagnostics["market_regime"].astype(str).tolist()
    unknown = sorted(set(labels) - set(REGIMES))
    if unknown:
        raise ValueError(f"Unknown market regimes: {', '.join(unknown)}")

    counts = {source: {target: 0 for target in REGIMES} for source in REGIMES}
    for source, target in zip(labels, labels[1:]):
        counts[source][target] += 1

    probabilities = {}
    for source in REGIMES:
        total = sum(counts[source].values())
        probabilities[source] = {
            target: round(counts[source][target] / total, 8) if total else None
            for target in REGIMES
        }

    runs: list[tuple[str, int]] = []
    for label in labels:
        if runs and runs[-1][0] == label:
            runs[-1] = (label, runs[-1][1] + 1)
        else:
            runs.append((label, 1))

    persistence = {}
    for regime in REGIMES:
        durations = [length for label, length in runs if label == regime]
        persistence[regime] = {
            "episodes": len(durations),
            "total_candles": sum(durations),
            "average_duration_candles": round(sum(durations) / len(durations), 4) if durations else None,
            "median_duration_candles": float(pd.Series(durations).median()) if durations else None,
            "max_duration_candles": max(durations) if durations else None,
        }

    return {
        "sample_candles": len(labels),
        "transitions_observed": max(len(labels) - 1, 0),
        "transition_counts": counts,
        "transition_probabilities": probabilities,
        "persistence": persistence,
        "interpretation": (
            "Retrospective sample statistics only. Transition probabilities and "
            "durations use the complete supplied sample and are not causal live features."
        ),
    }
