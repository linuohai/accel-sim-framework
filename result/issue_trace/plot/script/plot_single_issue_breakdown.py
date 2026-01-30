#!/usr/bin/env python3
"""
Stall-reason breakdown plot (warp-event / "stall_warp_cycles" accounting).

Supported inputs:
  1) Issue-trace CSV: result/issue_trace/<log>_issue.csv[.gz/.zst]
     - Uses the classic accounting: sum the per-reason counters in STALL rows.
  2) Lightweight stats breakdown CSV: stall_reason_breakdown.csv
     - Uses the already-aggregated per-reason stall_warp_events.

Supports plain CSV as well as `*.csv.gz` and `*.csv.zst` (zstd requires the `zstd`
command in PATH, unless you install the `zstandard` Python module).

SVG output is dependency-free (standard library only). Optional PNG output
requires matplotlib. It follows the "stall warp-cycle" accounting described in
the issue-trace analysis:

- Only consume rows with event == STALL.
- For each STALL row, treat the reason counters (MEM_WAIT/REG_WAIT/...) as the
  number of warps blocked by that reason in that scheduler-cycle.
- Skip rows where all reason counters are zero (commonly warp == -1 with NA pc),
  because they typically mean "no candidate warp" rather than a true stall.

Outputs:
- <out-dir>/<stem>_stall_breakdown.csv
- <out-dir>/<stem>_stall_breakdown.svg (default)
- <out-dir>/<stem>_stall_breakdown.png (when --format png|both)

Default output directory:
  accel-sim-framework/result/issue_trace/plot/result/single_issue_breakdown
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, TextIO, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
PLOT_DIR = SCRIPT_DIR.parent
DEFAULT_OUT_DIR = PLOT_DIR / "result" / "single_issue_breakdown"

STALL_REASONS: Tuple[str, ...] = (
    "MEM_WAIT",
    "REG_WAIT",
    "IBUFFER_EMPTY",
    "WAIT_CTA_BARRIER",
    "WAIT_MEMBAR",
    "WAIT_ATOMIC",
    "WAIT_LDGSTS",
    "WAIT_DONE",
    "CONTROL_HAZARD",
    "PIPE_BUSY",
    "DUAL_ISSUE_RESTRICT",
)

# Legacy issue-trace/stat outputs used a single "BARRIER" bucket for all waiting() cases.
LEGACY_STALL_REASONS: Tuple[str, ...] = (
    "MEM_WAIT",
    "REG_WAIT",
    "IBUFFER_EMPTY",
    "BARRIER",
    "CONTROL_HAZARD",
    "PIPE_BUSY",
    "DUAL_ISSUE_RESTRICT",
)

# A simple color palette (roughly aligned with matplotlib tab10).
REASON_COLORS: Dict[str, str] = {
    "MEM_WAIT": "#1f77b4",
    "REG_WAIT": "#ff7f0e",
    "IBUFFER_EMPTY": "#2ca02c",
    # waiting() split (new)
    "WAIT_CTA_BARRIER": "#d62728",
    "WAIT_MEMBAR": "#9467bd",
    "WAIT_ATOMIC": "#8c564b",
    "WAIT_LDGSTS": "#e377c2",
    "WAIT_DONE": "#7f7f7f",
    # other reasons
    "CONTROL_HAZARD": "#bcbd22",
    "PIPE_BUSY": "#17becf",
    "DUAL_ISSUE_RESTRICT": "#aec7e8",
    # legacy combined bucket
    "BARRIER": "#d62728",
}


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


def _norm_header(name: str) -> str:
    return name.strip().lower()


def _safe_int(value: Optional[str]) -> int:
    if value is None:
        return 0
    text = value.strip()
    if not text or text.upper() == "NA":
        return 0
    try:
        return int(text, 0)
    except ValueError:
        try:
            return int(text)
        except ValueError:
            return 0


@dataclass
class BreakdownResult:
    reasons: Tuple[str, ...]
    totals: Dict[str, int]
    total_warp_cycles: int
    stall_rows_total: int
    stall_rows_used: int
    stall_rows_zero_counts: int
    stall_rows_warp_minus1: int
    stall_rows_warp_minus1_used: int
    missing_reason_columns: List[str]

def _detect_reason_set_from_header(header_map: Dict[str, int]) -> Tuple[str, ...]:
    keys = set(header_map.keys())
    if any(
        key in keys
        for key in (
            "wait_cta_barrier",
            "wait_membar",
            "wait_atomic",
            "wait_ldgsts",
            "wait_done",
        )
    ):
        return STALL_REASONS
    return LEGACY_STALL_REASONS


def _detect_reason_set_from_names(names: Iterable[str]) -> Tuple[str, ...]:
    up = {name.strip().upper() for name in names if name}
    if any(name.startswith("WAIT_") for name in up):
        return STALL_REASONS
    return LEGACY_STALL_REASONS


def analyze_issue_trace(csv_path: Path) -> BreakdownResult:
    total_warp_cycles = 0
    stall_rows_total = 0
    stall_rows_used = 0
    stall_rows_zero_counts = 0
    stall_rows_warp_minus1 = 0
    stall_rows_warp_minus1_used = 0

    with _open_text(csv_path, newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise SystemExit(f"empty csv: {csv_path}")

        header_map = {_norm_header(name): idx for idx, name in enumerate(header)}
        reasons = _detect_reason_set_from_header(header_map)
        totals = {reason: 0 for reason in reasons}
        event_idx = header_map.get("event")
        if event_idx is None:
            raise SystemExit(f"missing 'event' column in header: {csv_path}")

        warp_idx = header_map.get("warp")
        reason_idx: Dict[str, Optional[int]] = {}
        missing_reason_columns: List[str] = []
        for reason in reasons:
            idx = header_map.get(_norm_header(reason))
            if idx is None:
                missing_reason_columns.append(reason)
                reason_idx[reason] = None
            else:
                reason_idx[reason] = idx

        for row in reader:
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if event_idx >= len(row):
                continue
            if row[event_idx].strip().upper() != "STALL":
                continue

            stall_rows_total += 1
            is_warp_minus1 = False
            if warp_idx is not None and warp_idx < len(row):
                is_warp_minus1 = row[warp_idx].strip() == "-1"
                if is_warp_minus1:
                    stall_rows_warp_minus1 += 1

            per_row_counts: Dict[str, int] = {}
            row_sum = 0
            for reason, idx in reason_idx.items():
                value = _safe_int(row[idx]) if (idx is not None and idx < len(row)) else 0
                per_row_counts[reason] = value
                row_sum += value

            if row_sum == 0:
                stall_rows_zero_counts += 1
                continue

            stall_rows_used += 1
            if is_warp_minus1:
                stall_rows_warp_minus1_used += 1
            total_warp_cycles += row_sum
            for reason, value in per_row_counts.items():
                totals[reason] += value

    return BreakdownResult(
        reasons=reasons,
        totals=totals,
        total_warp_cycles=total_warp_cycles,
        stall_rows_total=stall_rows_total,
        stall_rows_used=stall_rows_used,
        stall_rows_zero_counts=stall_rows_zero_counts,
        stall_rows_warp_minus1=stall_rows_warp_minus1,
        stall_rows_warp_minus1_used=stall_rows_warp_minus1_used,
        missing_reason_columns=missing_reason_columns,
    )


def analyze_breakdown_csv(csv_path: Path) -> BreakdownResult:
    """
    Parse pre-aggregated stall reason breakdown.

    Expected header (sim-side stats):
      reason,stall_warp_events,fraction_of_stall_warp_events
    """
    counts: Dict[str, int] = {}

    with _open_text(csv_path, newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise SystemExit(f"empty csv: {csv_path}")

        header_map = {_norm_header(name): idx for idx, name in enumerate(header)}
        reason_idx = header_map.get("reason")
        if reason_idx is None:
            raise SystemExit(f"missing 'reason' column in header: {csv_path}")

        count_idx = header_map.get("stall_warp_events")
        if count_idx is None:
            count_idx = header_map.get("stall_warp_cycles")
        if count_idx is None:
            raise SystemExit(
                f"missing 'stall_warp_events' column in header: {csv_path}"
            )

        for row in reader:
            if not row:
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if reason_idx >= len(row) or count_idx >= len(row):
                continue
            reason = row[reason_idx].strip().upper()
            counts[reason] = counts.get(reason, 0) + _safe_int(row[count_idx])

    reasons = _detect_reason_set_from_names(counts.keys())
    totals = {reason: counts.get(reason, 0) for reason in reasons}
    total_warp_cycles = sum(totals.values())
    return BreakdownResult(
        reasons=reasons,
        totals=totals,
        total_warp_cycles=total_warp_cycles,
        stall_rows_total=0,
        stall_rows_used=0,
        stall_rows_zero_counts=0,
        stall_rows_warp_minus1=0,
        stall_rows_warp_minus1_used=0,
        missing_reason_columns=[],
    )


def _detect_input_is_issue_trace(csv_path: Path) -> bool:
    with _open_text(csv_path, newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise SystemExit(f"empty csv: {csv_path}")
    header_map = {_norm_header(name): idx for idx, name in enumerate(header)}
    return "event" in header_map


def write_breakdown_csv(
    out_csv: Path, stem: str, result: BreakdownResult, *, sort: bool = True
) -> None:
    rows = []
    denom = result.total_warp_cycles or 1
    for reason in result.reasons:
        value = result.totals.get(reason, 0)
        rows.append((reason, value, value / denom))
    if sort:
        rows.sort(key=lambda item: item[1], reverse=True)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "reason",
                "stall_warp_cycles",
                "fraction_of_stall_warp_cycles",
                "input_stem",
                "stall_rows_total",
                "stall_rows_used",
                "stall_rows_zero_counts_skipped",
            ]
        )
        for reason, value, frac in rows:
            writer.writerow(
                [
                    reason,
                    value,
                    f"{frac:.8f}",
                    stem,
                    result.stall_rows_total,
                    result.stall_rows_used,
                    result.stall_rows_zero_counts,
                ]
            )


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def write_breakdown_svg(
    out_svg: Path,
    title: str,
    result: BreakdownResult,
    *,
    width: int = 980,
    bar_height: int = 24,
    row_gap: int = 10,
    left_margin: int = 30,
    right_margin: int = 30,
    top_margin: int = 70,
    bottom_margin: int = 40,
    label_width: int = 220,
    sort: bool = True,
) -> None:
    denom = result.total_warp_cycles
    if denom <= 0:
        denom = 0

    items = [(reason, result.totals.get(reason, 0)) for reason in result.reasons]
    if sort:
        items.sort(key=lambda item: item[1], reverse=True)

    chart_x = left_margin + label_width
    chart_width = max(1, width - chart_x - right_margin)
    n = len(items)
    height = top_margin + n * bar_height + (n - 1) * row_gap + bottom_margin

    def y_of(i: int) -> int:
        return top_margin + i * (bar_height + row_gap)

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')

    title_text = _svg_escape(title)
    subtitle = (
        f"stall_warp_cycles={result.total_warp_cycles}"
    )
    if result.stall_rows_total:
        subtitle += (
            f"  STALL_rows_used={result.stall_rows_used}/{result.stall_rows_total}"
            f"  zero_count_STALL_rows_skipped={result.stall_rows_zero_counts}"
        )
    lines.append(
        f'<text x="{left_margin}" y="{left_margin + 5}" font-size="22" font-family="sans-serif">{title_text}</text>'
    )
    lines.append(
        f'<text x="{left_margin}" y="{left_margin + 30}" font-size="13" fill="#444" font-family="sans-serif">{_svg_escape(subtitle)}</text>'
    )

    # Axes baseline
    baseline_y = y_of(n - 1) + bar_height + 10
    lines.append(
        f'<line x1="{chart_x}" y1="{baseline_y}" x2="{chart_x + chart_width}" y2="{baseline_y}" stroke="#bbb" stroke-width="1"/>'
    )
    for tick in range(0, 101, 20):
        x = chart_x + int(chart_width * (tick / 100.0))
        lines.append(
            f'<line x1="{x}" y1="{baseline_y}" x2="{x}" y2="{baseline_y + 6}" stroke="#bbb" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{x}" y="{baseline_y + 22}" font-size="11" fill="#444" text-anchor="middle" font-family="sans-serif">{tick}%</text>'
        )

    # Bars
    for i, (reason, value) in enumerate(items):
        y = y_of(i)
        color = REASON_COLORS.get(reason, "#777777")
        frac = (value / denom) if denom else 0.0
        bar_w = int(round(chart_width * frac))

        # Label
        lines.append(
            f'<text x="{chart_x - 10}" y="{y + bar_height - 6}" font-size="13" fill="#111" text-anchor="end" font-family="sans-serif">{_svg_escape(reason)}</text>'
        )

        # Background bar
        lines.append(
            f'<rect x="{chart_x}" y="{y}" width="{chart_width}" height="{bar_height}" fill="#f5f5f5" stroke="#e0e0e0" stroke-width="1"/>'
        )
        if bar_w > 0:
            lines.append(
                f'<rect x="{chart_x}" y="{y}" width="{bar_w}" height="{bar_height}" fill="{color}"/>'
            )

        percent = f"{(frac * 100.0):.2f}%"
        label = f"{percent} ({value})"
        text_x = min(chart_x + bar_w + 8, chart_x + chart_width + 6)
        anchor = "start" if text_x < (chart_x + chart_width) else "end"
        if anchor == "end":
            text_x = chart_x + chart_width - 6
        lines.append(
            f'<text x="{text_x}" y="{y + bar_height - 6}" font-size="12" fill="#111" text-anchor="{anchor}" font-family="sans-serif">{_svg_escape(label)}</text>'
        )

    if result.missing_reason_columns:
        warn = "missing columns treated as 0: " + ", ".join(result.missing_reason_columns)
        lines.append(
            f'<text x="{left_margin}" y="{height - 14}" font-size="11" fill="#aa0000" font-family="sans-serif">{_svg_escape(warn)}</text>'
        )

    lines.append("</svg>")
    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _require_matplotlib() -> "tuple[Any, Any]":
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore

        return matplotlib, plt
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "PNG output requires matplotlib.\n"
            "Install matplotlib (and numpy if needed) or use --format svg.\n"
            f"Original error: {exc}"
        )


def write_breakdown_png(
    out_png: Path,
    title: str,
    result: BreakdownResult,
    *,
    dpi: int = 120,
    sort: bool = True,
) -> None:
    _, plt = _require_matplotlib()

    denom = result.total_warp_cycles
    if denom <= 0:
        denom = 0

    items = [(reason, result.totals.get(reason, 0)) for reason in result.reasons]
    if sort:
        items.sort(key=lambda item: item[1], reverse=True)

    reasons = [reason for reason, _value in items]
    values = [value for _reason, value in items]
    fracs = [((value / denom) * 100.0) if denom else 0.0 for value in values]

    fig_h = max(2.8, 0.45 * len(items) + 1.4)
    fig_w = 11.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    y = list(range(len(items)))
    colors = [REASON_COLORS.get(reason, "#777777") for reason in reasons]
    ax.barh(y, fracs, color=colors, alpha=0.95)

    ax.set_yticks(y)
    ax.set_yticklabels(reasons)
    ax.invert_yaxis()
    ax.set_xlim(0.0, 100.0)
    ax.set_xlabel("fraction of stall warp cycles (%)")
    ax.grid(True, axis="x", linestyle="--", linewidth=0.6, alpha=0.4)

    for yi, frac, value in zip(y, fracs, values):
        ax.text(
            min(frac + 1.0, 99.0),
            yi,
            f"{frac:.2f}% ({value})",
            va="center",
            ha="left",
            fontsize=9,
            color="#111111",
        )

    fig.suptitle(title, fontsize=14, y=0.98)
    subtitle = (
        f"stall_warp_cycles={result.total_warp_cycles}"
    )
    if result.stall_rows_total:
        subtitle += (
            f"    STALL_rows_used={result.stall_rows_used}/{result.stall_rows_total}"
            f"    zero_count_STALL_rows_skipped={result.stall_rows_zero_counts}"
        )
    ax.set_title(subtitle, fontsize=10, color="#444444")

    if result.missing_reason_columns:
        warn = "missing columns treated as 0: " + ", ".join(result.missing_reason_columns)
        fig.text(0.01, 0.01, warn, fontsize=9, color="#aa0000")

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot stall-reason breakdown (issue-trace or precomputed breakdown CSV)."
    )
    parser.add_argument(
        "issue_csv",
        type=Path,
        help=(
            "Path to either:\n"
            "  - an issue-trace CSV (.csv/.csv.gz/.csv.zst), or\n"
            "  - a precomputed breakdown CSV (stall_reason_breakdown.csv).\n"
        ),
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR}).",
    )
    parser.add_argument(
        "--out-name",
        default=None,
        help="Base output name (default: input stem).",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Plot title (default: derived from input filename).",
    )
    parser.add_argument(
        "--no-sort",
        action="store_true",
        help="Keep reasons in the default order (do not sort by contribution).",
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
        default=120,
        help="PNG DPI (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path: Path = args.issue_csv
    if not csv_path.is_file():
        raise SystemExit(f"input not found: {csv_path}")

    is_issue_trace = _detect_input_is_issue_trace(csv_path)
    result = analyze_issue_trace(csv_path) if is_issue_trace else analyze_breakdown_csv(csv_path)
    stem = args.out_name or csv_path.stem
    out_dir: Path = args.out_dir
    out_csv = out_dir / f"{stem}_stall_breakdown.csv"
    out_svg = out_dir / f"{stem}_stall_breakdown.svg"
    out_png = out_dir / f"{stem}_stall_breakdown.png"
    sort = not args.no_sort

    write_breakdown_csv(out_csv, stem, result, sort=sort)

    if args.title:
        title = args.title
    else:
        title = f"{csv_path.name} stall reason breakdown" if is_issue_trace else f"{stem} stall reason breakdown"
    if args.format in ("svg", "both"):
        write_breakdown_svg(out_svg, title, result, sort=sort)
    if args.format in ("png", "both"):
        write_breakdown_png(out_png, title, result, dpi=args.dpi, sort=sort)

    print(f"input: {csv_path}")
    print(f"output csv: {out_csv}")
    if args.format in ("svg", "both"):
        print(f"output svg: {out_svg}")
    if args.format in ("png", "both"):
        print(f"output png: {out_png}")
    print(f"stall warp cycles: {result.total_warp_cycles}")
    if is_issue_trace:
        print(f"STALL rows used/total: {result.stall_rows_used}/{result.stall_rows_total}")
        if result.stall_rows_zero_counts:
            print(f"skipped STALL rows (all-zero counts): {result.stall_rows_zero_counts}")
        if result.stall_rows_warp_minus1:
            print(f"STALL rows with warp=-1: {result.stall_rows_warp_minus1}")
            if result.stall_rows_warp_minus1_used:
                print(
                    "WARNING: some warp=-1 STALL rows had non-zero counts and were included: "
                    f"{result.stall_rows_warp_minus1_used}"
                )
    if result.missing_reason_columns:
        print("missing columns treated as 0: " + ", ".join(result.missing_reason_columns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
