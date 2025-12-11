#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

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


def plot_timeline(sm_warp_cycles, out_path: Path, title: str = None, max_y_labels: int = 40):
    if not sm_warp_cycles:
        print("No data to plot.")
        return

    mapping, sorted_pairs = build_axis_mapping(sm_warp_cycles.keys())

    xs = []
    ys = []
    for pair, cycles in sm_warp_cycles.items():
        y = mapping[pair]
        xs.extend(cycles)
        ys.extend([y] * len(cycles))

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.scatter(xs, ys, s=1, marker="s")

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
    title = f"{csv_path.name} SM/warp timeline"
    plot_timeline(sm_warp_cycles, out_path, title, max_y_labels=args.max_y_labels)


if __name__ == "__main__":
    main()
