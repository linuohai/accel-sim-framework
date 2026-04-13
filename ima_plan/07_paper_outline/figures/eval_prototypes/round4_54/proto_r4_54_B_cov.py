#!/usr/bin/env python3
"""
Round 5 §5.4 Layout B — Throttle Data Coverage (nohatch, full-width bar).

16 workloads × 3 schemes: Default, D5b, T40C200.
Y = Data Coverage % (0-100).
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
from _data import THROTTLE_COV  # noqa: E402

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


WORKLOADS = [k for k in ORDERED_27 if k in THROTTLE_COV]
n_wkl = len(WORKLOADS)
assert n_wkl == 16, f"Expected 16 coverage workloads, got {n_wkl}"


def col_arr(idx):
    return np.array([THROTTLE_COV[k][idx] for k in WORKLOADS])


default_c = col_arr(0)
d5b_c     = col_arr(1)
t40_c     = col_arr(2)

default_mean = float(np.mean(default_c))
d5b_mean     = float(np.mean(d5b_c))
t40_mean     = float(np.mean(t40_c))

default_all = np.append(default_c, default_mean)
d5b_all     = np.append(d5b_c,     d5b_mean)
t40_all     = np.append(t40_c,     t40_mean)

labels = [SHORT_NAME[k] for k in WORKLOADS] + ["MEAN"]
n_total = n_wkl + 1


GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.25
offsets = np.array([-1.0, 0.0, 1.0]) * bar_w

Y_LO, Y_HI = 0.0, 100.0

fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.40),
    constrained_layout=True,
)

schemes = [
    ("Default", default_all, PALETTE_TOL_BRIGHT[1]),
    ("D5b",     d5b_all,     PALETTE_TOL_BRIGHT[0]),
    ("T40C200", t40_all,     PALETTE_TOL_BRIGHT[3]),
]

bar_containers = {}
for i, (name, vals, color) in enumerate(schemes):
    bars = ax.bar(
        x + offsets[i], vals, bar_w,
        bottom=Y_LO,
        label=name, color=color,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )
    bar_containers[name] = (bars, vals, color)


sub_group_counts = []
for gname, gwkls in ALG_GROUPS:
    present = [w for w in gwkls if w in THROTTLE_COV]
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


ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.0)
ax.set_xlim(-0.7, x[-1] + 0.7)

ax.set_ylim(Y_LO, Y_HI + 3)
ax.set_ylabel("Data Coverage (%)")
yticks = [0, 20, 40, 60, 80, 100]
ax.set_yticks(yticks)
ax.set_yticklabels([f"{t:d}" for t in yticks])


legend_patches = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black",
          linewidth=0.4,
          label=f"Default ({default_mean:.1f}%)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black",
          linewidth=0.4,
          label=f"D5b ({d5b_mean:.1f}%)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[3], edgecolor="black",
          linewidth=0.4,
          label=f"T40C200 ({t40_mean:.1f}%)"),
]
ax.legend(
    handles=legend_patches, ncol=3, fontsize=6.5,
    loc="lower left", bbox_to_anchor=(0.0, 1.02), frameon=False,
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.4, handletextpad=0.4,
    borderaxespad=0,
)

subplot_label(ax, "(d) Throttle Coverage", y=-0.55)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_B_cov", out_dir)
plt.close(fig)


print("=== Round 5 §5.4 Throttle Coverage (nohatch) ===")
print(f"Workloads: {n_wkl}  |  MEAN per scheme:")
print(f"  Default  {default_mean:.2f}%")
print(f"  D5b      {d5b_mean:.2f}%")
print(f"  T40C200  {t40_mean:.2f}%")
print(f"\nSaved to {out_dir}/proto_r4_54_B_cov.{{pdf,svg}}")
