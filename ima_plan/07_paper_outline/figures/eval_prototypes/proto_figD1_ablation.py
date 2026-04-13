#!/usr/bin/env python3
"""
Proto Figure D1: Component Ablation — Index-Only vs Data-Only vs Full GRASP.

Grouped bar chart (full-width, 7.0") showing Speedup% vs baseline for
20 workloads grouped by algorithm, plus geometric mean.

Data source:
  ima_plan/06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md
  Section "Exp-A: Component Ablation" -> "结果：Speedup% (vs Baseline)"
"""

import sys
from pathlib import Path
import numpy as np

# ── Plot style import ────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, CB10, HATCHES, save_fig

apply_style()
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# ── Hardcoded data from Exp-A table ─────────────────────────────────────────
# (key, data_only_speedup%, index_only_speedup%, full_grasp_speedup%)
RAW_DATA = {
    "bfs_cit_dir":      (+10.2, +3.5,  +14.0),
    "sssp_cit_dir":     (+10.4, +2.5,  +10.8),
    "bc_cit_dir":       (+8.0,  +2.0,  +9.8),
    "spmv_web_sym":     (+0.5,  +22.4, +40.2),
    "bfs_web_sym":      (+43.5, +6.4,  +56.2),
    "cc_flickr_sym":    (+53.4, +36.9, +102.5),
    "spmv_flickr_sym":  (+8.6,  +22.5, +37.8),
    "bfs_flickr_sym":   (+13.4, +11.1, +27.2),
    "bfs_road_sym":     (+1.9,  +6.7,  +8.5),
    "sssp_road_sym":    (+2.1,  +5.4,  +6.3),
    "cc_road_sym":      (+1.1,  -0.1,  -0.7),
    "bc_road_sym":      (+1.4,  +3.3,  +4.7),
    "sssp_flickr_sym":  (+18.4, +5.6,  +20.0),
    "sssp_web_sym":     (+45.1, +4.6,  +46.9),
    "vc_web_sym":       (+0.6,  +3.1,  +2.5),
    "spmv_cit_sym":     (-1.1,  -0.7,  -1.3),
    "bc_flickr_sym":    (+14.9, +11.3, +23.6),
    "bc_web_sym":       (+7.6,  +3.0,  +14.2),
    "vc_cit_sym":       (+1.0,  +0.5,  +1.9),
    "cc_web_sym":       (+51.5, +17.5, +69.9),
}

# ── Algorithm group ordering ────────────────────────────────────────────────
GROUPS = [
    ("BFS",  ["bfs_cit_dir", "bfs_web_sym", "bfs_flickr_sym", "bfs_road_sym"]),
    ("SSSP", ["sssp_cit_dir", "sssp_web_sym", "sssp_flickr_sym", "sssp_road_sym"]),
    ("BC",   ["bc_cit_dir", "bc_web_sym", "bc_flickr_sym", "bc_road_sym"]),
    ("CC",   ["cc_flickr_sym", "cc_web_sym", "cc_road_sym"]),
    ("SpMV", ["spmv_cit_sym", "spmv_web_sym", "spmv_flickr_sym"]),
    ("VC",   ["vc_cit_sym", "vc_web_sym"]),
]

# Flatten ordered key list
ordered_keys = []
for _, members in GROUPS:
    ordered_keys.extend(members)

# Extract arrays in display order
data_only  = np.array([RAW_DATA[k][0] for k in ordered_keys])
index_only = np.array([RAW_DATA[k][1] for k in ordered_keys])
full_grasp = np.array([RAW_DATA[k][2] for k in ordered_keys])

# ── Geometric mean of speedup ratios ────────────────────────────────────────
# Speedup% -> ratio, then geometric mean, then back to %
def gmean_pct(pct_arr):
    ratios = 1.0 + pct_arr / 100.0
    return (np.exp(np.mean(np.log(ratios))) - 1.0) * 100.0

gmean_data  = gmean_pct(data_only)
gmean_index = gmean_pct(index_only)
gmean_full  = gmean_pct(full_grasp)

# ── Short x-labels ──────────────────────────────────────────────────────────
DATASET_ABBREV = {
    "cit_dir": "cit", "cit_sym": "cit",
    "web_sym": "web",
    "flickr_sym": "flk",
    "road_sym": "road",
}

def short_label(key):
    parts = key.split("_", 1)
    suffix = parts[1] if len(parts) > 1 else key
    return DATASET_ABBREV.get(suffix, suffix)

xlabels = [short_label(k) for k in ordered_keys]

# ── Plot ────────────────────────────────────────────────────────────────────
n = len(ordered_keys)
x = np.arange(n + 1)  # +1 for GMEAN
bar_w = 0.25

fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.40),
    constrained_layout=True,
)

