#!/usr/bin/env python3
"""Fig 1: L1 Miss Breakdown + IMA Share & Ideal L1D Headroom.

Introduction figure (§1 ¶2). Dual subplot, full-width (7.0").
  (a) Per-algorithm L1 miss rate (stacked: IMA Data / IMA Index / Other)
      + L2 miss rate (separate bar). Sym variants only, median across datasets.
  (b) Per-algorithm Ideal L1D speedup (geomean across datasets).

Data sources:
  (a) resource_blocks/data/cache_ima_breakdown.csv  (RB-03)
  (b) experiment_results.md — Ideal IPC / Base IPC, sym variants
"""

import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# ── Project style ───────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10, COLORS_IMA_ROLE

import matplotlib.pyplot as plt

apply_style()

# ── Paths ───────────────────────────────────────────────────────────────
DATA_CSV = (_REPO / "ima_plan/07_paper_outline/resource_blocks"
            / "data" / "cache_ima_breakdown.csv")
OUT_DIR = Path(__file__).resolve().parent

# ── Config ──────────────────────────────────────────────────────────────
ALGO_ORDER = ["BFS", "SSSP", "BC", "CC", "SpMV", "VC"]
ALGO_MAP = {"bfs": "BFS", "sssp": "SSSP", "bc": "BC",
            "cc": "CC", "spmv": "SpMV", "vc": "VC"}

COL_IMA_DATA  = COLORS_IMA_ROLE["data_load"]   # red
COL_IMA_INDEX = COLORS_IMA_ROLE["index_load"]   # blue
COL_OTHER     = "#CFCFCF"                        # light gray
COL_L2        = CB10[1]                          # orange

# Ideal L1D speedup = Ideal IPC / Base IPC, sym variants only.
# Extracted from experiment_results.md (2026-04-04).
IDEAL_L1D = {
    "BFS":  [1.76, 1.41, 1.49, 1.50, 1.52],   # cit, web, flickr, road, socLJ
    "SSSP": [2.46, 1.46, 1.59, 1.42],           # cit, web, flickr, road
    "BC":   [3.04, 1.78, 1.72, 1.59],           # cit, web, flickr, road
    "CC":   [2.23, 3.29, 2.82, 1.36],           # cit, web, flickr, road
    "SpMV": [2.29, 3.56, 3.20, 2.36, 3.99],    # cit, web, flickr, road, socLJ
    "VC":   [2.03, 2.70, 1.40],                 # cit, web, road
}


# ── Data loading ────────────────────────────────────────────────────────

def load_cache_data_sym(csv_path):
    """Load RB-03 CSV, keep only sym variants."""
    by_algo = defaultdict(list)
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if "_sym" not in row["dataset"]:
                continue
            algo = ALGO_MAP.get(row["algorithm"])
            if algo is None:
                continue
            l1_miss = float(row["l1_miss_rate"])
            l2_miss = float(row["l2_miss_rate"])
            l1_total = int(row["l1_total_misses"])
            idx_miss = int(row["ima_index_misses"])
            dat_miss = int(row["ima_data_misses"])
            other_miss = l1_total - idx_miss - dat_miss

            by_algo[algo].append({
                "l1_miss": l1_miss,
                "l2_miss": l2_miss,
                "ima_data_rate":  dat_miss / l1_total * l1_miss if l1_total else 0,
                "ima_index_rate": idx_miss / l1_total * l1_miss if l1_total else 0,
                "other_rate":     max(0, other_miss) / l1_total * l1_miss if l1_total else 0,
            })
    return by_algo


def geomean(vals):
    return float(np.exp(np.mean(np.log(vals))))


# ── Main ────────────────────────────────────────────────────────────────

