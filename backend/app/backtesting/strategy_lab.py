"""Strategy comparison laboratory for chronological Binance Futures research."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

import numpy as np
import pandas as pd

from app.backtesting.futures_simulator import FuturesConfig, run_futures_backtest
from app.backtesting.robustness import trade_bootstrap_analysis
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


def _spot_buy_and_hold_segment(
    frame: pd.DataFrame,
    start: int,
    end: int,
    config: FuturesConfig,
) -> tuple[list[dict], list[dict]]:
    """Model a fully funded spot buy-and-hold position with entry/exit costs."""
    if end - start < 2:
        raise ValueError("Benchmark segment requires at least two candles")
    entry_index = start + 1
    entry_bar = frame.iloc[entry_index]
    exit_bar = frame.iloc[end - 1]
    entry_fill = float(entry_bar["open"]) * (1.0 + config.slippage_rate)
    exit_fill = float(exit_bar["close"]) * (1.0 - config.slippage_rate)
    entry_fee_rate = config.taker_fee_rate
    quantity = config.initial_equity / (entry_fill * (1.0 + entry_fee_rate))
    entry_fee = quantity * entry_fill * entry_fee_rate
    cash = config.initial_equity - quantity * entry_fill - entry_fee
    exit_fee = quantity * exit_fill * entry_fee_rate
    final_equity = cash + quantity * exit_fill - exit_fee

    curve = []
    for index in range(start, end):
        bar = frame.iloc[index]
        if index < entry_index:
            equity = config.initial_equity
        else:
            estimated_exit = float(bar["close"]) * (1.0 - config.slippage_rate)
            equity = cash + quantity * estimated_exit * (1.0 - entry_fee_rate)
        curve.append({
            "timestamp": bar["timestamp"].isoformat(),
            "equity": float(equity),
        })
    curve[-1]["equity"] = float(final_equity)
    trade = {
        "entry_time": entry_bar["timestamp"].isoformat(),
        "exit_time": exit_bar["timestamp"].isoformat(),
        "entry_price": entry_fill,
        "exit_price": exit_fill,
        "quantity": quantity,
        "gross_pnl": (exit_fill - entry_fill) * quantity,
        "fees": entry_fee + exit_fee,
        "funding_paid": 0.0,
        "net_pnl": final_equity - config.initial_equity,
        "reason": "end_of_data",
    }
    return curve, [trade]


def _benchmark_comparisons(
    frame: pd.DataFrame,
    segments: dict[str, tuple[int, int]],
    scenarios: dict[str, tuple[FuturesConfig, pd.DataFrame | None]],
    timeframe: str,
) -> list[dict]:
    """Compare with a fully funded spot hold and an uninvested cash baseline."""
    output = []
    for segment_name, (start, end) in segments.items():
        for scenario_name, (scenario_config, _) in scenarios.items():
            spot_curve, spot_trades = _spot_buy_and_hold_segment(
                frame, start, end, scenario_config
            )
            spot_metrics = performance_metrics(
                spot_curve, spot_trades, scenario_config.initial_equity,
                BARS_PER_YEAR[timeframe],
            )
            output.append({
                "benchmark": "buy_and_hold_spot",
                "segment": segment_name,
                "cost_scenario": scenario_name,
                "start_index": start,
                "end_index_exclusive": end,
                **spot_metrics,
            })

            cash_curve = [
                {"timestamp": frame.iloc[index]["timestamp"].isoformat(),
                 "equity": scenario_config.initial_equity}
                for index in range(start, end)
            ]
            cash_metrics = performance_metrics(
                cash_curve, [], scenario_config.initial_equity,
                BARS_PER_YEAR[timeframe],
            )
            output.append({
                "benchmark": "cash_no_trade",
                "segment": segment_name,
                "cost_scenario": scenario_name,
                "start_index": start,
                "end_index_exclusive": end,
                **cash_metrics,
            })
    return output


def _sensitivity_analysis(
    frame: pd.DataFrame,
    funding: pd.DataFrame | None,
    validation_start: int,
    validation_end: int,
    strategies: dict[str, Strategy],
    base: FuturesConfig,
    timeframe: str,
) -> list[dict]:
    """Run one-factor-at-a-time sensitivity on validation data only."""
    dimensions = {
        "risk_fraction": (0.5, 1.0, 1.5, 2.0),
        "leverage": (0.5, 1.0, 1.5, 2.0),
        "taker_fee_rate": (0.5, 1.0, 1.5, 2.0),
        "slippage_rate": (0.5, 1.0, 1.5, 2.0),
    }
    output = []
    for parameter, multipliers in dimensions.items():
        for multiplier in multipliers:
            raw_value = getattr(base, parameter) * multiplier
            if parameter == "risk_fraction":
                value = min(raw_value, 0.02)
            elif parameter == "leverage":
                value = max(raw_value, 1.0)
            else:
                value = min(raw_value, 0.099)
            scenario_config = replace(base, **{parameter: value})
            scenario_config.validate()
            for strategy_name, strategy in strategies.items():
                result, curve = _evaluate_segment(
                    frame, funding, validation_start, validation_end,
                    strategy, scenario_config,
                )
                metrics = performance_metrics(
                    curve, result["trades"], base.initial_equity,
                    BARS_PER_YEAR[timeframe],
                )
                output.append({
                    "strategy": strategy_name,
                    "segment": "validation",
                    "parameter": parameter,
                    "multiplier": multiplier,
                    "parameter_value": value,
                    **metrics,
                })
    return output


def run_strategy_lab(
    candles: pd.DataFrame,
    funding: pd.DataFrame | None = None,
    timeframe: str = "1h",
    config: FuturesConfig | None = None,
    monte_carlo_simulations: int = 1000,
    monte_carlo_seed: int = 42,
) -> dict:
    """Compare five strategies across chronological splits, costs and bootstrap robustness."""
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
    monte_carlo_rows = []
    regime_labels = _regime_labels(indicator_frame)
    benchmark_rows = _benchmark_comparisons(
        frame, segments, scenarios, timeframe
    )
    sensitivity_rows = _sensitivity_analysis(
        frame, funding, train_end, validation_end, strategies, base, timeframe
    )
    for segment_name, (start, end) in segments.items():
        for strategy_name, strategy in strategies.items():
            for scenario_name, (scenario_config, scenario_funding) in scenarios.items():
                result, curve = _evaluate_segment(
                    frame, scenario_funding, start, end, strategy, scenario_config
                )
                metrics = performance_metrics(
                    curve, result["trades"], base.initial_equity, BARS_PER_YEAR[timeframe]
                )
                bootstrap = trade_bootstrap_analysis(
                    result["trades"], base.initial_equity,
                    simulations=monte_carlo_simulations,
                    seed=monte_carlo_seed + len(monte_carlo_rows),
                )
                monte_carlo_rows.append({
                    "timeframe": timeframe,
                    "strategy": strategy_name,
                    "segment": segment_name,
                    "cost_scenario": scenario_name,
                    **bootstrap,
                })
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
        "monte_carlo": monte_carlo_rows,
        "benchmarks": benchmark_rows,
        "sensitivity": sensitivity_rows,
    }
