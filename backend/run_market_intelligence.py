"""Generate offline Phase 8 market intelligence reports from historical CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.intelligence.market_analysis import analyze_market, summarize_market
from app.intelligence.multi_timeframe import multi_timeframe_consensus
from app.intelligence.regime_transitions import regime_transition_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="ACTP Phase 8 offline market intelligence")
    parser.add_argument("--candles", type=Path, help="Single-timeframe candle CSV")
    parser.add_argument("--timeframe-dataset", action="append", default=[], metavar="TF,CSV",
                        help="Repeat for multi-timeframe analysis, e.g. 1h,data/BTCUSDT_1h.csv")
    parser.add_argument("--output-dir", default=Path("reports/phase8"), type=Path)
    parser.add_argument("--volatility-window", default=48, type=int)
    args = parser.parse_args()
    if not args.candles and not args.timeframe_dataset:
        parser.error("Provide --candles or at least two --timeframe-dataset arguments")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.candles:
        if not args.candles.is_file():
            parser.error(f"Missing candles CSV: {args.candles}")
        diagnostics = analyze_market(
            pd.read_csv(args.candles), volatility_window=args.volatility_window
        )
        summary = summarize_market(diagnostics)
        transitions = regime_transition_analysis(diagnostics)
        summary["regime_transitions"] = transitions
        diagnostics.to_csv(args.output_dir / "market_diagnostics.csv", index=False)
        (args.output_dir / "market_summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
        )
        pd.DataFrame.from_dict(transitions["transition_counts"], orient="index").rename_axis(
            "from_regime"
        ).to_csv(args.output_dir / "regime_transition_matrix.csv")
        pd.DataFrame.from_dict(
            transitions["transition_probabilities"], orient="index"
        ).rename_axis("from_regime").to_csv(
            args.output_dir / "regime_transition_probabilities.csv"
        )
        pd.DataFrame.from_dict(transitions["persistence"], orient="index").rename_axis(
            "regime"
        ).to_csv(args.output_dir / "regime_persistence.csv")
        print(f"Single-timeframe reports: {args.output_dir}")

    if args.timeframe_dataset:
        datasets = {}
        for spec in args.timeframe_dataset:
            try:
                timeframe, filename = spec.split(",", 1)
            except ValueError:
                parser.error(f"Invalid --timeframe-dataset {spec!r}; expected TF,CSV")
            path = Path(filename)
            if not path.is_file():
                parser.error(f"Missing timeframe CSV: {path}")
            datasets[timeframe] = analyze_market(
                pd.read_csv(path), volatility_window=args.volatility_window
            )
        if len(datasets) < 2:
            parser.error("At least two --timeframe-dataset arguments are required")
        consensus = multi_timeframe_consensus(datasets)
        consensus.to_csv(args.output_dir / "multi_timeframe_consensus.csv", index=False)
        print(f"Multi-timeframe consensus: {args.output_dir / 'multi_timeframe_consensus.csv'}")


if __name__ == "__main__":
    main()
