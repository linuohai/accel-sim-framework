#!/usr/bin/env python3
"""
Round 5 §5.4 Layout A — Component Ablation (nohatch, full-width bar).

20 workloads × 3 schemes: Data-Only, Index-Only, Full GRASP.
NoPF = 1.0x implicit baseline, bars represent speedup multiplier.

Style rules match proto_r4_52_A_nohatch.py:
  - parents[5], apply_style(), figsize_full(), constrained_layout
  - PALETTE_TOL_BRIGHT (no blue/orange)
  - NO hatching (DMP-style color-only)
  - Bars sit on bottom = Y_LO
  - Outliers above Y_HI clipped and annotated with arrow + value
  - Vertical group separators between algorithm groups
  - GMEAN bar at right with solid black separator
  - Subtitle below via subplot_label

Color order:
  Data-Only   = palette[1] red
  Index-Only  = palette[2] purple
  Full GRASP  = palette[0] green
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from plot_util import (  # noqa: E402
    apply_style, figsize_full, save_fig,
    PALETTE_TOL_BRIGHT, subplot_label,
)
from workload_names import (  # noqa: E402
    ORDERED_27, SHORT_NAME, ALG_GROUPS,
)
from _data import ABLATION_PCT, pct_to_mult, gmean  # noqa: E402

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Build workload order from ORDERED_27 intersected with data ─────────────
WORKLOADS = [k for k in ORDERED_27 if k in ABLATION_PCT]
n_wkl = len(WORKLOADS)
assert n_wkl == 20, f"Expected 20 ablation workloads, got {n_wkl}"


# ── Compute speedup multipliers ────────────────────────────────────────────
do_mult = np.array([pct_to_mult(ABLATION_PCT[k][0]) for k in WORKLOADS])
io_mult = np.array([pct_to_mult(ABLATION_PCT[k][1]) for k in WORKLOADS])
fg_mult = np.array([pct_to_mult(ABLATION_PCT[k][2]) for k in WORKLOADS])

do_gm = gmean(do_mult)
io_gm = gmean(io_mult)
fg_gm = gmean(fg_mult)

do_all = np.append(do_mult, do_gm)
io_all = np.append(io_mult, io_gm)
fg_all = np.append(fg_mult, fg_gm)

labels = [SHORT_NAME[k] for k in WORKLOADS] + ["GMEAN"]
n_total = n_wkl + 1


# ── Layout ──────────────────────────────────────────────────────────────────
GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.25
offsets = np.array([-1.0, 0.0, 1.0]) * bar_w

Y_LO, Y_HI = 0.85, 1.50

fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.40),
    constrained_layout=True,
)

# Scheme order: Data-Only (red), Index-Only (purple), Full GRASP (green)
schemes = [
    ("Data-Only",  do_all, PALETTE_TOL_BRIGHT[1]),  # red
    ("Index-Only", io_all, PALETTE_TOL_BRIGHT[2]),  # purple
    ("Full GRASP", fg_all, PALETTE_TOL_BRIGHT[0]),  # green
]


def bar_heights(vals: np.ndarray) -> np.ndarray:
    clipped = np.minimum(vals, Y_HI)
    return clipped - Y_LO


bar_containers = {}
for i, (name, vals, color) in enumerate(schemes):
    heights = bar_heights(vals)
    bars = ax.bar(
        x + offsets[i], heights, bar_w,
        bottom=Y_LO,
        label=name, color=color,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )
    bar_containers[name] = (bars, vals, color)


# ── Annotate clipped outliers (stack at same x) ───────────────────────────
scheme_order = list(bar_containers.keys())
for j in range(n_total):
    clipped_here = []
    for si, name in enumerate(scheme_order):
        bars, vals, color = bar_containers[name]
        v = vals[j]
        if v >= Y_HI:
            clipped_here.append((si, name, v, color))
    if not clipped_here:
        continue
    for stack_i, (si, name, v, color) in enumerate(clipped_here):
        bars, _, _ = bar_containers[name]
        cx = bars[j].get_x() + bars[j].get_width() / 2
        y_offset = 1.5 + stack_i * 6.5
        ax.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, Y_HI),
            xytext=(0, y_offset), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.5, fontweight="bold", color=color,
            zorder=6,
        )
        if stack_i == 0:
            ax.annotate(
                "",
                xy=(cx, Y_HI + 0.012), xytext=(cx, Y_HI - 0.005),
                arrowprops=dict(arrowstyle="->", color=color,
                                lw=0.6, shrinkA=0, shrinkB=0),
                zorder=5,
            )


# ── Algorithm group separators (within 20-workload subset) ─────────────────
sub_group_counts = []
cumulative = 0
for gname, gwkls in ALG_GROUPS:
    present = [w for w in gwkls if w in ABLATION_PCT]
    if not present:
        continue
    sub_group_counts.append((gname, len(present)))

# Draw vertical separators between groups
offset = 0
for idx, (gname, gsize) in enumerate(sub_group_counts):
    offset += gsize
    if idx < len(sub_group_counts) - 1:
        sep_x = offset - 0.5
        ax.axvline(x=sep_x, color="#999999", linestyle="--",
                   linewidth=0.5, alpha=0.7, zorder=1)

gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
ax.axvline(x=gmean_sep_x, color="black", linestyle="-",
           linewidth=0.8, alpha=0.8, zorder=1)


# ── Algorithm group labels below x-tick labels ─────────────────────────────
cum = 0
for gname, gsize in sub_group_counts:
    centre = cum + (gsize - 1) / 2.0
    ax.annotate(
        gname,
        xy=(centre, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -28), textcoords="offset points",
        ha="center", va="top",
        fontsize=7, fontweight="bold",
        annotation_clip=False,
    )
    cum += gsize
ax.annotate(
    "Avg",
    xy=(x[-1], 0), xycoords=("data", "axes fraction"),
    xytext=(0, -28), textcoords="offset points",
    ha="center", va="top",
    fontsize=7, fontweight="bold",
    annotation_clip=False,
)


# ── Axes ───────────────────────────────────────────────────────────────────
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.0)
ax.set_xlim(-0.7, x[-1] + 0.7)

ax.set_ylim(Y_LO, Y_HI + 0.03)
ax.set_ylabel("Normalized Speedup over No-PF (\u00d7)")
yticks = [0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
ax.set_yticks(yticks)
ax.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks])
ax.axhline(1.0, color="#888888", linewidth=0.5, linestyle=":",
           alpha=0.7, zorder=1)


# ── Legend with per-scheme geomean inline ──────────────────────────────────
legend_patches = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black",
          linewidth=0.4,
          label=f"Data-Only ({do_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[2], edgecolor="black",
          linewidth=0.4,
          label=f"Index-Only ({io_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black",
          linewidth=0.4,
          label=f"Full GRASP ({fg_gm:.2f}\u00d7)"),
]
ax.legend(
    handles=legend_patches, ncol=3, fontsize=6.5,
    loc="lower left", bbox_to_anchor=(0.0, 1.02), frameon=False,
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.4, handletextpad=0.4,
    borderaxespad=0,
)


# ── Subtitle below ─────────────────────────────────────────────────────────
subplot_label(ax, "(a) Component Ablation", y=-0.55)


# ── Save ───────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_A_component", out_dir)
plt.close(fig)


# ── Console summary ────────────────────────────────────────────────────────
print("=== Round 5 §5.4 Component Ablation (nohatch) ===")
print(f"Workloads: {n_wkl}  |  GMEAN per scheme:")
print(f"  Data-Only  {do_gm:.3f}\u00d7")
print(f"  Index-Only {io_gm:.3f}\u00d7")
print(f"  Full GRASP {fg_gm:.3f}\u00d7")

print(f"\nClipped bars (>= {Y_HI:.2f}\u00d7):")
for name, (_, vals, _) in bar_containers.items():
    for j, v in enumerate(vals[:-1]):
        if v >= Y_HI:
            print(f"  {name:11s}  {WORKLOADS[j]:18s}  {v:.3f}\u00d7")

print(f"\nRegressions (< 1.00\u00d7):")
for name, (_, vals, _) in bar_containers.items():
    for j, v in enumerate(vals[:-1]):
        if v < 1.0:
            print(f"  {name:11s}  {WORKLOADS[j]:18s}  {v:.3f}\u00d7")

print(f"\nSaved to {out_dir}/proto_r4_54_A_component.{{pdf,svg}}")
