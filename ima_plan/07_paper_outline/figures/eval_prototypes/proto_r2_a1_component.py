#!/usr/bin/env python3
"""Round-2 Fig A1: Component Ablation with Synergy Gap.

Two vertically stacked subplots (shared x-axis):
  (a) Speedup (%) — grouped bars: Index-Only / Data-Only / Full GRASP
  (b) Synergy Gap (pp) — single bar per workload:
      Synergy = Full_speedup - Index_speedup - Data_speedup
      Positive = pipeline coordination provides extra benefit (super-additive)
      Negative = components interfere
      Color: positive=green, negative=red, near-zero=gray

Data source:
  ima_plan/06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md
  §Exp-A "Component Ablation" -> "Speedup% (vs Baseline)" (20 workloads)

Workload subset: 13 representative workloads chosen from the 20 in §Exp-A,
preferring the 8-workload core + a few CC/VC for diversity.
"""

import sys
from pathlib import Path

import numpy as np

# ── Plot style import ────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10, HATCHES, legend_below
from workload_names import SHORT_NAME

apply_style()
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

OUT_DIR = Path(__file__).resolve().parent

# ── Hardcoded data from §Exp-A "Speedup% (vs Baseline)" ─────────────────────
# (data_only_pct, index_only_pct, full_grasp_pct)
RAW_DATA = {
    "bfs_cit_dir":     (+10.2, +3.5,  +14.0),
    "sssp_cit_dir":    (+10.4, +2.5,  +10.8),
    "bc_cit_dir":      (+8.0,  +2.0,  +9.8),
    "spmv_web_sym":    (+0.5,  +22.4, +40.2),
    "bfs_web_sym":     (+43.5, +6.4,  +56.2),
    "cc_flickr_sym":   (+53.4, +36.9, +102.5),
    "spmv_flickr_sym": (+8.6,  +22.5, +37.8),
    "bfs_flickr_sym":  (+13.4, +11.1, +27.2),
    "sssp_web_sym":    (+45.1, +4.6,  +46.9),
    "cc_web_sym":      (+51.5, +17.5, +69.9),
    "bc_web_sym":      (+7.6,  +3.0,  +14.2),
    "bc_flickr_sym":   (+14.9, +11.3, +23.6),
    "sssp_flickr_sym": (+18.4, +5.6,  +20.0),
}

# ── Display order (algorithm-grouped, matches user-requested 13) ─────────────
ORDERED = [
    "bfs_cit_dir",
    "bfs_web_sym",
    "bfs_flickr_sym",
    "sssp_cit_dir",
    "sssp_web_sym",
    "sssp_flickr_sym",
    "bc_cit_dir",
    "bc_web_sym",
    "bc_flickr_sym",
    "cc_web_sym",
    "cc_flickr_sym",
    "spmv_web_sym",
    "spmv_flickr_sym",
]
assert set(ORDERED) == set(RAW_DATA.keys())

# Algorithm group boundaries (between consecutive groups)
GROUPS = [
    ("BFS",  3),
    ("SSSP", 3),
    ("BC",   3),
    ("CC",   2),
    ("SpMV", 2),
]

data_only  = np.array([RAW_DATA[k][0] for k in ORDERED])
index_only = np.array([RAW_DATA[k][1] for k in ORDERED])
full_grasp = np.array([RAW_DATA[k][2] for k in ORDERED])

# Synergy Gap (percentage points)
synergy = full_grasp - index_only - data_only

# ── Geometric mean helper ────────────────────────────────────────────────────
def gmean_pct(pct_arr):
    ratios = 1.0 + pct_arr / 100.0
    return (np.exp(np.mean(np.log(ratios))) - 1.0) * 100.0


gmean_index = gmean_pct(index_only)
gmean_data  = gmean_pct(data_only)
gmean_full  = gmean_pct(full_grasp)
mean_synergy = float(np.mean(synergy))

# ── Plot setup ───────────────────────────────────────────────────────────────
n = len(ORDERED)
x = np.arange(n)
bar_w = 0.27

fig, axes = plt.subplots(
    2, 1, figsize=(7.0, 4.0),
    constrained_layout=True, sharex=True,
)
ax_speedup, ax_synergy = axes

# ── (a) Grouped speedup bars ─────────────────────────────────────────────────
schemes = [
    (-1, "Index-Only", CB10[0], HATCHES[1], index_only, gmean_index),
    ( 0, "Data-Only",  CB10[1], HATCHES[2], data_only,  gmean_data),
    (+1, "Full GRASP", CB10[3], HATCHES[0], full_grasp, gmean_full),
]

for shift, label, color, hatch, vals, gm in schemes:
    ax_speedup.bar(
        x + shift * bar_w, vals, bar_w,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        label=f"{label} (avg {gm:+.1f}%)",
        zorder=3,
    )

ax_speedup.axhline(y=0, color="black", linewidth=0.6, zorder=2)
ax_speedup.set_ylabel("Speedup (%)")
ymax_top = max(full_grasp.max(), data_only.max(), index_only.max())
ymin_top = min(full_grasp.min(), data_only.min(), index_only.min(), 0)
ax_speedup.set_ylim(ymin_top - 4, ymax_top * 1.18)
ax_speedup.set_title("(a) Component Ablation: IPC Speedup vs Baseline",
                     fontsize=8, pad=4)

