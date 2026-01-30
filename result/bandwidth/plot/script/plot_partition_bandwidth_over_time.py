#!/usr/bin/env python3
"""
Plot HBM partition bandwidth over time from Accel-Sim partition trace CSVs.

This script writes PNG plots by default (requires matplotlib + numpy; can be placed in
`./_pydeps` next to this script). Output directory:
  accel-sim-framework/result/bandwidth/plot/result

The input CSV must contain:
  - cycle
  - hbm_bw_GBps
  - hbm_occupancy
  - part<N>_bw_GBps (one or more)
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
_PYDEPS_DIR = SCRIPT_DIR / "_pydeps"
if _PYDEPS_DIR.is_dir():
    sys.path.insert(0, str(_PYDEPS_DIR))

PLOT_DIR = SCRIPT_DIR.parent
BANDWIDTH_DIR = PLOT_DIR.parent
DEFAULT_OUT_DIR = PLOT_DIR / "result"


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


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = value.strip()
    if not text or text.upper() == "NA":
        return None
    try:
        return float(text)
    except ValueError:
        return None


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
    preferred = [p for p in candidates if "hbm_partition" in p.stem.lower()]
    return preferred or candidates


def discover_default_input(trace_dir: Path) -> Path:
    candidates = _discover_candidates(trace_dir)
    if not candidates:
        raise SystemExit(f"no CSV candidates found under: {trace_dir}")
    return candidates[0]


def _parse_partition_columns(header: Sequence[str]) -> List[Tuple[int, int]]:
    parts: List[Tuple[int, int]] = []
    for idx, name in enumerate(header):
        norm = _norm_header(name)
        if not norm.startswith("part") or not norm.endswith("_bw_gbps"):
            continue
        mid = norm[len("part") : -len("_bw_gbps")]
        if not mid.isdigit():
            continue
        parts.append((int(mid), idx))
    parts.sort(key=lambda item: item[0])
    return parts


@dataclass
class HeaderInfo:
    cycle_idx: int
    bw_idx: int
    occ_idx: int
    part_columns: List[Tuple[int, int]]


def _read_header_info(csv_path: Path) -> HeaderInfo:
    header = _open_csv_header(csv_path)
    if not header:
        raise SystemExit("missing CSV header")
    header_map = {_norm_header(name): idx for idx, name in enumerate(header)}
    cycle_idx = header_map.get("cycle")
    bw_idx = header_map.get("hbm_bw_gbps")
    occ_idx = header_map.get("hbm_occupancy")
    if cycle_idx is None or bw_idx is None or occ_idx is None:
        missing = []
        if cycle_idx is None:
            missing.append("cycle")
        if bw_idx is None:
            missing.append("hbm_bw_GBps")
        if occ_idx is None:
            missing.append("hbm_occupancy")
        raise SystemExit(f"missing required columns: {', '.join(missing)}")
    part_columns = _parse_partition_columns(header)
    if not part_columns:
        raise SystemExit("missing partition columns (part<N>_bw_GBps)")
    return HeaderInfo(
        cycle_idx=int(cycle_idx),
        bw_idx=int(bw_idx),
        occ_idx=int(occ_idx),
        part_columns=part_columns,
    )


def _iter_rows(csv_path: Path, header: HeaderInfo) -> Iterator[Tuple[int, float, float, List[float]]]:
    with csv_path.open(newline="") as handle:
        reader = csv.reader(handle)
        header_seen = False
        for row in reader:
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if not header_seen:
                header_seen = True
                continue
            if header.cycle_idx >= len(row):
                continue
            cycle = _safe_int(row[header.cycle_idx])
            if cycle is None:
                continue
            bw = _safe_float(row[header.bw_idx]) if header.bw_idx < len(row) else None
            occ = _safe_float(row[header.occ_idx]) if header.occ_idx < len(row) else None
            if bw is None:
                bw = 0.0
            if occ is None:
                occ = 0.0
            part_values: List[float] = []
            for _part_idx, col_idx in header.part_columns:
                if col_idx < len(row):
                    value = _safe_float(row[col_idx])
                    part_values.append(value if value is not None else 0.0)
                else:
                    part_values.append(0.0)
            yield cycle, bw, occ, part_values


@dataclass
class ScanInfo:
    unique_cycles: int
    first_cycle: int
    last_cycle: int
    max_bw_gbps: float
    max_occupancy: float
    theoretical_bw_gbps_est: float
    partition_count: int


@dataclass
class SeriesPoint:
    cycle_mid: float
    cycle_start: int
    cycle_end: int
    sample_count: int
    bw_avg: float
    occ_avg: float
    part_avg: List[float]


def _compute_window(
    unique_cycles: int, *, target_points: int, window_override: Optional[int]
) -> int:
    if window_override is not None and window_override > 0:
        return int(window_override)
    target = max(10, int(target_points))
    return max(1, int(unique_cycles) // target)


def scan_csv(csv_path: Path, header: HeaderInfo) -> ScanInfo:
    max_bw = 0.0
    max_occ = 0.0
    first_cycle: Optional[int] = None
    last_cycle: Optional[int] = None
    ratio_sum = 0.0
    ratio_count = 0
    rows = 0

    for cycle, bw, occ, _parts in _iter_rows(csv_path, header):
        rows += 1
        if first_cycle is None or cycle < first_cycle:
            first_cycle = cycle
        if last_cycle is None or cycle > last_cycle:
            last_cycle = cycle
        if bw > max_bw:
            max_bw = bw
        if occ > max_occ:
            max_occ = occ
        if occ > 0.0:
            ratio_sum += bw / occ
            ratio_count += 1

    if rows == 0:
        raise SystemExit("no usable rows")
    return ScanInfo(
        unique_cycles=rows,
        first_cycle=first_cycle if first_cycle is not None else 0,
        last_cycle=last_cycle if last_cycle is not None else 0,
        max_bw_gbps=max_bw,
        max_occupancy=max_occ,
        theoretical_bw_gbps_est=(ratio_sum / ratio_count) if ratio_count else 0.0,
        partition_count=len(header.part_columns),
    )


def bin_csv(
    csv_path: Path, header: HeaderInfo, *, window: int
) -> List[SeriesPoint]:
    points: List[SeriesPoint] = []
    part_count = len(header.part_columns)
    if part_count <= 0:
        return points

    cur_count = 0
    cycle_start: Optional[int] = None
    cycle_end: Optional[int] = None
    bw_sum = 0.0
    occ_sum = 0.0
    part_sums = [0.0 for _ in range(part_count)]

    def flush() -> None:
        nonlocal cur_count, cycle_start, cycle_end, bw_sum, occ_sum, part_sums
        if cur_count <= 0 or cycle_start is None or cycle_end is None:
            return
        mid = 0.5 * (cycle_start + cycle_end)
        part_avg = [v / cur_count for v in part_sums]
        points.append(
            SeriesPoint(
                cycle_mid=mid,
                cycle_start=cycle_start,
                cycle_end=cycle_end,
                sample_count=cur_count,
                bw_avg=bw_sum / cur_count,
                occ_avg=occ_sum / cur_count,
                part_avg=part_avg,
            )
        )
        cur_count = 0
        cycle_start = None
        cycle_end = None
        bw_sum = 0.0
        occ_sum = 0.0
        part_sums = [0.0 for _ in range(part_count)]

    for cycle, bw, occ, part_values in _iter_rows(csv_path, header):
        if cycle_start is None:
            cycle_start = cycle
        cycle_end = cycle
        cur_count += 1
        bw_sum += bw
        occ_sum += occ
        for i in range(part_count):
            part_sums[i] += part_values[i] if i < len(part_values) else 0.0
        if cur_count >= window:
            flush()

    flush()
    return points


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
            "PNG/SVG output requires matplotlib.\n"
            f"Install into {target} with:\n"
            f"  TMPDIR=... PIP_CACHE_DIR=... pip3 install --no-cache-dir --target {target} "
            "numpy==1.19.5 matplotlib==3.2.2\n"
            f"error: {exc}"
        ) from exc


def _partition_colors(partitions: int) -> List[Tuple[float, float, float, float]]:
    _, plt, _ = _require_matplotlib()
    palette: List[Tuple[float, float, float, float]] = []
    for cmap_name in ("tab20", "tab20b", "tab20c"):
        cmap = plt.get_cmap(cmap_name)
        for i in range(cmap.N):
            palette.append(cmap(i))
    if not palette:
        return [(0.2, 0.4, 0.8, 0.9)] * partitions
    if partitions <= len(palette):
        return palette[:partitions]
    colors: List[Tuple[float, float, float, float]] = []
    for i in range(partitions):
        colors.append(palette[i % len(palette)])
    return colors


def _compute_weighted_stats(series: Sequence[SeriesPoint]) -> Tuple[float, float]:
    total_samples = sum(p.sample_count for p in series)
    if total_samples == 0:
        return 0.0, 0.0
    avg_bw = sum(p.bw_avg * p.sample_count for p in series) / total_samples
    avg_occ = sum(p.occ_avg * p.sample_count for p in series) / total_samples
    return avg_bw, avg_occ


def _build_partition_stack_figure(
    *,
    title: str,
    subtitle: str,
    series: Sequence[SeriesPoint],
    scan: ScanInfo,
    smooth: int = 1,
    width: int = 1280,
    height: int = 560,
    dpi: int = 100,
    legend: bool = False,
) -> "object":
    if not series:
        raise SystemExit("empty series")

    _, plt, FuncFormatter = _require_matplotlib()

    x = [p.cycle_mid for p in series]
    part_count = scan.partition_count
    part_series = [list() for _ in range(part_count)]
    occ_series: List[float] = []
    for point in series:
        for i, value in enumerate(point.part_avg):
            part_series[i].append(value)
        occ_series.append(point.occ_avg)

    smoothed_parts = [smooth_moving_average(vals, smooth) for vals in part_series]
    total_line = [
        sum(smoothed_parts[j][i] for j in range(part_count)) for i in range(len(x))
    ]
    occ_max = max(occ_series) if occ_series else 0.0
    occ_upper = occ_max * 1.05 if occ_max > 0.0 else 0.01

    colors = _partition_colors(part_count)
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("white")

    text = "#0f172a"
    subtext = "#475569"
    grid = "#e9eef5"

    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.08, right=0.98)
    fig.text(0.08, 0.95, title, fontsize=18, color=text)
    fig.text(0.08, 0.91, subtitle, fontsize=10, color=subtext)

    avg_bw, avg_occ = _compute_weighted_stats(series)
    summary = (
        f"avg_bw={avg_bw:.1f} GB/s  peak_bw={scan.max_bw_gbps:.1f} GB/s  "
        f"avg_occ={avg_occ * 100:.1f}%  peak_occ={scan.max_occupancy * 100:.1f}%"
    )
    if scan.theoretical_bw_gbps_est > 0.0:
        summary += f"  theory≈{scan.theoretical_bw_gbps_est:.1f} GB/s"
    explain = "stacked=partition bandwidth (window mean)  line=total  right-axis=occupancy"
    fig.text(0.08, 0.87, explain, fontsize=9, color=subtext)
    fig.text(0.98, 0.87, summary, fontsize=9, color=subtext, ha="right")

    labels = [f"part{i}" for i in range(part_count)]
    ax.stackplot(
        x, smoothed_parts, colors=colors, alpha=0.88, linewidth=0, labels=labels
    )
    ax.plot(x, total_line, color=text, linewidth=1.6)

    ax2 = ax.twinx()
    ax2.set_ylim(0.0, occ_upper)
    ax2.set_ylabel("HBM occupancy (utilization)", color=subtext)
    ax2.tick_params(axis="y", colors=subtext)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _pos: f"{y*100:.0f}%"))

    ax.set_ylabel("HBM bandwidth (GB/s)", color=subtext)
    ax.set_xlabel("cycle", color=subtext)
    ax.grid(True, color=grid, linewidth=1)
    ax.set_axisbelow(True)

    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))

    for spine in ax.spines.values():
        spine.set_color(grid)
    for spine in ax2.spines.values():
        spine.set_color(grid)

    if legend:
        ax.legend(loc="upper right", frameon=False, ncol=4, fontsize=7)

    return fig


def write_partition_stack_plot(
    out_path: Path,
    *,
    title: str,
    subtitle: str,
    series: Sequence[SeriesPoint],
    scan: ScanInfo,
    smooth: int = 1,
    width: int = 1280,
    height: int = 560,
    dpi: int = 100,
    legend: bool = False,
) -> None:
    _, plt, _ = _require_matplotlib()
    fig = _build_partition_stack_figure(
        title=title,
        subtitle=subtitle,
        series=series,
        scan=scan,
        smooth=smooth,
        width=width,
        height=height,
        dpi=dpi,
        legend=legend,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot HBM partition bandwidth over time (PNG by default). "
            "If no input is provided, the script picks the most-recent CSV under result/bandwidth."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 plot_partition_bandwidth_over_time.py\n"
            "  python3 plot_partition_bandwidth_over_time.py ../btree_hbm_partition.csv\n"
            "  python3 plot_partition_bandwidth_over_time.py --stem btree_hbm_partition\n"
            "  python3 plot_partition_bandwidth_over_time.py --all --points 3000\n"
            "  python3 plot_partition_bandwidth_over_time.py --smooth 9\n"
            "  python3 plot_partition_bandwidth_over_time.py --format svg\n"
        ),
    )
    parser.add_argument(
        "positional_csvs",
        nargs="*",
        type=Path,
        help="Input CSV path(s). If omitted, auto-pick from result/bandwidth.",
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
        help="Pick input CSV by stem from result/bandwidth (can be repeated).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot all matching CSVs under result/bandwidth.",
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
        "--legend",
        action="store_true",
        help="Show partition legend (can be large if many partitions).",
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
            path = (BANDWIDTH_DIR / f"{stem}.csv").resolve()
            inputs.append(path)

    if args.all:
        inputs.extend(_discover_candidates(BANDWIDTH_DIR))

    if not inputs:
        inputs = [discover_default_input(BANDWIDTH_DIR)]

    dedup: List[Path] = []
    seen: set = set()
    for path in inputs:
        p = path.resolve()
        if p in seen:
            continue
        seen.add(p)
        dedup.append(p)
    return dedup


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    inputs = resolve_inputs(args)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for csv_path in inputs:
        if not csv_path.is_file():
            print(f"[skip] not found: {csv_path}", file=sys.stderr)
            failures += 1
            continue

        try:
            header = _read_header_info(csv_path)
            scan = scan_csv(csv_path, header)
            window = _compute_window(
                scan.unique_cycles, target_points=args.points, window_override=args.window
            )
            series = bin_csv(csv_path, header, window=window)
        except SystemExit as exc:
            print(f"[skip] {csv_path.name}: {exc}", file=sys.stderr)
            failures += 1
            continue

        title = f"{csv_path.name} HBM partition bandwidth over time"
        subtitle = (
            f"unique_cycles={scan.unique_cycles}  window={window}  points={len(series)}  "
            f"partitions={scan.partition_count}  max_bw={scan.max_bw_gbps:.1f}GB/s"
        )

        outputs: List[Path] = []
        want_png = args.format in ("png", "both")
        want_svg = args.format in ("svg", "both")

        if want_png:
            out_png = out_dir / f"{csv_path.stem}_partition_bandwidth.png"
            try:
                write_partition_stack_plot(
                    out_png,
                    title=title,
                    subtitle=subtitle,
                    series=series,
                    scan=scan,
                    smooth=args.smooth,
                    width=args.width,
                    height=args.height,
                    dpi=args.dpi,
                    legend=args.legend,
                )
                outputs.append(out_png)
            except SystemExit as exc:
                print(f"[skip] PNG: {csv_path.name}: {exc}", file=sys.stderr)
                failures += 1

        if want_svg:
            out_svg = out_dir / f"{csv_path.stem}_partition_bandwidth.svg"
            try:
                write_partition_stack_plot(
                    out_svg,
                    title=title,
                    subtitle=subtitle,
                    series=series,
                    scan=scan,
                    smooth=args.smooth,
                    width=args.width,
                    height=args.height,
                    dpi=args.dpi,
                    legend=args.legend,
                )
                outputs.append(out_svg)
            except SystemExit as exc:
                print(f"[skip] SVG: {csv_path.name}: {exc}", file=sys.stderr)
                failures += 1

        print(f"input: {csv_path}")
        for out_path in outputs:
            print(f"output: {out_path}")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
