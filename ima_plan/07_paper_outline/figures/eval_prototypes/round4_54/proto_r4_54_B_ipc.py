#!/usr/bin/env python3
"""
Round 5 §5.4 Layout B — Throttle IPC Ablation (nohatch, full-width bar).

22 workloads × 3 schemes: Default, D5b (paper version), T40C200.
Speedup% over NoPF baseline converted to multiplier (1.0 + pct/100).

Color order:
  Default  = palette[1] red
  D5b      = palette[0] green (highlight — paper version)
  T40C200  = palette[3] yellow

Style rules same as proto_r4_52_A_nohatch.py.
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
from _data import THROTTLE_IPC_PCT, pct_to_mult, gmean  # noqa: E402

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Workload order ────────────────────────────────────────────────────────
WORKLOADS = [k for k in ORDERED_27 if k in THROTTLE_IPC_PCT]
n_wkl = len(WORKLOADS)
assert n_wkl == 22, f"Expected 22 throttle IPC workloads, got {n_wkl}"


# ── Multipliers ────────────────────────────────────────────────────────────
def to_mult_arr(idx):
    return np.array([pct_to_mult(THROTTLE_IPC_PCT[k][idx]) for k in WORKLOADS])


default_m = to_mult_arr(0)
d5b_m     = to_mult_arr(1)
t40_m     = to_mult_arr(2)

default_gm = gmean(default_m)
d5b_gm     = gmean(d5b_m)
t40_gm     = gmean(t40_m)

default_all = np.append(default_m, default_gm)
d5b_all     = np.append(d5b_m, d5b_gm)
t40_all     = np.append(t40_m, t40_gm)

labels = [SHORT_NAME[k] for k in WORKLOADS] + ["GMEAN"]
n_total = n_wkl + 1


# ── Layout ─────────────────────────────────────────────────────────────────
GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.25
offsets = np.array([-1.0, 0.0, 1.0]) * bar_w

Y_LO, Y_HI = 0.90, 1.50

fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.40),
    constrained_layout=True,
)

schemes = [
    ("Default", default_all, PALETTE_TOL_BRIGHT[1]),  # red
    ("D5b",     d5b_all,     PALETTE_TOL_BRIGHT[0]),  # green (paper version)
    ("T40C200", t40_all,     PALETTE_TOL_BRIGHT[3]),  # yellow
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


# ── Annotate clipped outliers ──────────────────────────────────────────────
# Group clipped values by workload index so overlapping annotations at the
# same x can be stacked vertically.
scheme_order = list(bar_containers.keys())
for j in range(n_total):
    # Collect all clipped schemes at this index
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
        # Stack values vertically: first at 1.5pt above Y_HI, then +6pt, ...
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


# ── Regression annotation (bars below Y_LO) ───────────────────────────────
for name, (bars, vals, color) in bar_containers.items():
    for j, bar in enumerate(bars):
        v = vals[j]
        if v >= Y_LO:
            continue
        cx = bar.get_x() + bar.get_width() / 2
        # Draw a small down-arrow at Y_LO with value
        ax.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, Y_LO + 0.002),
            xytext=(0, 1.5), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.5, fontweight="bold", color=color,
            zorder=6,
        )


# ── Group separators + labels ──────────────────────────────────────────────
sub_group_counts = []
for gname, gwkls in ALG_GROUPS:
    present = [w for w in gwkls if w in THROTTLE_IPC_PCT]
    if not present:
        continue
    sub_group_counts.append((gname, len(present)))

offset_i = 0
for idx, (gname, gsize) in enumerate(sub_group_counts):
    offset_i += gsize
    if idx < len(sub_group_counts) - 1:
        sep_x = offset_i - 0.5
        ax.axvline(x=sep_x, color="#999999", linestyle="--",
                   linewidth=0.5, alpha=0.7, zorder=1)

gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
ax.axvline(x=gmean_sep_x, color="black", linestyle="-",
           linewidth=0.8, alpha=0.8, zorder=1)

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


# ── Legend ─────────────────────────────────────────────────────────────────
legend_patches = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black",
          linewidth=0.4,
          label=f"Default ({default_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black",
          linewidth=0.4,
          label=f"D5b ({d5b_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[3], edgecolor="black",
          linewidth=0.4,
          label=f"T40C200 ({t40_gm:.2f}\u00d7)"),
]
ax.legend(
    handles=legend_patches, ncol=3, fontsize=6.5,
    loc="lower left", bbox_to_anchor=(0.0, 1.02), frameon=False,
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.4, handletextpad=0.4,
    borderaxespad=0,
)

subplot_label(ax, "(b) Throttle IPC", y=-0.55)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_B_ipc", out_dir)
plt.close(fig)


print("=== Round 5 §5.4 Throttle IPC (nohatch) ===")
print(f"Workloads: {n_wkl}  |  GMEAN per scheme:")
print(f"  Default  {default_gm:.3f}\u00d7")
print(f"  D5b      {d5b_gm:.3f}\u00d7")
print(f"  T40C200  {t40_gm:.3f}\u00d7")

print(f"\nClipped bars (>= {Y_HI:.2f}\u00d7):")
for name, (_, vals, _) in bar_containers.items():
    for j, v in enumerate(vals[:-1]):
        if v >= Y_HI:
            print(f"  {name:8s}  {WORKLOADS[j]:18s}  {v:.3f}\u00d7")

print(f"\nRegressions (< {Y_LO:.2f}\u00d7, clipped to Y_LO):")
for name, (_, vals, _) in bar_containers.items():
    for j, v in enumerate(vals[:-1]):
        if v < Y_LO:
            print(f"  {name:8s}  {WORKLOADS[j]:18s}  {v:.3f}\u00d7")

print(f"\nSaved to {out_dir}/proto_r4_54_B_ipc.{{pdf,svg}}")
