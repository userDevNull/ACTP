"""Generate offline Phase 8 market intelligence reports from historical CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from app.intelligence.market_analysis import analyze_market, summarize_market


def main() -> None:
    parser = argparse.ArgumentParser(description="ACTP Phase 8 offline market intelligence")
    parser.add_argument("--candles", required=True, type=Path)
    parser.add_argument("--output-dir", default=Path("reports/phase8"), type=Path)
    parser.add_argument("--volatility-window", default=48, type=int)
    args = parser.parse_args()
    if not args.candles.is_file():
        parser.error(f"Missing candles CSV: {args.candles}")
    candles = pd.read_csv(args.candles)
    diagnostics = analyze_market(candles, volatility_window=args.volatility_window)
    summary = summarize_market(diagnostics)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "market_diagnostics.csv"
    json_path = args.output_dir / "market_summary.json"
    diagnostics.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Diagnostics: {csv_path}")
    print(f"Summary: {json_path}")
    print(f"Latest regime: {summary['latest_regime']}")


if __name__ == "__main__":
    main()
