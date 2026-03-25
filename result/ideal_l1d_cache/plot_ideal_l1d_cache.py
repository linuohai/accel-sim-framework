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

Outputs (written next to this script, with a YYYYMM_ prefix):
  - <YYYYMM>[_TAG]_ipc_compare.svg
  - <YYYYMM>[_TAG]_stall_breakdown_compare.svg

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
from datetime import datetime
from hashlib import md5
from math import ceil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


PREFERRED_STALL_REASONS: Tuple[str, ...] = (
    "MEM_WAIT",
    "WAIT_ATOMIC",
    "PIPE_BUSY",
    "IBUFFER_EMPTY",
    "WAIT_CTA_BARRIER",
    "BARRIER",
    "CONTROL_HAZARD",
    "REG_WAIT",
    "WAIT_MEMBAR",
    "WAIT_LDGSTS",
    "DUAL_ISSUE_RESTRICT",
    "WAIT_DONE",
)

REASON_COLORS: Dict[str, str] = {
    "MEM_WAIT": "#1f77b4",
    "WAIT_ATOMIC": "#17becf",
    "REG_WAIT": "#ff7f0e",
    "IBUFFER_EMPTY": "#2ca02c",
    "BARRIER": "#d62728",
    "WAIT_CTA_BARRIER": "#d62728",
    "WAIT_MEMBAR": "#bcbd22",
    "WAIT_LDGSTS": "#bcbd22",
    "WAIT_DONE": "#7f7f7f",
    "CONTROL_HAZARD": "#9467bd",
    "PIPE_BUSY": "#8c564b",
    "DUAL_ISSUE_RESTRICT": "#e377c2",
}

FALLBACK_PALETTE: Tuple[str, ...] = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
)


def _reason_color(reason: str) -> str:
    reason = reason.strip().upper()
    if reason in REASON_COLORS:
        return REASON_COLORS[reason]
    h = int(md5(reason.encode("utf-8", errors="ignore")).hexdigest()[:8], 16)
    return FALLBACK_PALETTE[h % len(FALLBACK_PALETTE)]


def _ordered_stall_reasons(reasons: Iterable[str]) -> List[str]:
    deduped = {r.strip().upper() for r in reasons if r and r.strip()}
    ordered = [r for r in PREFERRED_STALL_REASONS if r in deduped]
    ordered.extend(sorted(r for r in deduped if r not in set(ordered)))
    return ordered


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
    totals: Dict[str, int] = {}
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
            if not reason:
                continue
            raw = (row.get(count_col) or "").strip()
            try:
                totals[reason] = totals.get(reason, 0) + int(raw, 0)
            except ValueError:
                totals[reason] = totals.get(reason, 0) + 0
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
    baseline_color: str = "#7b2cbf",
    ideal_color: str = "#00c853",
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
    # No whitespace between baseline/ideal bars for the same workload.
    bar_gap = 0.0
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


