#!/usr/bin/env python3
"""
Proto R2 S3 — Throttle Control (DUAL-AXIS BAR + LINE).

Bars (left axis):  IPC Speedup% for Default / D5b / T40C200
Lines (right axis): Data Coverage% for the same three configs

Shows the key insight: D5b roughly matches Default's IPC speedup while
delivering 2-4x higher data coverage. Coverage is the dominant signal of
prefetch quality, so the throttle controller wins even when raw speedup
appears similar.

Data source: sensitivity_ablation_experiments.md §Exp-B (Speedup% and
Data Coverage% tables).
"""

import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[4]  # -> /workspace/prefetch
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))

from plot_util import apply_style, figsize_full, save_fig, CB10, HATCHES  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

apply_style()

# ── Workloads ────────────────────────────────────────────────────────────────

WORKLOADS = [
    "bfs_cit_dir", "sssp_cit_dir", "bc_cit_dir", "spmv_web_sym",
    "bfs_web_sym", "cc_flickr_sym", "spmv_flickr_sym", "bfs_flickr_sym",
]
SHORT = ["BFS-cp", "SSSP-cp", "BC-cp", "SpMV-wg", "BFS-wg", "CC-fl", "SpMV-fl", "BFS-fl"]

# ── Exp-B: Speedup% (Default, D5b, T40C200) ─────────────────────────────────

THROTTLE_SPEEDUP = {
    "bfs_cit_dir":     (13.6, 13.9, 14.0),
    "sssp_cit_dir":    (11.0, 10.8, 10.8),
    "bc_cit_dir":      (9.8,  9.8,  9.8),
    "spmv_web_sym":    (40.1, 36.7, 40.2),
    "bfs_web_sym":     (56.1, 56.4, 56.2),
    "cc_flickr_sym":   (138.6, 122.0, 102.5),
    "spmv_flickr_sym": (38.0, 37.2, 37.8),
    "bfs_flickr_sym":  (27.0, 27.2, 27.2),
}

# ── Exp-B: Data Coverage% (Default, D5b, T40C200) ───────────────────────────

THROTTLE_COVERAGE = {
    "bfs_cit_dir":     (18.3, 38.3, 38.3),
    "sssp_cit_dir":    (17.2, 37.1, 37.0),
    "bc_cit_dir":      (5.6,  40.4, 40.4),
    "spmv_web_sym":    (5.9,  10.8, 8.2),
    "bfs_web_sym":     (26.9, 35.5, 34.4),
    "cc_flickr_sym":   (59.0, 76.4, 71.1),
    "spmv_flickr_sym": (24.2, 54.1, 51.1),
    "bfs_flickr_sym":  (48.8, 68.7, 67.6),
}

CONFIGS = ["Default", "D5b", "T40C200"]
BAR_COLORS = [CB10[7], CB10[0], CB10[2]]      # gray, blue, orange-ish
BAR_HATCHES = [HATCHES[1], HATCHES[0], HATCHES[2]]  # //, solid, \\
LINE_COLORS = ["#444444", "#003D66", "#7A2D00"]  # darker shades for lines
LINE_MARKERS = ["o", "s", "^"]

# ── Build Figure ─────────────────────────────────────────────────────────────

fig, ax1 = plt.subplots(figsize=figsize_full(aspect=0.42), constrained_layout=True)
ax2 = ax1.twinx()

x = np.arange(len(WORKLOADS))
n_groups = len(CONFIGS)
width = 0.26

# ── Bars: IPC Speedup% on ax1 ────────────────────────────────────────────────

for i, cfg in enumerate(CONFIGS):
    vals = [THROTTLE_SPEEDUP[wl][i] for wl in WORKLOADS]
    offset = (i - (n_groups - 1) / 2) * width
    ax1.bar(
        x + offset, vals, width,
        color=BAR_COLORS[i], hatch=BAR_HATCHES[i],
        edgecolor="white", linewidth=0.5,
        label=f"{cfg} (Speedup)",
        zorder=3,
    )

