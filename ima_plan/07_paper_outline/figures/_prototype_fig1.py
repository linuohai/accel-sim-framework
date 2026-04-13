#!/usr/bin/env python3
"""[PROTOTYPE v2] Fig 1: L1/L2 Cache + IMA Breakdown & Ideal L1D Speedup
双子图 — sym-only, geomean, no scatter.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10, COLORS_IMA_ROLE

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

apply_style()

# ── Constants ───────────────────────────────────────────────────────────
DATA_CSV = _REPO / "ima_plan/07_paper_outline/resource_blocks/data/cache_ima_breakdown.csv"
OUT_DIR = Path(__file__).resolve().parent

ALGO_ORDER = ["BFS", "SSSP", "BC", "CC", "SpMV", "VC"]
ALGO_MAP = {"bfs": "BFS", "sssp": "SSSP", "bc": "BC",
            "cc": "CC", "spmv": "SpMV", "vc": "VC"}

COL_DATA  = COLORS_IMA_ROLE["data_load"]
COL_INDEX = COLORS_IMA_ROLE["index_load"]
COL_OTHER = "#CFCFCF"
COL_L2    = CB10[1]           # orange — distinct from red/blue/gray

# ── Ideal L1D data (experiment_results.md, sym variants only) ───────────
IDEAL_DATA = {
    "BFS":  [1.76, 1.41, 1.49, 1.50, 1.52],   # cit, web, flickr, road, socLJ
    "SSSP": [2.46, 1.46, 1.59, 1.42],           # cit, web, flickr, road
    "BC":   [3.04, 1.78, 1.72, 1.59],           # cit, web, flickr, road
    "CC":   [2.23, 3.29, 2.82, 1.36],           # cit, web, flickr, road
    "SpMV": [2.29, 3.56, 3.20, 2.36, 3.99],    # cit, web, flickr, road, socLJ
    "VC":   [2.03, 2.70, 1.40],                 # cit, web, road
}


def load_cache_data_sym_only(csv_path):
    """Load CSV, keep only sym variants."""
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

            ima_data_rate = dat_miss / l1_total * l1_miss if l1_total else 0
            ima_index_rate = idx_miss / l1_total * l1_miss if l1_total else 0
            other_rate = max(0, other_miss) / l1_total * l1_miss if l1_total else 0

            by_algo[algo].append({
                "l1_miss": l1_miss, "l2_miss": l2_miss,
                "ima_data_rate": ima_data_rate,
                "ima_index_rate": ima_index_rate,
                "other_rate": other_rate,
            })
    return by_algo


def geomean(vals):
    return np.exp(np.mean(np.log(vals)))


def main():
    by_algo = load_cache_data_sym_only(DATA_CSV)
    algos = [a for a in ALGO_ORDER if a in by_algo]

    # ── Compute medians for subplot (a) ─────────────────────────────────
    med_data = []
    for algo in algos:
        pts = by_algo[algo]
        med_data.append({
            "ima_data":  np.median([p["ima_data_rate"] for p in pts]) * 100,
            "ima_index": np.median([p["ima_index_rate"] for p in pts]) * 100,
            "other":     np.median([p["other_rate"] for p in pts]) * 100,
            "l2_miss":   np.median([p["l2_miss"] for p in pts]) * 100,
        })

    # ── Compute per-algo geomean for subplot (b) ───────────────────────
    ideal_gm = []
    for algo in algos:
        vals = IDEAL_DATA.get(algo, [])
        ideal_gm.append(geomean(vals) if vals else 0)

    # Overall geomean across all sym workloads
    all_vals = [v for algo in ALGO_ORDER for v in IDEAL_DATA.get(algo, [])]
    overall_gm = geomean(all_vals)

    # ── Figure: dual subplot ────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.7),
                                    gridspec_kw={"width_ratios": [1.15, 1]},
                                    constrained_layout=True)

    x = np.arange(len(algos))

    # ── Subplot (a): L1 Miss Breakdown + L2 Miss Rate ──────────────────
    bar_w = 0.30
    gap = 0.12

    ima_d = [m["ima_data"] for m in med_data]
    ima_i = [m["ima_index"] for m in med_data]
    other = [m["other"] for m in med_data]
    l2_m  = [m["l2_miss"] for m in med_data]

    x_l1 = x - gap/2 - bar_w/2
    x_l2 = x + gap/2 + bar_w/2

    # Stacked L1 bars
    ax1.bar(x_l1, ima_d, bar_w, color=COL_DATA, edgecolor="black", linewidth=0.4,
            label="IMA Data Miss")
    ax1.bar(x_l1, ima_i, bar_w, bottom=ima_d, color=COL_INDEX,
            edgecolor="black", linewidth=0.4, label="IMA Index Miss")
    ax1.bar(x_l1, other, bar_w,
            bottom=[d+i for d,i in zip(ima_d, ima_i)], color=COL_OTHER,
            edgecolor="black", linewidth=0.4, label="Other Miss")

    # L2 miss rate bars
    ax1.bar(x_l2, l2_m, bar_w, color=COL_L2, edgecolor="black",
            linewidth=0.4, label="L2 Miss Rate")

    ax1.set_ylabel("Miss Rate (%)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(algos)
    ax1.set_ylim(0, 80)
    ax1.legend(fontsize=6, loc="upper right", ncol=2,
               handlelength=1.2, handletextpad=0.4, columnspacing=0.8)
    ax1.set_title("(a) L1 Miss Breakdown vs. L2 Miss Rate", fontsize=8, pad=4)

    # ── Subplot (b): Ideal L1D Speedup (geomean per algo) ──────────────
    bars = ax2.bar(x, ideal_gm, 0.55, color=CB10[0], edgecolor="black", linewidth=0.4)

    # Overall geomean line
    ax2.axhline(y=overall_gm, color="gray", linestyle="--", linewidth=0.8)
    # Place geomean label at left to avoid overlap with bar labels
    ax2.annotate(f"Geomean: {overall_gm:.1f}×",
                 xy=(0.03, overall_gm), xycoords=("axes fraction", "data"),
                 fontsize=6.5, va="bottom", ha="left", color="gray")

    # 1.0× baseline
    ax2.axhline(y=1.0, color="black", linestyle=":", linewidth=0.5, alpha=0.3)

    # Bar value labels — offset those near geomean line to avoid overlap
    for i, v in enumerate(ideal_gm):
        offset = 0.06
        # Push label higher if it would overlap with geomean line annotation
        if abs(v - overall_gm) < 0.15:
            offset = 0.12
        ax2.text(i, v + offset, f"{v:.1f}×", ha="center", va="bottom", fontsize=6.5)

    ax2.set_ylabel("Ideal L1D Speedup (×)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(algos)
    ax2.set_ylim(0, 3.8)
    ax2.set_title("(b) Ideal L1D Headroom", fontsize=8, pad=4)

    # ── Save ────────────────────────────────────────────────────────────
    fig.suptitle("[PROTOTYPE v2] Fig 1 — Introduction", fontsize=9, y=1.02)
    save_fig(fig, "_prototype_fig1", OUT_DIR)
    plt.close(fig)

    # ── Print summary stats for paper text ──────────────────────────────
    print(f"Saved to {OUT_DIR}/_prototype_fig1.pdf + .svg\n")
    print("=== Per-algo medians (sym-only, for §1 text) ===")
    for i, algo in enumerate(algos):
        l1_total = med_data[i]["ima_data"] + med_data[i]["ima_index"] + med_data[i]["other"]
        ima_pct = (med_data[i]["ima_data"] + med_data[i]["ima_index"]) / l1_total * 100 if l1_total else 0
        print(f"  {algo:5s}: L1 miss={l1_total:5.1f}%  L2 miss={med_data[i]['l2_miss']:5.1f}%  "
              f"IMA share={ima_pct:5.1f}%  Ideal={ideal_gm[i]:.2f}×")
    print(f"\n  L1 miss range: {min(m['ima_data']+m['ima_index']+m['other'] for m in med_data):.0f}"
          f"–{max(m['ima_data']+m['ima_index']+m['other'] for m in med_data):.0f}%")
    all_l2 = [m["l2_miss"] for m in med_data]
    print(f"  L2 miss range: {min(all_l2):.0f}–{max(all_l2):.0f}%  →  L2 hit: {100-max(all_l2):.0f}–{100-min(all_l2):.0f}%")
    all_ima = [(m["ima_data"]+m["ima_index"])/(m["ima_data"]+m["ima_index"]+m["other"])*100
               for m in med_data if (m["ima_data"]+m["ima_index"]+m["other"]) > 0]
    print(f"  IMA share range: {min(all_ima):.0f}–{max(all_ima):.0f}%")
    print(f"  Ideal L1D overall geomean: {overall_gm:.2f}× (n={len(all_vals)} sym workloads)")
    print(f"  Ideal L1D range: {min(all_vals):.1f}×–{max(all_vals):.1f}×")


if __name__ == "__main__":
    main()
