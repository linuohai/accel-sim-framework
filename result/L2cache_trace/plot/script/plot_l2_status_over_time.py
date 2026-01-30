#!/usr/bin/env python3
"""
Plot L1/L2 cache status over time from Accel-Sim trace CSVs.

This script generates one figure per CSV:
  - Stacked cache status distribution over time (area plot)

Default output directory:
  accel-sim-framework/result/L2cache_trace/plot/result/l2_cache/
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
PLOT_DIR = SCRIPT_DIR.parent
RESULT_DIR = PLOT_DIR.parent.parent

_PYDEPS_DIR = SCRIPT_DIR / "_pydeps"
_L1_PYDEPS_DIR = RESULT_DIR / "L1cache_trace" / "plot" / "script" / "_pydeps"
for dep_dir in (_PYDEPS_DIR, _L1_PYDEPS_DIR):
    if dep_dir.is_dir():
        sys.path.insert(0, str(dep_dir))

L2_TRACE_DIR = RESULT_DIR / "L2cache_trace"
DEFAULT_OUT_DIR = PLOT_DIR / "result" / "l2_cache"

STATUS_ORDER = [
    "HIT",
    "HIT_RESERVED",
    "MSHR_HIT",
    "MISS",
    "SECTOR_MISS",
    "RESERVATION_FAIL",
]
MISS_SET = {"MISS", "SECTOR_MISS"}


def _norm_header(name: str) -> str:
    return name.strip().lower()


def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text or text.upper() == "NA":
        return None
    try:
        return int(text, 0)
    except ValueError:
        try:
            return int(text)
        except ValueError:
            return None


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _format_si(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1e9:
        return f"{value / 1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{value / 1e6:.2f}M"
    if abs_v >= 1e3:
        return f"{value / 1e3:.2f}K"
    if abs_v >= 10:
        return f"{value:.0f}"
    if abs_v >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def smooth_moving_average(values: Sequence[float], window: int) -> List[float]:
    n = len(values)
    if n == 0:
        return []
    w = int(window)
    if w <= 1:
        return list(values)
    if w > n:
        w = n
    if w % 2 == 0:
        w += 1
        if w > n:
            w = n if n % 2 == 1 else max(1, n - 1)
    half = w // 2

    out: List[float] = []
    for i in range(n):
        lo = 0 if i - half < 0 else i - half
        hi = n - 1 if i + half >= n else i + half
        s = 0.0
        cnt = 0
        for j in range(lo, hi + 1):
            s += float(values[j])
            cnt += 1
        out.append(s / cnt if cnt else float(values[i]))
    return out


def _open_csv_header(path: Path) -> List[str]:
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                continue
            return row
    return []


def _discover_candidates(trace_dir: Path) -> List[Path]:
    if not trace_dir.is_dir():
        return []
    candidates = sorted(
        trace_dir.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates


def _has_status_columns(path: Path) -> bool:
    header = _open_csv_header(path)
    if not header:
        return False
    normalized = {_norm_header(name) for name in header}
    return "cycle" in normalized and (
        "l1_status" in normalized or "l2_status" in normalized or "status" in normalized
    )


def discover_default_input(trace_dir: Path) -> Path:
    candidates = _discover_candidates(trace_dir)
    if not candidates:
        raise SystemExit(f"no CSV candidates found under: {trace_dir}")

    for path in candidates:
        try:
            if _has_status_columns(path):
                return path
        except OSError:
            continue

    return candidates[0]


def _parse_filter_list(values: Optional[Sequence[str]]) -> Optional[set]:
    if not values:
        return None
    items: set = set()
    for entry in values:
        if entry is None:
            continue
        for part in entry.split(","):
            part = part.strip().upper()
            if part:
                items.add(part)
    return items or None


def _resolve_columns(header: Sequence[str]) -> Tuple[str, str, Optional[str], Optional[str]]:
    norm_map = {_norm_header(name): name for name in header}
    cycle_col = norm_map.get("cycle")
    status_col = norm_map.get("l1_status") or norm_map.get("l2_status") or norm_map.get("status")
    op_col = norm_map.get("op")
    space_col = norm_map.get("space")
    if not cycle_col:
        raise SystemExit("missing 'cycle' column")
    if not status_col:
        raise SystemExit("missing status column (l1_status/l2_status)")
    return cycle_col, status_col, op_col, space_col


def _status_tag(status_col: str) -> str:
    norm = _norm_header(status_col)
    if "l2" in norm:
        return "l2"
    return "l1"


def _filter_desc(op_filter: Optional[set], space_filter: Optional[set]) -> str:
    parts: List[str] = []
    if op_filter:
        parts.append(f"op={','.join(sorted(op_filter))}")
    if space_filter:
        parts.append(f"space={','.join(sorted(space_filter))}")
    return "  ".join(parts)


def _order_statuses(status_counts: Dict[str, int]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for name in STATUS_ORDER:
        if name in status_counts:
            ordered.append(name)
            seen.add(name)
    extras = sorted(s for s in status_counts if s not in seen)
    ordered.extend(extras)
    return ordered


@dataclass
class ScanInfo:
    total_rows: int
    used_rows: int
    min_cycle: int
    max_cycle: int
    status_counts: Dict[str, int]
    cycle_column: str
    status_column: str
    op_column: Optional[str]
    space_column: Optional[str]
    filter_desc: str


@dataclass
class BinSeries:
    cycle_mid: List[float]
    cycle_start: List[int]
    cycle_end: List[int]
    bin_span: List[int]
    miss: List[float]
    resfail: List[float]
    total: List[float]
    status_counts: Dict[str, List[float]]


def scan_csv(
    csv_path: Path,
    *,
    op_filter: Optional[set],
    space_filter: Optional[set],
) -> ScanInfo:
    header = _open_csv_header(csv_path)
    if not header:
        raise SystemExit("missing CSV header")

    cycle_col, status_col, op_col, space_col = _resolve_columns(header)
    if op_filter and not op_col:
        raise SystemExit("filter requested but missing 'op' column")
    if space_filter and not space_col:
        raise SystemExit("filter requested but missing 'space' column")

    total_rows = 0
    used_rows = 0
    min_cycle: Optional[int] = None
    max_cycle: Optional[int] = None
    status_counts: Dict[str, int] = {}

    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            total_rows += 1
            cycle = _safe_int(row.get(cycle_col))
            if cycle is None:
                continue
            if op_filter and row.get(op_col, "").strip().upper() not in op_filter:
                continue
            if space_filter and row.get(space_col, "").strip().upper() not in space_filter:
                continue
            used_rows += 1
            if min_cycle is None or cycle < min_cycle:
                min_cycle = cycle
            if max_cycle is None or cycle > max_cycle:
                max_cycle = cycle
            status = (row.get(status_col) or "").strip().upper() or "UNKNOWN"
            status_counts[status] = status_counts.get(status, 0) + 1

    if used_rows == 0 or min_cycle is None or max_cycle is None:
        raise SystemExit("no usable rows after filters")

    return ScanInfo(
        total_rows=total_rows,
        used_rows=used_rows,
        min_cycle=min_cycle,
        max_cycle=max_cycle,
        status_counts=status_counts,
        cycle_column=cycle_col,
        status_column=status_col,
        op_column=op_col,
        space_column=space_col,
        filter_desc=_filter_desc(op_filter, space_filter),
    )


def _choose_window(min_cycle: int, max_cycle: int, target_points: int, window_override: Optional[int]) -> int:
    if window_override and window_override > 0:
        return window_override
    span = max_cycle - min_cycle + 1
    if span <= 0:
        return 1
    points = max(1, target_points)
    return max(1, int(math.ceil(span / points)))


def bin_csv(
    csv_path: Path,
    *,
    scan: ScanInfo,
    statuses: List[str],
    window: int,
    op_filter: Optional[set],
    space_filter: Optional[set],
    per_cycle: bool,
) -> BinSeries:
    num_bins = ((scan.max_cycle - scan.min_cycle) // window) + 1
    status_counts: Dict[str, List[float]] = {s: [0.0] * num_bins for s in statuses}
    miss = [0.0] * num_bins
    resfail = [0.0] * num_bins
    total = [0.0] * num_bins

    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cycle = _safe_int(row.get(scan.cycle_column))
            if cycle is None:
                continue
            if op_filter and row.get(scan.op_column, "").strip().upper() not in op_filter:
                continue
            if space_filter and row.get(scan.space_column, "").strip().upper() not in space_filter:
                continue
            idx = (cycle - scan.min_cycle) // window
            if idx < 0 or idx >= num_bins:
                continue
            status = (row.get(scan.status_column) or "").strip().upper() or "UNKNOWN"
            if status not in status_counts:
                status_counts[status] = [0.0] * num_bins
                statuses.append(status)
            total[idx] += 1.0
            status_counts[status][idx] += 1.0
            if status in MISS_SET:
                miss[idx] += 1.0
            if status == "RESERVATION_FAIL":
                resfail[idx] += 1.0

    cycle_start: List[int] = []
    cycle_end: List[int] = []
    cycle_mid: List[float] = []
    bin_span: List[int] = []
    for idx in range(num_bins):
        start = scan.min_cycle + idx * window
        end = min(scan.max_cycle, start + window - 1)
        span = max(1, end - start + 1)
        cycle_start.append(start)
        cycle_end.append(end)
        cycle_mid.append((start + end) / 2.0)
        bin_span.append(span)

    if per_cycle:
        for i, span in enumerate(bin_span):
            if span <= 0:
                continue
            miss[i] /= span
            resfail[i] /= span
            total[i] /= span
            for status in status_counts:
                status_counts[status][i] /= span

    return BinSeries(
        cycle_mid=cycle_mid,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        bin_span=bin_span,
        miss=miss,
        resfail=resfail,
        total=total,
        status_counts=status_counts,
    )


def _require_matplotlib() -> "tuple[object, object, object]":
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.ticker import FuncFormatter  # type: ignore

        return matplotlib, plt, FuncFormatter
    except Exception as exc:
        target = SCRIPT_DIR / "_pydeps"
        raise SystemExit(
            "PNG output requires matplotlib.\n"
            f"Install into {target} with:\n"
            f"  TMPDIR=... PIP_CACHE_DIR=... pip3 install --no-cache-dir --target {target} "
            "numpy==1.19.5 matplotlib==3.2.2\n"
            f"error: {exc}"
        ) from exc


def _apply_smoothing(values: Sequence[float], smooth: int) -> List[float]:
    if smooth <= 1:
        return list(values)
    return smooth_moving_average(values, smooth)


def _compute_stack(
    series: BinSeries,
    statuses: Sequence[str],
    *,
    smooth: int,
    normalize: bool,
) -> Dict[str, List[float]]:
    data: Dict[str, List[float]] = {}
    for status in statuses:
        values = series.status_counts.get(status, [])
        data[status] = _apply_smoothing(values, smooth)

    if normalize:
        count = len(series.cycle_mid)
        for i in range(count):
            total = sum(data[status][i] for status in statuses) if statuses else 0.0
            if total <= 0.0:
                continue
            for status in statuses:
                data[status][i] = data[status][i] / total
    return data


def _nice_step(max_val: float, steps: int = 5) -> float:
    if max_val <= 0.0:
        return 1.0
    raw = max_val / max(1, steps)
    power = 10 ** math.floor(math.log10(raw))
    norm = raw / power
    if norm <= 1:
        step = 1
    elif norm <= 2:
        step = 2
    elif norm <= 5:
        step = 5
    else:
        step = 10
    return step * power


def write_miss_resfail_png(
    out_png: Path,
    *,
    title: str,
    subtitle: str,
    series: BinSeries,
    smooth: int = 1,
    per_cycle: bool = False,
    width: int = 1280,
    height: int = 560,
    dpi: int = 100,
) -> None:
    if not series.cycle_mid:
        raise SystemExit("empty series")

    _, plt, FuncFormatter = _require_matplotlib()

    x = series.cycle_mid
    miss = _apply_smoothing(series.miss, smooth)
    resfail = _apply_smoothing(series.resfail, smooth)

    orange = "#f97316"
    red = "#ef4444"
    grid = "#e9eef5"
    text = "#0f172a"
    subtext = "#475569"

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("white")

    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.08, right=0.98)
    fig.text(0.08, 0.95, title, fontsize=18, color=text)
    fig.text(0.08, 0.91, subtitle, fontsize=10, color=subtext)

    explain = "line=window mean"
    fig.text(0.08, 0.87, explain, fontsize=9, color=subtext)

    ax.plot(x, miss, color=orange, linewidth=2.2, label="MISS+SECTOR_MISS")
    ax.plot(x, resfail, color=red, linewidth=2.2, label="RESERVATION_FAIL")

    y_label = "events per cycle" if per_cycle else "events per window"
    ax.set_ylabel(y_label, color=subtext)
    ax.set_xlabel("cycle", color=subtext)
    ax.grid(True, color=grid, linewidth=1)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=False)

    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))

    for spine in ax.spines.values():
        spine.set_color(grid)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


def write_status_stack_png(
    out_png: Path,
    *,
    title: str,
    subtitle: str,
    series: BinSeries,
    statuses: Sequence[str],
    smooth: int = 1,
    normalize: bool = False,
    per_cycle: bool = False,
    width: int = 1280,
    height: int = 560,
    dpi: int = 100,
) -> None:
    if not series.cycle_mid:
        raise SystemExit("empty series")

    _, plt, FuncFormatter = _require_matplotlib()

    colors = _status_colors()
    stack_data = _compute_stack(series, statuses, smooth=smooth, normalize=normalize)
    visible_statuses = [s for s in statuses if sum(stack_data.get(s, [])) > 0.0]
    if not visible_statuses:
        raise SystemExit("no status data to plot")

    x = series.cycle_mid
    ys = [stack_data[s] for s in visible_statuses]
    cs = [colors.get(s, "#64748b") for s in visible_statuses]

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("white")

    text = "#0f172a"
    subtext = "#475569"
    grid = "#e9eef5"

    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.08, right=0.98)
    fig.text(0.08, 0.95, title, fontsize=18, color=text)
    fig.text(0.08, 0.91, subtitle, fontsize=10, color=subtext)
    explain = "stacked=window counts" if not normalize else "stacked=ratio per window"
    fig.text(0.08, 0.87, explain, fontsize=9, color=subtext)

    ax.stackplot(x, ys, labels=visible_statuses, colors=cs, alpha=0.88)

    if normalize:
        y_label = "fraction of events"
    else:
        y_label = "events per cycle" if per_cycle else "events per window"
    ax.set_ylabel(y_label, color=subtext)
    ax.set_xlabel("cycle", color=subtext)
    ax.grid(True, color=grid, linewidth=1)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=False, fontsize=8)

    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))
    if normalize:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: f"{v*100:.0f}%"))
    else:
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))

    for spine in ax.spines.values():
        spine.set_color(grid)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


def _status_colors() -> Dict[str, str]:
    return {
        "HIT": "#2563eb",
        "HIT_RESERVED": "#93c5fd",
        "MSHR_HIT": "#14b8a6",
        "MISS": "#f59e0b",
        "SECTOR_MISS": "#8b5cf6",
        "RESERVATION_FAIL": "#dc2626",
        "UNKNOWN": "#64748b",
    }


def write_miss_resfail_svg(
    out_svg: Path,
    *,
    title: str,
    subtitle: str,
    series: BinSeries,
    smooth: int = 1,
    per_cycle: bool = False,
    width: int = 1280,
    height: int = 560,
) -> None:
    if not series.cycle_mid:
        raise SystemExit("empty series")

    # Layout
    left_margin = 74
    right_margin = 30
    title_y = 34
    subtitle_y = 56
    legend_y = 78
    top_margin = 108
    bottom_margin = 54
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_w = chart_x1 - chart_x0
    chart_y0 = top_margin
    chart_y1 = height - bottom_margin

    x_min = min(series.cycle_start)
    x_max = max(series.cycle_end)
    if x_max <= x_min:
        x_max = x_min + 1

    def x_of(x: float) -> float:
        return chart_x0 + (x - x_min) * chart_w / (x_max - x_min)

    miss = _apply_smoothing(series.miss, smooth)
    resfail = _apply_smoothing(series.resfail, smooth)
    y_max = max(max(miss), max(resfail), 1.0)
    step = _nice_step(y_max)
    y_max_axis = math.ceil(y_max / step) * step
    if y_max_axis <= 0:
        y_max_axis = 1.0

    def y_of(v: float) -> float:
        t = v / y_max_axis if y_max_axis > 0 else 0.0
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        return chart_y1 - t * (chart_y1 - chart_y0)

    def line_path(values: Sequence[float]) -> str:
        coords = [(x_of(x), y_of(v)) for x, v in zip(series.cycle_mid, values)]
        return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in coords)

    miss_path = line_path(miss)
    resfail_path = line_path(resfail)

    text = "#0f172a"
    subtext = "#475569"
    grid = "#e9eef5"
    orange = "#f97316"
    red = "#ef4444"

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>',
        f'<text x="{left_margin}" y="{title_y}" font-size="22" font-family="sans-serif" fill="{text}">{_svg_escape(title)}</text>',
        f'<text x="{left_margin}" y="{subtitle_y}" font-size="12" font-family="sans-serif" fill="{subtext}">{_svg_escape(subtitle)}</text>',
    ]

    explain = "line=window mean"
    lines.append(
        f'<text x="{left_margin}" y="{legend_y}" font-size="12" font-family="sans-serif" fill="{subtext}">{_svg_escape(explain)}</text>'
    )

    # Grid + axes
    y = 0.0
    while y <= y_max_axis + 1e-9:
        yy = y_of(y)
        lines.append(
            f'<line x1="{chart_x0}" y1="{yy:.2f}" x2="{chart_x1}" y2="{yy:.2f}" stroke="{grid}" stroke-width="1"/>'
        )
        label = _format_si(y)
        lines.append(
            f'<text x="{chart_x0 - 10}" y="{yy + 4:.2f}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="end">{_svg_escape(label)}</text>'
        )
        y += step

    x_ticks = 6
    for i in range(x_ticks):
        t = i / (x_ticks - 1) if x_ticks > 1 else 0.0
        xv = x_min + t * (x_max - x_min)
        xx = x_of(xv)
        lines.append(
            f'<line x1="{xx:.2f}" y1="{chart_y0}" x2="{xx:.2f}" y2="{chart_y1}" stroke="{grid}" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{xx:.2f}" y="{chart_y1 + 20}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="middle">{_svg_escape(_format_si(xv))}</text>'
        )

    lines.append(
        f'<text x="{chart_x0}" y="{height - 14}" font-size="12" font-family="sans-serif" fill="{subtext}">cycle</text>'
    )
    y_label = "events per cycle" if per_cycle else "events per window"
    lines.append(
        f'<text x="18" y="{(chart_y0 + chart_y1) / 2:.2f}" font-size="12" font-family="sans-serif" fill="{subtext}" transform="rotate(-90 18 {(chart_y0 + chart_y1) / 2:.2f})">{_svg_escape(y_label)}</text>'
    )

    # Lines
    lines.append(f'<path d="{miss_path}" fill="none" stroke="{orange}" stroke-width="2.2"/>')
    lines.append(f'<path d="{resfail_path}" fill="none" stroke="{red}" stroke-width="2.2"/>')

    # Legend
    legend_x = chart_x1 - 260
    legend_y2 = legend_y - 2
    lines.append(
        f'<line x1="{legend_x}" y1="{legend_y2}" x2="{legend_x + 18}" y2="{legend_y2}" stroke="{orange}" stroke-width="2.2"/>'
    )
    lines.append(
        f'<text x="{legend_x + 24}" y="{legend_y2 + 4}" font-size="12" font-family="sans-serif" fill="{text}">MISS+SECTOR_MISS</text>'
    )
    lines.append(
        f'<line x1="{legend_x}" y1="{legend_y2 + 18}" x2="{legend_x + 18}" y2="{legend_y2 + 18}" stroke="{red}" stroke-width="2.2"/>'
    )
    lines.append(
        f'<text x="{legend_x + 24}" y="{legend_y2 + 22}" font-size="12" font-family="sans-serif" fill="{text}">RESERVATION_FAIL</text>'
    )

    lines.append("</svg>")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_status_stack_svg(
    out_svg: Path,
    *,
    title: str,
    subtitle: str,
    series: BinSeries,
    statuses: Sequence[str],
    smooth: int = 1,
    normalize: bool = False,
    per_cycle: bool = False,
    width: int = 1280,
    height: int = 560,
) -> None:
    if not series.cycle_mid:
        raise SystemExit("empty series")

    # Layout
    left_margin = 74
    right_margin = 30
    title_y = 34
    subtitle_y = 56
    legend_y = 78
    top_margin = 108
    bottom_margin = 54
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_w = chart_x1 - chart_x0
    chart_y0 = top_margin
    chart_y1 = height - bottom_margin

    x_min = min(series.cycle_start)
    x_max = max(series.cycle_end)
    if x_max <= x_min:
        x_max = x_min + 1

    def x_of(x: float) -> float:
        return chart_x0 + (x - x_min) * chart_w / (x_max - x_min)

    stack_data = _compute_stack(series, statuses, smooth=smooth, normalize=normalize)
    visible_statuses = [s for s in statuses if sum(stack_data.get(s, [])) > 0.0]
    if not visible_statuses:
        raise SystemExit("no status data to plot")

    if normalize:
        y_max_axis = 1.0
        step = 0.2
    else:
        totals = [
            sum(stack_data[s][i] for s in visible_statuses)
            for i in range(len(series.cycle_mid))
        ]
        y_max = max(max(totals), 1.0)
        step = _nice_step(y_max)
        y_max_axis = math.ceil(y_max / step) * step
        if y_max_axis <= 0:
            y_max_axis = 1.0

    def y_of(v: float) -> float:
        t = v / y_max_axis if y_max_axis > 0 else 0.0
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        return chart_y1 - t * (chart_y1 - chart_y0)

    colors = _status_colors()

    def area_path(bottom: Sequence[float], top: Sequence[float]) -> str:
        pts_top = [(x_of(x), y_of(v)) for x, v in zip(series.cycle_mid, top)]
        pts_bottom = [(x_of(x), y_of(v)) for x, v in zip(series.cycle_mid, bottom)]
        coords = pts_top + list(reversed(pts_bottom))
        return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in coords) + " Z"

    text = "#0f172a"
    subtext = "#475569"
    grid = "#e9eef5"

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>',
        f'<text x="{left_margin}" y="{title_y}" font-size="22" font-family="sans-serif" fill="{text}">{_svg_escape(title)}</text>',
        f'<text x="{left_margin}" y="{subtitle_y}" font-size="12" font-family="sans-serif" fill="{subtext}">{_svg_escape(subtitle)}</text>',
    ]

    explain = "stacked=window counts" if not normalize else "stacked=ratio per window"
    lines.append(
        f'<text x="{left_margin}" y="{legend_y}" font-size="12" font-family="sans-serif" fill="{subtext}">{_svg_escape(explain)}</text>'
    )

    # Grid + axes
    y = 0.0
    while y <= y_max_axis + 1e-9:
        yy = y_of(y)
        lines.append(
            f'<line x1="{chart_x0}" y1="{yy:.2f}" x2="{chart_x1}" y2="{yy:.2f}" stroke="{grid}" stroke-width="1"/>'
        )
        label = f"{y*100:.0f}%" if normalize else _format_si(y)
        lines.append(
            f'<text x="{chart_x0 - 10}" y="{yy + 4:.2f}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="end">{_svg_escape(label)}</text>'
        )
        y += step

    x_ticks = 6
    for i in range(x_ticks):
        t = i / (x_ticks - 1) if x_ticks > 1 else 0.0
        xv = x_min + t * (x_max - x_min)
        xx = x_of(xv)
        lines.append(
            f'<line x1="{xx:.2f}" y1="{chart_y0}" x2="{xx:.2f}" y2="{chart_y1}" stroke="{grid}" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{xx:.2f}" y="{chart_y1 + 20}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="middle">{_svg_escape(_format_si(xv))}</text>'
        )

    lines.append(
        f'<text x="{chart_x0}" y="{height - 14}" font-size="12" font-family="sans-serif" fill="{subtext}">cycle</text>'
    )
    y_label = "fraction of events" if normalize else ("events per cycle" if per_cycle else "events per window")
    lines.append(
        f'<text x="18" y="{(chart_y0 + chart_y1) / 2:.2f}" font-size="12" font-family="sans-serif" fill="{subtext}" transform="rotate(-90 18 {(chart_y0 + chart_y1) / 2:.2f})">{_svg_escape(y_label)}</text>'
    )

    # Stacked areas
    bottom = [0.0] * len(series.cycle_mid)
    for status in visible_statuses:
        values = stack_data[status]
        top = [b + v for b, v in zip(bottom, values)]
        path = area_path(bottom, top)
        color = colors.get(status, "#64748b")
        lines.append(f'<path d="{path}" fill="{color}" fill-opacity="0.85" stroke="none"/>')
        bottom = top

    # Legend
    legend_x = chart_x1 - 320
    legend_y2 = legend_y - 2
    for idx, status in enumerate(visible_statuses):
        x = legend_x + (idx % 3) * 105
        y = legend_y2 + (idx // 3) * 16
        color = colors.get(status, "#64748b")
        lines.append(f'<rect x="{x}" y="{y - 10}" width="10" height="10" fill="{color}"/>')
        lines.append(
            f'<text x="{x + 14}" y="{y - 1}" font-size="11" font-family="sans-serif" fill="{text}">{_svg_escape(status)}</text>'
        )

    lines.append("</svg>")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot L1/L2 cache status over time from Accel-Sim trace CSVs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 plot_l2_status_over_time.py\n"
            "  python3 plot_l2_status_over_time.py ../../bfs_web_l2.csv\n"
            "  python3 plot_l2_status_over_time.py --stem bfs_web_l2\n"
            "  python3 plot_l2_status_over_time.py --all --points 3000\n"
            "  python3 plot_l2_status_over_time.py --op LD --space GLOBAL\n"
            "  python3 plot_l2_status_over_time.py --window 50000 --per-cycle\n"
            "  python3 plot_l2_status_over_time.py --format svg\n"
        ),
    )
    parser.add_argument(
        "positional_csvs",
        nargs="*",
        type=Path,
        help="Input CSV path(s). If omitted, auto-pick from result/L2cache_trace.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        action="append",
        default=None,
        help="Input CSV path (can be repeated).",
    )
    parser.add_argument(
        "--stem",
        action="append",
        default=None,
        help=(
            "Pick input CSV by stem from result/L2cache_trace (can be repeated). "
            "Example: bfs_web_l2"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot all matching CSVs under result/L2cache_trace.",
    )
    parser.add_argument(
        "--points",
        type=int,
        default=2000,
        help="Target number of plotted points (default: %(default)s).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=None,
        help="Window size in cycles (overrides --points).",
    )
    parser.add_argument(
        "--smooth",
        type=int,
        default=1,
        help="Moving-average smoothing in plotted points (default: %(default)s; 1 disables).",
    )
    parser.add_argument(
        "--format",
        choices=("png", "svg", "both"),
        default="png",
        help="Output format (default: %(default)s).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=100,
        help="PNG DPI (default: %(default)s).",
    )
    parser.add_argument(
        "--per-cycle",
        action="store_true",
        help="Normalize counts by the window cycle span (events per cycle).",
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize the stacked status chart to 0..1 (ratio per window).",
    )
    parser.add_argument(
        "--op",
        action="append",
        default=None,
        help="Filter by op (LD/ST). Can repeat or use comma-separated values.",
    )
    parser.add_argument(
        "--space",
        action="append",
        default=None,
        help="Filter by space (GLOBAL/LOCAL/SHARED/etc). Can repeat or use comma-separated values.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR}).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Canvas width in pixels (default: %(default)s).",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=560,
        help="Canvas height in pixels (default: %(default)s).",
    )
    return parser.parse_args(argv)


def resolve_inputs(args: argparse.Namespace) -> List[Path]:
    inputs: List[Path] = []

    if args.positional_csvs:
        inputs.extend(args.positional_csvs)

    if args.csv:
        inputs.extend(args.csv)

    if args.stem:
        for stem in args.stem:
            stem = stem.strip()
            if not stem:
                continue
            path = (L2_TRACE_DIR / f"{stem}.csv").resolve()
            inputs.append(path)

    if args.all:
        inputs.extend(_discover_candidates(L2_TRACE_DIR))

    if not inputs:
        inputs = [discover_default_input(L2_TRACE_DIR)]

    dedup: List[Path] = []
    seen: set = set()
    for path in inputs:
        p = path.resolve()
        if p in seen:
            continue
        seen.add(p)
        dedup.append(p)
    return dedup


def process_csv(
    csv_path: Path,
    *,
    target_points: int,
    window_override: Optional[int],
    op_filter: Optional[set],
    space_filter: Optional[set],
    per_cycle: bool,
) -> Tuple[ScanInfo, BinSeries, List[str], int]:
    scan = scan_csv(csv_path, op_filter=op_filter, space_filter=space_filter)
    statuses = _order_statuses(scan.status_counts)
    window = _choose_window(scan.min_cycle, scan.max_cycle, target_points, window_override)
    series = bin_csv(
        csv_path,
        scan=scan,
        statuses=statuses,
        window=window,
        op_filter=op_filter,
        space_filter=space_filter,
        per_cycle=per_cycle,
    )
    return scan, series, statuses, window


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    inputs = resolve_inputs(args)
    op_filter = _parse_filter_list(args.op)
    space_filter = _parse_filter_list(args.space)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for csv_path in inputs:
        if not csv_path.is_file():
            print(f"[skip] not found: {csv_path}", file=sys.stderr)
            failures += 1
            continue

        try:
            scan, series, statuses, window = process_csv(
                csv_path,
                target_points=args.points,
                window_override=args.window,
                op_filter=op_filter,
                space_filter=space_filter,
                per_cycle=args.per_cycle,
            )
        except SystemExit as exc:
            print(f"[skip] {csv_path.name}: {exc}", file=sys.stderr)
            failures += 1
            continue

        status_tag = _status_tag(scan.status_column)
        points = len(series.cycle_mid)
        subtitle = (
            f"rows={scan.used_rows}/{scan.total_rows}  "
            f"cycles={scan.min_cycle}..{scan.max_cycle}  "
            f"window={window}  points={points}"
        )
        if scan.filter_desc:
            subtitle += f"  {scan.filter_desc}"

        outputs: List[Path] = []
        want_png = args.format in ("png", "both")
        want_svg = args.format in ("svg", "both")

        stack_title = f"{csv_path.name} {status_tag.upper()} status stack over time"

        stack_name = f"{csv_path.stem}_{status_tag}_status_stack"

        if want_png:
            try:
                out_png = out_dir / f"{stack_name}.png"
                write_status_stack_png(
                    out_png,
                    title=stack_title,
                    subtitle=subtitle,
                    series=series,
                    statuses=statuses,
                    smooth=args.smooth,
                    normalize=args.normalize,
                    per_cycle=args.per_cycle,
                    width=args.width,
                    height=args.height,
                    dpi=args.dpi,
                )
                outputs.append(out_png)
            except SystemExit as exc:
                print(f"[skip] PNG(stack): {csv_path.name}: {exc}", file=sys.stderr)
                failures += 1

        if want_svg:
            out_svg = out_dir / f"{stack_name}.svg"
            write_status_stack_svg(
                out_svg,
                title=stack_title,
                subtitle=subtitle,
                series=series,
                statuses=statuses,
                smooth=args.smooth,
                normalize=args.normalize,
                per_cycle=args.per_cycle,
                width=args.width,
                height=args.height,
            )
            outputs.append(out_svg)

        print(f"input: {csv_path}")
        for out_path in outputs:
            print(f"output: {out_path}")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