def plot_perf_svg_3(
    out_svg: Path,
    *,
    title: str,
    metric: str,
    items: Sequence[Tuple[str, float, float, float, str]],
    baseline_color: str,
    ideal_color: str,
    gto_color: str,
    width: int = 1400,
) -> None:
    # items: (label, baseline_value, ideal_value, gto_value, note)
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

    max_value = 1.0
    for _, b, i, g, _ in items:
        max_value = max(max_value, b, i, g)
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
    bar_gap = 0.0
    bar_w = min(36.0, (group_w - bar_gap) / 3.0)
    if bar_w < 8.0:
        bar_w = 8.0

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    lines.append(
        f'<text x="30" y="40" font-size="22" font-family="sans-serif">{_svg_escape(title)}</text>'
    )
    lines.append(
        f'<text x="30" y="82" font-size="13" fill="#444" font-family="sans-serif">{_svg_escape(metric)}</text>'
    )

    # Legend
    legend_w = 360
    legend_x = max(chart_x0, chart_x1 - legend_w)
    legend_y = 60
    lines.append(f'<rect x="{legend_x}" y="{legend_y - 12}" width="14" height="14" fill="{baseline_color}"/>')
    lines.append(f'<text x="{legend_x + 20}" y="{legend_y}" font-size="13" font-family="sans-serif">baseline</text>')
    lines.append(f'<rect x="{legend_x + 110}" y="{legend_y - 12}" width="14" height="14" fill="{ideal_color}"/>')
    lines.append(f'<text x="{legend_x + 130}" y="{legend_y}" font-size="13" font-family="sans-serif">ideal-l1d</text>')
    lines.append(f'<rect x="{legend_x + 230}" y="{legend_y - 12}" width="14" height="14" fill="{gto_color}"/>')
    lines.append(f'<text x="{legend_x + 250}" y="{legend_y}" font-size="13" font-family="sans-serif">gto</text>')

    # Grid + Y ticks
    ticks = 5
    for t in range(ticks + 1):
        v = (max_value * t) / float(ticks)
        y = y_of(v)
        lines.append(
            f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid_color}" stroke-width="1"/>'
        )
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

    # Bars (3 per workload group, no gaps)
    for idx, (label, b, i, g, note) in enumerate(items):
        group_center = chart_x0 + group_w * (idx + 0.5)
        left_x = group_center - (1.5 * bar_w)
        baseline_x = left_x
        ideal_x = left_x + bar_w
        gto_x = left_x + 2.0 * bar_w

        # baseline
        bh = h_of(b)
        by = chart_y1 - bh
        lines.append(f'<rect x="{baseline_x:.2f}" y="{by:.2f}" width="{bar_w:.2f}" height="{bh:.2f}" fill="{baseline_color}"/>')
        lines.append(
            f'<text x="{baseline_x + bar_w / 2.0:.2f}" y="{by - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{b:.2f}</text>'
        )

        # ideal
        ih = h_of(i)
        iy = chart_y1 - ih
        lines.append(f'<rect x="{ideal_x:.2f}" y="{iy:.2f}" width="{bar_w:.2f}" height="{ih:.2f}" fill="{ideal_color}"/>')
        lines.append(
            f'<text x="{ideal_x + bar_w / 2.0:.2f}" y="{iy - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{i:.2f}</text>'
        )

        # gto
        gh = h_of(g)
        gy = chart_y1 - gh
        lines.append(f'<rect x="{gto_x:.2f}" y="{gy:.2f}" width="{bar_w:.2f}" height="{gh:.2f}" fill="{gto_color}"/>')
        lines.append(
            f'<text x="{gto_x + bar_w / 2.0:.2f}" y="{gy - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{g:.2f}</text>'
        )

        # x-axis label
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