# 3 schemes: Index-Only, Data-Only, Full GRASP
schemes = [
    (-1, "Index-Only",  CB10[0], HATCHES[1],
     np.append(index_only, gmean_index)),
    ( 0, "Data-Only",   CB10[1], HATCHES[2],
     np.append(data_only, gmean_data)),
    (+1, "Full GRASP",  CB10[3], HATCHES[0],
     np.append(full_grasp, gmean_full)),
]

for shift, label, color, hatch, vals in schemes:
    offset = shift * bar_w
    ax.bar(
        x + offset, vals, bar_w,
        label=label, color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )

# ── Annotate GMEAN values with offset labels to the right ──────────────────
# Place labels at fixed vertical spacing to the right of bars, with thin
# connector lines to avoid overlap.  Ordered bottom-to-top by value.
gmean_x = n
text_x = gmean_x + 0.65          # x position for text, right of all bars
text_y_positions = [11, 24, 37]   # evenly spaced, well separated
for (shift, label, color, hatch, vals), ty in zip(schemes, text_y_positions):
    v = vals[-1]
    bar_cx = gmean_x + shift * bar_w
    ax.annotate(
        f"{v:+.1f}%",
        xy=(bar_cx, v),                   # point at bar top
        xytext=(text_x, ty),              # label position
        fontsize=5.5, fontweight="bold", color=color,
        ha="left", va="center",
        arrowprops=dict(arrowstyle="-", color=color, lw=0.6),
        zorder=5,
    )

# ── Vertical dashed separators between algorithm groups ────────────────────
cumulative = 0
for gname, members in GROUPS[:-1]:
    cumulative += len(members)
    ax.axvline(x=cumulative - 0.5, color="#999999", linestyle="--",
               linewidth=0.5, alpha=0.6, zorder=1)

# GMEAN separator (solid)
ax.axvline(x=n - 0.5, color="black", linestyle="-",
           linewidth=0.8, alpha=0.8, zorder=1)

# ── Baseline at y=0 ────────────────────────────────────────────────────────
ax.axhline(y=0, color="black", linewidth=0.6, zorder=2)

# ── Algorithm group labels below tick labels ───────────────────────────────
cumulative = 0
for gname, members in GROUPS:
    gsize = len(members)
    center = cumulative + (gsize - 1) / 2.0
    ax.annotate(
        gname,
        xy=(center, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -28), textcoords="offset points",
        ha="center", va="top",
        fontsize=7, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize
ax.annotate(
    "Avg",
    xy=(n, 0), xycoords=("data", "axes fraction"),
    xytext=(0, -28), textcoords="offset points",
    ha="center", va="top",
    fontsize=7, fontweight="bold",
    annotation_clip=False,
)

# ── Axes formatting ─────────────────────────────────────────────────────────
ax.set_ylabel("Speedup (%)")
y_max = max(full_grasp.max(), data_only.max(), index_only.max())
y_min = min(full_grasp.min(), data_only.min(), index_only.min())
ax.set_ylim(y_min - 5, y_max * 1.12)
ax.set_xlim(-0.6, n + 1.6)

xtick_labels = xlabels + [""]
ax.set_xticks(x)
ax.set_xticklabels(xtick_labels, rotation=45, ha="right", fontsize=5.5)

# ── Legend at top with average speedup per scheme ──────────────────────────
legend_patches = [
    Patch(facecolor=CB10[0], edgecolor="black", hatch=HATCHES[1],
          linewidth=0.4, label=f"Index-Only (avg {gmean_index:+.1f}%)"),
    Patch(facecolor=CB10[1], edgecolor="black", hatch=HATCHES[2],
          linewidth=0.4, label=f"Data-Only (avg {gmean_data:+.1f}%)"),
    Patch(facecolor=CB10[3], edgecolor="black", hatch=HATCHES[0],
          linewidth=0.4, label=f"Full GRASP (avg {gmean_full:+.1f}%)"),
]
ax.legend(
    handles=legend_patches, ncol=3, fontsize=6.5,
    loc="upper left", frameon=False,
    handlelength=1.4, handleheight=0.9,
    bbox_to_anchor=(0.0, 1.01),
)

# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_figD1_ablation", out_dir)
plt.close(fig)

# ── Print summary ───────────────────────────────────────────────────────────
print(f"GMEAN Index-Only: {gmean_index:+.1f}%")
print(f"GMEAN Data-Only:  {gmean_data:+.1f}%")
print(f"GMEAN Full GRASP: {gmean_full:+.1f}%")
print(f"Synergy check: Full ({gmean_full:+.1f}%) vs"
      f" Index+Data sum ({gmean_index + gmean_data:+.1f}%)")
print(f"Saved to {out_dir}/proto_figD1_ablation.{{pdf,svg}}")
