#!/usr/bin/env python3
"""
Round 5 §5.4 Combined alternative — Throttle 3-metric (nohatch).

1×3 horizontal subplots (full-width, ~7.0 x 2.4):
  (a) IPC speedup (x)     — aggregated per-algorithm lines
  (b) Prefetch Accuracy % — aggregated per-algorithm lines
  (c) Data Coverage %     — aggregated per-algorithm lines

Alternative to having three separate full-width B figures. Uses the same
aggregation scheme as the Distance/Storage sensitivity plots.

Color assignment (3 throttle configs):
  Default  = palette[1] red
  D5b      = palette[0] green (paper version)
  T40C200  = palette[3] yellow
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from plot_util import (  # noqa: E402
    apply_style, save_fig,
    PALETTE_TOL_BRIGHT, subplot_label,
)
from _data import (  # noqa: E402
    THROTTLE_IPC_PCT, THROTTLE_ACC, THROTTLE_COV,
    pct_to_mult, gmean, SENS_ALGORITHMS,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


THROTTLE_CFGS = ["Default", "D5b", "T40C200"]
CFG_COLORS = [
    PALETTE_TOL_BRIGHT[1],  # Default red
    PALETTE_TOL_BRIGHT[0],  # D5b green
    PALETTE_TOL_BRIGHT[3],  # T40C200 yellow
]
CFG_MARKERS = ["s", "o", "^"]
n_c = 3


def per_algorithm_values(data_dict, aggregator):
    """Return list of (alg, values[3]) for each algorithm with workloads
    present in data_dict. aggregator should accept a 1D numpy array and
    return a scalar (gmean or mean)."""
    out = []
    for name, wkls in SENS_ALGORITHMS:
        present = [w for w in wkls if w in data_dict]
        if not present:
            continue
        vals = np.zeros(n_c, dtype=float)
        for ci in range(n_c):
            col = np.array([data_dict[w][ci] for w in present], dtype=float)
            vals[ci] = aggregator(col)
        out.append((name, vals, len(present)))
    return out


def overall_agg(data_dict, aggregator):
    wkls = list(data_dict.keys())
    vals = np.zeros(n_c, dtype=float)
    for ci in range(n_c):
        col = np.array([data_dict[w][ci] for w in wkls], dtype=float)
        vals[ci] = aggregator(col)
    return vals, len(wkls)


# IPC speedup × → gmean across multipliers
ipc_mult = {k: tuple(pct_to_mult(v) for v in THROTTLE_IPC_PCT[k])
            for k in THROTTLE_IPC_PCT}
ipc_alg_lines = per_algorithm_values(ipc_mult, gmean)
ipc_overall, ipc_n = overall_agg(ipc_mult, gmean)

# Accuracy % → arithmetic mean
acc_alg_lines = per_algorithm_values(THROTTLE_ACC, np.mean)
acc_overall, acc_n = overall_agg(THROTTLE_ACC, np.mean)

# Coverage % → arithmetic mean
cov_alg_lines = per_algorithm_values(THROTTLE_COV, np.mean)
cov_overall, cov_n = overall_agg(THROTTLE_COV, np.mean)


# ── Colors & markers for algorithms ────────────────────────────────────────
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
    nrows=1, ncols=3,
    figsize=(7.0, 2.5),
    constrained_layout=True,
)

x = np.arange(n_c)
TICKLABELS = THROTTLE_CFGS


def plot_panel(ax, alg_lines, overall, overall_n, ylabel, ylo, yhi,
               yticks, ytick_fmt, subtitle, ref_y=None):
    for name, line, _ in alg_lines:
        ax.plot(
            x, line,
            marker=ALG_MARKERS[name], color=ALG_COLORS[name],
            markersize=4.5, linewidth=1.1, alpha=0.72,
            markeredgecolor="white", markeredgewidth=0.3,
            zorder=4,
        )
    ax.plot(
        x, overall,
        marker="o", color="black",
        markersize=6.0, linewidth=2.2,
        markeredgecolor="white", markeredgewidth=0.6,
        zorder=10,
    )
    if ref_y is not None:
        ax.axhline(ref_y, color="#888888", linewidth=0.6,
                   linestyle=":", alpha=0.7, zorder=1)
    ax.set_xticks(x)
    ax.set_xticklabels(TICKLABELS, fontsize=6.5)
    ax.set_xlim(-0.3, n_c - 1 + 0.3)
    ax.set_ylim(ylo, yhi)
    ax.set_yticks(yticks)
    ax.set_yticklabels([ytick_fmt.format(t) for t in yticks])
    ax.tick_params(axis="y", labelsize=6.5)
    ax.set_ylabel(ylabel, fontsize=7.5, labelpad=2)
    subplot_label(ax, subtitle, y=-0.40)


# (a) IPC speedup ×
plot_panel(
    axes[0], ipc_alg_lines, ipc_overall, ipc_n,
    ylabel="Speedup over No-PF (\u00d7)",
    ylo=0.95, yhi=1.85,
    yticks=[1.0, 1.2, 1.4, 1.6, 1.8],
    ytick_fmt="{:.1f}\u00d7",
    subtitle="(a) IPC",
    ref_y=1.0,
)

# (b) Accuracy %
plot_panel(
    axes[1], acc_alg_lines, acc_overall, acc_n,
    ylabel="Prefetch Accuracy (%)",
    ylo=40, yhi=102,
    yticks=[40, 60, 80, 100],
    ytick_fmt="{:d}",
    subtitle="(b) Accuracy",
)

# (c) Coverage %
plot_panel(
    axes[2], cov_alg_lines, cov_overall, cov_n,
    ylabel="Data Coverage (%)",
    ylo=0, yhi=80,
    yticks=[0, 20, 40, 60, 80],
    ytick_fmt="{:d}",
    subtitle="(c) Coverage",
)


# ── Legend shared above figure ────────────────────────────────────────────
handles = []
for name, _, n_wl in ipc_alg_lines:
    handles.append(Line2D(
        [0], [0],
        marker=ALG_MARKERS[name], color=ALG_COLORS[name],
        markersize=5, linewidth=1.2,
        markeredgecolor="white", markeredgewidth=0.3,
        label=f"{name}",
    ))
handles.append(Line2D(
    [0], [0],
    marker="o", color="black",
    markersize=5.5, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.5,
    label="Overall GMEAN",
))

fig.legend(
    handles=handles, ncol=7, fontsize=6.5,
    loc="lower center", bbox_to_anchor=(0.5, 1.00), frameon=False,
    handlelength=1.6, handleheight=0.9,
    columnspacing=1.2, handletextpad=0.3,
    borderaxespad=0,
)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_BC_throttle3", out_dir)
plt.close(fig)


print("=== Round 5 §5.4 Throttle 3-metric combined (nohatch) ===")
print(f"Panel (a) IPC ×   Overall (n={ipc_n}): " +
      " ".join(f"{v:.3f}" for v in ipc_overall))
print(f"Panel (b) Acc %  Overall (n={acc_n}): " +
      " ".join(f"{v:.1f}" for v in acc_overall))
print(f"Panel (c) Cov %  Overall (n={cov_n}): " +
      " ".join(f"{v:.1f}" for v in cov_overall))
print(f"\nSaved to {out_dir}/proto_r4_54_BC_throttle3.{{pdf,svg}}")
