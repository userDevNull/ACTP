"""Build a self-contained offline HTML dashboard from ACTP research JSON."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


PALETTE = ["#2563eb", "#16a34a", "#d97706", "#9333ea", "#dc2626", "#0891b2"]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _fmt(value: Any, suffix: str = "") -> str:
    number = _number(value)
    return "—" if number is None else f"{number:,.2f}{suffix}"


def _svg_bar_chart(
    title: str,
    rows: list[dict],
    label_field: str,
    value_field: str,
    suffix: str = "%",
) -> str:
    usable = [(str(row.get(label_field, "")), _number(row.get(value_field))) for row in rows]
    usable = [(label, value) for label, value in usable if value is not None]
    if not usable:
        return f'<section class="chart"><h3>{escape(title)}</h3><p>No data available.</p></section>'
    width, row_height, left, right = 1000, 30, 330, 90
    height = max(180, 75 + len(usable) * row_height)
    plot_width = width - left - right
    low = min(0.0, min(value for _, value in usable))
    high = max(0.0, max(value for _, value in usable))
    span = max(high - low, 1.0)
    pad = span * 0.08
    low -= pad
    high += pad
    scale = plot_width / (high - low)
    zero_x = left + (0 - low) * scale
    parts = [f'<section class="chart"><h3>{escape(title)}</h3>',
             f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">']
    parts.append(f'<line x1="{zero_x:.1f}" y1="35" x2="{zero_x:.1f}" y2="{height-20}" stroke="#64748b" stroke-dasharray="4 4"/>')
    for index, (label, value) in enumerate(usable):
        y = 45 + index * row_height
        x_value = left + (value - low) * scale
        x = min(zero_x, x_value)
        bar_width = max(1.0, abs(x_value - zero_x))
        color = "#16a34a" if value >= 0 else "#dc2626"
        parts.append(f'<text x="{left-12}" y="{y+14}" text-anchor="end" class="axis-label">{escape(label[:48])}</text>')
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{bar_width:.1f}" height="18" rx="3" fill="{color}"/>')
        value_x = min(width-right+6, max(left+4, x_value + (8 if value >= 0 else -8)))
        anchor = "start" if value >= 0 else "end"
        parts.append(f'<text x="{value_x:.1f}" y="{y+14}" text-anchor="{anchor}" class="value-label">{value:,.2f}{escape(suffix)}</text>')
    parts.append("</svg></section>")
    return "".join(parts)


def _svg_line_chart(title: str, rows: list[dict], y_field: str) -> str:
    series: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        x, y = _number(row.get("multiplier")), _number(row.get(y_field))
        if x is not None and y is not None:
            series[str(row.get("strategy", "strategy"))].append((x, y))
    if not series:
        return f'<section class="chart"><h3>{escape(title)}</h3><p>No data available.</p></section>'
    width, height = 900, 350
    left, right, top, bottom = 72, 24, 28, 68
    all_points = [point for points in series.values() for point in points]
    min_x, max_x = min(p[0] for p in all_points), max(p[0] for p in all_points)
    min_y, max_y = min(0.0, min(p[1] for p in all_points)), max(0.0, max(p[1] for p in all_points))
    if max_x == min_x:
        max_x = min_x + 1
    if max_y == min_y:
        max_y = min_y + 1
    y_pad = (max_y - min_y) * 0.1
    min_y -= y_pad
    max_y += y_pad
    plot_w, plot_h = width-left-right, height-top-bottom
    xmap = lambda value: left + (value-min_x)/(max_x-min_x)*plot_w
    ymap = lambda value: top + (max_y-value)/(max_y-min_y)*plot_h
    parts = [f'<section class="chart"><h3>{escape(title)}</h3>',
             f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
             f'<line x1="{left}" y1="{ymap(0):.1f}" x2="{width-right}" y2="{ymap(0):.1f}" stroke="#94a3b8" stroke-dasharray="4 4"/>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#64748b"/>',
             f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#64748b"/>']
    for tick in range(5):
        value = min_y + (max_y - min_y) * tick / 4
        y = ymap(value)
        parts.append(f'<line x1="{left-4}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#e2e8f0"/>')
        parts.append(f'<text x="{left-9}" y="{y+4:.1f}" text-anchor="end" class="axis-label">{value:.1f}%</text>')
    for value in sorted({point[0] for point in all_points}):
        x = xmap(value)
        parts.append(f'<line x1="{x:.1f}" y1="{height-bottom}" x2="{x:.1f}" y2="{height-bottom+4}" stroke="#64748b"/>')
        parts.append(f'<text x="{x:.1f}" y="{height-bottom+18}" text-anchor="middle" class="axis-label">{value:g}x</text>')
    for index, (name, points) in enumerate(sorted(series.items())):
        points.sort()
        color = PALETTE[index % len(PALETTE)]
        coords = " ".join(f"{xmap(x):.1f},{ymap(y):.1f}" for x, y in points)
        parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
        for x, y in points:
            parts.append(f'<circle cx="{xmap(x):.1f}" cy="{ymap(y):.1f}" r="4" fill="{color}"/>')
        legend_x = left + (index % 3) * 260
        legend_y = height - 34 + (index // 3) * 17
        parts.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x+18}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{legend_x+24}" y="{legend_y+4}" class="axis-label">{escape(name)}</text>')
    parts.append(f'<text x="{width/2}" y="{height-6}" text-anchor="middle" class="axis-label">Multiplier of base setting</text>')
    parts.append("</svg></section>")
    return "".join(parts)


def _svg_interval_chart(title: str, rows: list[dict]) -> str:
    usable = []
    for row in rows:
        median = _number(row.get("final_equity_median"))
        low = _number(row.get("final_equity_p05"))
        high = _number(row.get("final_equity_p95"))
        if median is not None and low is not None and high is not None:
            label = " / ".join(str(row.get(key, "")) for key in ("symbol", "timeframe", "strategy"))
            usable.append((label, low, median, high))
    if not usable:
        return f'<section class="chart"><h3>{escape(title)}</h3><p>No data available.</p></section>'
    width, row_height, left, right = 1000, 32, 350, 90
    height = max(180, 75 + len(usable)*row_height)
    low_value = min(x[1] for x in usable)
    high_value = max(x[3] for x in usable)
    if high_value == low_value:
        high_value = low_value + 1
    scale = (width-left-right)/(high_value-low_value)
    parts = [f'<section class="chart"><h3>{escape(title)}</h3>',
             f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">']
    for index, (label, low, median, high) in enumerate(usable):
        y = 44 + index*row_height
        x1, xm, x2 = (left+(v-low_value)*scale for v in (low, median, high))
        parts.append(f'<text x="{left-12}" y="{y+5}" text-anchor="end" class="axis-label">{escape(label[:48])}</text>')
        parts.append(f'<line x1="{x1:.1f}" y1="{y}" x2="{x2:.1f}" y2="{y}" stroke="#64748b" stroke-width="5" stroke-linecap="round"/>')
        parts.append(f'<circle cx="{xm:.1f}" cy="{y}" r="6" fill="#2563eb"/>')
        parts.append(f'<text x="{min(width-right+8,x2+8):.1f}" y="{y+5}" class="value-label">{median:,.2f}</text>')
    parts.append("</svg><p class=\"note\">Line: 5th–95th percentile; dot: median. Trade-level bootstrap approximation, not a forecast.</p></section>")
    return "".join(parts)


def build_research_dashboard(report: dict) -> str:
    """Render validation, benchmark, sensitivity and bootstrap views."""
    results = report.get("results", [])
    benchmarks = report.get("benchmarks", [])
    sensitivity = report.get("sensitivity", [])
    monte_carlo = report.get("monte_carlo", [])
    datasets = report.get("datasets", [])
    validation_base = [
        row for row in results
        if row.get("segment") == "validation" and row.get("cost_scenario") == "base_cost"
    ]
    strategy_bars = [
        {**row, "label": f'{row.get("symbol","")} {row.get("timeframe","")} · {row.get("strategy","")}'}
        for row in validation_base
    ]
    benchmark_bars = [
        {**row, "label": f'{row.get("symbol","")} {row.get("timeframe","")} · {row.get("benchmark","")} · {row.get("segment","")}'}
        for row in benchmarks
        if row.get("segment") in ("validation", "test") and row.get("cost_scenario") == "base_cost"
    ]
    validation_mc = [
        row for row in monte_carlo
        if row.get("segment") == "validation" and row.get("cost_scenario") == "base_cost"
    ]

    charts = [
        _svg_bar_chart("Validation returns — strategies (base costs)", strategy_bars, "label", "net_return_pct"),
        _svg_bar_chart("Matched benchmark returns — validation and test", benchmark_bars, "label", "net_return_pct"),
        _svg_interval_chart("Validation bootstrap final-equity distribution", validation_mc),
    ]
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in sensitivity:
        groups[(str(row.get("symbol", "")), str(row.get("timeframe", "")))].append(row)
    for (symbol, timeframe), group in sorted(groups.items()):
        for parameter in ("risk_fraction", "leverage", "taker_fee_rate", "slippage_rate"):
            selected = [row for row in group if row.get("parameter") == parameter]
            charts.append(_svg_line_chart(
                f"Sensitivity — {symbol} {timeframe} — {parameter}",
                selected,
                "net_return_pct",
            ))

    table_rows = []
    for row in sorted(validation_base, key=lambda item: _number(item.get("net_return_pct")) or 0, reverse=True):
        table_rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('symbol','')))}</td>"
            f"<td>{escape(str(row.get('timeframe','')))}</td>"
            f"<td>{escape(str(row.get('strategy','')))}</td>"
            f"<td>{_fmt(row.get('net_return_pct'), '%')}</td>"
            f"<td>{_fmt(row.get('excess_return_vs_spot_pct'), '%')}</td>"
            f"<td>{_fmt(row.get('max_drawdown_pct'), '%')}</td>"
            f"<td>{_fmt(row.get('trades'))}</td>"
            "</tr>"
        )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    warning = escape(str(report.get("warning", "Research only; not a live-trading recommendation.")))
    dataset_text = ", ".join(
        f"{escape(str(item.get('symbol','')))} {escape(str(item.get('timeframe','')))} ({escape(str(item.get('candles','?')))} candles)"
        for item in datasets
    ) or "Dataset metadata not supplied"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ACTP — Offline Research Dashboard</title>
<style>
:root{{--bg:#f4f7fb;--panel:#fff;--ink:#172033;--muted:#64748b;--line:#dbe3ee;--blue:#2563eb}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}
header{{padding:32px max(20px,calc((100vw - 1180px)/2));background:#101c34;color:#fff}}
header h1{{margin:0 0 8px;font-size:28px}}header p{{margin:4px 0;color:#cbd5e1}}
main{{max-width:1180px;margin:24px auto;padding:0 18px 48px}}
.notice{{padding:14px 16px;border-left:4px solid #d97706;background:#fff7ed;border-radius:8px;margin-bottom:20px}}
section.chart,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;margin:16px 0;overflow:hidden}}
h2{{font-size:21px;margin:28px 0 10px}}h3{{font-size:17px;margin:0 0 12px}}svg{{width:100%;height:auto;display:block;overflow:visible}}
.axis-label{{font-size:12px;fill:#475569}}.value-label{{font-size:12px;fill:#0f172a;font-weight:600}}
.note,.muted{{color:var(--muted);font-size:13px}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}th{{background:#f8fafc}}
.table-wrap{{overflow-x:auto}}.meta{{display:flex;gap:16px;flex-wrap:wrap;color:#cbd5e1;font-size:13px}}
@media(max-width:700px){{header h1{{font-size:23px}}section.chart,.panel{{padding:10px}}}}
</style>
</head>
<body>
<header><h1>ACTP Research Dashboard</h1><p>Offline strategy, benchmark, sensitivity and bootstrap review</p><div class="meta"><span>Generated: {generated}</span><span>Datasets: {dataset_text}</span></div></header>
<main>
<div class="notice"><strong>Research only.</strong> {warning} Charts summarize historical backtests and bootstrap diagnostics. They do not predict future returns or model all exchange execution and liquidation conditions.</div>
<h2>Validation performance</h2>
<p class="muted">Strategy returns are shown after configured costs. Excess return versus spot is also listed below. Use validation for comparisons; keep the final test segment for frozen evaluation.</p>
{charts[0]}
{charts[1]}
<div class="panel"><h3>Validation strategy scorecard — base costs</h3><div class="table-wrap"><table><thead><tr><th>Symbol</th><th>Timeframe</th><th>Strategy</th><th>Return</th><th>Excess vs spot</th><th>Max drawdown</th><th>Trades</th></tr></thead><tbody>{''.join(table_rows) or '<tr><td colspan="7">No validation results available.</td></tr>'}</tbody></table></div></div>
<h2>Bootstrap robustness</h2>
{charts[2]}
<h2>Parameter sensitivity</h2>
<p class="muted">One-factor-at-a-time validation-only sensitivity. A flatter curve generally indicates less dependence on that parameter within the tested range; it does not establish profitability or robustness outside the tested range.</p>
{''.join(charts[3:]) or '<div class="panel">No sensitivity data available.</div>'}
<footer class="muted">Generated by ACTP. This file is self-contained and can be opened locally without a network connection.</footer>
</main>
</body></html>"""


def write_research_dashboard(report: dict, output_path: str | Path) -> Path:
    """Write the self-contained HTML report and return its path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_research_dashboard(report), encoding="utf-8")
    return path
