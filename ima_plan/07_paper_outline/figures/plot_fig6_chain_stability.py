#!/usr/bin/env python3
"""Fig 6: IMAD.WIDE chain conformance across GPU generations (§2.5).

Gardenia-only single-column adaptation of RB-02. Shows that for each of
the six Gardenia graph algorithms, the LDG -> IMAD.WIDE -> LDG chain
remains the compiler-preferred form across all six current NVIDIA SM
targets (Volta through Hopper). Five of six exceed 86%; only BC dips
to 78% on SM70/SM80, where nvcc occasionally chooses an alternative
LEA/IADD3 sequence.

Source CSV:
    ima_plan/07_paper_outline/resource_blocks/data/chain_conformance.csv
"""

import csv
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402

apply_style()

# ── Paths ───────────────────────────────────────────────────────────────
DATA_CSV = (_REPO / "ima_plan/07_paper_outline/resource_blocks"
            / "data" / "chain_conformance.csv")
OUT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = (_REPO / "ima_plan/07_paper_outline/latex_template"
                 / "figures" / "2-Background_Motivation")

# ── Config ──────────────────────────────────────────────────────────────
ALGO_ORDER = ["bfs", "sssp", "bc", "cc", "spmv", "vc"]
ALGO_DISPLAY = {"bfs": "BFS", "sssp": "SSSP", "bc": "BC",
                "cc": "CC", "spmv": "SpMV", "vc": "VC"}

SM_ORDER = ["sm70", "sm75", "sm80", "sm86", "sm89", "sm90"]
SM_SHORT = ["70", "75", "80", "86", "89", "90"]
SM_COLORS = [CB10[0], CB10[1], CB10[4], CB10[3], CB10[5], CB10[8]]


def load_gardenia(csv_path):
    """Return {(algo, sm): conformance_percent}."""
    out = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row["suite"] != "gardenia":
                continue
            out[(row["algorithm"], row["sm"])] = float(row["conformance"]) * 100
    return out


def main():
    data = load_gardenia(DATA_CSV)

    n_algo = len(ALGO_ORDER)
    n_sm = len(SM_ORDER)

    fig, ax = plt.subplots(figsize=(3.5, 2.0), constrained_layout=True)

    bar_w = 0.13            # one SM bar width (in algorithm-units)
    group_w = n_sm * bar_w  # = 0.78
    group_gap = 0.40        # gap between algorithm groups
    pitch = group_w + group_gap

    x_centers = np.arange(n_algo) * pitch

    # Plot one set of bars per SM
    for si, sm in enumerate(SM_ORDER):
        xs, vals = [], []
        for ai, algo in enumerate(ALGO_ORDER):
            v = data.get((algo, sm))
            if v is not None:
                xs.append(x_centers[ai] + si * bar_w)
                vals.append(v)
        ax.bar(xs, vals, width=bar_w * 0.92,
               color=SM_COLORS[si], edgecolor="black", linewidth=0.25,
               zorder=3, label=f"SM{SM_SHORT[si]}")

    # 80% reference line — aligned with the labeled "80" y-tick below
    ax.axhline(80, color="#666666", linestyle="--", linewidth=0.7, zorder=2)

    # X axis: algorithm group labels at center of each group
    xticks = [xc + group_w / 2 - bar_w / 2 for xc in x_centers]
    ax.set_xticks(xticks)
    ax.set_xticklabels([ALGO_DISPLAY[a] for a in ALGO_ORDER], fontsize=7)
    ax.tick_params(axis="x", pad=1)

    ax.set_ylabel("IMAD.WIDE chain ratio (%)", fontsize=7)
    ax.set_ylim(0, 116)
    # 80 is a labeled tick AND the dashed reference line position
    ax.set_yticks([0, 25, 50, 80, 100])
    ax.set_xlim(-0.10, x_centers[-1] + group_w + 0.05)

    # Compact legend in two rows of 3 above the plot
    handles = [mpatches.Patch(facecolor=SM_COLORS[i],
                              edgecolor="black", linewidth=0.3,
                              label=f"SM{SM_SHORT[i]}")
               for i in range(n_sm)]
    ax.legend(handles=handles, fontsize=5.8, ncol=6,
              loc="upper center", bbox_to_anchor=(0.5, 1.10),
              frameon=False, columnspacing=0.6,
              handlelength=0.8, handletextpad=0.3)

    save_fig(fig, "chain_stability", OUT_DIR)
    save_fig(fig, "chain_stability", PAPER_FIG_DIR)
    plt.close(fig)

    print(f"Saved: {OUT_DIR}/chain_stability.pdf")
    print(f"Saved: {PAPER_FIG_DIR}/chain_stability.pdf")
    print()
    print("Per-algorithm IMAD.WIDE chain conformance (Gardenia, all SMs):")
    for algo in ALGO_ORDER:
        vs = [data[(algo, sm)] for sm in SM_ORDER if (algo, sm) in data]
        print(f"  {ALGO_DISPLAY[algo]:5s}  "
              f"min={min(vs):5.1f}%  max={max(vs):5.1f}%")


if __name__ == "__main__":
    main()
