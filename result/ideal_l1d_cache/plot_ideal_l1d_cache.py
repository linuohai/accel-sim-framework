#!/usr/bin/env python3
"""
Plot Ideal L1D vs Baseline comparisons for multiple traceL1 keys.

Inputs (for each key K):
  - Baseline log: result/log/{K}{baseline_suffix}.log
  - Ideal log:    result/log/{K}{ideal_suffix}.log
  - Baseline stall breakdown:
      result/issue_trace/stall_reason_pc_stats/{K}{baseline_suffix}/
        {K}{baseline_suffix}_stall_reason_breakdown.csv
  - Ideal stall breakdown:
      result/issue_trace/stall_reason_pc_stats/{K}{ideal_suffix}/
        {K}{ideal_suffix}_stall_reason_breakdown.csv

Outputs (written next to this script):
  - ipc_compare.svg
  - stall_breakdown_compare.svg

Notes:
  - If any workload has different gpu_tot_sim_insn between baseline and ideal,
    the performance plot falls back to cycles for ALL workloads (to keep a
    consistent axis). The output file name remains ipc_compare.svg.
  - This script is dependency-free (stdlib only).
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


STALL_REASONS: Tuple[str, ...] = (
    "MEM_WAIT",
    "REG_WAIT",
    "IBUFFER_EMPTY",
    "BARRIER",
    "CONTROL_HAZARD",
    "PIPE_BUSY",
    "DUAL_ISSUE_RESTRICT",
)

REASON_COLORS: Dict[str, str] = {
    "MEM_WAIT": "#1f77b4",
    "REG_WAIT": "#ff7f0e",
    "IBUFFER_EMPTY": "#2ca02c",
    "BARRIER": "#d62728",
    "CONTROL_HAZARD": "#9467bd",
    "PIPE_BUSY": "#8c564b",
    "DUAL_ISSUE_RESTRICT": "#e377c2",
}


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


@dataclass(frozen=True)
class RunTotals:
    cycles: int
    insn: int
    ipc_from_log: Optional[float]

    @property
    def ipc(self) -> float:
        # Prefer derived IPC to avoid relying on log formatting.
        if self.cycles <= 0:
            return 0.0
        return float(self.insn) / float(self.cycles)


def _repo_root_from_script(script_path: Path) -> Path:
    # .../accel-sim-framework/result/ideal_l1d_cache/plot_*.py -> accel-sim-framework
    return script_path.resolve().parents[2]


def _read_text_lines(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        yield from handle


def parse_totals_from_log(path: Path) -> RunTotals:
    cycles: Optional[int] = None
    insn: Optional[int] = None
    ipc: Optional[float] = None

    re_cycle = re.compile(r"^\s*gpu_tot_sim_cycle\s*=\s*([0-9]+)\s*$")
    re_insn = re.compile(r"^\s*gpu_tot_sim_insn\s*=\s*([0-9]+)\s*$")
    re_ipc = re.compile(r"^\s*gpu_tot_ipc\s*=\s*([0-9]*\.?[0-9]+)\s*$")

    for line in _read_text_lines(path):
        m = re_cycle.match(line)
        if m:
            cycles = int(m.group(1))
            continue
        m = re_insn.match(line)
        if m:
            insn = int(m.group(1))
            continue
        m = re_ipc.match(line)
        if m:
            ipc = float(m.group(1))
            continue

    if cycles is None or insn is None:
        raise SystemExit(f"failed to parse totals from log: {path}")
    return RunTotals(cycles=cycles, insn=insn, ipc_from_log=ipc)


def parse_stall_breakdown(path: Path) -> Dict[str, int]:
    totals = {reason: 0 for reason in STALL_REASONS}
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"empty csv: {path}")
        headers = {name.strip().lower() for name in reader.fieldnames if name}
        count_col: Optional[str] = None
        if "stall_warp_cycles" in headers:
            count_col = "stall_warp_cycles"
        elif "stall_warp_events" in headers:
            count_col = "stall_warp_events"
        if count_col is None:
            raise SystemExit(f"unexpected header in {path}: {reader.fieldnames}")

        for row in reader:
            reason = (row.get("reason") or "").strip().upper()
            if reason not in totals:
                continue
            raw = (row.get(count_col) or "").strip()
            try:
                totals[reason] += int(raw, 0)
            except ValueError:
                totals[reason] += 0
    return totals


def _write_svg(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_perf_svg(
    out_svg: Path,
    *,
    title: str,
    metric: str,
    items: Sequence[Tuple[str, float, float, str]],
    width: int = 1200,
) -> None:
    # items: (label, baseline_value, ideal_value, note)
    # This plot expects values already normalized (typically baseline=1.0).
    left_margin = 70
    right_margin = 30
    top_margin = 120
    bottom_margin = 85
    axis_color = "#333"
    grid_color = "#e6e6e6"

    height = 420
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_y0 = top_margin
    chart_y1 = height - bottom_margin
    chart_w = max(1, chart_x1 - chart_x0)
    chart_h = max(1, chart_y1 - chart_y0)

    baseline_color = "#4c78a8"
    ideal_color = "#f58518"

    max_value = 1.0
    for _, b, i, _ in items:
        max_value = max(max_value, b, i)
    max_value *= 1.15
    if max_value <= 0:
        max_value = 1.0

    def y_of(v: float) -> float:
        v = max(0.0, v)
        return chart_y1 - (v / max_value) * chart_h

    def h_of(v: float) -> float:
        v = max(0.0, v)
        return (v / max_value) * chart_h

    n = max(1, len(items))
    group_w = chart_w / float(n)
    bar_gap = max(6.0, group_w * 0.08)
    bar_w = min(42.0, (group_w - bar_gap) / 2.0)
    if bar_w < 10.0:
        bar_w = 10.0

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    lines.append(
        f'<text x="30" y="40" font-size="22" font-family="sans-serif">{_svg_escape(title)}</text>'
    )
    lines.append(f'<text x="30" y="82" font-size="13" fill="#444" font-family="sans-serif">{_svg_escape(metric)}</text>')

    # Legend
    legend_w = 220
    legend_x = max(chart_x0, chart_x1 - legend_w)
    legend_y = 60
    lines.append(f'<rect x="{legend_x}" y="{legend_y - 12}" width="14" height="14" fill="{baseline_color}"/>')
    lines.append(f'<text x="{legend_x + 20}" y="{legend_y}" font-size="13" font-family="sans-serif">baseline</text>')
    lines.append(f'<rect x="{legend_x + 110}" y="{legend_y - 12}" width="14" height="14" fill="{ideal_color}"/>')
    lines.append(f'<text x="{legend_x + 130}" y="{legend_y}" font-size="13" font-family="sans-serif">ideal</text>')

    # Grid + Y ticks
    ticks = 5
    for t in range(ticks + 1):
        v = (max_value * t) / float(ticks)
        y = y_of(v)
        lines.append(f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid_color}" stroke-width="1"/>')
        lines.append(
            f'<text x="{chart_x0 - 10}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#444" font-family="sans-serif">{v:.2f}</text>'
        )

    # Baseline reference line at 1.0
    if max_value >= 1.0:
        y1 = y_of(1.0)
        lines.append(f'<line x1="{chart_x0}" y1="{y1:.2f}" x2="{chart_x1}" y2="{y1:.2f}" stroke="#999" stroke-width="1.5"/>')

    # Axes
    lines.append(f'<line x1="{chart_x0}" y1="{chart_y0}" x2="{chart_x0}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.5"/>')
    lines.append(f'<line x1="{chart_x0}" y1="{chart_y1}" x2="{chart_x1}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.5"/>')

    # Bars
    for idx, (label, b, i, note) in enumerate(items):
        group_center = chart_x0 + group_w * (idx + 0.5)
        baseline_x = group_center - (bar_gap / 2.0) - bar_w
        ideal_x = group_center + (bar_gap / 2.0)

        # baseline bar
        bh = h_of(b)
        by = chart_y1 - bh
        lines.append(f'<rect x="{baseline_x:.2f}" y="{by:.2f}" width="{bar_w:.2f}" height="{bh:.2f}" fill="{baseline_color}"/>')
        lines.append(
            f'<text x="{baseline_x + bar_w / 2.0:.2f}" y="{by - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{b:.2f}</text>'
        )

        # ideal bar
        ih = h_of(i)
        iy = chart_y1 - ih
        lines.append(f'<rect x="{ideal_x:.2f}" y="{iy:.2f}" width="{bar_w:.2f}" height="{ih:.2f}" fill="{ideal_color}"/>')
        lines.append(
            f'<text x="{ideal_x + bar_w / 2.0:.2f}" y="{iy - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{i:.2f}</text>'
        )

        # x-axis label (rotate a bit for readability)
        label_y = chart_y1 + 28
        lines.append(
            f'<text x="{group_center:.2f}" y="{label_y:.2f}" text-anchor="middle" font-size="12" font-family="sans-serif" transform="rotate(-20 {group_center:.2f} {label_y:.2f})">{_svg_escape(label)}</text>'
        )
        if note:
            note_y = chart_y1 + 46
            lines.append(
                f'<text x="{group_center:.2f}" y="{note_y:.2f}" text-anchor="middle" font-size="10" fill="#666" font-family="sans-serif" transform="rotate(-20 {group_center:.2f} {note_y:.2f})">{_svg_escape(note)}</text>'
            )

    lines.append("</svg>")
    _write_svg(out_svg, lines)


def plot_stall_svg(
    out_svg: Path,
    *,
    title: str,
    subtitle: str,
    items: Sequence[Tuple[str, Dict[str, int], Dict[str, int]]],
    width: int = 1400,
) -> None:
    left_margin = 70
    right_margin = 30
    top_margin = 150
    bottom_margin = 110
    axis_color = "#333"
    grid_color = "#e6e6e6"

    height = 520
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_y0 = top_margin
    chart_y1 = height - bottom_margin
    chart_w = max(1, chart_x1 - chart_x0)
    chart_h = max(1, chart_y1 - chart_y0)

    def total(d: Dict[str, int]) -> int:
        return sum(int(d.get(r, 0)) for r in STALL_REASONS)

    # Normalize each workload by its baseline total stall warp-cycles.
    max_ratio = 1.0
    normalized: List[Tuple[str, Dict[str, float], Dict[str, float], float]] = []
    for label, b, i in items:
        btot = float(total(b))
        denom = btot if btot > 0 else 1.0
        b_norm = {r: float(int(b.get(r, 0))) / denom for r in STALL_REASONS}
        i_norm = {r: float(int(i.get(r, 0))) / denom for r in STALL_REASONS}
        ideal_total_ratio = sum(i_norm.values())
        max_ratio = max(max_ratio, 1.0, ideal_total_ratio)
        normalized.append((label, b_norm, i_norm, ideal_total_ratio))
    max_ratio *= 1.15

    def y_of(v: float) -> float:
        v = max(0.0, v)
        return chart_y1 - (v / max_ratio) * chart_h

    def h_of(v: float) -> float:
        v = max(0.0, v)
        return (v / max_ratio) * chart_h

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')

    lines.append(
        f'<text x="30" y="40" font-size="22" font-family="sans-serif">{_svg_escape(title)}</text>'
    )
    lines.append(
        f'<text x="30" y="68" font-size="13" fill="#444" font-family="sans-serif">{_svg_escape(subtitle)}</text>'
    )

    # Legend (compact grid)
    legend_y = top_margin - 45
    cols = 4
    cell_w = (chart_x1 - chart_x0) / float(cols)
    for idx, reason in enumerate(STALL_REASONS):
        row = idx // cols
        col = idx % cols
        x = chart_x0 + col * cell_w
        y = legend_y + row * 18
        color = REASON_COLORS.get(reason, "#999")
        lines.append(f'<rect x="{x:.2f}" y="{y - 11:.2f}" width="12" height="12" fill="{color}"/>')
        lines.append(
            f'<text x="{x + 16:.2f}" y="{y:.2f}" font-size="11" font-family="sans-serif">{_svg_escape(reason)}</text>'
        )

    # Grid + Y ticks
    ticks = 5
    for t in range(ticks + 1):
        v = (max_ratio * t) / float(ticks)
        y = y_of(v)
        lines.append(f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid_color}" stroke-width="1"/>')
        lines.append(
            f'<text x="{chart_x0 - 10}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#444" font-family="sans-serif">{v:.2f}</text>'
        )

    # Baseline reference line at 1.0
    if max_ratio >= 1.0:
        y1 = y_of(1.0)
        lines.append(f'<line x1="{chart_x0}" y1="{y1:.2f}" x2="{chart_x1}" y2="{y1:.2f}" stroke="#999" stroke-width="1.5"/>')

    # Axes
    lines.append(f'<line x1="{chart_x0}" y1="{chart_y0}" x2="{chart_x0}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.5"/>')
    lines.append(f'<line x1="{chart_x0}" y1="{chart_y1}" x2="{chart_x1}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.5"/>')

    # Bars (two stacked bars per workload group)
    n = max(1, len(normalized))
    group_w = chart_w / float(n)
    bar_gap = max(6.0, group_w * 0.08)
    bar_w = min(42.0, (group_w - bar_gap) / 2.0)
    if bar_w < 10.0:
        bar_w = 10.0

    for idx, (label, b_norm, i_norm, ideal_total_ratio) in enumerate(normalized):
        group_center = chart_x0 + group_w * (idx + 0.5)
        baseline_x = group_center - (bar_gap / 2.0) - bar_w
        ideal_x = group_center + (bar_gap / 2.0)

        # baseline stacked bar (total should be 1.0)
        y_cursor = chart_y1
        for reason in STALL_REASONS:
            v = float(b_norm.get(reason, 0.0))
            if v <= 0:
                continue
            h = h_of(v)
            y_cursor -= h
            lines.append(
                f'<rect x="{baseline_x:.2f}" y="{y_cursor:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{REASON_COLORS.get(reason, "#999")}"/>'
            )
        # baseline label and ratio
        lines.append(
            f'<text x="{baseline_x + bar_w / 2.0:.2f}" y="{chart_y1 + 18:.2f}" text-anchor="middle" font-size="11" fill="#444" font-family="sans-serif">baseline</text>'
        )
        lines.append(
            f'<text x="{baseline_x + bar_w / 2.0:.2f}" y="{y_of(1.0) - 6:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">1.00</text>'
        )

        # ideal stacked bar (normalized by baseline total)
        y_cursor = chart_y1
        for reason in STALL_REASONS:
            v = float(i_norm.get(reason, 0.0))
            if v <= 0:
                continue
            h = h_of(v)
            y_cursor -= h
            lines.append(
                f'<rect x="{ideal_x:.2f}" y="{y_cursor:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{REASON_COLORS.get(reason, "#999")}"/>'
            )
        lines.append(
            f'<text x="{ideal_x + bar_w / 2.0:.2f}" y="{chart_y1 + 18:.2f}" text-anchor="middle" font-size="11" fill="#444" font-family="sans-serif">ideal</text>'
        )
        lines.append(
            f'<text x="{ideal_x + bar_w / 2.0:.2f}" y="{y_of(ideal_total_ratio) - 6:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{ideal_total_ratio:.2f}</text>'
        )

        # x-axis label (rotate a bit)
        label_y = chart_y1 + 52
        lines.append(
            f'<text x="{group_center:.2f}" y="{label_y:.2f}" text-anchor="middle" font-size="12" font-family="sans-serif" transform="rotate(-20 {group_center:.2f} {label_y:.2f})">{_svg_escape(label)}</text>'
        )

    lines.append("</svg>")
    _write_svg(out_svg, lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Plot Ideal L1D vs baseline for multiple trace keys.")
    parser.add_argument("keys", nargs="+", help="traceL1 keys (e.g., bfs_usa bfs_web bfs_cit pathfinder)")
    parser.add_argument("--baseline-suffix", default="", help="baseline log_name suffix (default: empty)")
    parser.add_argument("--ideal-suffix", default="_ideal_l1d", help="ideal log_name suffix (default: _ideal_l1d)")
    args = parser.parse_args(argv)

    script_path = Path(__file__)
    base_dir = _repo_root_from_script(script_path)
    log_dir = base_dir / "result/log"
    stall_base = base_dir / "result/issue_trace/stall_reason_pc_stats"

    # Load inputs
    perf_rows: List[Tuple[str, RunTotals, RunTotals, str]] = []
    stall_rows: List[Tuple[str, Dict[str, int], Dict[str, int]]] = []
    insn_mismatch = False
    for key in args.keys:
        baseline_name = f"{key}{args.baseline_suffix}"
        ideal_name = f"{key}{args.ideal_suffix}"

        baseline_log = log_dir / f"{baseline_name}.log"
        ideal_log = log_dir / f"{ideal_name}.log"
        if not baseline_log.is_file():
            raise SystemExit(f"missing baseline log: {baseline_log}")
        if not ideal_log.is_file():
            raise SystemExit(f"missing ideal log: {ideal_log}")

        b_tot = parse_totals_from_log(baseline_log)
        i_tot = parse_totals_from_log(ideal_log)
        note = ""
        if b_tot.insn != i_tot.insn:
            insn_mismatch = True
            note = f"insn mismatch: {b_tot.insn} vs {i_tot.insn}"

        baseline_stall = stall_base / baseline_name / f"{baseline_name}_stall_reason_breakdown.csv"
        ideal_stall = stall_base / ideal_name / f"{ideal_name}_stall_reason_breakdown.csv"
        if not baseline_stall.is_file():
            raise SystemExit(f"missing baseline stall breakdown: {baseline_stall}")
        if not ideal_stall.is_file():
            raise SystemExit(f"missing ideal stall breakdown: {ideal_stall}")

        b_stall = parse_stall_breakdown(baseline_stall)
        i_stall = parse_stall_breakdown(ideal_stall)

        perf_rows.append((key, b_tot, i_tot, note))
        stall_rows.append((key, b_stall, i_stall))

    out_dir = script_path.resolve().parent
    out_ipc = out_dir / "ipc_compare.svg"
    out_stall = out_dir / "stall_breakdown_compare.svg"

    if insn_mismatch:
        metric = "Performance (normalized): speedup = baseline_cycles / run_cycles (baseline=1.0)"
        items = [
            (k, 1.0, (float(b.cycles) / float(i.cycles)) if i.cycles else 0.0, note)
            for k, b, i, note in perf_rows
        ]
        plot_perf_svg(out_ipc, title="Ideal L1D vs Baseline", metric=metric, items=items)
    else:
        metric = "Performance (normalized): IPC ratio = ideal_ipc / baseline_ipc (baseline=1.0)"
        items = [
            (k, 1.0, (i.ipc / b.ipc) if b.ipc else 0.0, "")
            for k, b, i, _ in perf_rows
        ]
        plot_perf_svg(out_ipc, title="Ideal L1D vs Baseline", metric=metric, items=items)

    plot_stall_svg(
        out_stall,
        title="Ideal L1D vs Baseline",
        subtitle="Issue-stall breakdown (stall warp-cycles) from stall_reason_pc_stats",
        items=stall_rows,
    )

    print(f"wrote: {out_ipc}")
    print(f"wrote: {out_stall}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
