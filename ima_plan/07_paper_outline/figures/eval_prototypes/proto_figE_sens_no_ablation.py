#!/usr/bin/env python3
"""
Proto Fig E — 2x2 Sensitivity Composite (no component ablation).

(a) Throttle IPC Speedup   (b) Throttle Data Coverage
(c) Prefetch Distance       (d) Storage Budget

Data sources:
  - Exp-B (throttle): sensitivity_ablation_experiments.md §Exp-B
  - Exp-C (distance): sensitivity_ablation_experiments.md §Exp-C IPC table
  - Exp-D (storage):  sensitivity_ablation_experiments.md §Exp-D IPC table
"""

import sys
from pathlib import Path
import numpy as np

# ── plot_util import ─────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, CB10, HATCHES, save_fig  # noqa: E402

apply_style()

import matplotlib.pyplot as plt  # noqa: E402

# ── Workload labels ──────────────────────────────────────────────────────────
WKLDS = [
    "bfs_cit_dir", "sssp_cit_dir", "bc_cit_dir", "spmv_web_sym",
    "bfs_web_sym", "cc_flickr_sym", "spmv_flickr_sym", "bfs_flickr_sym",
]
SHORT = ["BFS-c", "SSS-c", "BC-c", "SpM-w", "BFS-w", "CC-f", "SpM-f", "BFS-f"]

# ── Baseline IPC (no prefetcher) ─────────────────────────────────────────────
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

# ═════════════════════════════════════════════════════════════════════════════
# Exp-B: Throttle Control — Speedup% and Data Coverage%
# Source: sensitivity_ablation_experiments.md §Exp-B tables
# ═════════════════════════════════════════════════════════════════════════════

# IPC Speedup% (directly from table)
THROTTLE_SPEEDUP = {
    #                     Default   D5b   T40C200
    "bfs_cit_dir":       ( 13.6,   13.9,   14.0),
    "sssp_cit_dir":      ( 11.0,   10.8,   10.8),
    "bc_cit_dir":        (  9.8,    9.8,    9.8),
    "spmv_web_sym":      ( 40.1,   36.7,   40.2),
    "bfs_web_sym":       ( 56.1,   56.4,   56.2),
    "cc_flickr_sym":     (138.6,  122.0,  102.5),
    "spmv_flickr_sym":   ( 38.0,   37.2,   37.8),
    "bfs_flickr_sym":    ( 27.0,   27.2,   27.2),
}

# Data Coverage% (directly from table)
THROTTLE_COVERAGE = {
    #                     Default   D5b   T40C200
    "bfs_cit_dir":       ( 18.3,   38.3,   38.3),
    "sssp_cit_dir":      ( 17.2,   37.1,   37.0),
    "bc_cit_dir":        (  5.6,   40.4,   40.4),
    "spmv_web_sym":      (  5.9,   10.8,    8.2),
    "bfs_web_sym":       ( 26.9,   35.5,   34.4),
    "cc_flickr_sym":     ( 59.0,   76.4,   71.1),
    "spmv_flickr_sym":   ( 24.2,   54.1,   51.1),
    "bfs_flickr_sym":    ( 48.8,   68.7,   67.6),
}

# ═════════════════════════════════════════════════════════════════════════════
# Exp-C: Prefetch Distance — IPC (D=1,2,4,8)
# Source: sensitivity_ablation_experiments.md §Exp-C IPC table
# ═════════════════════════════════════════════════════════════════════════════

DIST_IPC = {
    #                     D=1        D=2        D=4        D=8
    "bfs_cit_dir":     (  6.0830,   6.0016,   5.8353,   5.6452),
    "sssp_cit_dir":    (  6.5949,   6.5631,   6.4006,   6.2253),
    "bc_cit_dir":      (104.6244, 104.5427, 104.0702, 103.1893),
    "spmv_web_sym":    (181.8048, 177.6429, 176.4435, 174.1239),
    "bfs_web_sym":     ( 11.4819,  11.4908,  11.4573,  11.3891),
    "cc_flickr_sym":   ( 94.8873, 117.6036, 108.5085, 112.1545),
    "spmv_flickr_sym": (109.2283, 106.7236, 101.5856,  98.6639),
    "bfs_flickr_sym":  ( 12.4611,  12.6612,  12.5458,  12.4249),
}

# ═════════════════════════════════════════════════════════════════════════════
# Exp-D: Storage Budget — IPC (S1, S2, S3, S4)
# Source: sensitivity_ablation_experiments.md §Exp-D IPC table
# ═════════════════════════════════════════════════════════════════════════════

STORAGE_IPC = {
    #                     S1         S2         S3         S4
    "bfs_cit_dir":     (  6.0789,   6.0789,   6.0789,   6.0789),
    "sssp_cit_dir":    (  6.5920,   6.5920,   6.5920,   6.5920),
    "bc_cit_dir":      (104.6116, 104.6116, 104.6116, 104.6116),
    "spmv_web_sym":    (165.4689, 169.3697, 167.6819, 179.5210),
    "bfs_web_sym":     ( 11.4964,  11.4964,  11.4964,  11.4964),
    "cc_flickr_sym":   (111.1339, 111.1339, 111.1339, 111.1339),
    "spmv_flickr_sym": ( 98.2555,  99.5312,  97.0296,  98.1003),
    "bfs_flickr_sym":  ( 12.4521,  12.4521,  12.4521,  12.4521),
}