def plot_perf_svg_4(
    out_svg: Path,
    *,
    title: str,
    metric: str,
    items: Sequence[Tuple[str, float, float, float, float, str]],
    baseline_color: str,
    ideal_color: str,
    gto_color: str,
    gto_ideal_color: str,
    width: int = 1600,
) -> None:
    # items: (label, baseline_value, ideal_value, gto_value, gto_ideal_value, note)
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

    max_value = 1.0
    for _, b, i, g, gi, _ in items:
        max_value = max(max_value, b, i, g, gi)
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
    bar_gap = 0.0
    bar_w = min(30.0, (group_w - bar_gap) / 4.0)
    if bar_w < 7.0:
        bar_w = 7.0

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    lines.append(
        f'<text x="30" y="40" font-size="22" font-family="sans-serif">{_svg_escape(title)}</text>'
    )
    lines.append(
        f'<text x="30" y="82" font-size="13" fill="#444" font-family="sans-serif">{_svg_escape(metric)}</text>'
    )

    # Legend
    legend_w = 520
    legend_x = max(chart_x0, chart_x1 - legend_w)
    legend_y = 60
    lines.append(f'<rect x="{legend_x}" y="{legend_y - 12}" width="14" height="14" fill="{baseline_color}"/>')
    lines.append(f'<text x="{legend_x + 20}" y="{legend_y}" font-size="13" font-family="sans-serif">baseline</text>')
    lines.append(f'<rect x="{legend_x + 110}" y="{legend_y - 12}" width="14" height="14" fill="{ideal_color}"/>')
    lines.append(f'<text x="{legend_x + 130}" y="{legend_y}" font-size="13" font-family="sans-serif">ideal-l1d</text>')
    lines.append(f'<rect x="{legend_x + 230}" y="{legend_y - 12}" width="14" height="14" fill="{gto_color}"/>')
    lines.append(f'<text x="{legend_x + 250}" y="{legend_y}" font-size="13" font-family="sans-serif">gto</text>')
    lines.append(f'<rect x="{legend_x + 320}" y="{legend_y - 12}" width="14" height="14" fill="{gto_ideal_color}"/>')
    lines.append(f'<text x="{legend_x + 340}" y="{legend_y}" font-size="13" font-family="sans-serif">gto+ideal-l1d (vs gto)</text>')

    # Grid + Y ticks
    ticks = 5
    for t in range(ticks + 1):
        v = (max_value * t) / float(ticks)
        y = y_of(v)
        lines.append(
            f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid_color}" stroke-width="1"/>'
        )
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

    # Bars (4 per workload group, no gaps)
    for idx, (label, b, i, g, gi, note) in enumerate(items):
        group_center = chart_x0 + group_w * (idx + 0.5)
        left_x = group_center - (2.0 * bar_w)
        baseline_x = left_x
        ideal_x = left_x + bar_w
        gto_x = left_x + 2.0 * bar_w
        gto_ideal_x = left_x + 3.0 * bar_w

        # baseline
        bh = h_of(b)
        by = chart_y1 - bh
        lines.append(f'<rect x="{baseline_x:.2f}" y="{by:.2f}" width="{bar_w:.2f}" height="{bh:.2f}" fill="{baseline_color}"/>')
        lines.append(
            f'<text x="{baseline_x + bar_w / 2.0:.2f}" y="{by - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{b:.2f}</text>'
        )

        # ideal
        ih = h_of(i)
        iy = chart_y1 - ih
        lines.append(f'<rect x="{ideal_x:.2f}" y="{iy:.2f}" width="{bar_w:.2f}" height="{ih:.2f}" fill="{ideal_color}"/>')
        lines.append(
            f'<text x="{ideal_x + bar_w / 2.0:.2f}" y="{iy - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{i:.2f}</text>'
        )

        # gto
        gh = h_of(g)
        gy = chart_y1 - gh
        lines.append(f'<rect x="{gto_x:.2f}" y="{gy:.2f}" width="{bar_w:.2f}" height="{gh:.2f}" fill="{gto_color}"/>')
        lines.append(
            f'<text x="{gto_x + bar_w / 2.0:.2f}" y="{gy - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{g:.2f}</text>'
        )

        # gto+ideal
        gih = h_of(gi)
        giy = chart_y1 - gih
        lines.append(
            f'<rect x="{gto_ideal_x:.2f}" y="{giy:.2f}" width="{bar_w:.2f}" height="{gih:.2f}" fill="{gto_ideal_color}"/>'
        )
        gi_rel = (gi / g) if g > 0 else 0.0
        lines.append(
            f'<text x="{gto_ideal_x + bar_w / 2.0:.2f}" y="{giy - 4:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">{gi_rel:.2f}</text>'
        )

        # x-axis label
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
    bottom_margin = 110
    axis_color = "#333"
    grid_color = "#e6e6e6"

    all_reasons: List[str] = []
    for _, b, i in items:
        all_reasons.extend(b.keys())
        all_reasons.extend(i.keys())
    reasons = _ordered_stall_reasons(all_reasons)

    legend_cols = 4
    legend_row_h = 18
    legend_rows = max(1, int(ceil(len(reasons) / float(legend_cols))))
    legend_y = 90
    chart_y0 = legend_y + legend_rows * legend_row_h + 30
    min_chart_h = 260
    height = max(520, chart_y0 + min_chart_h + bottom_margin)

    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_y1 = height - bottom_margin
    chart_w = max(1, chart_x1 - chart_x0)
    chart_h = max(1, chart_y1 - chart_y0)

    def total(d: Dict[str, int]) -> int:
        return sum(int(v) for v in d.values())

    # Plot as a single chart that fuses:
    # - composition (stacked by stall reason)
    # - total change (ideal bar height equals total_ideal / total_baseline)
    max_ratio = 1.0
    normalized: List[Tuple[str, Dict[str, float], Dict[str, float], float]] = []
    for label, b, i in items:
        btot = float(total(b))
        itot = float(total(i))
        denom = btot if btot > 0 else 1.0
        b_norm = {r: float(int(b.get(r, 0))) / denom for r in reasons}
        i_norm = {r: float(int(i.get(r, 0))) / denom for r in reasons}
        ideal_total_ratio = (itot / btot) if btot > 0 else 0.0
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
    cell_w = (chart_x1 - chart_x0) / float(legend_cols)
    for idx, reason in enumerate(reasons):
        row = idx // legend_cols
        col = idx % legend_cols
        x = chart_x0 + col * cell_w
        y = legend_y + row * legend_row_h
        color = _reason_color(reason)
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
            f'<text x="{chart_x0 - 10}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#444" font-family="sans-serif">{v * 100:.0f}%</text>'
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
        for reason in reasons:
            v = float(b_norm.get(reason, 0.0))
            if v <= 0:
                continue
            h = h_of(v)
            y_cursor -= h
            lines.append(
                f'<rect x="{baseline_x:.2f}" y="{y_cursor:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{_reason_color(reason)}"/>'
            )
        # baseline label and ratio
        lines.append(
            f'<text x="{baseline_x + bar_w / 2.0:.2f}" y="{chart_y1 + 18:.2f}" text-anchor="middle" font-size="11" fill="#444" font-family="sans-serif">baseline</text>'
        )
        lines.append(
            f'<text x="{baseline_x + bar_w / 2.0:.2f}" y="{y_of(1.0) - 6:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">tot=1.00x</text>'
        )

        # ideal stacked bar (normalized)
        y_cursor = chart_y1
        for reason in reasons:
            v = float(i_norm.get(reason, 0.0))
            if v <= 0:
                continue
            h = h_of(v)
            y_cursor -= h
            lines.append(
                f'<rect x="{ideal_x:.2f}" y="{y_cursor:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{_reason_color(reason)}"/>'
            )
        lines.append(
            f'<text x="{ideal_x + bar_w / 2.0:.2f}" y="{chart_y1 + 18:.2f}" text-anchor="middle" font-size="11" fill="#444" font-family="sans-serif">ideal</text>'
        )
        lines.append(
            f'<text x="{ideal_x + bar_w / 2.0:.2f}" y="{y_of(ideal_total_ratio) - 6:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif">tot={ideal_total_ratio:.2f}x</text>'
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
    parser.add_argument("keys", nargs="*", help="traceL1 keys (e.g., bfs_usa bfs_web bfs_cit pathfinder)")
    parser.add_argument("--baseline-suffix", default="", help="baseline log_name suffix (default: empty)")
    parser.add_argument("--ideal-suffix", default="_ideal_l1d", help="ideal log_name suffix (default: _ideal_l1d)")
    parser.add_argument(
        "--pair",
        action="append",
        default=[],
        help="Explicit mapping: [label=]baseline,ideal[,gto,gto_ideal] (repeatable; names are log_name stems w/o .log)",
    )
    parser.add_argument("--with-gto", action="store_true", help="Add a third IPC bar for gto (normalized to baseline)")
    parser.add_argument(
        "--with-gto-ideal",
        action="store_true",
        help="Add a fourth IPC bar for gto+ideal-l1d (normalized to baseline)",
    )
    parser.add_argument("--gto-suffix", default="_gto", help="gto log_name suffix (default: _gto)")
    parser.add_argument("--tag", default="", help="Output tag inserted after YYYYMM_ prefix")
    parser.add_argument("--out-ipc", default="", help="Write IPC SVG to this path (overrides default naming)")
    parser.add_argument(
        "--ipc-baseline-color",
        default="#2b2d42",
        help="IPC plot baseline bar color (#RRGGBB)",
    )
    parser.add_argument(
        "--ipc-ideal-color",
        default="#f77f00",
        help="IPC plot ideal bar color (#RRGGBB)",
    )
    parser.add_argument(
        "--ipc-gto-color",
        default="#3b5bdb",
        help="IPC plot gto bar color (#RRGGBB)",
    )
    parser.add_argument(
        "--ipc-gto-ideal-color",
        default="#d6336c",
        help="IPC plot gto+ideal-l1d bar color (#RRGGBB)",
    )
    parser.add_argument("--skip-ipc", action="store_true", help="Skip IPC plot output")
    parser.add_argument("--skip-stall", action="store_true", help="Skip stall breakdown plot output")
    args = parser.parse_args(argv)

    color_re = re.compile(r"^#[0-9a-fA-F]{6}$")
    if not color_re.match(args.ipc_baseline_color):
        raise SystemExit(f"invalid --ipc-baseline-color (expected #RRGGBB): {args.ipc_baseline_color!r}")
    if not color_re.match(args.ipc_ideal_color):
        raise SystemExit(f"invalid --ipc-ideal-color (expected #RRGGBB): {args.ipc_ideal_color!r}")
    if not color_re.match(args.ipc_gto_color):
        raise SystemExit(f"invalid --ipc-gto-color (expected #RRGGBB): {args.ipc_gto_color!r}")
    if not color_re.match(args.ipc_gto_ideal_color):
        raise SystemExit(f"invalid --ipc-gto-ideal-color (expected #RRGGBB): {args.ipc_gto_ideal_color!r}")

    script_path = Path(__file__)
    base_dir = _repo_root_from_script(script_path)
    log_dir = base_dir / "result/log"
    stall_base = base_dir / "result/issue_trace/stall_reason_pc_stats"

    with_gto = bool(args.with_gto or args.with_gto_ideal)
    cases: List[Tuple[str, str, str, str, str]] = []
    for key in args.keys:
        baseline_name = f"{key}{args.baseline_suffix}"
        ideal_name = f"{key}{args.ideal_suffix}"
        gto_name = f"{baseline_name}{args.gto_suffix}" if not baseline_name.endswith(args.gto_suffix) else baseline_name
        gto_ideal_name = f"{ideal_name}{args.gto_suffix}" if not ideal_name.endswith(args.gto_suffix) else ideal_name
        cases.append((key, baseline_name, ideal_name, gto_name, gto_ideal_name))

    for raw in args.pair:
        raw = (raw or "").strip()
        if not raw:
            continue
        if "=" in raw:
            label, rest = raw.split("=", 1)
            label = label.strip()
            rest = rest.strip()
        else:
            label = ""
            rest = raw
        parts = [p.strip() for p in rest.split(",") if p.strip()]
        if len(parts) not in (2, 4):
            raise SystemExit(f"invalid --pair (expected [label=]baseline,ideal[,gto,gto_ideal]): {raw!r}")
        baseline_name, ideal_name = parts[0], parts[1]
        if not label:
            label = baseline_name
        if len(parts) == 4:
            gto_name, gto_ideal_name = parts[2], parts[3]
        else:
            gto_name = f"{baseline_name}{args.gto_suffix}" if not baseline_name.endswith(args.gto_suffix) else baseline_name
            gto_ideal_name = f"{ideal_name}{args.gto_suffix}" if not ideal_name.endswith(args.gto_suffix) else ideal_name
        cases.append((label, baseline_name, ideal_name, gto_name, gto_ideal_name))

    if not cases:
        raise SystemExit("no workloads specified: pass keys and/or --pair")
    if args.skip_ipc and args.skip_stall:
        raise SystemExit("nothing to do: both --skip-ipc and --skip-stall are set")

    # Load inputs
    perf_rows: List[
        Tuple[str, RunTotals, RunTotals, Optional[RunTotals], Optional[RunTotals], str]
    ] = []
    stall_rows: List[Tuple[str, Dict[str, int], Dict[str, int]]] = []
    insn_mismatch = False
    for label, baseline_name, ideal_name, gto_name, gto_ideal_name in cases:
        baseline_log = log_dir / f"{baseline_name}.log"
        ideal_log = log_dir / f"{ideal_name}.log"
        if not baseline_log.is_file():
            raise SystemExit(f"missing baseline log: {baseline_log}")
        if not ideal_log.is_file():
            raise SystemExit(f"missing ideal log: {ideal_log}")

        b_tot = parse_totals_from_log(baseline_log)
        i_tot = parse_totals_from_log(ideal_log)
        g_tot: Optional[RunTotals] = None
        gi_tot: Optional[RunTotals] = None
        if with_gto:
            gto_log = log_dir / f"{gto_name}.log"
            if not gto_log.is_file():
                raise SystemExit(f"missing gto log: {gto_log}")
            g_tot = parse_totals_from_log(gto_log)
        if args.with_gto_ideal:
            gi_log = log_dir / f"{gto_ideal_name}.log"
            if not gi_log.is_file():
                # Fallback for some older naming patterns (e.g., fa4k):
                # <baseline>_gto_ideal_l1d_gto instead of <baseline>_ideal_l1d_gto
                alt = f"{gto_name}{args.ideal_suffix}"
                if not alt.endswith(args.gto_suffix):
                    alt = f"{alt}{args.gto_suffix}"
                alt_log = log_dir / f"{alt}.log"
                if alt_log.is_file():
                    gi_log = alt_log
                else:
                    raise SystemExit(f"missing gto+ideal log: {gi_log}")
            gi_tot = parse_totals_from_log(gi_log)
        note = ""
        if (
            b_tot.insn != i_tot.insn
            or (g_tot is not None and b_tot.insn != g_tot.insn)
            or (gi_tot is not None and b_tot.insn != gi_tot.insn)
        ):
            insn_mismatch = True
            note = f"insn mismatch: {b_tot.insn} vs {i_tot.insn}"
        perf_rows.append((label, b_tot, i_tot, g_tot, gi_tot, note))

        if args.skip_stall:
            continue
        baseline_stall = stall_base / baseline_name / f"{baseline_name}_stall_reason_breakdown.csv"
        ideal_stall = stall_base / ideal_name / f"{ideal_name}_stall_reason_breakdown.csv"
        if not baseline_stall.is_file():
            raise SystemExit(f"missing baseline stall breakdown: {baseline_stall}")
        if not ideal_stall.is_file():
            raise SystemExit(f"missing ideal stall breakdown: {ideal_stall}")

        b_stall = parse_stall_breakdown(baseline_stall)
        i_stall = parse_stall_breakdown(ideal_stall)
        stall_rows.append((label, b_stall, i_stall))

    out_dir = script_path.resolve().parent
    month_prefix = datetime.now().strftime("%Y%m")
    tag = (args.tag or "").strip()
    tag_part = f"_{tag}" if tag else ""
    out_ipc = Path(args.out_ipc).expanduser() if args.out_ipc else (out_dir / f"{month_prefix}{tag_part}_ipc_compare.svg")
    out_stall = out_dir / f"{month_prefix}{tag_part}_stall_breakdown_compare.svg"

    wrote: List[Path] = []

    if not args.skip_ipc:
        if insn_mismatch:
            metric = "Performance (normalized): speedup = baseline_cycles / run_cycles (baseline=1.0)"
            if args.with_gto_ideal:
                items4 = [
                    (
                        k,
                        1.0,
                        (float(b.cycles) / float(i.cycles)) if i.cycles else 0.0,
                        (float(b.cycles) / float(g.cycles)) if (g is not None and g.cycles) else 0.0,
                        (float(b.cycles) / float(gi.cycles)) if (gi is not None and gi.cycles) else 0.0,
                        note,
                    )
                    for k, b, i, g, gi, note in perf_rows
                ]
                plot_perf_svg_4(
                    out_ipc,
                    title="Ideal L1D vs Baseline (+GTO,+GTO+Ideal)",
                    metric=metric,
                    items=items4,
                    baseline_color=args.ipc_baseline_color,
                    ideal_color=args.ipc_ideal_color,
                    gto_color=args.ipc_gto_color,
                    gto_ideal_color=args.ipc_gto_ideal_color,
                )
            elif with_gto:
                items3 = [
                    (
                        k,
                        1.0,
                        (float(b.cycles) / float(i.cycles)) if i.cycles else 0.0,
                        (float(b.cycles) / float(g.cycles)) if (g is not None and g.cycles) else 0.0,
                        note,
                    )
                    for k, b, i, g, _gi, note in perf_rows
                ]
                plot_perf_svg_3(
                    out_ipc,
                    title="Ideal L1D vs Baseline (+GTO)",
                    metric=metric,
                    items=items3,
                    baseline_color=args.ipc_baseline_color,
                    ideal_color=args.ipc_ideal_color,
                    gto_color=args.ipc_gto_color,
                )
            else:
                items = [
                    (k, 1.0, (float(b.cycles) / float(i.cycles)) if i.cycles else 0.0, note)
                    for k, b, i, _g, _gi, note in perf_rows
                ]
                plot_perf_svg(
                    out_ipc,
                    title="Ideal L1D vs Baseline",
                    metric=metric,
                    items=items,
                    baseline_color=args.ipc_baseline_color,
                    ideal_color=args.ipc_ideal_color,
                )
        else:
            metric = "Performance (normalized): IPC ratio = ideal_ipc / baseline_ipc (baseline=1.0)"
            if args.with_gto_ideal:
                items4 = [
                    (
                        k,
                        1.0,
                        (i.ipc / b.ipc) if b.ipc else 0.0,
                        (g.ipc / b.ipc) if (g is not None and b.ipc) else 0.0,
                        (gi.ipc / b.ipc) if (gi is not None and b.ipc) else 0.0,
                        "",
                    )
                    for k, b, i, g, gi, _note in perf_rows
                ]
                plot_perf_svg_4(
                    out_ipc,
                    title="Ideal L1D vs Baseline (+GTO,+GTO+Ideal)",
                    metric=metric,
                    items=items4,
                    baseline_color=args.ipc_baseline_color,
                    ideal_color=args.ipc_ideal_color,
                    gto_color=args.ipc_gto_color,
                    gto_ideal_color=args.ipc_gto_ideal_color,
                )
            elif with_gto:
                items3 = [
                    (
                        k,
                        1.0,
                        (i.ipc / b.ipc) if b.ipc else 0.0,
                        (g.ipc / b.ipc) if (g is not None and b.ipc) else 0.0,
                        "",
                    )
                    for k, b, i, g, _gi, _note in perf_rows
                ]
                plot_perf_svg_3(
                    out_ipc,
                    title="Ideal L1D vs Baseline (+GTO)",
                    metric=metric,
                    items=items3,
                    baseline_color=args.ipc_baseline_color,
                    ideal_color=args.ipc_ideal_color,
                    gto_color=args.ipc_gto_color,
                )
            else:
                items = [
                    (k, 1.0, (i.ipc / b.ipc) if b.ipc else 0.0, "")
                    for k, b, i, _g, _gi, _note in perf_rows
                ]
                plot_perf_svg(
                    out_ipc,
                    title="Ideal L1D vs Baseline",
                    metric=metric,
                    items=items,
                    baseline_color=args.ipc_baseline_color,
                    ideal_color=args.ipc_ideal_color,
                )
        wrote.append(out_ipc)

    if not args.skip_stall:
        plot_stall_svg(
            out_stall,
            title="Ideal L1D vs Baseline",
            subtitle="Issue-stall breakdown (stacked) normalized by baseline total (baseline=100%, ideal height shows total change)",
            items=stall_rows,
        )
        wrote.append(out_stall)

    for p in wrote:
        print(f"wrote: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
