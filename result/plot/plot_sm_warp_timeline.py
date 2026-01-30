#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np


def parse_issue_trace(path: Path):
    sm_warp_cycles = {}
    with path.open() as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        has_cycles_list = "cycles" in fieldnames
        has_cycle_single = "cycle" in fieldnames
        for row in reader:
            try:
                sm = int(row["sm"])
                warp = int(row["warp"])
            except (KeyError, ValueError):
                continue
            cycles = []
            if has_cycles_list:
                cycles_field = row.get("cycles", "")
                if not cycles_field:
                    continue
                try:
                    cycles = [int(c) for c in cycles_field.split(";") if c]
                except ValueError:
                    continue
            elif has_cycle_single:
                cycle_str = row.get("cycle", "")
                if not cycle_str:
                    continue
                try:
                    cycle = int(cycle_str)
                except ValueError:
                    continue
                event = row.get("event", "")
                if event and event.upper() != "ISSUE":
                    continue
                cycles = [cycle]
            else:
                continue
            if not cycles:
                continue
            key = (sm, warp)
            existing = sm_warp_cycles.get(key)
            if existing is None:
                sm_warp_cycles[key] = set(cycles)
            else:
                existing.update(cycles)
    # convert sets to sorted lists
    return {k: sorted(v) for k, v in sm_warp_cycles.items()}


def build_axis_mapping(pairs):
    sorted_pairs = sorted(pairs)
    mapping = {pair: idx for idx, pair in enumerate(sorted_pairs)}
    return mapping, sorted_pairs


