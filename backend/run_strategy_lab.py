"""Run the Phase 7 strategy performance laboratory on local Futures CSV data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.backtesting.futures_simulator import FuturesConfig
from app.backtesting.strategy_lab import run_strategy_lab


def parse_dataset(value: str) -> tuple[str, str, Path, Path | None]:
    parts = value.split(",", 3)
    if len(parts) not in (3, 4):
        raise argparse.ArgumentTypeError(
            "Dataset format: SYMBOL,TIMEFRAME,CANDLES_CSV[,FUNDING_CSV]"
        )
    symbol, timeframe, candles_path = parts[:3]
    funding_path = Path(parts[3]) if len(parts) == 4 and parts[3] else None
    if not symbol.strip() or not timeframe.strip():
        raise argparse.ArgumentTypeError("Symbol and timeframe cannot be empty")
    return symbol.upper(), timeframe, Path(candles_path), funding_path


def main() -> None:
    parser = argparse.ArgumentParser(description="ACTP Phase 7 strategy performance lab")
    parser.add_argument(
        "--dataset", action="append", type=parse_dataset, required=True,
        help="Repeat for each symbol/timeframe: SYMBOL,TIMEFRAME,CANDLES_CSV[,FUNDING_CSV]",
    )
    parser.add_argument("--equity", type=float, default=500.0)
    parser.add_argument("--leverage", type=float, default=1.0)
    parser.add_argument("--risk", type=float, default=0.005)
    parser.add_argument("--fee", type=float, default=0.0005)
    parser.add_argument("--slippage", type=float, default=0.0005)
    parser.add_argument("--maintenance-margin", type=float, default=0.005)
    parser.add_argument("--monte-carlo-simulations", type=int, default=1000,
                        help="Trade-bootstrap paths per experiment (default: 1000)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Deterministic Monte Carlo seed (default: 42)")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase7"))
    args = parser.parse_args()

    config = FuturesConfig(
        initial_equity=args.equity,
        leverage=args.leverage,
        risk_fraction=args.risk,
        taker_fee_rate=args.fee,
        slippage_rate=args.slippage,
        maintenance_margin_rate=args.maintenance_margin,
    )
    all_rows = []
    regime_rows = []
    monte_carlo_rows = []
    dataset_summaries = []

    for symbol, timeframe, candles_path, funding_path in args.dataset:
        if not candles_path.is_file():
            parser.error(f"Candle file not found: {candles_path}")
        candles = pd.read_csv(candles_path)
        funding = None
        if funding_path:
            if not funding_path.is_file():
                parser.error(f"Funding file not found: {funding_path}")
            funding = pd.read_csv(funding_path)

        report = run_strategy_lab(
            candles, funding, timeframe, config,
            monte_carlo_simulations=args.monte_carlo_simulations,
            monte_carlo_seed=args.seed,
        )
        for row in report["results"]:
            all_rows.append({"symbol": symbol, **row})
        for row in report["regime_attribution"]:
            regime_rows.append({"symbol": symbol, **row})
        for row in report["monte_carlo"]:
            monte_carlo_rows.append({"symbol": symbol, **row})
        dataset_summaries.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "candles": len(candles),
            "splits": report["splits"],
            "strategies": report["strategies"],
            "cost_scenarios": report["cost_scenarios"],
        })
        print(
            f"Completed {symbol} {timeframe}: "
            f"{len(report['results'])} experiments, "
            f"{len(report['regime_attribution'])} regime groups"
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "strategy_lab_results.csv"
    regime_csv_path = args.output_dir / "strategy_lab_regime_attribution.csv"
    monte_carlo_csv_path = args.output_dir / "strategy_lab_monte_carlo.csv"
    json_path = args.output_dir / "strategy_lab_report.json"

    results = pd.DataFrame(all_rows)
    if not results.empty:
        results = results.sort_values(
            ["symbol", "timeframe", "segment", "cost_scenario", "net_return_pct"],
            ascending=[True, True, True, True, False],
        )
    results.to_csv(csv_path, index=False)
    pd.DataFrame(regime_rows).to_csv(regime_csv_path, index=False)
    pd.DataFrame(monte_carlo_rows).to_csv(monte_carlo_csv_path, index=False)

    payload = {
        "warning": (
            "Research only; not a profitability guarantee or live-trading recommendation. "
            "Do not select strategies using the final test segment."
        ),
        "datasets": dataset_summaries,
        "results": all_rows,
        "regime_attribution": regime_rows,
        "monte_carlo": monte_carlo_rows,
        "monte_carlo_settings": {
            "simulations_per_experiment": args.monte_carlo_simulations,
            "seed": args.seed,
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(f"CSV report: {csv_path}")
    print(f"Regime attribution CSV: {regime_csv_path}")
    print(f"Monte Carlo robustness CSV: {monte_carlo_csv_path}")
    print(f"JSON report: {json_path}")


if __name__ == "__main__":
    main()
