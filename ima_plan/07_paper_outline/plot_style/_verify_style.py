"""Verify the academic style with realistic paper figures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_util import (
    apply_style, figsize_col, figsize_full, save_fig, CB10,
    COLORS_L1_STATUS, COLORS_STALL, COLORS_IMA_ROLE, annotate_bars,
)

apply_style()

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "_verify"
OUT.mkdir(exist_ok=True)

# ── Test 1: Single-column bar chart (IPC speedup) ────────────────────────────

fig, ax = plt.subplots(figsize=figsize_col())
workloads = ["BFS", "SSSP", "BC", "SpMV", "CC", "Gmean"]
baseline = [1.0] * 6
grasp = [1.32, 1.18, 1.25, 1.41, 1.15, 1.26]

x = np.arange(len(workloads))
w = 0.35
bars1 = ax.bar(x - w/2, baseline, w, label="Baseline", color=CB10[2], edgecolor="black", linewidth=0.3)
bars2 = ax.bar(x + w/2, grasp, w, label="GRASP", color=CB10[0], edgecolor="black", linewidth=0.3)
annotate_bars(ax, bars2, fmt="{:.2f}", offset=0.01)

ax.set_ylabel("Normalized IPC")
ax.set_xticks(x)
ax.set_xticklabels(workloads)
ax.set_ylim(0, 1.65)
ax.axhline(y=1.0, color="black", linewidth=0.4, linestyle="--", alpha=0.5)
ax.legend(loc="upper right")
save_fig(fig, "test_ipc_speedup", OUT, formats=("pdf", "png"))
plt.close(fig)
print("1/4 IPC speedup bar chart — OK")

# ── Test 2: Stacked bar (L1 miss breakdown) ──────────────────────────────────

fig, ax = plt.subplots(figsize=figsize_col())
workloads = ["BFS", "SSSP", "BC", "SpMV", "CC"]
np.random.seed(123)

# Simulate L1 status data (HIT dominant)
raw = {
    "HIT":              [0.45, 0.50, 0.42, 0.55, 0.48],
    "HIT_RESERVED":     [0.12, 0.10, 0.14, 0.08, 0.11],
    "MSHR_HIT":         [0.08, 0.06, 0.09, 0.05, 0.07],
    "MISS":             [0.20, 0.18, 0.22, 0.15, 0.19],
    "SECTOR_MISS":      [0.10, 0.12, 0.08, 0.13, 0.10],
    "RESERVATION_FAIL": [0.05, 0.04, 0.05, 0.04, 0.05],
}

x = np.arange(len(workloads))
bottom = np.zeros(len(workloads))
for status, values in raw.items():
    ax.bar(x, values, 0.6, bottom=bottom, label=status,
           color=COLORS_L1_STATUS[status], edgecolor="black", linewidth=0.3)
    bottom += np.array(values)

ax.set_ylabel("Fraction of L1 Accesses")
ax.set_xticks(x)
ax.set_xticklabels(workloads)
ax.set_ylim(0, 1.05)
ax.legend(loc="upper right", ncol=2, fontsize=5.5)
save_fig(fig, "test_l1_breakdown", OUT, formats=("pdf", "png"))
plt.close(fig)
print("2/4 L1 breakdown stacked bar — OK")

# ── Test 3: Full-width stall breakdown ────────────────────────────────────────

fig, ax = plt.subplots(figsize=figsize_full(aspect=0.35))
workloads = ["BFS", "SSSP", "BC", "SpMV", "CC"]

stall_data = {
    "MEM_WAIT":         [0.35, 0.30, 0.28, 0.40, 0.32],
    "WAIT_MEMBAR":      [0.05, 0.04, 0.06, 0.03, 0.05],
    "WAIT_LDGSTS":      [0.02, 0.01, 0.03, 0.01, 0.02],
    "REG_WAIT":         [0.15, 0.20, 0.18, 0.12, 0.16],
    "PIPE_BUSY":        [0.08, 0.10, 0.07, 0.09, 0.08],
    "CONTROL_HAZARD":   [0.03, 0.02, 0.04, 0.02, 0.03],
    "IBUFFER_EMPTY":    [0.12, 0.15, 0.10, 0.14, 0.13],
    "WAIT_CTA_BARRIER": [0.10, 0.08, 0.12, 0.09, 0.11],
    "WAIT_ATOMIC":      [0.05, 0.05, 0.06, 0.05, 0.05],
    "WAIT_DONE":        [0.05, 0.05, 0.06, 0.05, 0.05],
}

x = np.arange(len(workloads))
bottom = np.zeros(len(workloads))
for reason, values in stall_data.items():
    ax.bar(x, values, 0.6, bottom=bottom, label=reason,
           color=COLORS_STALL[reason], edgecolor="black", linewidth=0.3)
    bottom += np.array(values)

ax.set_ylabel("Fraction of Cycles")
ax.set_xticks(x)
ax.set_xticklabels(workloads)
ax.set_ylim(0, 1.05)
ax.legend(loc="upper right", ncol=5, fontsize=5)
save_fig(fig, "test_stall_breakdown", OUT, formats=("pdf", "png"))
plt.close(fig)
print("3/4 Stall breakdown (full-width) — OK")

# ── Test 4: Line plot (sensitivity study) ─────────────────────────────────────

fig, ax = plt.subplots(figsize=figsize_col())
prefetch_degree = [1, 2, 4, 8, 16]
bfs_speedup  = [1.10, 1.22, 1.32, 1.30, 1.25]
sssp_speedup = [1.05, 1.12, 1.18, 1.20, 1.17]
spmv_speedup = [1.15, 1.28, 1.41, 1.38, 1.30]

ax.plot(prefetch_degree, bfs_speedup, "o-", label="BFS", color=CB10[0], markersize=4)
ax.plot(prefetch_degree, sssp_speedup, "s--", label="SSSP", color=CB10[1], markersize=4)
ax.plot(prefetch_degree, spmv_speedup, "^-.", label="SpMV", color=CB10[3], markersize=4)

ax.set_xlabel("Prefetch Degree")
ax.set_ylabel("Speedup over Baseline")
ax.set_xticks(prefetch_degree)
ax.set_ylim(1.0, 1.5)
ax.axhline(y=1.0, color="black", linewidth=0.4, linestyle="--", alpha=0.5)
ax.legend()
save_fig(fig, "test_sensitivity", OUT, formats=("pdf", "png"))
plt.close(fig)
print("4/4 Sensitivity line plot — OK")

# ── Font embedding check ──────────────────────────────────────────────────────
print(f"\nfont.family: {plt.rcParams['font.family']}")
print(f"font.serif:  {plt.rcParams['font.serif']}")
print(f"pdf.fonttype: {plt.rcParams['pdf.fonttype']}")
print(f"savefig.dpi:  {plt.rcParams['savefig.dpi']}")
print(f"\nAll outputs in: {OUT}/")
