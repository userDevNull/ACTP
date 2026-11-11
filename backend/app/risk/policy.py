"""Conservative risk prechecks for hypothetical signals."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_risk_fraction: float = 0.005
    max_daily_loss_fraction: float = 0.02
    max_drawdown_fraction: float = 0.10
    max_open_positions: int = 2
    max_leverage: float = 1.0


@dataclass(frozen=True)
class RiskAssessment:
    allowed: bool
    reason: str


def assess_signal(
    signal: int,
    *,
    equity: float,
    starting_day_equity: float,
    peak_equity: float,
    open_positions: int,
    requested_risk_fraction: float,
    requested_leverage: float,
    limits: RiskLimits = RiskLimits(),
) -> RiskAssessment:
    if signal not in (-1, 0, 1):
        return RiskAssessment(False, "Invalid signal")
    if signal == 0:
        return RiskAssessment(False, "HOLD: no position requested")
    if equity <= 0 or starting_day_equity <= 0 or peak_equity <= 0:
        return RiskAssessment(False, "Invalid equity")
    if equity <= starting_day_equity * (1 - limits.max_daily_loss_fraction):
        return RiskAssessment(False, "Daily loss circuit breaker")
    if equity <= peak_equity * (1 - limits.max_drawdown_fraction):
        return RiskAssessment(False, "Drawdown circuit breaker")
    if open_positions >= limits.max_open_positions:
        return RiskAssessment(False, "Open position limit")
    if not 0 < requested_risk_fraction <= limits.max_risk_fraction:
        return RiskAssessment(False, "Requested trade risk exceeds limit")
    if not 0 < requested_leverage <= limits.max_leverage:
        return RiskAssessment(False, "Requested leverage exceeds limit")
    return RiskAssessment(True, "Passes research risk checks")
