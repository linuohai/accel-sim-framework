#!/usr/bin/env python3
"""
Round 5 §5.4 Layout C — Distance Sensitivity (nohatch, full-width line).

20 workloads aggregated into 6 algorithm GMEAN lines (faint) + bold overall
GMEAN line on top.

x = prefetch distance {1, 2, 4, 8}
y = normalized speedup over D=1 (1.0 implicit baseline)

Style:
  - PALETTE_TOL_BRIGHT palette for algorithm colors
  - Overall GMEAN = bold black
  - Subplot label below via subplot_label
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
from _data import (  # noqa: E402
    DISTANCE_IPC, DISTANCES, SENS_ALGORITHMS,
    sensitivity_normalized, algorithm_gmean_lines, overall_gmean_line,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


# ── Normalize IPC to D=1 baseline ───────────────────────────────────────────
WORKLOADS = list(DISTANCE_IPC.keys())
norm = sensitivity_normalized(DISTANCE_IPC, WORKLOADS)
alg_lines = algorithm_gmean_lines(norm, SENS_ALGORITHMS)
overall = overall_gmean_line(norm)

n_d = len(DISTANCES)
assert n_d == 4


# ── Colors & markers for 6 algorithms ──────────────────────────────────────
# Use PALETTE_TOL_BRIGHT (5 colors) + slate for 6th
ALG_COLORS = {
    "BFS":  PALETTE_TOL_BRIGHT[0],  # green
    "SSSP": PALETTE_TOL_BRIGHT[1],  # red
    "BC":   PALETTE_TOL_BRIGHT[2],  # purple
    "CC":   PALETTE_TOL_BRIGHT[3],  # yellow
    "SpMV": PALETTE_TOL_BRIGHT[4],  # gray
    "VC":   "#4B4B6A",              # slate violet (6th algorithm)
}
ALG_MARKERS = {
    "BFS":  "o",
    "SSSP": "s",
    "BC":   "^",
    "CC":   "D",
    "SpMV": "v",
    "VC":   "*",
}


# ── Figure ─────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.32),
    constrained_layout=True,
)

x = np.arange(n_d)

# Plot algorithm GMEAN lines (faint, but distinguishable)
for name, line, n_wl in alg_lines:
    ax.plot(
        x, line,
        marker=ALG_MARKERS[name], color=ALG_COLORS[name],
        markersize=5.5, linewidth=1.3, alpha=0.75,
        markeredgecolor="white", markeredgewidth=0.4,
        label=f"{name} (n={n_wl})",
        zorder=5,
    )

# Bold overall GMEAN line on top
ax.plot(
    x, overall,
    marker="o", color="black",
    markersize=7.0, linewidth=2.4,
    markeredgecolor="white", markeredgewidth=0.7,
    label="Overall GMEAN",
    zorder=10,
)

# Y = 1.0 reference
ax.axhline(1.0, color="#888888", linewidth=0.6, linestyle=":",
           alpha=0.7, zorder=1)


# ── Y-axis: tight range ─────────────────────────────────────────────────────
# Check data range
y_min = min(float(overall.min()),
            min(float(line.min()) for _, line, _ in alg_lines))
y_max = max(float(overall.max()),
            max(float(line.max()) for _, line, _ in alg_lines))

Y_LO, Y_HI = 0.90, 1.15
ax.set_ylim(Y_LO, Y_HI)

# Annotate outliers outside range
for name, line, _ in alg_lines:
    for j, v in enumerate(line):
        if v > Y_HI:
            ax.annotate(
                f"{v:.2f}\u00d7",
                xy=(x[j], Y_HI),
                xytext=(4, -2), textcoords="offset points",
                ha="left", va="top",
                fontsize=5.5, fontweight="bold",
                color=ALG_COLORS[name],
                zorder=11,
            )
            ax.annotate(
                "",
                xy=(x[j], Y_HI - 0.002), xytext=(x[j], Y_HI - 0.025),
                arrowprops=dict(arrowstyle="->", color=ALG_COLORS[name],
                                lw=0.7, shrinkA=0, shrinkB=0),
                zorder=11,
            )
        elif v < Y_LO:
            ax.annotate(
                f"{v:.2f}\u00d7",
                xy=(x[j], Y_LO),
                xytext=(4, 2), textcoords="offset points",
                ha="left", va="bottom",
                fontsize=5.5, fontweight="bold",
                color=ALG_COLORS[name],
                zorder=11,
            )


# ── X-axis ──────────────────────────────────────────────────────────────────
ax.set_xticks(x)
ax.set_xticklabels([f"D={d}" for d in DISTANCES], fontsize=8)
ax.set_xlim(-0.35, n_d - 1 + 0.35)
ax.set_xlabel("Prefetch Distance", fontsize=9, labelpad=3)
ax.set_ylabel("Normalized Speedup over D=1 (\u00d7)")

yticks = [0.90, 0.95, 1.00, 1.05, 1.10, 1.15]
ax.set_yticks(yticks)
ax.set_yticklabels([f"{t:.2f}\u00d7" for t in yticks])


# ── Legend ─────────────────────────────────────────────────────────────────
# Compose legend: 6 algorithm lines + overall
handles = []
for name, _, n_wl in alg_lines:
    handles.append(Line2D(
        [0], [0],
        marker=ALG_MARKERS[name], color=ALG_COLORS[name],
        markersize=5, linewidth=1.3,
        markeredgecolor="white", markeredgewidth=0.4,
        label=f"{name} (n={n_wl})",
    ))
handles.append(Line2D(
    [0], [0],
    marker="o", color="black",
    markersize=6, linewidth=2.2,
    markeredgecolor="white", markeredgewidth=0.6,
    label=f"Overall (n={len(WORKLOADS)})",
))

ax.legend(
    handles=handles, ncol=7, fontsize=6.5,
    loc="lower left", bbox_to_anchor=(0.0, 1.02), frameon=False,
    handlelength=1.8, handleheight=0.9,
    columnspacing=1.2, handletextpad=0.3,
    borderaxespad=0,
)

subplot_label(ax, "(e) Distance Sensitivity", y=-0.40)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_C_distance", out_dir)
plt.close(fig)


print("=== Round 5 §5.4 Distance Sensitivity (nohatch) ===")
print(f"Workloads: {len(WORKLOADS)}  |  Algorithm GMEAN lines:")
for name, line, n in alg_lines:
    vals = " ".join(f"{v:.3f}" for v in line)
    print(f"  {name:6s} (n={n}): {vals}")
print(f"  Overall   (n={len(WORKLOADS)}): " +
      " ".join(f"{v:.3f}" for v in overall))
print(f"\nData range: {y_min:.3f} .. {y_max:.3f}")
print(f"Saved to {out_dir}/proto_r4_54_C_distance.{{pdf,svg}}")
