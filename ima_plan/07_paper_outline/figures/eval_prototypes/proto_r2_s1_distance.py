#!/usr/bin/env python3
"""
Proto R2 S1 — Prefetch Distance Sensitivity (LINE PLOT).

Visualizes the IPC speedup of 8 representative workloads at four prefetch
distance settings (D=1/2/4/8). Each workload is one line; geomean line is
overlaid in bold black. The recommended D=1 is marked with a vertical
dashed annotation.

Data source: sensitivity_ablation_experiments.md §Exp-C IPC table.
"""

import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[4]  # -> /workspace/prefetch
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))

from plot_util import apply_style, figsize_full, save_fig, CB10  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

apply_style()

# ── Workloads ────────────────────────────────────────────────────────────────

WORKLOADS = [
    "bfs_cit_dir", "sssp_cit_dir", "bc_cit_dir", "spmv_web_sym",
    "bfs_web_sym", "cc_flickr_sym", "spmv_flickr_sym", "bfs_flickr_sym",
]
SHORT = ["BFS-cp", "SSSP-cp", "BC-cp", "SpMV-wg", "BFS-wg", "CC-fl", "SpMV-fl", "BFS-fl"]

# ── Baseline IPC ─────────────────────────────────────────────────────────────

BASELINE_IPC = {
    "bfs_cit_dir":     5.3349,
    "sssp_cit_dir":    5.9499,
    "bc_cit_dir":     95.2826,
    "spmv_web_sym":  129.6846,
    "bfs_web_sym":     7.3528,
    "cc_flickr_sym":  46.8674,
    "spmv_flickr_sym": 79.2566,
    "bfs_flickr_sym":  9.7943,
}

# ── Exp-C: Distance IPC (D=1, 2, 4, 8) ──────────────────────────────────────

DISTANCE_IPC = {
    "bfs_cit_dir":     (6.0830, 6.0016, 5.8353, 5.6452),
    "sssp_cit_dir":    (6.5949, 6.5631, 6.4006, 6.2253),
    "bc_cit_dir":      (104.6244, 104.5427, 104.0702, 103.1893),
    "spmv_web_sym":    (181.8048, 177.6429, 176.4435, 174.1239),
    "bfs_web_sym":     (11.4819, 11.4908, 11.4573, 11.3891),
    "cc_flickr_sym":   (94.8873, 117.6036, 108.5085, 112.1545),
    "spmv_flickr_sym": (109.2283, 106.7236, 101.5856, 98.6639),
    "bfs_flickr_sym":  (12.4611, 12.6612, 12.5458, 12.4249),
}

DISTANCES = [1, 2, 4, 8]

# ── Convert IPC -> Normalized Speedup (1.0 = baseline) ──────────────────────

speedup_norm = {}
for wl in WORKLOADS:
    base = BASELINE_IPC[wl]
    speedup_norm[wl] = tuple(ipc / base for ipc in DISTANCE_IPC[wl])

# Geomean across workloads at each distance
geomean_norm = []
for di in range(len(DISTANCES)):
    vals = np.array([speedup_norm[wl][di] for wl in WORKLOADS])
    geomean_norm.append(float(np.exp(np.mean(np.log(vals)))))

# ── Build Figure ─────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=figsize_full(aspect=0.40), constrained_layout=True)

MARKERS = ["o", "s", "^", "D", "v", "*", "P", "X"]
COLORS = [CB10[0], CB10[1], CB10[3], CB10[4], CB10[5], CB10[6], CB10[7], CB10[8]]

x_pos = np.arange(len(DISTANCES))

# Per-workload lines
for i, wl in enumerate(WORKLOADS):
    ax.plot(
        x_pos, speedup_norm[wl],
        marker=MARKERS[i], color=COLORS[i],
        markersize=4.5, linewidth=1.0,
        markeredgecolor="white", markeredgewidth=0.4,
        label=SHORT[i],
    )

# Geomean line in bold black
ax.plot(
    x_pos, geomean_norm,
    marker="o", color="black",
    markersize=5.5, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.6,
    label="Geomean", zorder=10,
)

# Baseline reference (1.0)
ax.axhline(1.0, color="#888888", linewidth=0.8, linestyle=":", zorder=0)

# Highlight selected D=1
sel_idx = 0
ax.axvline(sel_idx, color="#444444", linewidth=0.9, linestyle="--", zorder=1)
ymin, ymax = 0.85, 1.95
ax.set_ylim(ymin, ymax)
ax.annotate(
    "Selected: D=1",
    xy=(sel_idx, ymax * 0.96),
    xytext=(sel_idx + 0.5, ymax * 0.96),
    fontsize=7, color="#222222",
    arrowprops=dict(arrowstyle="->", color="#444444", lw=0.7),
    ha="left", va="top",
)

# Axes
ax.set_xticks(x_pos)
ax.set_xticklabels([f"D={d}" for d in DISTANCES], fontsize=7)
ax.set_xlabel("Prefetch Distance", fontsize=8)
ax.set_ylabel("Normalized Speedup", fontsize=8)
ax.tick_params(axis="y", labelsize=7)

# Legend outside (right)
ax.legend(
    fontsize=6, loc="center left", bbox_to_anchor=(1.01, 0.5),
    ncol=1, frameon=True, framealpha=0.95, handlelength=1.6,
    columnspacing=0.8, labelspacing=0.35, borderaxespad=0,
)

# ── Save & Close ─────────────────────────────────────────────────────────────

out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r2_s1_distance", out_dir)
plt.close(fig)

# ── Console summary ──────────────────────────────────────────────────────────

print("Distance Sensitivity (Normalized Speedup vs baseline)")
print(f"{'Workload':<18} " + "  ".join(f"D={d:<4}" for d in DISTANCES))
for i, wl in enumerate(WORKLOADS):
    row = "  ".join(f"{speedup_norm[wl][di]:.3f} " for di in range(len(DISTANCES)))
    print(f"{SHORT[i]:<18} {row}")
print(f"{'Geomean':<18} " + "  ".join(f"{g:.3f} " for g in geomean_norm))
print(f"\nSaved to {out_dir}/proto_r2_s1_distance.{{pdf,svg}}")
