"""Small, deterministic OHLCV backtester for research and paper validation.

Signals are evaluated at candle close and queued for execution at the next
candle open. Positions are marked only after that open and the current candle's
range have occurred. If stop and target are both touched in one bar, the stop
is assumed to fill first (conservative assumption).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Literal

import pandas as pd

Signal = Literal[-1, 0, 1]
Strategy = Callable[[pd.DataFrame, int], Signal]


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 500.0
    risk_per_trade: float = 0.005
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0005
    funding_rate_per_bar: float = 0.0
    max_leverage: float = 1.0

    def validate(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if not 0 < self.risk_per_trade <= 0.02:
            raise ValueError("risk_per_trade must be in (0, 0.02]")
        if not 0 < self.stop_loss_pct < 1:
            raise ValueError("stop_loss_pct must be in (0, 1)")
        if not 0 < self.take_profit_pct < 1:
            raise ValueError("take_profit_pct must be in (0, 1)")
        if not 0 <= self.funding_rate_per_bar < 0.1:
            raise ValueError("funding_rate_per_bar must be in [0, 0.1)")
        if not 0 <= self.fee_rate < 0.1 or not 0 <= self.slippage_rate < 0.1:
            raise ValueError("fee and slippage rates must be in [0, 0.1)")
        if self.max_leverage < 1:
            raise ValueError("max_leverage must be at least 1")


def _validate_data(data: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {', '.join(sorted(missing))}")
    if len(data) < 3:
        raise ValueError("At least 3 candles are required")
    frame = data.copy().reset_index(drop=True)
    for col in required:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    if frame[list(required)].isna().any().any():
        raise ValueError("OHLC data cannot contain missing values")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("Candle high is inconsistent")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("Candle low is inconsistent")
    return frame


def run_backtest(
    data: pd.DataFrame,
    strategy: Strategy,
    config: BacktestConfig | None = None,
) -> dict:
    """Run a single-position, isolated-notional simulation; never places orders."""
    cfg = config or BacktestConfig()
    cfg.validate()
    candles = _validate_data(data)

    cash = cfg.initial_cash
    position = None
    pending_signal: Signal = 0
    equity_curve = []
    trades = []

    def close_position(exit_price: float, reason: str, bar_index: int) -> None:
        nonlocal cash, position
        if position is None:
            return
        direction = position["direction"]
        qty = position["qty"]
        fill = exit_price * (1 - cfg.slippage_rate if direction == 1 else 1 + cfg.slippage_rate)
        gross = (fill - position["entry"]) * qty * direction
        exit_fee = abs(fill * qty) * cfg.fee_rate
        funding = position["notional"] * cfg.funding_rate_per_bar * position["bars_held"] * direction
        net = gross - exit_fee - position["entry_fee"] - funding
        # Entry fee was deducted from cash when the position was opened.
        cash += gross - exit_fee - funding
        trades.append({
            "side": "LONG" if direction == 1 else "SHORT",
            "entry_index": position["entry_index"],
            "exit_index": bar_index,
            "entry_price": position["entry"],
            "exit_price": fill,
            "quantity": qty,
            "net_pnl": net,
            "reason": reason,
        })
        position = None

    def open_position(direction: int, raw_open: float, bar_index: int) -> None:
        nonlocal cash, position
        if cash <= 0:
            return
        entry = raw_open * (1 + cfg.slippage_rate if direction == 1 else 1 - cfg.slippage_rate)
        risk_budget = cash * cfg.risk_per_trade
        stop_distance = entry * cfg.stop_loss_pct
        qty_by_risk = risk_budget / stop_distance
        max_notional = cash * cfg.max_leverage
        qty = min(qty_by_risk, max_notional / entry) if entry else 0.0
        if qty <= 0:
            return
        notional = qty * entry
        entry_fee = notional * cfg.fee_rate
        if entry_fee >= cash:
            return
        cash -= entry_fee
        position = {
            "direction": direction,
            "entry": entry,
            "qty": qty,
            "notional": notional,
            "entry_fee": entry_fee,
            "entry_index": bar_index,
            "bars_held": 0,
            "stop": entry * (1 - cfg.stop_loss_pct if direction == 1 else 1 + cfg.stop_loss_pct),
            "target": entry * (1 + cfg.take_profit_pct if direction == 1 else 1 - cfg.take_profit_pct),
        }

    for i, bar in candles.iterrows():
        raw_open = float(bar.open)
        entered_this_bar = False

        # Apply only the signal generated at the previous candle close.
        if pending_signal != 0:
            if position is not None and pending_signal == -position["direction"]:
                close_position(raw_open, "reverse_signal", i)
            if position is None:
                open_position(int(pending_signal), raw_open, i)
                entered_this_bar = position is not None

        # Check the current candle's range only after any next-open entry.
        if position is not None:
            stop_hit = bar.low <= position["stop"] if position["direction"] == 1 else bar.high >= position["stop"]
            target_hit = bar.high >= position["target"] if position["direction"] == 1 else bar.low <= position["target"]
            if stop_hit:
                close_position(position["stop"], "stop_loss", i)
            elif target_hit:
                close_position(position["target"], "take_profit", i)

        # A held position accrues one approximate bar of funding after surviving
        # this candle. A position opened and closed within this bar accrues none.
        if position is not None and not entered_this_bar:
            position["bars_held"] += 1
        elif position is not None and entered_this_bar:
            position["bars_held"] += 1

        unrealized = 0.0
        if position is not None:
            unrealized = (float(bar.close) - position["entry"]) * position["qty"] * position["direction"]
        equity_curve.append({"index": i, "equity": cash + unrealized})

        # Generate a fresh signal at this close for the following candle open.
        pending_signal = 0
        if i < len(candles) - 1:
            signal = strategy(candles.iloc[: i + 1], i)
            if signal not in (-1, 0, 1):
                raise ValueError("Strategy must return -1, 0, or 1")
            pending_signal = int(signal)

    if position is not None:
        close_position(float(candles.iloc[-1].close), "end_of_data", len(candles) - 1)
        equity_curve[-1]["equity"] = cash

    equity = pd.Series([point["equity"] for point in equity_curve], dtype=float)
    peak = equity.cummax()
    drawdown = (equity / peak) - 1
    wins = [trade["net_pnl"] for trade in trades if trade["net_pnl"] > 0]
    losses = [trade["net_pnl"] for trade in trades if trade["net_pnl"] < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    total_return = (cash / cfg.initial_cash) - 1

    return {
        "config": asdict(cfg),
        "summary": {
            "initial_cash": cfg.initial_cash,
            "final_equity": round(cash, 8),
            "total_return_pct": round(total_return * 100, 4),
            "max_drawdown_pct": round(float(drawdown.min()) * 100, 4),
            "trades": len(trades),
            "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
            "average_trade_pnl": round(sum(trade["net_pnl"] for trade in trades) / len(trades), 8) if trades else 0.0,
        },
        "trades": trades,
        "equity_curve": equity_curve,
    }