# ── Helper: IPC -> Speedup% ─────────────────────────────────────────────────
def ipc_to_speedup(ipc_val, wkld):
    """Convert absolute IPC to Speedup% over baseline."""
    base = BASELINE_IPC[wkld]
    return (ipc_val - base) / base * 100.0


# ── Build figure ─────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(7.0, 3.85), constrained_layout=True)
ax_a, ax_b = axes[0]
ax_c, ax_d = axes[1]

n = len(WKLDS)
x = np.arange(n)

# ── (a) Throttle IPC Speedup ────────────────────────────────────────────────
configs_ab = ["Default", "D5b", "T40C200"]
colors_ab = [CB10[7], CB10[0], CB10[2]]      # gray, blue, green
hatches_ab = ["//", "", "\\\\"]               # Default hatched, D5b solid, T40C200 hatched
bar_w = 0.25

for i, (cfg, col, hat) in enumerate(zip(configs_ab, colors_ab, hatches_ab)):
    vals = [THROTTLE_SPEEDUP[w][i] for w in WKLDS]
    ax_a.bar(x + (i - 1) * bar_w, vals, bar_w, label=cfg,
             color=col, hatch=hat, edgecolor="black", linewidth=0.4)

ax_a.set_ylabel("Speedup (%)", fontsize=7)
ax_a.set_xticks(x)
ax_a.set_xticklabels(SHORT, fontsize=7, rotation=30, ha="right")
ax_a.tick_params(axis="y", labelsize=7)
ax_a.set_title("(a) Throttle: IPC Speedup", fontsize=8)
ax_a.legend(fontsize=6, ncol=3, loc="upper right", framealpha=0.8)

# ── (b) Throttle Data Coverage ──────────────────────────────────────────────
for i, (cfg, col, hat) in enumerate(zip(configs_ab, colors_ab, hatches_ab)):
    vals = [THROTTLE_COVERAGE[w][i] for w in WKLDS]
    ax_b.bar(x + (i - 1) * bar_w, vals, bar_w, label=cfg,
             color=col, hatch=hat, edgecolor="black", linewidth=0.4)

ax_b.set_ylabel("Data Coverage (%)", fontsize=7)
ax_b.set_xticks(x)
ax_b.set_xticklabels(SHORT, fontsize=7, rotation=30, ha="right")
ax_b.tick_params(axis="y", labelsize=7)
ax_b.set_title("(b) Throttle: Data Coverage", fontsize=8)
ax_b.legend(fontsize=6, ncol=3, loc="upper left", framealpha=0.8)

# ── (c) Prefetch Distance ──────────────────────────────────────────────────
dist_labels = ["D=1", "D=2", "D=4", "D=8"]
colors_c = CB10[:4]
bar_w_c = 0.19

for i, (dlbl, col) in enumerate(zip(dist_labels, colors_c)):
    vals = [ipc_to_speedup(DIST_IPC[w][i], w) for w in WKLDS]
    ax_c.bar(x + (i - 1.5) * bar_w_c, vals, bar_w_c, label=dlbl,
             color=col, edgecolor="black", linewidth=0.4)

ax_c.set_ylabel("Speedup (%)", fontsize=7)
ax_c.set_xticks(x)
ax_c.set_xticklabels(SHORT, fontsize=7, rotation=30, ha="right")
ax_c.tick_params(axis="y", labelsize=7)
ax_c.set_title("(c) Prefetch Distance", fontsize=8)
ax_c.legend(fontsize=6, ncol=4, loc="upper right", framealpha=0.8)

# ── (d) Storage Budget ─────────────────────────────────────────────────────
stor_labels = ["S1 (712B)", "S2 (1.1KB)", "S3 (1.9KB)", "S4 (3.6KB)"]
colors_d = CB10[:4]
bar_w_d = 0.19

for i, (slbl, col) in enumerate(zip(stor_labels, colors_d)):
    vals = [ipc_to_speedup(STORAGE_IPC[w][i], w) for w in WKLDS]
    ax_d.bar(x + (i - 1.5) * bar_w_d, vals, bar_w_d, label=slbl,
             color=col, edgecolor="black", linewidth=0.4)

ax_d.set_ylabel("Speedup (%)", fontsize=7)
ax_d.set_xticks(x)
ax_d.set_xticklabels(SHORT, fontsize=7, rotation=30, ha="right")
ax_d.tick_params(axis="y", labelsize=7)
ax_d.set_title("(d) Storage Budget", fontsize=8)
ax_d.legend(fontsize=6, ncol=2, loc="upper right", framealpha=0.8)

# ── Save ─────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_figE_sens_no_ablation", out_dir)
plt.close(fig)
print(f"Saved to {out_dir}/proto_figE_sens_no_ablation.{{pdf,svg}}")
