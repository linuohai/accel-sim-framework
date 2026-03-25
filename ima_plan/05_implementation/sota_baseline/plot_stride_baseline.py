#!/usr/bin/env python3
"""
Plot SOTA stride baseline results for weekly report / paper.
Generates 4 figures covering all workloads with high information density.

Usage:
    python3 ima_plan/05_implementation/sota_baseline/plot_stride_baseline.py
"""

import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_col, figsize_full, save_fig, CB10, annotate_bars

import matplotlib.pyplot as plt

apply_style()

OUT_DIR = Path(__file__).resolve().parent / "figures"

# ── Data ─────────────────────────────────────────────────────────────────────

WORKLOADS_5 = ["BFS", "SSSP", "SpMV", "CC", "B+Tree"]

# 500k window (primary evidence)
IPC_NOPF_500k = [0.0379, 0.0389, 5.0766, 3.2088, 60.2834]
IPC_INTRA_500k = [0.0394, 0.0405, 5.0572, 3.2028, 60.2202]
UPLIFT_500k = [3.96, 4.11, -0.38, -0.19, -0.10]
ACCURACY_500k = [99.6, 99.7, 8.2, 9.3, 13.8]

# Prefetch statistics (500k)
PF_ISSUED = [277, 582, 3412, 3553, 12714]
PF_USEFUL = [276, 580, 281, 329, 1752]
PF_USELESS = [i - u for i, u in zip(PF_ISSUED, PF_USEFUL)]

# Uplift trend across windows (BFS/SSSP only have all 3)
WINDOWS = ["80k", "200k", "500k"]
BFS_UPLIFT_TREND = [1.34, 2.57, 3.96]
SSSP_UPLIFT_TREND = [1.33, 2.72, 4.11]

# 80k all 5 workloads
UPLIFT_80k = [1.34, 1.33, 0.59, -0.22, -2.63]

# Resource pressure delta (500k, intra - nopf)
RFAIL_DELTA = [None, None, 10958, 150, 1698]  # only for negative workloads
MEMWAIT_DELTA_PP = [None, None, 1.1, 0.1, 0.2]  # percentage points

# ── Figure 1: IPC Uplift all workloads (500k) ───────────────────────────────

fig1, ax1 = plt.subplots(figsize=figsize_full(0.35), constrained_layout=True)

x = np.arange(len(WORKLOADS_5))
colors = [CB10[0] if u > 0 else CB10[2] for u in UPLIFT_500k]
bars = ax1.bar(x, UPLIFT_500k, width=0.55, color=colors, edgecolor="black", linewidth=0.5)

# Annotate values
for i, (bar, val) in enumerate(zip(bars, UPLIFT_500k)):
    h = bar.get_height()
    sign = "+" if val > 0 else ""
    y_pos = h + 0.15 if h >= 0 else h - 0.15
    va = "bottom" if h >= 0 else "top"
    ax1.text(bar.get_x() + bar.get_width() / 2, y_pos,
             f"{sign}{val:.2f}%", ha="center", va=va, fontsize=7, fontweight="bold")

ax1.axhline(0, color="black", linewidth=0.5, linestyle="-")
# Geomean line
geomean = 1.46
ax1.axhline(geomean, color=CB10[1], linewidth=1.0, linestyle="--", label=f"Geomean = +{geomean}%")
ax1.set_xticks(x)
ax1.set_xticklabels(WORKLOADS_5)
ax1.set_ylabel("IPC Uplift (%)")
ax1.set_title("Stride Baseline (intra) IPC Uplift — 500k Window, All Workloads")
ax1.set_ylim(-1.5, 5.5)
ax1.legend(loc="upper right", frameon=True, edgecolor="gray")

save_fig(fig1, "stride_ipc_uplift_500k", OUT_DIR)
plt.close(fig1)

# ── Figure 2: Accuracy + Issued/Useful (full width, 2 subplots) ─────────────

fig2, (ax2a, ax2b) = plt.subplots(1, 2, figsize=figsize_full(0.38), constrained_layout=True)

# 2a: Accuracy per workload
bars_acc = ax2a.bar(x, ACCURACY_500k, width=0.55, color=CB10[0], edgecolor="black", linewidth=0.5)
for bar, val in zip(bars_acc, ACCURACY_500k):
    h = bar.get_height()
    ax2a.text(bar.get_x() + bar.get_width() / 2, h + 1.5,
              f"{val:.1f}%", ha="center", va="bottom", fontsize=6.5, fontweight="bold")
