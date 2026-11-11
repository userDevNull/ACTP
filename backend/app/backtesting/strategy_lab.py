"""Strategy comparison laboratory for chronological Binance Futures research."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

import numpy as np
import pandas as pd

from app.backtesting.futures_simulator import FuturesConfig, run_futures_backtest
from app.intelligence.regime import features
from app.strategies.adaptive import backtest_signal

Strategy = Callable[[pd.DataFrame, int], int]

BARS_PER_YEAR = {
    "1m": 525600, "3m": 175200, "5m": 105120, "15m": 35040,
    "30m": 17520, "1h": 8760, "2h": 4380, "4h": 2190,
    "6h": 1460, "8h": 1095, "12h": 730, "1d": 365, "1w": 52,
}


def _trend(history: pd.DataFrame, index: int) -> int:
    if len(history) < 70:
        return 0
    frame = features(history)
    row, prev = frame.iloc[-1], frame.iloc[-2]
    if not np.isfinite([row["adx"], row["ema_fast"], row["ema_slow"],
                        prev["ema_fast"], prev["ema_slow"]]).all():
        return 0
    if row["adx"] < 20:
        return 0
    if prev["ema_fast"] <= prev["ema_slow"] and row["ema_fast"] > row["ema_slow"]:
        return 1
    if prev["ema_fast"] >= prev["ema_slow"] and row["ema_fast"] < row["ema_slow"]:
        return -1
    return 0


def _breakout(history: pd.DataFrame, index: int) -> int:
    if len(history) < 70:
        return 0
    row = features(history).iloc[-1]
    if not np.isfinite([row["prior_high"], row["prior_low"],
                        row["relative_volume"]]).all() or row["relative_volume"] < 1.2:
        return 0
    if row["close"] > row["prior_high"]:
        return 1
    if row["close"] < row["prior_low"]:
        return -1
    return 0


def _momentum(history: pd.DataFrame, index: int) -> int:
    if len(history) < 70:
        return 0
    row = features(history).iloc[-1]
    if not np.isfinite([row["ema_fast"], row["ema_slow"], row["rsi"],
                        row["relative_volume"]]).all():
        return 0
    if row["relative_volume"] < 1.0:
        return 0
    if row["close"] > row["ema_fast"] > row["ema_slow"] and row["rsi"] >= 60:
        return 1
    if row["close"] < row["ema_fast"] < row["ema_slow"] and row["rsi"] <= 40:
        return -1
    return 0


def _mean_reversion(history: pd.DataFrame, index: int) -> int:
    if len(history) < 70:
        return 0
    row = features(history).iloc[-1]
    if not np.isfinite([row["adx"], row["lower_band"], row["upper_band"],
                        row["rsi"]]).all() or row["adx"] >= 20:
        return 0
    if row["close"] < row["lower_band"] and row["rsi"] < 35:
        return 1
    if row["close"] > row["upper_band"] and row["rsi"] > 65:
        return -1
    return 0


def _classify_feature_row(row: pd.Series) -> str:
    required = ["adx", "atr_pct", "relative_volume", "ema_fast", "ema_slow",
                "prior_high", "prior_low"]
    if not np.isfinite(row[required].astype(float).to_numpy()).all():
        return "UNCERTAIN"
    price = float(row["close"])
    adx = float(row["adx"])
    atr_pct = float(row["atr_pct"])
    rv = float(row["relative_volume"])
    fast = float(row["ema_fast"])
    slow = float(row["ema_slow"])
    if atr_pct > 0.08:
        return "UNCERTAIN"
    if price > row["prior_high"] and rv >= 1.5 and adx >= 18:
        return "BREAKOUT_UP"
    if price < row["prior_low"] and rv >= 1.5 and adx >= 18:
        return "BREAKOUT_DOWN"
    if adx >= 25 and fast > slow and price > slow:
        return "TREND_UP"
    if adx >= 25 and fast < slow and price < slow:
        return "TREND_DOWN"
    if adx < 20:
        return "RANGE"
    return "UNCERTAIN"


def _precomputed_catalog(indicators: pd.DataFrame) -> dict[str, Strategy]:
    """Create causal O(1)-per-bar strategy callbacks from one indicator pass."""
    def row_pair(index: int):
        if index < 69 or index >= len(indicators):
            return None, None
        return indicators.iloc[index], indicators.iloc[index - 1]

    def trend(history: pd.DataFrame, index: int) -> int:
        row, prev = row_pair(index)
        if row is None or not np.isfinite([row["adx"], row["ema_fast"], row["ema_slow"],
                                           prev["ema_fast"], prev["ema_slow"]]).all():
            return 0
        if row["adx"] < 20:
            return 0
        if prev["ema_fast"] <= prev["ema_slow"] and row["ema_fast"] > row["ema_slow"]:
            return 1
        if prev["ema_fast"] >= prev["ema_slow"] and row["ema_fast"] < row["ema_slow"]:
            return -1
        return 0

    def breakout(history: pd.DataFrame, index: int) -> int:
        row, _ = row_pair(index)
        if row is None or not np.isfinite([row["prior_high"], row["prior_low"],
                                           row["relative_volume"]]).all():
            return 0
        if row["relative_volume"] < 1.2:
            return 0
        if row["close"] > row["prior_high"]:
            return 1
        if row["close"] < row["prior_low"]:
            return -1
        return 0

    def momentum(history: pd.DataFrame, index: int) -> int:
        row, _ = row_pair(index)
        if row is None or not np.isfinite([row["ema_fast"], row["ema_slow"], row["rsi"],
                                           row["relative_volume"]]).all():
            return 0
        if row["relative_volume"] < 1.0:
            return 0
        if row["close"] > row["ema_fast"] > row["ema_slow"] and row["rsi"] >= 60:
            return 1
        if row["close"] < row["ema_fast"] < row["ema_slow"] and row["rsi"] <= 40:
            return -1
        return 0

    def mean_reversion(history: pd.DataFrame, index: int) -> int:
        row, _ = row_pair(index)
        if row is None or not np.isfinite([row["adx"], row["lower_band"], row["upper_band"],
                                           row["rsi"]]).all() or row["adx"] >= 20:
            return 0
        if row["close"] < row["lower_band"] and row["rsi"] < 35:
            return 1
        if row["close"] > row["upper_band"] and row["rsi"] > 65:
            return -1
        return 0

    def adaptive(history: pd.DataFrame, index: int) -> int:
        row, previous = row_pair(index)
        if row is None:
            return 0
        regime = _classify_feature_row(row)
        if regime in ("UNCERTAIN",):
            return 0
        required = ["close", "ema_fast", "ema_slow", "sma20", "upper_band",
                    "lower_band", "rsi", "relative_volume", "atr_pct"]
        if not np.isfinite(row[required].astype(float).to_numpy()).all():
            return 0
        price = float(row["close"])
        rsi = float(row["rsi"])
        if regime in ("BREAKOUT_UP", "BREAKOUT_DOWN"):
            return 1 if regime == "BREAKOUT_UP" else -1
        if regime == "RANGE":
            if price < row["lower_band"] and rsi < 35:
                return 1
            if price > row["upper_band"] and rsi > 65:
                return -1
            return 0
        side = 1 if regime == "TREND_UP" else -1
        fast = float(row["ema_fast"])
        prev_close = float(previous["close"])
        prev_fast = float(previous["ema_fast"])
        if side == 1 and prev_close <= prev_fast and price > fast and 40 <= rsi <= 70:
            return 1
        if side == -1 and prev_close >= prev_fast and price < fast and 30 <= rsi <= 60:
            return -1
        if side == 1 and price > float(previous["high"]) and rsi >= 60 and row["relative_volume"] >= 1.3:
            return 1
        if side == -1 and price < float(previous["low"]) and rsi <= 40 and row["relative_volume"] >= 1.3:
            return -1
        return 0

    return {
        "adaptive": adaptive,
        "trend_crossover": trend,
        "breakout": breakout,
        "momentum": momentum,
        "mean_reversion": mean_reversion,
    }


def strategy_catalog(indicators: pd.DataFrame | None = None) -> dict[str, Strategy]:
    """Return the fixed Phase 7 strategy set, optionally using precomputed features."""
    if indicators is not None:
        return _precomputed_catalog(indicators)
    return {
        "adaptive": backtest_signal,
        "trend_crossover": _trend,
        "breakout": _breakout,
        "momentum": _momentum,
        "mean_reversion": _mean_reversion,
    }



def _regime_labels(indicator_frame: pd.DataFrame) -> list[str]:
    """Return causal regime labels from a precomputed indicator frame."""
    return [_classify_feature_row(row) for _, row in indicator_frame.iterrows()]


def _regime_attribution(
    trades: list[dict],
    candles: pd.DataFrame,
    labels: list[str],
) -> list[dict]:
    """Attribute each trade to the regime at its signal candle, before entry."""
    timestamp_to_index = {
        timestamp.isoformat(): index
        for index, timestamp in enumerate(candles["timestamp"])
    }
    grouped: dict[str, list[dict]] = {}
    for trade in trades:
        entry_index = timestamp_to_index.get(trade["entry_time"])
        if entry_index is None:
            continue
        signal_index = max(entry_index - 1, 0)
        regime = labels[signal_index]
        grouped.setdefault(regime, []).append(trade)

    output = []
    for regime, items in sorted(grouped.items()):
        pnls = [float(item["net_pnl"]) for item in items]
        wins = [value for value in pnls if value > 0]
        losses = [value for value in pnls if value < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        output.append({
            "regime": regime,
            "trades": len(items),
            "net_pnl": round(sum(pnls), 8),
            "win_rate_pct": round(len(wins) / len(items) * 100, 2),
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
            "expectancy": round(sum(pnls) / len(items), 8),
            "fees_paid": round(sum(float(item["fees"]) for item in items), 8),
            "funding_paid": round(sum(float(item["funding_paid"]) for item in items), 8),
        })
    return output


def performance_metrics(
    equity_curve: list[dict],
    trades: list[dict],
    initial_equity: float,
    bars_per_year: int,
) -> dict:
    """Calculate comparable metrics from a segment-only equity curve."""
    values = pd.Series([float(point["equity"]) for point in equity_curve], dtype=float)
    if values.empty:
        final_equity = float(initial_equity)
        max_drawdown_pct = 0.0
        max_drawdown_amount = 0.0
        returns = pd.Series(dtype=float)
    else:
        final_equity = float(values.iloc[-1])
        peaks = values.cummax()
        drawdowns = values / peaks - 1.0
        max_drawdown_pct = float(drawdowns.min() * 100.0)
        max_drawdown_amount = float((peaks - values).max())
        returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()

    mean_return = float(returns.mean()) if not returns.empty else 0.0
    volatility = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    downside = returns[returns < 0]
    downside_volatility = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sharpe = (mean_return / volatility * np.sqrt(bars_per_year)) if volatility > 0 else None
    sortino = (mean_return / downside_volatility * np.sqrt(bars_per_year)) if downside_volatility > 0 else None

    pnl = [float(trade["net_pnl"]) for trade in trades]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    gross_profit, gross_loss = sum(wins), abs(sum(losses))
    net_profit = sum(pnl)
    return {
        "initial_equity": round(float(initial_equity), 8),
        "final_equity": round(final_equity, 8),
        "net_return_pct": round((final_equity / initial_equity - 1) * 100, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "max_drawdown_amount": round(max_drawdown_amount, 8),
        "trades": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
        "expectancy": round(net_profit / len(trades), 8) if trades else 0.0,
        "average_win": round(float(np.mean(wins)), 8) if wins else None,
        "average_loss": round(float(np.mean(losses)), 8) if losses else None,
        "sharpe_ratio_annualized": round(float(sharpe), 4) if sharpe is not None else None,
        "sortino_ratio_annualized": round(float(sortino), 4) if sortino is not None else None,
        "recovery_factor": round(net_profit / max_drawdown_amount, 4) if max_drawdown_amount > 0 else None,
        "liquidations": sum(trade["reason"] == "estimated_liquidation" for trade in trades),
        "funding_paid": round(sum(float(trade["funding_paid"]) for trade in trades), 8),
        "fees_paid": round(sum(float(trade["fees"]) for trade in trades), 8),
    }


def _evaluate_segment(
    candles: pd.DataFrame,
    funding: pd.DataFrame | None,
    start: int,
    end: int,
    strategy: Strategy,
    config: FuturesConfig,
) -> tuple[dict, list[dict]]:
    def gated(history: pd.DataFrame, index: int) -> int:
        return 0 if index < start else strategy(history, index)

    result = run_futures_backtest(
        candles.iloc[:end].reset_index(drop=True),
        gated,
        funding,
        config,
    )
    # Include only evaluation-period bars; pre-segment bars are indicator warm-up.
    curve = result["equity_curve"][start:]
    return result, curve


def run_strategy_lab(
    candles: pd.DataFrame,
    funding: pd.DataFrame | None = None,
    timeframe: str = "1h",
    config: FuturesConfig | None = None,
) -> dict:
    """Compare five fixed strategies across train/validation/test and cost stress."""
    if timeframe not in BARS_PER_YEAR:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(candles.columns):
        raise ValueError(f"Candles require: {', '.join(sorted(required))}")
    if len(candles) < 100:
        raise ValueError("At least 100 candles are required for a research lab run")

    frame = candles.copy().reset_index(drop=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    base = config or FuturesConfig()
    base.validate()

    train_end = int(len(frame) * 0.60)
    validation_end = int(len(frame) * 0.80)
    segments = {
        "train": (0, train_end),
        "validation": (train_end, validation_end),
        "test": (validation_end, len(frame)),
    }
    indicator_frame = features(frame)
    strategies = strategy_catalog(indicator_frame)
    scenarios = {
        "base_cost": (base, funding),
        "2x_cost_stress": (
            replace(base,
                    taker_fee_rate=min(base.taker_fee_rate * 2, 0.099),
                    slippage_rate=min(base.slippage_rate * 2, 0.099)),
            (funding.assign(funding_rate=funding["funding_rate"] * 1.5)
             if funding is not None and not funding.empty else funding),
        ),
    }

    rows = []
    regime_rows = []
    regime_labels = _regime_labels(indicator_frame)
    for segment_name, (start, end) in segments.items():
        for strategy_name, strategy in strategies.items():
            for scenario_name, (scenario_config, scenario_funding) in scenarios.items():
                result, curve = _evaluate_segment(
                    frame, scenario_funding, start, end, strategy, scenario_config
                )
                metrics = performance_metrics(
                    curve, result["trades"], base.initial_equity, BARS_PER_YEAR[timeframe]
                )
                rows.append({
                    "timeframe": timeframe,
                    "strategy": strategy_name,
                    "segment": segment_name,
                    "cost_scenario": scenario_name,
                    "start_index": start,
                    "end_index_exclusive": end,
                    "bars": end - start,
                    **metrics,
                })
                for attribution in _regime_attribution(result["trades"], frame, regime_labels):
                    regime_rows.append({
                        "timeframe": timeframe,
                        "strategy": strategy_name,
                        "segment": segment_name,
                        "cost_scenario": scenario_name,
                        **attribution,
                    })

    return {
        "warning": (
            "Research only. The test segment must remain untouched until strategy "
            "choices are frozen. Sharpe/Sortino annualization assumes continuous "
            "crypto trading at the supplied timeframe. Simulator liquidation, "
            "funding event ordering, spread and fills remain approximations."
        ),
        "splits": {
            "train_end": train_end,
            "validation_end": validation_end,
            "total": len(frame),
        },
        "strategies": list(strategies),
        "cost_scenarios": list(scenarios),
        "results": rows,
        "regime_attribution": regime_rows,
    }
