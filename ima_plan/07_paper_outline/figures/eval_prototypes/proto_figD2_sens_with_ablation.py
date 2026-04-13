#!/usr/bin/env python3
"""
Figure D2: 2x2 Sensitivity Composite with Component Ablation.

Subplots:
  (a) Component Ablation  — Index-Only / Data-Only / Full
  (b) Throttle Control    — Default / D5b / T40C200
  (c) Prefetch Distance   — D=1 / D=2 / D=4 / D=8
  (d) Storage Budget      — S1(712B) / S2(1.1K) / S3(1.9K) / S4(3.6K)

Data source: sensitivity_ablation_experiments.md (Exp-A through Exp-D)
"""

import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[4]  # -> /workspace/prefetch
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))

from plot_util import apply_style, CB10, HATCHES, save_fig  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

apply_style()

# ── 8 Representative Workloads ───────────────────────────────────────────────

WORKLOADS = [
    "bfs_cit_dir", "sssp_cit_dir", "bc_cit_dir", "spmv_web_sym",
    "bfs_web_sym", "cc_flickr_sym", "spmv_flickr_sym", "bfs_flickr_sym",
]
X_LABELS = ["BFS-c", "SSS-c", "BC-c", "SpM-w", "BFS-w", "CC-f", "SpM-f", "BFS-f"]

# ── Baseline IPC (no GRASP) ──────────────────────────────────────────────────

BASELINE_IPC = {
    "bfs_cit_dir":     5.3349,
    "sssp_cit_dir":    5.9499,
    "bc_cit_dir":      95.2826,
    "spmv_web_sym":    129.6846,
    "bfs_web_sym":     7.3528,
    "cc_flickr_sym":   46.8674,
    "spmv_flickr_sym": 79.2566,
    "bfs_flickr_sym":  9.7943,
}

# ── Exp-A: Component Ablation IPC ────────────────────────────────────────────
# Source: sensitivity_ablation_experiments.md §Exp-A IPC table

ABLATION_IPC = {
    # workload: (Index-Only, Data-Only, Full GRASP)
    "bfs_cit_dir":     (5.5220,   5.8772,   6.0830),
    "sssp_cit_dir":    (6.0955,   6.5705,   6.5949),
    "bc_cit_dir":      (97.1852,  102.9133, 104.6244),
    "spmv_web_sym":    (158.6675, 130.3898, 181.8048),
    "bfs_web_sym":     (7.8197,   10.5485,  11.4819),
    "cc_flickr_sym":   (64.1420,  71.9062,  94.8873),
    "spmv_flickr_sym": (97.0964,  86.0611,  109.2283),
    "bfs_flickr_sym":  (10.8845,  11.1063,  12.4611),
}

# ── Exp-B: Throttle Control Speedup% ────────────────────────────────────────
# Source: sensitivity_ablation_experiments.md §Exp-B Speedup% table
# (Default, D5b, T40C200)

THROTTLE_SPEEDUP = {
    "bfs_cit_dir":     (+13.6, +13.9, +14.0),
    "sssp_cit_dir":    (+11.0, +10.8, +10.8),
    "bc_cit_dir":      (+9.8,  +9.8,  +9.8),
    "spmv_web_sym":    (+40.1, +36.7, +40.2),
    "bfs_web_sym":     (+56.1, +56.4, +56.2),
    "cc_flickr_sym":   (+138.6, +122.0, +102.5),
    "spmv_flickr_sym": (+38.0, +37.2, +37.8),
    "bfs_flickr_sym":  (+27.0, +27.2, +27.2),
}

# ── Exp-C: Prefetch Distance IPC ────────────────────────────────────────────
# Source: sensitivity_ablation_experiments.md §Exp-C IPC table
# (D=1, D=2, D=4, D=8)

DISTANCE_IPC = {
    "bfs_cit_dir":     (6.0830,  6.0016,  5.8353,  5.6452),
    "sssp_cit_dir":    (6.5949,  6.5631,  6.4006,  6.2253),
    "bc_cit_dir":      (104.6244, 104.5427, 104.0702, 103.1893),
    "spmv_web_sym":    (181.8048, 177.6429, 176.4435, 174.1239),
    "bfs_web_sym":     (11.4819, 11.4908, 11.4573, 11.3891),
    "cc_flickr_sym":   (94.8873, 117.6036, 108.5085, 112.1545),
    "spmv_flickr_sym": (109.2283, 106.7236, 101.5856, 98.6639),
    "bfs_flickr_sym":  (12.4611, 12.6612, 12.5458, 12.4249),
}

# ── Exp-D: Storage Budget IPC ───────────────────────────────────────────────
# Source: sensitivity_ablation_experiments.md §Exp-D IPC table
# (S1=712B, S2=1.1KB, S3=1.9KB, S4=3.6KB)

STORAGE_IPC = {
    "bfs_cit_dir":     (6.0789,  6.0789,  6.0789,  6.0789),
    "sssp_cit_dir":    (6.5920,  6.5920,  6.5920,  6.5920),
    "bc_cit_dir":      (104.6116, 104.6116, 104.6116, 104.6116),
    "spmv_web_sym":    (165.4689, 169.3697, 167.6819, 179.5210),
    "bfs_web_sym":     (11.4964, 11.4964, 11.4964, 11.4964),
    "cc_flickr_sym":   (111.1339, 111.1339, 111.1339, 111.1339),
    "spmv_flickr_sym": (98.2555, 99.5312, 97.0296, 98.1003),
    "bfs_flickr_sym":  (12.4521, 12.4521, 12.4521, 12.4521),
}