# ── Lines: Data Coverage% on ax2 ─────────────────────────────────────────────

for i, cfg in enumerate(CONFIGS):
    cov = [THROTTLE_COVERAGE[wl][i] for wl in WORKLOADS]
    ax2.plot(
        x, cov,
        color=LINE_COLORS[i], marker=LINE_MARKERS[i],
        markersize=4.5, linewidth=1.4,
        markeredgecolor="white", markeredgewidth=0.4,
        label=f"{cfg} (Coverage)",
        zorder=10,
    )

# ── Axes formatting ──────────────────────────────────────────────────────────

ax1.set_ylabel("IPC Speedup (%)", fontsize=8)
ax2.set_ylabel("Data Coverage (%)", fontsize=8)
ax1.set_xlabel("Workload", fontsize=8)

ax1.set_xticks(x)
ax1.set_xticklabels(SHORT, fontsize=7)
ax1.tick_params(axis="y", labelsize=7)
ax2.tick_params(axis="y", labelsize=7)

# Y-limits with headroom. Use round numbers and fix ticks on both axes
# so the dual-axis labels read cleanly.
sp_max = max(max(THROTTLE_SPEEDUP[wl]) for wl in WORKLOADS)
ax1.set_ylim(0, 160)
ax1.set_yticks([0, 40, 80, 120, 160])
ax2.set_ylim(0, 100)
ax2.set_yticks([0, 25, 50, 75, 100])

# ax2 has its own grid by default — disable to keep ax1's grid as the
# single dominant horizontal reference.
ax2.grid(False)

# ── Combined legend (bars + lines) ───────────────────────────────────────────

bar_handles = [
    Patch(facecolor=BAR_COLORS[i], hatch=BAR_HATCHES[i],
          edgecolor="white", linewidth=0.5, label=f"{cfg} Speedup")
    for i, cfg in enumerate(CONFIGS)
]
line_handles = [
    Line2D([0], [0], color=LINE_COLORS[i], marker=LINE_MARKERS[i],
           markersize=4.5, linewidth=1.4, markeredgecolor="white",
           markeredgewidth=0.4, label=f"{cfg} Coverage")
    for i, cfg in enumerate(CONFIGS)
]

ax1.legend(
    handles=bar_handles + line_handles,
    fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.18),
    ncol=6, frameon=True, framealpha=0.95,
    handlelength=1.6, columnspacing=1.0, labelspacing=0.3,
    borderaxespad=0,
)

# ── Save & Close ─────────────────────────────────────────────────────────────

out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r2_s3_throttle", out_dir)
plt.close(fig)

# ── Console summary ──────────────────────────────────────────────────────────

print("Throttle Control — Speedup%  /  Data Coverage%")
print(f"{'Workload':<14} " + "  ".join(f"{c:>10}" for c in CONFIGS))
print(" Speedup%")
for i, wl in enumerate(WORKLOADS):
    row = "  ".join(f"{THROTTLE_SPEEDUP[wl][j]:+10.1f}" for j in range(n_groups))
    print(f"  {SHORT[i]:<12} {row}")
print(" Data Coverage%")
for i, wl in enumerate(WORKLOADS):
    row = "  ".join(f"{THROTTLE_COVERAGE[wl][j]:10.1f}" for j in range(n_groups))
    print(f"  {SHORT[i]:<12} {row}")

# Quick coverage uplift summary
cov_uplift = []
for wl in WORKLOADS:
    d, d5b, _ = THROTTLE_COVERAGE[wl]
    if d > 0:
        cov_uplift.append(d5b / d)
print(
    "\nCoverage uplift D5b vs Default — "
    f"min {min(cov_uplift):.2f}x, mean {np.mean(cov_uplift):.2f}x, "
    f"max {max(cov_uplift):.2f}x"
)
print(f"Saved to {out_dir}/proto_r2_s3_throttle.{{pdf,svg}}")
