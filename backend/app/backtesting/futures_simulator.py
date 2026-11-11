"""Research-only isolated-margin Futures simulator with timestamped funding.

This is an approximation, not an exchange-matching engine. Liquidation uses a
single configured maintenance-margin rate, not Binance's symbol/position-tier
schedule or mark-price stream. Use results for sensitivity analysis only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class FuturesConfig:
    initial_equity: float = 500.0
    risk_fraction: float = 0.005
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    leverage: float = 1.0
    taker_fee_rate: float = 0.0005
    slippage_rate: float = 0.0005
    maintenance_margin_rate: float = 0.005

    def validate(self) -> None:
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if not 0 < self.risk_fraction <= 0.02:
            raise ValueError("risk_fraction must be in (0, 0.02]")
        if not 0 < self.stop_loss_pct < 1 or not 0 < self.take_profit_pct < 1:
            raise ValueError("stop and target percentages must be in (0, 1)")
        if self.leverage < 1:
            raise ValueError("leverage must be >= 1")
        if not 0 <= self.taker_fee_rate < 0.1 or not 0 <= self.slippage_rate < 0.1:
            raise ValueError("fee and slippage must be in [0, 0.1)")
        if not 0 <= self.maintenance_margin_rate < 0.5:
            raise ValueError("maintenance margin rate must be in [0, 0.5)")


def run_futures_backtest(
    candles: pd.DataFrame,
    strategy,
    funding: pd.DataFrame | None = None,
    config: FuturesConfig | None = None,
) -> dict:
    cfg = config or FuturesConfig()
    cfg.validate()
    required = {"open", "high", "low", "close", "timestamp"}
    if not required.issubset(candles.columns):
        raise ValueError(f"Required columns: {', '.join(sorted(required))}")
    frame = candles.copy().reset_index(drop=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    for col in ("open", "high", "low", "close"):
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    if len(frame) < 3 or frame[list(("open", "high", "low", "close"))].isna().any().any():
        raise ValueError("At least three complete OHLC candles are required")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("Invalid high")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("Invalid low")

    funding_events = pd.DataFrame(columns=["funding_time", "funding_rate"])
    if funding is not None and not funding.empty:
        if not {"funding_time", "funding_rate"}.issubset(funding.columns):
            raise ValueError("Funding data requires funding_time and funding_rate")
        funding_events = funding[["funding_time", "funding_rate"]].copy()
        funding_events["funding_time"] = pd.to_datetime(funding_events["funding_time"], utc=True, errors="raise")
        funding_events["funding_rate"] = pd.to_numeric(funding_events["funding_rate"], errors="raise")
        funding_events = funding_events.sort_values("funding_time").reset_index(drop=True)

    equity = cfg.initial_equity
    position = None
    trades = []
    curve = []
    funding_idx = 0

    def close(exit_price: float, reason: str, idx: int) -> None:
        nonlocal equity, position
        if position is None:
            return
        direction = position["direction"]
        fill = exit_price * (1 - cfg.slippage_rate if direction == 1 else 1 + cfg.slippage_rate)
        gross = (fill - position["entry"]) * position["qty"] * direction
        exit_fee = abs(fill * position["qty"]) * cfg.taker_fee_rate
        pnl = gross - exit_fee - position["entry_fee"] - position["funding_paid"]
        equity += gross - exit_fee
        trades.append({
            "side": "LONG" if direction == 1 else "SHORT",
            "entry_time": frame.iloc[position["entry_idx"]]["timestamp"].isoformat(),
            "exit_time": frame.iloc[idx]["timestamp"].isoformat(),
            "entry_price": position["entry"], "exit_price": fill,
            "quantity": position["qty"], "gross_pnl": gross,
            "fees": position["entry_fee"] + exit_fee,
            "funding_paid": position["funding_paid"], "net_pnl": pnl,
            "reason": reason,
        })
        position = None

    for i, bar in frame.iterrows():
        timestamp = bar["timestamp"]

        # Apply each funding event once if the position is open at its timestamp.
        while funding_idx < len(funding_events) and funding_events.iloc[funding_idx]["funding_time"] <= timestamp:
            event = funding_events.iloc[funding_idx]
            if position is not None and event["funding_time"] > frame.iloc[position["entry_idx"]]["timestamp"]:
                payment = position["notional"] * float(event["funding_rate"]) * position["direction"]
                equity -= payment
                position["funding_paid"] += payment
            funding_idx += 1

        if position is not None:
            direction = position["direction"]
            # Approximate isolated liquidation threshold. Liquidation is checked
            # before stop/target and uses candle extremes as a proxy for mark price.
            liq = position["liquidation_price"]
            liq_hit = bar["low"] <= liq if direction == 1 else bar["high"] >= liq
            stop_hit = bar["low"] <= position["stop"] if direction == 1 else bar["high"] >= position["stop"]
            target_hit = bar["high"] >= position["target"] if direction == 1 else bar["low"] <= position["target"]
            if liq_hit:
                close(liq, "estimated_liquidation", i)
            elif stop_hit:
                close(position["stop"], "stop_loss", i)
            elif target_hit:
                close(position["target"], "take_profit", i)

        # Mark-to-market at the candle close before generating a signal.
        unrealized = 0.0
        if position is not None:
            unrealized = (float(bar["close"]) - position["entry"]) * position["qty"] * position["direction"]
        curve.append({"timestamp": timestamp.isoformat(), "equity": equity + unrealized})

        # Signals from candle i close are filled no earlier than candle i+1 open.
        if i < len(frame) - 1:
            signal = strategy(frame.iloc[:i + 1].copy(), i)
            if signal not in (-1, 0, 1):
                raise ValueError("Strategy must return -1, 0, or 1")
            if position is not None and signal == -position["direction"]:
                close(float(frame.iloc[i + 1]["open"]), "reverse_signal", i + 1)
            if position is None and signal != 0 and equity > 0:
                direction = int(signal)
                next_open = float(frame.iloc[i + 1]["open"])
                entry = next_open * (1 + cfg.slippage_rate if direction == 1 else 1 - cfg.slippage_rate)
                stop_distance = entry * cfg.stop_loss_pct
                risk_cash = equity * cfg.risk_fraction
                qty_by_risk = risk_cash / stop_distance
                qty_by_margin = equity * cfg.leverage / entry
                qty = min(qty_by_risk, qty_by_margin)
                notional = qty * entry
                entry_fee = notional * cfg.taker_fee_rate
                if qty > 0 and entry_fee < equity:
                    equity -= entry_fee
                    # Approximation for linear USDT-margined isolated position.
                    liq_distance = (1 / cfg.leverage) - cfg.maintenance_margin_rate
                    liq_price = entry * (1 - liq_distance if direction == 1 else 1 + liq_distance)
                    position = {
                        "direction": direction, "entry": entry, "qty": qty,
                        "notional": notional, "entry_fee": entry_fee,
                        "funding_paid": 0.0, "entry_idx": i + 1,
                        "stop": entry * (1 - cfg.stop_loss_pct if direction == 1 else 1 + cfg.stop_loss_pct),
                        "target": entry * (1 + cfg.take_profit_pct if direction == 1 else 1 - cfg.take_profit_pct),
                        "liquidation_price": liq_price,
                    }

    if position is not None:
        close(float(frame.iloc[-1]["close"]), "end_of_data", len(frame) - 1)
        curve[-1]["equity"] = equity

    series = pd.Series([x["equity"] for x in curve], dtype=float)
    peak = series.cummax()
    dd = (series / peak) - 1
    wins = [x["net_pnl"] for x in trades if x["net_pnl"] > 0]
    losses = [x["net_pnl"] for x in trades if x["net_pnl"] < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    return {
        "config": asdict(cfg),
        "summary": {
            "initial_equity": cfg.initial_equity,
            "final_equity": round(equity, 8),
            "return_pct": round((equity / cfg.initial_equity - 1) * 100, 4),
            "max_drawdown_pct": round(float(dd.min()) * 100, 4),
            "trades": len(trades),
            "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
            "liquidations": sum(t["reason"] == "estimated_liquidation" for t in trades),
            "funding_total": round(sum(t["funding_paid"] for t in trades), 8),
        },
        "trades": trades,
        "equity_curve": curve,
        "limitations": [
            "Liquidation is an estimate using one fixed maintenance-margin rate and candle extremes, not exchange mark price or tier tables.",
            "Fees are modeled as taker fees; maker rebates, partial fills, spread and order-book depth are not modeled.",
            "Funding events are applied at supplied timestamps when a position is open; intrabar event ordering is approximated at candle timestamps.",
            "No exchange quantity/price precision, min notional, ADL, insurance fund, or cross-margin portfolio effects.",
        ],
    }
