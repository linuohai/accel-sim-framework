#!/usr/bin/env python3
"""
Proto R2 S2 — Storage Budget Sensitivity (LINE PLOT with annotation).

Shows IPC speedup at four storage budgets (S1=712B, S2=1.1KB, S3=1.9KB,
S4=3.6KB) for 8 representative workloads. The key insight is that 6/8
workloads are essentially flat (no benefit from larger storage); only
SpMV-wg shows clear improvement with larger CT/PRB capacity. The
recommended S1 is annotated with an arrow.

Data source: sensitivity_ablation_experiments.md §Exp-D IPC table.
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

# ── Exp-D: Storage IPC (S1, S2, S3, S4) ─────────────────────────────────────

STORAGE_IPC = {
    "bfs_cit_dir":     (6.0789, 6.0789, 6.0789, 6.0789),
    "sssp_cit_dir":    (6.5920, 6.5920, 6.5920, 6.5920),
    "bc_cit_dir":      (104.6116, 104.6116, 104.6116, 104.6116),
    "spmv_web_sym":    (165.4689, 169.3697, 167.6819, 179.5210),
    "bfs_web_sym":     (11.4964, 11.4964, 11.4964, 11.4964),
    "cc_flickr_sym":   (111.1339, 111.1339, 111.1339, 111.1339),
    "spmv_flickr_sym": (98.2555, 99.5312, 97.0296, 98.1003),
    "bfs_flickr_sym":  (12.4521, 12.4521, 12.4521, 12.4521),
}

STORAGE_LABELS = ["S1\n712 B", "S2\n1.1 KB", "S3\n1.9 KB", "S4\n3.6 KB"]
STORAGE_BYTES = [712, 1126, 1946, 3686]  # informational only

# ── Convert IPC -> Normalized Speedup (1.0 = baseline) ──────────────────────

speedup_norm = {}
for wl in WORKLOADS:
    base = BASELINE_IPC[wl]
    speedup_norm[wl] = tuple(ipc / base for ipc in STORAGE_IPC[wl])

# Geomean across workloads at each storage budget
geomean_norm = []
for si in range(len(STORAGE_LABELS)):
    vals = np.array([speedup_norm[wl][si] for wl in WORKLOADS])
    geomean_norm.append(float(np.exp(np.mean(np.log(vals)))))

# ── Build Figure ─────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=figsize_full(aspect=0.40), constrained_layout=True)

MARKERS = ["o", "s", "^", "D", "v", "*", "P", "X"]
COLORS = [CB10[0], CB10[1], CB10[3], CB10[4], CB10[5], CB10[6], CB10[7], CB10[8]]

x_pos = np.arange(len(STORAGE_LABELS))

# Per-workload lines. Highlight SpMV-wg (the counterexample) with thicker line.
for i, wl in enumerate(WORKLOADS):
    is_spmv_wg = (wl == "spmv_web_sym")
    ax.plot(
        x_pos, speedup_norm[wl],
        marker=MARKERS[i], color=COLORS[i],
        markersize=4.8 if is_spmv_wg else 4.0,
        linewidth=1.6 if is_spmv_wg else 1.0,
        markeredgecolor="white", markeredgewidth=0.4,
        label=SHORT[i],
        zorder=8 if is_spmv_wg else 5,
    )

# Geomean line in bold black
ax.plot(
    x_pos, geomean_norm,
    marker="o", color="black",
    markersize=5.5, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.6,
    label="Geomean", zorder=10,
)

# Baseline reference
ax.axhline(1.0, color="#888888", linewidth=0.8, linestyle=":", zorder=0)

# Y-limits leave headroom for annotation
ymin, ymax = 0.95, 1.65
ax.set_ylim(ymin, ymax)

# Highlight selected S1
sel_idx = 0
ax.axvline(sel_idx, color="#444444", linewidth=0.9, linestyle="--", zorder=1)

# Arrow annotation pointing at the S1 geomean point.
# Place text in upper-left so the arrow stays inside the empty top area
# and does not cross the SpMV-wg line.
ax.annotate(
    "Selected: S1 (712 B)\n6/8 workloads flat",
    xy=(sel_idx + 0.02, geomean_norm[0] + 0.005),
    xytext=(sel_idx + 0.35, 1.55),
    fontsize=7, color="#222222",
    arrowprops=dict(arrowstyle="->", color="#444444", lw=0.7,
                    connectionstyle="arc3,rad=-0.15"),
    ha="left", va="center",
    bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
              edgecolor="none", alpha=0.85),
)

# Axes
ax.set_xticks(x_pos)
ax.set_xticklabels(STORAGE_LABELS, fontsize=7)
ax.set_xlabel("Per-SM Storage Budget", fontsize=8)
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
save_fig(fig, "proto_r2_s2_storage", out_dir)
plt.close(fig)

# ── Console summary ──────────────────────────────────────────────────────────

print("Storage Budget Sensitivity (Normalized Speedup vs baseline)")
print(f"{'Workload':<18} " + "  ".join(f"{lbl.replace(chr(10), ' '):<10}" for lbl in STORAGE_LABELS))
for i, wl in enumerate(WORKLOADS):
    row = "  ".join(f"{speedup_norm[wl][si]:.3f}     " for si in range(len(STORAGE_LABELS)))
    print(f"{SHORT[i]:<18} {row}")
print(f"{'Geomean':<18} " + "  ".join(f"{g:.3f}     " for g in geomean_norm))

# Quick flat-vs-varying tally
flat_count = sum(1 for wl in WORKLOADS if max(speedup_norm[wl]) - min(speedup_norm[wl]) < 1e-4)
print(f"\nFlat workloads (no variance): {flat_count}/{len(WORKLOADS)}")
print(f"Saved to {out_dir}/proto_r2_s2_storage.{{pdf,svg}}")
