#!/usr/bin/env python3
"""
Plot L2 data/fill port utilization over time from l2_bw CSVs.

Default input directory:
  accel-sim-framework/result/l2_bw

Default output directory:
  accel-sim-framework/result/l2_bw/plot/result
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
_PYDEPS_ENABLED = False

PLOT_DIR = SCRIPT_DIR.parent
TRACE_DIR = PLOT_DIR.parent
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


def infer_peak_gbps(bw: Sequence[float], util: Sequence[float]) -> Optional[float]:
    pairs: List[Tuple[float, float]] = []
    for b, u in zip(bw, util):
        if b <= 0.0 or u <= 0.0:
            continue
        if u > 1.5:
            continue
        pairs.append((float(b), float(u)))
    if not pairs:
        return None

    max_u = max(u for _b, u in pairs)
    threshold = max_u * 0.1
    ratios = [b / u for b, u in pairs if u >= threshold]
    if not ratios:
        ratios = [b / u for b, u in pairs]
    ratios.sort()
    return ratios[len(ratios) // 2]


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
    preferred = [p for p in candidates if "l2" in p.stem.lower()]
    return preferred or candidates


def discover_default_input(trace_dir: Path) -> Path:
    candidates = _discover_candidates(trace_dir)
    if not candidates:
        raise SystemExit(f"no CSV candidates found under: {trace_dir}")
    return candidates[0]


@dataclass
class HeaderInfo:
    cycle_begin_idx: int
    cycle_end_idx: int
    data_bw_idx: int
    fill_bw_idx: int
    data_util_idx: int
    fill_util_idx: int


def _read_header_info(csv_path: Path) -> HeaderInfo:
    header = _open_csv_header(csv_path)
    if not header:
        raise SystemExit("missing CSV header")
    header_map = {_norm_header(name): idx for idx, name in enumerate(header)}
    required = (
        "cycle_begin",
        "cycle_end",
        "l2_data_gbps",
        "l2_fill_gbps",
        "l2_data_util",
        "l2_fill_util",
    )
    missing = [name for name in required if name not in header_map]
    if missing:
        raise SystemExit(f"missing required columns: {', '.join(missing)}")
    return HeaderInfo(
        cycle_begin_idx=int(header_map["cycle_begin"]),
        cycle_end_idx=int(header_map["cycle_end"]),
        data_bw_idx=int(header_map["l2_data_gbps"]),
        fill_bw_idx=int(header_map["l2_fill_gbps"]),
        data_util_idx=int(header_map["l2_data_util"]),
        fill_util_idx=int(header_map["l2_fill_util"]),
    )


def _iter_rows(csv_path: Path) -> Iterator[List[str]]:
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
            yield row


def read_series(
    csv_path: Path, header: HeaderInfo
) -> Tuple[List[float], List[float], List[float], List[float], List[float]]:
    x: List[float] = []
    data_bw: List[float] = []
    fill_bw: List[float] = []
    data_util: List[float] = []
    fill_util: List[float] = []

    for row in _iter_rows(csv_path):
        if header.cycle_begin_idx >= len(row) or header.cycle_end_idx >= len(row):
            continue
        c0 = _safe_int(row[header.cycle_begin_idx])
        c1 = _safe_int(row[header.cycle_end_idx])
        if c0 is None or c1 is None:
            continue
        mid = 0.5 * (c0 + c1)

        dbw = _safe_float(row[header.data_bw_idx]) if header.data_bw_idx < len(row) else None
        fbw = _safe_float(row[header.fill_bw_idx]) if header.fill_bw_idx < len(row) else None
        du = _safe_float(row[header.data_util_idx]) if header.data_util_idx < len(row) else None
        fu = _safe_float(row[header.fill_util_idx]) if header.fill_util_idx < len(row) else None

        x.append(mid)
        data_bw.append(dbw if dbw is not None else 0.0)
        fill_bw.append(fbw if fbw is not None else 0.0)
        data_util.append(du if du is not None else 0.0)
        fill_util.append(fu if fu is not None else 0.0)

    return x, data_bw, fill_bw, data_util, fill_util


def _require_matplotlib() -> "tuple[object, object, object]":
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.ticker import FuncFormatter  # type: ignore

        return matplotlib, plt, FuncFormatter
    except Exception as exc:
        global _PYDEPS_ENABLED
        if _PYDEPS_DIR.is_dir() and not _PYDEPS_ENABLED:
            sys.path.insert(0, str(_PYDEPS_DIR))
            _PYDEPS_ENABLED = True
            return _require_matplotlib()
        raise SystemExit(
            "SVG/PNG output requires matplotlib+numpy. "
            "If your system python lacks them, vendor deps under: "
            f"{_PYDEPS_DIR}\nerror: {exc}"
        ) from exc


def write_plot(
    out_path: Path,
    *,
    title: str,
    subtitle: str,
    x: Sequence[float],
    data_util: Sequence[float],
    fill_util: Sequence[float],
    smooth: int = 1,
    width: int = 1280,
    height: int = 560,
    dpi: int = 100,
) -> None:
    _, plt, FuncFormatter = _require_matplotlib()

    data_util_s = smooth_moving_average(data_util, smooth)
    fill_util_s = smooth_moving_average(fill_util, smooth)

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor("white")

    text = "#0f172a"
    subtext = "#475569"
    grid = "#e9eef5"

    fig.subplots_adjust(top=0.82, bottom=0.14, left=0.08, right=0.92)
    fig.text(0.08, 0.95, title, fontsize=18, color=text)
    fig.text(0.08, 0.91, subtitle, fontsize=10, color=subtext)

    ax.fill_between(x, data_util_s, 0, color="#16a34a", alpha=0.12, linewidth=0)
    ax.plot(x, data_util_s, color="#16a34a", linewidth=1.8, label="data util")
    ax.fill_between(
        x, fill_util_s, 0, color="#8b5cf6", alpha=0.12, linewidth=0
    )
    ax.plot(x, fill_util_s, color="#8b5cf6", linewidth=1.8, label="fill util")
    ax.set_ylabel("utilization", color=subtext)
    ax.set_xlabel("cycle", color=subtext)
    ax.grid(True, color=grid, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_ylim(0.0, 1.05)
    ax.tick_params(axis="y", colors=subtext)
    ax.tick_params(axis="x", colors=subtext)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _pos: f"{y*100:.0f}%"))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: _format_si(v)))

    ax.legend(loc="upper right", frameon=False, fontsize=8)

    for spine in ax.spines.values():
        spine.set_color(grid)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor="white")
    plt.close(fig)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot L2 data/fill port utilization over time from l2_bw CSVs. "
            "If no input is provided, the script picks the most-recent CSV under result/l2_bw."
        )
    )
    parser.add_argument(
        "positional_csvs",
        nargs="*",
        type=Path,
        help="Input CSV path(s). If omitted, auto-pick from result/l2_bw.",
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
        help="Pick input CSV by stem from result/l2_bw (can be repeated).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Plot all matching CSVs under result/l2_bw.",
    )
    parser.add_argument(
        "--smooth",
        type=int,
        default=1,
        help="Moving-average smoothing in plotted points (default: %(default)s; 1 disables).",
    )
    parser.add_argument(
        "--format",
        choices=("svg", "png", "both"),
        default="svg",
        help="Output format (default: %(default)s).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=100,
        help="PNG DPI (default: %(default)s).",
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
            inputs.append((TRACE_DIR / f"{stem}.csv").resolve())
    if args.all:
        inputs.extend(_discover_candidates(TRACE_DIR))
    if not inputs:
        inputs = [discover_default_input(TRACE_DIR)]

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
            x, data_bw, fill_bw, data_util, fill_util = read_series(csv_path, header)
        except SystemExit as exc:
            print(f"[skip] {csv_path.name}: {exc}", file=sys.stderr)
            failures += 1
            continue

        if not x:
            print(f"[skip] {csv_path.name}: no usable rows", file=sys.stderr)
            failures += 1
            continue

        peak_data = infer_peak_gbps(data_bw, data_util)
        peak_fill = infer_peak_gbps(fill_bw, fill_util)
        peak_parts: List[str] = []
        if peak_data is not None:
            peak_parts.append(f"data={peak_data:.2f} GB/s")
        if peak_fill is not None:
            peak_parts.append(f"fill={peak_fill:.2f} GB/s")
        peak_text = "peak " + ", ".join(peak_parts) if peak_parts else "peak N/A"

        title = f"{csv_path.name} L2 utilization over time"
        subtitle = (
            f"points={len(x)}  smooth={args.smooth}  {peak_text}  "
            "(windowed CSV: no re-binning)"
        )

        want_svg = args.format in ("svg", "both")
        want_png = args.format in ("png", "both")
        outputs: List[Path] = []

        if want_svg:
            out_svg = out_dir / f"{csv_path.stem}_l2_bw_over_time.svg"
            write_plot(
                out_svg,
                title=title,
                subtitle=subtitle,
                x=x,
                data_util=data_util,
                fill_util=fill_util,
                smooth=args.smooth,
                width=args.width,
                height=args.height,
                dpi=args.dpi,
            )
            outputs.append(out_svg)
        if want_png:
            out_png = out_dir / f"{csv_path.stem}_l2_bw_over_time.png"
            write_plot(
                out_png,
                title=title,
                subtitle=subtitle,
                x=x,
                data_util=data_util,
                fill_util=fill_util,
                smooth=args.smooth,
                width=args.width,
                height=args.height,
                dpi=args.dpi,
            )
            outputs.append(out_png)

        print(f"input: {csv_path}")
        for out_path in outputs:
            print(f"output: {out_path}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
