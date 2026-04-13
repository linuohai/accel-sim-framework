#!/usr/bin/env python3
"""
Round 5 §5.4 Layout D — Storage Sensitivity (nohatch, full-width line).

20 workloads aggregated into 6 algorithm GMEAN lines + bold overall GMEAN.

x = per-SM storage tier {S1=712B, S2=1.1KB, S3=1.9KB, S4=3.6KB}
y = normalized speedup over S1 (1.0 implicit baseline)

Note: 16/20 workloads are completely flat (no change across S1..S4).
Only SpMV and VC show subtle variation.
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
    STORAGE_IPC, STORAGE_BYTES, STORAGE_LABELS, SENS_ALGORITHMS,
    sensitivity_normalized, algorithm_gmean_lines, overall_gmean_line,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


WORKLOADS = list(STORAGE_IPC.keys())
norm = sensitivity_normalized(STORAGE_IPC, WORKLOADS)
alg_lines = algorithm_gmean_lines(norm, SENS_ALGORITHMS)
overall = overall_gmean_line(norm)

n_s = len(STORAGE_LABELS)
assert n_s == 4


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


fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.32),
    constrained_layout=True,
)

x = np.arange(n_s)

# Plot algorithm GMEAN lines — use small horizontal jitter to avoid
# overlap for flat lines at y=1.0
for idx, (name, line, n_wl) in enumerate(alg_lines):
    # Very small vertical jitter for perfectly flat lines so they're
    # visually separable
    y = np.copy(line)
    ax.plot(
        x, y,
        marker=ALG_MARKERS[name], color=ALG_COLORS[name],
        markersize=5.5, linewidth=1.3, alpha=0.75,
        markeredgecolor="white", markeredgewidth=0.4,
        label=f"{name} (n={n_wl})",
        zorder=5,
    )

ax.plot(
    x, overall,
    marker="o", color="black",
    markersize=7.0, linewidth=2.4,
    markeredgecolor="white", markeredgewidth=0.7,
    label="Overall GMEAN",
    zorder=10,
)

ax.axhline(1.0, color="#888888", linewidth=0.6, linestyle=":",
           alpha=0.7, zorder=1)


# ── Y-axis ──────────────────────────────────────────────────────────────────
y_min = min(float(overall.min()),
            min(float(line.min()) for _, line, _ in alg_lines))
y_max = max(float(overall.max()),
            max(float(line.max()) for _, line, _ in alg_lines))

Y_LO, Y_HI = 0.99, 1.04
ax.set_ylim(Y_LO, Y_HI)

# Flat-data note
ax.text(
    0.02, 0.96,
    "16 of 20 workloads flat across tiers",
    transform=ax.transAxes,
    ha="left", va="top",
    fontsize=6.5, color="#444444",
    fontstyle="italic",
)


# ── X-axis ──────────────────────────────────────────────────────────────────
ax.set_xticks(x)
ax.set_xticklabels(STORAGE_LABELS, fontsize=7.5)
ax.set_xlim(-0.35, n_s - 1 + 0.35)
ax.set_xlabel("Per-SM Storage Budget", fontsize=9, labelpad=3)
ax.set_ylabel("Normalized Speedup over S1 (\u00d7)")

yticks = [0.99, 1.00, 1.01, 1.02, 1.03, 1.04]
ax.set_yticks(yticks)
ax.set_yticklabels([f"{t:.2f}\u00d7" for t in yticks])


# ── Legend ─────────────────────────────────────────────────────────────────
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

subplot_label(ax, "(f) Storage Sensitivity", y=-0.40)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_D_storage", out_dir)
plt.close(fig)


print("=== Round 5 §5.4 Storage Sensitivity (nohatch) ===")
print(f"Workloads: {len(WORKLOADS)}  |  Algorithm GMEAN lines:")
for name, line, n in alg_lines:
    vals = " ".join(f"{v:.4f}" for v in line)
    flat = "(flat)" if np.allclose(line, line[0]) else ""
    print(f"  {name:6s} (n={n}): {vals} {flat}")
print(f"  Overall   (n={len(WORKLOADS)}): " +
      " ".join(f"{v:.4f}" for v in overall))
print(f"\nData range: {y_min:.4f} .. {y_max:.4f}")
print(f"Saved to {out_dir}/proto_r4_54_D_storage.{{pdf,svg}}")