# ── Helper: IPC -> Speedup% ─────────────────────────────────────────────────

def ipc_to_speedup(ipc_val, baseline_ipc):
    """Compute speedup percentage: (ipc - baseline) / baseline * 100."""
    return (ipc_val - baseline_ipc) / baseline_ipc * 100.0


# ── Build Figure ─────────────────────────────────────────────────────────────

fig, axes = plt.subplots(2, 2, figsize=(7.0, 3.85), constrained_layout=True)

x = np.arange(len(WORKLOADS))


# ── (a) Component Ablation ───────────────────────────────────────────────────

ax = axes[0, 0]
n_groups_a = 3
width_a = 0.24
labels_a = ["Index-Only", "Data-Only", "Full"]
colors_a = [CB10[0], CB10[1], CB10[3]]
hatches_a = ["//", "\\\\", ""]

for i, (label, color, hatch) in enumerate(zip(labels_a, colors_a, hatches_a)):
    vals = []
    for wl in WORKLOADS:
        ipc = ABLATION_IPC[wl][i]
        vals.append(ipc_to_speedup(ipc, BASELINE_IPC[wl]))
    offset = (i - (n_groups_a - 1) / 2) * width_a
    ax.bar(x + offset, vals, width_a, label=label,
           color=color, hatch=hatch, edgecolor="white", linewidth=0.5)

ax.set_title("(a) Component Ablation", fontsize=8)
ax.set_ylabel("Speedup (%)", fontsize=7)
ax.set_xticks(x)
ax.set_xticklabels(X_LABELS, fontsize=7)
ax.tick_params(axis="y", labelsize=7)
ax.legend(fontsize=6, loc="upper left", ncol=1, framealpha=0.9)


# ── (b) Throttle Control ────────────────────────────────────────────────────

ax = axes[0, 1]
n_groups_b = 3
width_b = 0.24
labels_b = ["Default", "D5b", "T40C200"]
colors_b = [CB10[7], CB10[0], CB10[2]]
hatches_b = ["//", "", "\\\\"]

for i, (label, color, hatch) in enumerate(zip(labels_b, colors_b, hatches_b)):
    vals = [THROTTLE_SPEEDUP[wl][i] for wl in WORKLOADS]
    offset = (i - (n_groups_b - 1) / 2) * width_b
    ax.bar(x + offset, vals, width_b, label=label,
           color=color, hatch=hatch, edgecolor="white", linewidth=0.5)

ax.set_title("(b) Throttle Control", fontsize=8)
ax.set_ylabel("Speedup (%)", fontsize=7)
ax.set_xticks(x)
ax.set_xticklabels(X_LABELS, fontsize=7)
ax.tick_params(axis="y", labelsize=7)
ax.legend(fontsize=6, loc="upper left", ncol=1, framealpha=0.9)


# ── (c) Prefetch Distance ───────────────────────────────────────────────────

ax = axes[1, 0]
n_groups_c = 4
width_c = 0.19
labels_c = ["D=1", "D=2", "D=4", "D=8"]
colors_c = [CB10[0], CB10[1], CB10[2], CB10[3]]

for i, (label, color) in enumerate(zip(labels_c, colors_c)):
    vals = []
    for wl in WORKLOADS:
        ipc = DISTANCE_IPC[wl][i]
        vals.append(ipc_to_speedup(ipc, BASELINE_IPC[wl]))
    offset = (i - (n_groups_c - 1) / 2) * width_c
    ax.bar(x + offset, vals, width_c, label=label,
           color=color, edgecolor="white", linewidth=0.5)

ax.set_title("(c) Prefetch Distance", fontsize=8)
ax.set_ylabel("Speedup (%)", fontsize=7)
ax.set_xticks(x)
ax.set_xticklabels(X_LABELS, fontsize=7)
ax.tick_params(axis="y", labelsize=7)
ax.legend(fontsize=6, loc="upper left", ncol=2, framealpha=0.9)


# ── (d) Storage Budget ──────────────────────────────────────────────────────

ax = axes[1, 1]
n_groups_d = 4
width_d = 0.19
labels_d = ["S1 (712B)", "S2 (1.1K)", "S3 (1.9K)", "S4 (3.6K)"]
colors_d = [CB10[0], CB10[1], CB10[2], CB10[3]]

for i, (label, color) in enumerate(zip(labels_d, colors_d)):
    vals = []
    for wl in WORKLOADS:
        ipc = STORAGE_IPC[wl][i]
        vals.append(ipc_to_speedup(ipc, BASELINE_IPC[wl]))
    offset = (i - (n_groups_d - 1) / 2) * width_d
    ax.bar(x + offset, vals, width_d, label=label,
           color=color, edgecolor="white", linewidth=0.5)

ax.set_title("(d) Storage Budget", fontsize=8)
ax.set_ylabel("Speedup (%)", fontsize=7)
ax.set_xticks(x)
ax.set_xticklabels(X_LABELS, fontsize=7)
ax.tick_params(axis="y", labelsize=7)
ax.legend(fontsize=6, loc="upper left", ncol=2, framealpha=0.9)


# ── Save & Close ─────────────────────────────────────────────────────────────

out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_figD2_sens_with_ablation", out_dir)
plt.close(fig)
print(f"Saved to {out_dir}/proto_figD2_sens_with_ablation.{{pdf,svg}}")