def main():
    by_algo = load_cache_data_sym(DATA_CSV)
    algos = [a for a in ALGO_ORDER if a in by_algo]
    n = len(algos)
    x = np.arange(n)

    # ── (a) Per-algo medians ────────────────────────────────────────────
    ima_d, ima_i, other, l2_m = [], [], [], []
    for algo in algos:
        pts = by_algo[algo]
        ima_d.append(np.median([p["ima_data_rate"] for p in pts]) * 100)
        ima_i.append(np.median([p["ima_index_rate"] for p in pts]) * 100)
        other.append(np.median([p["other_rate"] for p in pts]) * 100)
        l2_m.append(np.median([p["l2_miss"] for p in pts]) * 100)

    # ── (b) Per-algo geomean Ideal speedup ──────────────────────────────
    ideal_gm = [geomean(IDEAL_L1D[a]) for a in algos]
    all_vals = [v for a in ALGO_ORDER for v in IDEAL_L1D.get(a, [])]
    overall_gm = geomean(all_vals)

    # ── Figure — single-column vertical stack ─────────────────────────
    fig, (ax_a, ax_b) = plt.subplots(
        2, 1, figsize=(3.5, 4.2),
        constrained_layout=True,
    )

    # ── (a) L1 Miss Breakdown + L2 Miss Rate ───────────────────────────
    bar_w = 0.30
    gap = 0.12
    x_l1 = x - gap / 2 - bar_w / 2
    x_l2 = x + gap / 2 + bar_w / 2

    # Solid fills only — colors are sufficiently distinct in grayscale:
    # Red ~40% gray, Blue ~35%, Light gray ~80%, Orange ~50%
    ax_a.bar(x_l1, ima_d, bar_w, color=COL_IMA_DATA, edgecolor="black",
             linewidth=0.4, label="IMA Data Miss")
    ax_a.bar(x_l1, ima_i, bar_w, bottom=ima_d, color=COL_IMA_INDEX,
             edgecolor="black", linewidth=0.4, label="IMA Index Miss")
    ax_a.bar(x_l1, other, bar_w, bottom=[d + i for d, i in zip(ima_d, ima_i)],
             color=COL_OTHER, edgecolor="black", linewidth=0.4,
             label="Other Miss")
    ax_a.bar(x_l2, l2_m, bar_w, color=COL_L2, edgecolor="black",
             linewidth=0.4, label="L2 Miss Rate")

    ax_a.set_ylabel("Miss Rate (%)")
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(algos)
    ax_a.set_ylim(0, 70)
    ax_a.legend(fontsize=6, loc="upper right", ncol=2,
                handlelength=1.2, handletextpad=0.4, columnspacing=0.8)
    # Subtitle below x-axis (not above)
    ax_a.set_xlabel("(a) L1 Miss Breakdown vs. L2 Miss Rate",
                     fontsize=9, labelpad=6)

    # ── (b) Ideal L1D Speedup ──────────────────────────────────────────
    ax_b.bar(x, ideal_gm, 0.55, color=CB10[0], edgecolor="black", linewidth=0.4)

    # Geomean line — label at left. 2-decimal precision is required: BC
    # (1.96), VC (1.97), and the overall geomean (2.04) all round to "2.0"
    # at 1 decimal, which makes the dashed line appear misaligned with the
    # BC/VC bars that display identical labels. 2 decimals exposes the real
    # ordering (BC/VC are below geomean; CC/SpMV are above).
    ax_b.axhline(y=overall_gm, color="gray", linestyle="--", linewidth=0.8)
    ax_b.annotate(
        f"Geomean: {overall_gm:.2f}\u00d7",
        xy=(0.03, overall_gm), xycoords=("axes fraction", "data"),
        fontsize=6.5, va="bottom", ha="left", color="gray",
    )

    # 1.0× baseline
    ax_b.axhline(y=1.0, color="black", linestyle=":", linewidth=0.5, alpha=0.3)

    # Bar value labels — push near-geomean labels above the dashed line
    for i, v in enumerate(ideal_gm):
        offset = 0.06 if abs(v - overall_gm) >= 0.15 else 0.12
        ax_b.text(i, v + offset, f"{v:.2f}\u00d7",
                  ha="center", va="bottom", fontsize=6.5)

    ax_b.set_ylabel("Ideal L1D Speedup (\u00d7)")
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(algos)
    ax_b.set_ylim(0, 3.8)
    # Subtitle below x-axis (not above)
    ax_b.set_xlabel("(b) Ideal L1D Headroom",
                     fontsize=9, labelpad=6)

    # ── Save ────────────────────────────────────────────────────────────
    # Working copy (figures/ for iteration)
    save_fig(fig, "fig1_cache_ima_ideal", OUT_DIR)
    # Paper copy (latex_template/figures/ for final compilation)
    paper_fig_dir = _REPO / "ima_plan/07_paper_outline/latex_template/figures"
    save_fig(fig, "fig1_cache_ima_ideal", paper_fig_dir)
    plt.close(fig)

    # ── Summary for verification ────────────────────────────────────────
    print(f"Saved: {OUT_DIR}/fig1_cache_ima_ideal.pdf + .svg")
    print(f"\n§1 text numbers (sym-only, per-algo median):")
    print(f"  L1 miss range:  {min(d+i+o for d,i,o in zip(ima_d,ima_i,other)):.0f}"
          f"–{max(d+i+o for d,i,o in zip(ima_d,ima_i,other)):.0f}%")
    print(f"  L2 miss range:  {min(l2_m):.0f}–{max(l2_m):.0f}%"
          f"  →  L2 hit: {100-max(l2_m):.0f}–{100-min(l2_m):.0f}%")
    all_ima_pct = [(d+i)/(d+i+o)*100 for d,i,o in zip(ima_d,ima_i,other) if d+i+o > 0]
    print(f"  IMA share range: {min(all_ima_pct):.0f}–{max(all_ima_pct):.0f}%")
    print(f"  Ideal L1D geomean: {overall_gm:.2f}× (n={len(all_vals)})")
    print(f"  Ideal L1D range:   {min(all_vals):.1f}×–{max(all_vals):.1f}×")


if __name__ == "__main__":
    main()
