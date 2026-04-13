#!/usr/bin/env python3
"""
Round 4 §5.4 Layout C (ablation panel): single-column component ablation.

Single grouped bar chart, x = 8 representative workloads + GMEAN, three
schemes per workload:
  - Index-Only  (IPU only, no DPU)
  - Data-Only   (DPU only, no IPU)
  - Full GRASP  (this work — IPU + DPU + Throttle)

This is the companion to proto_r4_54_C_sens.py — together they form Layout C
of §5.4 by separating sensitivity (1x3 row) from ablation (1x1 single column),
trading composite-figure cost for paragraph-level placement flexibility.

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT (greens/reds/purples) — no blue/orange
  - HATCHES_DENSE for B&W readability
  - GRASP / Full GRASP = green palette[0] + solid HATCHES_DENSE[0]
  - Single panel — no subplot label needed
  - Tight y-axis with the GMEAN bar separator
  - Path depth: parents[5]
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

# round4/ is 5 levels deep from repo root
_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, figsize_col, save_fig,
    PALETTE_TOL_BRIGHT, HATCHES_DENSE,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── 8 Representative Workloads ───────────────────────────────────────────────
WORKLOADS = [
    "bfs_cit_dir", "sssp_cit_dir", "bc_cit_dir", "spmv_web_sym",
    "bfs_web_sym", "cc_flickr_sym", "spmv_flickr_sym", "bfs_flickr_sym",
]
SHORT = ["BFS-cp", "SSSP-cp", "BC-cp", "SpM-wg",
         "BFS-wg", "CC-fl", "SpM-fl", "BFS-fl"]


# ── Baseline IPC ─────────────────────────────────────────────────────────────
BASELINE_IPC = {
    "bfs_cit_dir":     5.3349,
    "sssp_cit_dir":    5.9499,
    "bc_cit_dir":      95.2826,
    "spmv_web_sym":    129.6846,
    "bfs_web_sym":     7.3528,
    "cc_flickr_sym":   46.8674,
    "spmv_flickr_sym": 79.2566,
    "bfs_flickr_sym":  9.7943,
}


# ── Exp-A: Component Ablation IPC (Index-Only, Data-Only, Full GRASP) ───────
ABLATION_IPC = {
    "bfs_cit_dir":     (5.5220,   5.8772,   6.0830),
    "sssp_cit_dir":    (6.0955,   6.5705,   6.5949),
    "bc_cit_dir":      (97.1852,  102.9133, 104.6244),
    "spmv_web_sym":    (158.6675, 130.3898, 181.8048),
    "bfs_web_sym":     (7.8197,   10.5485,  11.4819),
    "cc_flickr_sym":   (64.1420,  71.9062,  94.8873),
    "spmv_flickr_sym": (97.0964,  86.0611,  109.2283),
    "bfs_flickr_sym":  (10.8845,  11.1063,  12.4611),
}


# ── Helpers ─────────────────────────────────────────────────────────────────
def ipc_to_speedup_pct(ipc, base):
    return (ipc - base) / base * 100.0


def gmean_pct(arr):
    """Geometric mean of (1+x/100) - 1, in percentage points."""
    ratios = 1.0 + arr / 100.0
    return (float(np.exp(np.mean(np.log(ratios)))) - 1.0) * 100.0


# Build per-scheme arrays in WORKLOAD order
ablation_pct = {
    wl: tuple(ipc_to_speedup_pct(v, BASELINE_IPC[wl])
              for v in ABLATION_IPC[wl])
    for wl in WORKLOADS
}
index_only = np.array([ablation_pct[wl][0] for wl in WORKLOADS])
data_only  = np.array([ablation_pct[wl][1] for wl in WORKLOADS])
full_grasp = np.array([ablation_pct[wl][2] for wl in WORKLOADS])

gm_index = gmean_pct(index_only)
gm_data  = gmean_pct(data_only)
gm_full  = gmean_pct(full_grasp)

# Append GMEAN as last x-column
index_all = np.append(index_only, gm_index)
data_all  = np.append(data_only,  gm_data)
full_all  = np.append(full_grasp, gm_full)
labels_all = SHORT + ["GMEAN"]


# ── Build Figure (single-column, slightly taller) ───────────────────────────
fig, ax = plt.subplots(
    figsize=figsize_col(aspect=0.78),  # ~3.5 x 2.7
    constrained_layout=True,
)

GMEAN_GAP = 0.55
n_total = len(labels_all)
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.27
n_groups = 3

schemes = [
    ("Index-Only", index_all, PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),  # red
    ("Data-Only",  data_all,  PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),  # purple
    ("Full GRASP", full_all,  PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),  # green solid
]

for i, (label, vals, color, hatch) in enumerate(schemes):
    offset = (i - (n_groups - 1) / 2) * bar_w
    ax.bar(
        x + offset, vals, bar_w,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        label=label, zorder=3,
    )

ax.axhline(0, color="black", linewidth=0.6, zorder=2)

# GMEAN separator
gmean_sep_x = (len(SHORT) - 1) + (1 + GMEAN_GAP) / 2.0
ax.axvline(gmean_sep_x, color="black", linestyle="-",
           linewidth=0.7, alpha=0.7, zorder=1)

# Tight y-axis: data range -1 to 102%, leave headroom for legend
ax.set_ylim(-5, 130)
ax.set_yticks([0, 30, 60, 90, 120])

ax.set_xticks(x)
ax.set_xticklabels(labels_all, rotation=45, ha="right", fontsize=6.5)
ax.set_ylabel("Speedup over No-PF (%)", fontsize=7.5)
ax.tick_params(axis="y", labelsize=7)
ax.set_xlim(-0.7, x[-1] + 0.7)

# Legend with inline GMEANs
legend_patches = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black",
          hatch=HATCHES_DENSE[1], linewidth=0.4,
          label=f"Index-Only ({gm_index:+.1f}%)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[2], edgecolor="black",
          hatch=HATCHES_DENSE[2], linewidth=0.4,
          label=f"Data-Only ({gm_data:+.1f}%)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black",
          hatch=HATCHES_DENSE[0], linewidth=0.4,
          label=f"Full GRASP ({gm_full:+.1f}%)"),
]
ax.legend(
    handles=legend_patches, ncol=1, fontsize=6.0,
    loc="upper left", bbox_to_anchor=(0.0, 1.0),
    frameon=True, framealpha=0.92,
    handlelength=1.4, columnspacing=0.9,
    handletextpad=0.4, labelspacing=0.3,
    borderaxespad=0.4,
)

# Axis title (single panel — no subplot label needed)
ax.set_title("Component Ablation: IPC Speedup vs Baseline",
             fontsize=8, pad=4)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_C_abl", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.4 Layout C (ablation panel) — single column ===")
print()
print("Per-workload speedup (%):")
print(f"  {'Workload':<10s}  {'Index':>8s}  {'Data':>8s}  {'Full':>8s}  Synergy")
for wl, sl in zip(WORKLOADS, SHORT):
    iv, dv, fv = ablation_pct[wl]
    syn = fv - iv - dv
    print(f"  {sl:<10s}  {iv:+7.1f}%  {dv:+7.1f}%  {fv:+7.1f}%  {syn:+5.1f}pp")
print()
print(f"GMEAN (geometric):")
print(f"  Index-Only  {gm_index:+6.2f}%")
print(f"  Data-Only   {gm_data:+6.2f}%")
print(f"  Full GRASP  {gm_full:+6.2f}%")
print(f"  Sum (I+D)   {gm_index + gm_data:+6.2f}%   "
      f"(super-additive: {gm_full > gm_index + gm_data})")
print()
print(f"Saved to {out_dir}/proto_r4_54_C_abl.{{pdf,svg}}")
