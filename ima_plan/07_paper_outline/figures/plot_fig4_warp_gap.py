#!/usr/bin/env python3
"""Fig 4: Warp gap chart for §2.3 (The IMA Latency-Hiding Crisis).

For each Gardenia graph algorithm, plot N_required (Little's Law)
against the A100 hardware ceiling of 64 concurrent warps per SM.
Every algorithm exceeds the ceiling by at least 2.5x, demonstrating
that the GPU's warp-parallelism contract is structurally broken
under IMA serial dependency.

Formula:
    N_required = L_chain / C
where
    L_chain ~ 786 cycles (RB-01: weighted average of measured chain
              latencies in BFS/SpMV; 0.75 * 886 + 0.25 * 487)
    C ~ 3-5  cycles (per-iteration loop body length, varies per algo)
"""

import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402

apply_style()

# ── Output paths ────────────────────────────────────────────────────────
OUT_DIR = Path(__file__).resolve().parent
PAPER_FIG_DIR = (_REPO / "ima_plan/07_paper_outline/latex_template"
                 / "figures" / "2-Background_Motivation")

# ── Parameters ──────────────────────────────────────────────────────────
N_MAX = 64  # A100 SM concurrent warp ceiling

# Gardenia 6-algo set, ordered to match §1 narrative
WORKLOADS = {
    "BFS":  {"L_chain": 786, "C": 3},
    "SSSP": {"L_chain": 786, "C": 3},
    "BC":   {"L_chain": 786, "C": 5},
    "CC":   {"L_chain": 786, "C": 3},
    "SpMV": {"L_chain": 786, "C": 4},
    "VC":   {"L_chain": 786, "C": 4},
}


def main():
    names = list(WORKLOADS.keys())
    n_required = [WORKLOADS[n]["L_chain"] / WORKLOADS[n]["C"] for n in names]
    gap_ratio = [n / N_MAX for n in n_required]

    fig, ax = plt.subplots(figsize=(3.5, 1.95), constrained_layout=True)

    x = np.arange(len(names))
    bar_color = CB10[0]  # tableau colorblind blue
    bars = ax.bar(x, n_required, color=bar_color, width=0.55,
                  zorder=3, edgecolor="black", linewidth=0.4)

    # Hardware ceiling line
    ax.axhline(N_MAX, color="#D62728", linestyle="--", linewidth=1.0,
               zorder=4,
               label=r"$N_{\mathrm{max}}=64$ (A100 SM ceiling)")

    # Light red shading above the ceiling = "unhideable" region
    ymax = max(n_required) * 1.22
    ax.axhspan(N_MAX, ymax, color="#D62728", alpha=0.05, zorder=1)

    # Bar value labels: single-line "N (k.x)" — saves vertical headroom
    for i, (n, r) in enumerate(zip(n_required, gap_ratio)):
        ax.text(i, n + 4, f"{int(n)} ({r:.1f}x)",
                ha="center", va="bottom", fontsize=6.0)

    ax.set_xticks(x)
    ax.set_xticklabels(names)
    ax.set_ylabel(r"Required warps $N_{\mathrm{req}}$")
    ax.set_ylim(0, ymax)
    # Legend ABOVE the plot area, not inside — avoids overlap with bar labels
    ax.legend(fontsize=6.0, loc="lower center",
              bbox_to_anchor=(0.5, 1.01), frameon=False,
              handlelength=1.4, handletextpad=0.4)

    # Persist to working dir + paper figure dir
    save_fig(fig, "warp_gap", OUT_DIR)
    save_fig(fig, "warp_gap", PAPER_FIG_DIR)
    plt.close(fig)

    print(f"Saved: {OUT_DIR}/warp_gap.pdf")
    print(f"Saved: {PAPER_FIG_DIR}/warp_gap.pdf")
    print()
    print("Per-algorithm Little's Law gap:")
    for n, nr, r in zip(names, n_required, gap_ratio):
        print(f"  {n:5s}  N_required = {int(nr):3d}   ({r:.1f}x ceiling)")


if __name__ == "__main__":
    main()