# Legend at top of subplot (a) — 3 columns, includes geomean
ax_speedup.legend(
    ncol=3, fontsize=6.5, frameon=False,
    loc="upper left", bbox_to_anchor=(0.0, 1.0),
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.4,
)

# ── (b) Synergy Gap bars ─────────────────────────────────────────────────────
# Color mapping by sign: green (positive), gray (near-zero |x|<1.5), red (negative)
GREEN = "#2CA02C"
RED   = "#D62728"
GRAY  = "#999999"

def synergy_color(v):
    if v >= 1.5:
        return GREEN
    if v <= -1.5:
        return RED
    return GRAY

bar_colors = [synergy_color(v) for v in synergy]
bars_syn = ax_synergy.bar(
    x, synergy, bar_w * 2.4,
    color=bar_colors, edgecolor="black", linewidth=0.4,
    zorder=3,
)

ax_synergy.axhline(y=0, color="black", linewidth=0.6, zorder=2)
ax_synergy.set_ylabel("Synergy Gap (pp)")
ymax_b = max(synergy.max(), 0) * 1.30
ymin_b = min(synergy.min(), 0) * 1.30 - 1
ax_synergy.set_ylim(ymin_b, ymax_b + 2)
ax_synergy.set_title(
    "(b) Synergy Gap = Full $-$ Index $-$ Data  "
    "($>$0: super-additive pipeline benefit)",
    fontsize=8, pad=4,
)

# Annotate top-3 largest synergy bars (by absolute value)
order_by_abs = np.argsort(-np.abs(synergy))[:3]
for idx in order_by_abs:
    v = synergy[idx]
    label = f"{v:+.1f}"
    va = "bottom" if v >= 0 else "top"
    offset = 0.6 if v >= 0 else -0.6
    ax_synergy.text(
        x[idx], v + offset, label,
        ha="center", va=va, fontsize=6, fontweight="bold",
        color=synergy_color(v),
    )

# Mean synergy reference line (dotted)
ax_synergy.axhline(
    y=mean_synergy, color="#444444", linestyle=":",
    linewidth=0.7, alpha=0.8, zorder=2,
)
ax_synergy.text(
    n - 0.3, mean_synergy, f"  mean {mean_synergy:+.1f} pp",
    ha="left", va="center", fontsize=6, color="#444444",
)

# ── Vertical group separators on both subplots ───────────────────────────────
cumulative = 0
for gname, gsize in GROUPS[:-1]:
    cumulative += gsize
    for ax in axes:
        ax.axvline(
            x=cumulative - 0.5, color="#999999",
            linestyle="--", linewidth=0.5, alpha=0.6, zorder=1,
        )

# ── Algorithm group labels under bottom subplot ──────────────────────────────
cumulative = 0
for gname, gsize in GROUPS:
    center = cumulative + (gsize - 1) / 2.0
    ax_synergy.annotate(
        gname,
        xy=(center, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -32), textcoords="offset points",
        ha="center", va="top",
        fontsize=7, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize

# ── X-axis tick labels (only on bottom subplot) ──────────────────────────────
xlabels = [SHORT_NAME[k] for k in ORDERED]
ax_synergy.set_xticks(x)
ax_synergy.set_xticklabels(xlabels, rotation=45, ha="right", fontsize=7)

# Tick label sizes
for ax in axes:
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlim(-0.7, n - 0.3)

# ── Save ─────────────────────────────────────────────────────────────────────
save_fig(fig, "proto_r2_a1_component", OUT_DIR)
plt.close(fig)

# ── Verification print ──────────────────────────────────────────────────────
print(f"Saved: {OUT_DIR}/proto_r2_a1_component.{{pdf,svg}}")
print(f"Workloads: {n}")
print()
print(f"GMEAN Index-Only: {gmean_index:+6.2f}%")
print(f"GMEAN Data-Only:  {gmean_data:+6.2f}%")
print(f"GMEAN Full GRASP: {gmean_full:+6.2f}%")
print(f"Sum (I+D):        {gmean_index + gmean_data:+6.2f}%  "
      f"(super-additive: Full > sum is {gmean_full > gmean_index + gmean_data})")
print()
print(f"Synergy mean:     {mean_synergy:+6.2f} pp")
print(f"Synergy range:    {synergy.min():+6.2f} .. {synergy.max():+6.2f} pp")
print()
print("Per-workload synergy (Full - Index - Data, in pp):")
for k, s, full, idx_v, dat_v in zip(
    ORDERED, synergy, full_grasp, index_only, data_only
):
    sign_marker = "++" if s >= 5 else "+" if s >= 1.5 else "~" if s > -1.5 \
        else "-" if s > -5 else "--"
    print(f"  {SHORT_NAME[k]:9s}  Full={full:+6.1f}%  "
          f"Idx={idx_v:+6.1f}%  Dat={dat_v:+6.1f}%  "
          f"Synergy={s:+6.2f} pp  [{sign_marker}]")