ax2a.set_xticks(x)
ax2a.set_xticklabels(WORKLOADS_5)
ax2a.set_ylabel("Prefetch Accuracy (%)")
ax2a.set_title("(a) Prefetch Accuracy")
ax2a.set_ylim(0, 115)

# 2b: Stacked bar — useful vs useless
bars_useful = ax2b.bar(x, PF_USEFUL, width=0.55, color=CB10[0], edgecolor="black",
                       linewidth=0.5, label="Useful")
bars_useless = ax2b.bar(x, PF_USELESS, width=0.55, bottom=PF_USEFUL, color=CB10[2],
                        edgecolor="black", linewidth=0.5, label="Useless")

# Annotate total issued
for i, (total, useful) in enumerate(zip(PF_ISSUED, PF_USEFUL)):
    ax2b.text(x[i], total + 200, f"{total}", ha="center", va="bottom", fontsize=6)

ax2b.set_xticks(x)
ax2b.set_xticklabels(WORKLOADS_5)
ax2b.set_ylabel("Prefetch Requests")
ax2b.set_title("(b) Issued vs. Useful Prefetches")
ax2b.set_ylim(0, max(PF_ISSUED) * 1.15)
ax2b.legend(loc="upper left", frameon=True, edgecolor="gray")

save_fig(fig2, "stride_accuracy_issued", OUT_DIR)
plt.close(fig2)

# ── Figure 3: Uplift trend BFS/SSSP across windows ──────────────────────────

fig3, ax3 = plt.subplots(figsize=figsize_col(0.72), constrained_layout=True)

x_win = np.arange(len(WINDOWS))
w = 0.3
bars_bfs = ax3.bar(x_win - w / 2, BFS_UPLIFT_TREND, w, color=CB10[0], edgecolor="black",
                   linewidth=0.5, label="BFS")
bars_sssp = ax3.bar(x_win + w / 2, SSSP_UPLIFT_TREND, w, color=CB10[1], edgecolor="black",
                    linewidth=0.5, label="SSSP")

# Annotate
for bars in [bars_bfs, bars_sssp]:
    for bar in bars:
        h = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width() / 2, h + 0.08,
                 f"+{h:.2f}%", ha="center", va="bottom", fontsize=6)

ax3.set_xticks(x_win)
ax3.set_xticklabels(WINDOWS)
ax3.set_xlabel("Simulation Window (cycles)")
ax3.set_ylabel("IPC Uplift (%)")
ax3.set_title("IPC Uplift vs. Window Length")
ax3.set_ylim(0, 5.0)
ax3.legend(loc="upper left", frameon=True, edgecolor="gray")

save_fig(fig3, "stride_uplift_trend", OUT_DIR)
plt.close(fig3)

# ── Figure 4: 80k vs 500k comparison per workload ───────────────────────────

fig4, ax4 = plt.subplots(figsize=figsize_full(0.35), constrained_layout=True)

w4 = 0.3
bars_80 = ax4.bar(x - w4 / 2, UPLIFT_80k, w4, color=CB10[3], edgecolor="black",
                  linewidth=0.5, label="80k window")
bars_500 = ax4.bar(x + w4 / 2, UPLIFT_500k, w4, color=CB10[0], edgecolor="black",
                   linewidth=0.5, label="500k window")

# Annotate 500k values
for bar, val in zip(bars_500, UPLIFT_500k):
    h = bar.get_height()
    sign = "+" if val > 0 else ""
    y_pos = h + 0.12 if h >= 0 else h - 0.12
    va = "bottom" if h >= 0 else "top"
    ax4.text(bar.get_x() + bar.get_width() / 2, y_pos,
             f"{sign}{val:.1f}%", ha="center", va=va, fontsize=6)

ax4.axhline(0, color="black", linewidth=0.5)
ax4.set_xticks(x)
ax4.set_xticklabels(WORKLOADS_5)
ax4.set_ylabel("IPC Uplift (%)")
ax4.set_title("Stride Baseline IPC Uplift — 80k vs. 500k Window")
ax4.set_ylim(-3.5, 5.5)
ax4.legend(loc="lower left", frameon=True, edgecolor="gray")

save_fig(fig4, "stride_80k_vs_500k", OUT_DIR)
plt.close(fig4)

print(f"All figures saved to {OUT_DIR}/")
for f in sorted(OUT_DIR.glob("*")):
    print(f"  {f.name}")
