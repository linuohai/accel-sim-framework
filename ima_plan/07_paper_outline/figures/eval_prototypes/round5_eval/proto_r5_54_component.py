#!/usr/bin/env python3
"""
Round 5 §5.4 — Component Ablation (single-column).

Forked from round4_54/proto_r4_54_A_component.py but rendered at
single-column width (3.5in). 20 workloads x 3 schemes is tight but
readable with narrower bars and smaller fonts.

Output: component_ablation.{pdf,svg}
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/figures/eval_prototypes/round4_54"))

from plot_util import (  # noqa: E402
    apply_style, save_fig, PALETTE_TOL_BRIGHT,
)
from workload_names import (  # noqa: E402
    ORDERED_27, SHORT_NAME, ALG_GROUPS,
)
from _data import ABLATION_PCT, pct_to_mult, gmean  # noqa: E402

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


WORKLOADS = [k for k in ORDERED_27 if k in ABLATION_PCT]
n_wkl = len(WORKLOADS)
assert n_wkl == 20, f"Expected 20 ablation workloads, got {n_wkl}"


do_mult = np.array([pct_to_mult(ABLATION_PCT[k][0]) for k in WORKLOADS])
io_mult = np.array([pct_to_mult(ABLATION_PCT[k][1]) for k in WORKLOADS])
fg_mult = np.array([pct_to_mult(ABLATION_PCT[k][2]) for k in WORKLOADS])

do_gm = gmean(do_mult)
io_gm = gmean(io_mult)
fg_gm = gmean(fg_mult)

do_all = np.append(do_mult, do_gm)
io_all = np.append(io_mult, io_gm)
fg_all = np.append(fg_mult, fg_gm)

labels = [SHORT_NAME[k] for k in WORKLOADS] + ["GM"]
n_total = n_wkl + 1


# ── Layout ──────────────────────────────────────────────────────────────────
GMEAN_GAP = 0.5
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.25
offsets = np.array([-1.0, 0.0, 1.0]) * bar_w

Y_LO, Y_HI = 0.85, 1.50

fig, ax = plt.subplots(
    figsize=(3.5, 2.6),
    constrained_layout=True,
)

schemes = [
    ("Data-Only",  do_all, PALETTE_TOL_BRIGHT[1]),  # red
    ("Index-Only", io_all, PALETTE_TOL_BRIGHT[2]),  # purple
    ("Full GRASP", fg_all, PALETTE_TOL_BRIGHT[0]),  # green
]

bar_containers = {}
for i, (name, vals, color) in enumerate(schemes):
    clipped = np.minimum(vals, Y_HI)
    heights = clipped - Y_LO
    bars = ax.bar(
        x + offsets[i], heights, bar_w,
        bottom=Y_LO,
        color=color,
        edgecolor="black", linewidth=0.25,
        zorder=3,
    )
    bar_containers[name] = (bars, vals, color)

# Annotate outliers (stacked at same x)
scheme_order = list(bar_containers.keys())
for j in range(n_total):
    clipped_here = []
    for si, name in enumerate(scheme_order):
        bars, vals, color = bar_containers[name]
        v = vals[j]
        if v >= Y_HI:
            clipped_here.append((si, name, v, color))
    for stack_i, (si, name, v, color) in enumerate(clipped_here):
        bars, _, _ = bar_containers[name]
        cx = bars[j].get_x() + bars[j].get_width() / 2
        y_offset = 1.0 + stack_i * 5.0
        ax.annotate(
            f"{v:.1f}\u00d7",
            xy=(cx, Y_HI),
            xytext=(0, y_offset), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=4.2, fontweight="bold", color=color,
            zorder=6,
        )

# Regressions (<Y_LO)
for name, (bars, vals, color) in bar_containers.items():
    for j, bar in enumerate(bars):
        v = vals[j]
        if v >= Y_LO:
            continue
        cx = bar.get_x() + bar.get_width() / 2
        ax.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, Y_LO + 0.002),
            xytext=(0, 1.0), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=4.2, fontweight="bold", color=color,
            zorder=6,
        )


# Group separators
sub_group_counts = []
for gname, gwkls in ALG_GROUPS:
    present = [w for w in gwkls if w in ABLATION_PCT]
    if not present:
        continue
    sub_group_counts.append((gname, len(present)))

offset = 0
for idx, (gname, gsize) in enumerate(sub_group_counts):
    offset += gsize
    if idx < len(sub_group_counts) - 1:
        sep_x = offset - 0.5
        ax.axvline(x=sep_x, color="#999999", linestyle="--",
                   linewidth=0.4, alpha=0.7, zorder=1)

gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
ax.axvline(x=gmean_sep_x, color="black", linestyle="-",
           linewidth=0.7, alpha=0.8, zorder=1)


# Axes
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=55, ha="right", fontsize=4.5)
ax.tick_params(axis="x", length=2, pad=0.5)
ax.set_xlim(-0.7, x[-1] + 0.7)

ax.set_ylim(Y_LO, Y_HI + 0.03)
ax.set_ylabel("Speedup (\u00d7)", fontsize=6.5, labelpad=1)
ax.set_yticks([0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
ax.set_yticklabels([f"{t:.1f}\u00d7" for t in
                    [0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]], fontsize=5.5)
ax.tick_params(axis="y", length=2, pad=1)
ax.axhline(1.0, color="#888888", linewidth=0.4, linestyle=":",
           alpha=0.7, zorder=1)


# Legend above panel
legend_patches = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black", linewidth=0.3,
          label=f"Data-Only ({do_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[2], edgecolor="black", linewidth=0.3,
          label=f"Index-Only ({io_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black", linewidth=0.3,
          label=f"Full GRASP ({fg_gm:.2f}\u00d7)"),
]
ax.legend(
    handles=legend_patches, ncol=3, fontsize=5.2,
    loc="lower left", bbox_to_anchor=(0.0, 1.01), frameon=False,
    handlelength=1.0, handleheight=0.7,
    columnspacing=0.6, handletextpad=0.25,
    borderaxespad=0,
)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "component_ablation", out_dir)
plt.close(fig)


print("=== Round 5 §5.4 Component Ablation (single-col) ===")
print(f"n_wkl = {n_wkl}")
print(f"  Data-Only  GMEAN = {do_gm:.3f}\u00d7")
print(f"  Index-Only GMEAN = {io_gm:.3f}\u00d7")
print(f"  Full GRASP GMEAN = {fg_gm:.3f}\u00d7")
print(f"Saved to {out_dir}/component_ablation.{{pdf,svg}}")
