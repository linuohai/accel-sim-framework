#!/usr/bin/env python3
"""
Round 4 §5.4 Layout B: 1x4 Horizontal Row Sensitivity + Ablation.

Single row of four narrow panels:
  (a) Prefetch Distance sensitivity (line plot)
  (b) Storage Budget sensitivity     (line plot)
  (c) Throttle Control               (dual-axis line)
  (d) Component Ablation             (grouped bar)

Compared to Layout A (2x2 grid), this layout trades vertical compactness for
horizontal compactness — useful when paragraph flow makes a single wide row
of small multiples natural.

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT (greens/reds/purples) — no blue/orange
  - HATCHES_DENSE for ablation bars
  - GRASP / Full GRASP = green palette[0] + solid HATCHES_DENSE[0]
  - Subplot labels (a)-(d) BELOW axes
  - Tight y-axes (~70-80% data fill)
  - Path depth: parents[5]
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

# round4/ is 5 levels deep from repo root
_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, save_fig,
    PALETTE_TOL_BRIGHT, HATCHES_DENSE, subplot_label,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── 8 Representative Workloads ───────────────────────────────────────────────
WORKLOADS = [
    "bfs_cit_dir", "sssp_cit_dir", "bc_cit_dir", "spmv_web_sym",
    "bfs_web_sym", "cc_flickr_sym", "spmv_flickr_sym", "bfs_flickr_sym",
]
SHORT = ["BFS-cp", "SSSP-cp", "BC-cp", "SpM-wg",
         "BFS-wg", "CC-fl", "SpM-fl", "BFS-fl"]


# ── Baseline IPC ─────────────────────────────────────────────────────────────
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


# ── Exp-C: Distance IPC ─────────────────────────────────────────────────────
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
DISTANCES = [1, 2, 4, 8]


# ── Exp-D: Storage IPC ──────────────────────────────────────────────────────
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
STORAGE_LABELS = ["S1", "S2", "S3", "S4"]


# ── Exp-B: Throttle Speedup% & Accuracy% ────────────────────────────────────
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
THROTTLE_ACCURACY = {
    "bfs_cit_dir":     (99.89, 99.88, 99.88),
    "sssp_cit_dir":    (99.78, 99.70, 99.70),
    "bc_cit_dir":      (99.61, 99.59, 99.53),
    "spmv_web_sym":    (60.46, 57.48, 66.31),
    "bfs_web_sym":     (59.12, 64.46, 66.87),
    "cc_flickr_sym":   (76.84, 79.55, 88.93),
    "spmv_flickr_sym": (69.75, 68.83, 74.00),
    "bfs_flickr_sym":  (71.86, 76.37, 79.21),
}
THROTTLE_CFGS = ["Default", "D5b", "T40C200"]


# ── Exp-A: Component Ablation IPC ───────────────────────────────────────────
ABLATION_IPC = {
    "bfs_cit_dir":     (5.5220,   5.8772,   6.0830),
    "sssp_cit_dir":    (6.0955,   6.5705,   6.5949),
    "bc_cit_dir":      (97.1852,  102.9133, 104.6244),
    "spmv_web_sym":    (158.6675, 130.3898, 181.8048),
    "bfs_web_sym":     (7.8197,   10.5485,  11.4819),
    "cc_flickr_sym":   (64.1420,  71.9062,  94.8873),
    "spmv_flickr_sym": (97.0964,  86.0611,  109.2283),
    "bfs_flickr_sym":  (10.8845,  11.1063,  12.4611),
}


# ── Helpers ─────────────────────────────────────────────────────────────────
def ipc_to_norm(ipc, base):
    return ipc / base


def ipc_to_speedup_pct(ipc, base):
    return (ipc - base) / base * 100.0


def gmean_norm(per_wl_tuples, idx, workloads):
    vals = np.array([per_wl_tuples[wl][idx] for wl in workloads])
    return float(np.exp(np.mean(np.log(vals))))


# ── Build Figure (1x4 row, 7.0 x 2.2) ───────────────────────────────────────
fig, axes = plt.subplots(
    nrows=1, ncols=4,
    figsize=(7.0, 2.4),
    constrained_layout=True,
)

MARKERS = ["o", "s", "^", "D", "v", "*", "P", "X"]
WL_COLOR = "#AAAAAA"
GEO_COLOR = PALETTE_TOL_BRIGHT[0]    # GRASP green
ACC_LO_COLOR = PALETTE_TOL_BRIGHT[1]  # red
SEL_LINE_COLOR = "#444444"


# ────────────────────────────────────────────────────────────────────────────
# (a) Prefetch Distance
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0]
dist_norm = {wl: tuple(ipc_to_norm(v, BASELINE_IPC[wl])
                       for v in DISTANCE_IPC[wl])
             for wl in WORKLOADS}
dist_geom = [gmean_norm(dist_norm, i, WORKLOADS)
             for i in range(len(DISTANCES))]

x_d = np.arange(len(DISTANCES))
for i, wl in enumerate(WORKLOADS):
    ax.plot(
        x_d, dist_norm[wl],
        marker=MARKERS[i], color=WL_COLOR,
        markersize=3.0, linewidth=0.7, alpha=0.6,
        markeredgecolor="white", markeredgewidth=0.25,
        zorder=3,
    )
ax.plot(
    x_d, dist_geom,
    marker="o", color=GEO_COLOR,
    markersize=5.0, linewidth=1.8,
    markeredgecolor="white", markeredgewidth=0.6,
    zorder=10,
)
ax.axhline(1.0, color="#888888", linewidth=0.7, linestyle=":", zorder=1)
ax.axvline(0, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=2)

ax.set_ylim(0.92, 1.95)
ax.set_xticks(x_d)
ax.set_xticklabels([f"{d}" for d in DISTANCES], fontsize=7)
ax.set_xlabel("Distance", fontsize=7, labelpad=2)
ax.set_ylabel("Norm. Speedup", fontsize=7)
ax.tick_params(axis="y", labelsize=6.5)
# Mark the selected D=1 with a small annotation
ax.annotate(
    "D=1\nsel.",
    xy=(0, dist_geom[0] + 0.05),
    xytext=(0.6, 1.78),
    fontsize=5.5, color="#222",
    arrowprops=dict(arrowstyle="->", color=SEL_LINE_COLOR, lw=0.5),
    ha="left", va="center",
)
subplot_label(ax, "(a) Distance", y=-0.42)


# ────────────────────────────────────────────────────────────────────────────
# (b) Storage
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1]
stor_norm = {wl: tuple(ipc_to_norm(v, BASELINE_IPC[wl])
                       for v in STORAGE_IPC[wl])
             for wl in WORKLOADS}
stor_geom = [gmean_norm(stor_norm, i, WORKLOADS)
             for i in range(len(STORAGE_LABELS))]

x_s = np.arange(len(STORAGE_LABELS))
for i, wl in enumerate(WORKLOADS):
    is_spmv_wg = (wl == "spmv_web_sym")
    ax.plot(
        x_s, stor_norm[wl],
        marker=MARKERS[i],
        color=PALETTE_TOL_BRIGHT[2] if is_spmv_wg else WL_COLOR,
        markersize=4.0 if is_spmv_wg else 3.0,
        linewidth=1.3 if is_spmv_wg else 0.7,
        alpha=1.0 if is_spmv_wg else 0.55,
        markeredgecolor="white", markeredgewidth=0.25,
        zorder=8 if is_spmv_wg else 3,
    )
ax.plot(
    x_s, stor_geom,
    marker="o", color=GEO_COLOR,
    markersize=5.0, linewidth=1.8,
    markeredgecolor="white", markeredgewidth=0.6,
    zorder=10,
)
ax.axhline(1.0, color="#888888", linewidth=0.7, linestyle=":", zorder=1)
ax.axvline(0, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=2)

ax.set_ylim(1.00, 1.55)
ax.set_xticks(x_s)
ax.set_xticklabels(STORAGE_LABELS, fontsize=7)
ax.set_xlabel("Storage Budget", fontsize=7, labelpad=2)
ax.set_ylabel("Norm. Speedup", fontsize=7)
ax.tick_params(axis="y", labelsize=6.5)
# Tag SpM-wg outlier line
ax.text(
    x_s[-1], stor_norm["spmv_web_sym"][-1] - 0.03,
    "SpM-wg",
    fontsize=5.5, color=PALETTE_TOL_BRIGHT[2], fontweight="bold",
    ha="right", va="top",
)
subplot_label(ax, "(b) Storage", y=-0.42)


# ────────────────────────────────────────────────────────────────────────────
# (c) Throttle Control — dual axis
# ────────────────────────────────────────────────────────────────────────────
ax_c = axes[2]
ax_c2 = ax_c.twinx()

sp_mean = []
upf_mean = []
for ci in range(len(THROTTLE_CFGS)):
    spv = np.array([THROTTLE_SPEEDUP[wl][ci] for wl in WORKLOADS])
    accv = np.array([THROTTLE_ACCURACY[wl][ci] for wl in WORKLOADS])
    sp_mean.append(float(np.mean(spv)))
    upf_mean.append(float(np.mean(100.0 - accv)))

x_c = np.arange(len(THROTTLE_CFGS))

ax_c.plot(
    x_c, sp_mean,
    marker="o", color=GEO_COLOR,
    markersize=5.5, linewidth=1.8,
    markeredgecolor="white", markeredgewidth=0.5,
    zorder=10,
)
ax_c2.plot(
    x_c, upf_mean,
    marker="s", color=ACC_LO_COLOR,
    markersize=5.0, linewidth=1.4, linestyle="--",
    markeredgecolor="white", markeredgewidth=0.5,
    zorder=10,
)

# Selected D5b vertical
sel_c = 1
ax_c.axvline(sel_c, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=1)

ax_c.set_ylim(20, 60)
ax_c.set_yticks([20, 30, 40, 50, 60])
ax_c2.set_ylim(15, 50)
ax_c2.set_yticks([15, 25, 35, 45])
ax_c2.grid(False)

ax_c.set_xticks(x_c)
ax_c.set_xticklabels(["Def.", "D5b", "T40"], fontsize=7)
ax_c.set_xlabel("Throttle", fontsize=7, labelpad=2)
ax_c.set_ylabel("Speedup (%)", fontsize=7, color=GEO_COLOR)
ax_c2.set_ylabel("Useless PF (%)", fontsize=7, color=ACC_LO_COLOR)
ax_c.tick_params(axis="y", labelsize=6.5, labelcolor=GEO_COLOR)
ax_c2.tick_params(axis="y", labelsize=6.5, labelcolor=ACC_LO_COLOR)

# Inline mini legend
legend_lines = [
    Line2D([0], [0], color=GEO_COLOR, marker="o", markersize=4.0,
           linewidth=1.4, markeredgecolor="white", markeredgewidth=0.4,
           label="Speedup"),
    Line2D([0], [0], color=ACC_LO_COLOR, marker="s", markersize=4.0,
           linewidth=1.2, linestyle="--", markeredgecolor="white",
           markeredgewidth=0.4, label="Useless PF"),
]
ax_c.legend(handles=legend_lines, fontsize=5.5, frameon=False,
            loc="upper right", handlelength=1.2, borderaxespad=0.2,
            handletextpad=0.3, labelspacing=0.2)

subplot_label(ax_c, "(c) Throttle", y=-0.42)


# ────────────────────────────────────────────────────────────────────────────
# (d) Component Ablation
# ────────────────────────────────────────────────────────────────────────────
ax_d = axes[3]

ablation_pct = {
    wl: tuple(ipc_to_speedup_pct(v, BASELINE_IPC[wl])
              for v in ABLATION_IPC[wl])
    for wl in WORKLOADS
}

n_groups = 3
bar_w = 0.27
x_d_b = np.arange(len(WORKLOADS))

schemes_d = [
    ("Index-Only", PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),
    ("Data-Only",  PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),
    ("Full GRASP", PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),
]

for i, (label, color, hatch) in enumerate(schemes_d):
    vals = [ablation_pct[wl][i] for wl in WORKLOADS]
    offset = (i - (n_groups - 1) / 2) * bar_w
    ax_d.bar(
        x_d_b + offset, vals, bar_w,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.35,
        zorder=3,
    )

ax_d.axhline(0, color="black", linewidth=0.6, zorder=2)
ax_d.set_ylim(-5, 120)
ax_d.set_yticks([0, 30, 60, 90, 120])
ax_d.set_xticks(x_d_b)
# Use very short labels (algorithm only) since 8 workloads at single-column
# width can't fit full names. Tag the dataset suffix in the panel title.
SHORT_TINY = ["BFc", "SSc", "BCc", "SMw", "BFw", "CCf", "SMf", "BFf"]
ax_d.set_xticklabels(SHORT_TINY, rotation=45, ha="right", fontsize=5.5)
ax_d.set_ylabel("Speedup (%)", fontsize=7)
ax_d.tick_params(axis="y", labelsize=6.5)
ax_d.set_xlim(-0.7, len(WORKLOADS) - 0.3)

legend_d = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black",
          hatch=HATCHES_DENSE[1], linewidth=0.35, label="Idx"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[2], edgecolor="black",
          hatch=HATCHES_DENSE[2], linewidth=0.35, label="Data"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black",
          hatch=HATCHES_DENSE[0], linewidth=0.35, label="Full"),
]
ax_d.legend(handles=legend_d, ncol=3, fontsize=5.0, frameon=False,
            loc="upper left", bbox_to_anchor=(0.0, 1.02),
            handlelength=1.0, columnspacing=0.6, handletextpad=0.25)

subplot_label(ax_d, "(d) Ablation", y=-0.42)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_B", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.4 Layout B — 1x4 Horizontal Row ===")
print()
print(f"(a) Distance geomean: D=1 -> {dist_geom[0]:.3f}x"
      f" (best D=2 -> {max(dist_geom):.3f}x)")
print(f"(b) Storage  geomean: S1 -> {stor_geom[0]:.3f}x"
      f" (S4 -> {stor_geom[-1]:.3f}x)")
print(f"(c) Throttle: D5b speedup={sp_mean[1]:.1f}%, "
      f"useless={upf_mean[1]:.1f}%")
print(f"(d) Ablation: Full mean={np.mean([ablation_pct[wl][2] for wl in WORKLOADS]):.1f}% "
      f"(Index+Data sum mean="
      f"{np.mean([ablation_pct[wl][0]+ablation_pct[wl][1] for wl in WORKLOADS]):.1f}%)")
print()
print(f"Saved to {out_dir}/proto_r4_54_B.{{pdf,svg}}")
