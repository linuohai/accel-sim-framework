#!/usr/bin/env python3
"""Round-3 Reduce Variant V3: Index Coverage — statistical aggregation.

Box plot per algorithm group (BFS, SSSP, BC, CC, SpMV, VC, Ext.) showing
the distribution of Index Coverage % across each algorithm's datasets.
Individual workloads are overlaid as scattered points (with horizontal
jitter) so the reader can still see every data point.

Box-plot anatomy:
    box edges   : Q1 (25th pct) / Q3 (75th pct)
    inside line : median
    diamond     : mean
    whiskers    : min / max (boxplot default = 1.5 * IQR)
    scatter     : individual workloads, jittered around the box centre

This is the most condensed view: 7 boxes summarise 27 workloads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Project plot style ──────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (                                              # noqa: E402
    apply_style,
    save_fig,
    subplot_label,
    PALETTE_JEWEL,
)
from workload_names import ALG_GROUPS                                # noqa: E402

apply_style()
import matplotlib.pyplot as plt                                      # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"

# Deterministic jitter for the scatter overlay
RNG = np.random.default_rng(seed=20260407)


# ── Load & compute ─────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]


def idx_coverage(key: str):
    rec = DATA.get(key)
    if rec is None:
        return None
    base = rec.get("baseline") or {}
    g = rec.get("grasp") or {}
    bm = base.get("ima_idx_misses")
    gm = g.get("ima_idx_misses")
    if bm is None or gm is None or bm == 0:
        return None
    return (bm - gm) / bm * 100.0


# Build per-algorithm value lists.  MST is excluded (no IMA chain) which is
# the same convention used by ORDERED_27.
data_by_alg: dict[str, list[float]] = {}
for alg_label, wkls in ALG_GROUPS:
    cleaned = [w for w in wkls if w != "ls_mst_rmat12"]
    values = [idx_coverage(w) for w in cleaned]
    values = [v for v in values if v is not None]
    if values:
        data_by_alg[alg_label] = values

algs = list(data_by_alg.keys())
boxes = [data_by_alg[a] for a in algs]


# ── Plot ───────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.0, 2.2), constrained_layout=True)

bp = ax.boxplot(
    boxes,
    tick_labels=algs,
    showmeans=True,
    meanline=False,
    meanprops={
        "marker": "D",
        "markerfacecolor": PALETTE_JEWEL[0],
        "markeredgecolor": "black",
        "markersize": 5,
    },
    boxprops={
        "facecolor": PALETTE_JEWEL[0],
        "alpha": 0.4,
        "edgecolor": "black",
        "linewidth": 0.8,
    },
    medianprops={"color": "black", "linewidth": 1.0},
    whiskerprops={"color": "black", "linewidth": 0.6},
    capprops={"color": "black", "linewidth": 0.6},
    flierprops={
        "marker": "o",
        "markerfacecolor": "white",
        "markeredgecolor": "black",
        "markersize": 3,
        "alpha": 0.7,
    },
    patch_artist=True,
    widths=0.6,
)

# Overlay individual workloads as scatter (with jitter), one box at a time
for i, (_alg, values) in enumerate(data_by_alg.items()):
    centre = i + 1                                          # boxplot is 1-indexed
    jitter = RNG.uniform(-0.15, 0.15, size=len(values))
    xs = centre + jitter
    ax.scatter(
        xs, values,
        s=12, color="black", alpha=0.55, zorder=4,
        edgecolor="none",
    )

# Reference line at 0 % (any negative coverage = GRASP regression)
ax.axhline(0, color="gray", linestyle=":", linewidth=0.6, zorder=1)

# Overall mean across all 27 workloads (sanity reference).  The label
# is anchored above the BC box (column 3) where there is plenty of empty
# space — the right-hand side is occupied by the wide CC and Ext boxes.
all_values = [v for vs in data_by_alg.values() for v in vs]
overall_mean = float(np.mean(all_values))
ax.axhline(
    overall_mean, color="#C85200", linestyle="--",
    linewidth=0.9, alpha=0.9, zorder=2,
)
ax.text(
    3.0, overall_mean + 1.2,
    f"avg = {overall_mean:.1f}%",
    ha="center", va="bottom",
    fontsize=6.5, color="#C85200", zorder=5,
)

# Axes formatting
ax.set_ylabel("Index Coverage (%)", fontsize=7)
ax.set_ylim(-5, 50)
ax.set_yticks([0, 10, 20, 30, 40, 50])
ax.tick_params(axis="x", labelsize=7)
ax.tick_params(axis="y", labelsize=7)

# Subplot label BELOW
subplot_label(ax, "(c) Distribution by algorithm (box plot)", y=-0.32)

save_fig(fig, "proto_r3_reduce_v3_stats", OUT_DIR)
plt.close(fig)

# ── Report ─────────────────────────────────────────────────────────────────
print(f"Saved: {OUT_DIR}/proto_r3_reduce_v3_stats.{{pdf,svg}}")
print(f"overall mean across 27 workloads = {overall_mean:.2f}%\n")
print(f"{'Alg':<6} {'n':>3}  {'mean':>7}  {'median':>7}  {'min':>7}  {'max':>7}")
for alg, vs in data_by_alg.items():
    arr = np.array(vs)
    print(f"{alg:<6} {len(arr):>3}  "
          f"{arr.mean():>6.2f}%  "
          f"{np.median(arr):>6.2f}%  "
          f"{arr.min():>6.2f}%  "
          f"{arr.max():>6.2f}%")
