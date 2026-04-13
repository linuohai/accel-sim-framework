#!/usr/bin/env python3
"""
Round 5 §5.4 — Distance + Storage Sensitivity (single-column, 2x1 stacked).

Forked from round4_54/proto_r4_54_CD_sens.py but re-laid out for a
single-column figure (3.5in wide), with the two panels stacked vertically
instead of side-by-side. Per-algorithm GMEAN lines + bold overall line.

Output: sensitivity.{pdf,svg}
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
from _data import (  # noqa: E402
    DISTANCE_IPC, STORAGE_IPC, DISTANCES, STORAGE_LABELS, SENS_ALGORITHMS,
    sensitivity_normalized, algorithm_gmean_lines, overall_gmean_line,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


# ── Data ────────────────────────────────────────────────────────────────────
dist_wkls = list(DISTANCE_IPC.keys())
dist_norm = sensitivity_normalized(DISTANCE_IPC, dist_wkls)
dist_alg_lines = algorithm_gmean_lines(dist_norm, SENS_ALGORITHMS)
dist_overall = overall_gmean_line(dist_norm)

stor_wkls = list(STORAGE_IPC.keys())
stor_norm = sensitivity_normalized(STORAGE_IPC, stor_wkls)
stor_alg_lines = algorithm_gmean_lines(stor_norm, SENS_ALGORITHMS)
stor_overall = overall_gmean_line(stor_norm)


ALG_COLORS = {
    "BFS":  PALETTE_TOL_BRIGHT[0],
    "SSSP": PALETTE_TOL_BRIGHT[1],
    "BC":   PALETTE_TOL_BRIGHT[2],
    "CC":   PALETTE_TOL_BRIGHT[3],
    "SpMV": PALETTE_TOL_BRIGHT[4],
    "VC":   "#4B4B6A",
}
ALG_MARKERS = {
    "BFS":  "o",
    "SSSP": "s",
    "BC":   "^",
    "CC":   "D",
    "SpMV": "v",
    "VC":   "*",
}


fig, axes = plt.subplots(
    nrows=2, ncols=1,
    figsize=(3.5, 3.4),
    constrained_layout=True,
)


def plot_panel(ax, alg_lines, overall, x, xticklabels, xlabel, ylabel,
               ylo, yhi, yticks, subtitle, clip_upper=None):
    for name, line, _ in alg_lines:
        y_plot = np.minimum(line, clip_upper) if clip_upper else line
        ax.plot(
            x, y_plot,
            marker=ALG_MARKERS[name], color=ALG_COLORS[name],
            markersize=4.0, linewidth=1.0, alpha=0.75,
            markeredgecolor="white", markeredgewidth=0.3,
            zorder=5,
        )
        if clip_upper:
            for j, v in enumerate(line):
                if v > clip_upper:
                    ax.annotate(
                        f"{v:.2f}\u00d7",
                        xy=(x[j], clip_upper),
                        xytext=(2, -1), textcoords="offset points",
                        ha="left", va="top",
                        fontsize=4.5, fontweight="bold",
                        color=ALG_COLORS[name],
                        zorder=11,
                    )
    ax.plot(
        x, overall,
        marker="o", color="black",
        markersize=5.0, linewidth=1.8,
        markeredgecolor="white", markeredgewidth=0.5,
        zorder=10,
    )
    ax.axhline(1.0, color="#888888", linewidth=0.5,
               linestyle=":", alpha=0.7, zorder=1)
    ax.set_xticks(x)
    ax.set_xticklabels(xticklabels, fontsize=6.0)
    ax.set_xlim(-0.3, len(x) - 1 + 0.3)
    ax.set_ylim(ylo, yhi)
    ax.set_yticks(yticks)
    ax.set_yticklabels([f"{t:.2f}\u00d7" for t in yticks])
    ax.tick_params(axis="y", labelsize=6.0, length=2, pad=1)
    ax.tick_params(axis="x", length=2, pad=1)
    ax.set_xlabel(xlabel, fontsize=7, labelpad=1)
    ax.set_ylabel(ylabel, fontsize=7, labelpad=1)
    # Inline panel title top-left, with white bbox
    ax.text(
        0.02, 0.95, subtitle,
        transform=ax.transAxes,
        ha="left", va="top",
        fontsize=6.5, fontweight="bold",
        bbox=dict(facecolor="white", edgecolor="none",
                  pad=1.2, alpha=0.85),
        zorder=11,
    )


# (a) Distance
x_d = np.arange(len(DISTANCES))
plot_panel(
    axes[0], dist_alg_lines, dist_overall,
    x=x_d,
    xticklabels=[f"D={d}" for d in DISTANCES],
    xlabel="Prefetch Distance",
    ylabel="Speedup over D=1",
    ylo=0.95, yhi=1.10,
    yticks=[0.95, 1.00, 1.05, 1.10],
    subtitle="(a) Distance",
    clip_upper=1.10,
)

# (b) Storage
x_s = np.arange(len(STORAGE_LABELS))
plot_panel(
    axes[1], stor_alg_lines, stor_overall,
    x=x_s,
    xticklabels=["S1", "S2", "S3", "S4"],  # compact labels
    xlabel="Per-SM Storage",
    ylabel="Speedup over S1",
    ylo=0.99, yhi=1.04,
    yticks=[0.99, 1.01, 1.02, 1.04],
    subtitle="(b) Storage",
    clip_upper=1.04,
)


# ── Legend shared above figure ────────────────────────────────────────────
handles = []
for name, _, n_wl in dist_alg_lines:
    handles.append(Line2D(
        [0], [0],
        marker=ALG_MARKERS[name], color=ALG_COLORS[name],
        markersize=4, linewidth=1.0,
        markeredgecolor="white", markeredgewidth=0.3,
        label=f"{name}",
    ))
handles.append(Line2D(
    [0], [0],
    marker="o", color="black",
    markersize=4.5, linewidth=1.8,
    markeredgecolor="white", markeredgewidth=0.4,
    label="Overall",
))

fig.legend(
    handles=handles, ncol=4, fontsize=5.8,
    loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False,
    handlelength=1.2, handleheight=0.8,
    columnspacing=0.8, handletextpad=0.2,
    borderaxespad=0,
)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "sensitivity", out_dir)
plt.close(fig)


print("=== Round 5 §5.4 Sensitivity (single-col) ===")
print(f"Panel (a) Distance overall: " +
      " ".join(f"{v:.3f}" for v in dist_overall))
print(f"Panel (b) Storage  overall: " +
      " ".join(f"{v:.4f}" for v in stor_overall))
print(f"Saved to {out_dir}/sensitivity.{{pdf,svg}}")
