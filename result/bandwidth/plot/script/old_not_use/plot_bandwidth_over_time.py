#!/usr/bin/env python3
"""
Plot HBM occupancy (bandwidth utilization) over time from an Accel-Sim CSV trace.

Supports plain CSV as well as `*.csv.gz` and `*.csv.zst` (zstd requires the `zstd`
command in PATH, unless you install the `zstandard` Python module).

This script writes PNG plots by default (requires matplotlib + numpy; can be placed in
`./_pydeps` next to this script). It can also write SVG plots (no extra deps) to:
  accel-sim-framework/result/issue_trace/plot/result/bandwidth

The input CSV must contain:
  - cycle
  - hbm_bw_GBps
  - hbm_occupancy

Notes:
  - Issue trace CSVs log multiple rows per cycle, and the file is not globally cycle-sorted
    (due to buffered per-SM flushing). To produce a correct time series, this script
    deduplicates globally by cycle and then sorts by cycle.
  - L1 trace CSVs also work as input, but may be sparse in time.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import math
import shutil
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, TextIO, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
# Optional local deps (kept outside git): e.g., matplotlib for PNG output.
_PYDEPS_DIR = SCRIPT_DIR / "_pydeps"
if _PYDEPS_DIR.is_dir():
    sys.path.insert(0, str(_PYDEPS_DIR))

PLOT_DIR = SCRIPT_DIR.parent
ISSUE_TRACE_DIR = PLOT_DIR.parent
DEFAULT_OUT_DIR = PLOT_DIR / "result" / "bandwidth"

_CSV_EXTS_BY_PREFERENCE = (".csv.zst", ".csv.gz", ".csv")


@contextmanager
def _open_text(path: Path, *, newline: str = "") -> Iterator[TextIO]:
    suffix = path.suffix.lower()
    if suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline=newline) as handle:
            yield handle
        return

    if suffix == ".zst":
        try:
            import zstandard as zstd  # type: ignore

            with path.open("rb") as raw:
                with zstd.ZstdDecompressor().stream_reader(raw) as reader:
                    with io.TextIOWrapper(
                        reader, encoding="utf-8", errors="replace", newline=newline
                    ) as handle:
                        yield handle
            return
        except Exception:
            if shutil.which("zstd") is None:
                raise SystemExit(
                    f"zstd input detected but no decompressor is available for: {path}\n"
                    "Install either:\n"
                    "  - the `zstd` command (recommended), or\n"
                    "  - the Python `zstandard` module.\n"
                )

            proc = subprocess.Popen(
                ["zstd", "-dc", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert proc.stdout is not None
            try:
                with io.TextIOWrapper(
                    proc.stdout, encoding="utf-8", errors="replace", newline=newline
                ) as handle:
                    yield handle
            finally:
                stderr = b""
                if proc.stderr is not None:
                    stderr = proc.stderr.read()
                    proc.stderr.close()
                ret = proc.wait()
                if ret != 0:
                    msg = stderr.decode("utf-8", errors="replace").strip()
                    raise SystemExit(f"zstd -dc failed (exit {ret}) for {path}: {msg}")
            return

    with path.open("r", encoding="utf-8", errors="replace", newline=newline) as handle:
        yield handle


def _resolve_issue_trace_path_by_stem(issue_trace_dir: Path, stem: str) -> Path:
    for ext in _CSV_EXTS_BY_PREFERENCE:
        candidate = (issue_trace_dir / f"{stem}{ext}").resolve()
        if candidate.is_file():
            return candidate
    # Keep backward-compatible default (main() will report not found if missing).
    return (issue_trace_dir / f"{stem}.csv").resolve()


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
    """Simple centered moving average smoothing (window in points)."""
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
    with _open_text(path, newline="") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                continue
            return row
    return []


def _has_bandwidth_columns(path: Path) -> bool:
    header = _open_csv_header(path)
    if not header:
        return False
    normalized = {_norm_header(name) for name in header}
    return "cycle" in normalized and "hbm_bw_gbps" in normalized and "hbm_occupancy" in normalized


def _discover_candidates(issue_trace_dir: Path) -> List[Path]:
    if not issue_trace_dir.is_dir():
        return []
    # Top-level CSVs only (avoid plot outputs).
    candidates: List[Path] = []
    for pattern in ("*.csv", "*.csv.gz", "*.csv.zst"):
        candidates.extend(issue_trace_dir.glob(pattern))
    candidates = [p for p in candidates if not p.name.endswith(".csv.fifo")]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    # Prefer files that look like issue traces.
    preferred = [p for p in candidates if "issue" in p.stem.lower()]
    return preferred or candidates


def discover_default_input(issue_trace_dir: Path) -> Path:
    candidates = _discover_candidates(issue_trace_dir)
    if not candidates:
        raise SystemExit(f"no CSV candidates found under: {issue_trace_dir}")

    # Prefer the most-recent file that already includes bandwidth columns.
    for path in candidates:
        try:
            if _has_bandwidth_columns(path):
                return path
        except OSError:
            continue

    # Fall back to the latest CSV; main() will emit a helpful error if columns are missing.
    return candidates[0]


@dataclass
class ScanInfo:
    unique_cycles: int
    first_cycle: int
    last_cycle: int
    max_bw_gbps: float
    max_occupancy: float
    theoretical_bw_gbps_est: float


@dataclass
class SeriesPoint:
    cycle_mid: float
    cycle_start: int
    cycle_end: int
    sample_count: int
    bw_avg: float
    bw_min: float
    bw_max: float
    occ_avg: float
    occ_min: float
    occ_max: float


def _compute_window(
    unique_cycles: int, *, target_points: int, window_override: Optional[int]
) -> int:
    if window_override is not None and window_override > 0:
        return int(window_override)
    target = max(10, int(target_points))
    return max(1, int(unique_cycles) // target)


def collect_unique_cycle_samples(
    csv_path: Path,
) -> Tuple[ScanInfo, List[Tuple[int, float, float]]]:
    """Collect one (bw, occ) sample per unique cycle, then return samples sorted by cycle."""

    samples: Dict[int, Tuple[float, float]] = {}
    max_bw = 0.0
    max_occ = 0.0
    ratio_sum = 0.0
    ratio_count = 0

    def add_sample(cycle: int, bw: float, occ: float) -> None:
        nonlocal max_bw, max_occ, ratio_sum, ratio_count
        if cycle in samples:
            return
        samples[cycle] = (bw, occ)
        if bw > max_bw:
            max_bw = bw
        if occ > max_occ:
            max_occ = occ
        if occ > 0.0:
            ratio_sum += bw / occ
            ratio_count += 1

    used_fast_tail = False
    try:
        with _open_text(csv_path) as handle:
            header: Optional[List[str]] = None
            for line in handle:
                if not line:
                    continue
                if line.lstrip().startswith("#"):
                    continue
                stripped = line.strip()
                if not stripped:
                    continue
                header = [part.strip() for part in stripped.split(",")]
                break
            if header is None:
                raise SystemExit(f"empty CSV: {csv_path}")

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
                raise SystemExit(
                    f"missing required columns in {csv_path.name}: {', '.join(missing)}"
                )

            fast_tail = (
                cycle_idx == 0
                and bw_idx == len(header) - 2
                and occ_idx == len(header) - 1
            )
            if fast_tail:
                used_fast_tail = True
                for line in handle:
                    if not line:
                        continue
                    if line.lstrip().startswith("#"):
                        continue
                    stripped = line.strip()
                    if not stripped:
                        continue

                    comma = stripped.find(",")
                    if comma <= 0:
                        continue
                    cycle = _safe_int(stripped[:comma])
                    if cycle is None or cycle in samples:
                        continue
                    try:
                        _, bw_str, occ_str = stripped.rsplit(",", 2)
                    except ValueError:
                        continue
                    bw = _safe_float(bw_str)
                    occ = _safe_float(occ_str)
                    if bw is None or occ is None:
                        continue
                    add_sample(cycle, bw, occ)
    except OSError as exc:
        raise SystemExit(f"unable to open {csv_path}: {exc}") from exc

    if not used_fast_tail:
        # Generic CSV parsing for non-tail layouts (e.g. L1 traces).
        with _open_text(csv_path, newline="") as handle:
            reader = csv.reader(handle)
            header: Optional[List[str]] = None
            for row in reader:
                if not row:
                    continue
                if row[0].lstrip().startswith("#"):
                    continue
                header = row
                break
            if header is None:
                raise SystemExit(f"empty CSV: {csv_path}")

            header_map = {_norm_header(name): idx for idx, name in enumerate(header)}
            cycle_idx = header_map.get("cycle")
            bw_idx = header_map.get("hbm_bw_gbps")
            occ_idx = header_map.get("hbm_occupancy")
            if cycle_idx is None or bw_idx is None or occ_idx is None:
                raise SystemExit(f"missing required columns in {csv_path.name}")

            for row in reader:
                if not row:
                    continue
                if row[0].lstrip().startswith("#"):
                    continue
                if cycle_idx >= len(row):
                    continue
                cycle = _safe_int(row[cycle_idx])
                if cycle is None or cycle in samples:
                    continue
                bw = _safe_float(row[bw_idx]) if bw_idx < len(row) else None
                occ = _safe_float(row[occ_idx]) if occ_idx < len(row) else None
                if bw is None or occ is None:
                    continue
                add_sample(cycle, bw, occ)

    if not samples:
        raise SystemExit(f"no usable bandwidth samples found in: {csv_path}")

    cycles_sorted = sorted(samples)
    first_cycle = cycles_sorted[0]
    last_cycle = cycles_sorted[-1]
    theory = (ratio_sum / ratio_count) if ratio_count else 0.0
    scan = ScanInfo(
        unique_cycles=len(samples),
        first_cycle=first_cycle,
        last_cycle=last_cycle,
        max_bw_gbps=max_bw,
        max_occupancy=max_occ,
        theoretical_bw_gbps_est=theory,
    )
    series = [(c, samples[c][0], samples[c][1]) for c in cycles_sorted]
    return scan, series


def process_csv(
    csv_path: Path, *, target_points: int, window_override: Optional[int]
) -> Tuple[ScanInfo, List[SeriesPoint], int]:
    """Read CSV, build a per-cycle time series, then smooth into windowed points."""

    scan, samples = collect_unique_cycle_samples(csv_path)
    window = _compute_window(
        scan.unique_cycles, target_points=target_points, window_override=window_override
    )
    if window <= 0:
        window = 1

    points: List[SeriesPoint] = []

    cur_count = 0
    cycle_start: Optional[int] = None
    cycle_end: Optional[int] = None

    bw_sum = 0.0
    bw_min = float("inf")
    bw_max = 0.0

    occ_sum = 0.0
    occ_min = float("inf")
    occ_max = 0.0

    def flush() -> None:
        nonlocal cur_count, cycle_start, cycle_end, bw_sum, bw_min, bw_max, occ_sum, occ_min, occ_max
        if cur_count <= 0 or cycle_start is None or cycle_end is None:
            return
        mid = 0.5 * (cycle_start + cycle_end)
        points.append(
            SeriesPoint(
                cycle_mid=mid,
                cycle_start=cycle_start,
                cycle_end=cycle_end,
                sample_count=cur_count,
                bw_avg=bw_sum / cur_count,
                bw_min=bw_min,
                bw_max=bw_max,
                occ_avg=occ_sum / cur_count,
                occ_min=occ_min,
                occ_max=occ_max,
            )
        )
        cur_count = 0
        cycle_start = None
        cycle_end = None
        bw_sum = 0.0
        bw_min = float("inf")
        bw_max = 0.0
        occ_sum = 0.0
        occ_min = float("inf")
        occ_max = 0.0

    for cycle, bw, occ in samples:
        if cycle_start is None:
            cycle_start = cycle
        cycle_end = cycle
        cur_count += 1

        bw_sum += bw
        if bw < bw_min:
            bw_min = bw
        if bw > bw_max:
            bw_max = bw

        occ_sum += occ
        if occ < occ_min:
            occ_min = occ
        if occ > occ_max:
            occ_max = occ

        if cur_count >= window:
            flush()

    flush()
    return scan, points, window


def write_hbm_occupancy_svg(
    out_svg: Path,
    *,
    title: str,
    subtitle: str,
    series: Sequence[SeriesPoint],
    scan: ScanInfo,
    smooth: int = 1,
    show_range: bool = True,
    width: int = 1280,
    height: int = 560,
) -> None:
    if not series:
        raise SystemExit("empty series")

    # Layout (single panel)
    left_margin = 74
    right_margin = 30
    title_y = 34
    subtitle_y = 56
    legend_explain_y = 78
    legend_summary_y = 96
    top_margin = 128
    bottom_margin = 54
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_w = chart_x1 - chart_x0

    occ_y0 = top_margin
    occ_y1 = height - bottom_margin

    x_min = min(p.cycle_start for p in series)
    x_max = max(p.cycle_end for p in series)
    if x_max <= x_min:
        x_max = x_min + 1

    def x_of(x: float) -> float:
        return chart_x0 + (x - x_min) * chart_w / (x_max - x_min)

    # Occupancy: default to [0, 1] for comparability.
    occ_min_axis = 0.0
    occ_max_axis = 1.0

    def occ_y_of(occ: float) -> float:
        t = 0.0 if occ_max_axis <= occ_min_axis else (occ - occ_min_axis) / (
            occ_max_axis - occ_min_axis
        )
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        return occ_y1 - t * (occ_y1 - occ_y0)

    # Build paths (bands + avg lines).
    def band_path(
        y_hi_fn, y_lo_fn, hi_values: Sequence[float], lo_values: Sequence[float]
    ) -> str:
        pts_hi = [
            (x_of(p.cycle_mid), y_hi_fn(v)) for p, v in zip(series, hi_values)
        ]
        pts_lo = [
            (x_of(p.cycle_mid), y_lo_fn(v)) for p, v in zip(series, lo_values)
        ]
        coords = pts_hi + list(reversed(pts_lo))
        return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in coords) + " Z"

    def line_path(y_fn, values: Sequence[float]) -> str:
        coords = [(x_of(p.cycle_mid), y_fn(v)) for p, v in zip(series, values)]
        return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in coords)

    occ_band = band_path(
        occ_y_of,
        occ_y_of,
        [p.occ_max for p in series],
        [p.occ_min for p in series],
    )
    occ_line_values = smooth_moving_average([p.occ_avg for p in series], smooth)
    occ_line = line_path(occ_y_of, occ_line_values)

    # Summary stats (weighted by samples per point).
    total_samples = sum(p.sample_count for p in series)
    occ_avg_total = (
        sum(p.occ_avg * p.sample_count for p in series) / total_samples
        if total_samples
        else 0.0
    )
    occ_peak = max(p.occ_max for p in series)
    bw_avg_total = (
        sum(p.bw_avg * p.sample_count for p in series) / total_samples
        if total_samples
        else 0.0
    )
    bw_peak = max(p.bw_max for p in series)

    # Axes ticks.
    x_ticks = 6
    x_tick_vals = [
        x_min + i * (x_max - x_min) / (x_ticks - 1) for i in range(x_ticks)
    ]

    def x_label(v: float) -> str:
        return _format_si(v)

    occ_ticks = [0.0, 0.25, 0.5, 0.75, 1.0]

    # Styling.
    bg = "#ffffff"
    grid = "#e9eef5"
    axis = "#92a1b2"
    text = "#0f172a"
    subtext = "#475569"
    occ_fill = "#2563eb"  # blue

    lines: List[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    lines.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')

    lines.append(
        f'<text x="{left_margin}" y="{title_y}" font-size="22" font-family="sans-serif" fill="{text}">{_svg_escape(title)}</text>'
    )
    lines.append(
        f'<text x="{left_margin}" y="{subtitle_y}" font-size="13" font-family="sans-serif" fill="{subtext}">{_svg_escape(subtitle)}</text>'
    )

    # Frame + vertical grid.
    lines.append(
        f'<rect x="{chart_x0}" y="{occ_y0}" width="{chart_w}" height="{occ_y1 - occ_y0}" fill="none" stroke="{grid}" stroke-width="1"/>'
    )
    for v in x_tick_vals:
        x = x_of(v)
        lines.append(
            f'<line x1="{x:.2f}" y1="{occ_y0}" x2="{x:.2f}" y2="{occ_y1}" stroke="{grid}" stroke-width="1"/>'
        )
    lines.append(
        f'<text x="{chart_x0}" y="{occ_y0 - 10}" font-size="12" font-family="sans-serif" fill="{subtext}">HBM occupancy (utilization)</text>'
    )

    # Horizontal grid + y labels
    for t in occ_ticks:
        y = occ_y_of(t)
        lines.append(
            f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid}" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{chart_x0 - 10}" y="{y + 4:.2f}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="end">{int(t * 100)}%</text>'
        )

    # X tick labels.
    for v in x_tick_vals:
        x = x_of(v)
        lines.append(
            f'<text x="{x:.2f}" y="{occ_y1 + 22}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="middle">{_svg_escape(x_label(v))}</text>'
        )
    lines.append(
        f'<text x="{chart_x0 + chart_w * 0.5:.2f}" y="{height - 12}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="middle">cycle</text>'
    )

    # Band (min~max in window) and average line.
    if show_range:
        lines.append(f'<path d="{occ_band}" fill="{occ_fill}" opacity="0.12"/>')
    lines.append(
        f'<path d="{occ_line}" fill="none" stroke="{occ_fill}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Legend / stats
    legend_x = chart_x1
    summary = (
        f"avg_occ={occ_avg_total * 100:.1f}%  peak_occ={occ_peak * 100:.1f}%  "
        f"avg_bw={bw_avg_total:.1f} GB/s  peak_bw={bw_peak:.1f} GB/s"
    )
    if scan.theoretical_bw_gbps_est > 0.0:
        summary += f"  theory≈{scan.theoretical_bw_gbps_est:.1f} GB/s"
    explain = "实线=window均值"
    if show_range:
        explain += "  阴影=min~max"
    lines.append(
        f'<text x="{left_margin}" y="{legend_explain_y}" font-size="12" font-family="sans-serif" fill="{subtext}">{_svg_escape(explain)}</text>'
    )
    lines.append(
        f'<text x="{legend_x}" y="{legend_summary_y}" font-size="12" font-family="sans-serif" fill="{subtext}" text-anchor="end">{_svg_escape(summary)}</text>'
    )

    lines.append("</svg>")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_hbm_occupancy_fill_svg(
    out_svg: Path,
    *,
    title: str,
    subtitle: str,
    series: Sequence[SeriesPoint],
    scan: ScanInfo,
    smooth: int = 1,
    width: int = 1280,
    height: int = 560,
) -> None:
    if not series:
        raise SystemExit("empty series")

    # Layout (single panel)
    left_margin = 74
    right_margin = 30
    title_y = 34
    subtitle_y = 56
    legend_explain_y = 78
    legend_summary_y = 96
    top_margin = 128
    bottom_margin = 54
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_w = chart_x1 - chart_x0

    occ_y0 = top_margin
    occ_y1 = height - bottom_margin

    x_min = min(p.cycle_start for p in series)
    x_max = max(p.cycle_end for p in series)
    if x_max <= x_min:
        x_max = x_min + 1

    def x_of(x: float) -> float:
        return chart_x0 + (x - x_min) * chart_w / (x_max - x_min)

    # Occupancy: default to [0, 1] for comparability.
    occ_min_axis = 0.0
    occ_max_axis = 1.0

    def occ_y_of(occ: float) -> float:
        t = 0.0 if occ_max_axis <= occ_min_axis else (occ - occ_min_axis) / (
            occ_max_axis - occ_min_axis
        )
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        return occ_y1 - t * (occ_y1 - occ_y0)

    # Summary stats (weighted by samples per point).
    total_samples = sum(p.sample_count for p in series)
    occ_avg_total = (
        sum(p.occ_avg * p.sample_count for p in series) / total_samples
        if total_samples
        else 0.0
    )
    occ_peak = max(p.occ_max for p in series)
    bw_avg_total = (
        sum(p.bw_avg * p.sample_count for p in series) / total_samples
        if total_samples
        else 0.0
    )
    bw_peak = max(p.bw_max for p in series)

    # Axes ticks.
    x_ticks = 6
    x_tick_vals = [
        x_min + i * (x_max - x_min) / (x_ticks - 1) for i in range(x_ticks)
    ]

    def x_label(v: float) -> str:
        return _format_si(v)

    occ_ticks = [0.0, 0.25, 0.5, 0.75, 1.0]

    # Styling.
    bg = "#ffffff"
    grid = "#e9eef5"
    text = "#0f172a"
    subtext = "#475569"
    occ_fill = "#2563eb"  # blue

    lines: List[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    lines.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{bg}"/>')

    lines.append(
        f'<text x="{left_margin}" y="{title_y}" font-size="22" font-family="sans-serif" fill="{text}">{_svg_escape(title)}</text>'
    )
    lines.append(
        f'<text x="{left_margin}" y="{subtitle_y}" font-size="13" font-family="sans-serif" fill="{subtext}">{_svg_escape(subtitle)}</text>'
    )

    # Frame + vertical grid.
    lines.append(
        f'<rect x="{chart_x0}" y="{occ_y0}" width="{chart_w}" height="{occ_y1 - occ_y0}" fill="none" stroke="{grid}" stroke-width="1"/>'
    )
    for v in x_tick_vals:
        x = x_of(v)
        lines.append(
            f'<line x1="{x:.2f}" y1="{occ_y0}" x2="{x:.2f}" y2="{occ_y1}" stroke="{grid}" stroke-width="1"/>'
        )
    lines.append(
        f'<text x="{chart_x0}" y="{occ_y0 - 10}" font-size="12" font-family="sans-serif" fill="{subtext}">HBM occupancy (utilization)</text>'
    )

    # Horizontal grid + y labels
    for t in occ_ticks:
        y = occ_y_of(t)
        lines.append(
            f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid}" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{chart_x0 - 10}" y="{y + 4:.2f}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="end">{int(t * 100)}%</text>'
        )

    # X tick labels.
    for v in x_tick_vals:
        x = x_of(v)
        lines.append(
            f'<text x="{x:.2f}" y="{occ_y1 + 22}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="middle">{_svg_escape(x_label(v))}</text>'
        )
    lines.append(
        f'<text x="{chart_x0 + chart_w * 0.5:.2f}" y="{height - 12}" font-size="11" font-family="sans-serif" fill="{subtext}" text-anchor="middle">cycle</text>'
    )

    # Filled bars (per-window mean) + optional smoothed line overlay.
    base_y = occ_y_of(0.0)
    for p in series:
        x_left = x_of(p.cycle_start)
        x_right = x_of(p.cycle_end)
        w = max(1.0, x_right - x_left)
        top_y = occ_y_of(p.occ_avg)
        h = max(0.0, base_y - top_y)
        lines.append(
            f'<rect x="{x_left:.2f}" y="{top_y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{occ_fill}" opacity="0.25"/>'
        )

    # Smoothed trend line.
    occ_line_values = smooth_moving_average([p.occ_avg for p in series], smooth)
    coords = [
        (x_of(p.cycle_mid), occ_y_of(v)) for p, v in zip(series, occ_line_values)
    ]
    occ_line = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in coords)
    lines.append(
        f'<path d="{occ_line}" fill="none" stroke="{occ_fill}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Legend / stats
    legend_x = chart_x1
    summary = (
        f"avg_occ={occ_avg_total * 100:.1f}%  peak_occ={occ_peak * 100:.1f}%  "
        f"avg_bw={bw_avg_total:.1f} GB/s  peak_bw={bw_peak:.1f} GB/s"
    )
    if scan.theoretical_bw_gbps_est > 0.0:
        summary += f"  theory≈{scan.theoretical_bw_gbps_est:.1f} GB/s"
    explain = "柱=window均值  线=平滑趋势"
    lines.append(
        f'<text x="{left_margin}" y="{legend_explain_y}" font-size="12" font-family="sans-serif" fill="{subtext}">{_svg_escape(explain)}</text>'
    )
    lines.append(
        f'<text x="{legend_x}" y="{legend_summary_y}" font-size="12" font-family="sans-serif" fill="{subtext}" text-anchor="end">{_svg_escape(summary)}</text>'
    )

    lines.append("</svg>")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def _compute_weighted_stats(series: Sequence[SeriesPoint]) -> Tuple[float, float, float, float]:
    total_samples = sum(p.sample_count for p in series)
    occ_avg_total = (
        sum(p.occ_avg * p.sample_count for p in series) / total_samples
        if total_samples
        else 0.0
    )
    occ_peak = max(p.occ_max for p in series)
    bw_avg_total = (
        sum(p.bw_avg * p.sample_count for p in series) / total_samples
        if total_samples
        else 0.0
    )
    bw_peak = max(p.bw_max for p in series)
    return occ_avg_total, occ_peak, bw_avg_total, bw_peak


def write_hbm_occupancy_png(
    out_png: Path,
    *,
    title: str,
    subtitle: str,
    series: Sequence[SeriesPoint],
    scan: ScanInfo,
    smooth: int = 1,
    show_range: bool = True,
    width: int = 1280,
    height: int = 560,
    dpi: int = 100,
) -> None:
    if not series:
        raise SystemExit("empty series")

    _, plt, FuncFormatter = _require_matplotlib()

    x = [p.cycle_mid for p in series]
    occ_avg = smooth_moving_average([p.occ_avg for p in series], smooth)
    occ_min = [p.occ_min for p in series]
    occ_max = [p.occ_max for p in series]

    blue = "#2563eb"
    grid = "#e9eef5"
    text = "#0f172a"
    subtext = "#475569"

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("white")

    fig.subplots_adjust(top=0.78, bottom=0.14, left=0.08, right=0.98)
    fig.text(0.08, 0.95, title, fontsize=18, color=text)
    fig.text(0.08, 0.91, subtitle, fontsize=10, color=subtext)

    occ_avg_total, occ_peak, bw_avg_total, bw_peak = _compute_weighted_stats(series)
    summary = (
        f"avg_occ={occ_avg_total * 100:.1f}%  peak_occ={occ_peak * 100:.1f}%  "
        f"avg_bw={bw_avg_total:.1f} GB/s  peak_bw={bw_peak:.1f} GB/s"
    )
    if scan.theoretical_bw_gbps_est > 0.0:
        summary += f"  theory≈{scan.theoretical_bw_gbps_est:.1f} GB/s"
    explain = "line=window mean"
    if show_range:
        explain += "  band=min~max"
    fig.text(0.08, 0.87, explain, fontsize=9, color=subtext)
    fig.text(0.98, 0.87, summary, fontsize=9, color=subtext, ha="right")

    if show_range:
        ax.fill_between(x, occ_min, occ_max, color=blue, alpha=0.12, linewidth=0)
    ax.plot(x, occ_avg, color=blue, linewidth=2.2)

    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("HBM occupancy (utilization)", color=subtext)
    ax.set_xlabel("cycle", color=subtext)
    ax.grid(True, color=grid, linewidth=1)
    ax.set_axisbelow(True)

    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _pos: f"{y*100:.0f}%"))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))

    for spine in ax.spines.values():
        spine.set_color(grid)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


def write_hbm_occupancy_fill_png(
    out_png: Path,
    *,
    title: str,
    subtitle: str,
    series: Sequence[SeriesPoint],
    scan: ScanInfo,
    smooth: int = 1,
    width: int = 1280,
    height: int = 560,
    dpi: int = 100,
) -> None:
    if not series:
        raise SystemExit("empty series")

    _, plt, FuncFormatter = _require_matplotlib()

    blue = "#2563eb"
    grid = "#e9eef5"
    text = "#0f172a"
    subtext = "#475569"

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(top=0.78, bottom=0.14, left=0.08, right=0.98)

    fig.text(0.08, 0.95, title, fontsize=18, color=text)
    fig.text(0.08, 0.91, subtitle, fontsize=10, color=subtext)

    occ_avg_total, occ_peak, bw_avg_total, bw_peak = _compute_weighted_stats(series)
    summary = (
        f"avg_occ={occ_avg_total * 100:.1f}%  peak_occ={occ_peak * 100:.1f}%  "
        f"avg_bw={bw_avg_total:.1f} GB/s  peak_bw={bw_peak:.1f} GB/s"
    )
    if scan.theoretical_bw_gbps_est > 0.0:
        summary += f"  theory≈{scan.theoretical_bw_gbps_est:.1f} GB/s"
    explain = "solid bars=per-window mean (filled-under-curve style)"
    fig.text(0.08, 0.87, explain, fontsize=9, color=subtext)
    fig.text(0.98, 0.87, summary, fontsize=9, color=subtext, ha="right")

    x0 = [p.cycle_start for p in series]
    widths = [max(1, p.cycle_end - p.cycle_start + 1) for p in series]
    heights = [p.occ_avg for p in series]
    ax.bar(x0, heights, width=widths, align="edge", color=blue, alpha=0.25, linewidth=0)

    # Optional overlay: smoothed trend line for readability.
    x_mid = [p.cycle_mid for p in series]
    occ_line = smooth_moving_average([p.occ_avg for p in series], smooth)
    ax.plot(x_mid, occ_line, color=blue, linewidth=1.8)

    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("HBM occupancy (utilization)", color=subtext)
    ax.set_xlabel("cycle", color=subtext)
    ax.grid(True, color=grid, linewidth=1)
    ax.set_axisbelow(True)

    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _pos: f"{y*100:.0f}%"))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))

    for spine in ax.spines.values():
        spine.set_color(grid)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot HBM occupancy (bandwidth utilization) over time (PNG by default; SVG optional). "
            "If no input is provided, the script picks the most-recent CSV under result/issue_trace."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 plot_bandwidth_over_time.py\n"
            "  python3 plot_bandwidth_over_time.py ../pathfinder_issue.csv\n"
            "  python3 plot_bandwidth_over_time.py --stem bfs_roadnet_issue\n"
            "  python3 plot_bandwidth_over_time.py --csv ../bfs_roadnet_issue.csv\n"
            "  python3 plot_bandwidth_over_time.py --all\n"
            "  python3 plot_bandwidth_over_time.py ../pathfinder_issue.csv --smooth 11\n"
            "  python3 plot_bandwidth_over_time.py ../pathfinder_issue.csv --fill\n"
        ),
    )
    parser.add_argument(
        "positional_csvs",
        nargs="*",
        type=Path,
        help="Input CSV path(s). If omitted, auto-pick from result/issue_trace.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        action="append",
        default=None,
        help="Input CSV path (can be repeated). If omitted, auto-pick from result/issue_trace.",
    )
    parser.add_argument(
        "--stem",
        action="append",
        default=None,
        help=(
            "Pick input CSV by stem from result/issue_trace (can be repeated). "
            "Example: bfs_roadnet_issue"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot all matching CSVs under result/issue_trace.",
    )
    parser.add_argument(
        "--points",
        type=int,
        default=2000,
        help="Target number of plotted points after smoothing (default: %(default)s).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=None,
        help="Smoothing window in unique cycles (overrides --points).",
    )
    parser.add_argument(
        "--smooth",
        type=int,
        default=1,
        help="Extra moving-average smoothing in plotted points (default: %(default)s; 1 disables).",
    )
    parser.add_argument(
        "--fill",
        action="store_true",
        help="Generate filled-bars plot (one window as a solid bar) instead of the line plot.",
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
        "--no-range",
        action="store_true",
        help="Disable the min~max range band and plot only the average line.",
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
            inputs.append(_resolve_issue_trace_path_by_stem(ISSUE_TRACE_DIR, stem))

    if args.all:
        inputs.extend(_discover_candidates(ISSUE_TRACE_DIR))

    if not inputs:
        inputs = [discover_default_input(ISSUE_TRACE_DIR)]

    # Dedup while preserving order.
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
            scan, series, window = process_csv(
                csv_path, target_points=args.points, window_override=args.window
            )
        except SystemExit as exc:
            print(f"[skip] {csv_path.name}: {exc}", file=sys.stderr)
            failures += 1
            continue

        title = f"{csv_path.name} HBM utilization over time"
        subtitle = (
            f"unique_cycles={scan.unique_cycles}  window={window}  points={len(series)}  "
            f"max_bw={scan.max_bw_gbps:.1f}GB/s  max_occ={scan.max_occupancy * 100:.1f}%"
        )

        outputs: List[Path] = []
        want_png = args.format in ("png", "both")
        want_svg = args.format in ("svg", "both")

        if args.fill:
            if want_png:
                out_png = out_dir / f"{csv_path.stem}_bandwidth_fill.png"
                try:
                    write_hbm_occupancy_fill_png(
                        out_png,
                        title=title,
                        subtitle=subtitle,
                        series=series,
                        scan=scan,
                        smooth=args.smooth,
                        width=args.width,
                        height=args.height,
                        dpi=args.dpi,
                    )
                    outputs.append(out_png)
                except SystemExit as exc:
                    print(f"[skip] PNG(fill): {csv_path.name}: {exc}", file=sys.stderr)
                    failures += 1
            if want_svg:
                out_svg = out_dir / f"{csv_path.stem}_bandwidth_fill.svg"
                write_hbm_occupancy_fill_svg(
                    out_svg,
                    title=title,
                    subtitle=subtitle,
                    series=series,
                    scan=scan,
                    smooth=args.smooth,
                    width=args.width,
                    height=args.height,
                )
                outputs.append(out_svg)
        else:
            if want_png:
                out_png = out_dir / f"{csv_path.stem}_bandwidth.png"
                try:
                    write_hbm_occupancy_png(
                        out_png,
                        title=title,
                        subtitle=subtitle,
                        series=series,
                        scan=scan,
                        smooth=args.smooth,
                        show_range=not args.no_range,
                        width=args.width,
                        height=args.height,
                        dpi=args.dpi,
                    )
                    outputs.append(out_png)
                except SystemExit as exc:
                    print(f"[skip] PNG: {csv_path.name}: {exc}", file=sys.stderr)
                    failures += 1
            if want_svg:
                out_svg = out_dir / f"{csv_path.stem}_bandwidth.svg"
                write_hbm_occupancy_svg(
                    out_svg,
                    title=title,
                    subtitle=subtitle,
                    series=series,
                    scan=scan,
                    smooth=args.smooth,
                    show_range=not args.no_range,
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