def plot_timeline(
    sm_warp_cycles,
    out_path: Path,
    title: str = None,
    max_y_labels: int = 40,
    fig_width: float = 12.0,
    fig_height: float = 8.0,
    color_by="occupancy",
    colormap=None,
    marker_size: float = 1.0,
    alpha: float = 0.6,
    row_stripes: bool = True,
    stripe_color: str = "#f0f0f0",
    stripe_alpha: float = 0.08,
    max_stripe_rows: int = 2000,
):
    if not sm_warp_cycles:
        print("No data to plot.")
        return

    mapping, sorted_pairs = build_axis_mapping(sm_warp_cycles.keys())

    xs = []
    ys = []
    cs = []
    if color_by == "occupancy":
        counts = {pair: len(cycles) for pair, cycles in sm_warp_cycles.items()}
        for pair, cycles in sm_warp_cycles.items():
            y = mapping[pair]
            xs.extend(cycles)
            ys.extend([y] * len(cycles))
            cs.extend([counts[pair]] * len(cycles))
        cbar_label = "Active cycles per (SM, warp)"
        default_cmap = "cividis"
    elif color_by == "cycle":
        for pair, cycles in sm_warp_cycles.items():
            y = mapping[pair]
            xs.extend(cycles)
            ys.extend([y] * len(cycles))
            cs.extend(cycles)
        cbar_label = "Cycle"
        default_cmap = "viridis"
    else:
        raise ValueError(f"Unsupported color_by: {color_by}")

    xs = np.asarray(xs)
    ys = np.asarray(ys)
    cs = np.asarray(cs)
    if colormap is None:
        colormap = default_cmap
    vmin = float(np.min(cs)) if cs.size else 0.0
    vmax = float(np.max(cs)) if cs.size else 1.0
    if vmin == vmax:
        vmin = 0.0
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    if row_stripes and len(sorted_pairs) <= max_stripe_rows:
        for idx in range(0, len(sorted_pairs), 2):
            ax.axhspan(
                idx - 0.5,
                idx + 0.5,
                facecolor=stripe_color,
                alpha=stripe_alpha,
                zorder=0,
            )

    scatter = ax.scatter(
        xs,
        ys,
        s=marker_size,
        marker="s",
        c=cs,
        cmap=colormap,
        norm=norm,
        alpha=alpha,
        linewidths=0,
        zorder=2,
    )
    cbar = fig.colorbar(scatter, ax=ax, pad=0.01)
    cbar.set_label(cbar_label)

    ax.set_xlabel("Cycle")
    ax.set_ylabel("(SM, warp)")
    if title:
        ax.set_title(title)

    # y-axis ticks: show a subset to avoid clutter,
    # but try to cover different warps as well.
    if max_y_labels and max_y_labels > 0:
        n_pairs = len(sorted_pairs)
        from collections import Counter

        # approximate warps-per-SM to avoid aligning all ticks to the same warp
        counts_per_sm = Counter()
        for sm, warp in sorted_pairs:
            counts_per_sm[sm] += 1
        approx_warps_per_sm = 0
        if counts_per_sm:
            approx_warps_per_sm = max(
                1, int(round(sum(counts_per_sm.values()) / len(counts_per_sm)))
            )

        step = max(1, n_pairs // max_y_labels)
        if approx_warps_per_sm and step % approx_warps_per_sm == 0:
            step += 1

        yticks_idx = list(range(0, n_pairs, step))
        ax.set_yticks(yticks_idx)
        ax.set_yticklabels(
            [f"SM{sm},W{warp}" for (sm, warp) in (sorted_pairs[i] for i in yticks_idx)]
        )

    ax.set_ylim(-0.5, len(sorted_pairs) - 0.5)
    fig.tight_layout()
    fig.savefig(out_path)
    print(f"Saved figure to {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Plot per-(SM, warp) execution cycles from an "
            "issue+L1 trace CSV file."
        )
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("result/issue_trace/btree_issue_with_l1trace_shadow_accesses.csv"),
        help=(
            "Path to issue+L1 trace CSV (relative to the current working "
            "directory)."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        help=(
            "Output image path (relative to the current working directory). "
            "If omitted, it is derived from the CSV name and placed under "
            "result/plot/output/."
        ),
    )
    parser.add_argument(
        "--max-y-labels",
        type=int,
        default=40,
        help=(
            "Maximum number of (SM, warp) tick labels shown on the y-axis. "
            "Larger values show more labels but can clutter the plot."
        ),
    )
    parser.add_argument(
        "--fig-width",
        type=float,
        default=12.0,
        help=(
            "Matplotlib figure width in inches. Increase to stretch the plot "
            "horizontally when cycles span a long range."
        ),
    )
    parser.add_argument(
        "--fig-height",
        type=float,
        default=8.0,
        help=(
            "Matplotlib figure height in inches. Increase to spread out "
            "(SM, warp) rows vertically."
        ),
    )
    parser.add_argument(
        "--color-by",
        choices=("occupancy", "cycle"),
        default="occupancy",
        help=(
            "Color encoding strategy: 'occupancy' colors by total active cycles per "
            "(SM, warp), while 'cycle' colors by the cycle value itself."
        ),
    )
    parser.add_argument(
        "--colormap",
        default=None,
        help=(
            "Matplotlib colormap name. If omitted, a sensible default is chosen "
            "based on --color-by."
        ),
    )
    parser.add_argument(
        "--marker-size",
        type=float,
        default=1.0,
        help="Marker size for each cycle point.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.6,
        help="Marker transparency for dense plots.",
    )
    row_stripes_group = parser.add_mutually_exclusive_group()
    row_stripes_group.add_argument(
        "--row-stripes",
        dest="row_stripes",
        action="store_true",
        default=True,
        help="Enable alternating row stripes to improve readability.",
    )
    row_stripes_group.add_argument(
        "--no-row-stripes",
        dest="row_stripes",
        action="store_false",
        help="Disable alternating row stripes.",
    )
    parser.add_argument(
        "--stripe-color",
        default="#f0f0f0",
        help="Stripe background color for alternating rows.",
    )
    parser.add_argument(
        "--stripe-alpha",
        type=float,
        default=0.08,
        help="Stripe transparency for alternating rows.",
    )
    parser.add_argument(
        "--max-stripe-rows",
        type=int,
        default=2000,
        help=(
            "Maximum number of (SM, warp) rows before row stripes are disabled "
            "to avoid slow rendering."
        ),
    )
    auto_height_group = parser.add_mutually_exclusive_group()
    auto_height_group.add_argument(
        "--auto-height",
        dest="auto_height",
        action="store_true",
        default=True,
        help=(
            "Automatically scale the figure height based on how many (SM, warp) "
            "pairs are present (default: enabled). The computed value never goes "
            "below --fig-height and is capped to avoid overly tall plots."
        ),
    )
    auto_height_group.add_argument(
        "--no-auto-height",
        dest="auto_height",
        action="store_false",
        help="Disable automatic figure height scaling.",
    )
    args = parser.parse_args()

    csv_path = args.csv
    if args.out is not None:
        out_path = args.out
    else:
        # Default output: result/plot/output/<csv_stem>_sm_warp_timeline.png
        out_dir = Path("result/plot/output")
        out_path = out_dir / f"{csv_path.stem}_sm_warp_timeline.png"

    if not csv_path.is_file():
        print(f"Input CSV not found: {csv_path}")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)

    sm_warp_cycles = parse_issue_trace(csv_path)
    n_pairs = len(sm_warp_cycles)
    fig_height = args.fig_height
    if args.auto_height and n_pairs:
        fig_height = max(fig_height, min(32.0, 4.0 + 0.08 * n_pairs))
    fig_width = args.fig_width
    title = f"{csv_path.name} SM/warp timeline"
    plot_timeline(
        sm_warp_cycles,
        out_path,
        title,
        max_y_labels=args.max_y_labels,
        fig_width=fig_width,
        fig_height=fig_height,
        color_by=args.color_by,
        colormap=args.colormap,
        marker_size=args.marker_size,
        alpha=args.alpha,
        row_stripes=args.row_stripes,
        stripe_color=args.stripe_color,
        stripe_alpha=args.stripe_alpha,
        max_stripe_rows=args.max_stripe_rows,
    )


if __name__ == "__main__":
    main()
