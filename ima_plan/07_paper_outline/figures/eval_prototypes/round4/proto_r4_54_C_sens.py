#!/usr/bin/env python3
"""
Round 4 §5.4 Layout C (sensitivity panel): 1x3 row of sensitivity sweeps.

Subplots:
  (a) Prefetch Distance sensitivity (line plot, x = D=1..8)
  (b) Storage Budget sensitivity     (line plot, x = S1..S4)
  (c) Throttle Control               (dual-axis: speedup% + useless-pf%)

Layout C splits §5.4 into two figures: this script renders the sensitivity
half (1x3 row); the ablation half is in proto_r4_54_C_abl.py (single column).
This is useful when paper text needs to discuss sensitivity and ablation in
separate paragraphs without forcing them into the same composite figure.

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT (greens/reds/purples) — no blue/orange
  - Subplot labels (a)-(c) BELOW axes via subplot_label helper
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
    PALETTE_TOL_BRIGHT, subplot_label,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


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
STORAGE_LABELS = ["S1\n712 B", "S2\n1.1 KB", "S3\n1.9 KB", "S4\n3.6 KB"]


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
THROTTLE_CFGS = ["Default", "D5b\n(ours)", "T40C200"]
THROTTLE_KEYS = ["Default", "D5b", "T40C200"]


# ── Helpers ─────────────────────────────────────────────────────────────────
def ipc_to_norm(ipc, base):
    return ipc / base


def gmean_norm(per_wl_tuples, idx):
    vals = np.array([per_wl_tuples[wl][idx] for wl in WORKLOADS])
    return float(np.exp(np.mean(np.log(vals))))


# ── Figure (1x3, 7.0 x 2.4) ─────────────────────────────────────────────────
fig, axes = plt.subplots(
    nrows=1, ncols=3,
    figsize=(7.0, 2.5),
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
dist_geom = [gmean_norm(dist_norm, i) for i in range(len(DISTANCES))]

x_d = np.arange(len(DISTANCES))
for i, wl in enumerate(WORKLOADS):
    ax.plot(
        x_d, dist_norm[wl],
        marker=MARKERS[i], color=WL_COLOR,
        markersize=3.4, linewidth=0.8, alpha=0.6,
        markeredgecolor="white", markeredgewidth=0.3,
        label=SHORT[i] if SHORT[i] in ("CC-fl", "SpM-wg", "BFS-cp") else None,
        zorder=3,
    )
ax.plot(
    x_d, dist_geom,
    marker="o", color=GEO_COLOR,
    markersize=5.5, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.6,
    label="Geomean", zorder=10,
)
ax.axhline(1.0, color="#888888", linewidth=0.7, linestyle=":", zorder=1)
ax.axvline(0, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=2)

ax.set_ylim(0.92, 1.95)
ax.set_xticks(x_d)
ax.set_xticklabels([f"D={d}" for d in DISTANCES], fontsize=7)
ax.set_xlabel("Prefetch Distance", fontsize=7.5, labelpad=2)
ax.set_ylabel("Normalized Speedup", fontsize=7.5)
ax.tick_params(axis="y", labelsize=7)

# Inline annotation: selected D=1
ax.annotate(
    "D=1 selected",
    xy=(0, dist_geom[0] + 0.04),
    xytext=(0.5, 1.78),
    fontsize=6.5, color="#222",
    arrowprops=dict(arrowstyle="->", color=SEL_LINE_COLOR, lw=0.6),
    ha="left", va="center",
)
# Mini legend (geomean only — workloads use shared marker key)
legend_a = [
    Line2D([0], [0], color=WL_COLOR, marker="o", markersize=3.5,
           linewidth=0.8, label="Per-workload"),
    Line2D([0], [0], color=GEO_COLOR, marker="o", markersize=5,
           linewidth=1.8, label="Geomean"),
]
ax.legend(handles=legend_a, fontsize=5.5, frameon=False,
          loc="lower right", handlelength=1.4,
          handletextpad=0.3, labelspacing=0.2)
subplot_label(ax, "(a) Prefetch Distance", y=-0.36)


# ────────────────────────────────────────────────────────────────────────────
# (b) Storage Budget
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1]
stor_norm = {wl: tuple(ipc_to_norm(v, BASELINE_IPC[wl])
                       for v in STORAGE_IPC[wl])
             for wl in WORKLOADS}
stor_geom = [gmean_norm(stor_norm, i) for i in range(len(STORAGE_LABELS))]

x_s = np.arange(len(STORAGE_LABELS))
for i, wl in enumerate(WORKLOADS):
    is_spmv_wg = (wl == "spmv_web_sym")
    ax.plot(
        x_s, stor_norm[wl],
        marker=MARKERS[i],
        color=PALETTE_TOL_BRIGHT[2] if is_spmv_wg else WL_COLOR,
        markersize=4.4 if is_spmv_wg else 3.4,
        linewidth=1.5 if is_spmv_wg else 0.8,
        alpha=1.0 if is_spmv_wg else 0.55,
        markeredgecolor="white", markeredgewidth=0.3,
        zorder=8 if is_spmv_wg else 3,
    )
ax.plot(
    x_s, stor_geom,
    marker="o", color=GEO_COLOR,
    markersize=5.5, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.6,
    zorder=10,
)
ax.axhline(1.0, color="#888888", linewidth=0.7, linestyle=":", zorder=1)
ax.axvline(0, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=2)

ax.set_ylim(1.00, 1.55)
ax.set_xticks(x_s)
ax.set_xticklabels(STORAGE_LABELS, fontsize=6.5)
ax.set_xlabel("Per-SM Storage Budget", fontsize=7.5, labelpad=2)
ax.set_ylabel("Normalized Speedup", fontsize=7.5)
ax.tick_params(axis="y", labelsize=7)

ax.annotate(
    "S1 selected\n6/8 flat",
    xy=(0, stor_geom[0] + 0.005),
    xytext=(0.45, 1.46),
    fontsize=6.5, color="#222",
    arrowprops=dict(arrowstyle="->", color=SEL_LINE_COLOR, lw=0.6,
                    connectionstyle="arc3,rad=-0.15"),
    ha="left", va="center",
    bbox=dict(boxstyle="round,pad=0.20", facecolor="white",
              edgecolor="none", alpha=0.85),
)
ax.text(
    x_s[-1] + 0.05, stor_norm["spmv_web_sym"][-1] - 0.02,
    "SpM-wg",
    fontsize=6, color=PALETTE_TOL_BRIGHT[2], fontweight="bold",
    ha="left", va="center",
)
subplot_label(ax, "(b) Storage Budget", y=-0.36)


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
    markersize=6.0, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.6,
    zorder=10,
)
ax_c2.plot(
    x_c, upf_mean,
    marker="s", color=ACC_LO_COLOR,
    markersize=5.5, linewidth=1.6, linestyle="--",
    markeredgecolor="white", markeredgewidth=0.5,
    zorder=10,
)

# Selected D5b vertical
ax_c.axvline(1, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=1)

# Numeric labels above markers
for xi, sp, up in zip(x_c, sp_mean, upf_mean):
    ax_c.annotate(f"{sp:.0f}%", xy=(xi, sp), xytext=(0, 4),
                  textcoords="offset points",
                  ha="center", va="bottom", fontsize=6.0,
                  color=GEO_COLOR, fontweight="bold")
    ax_c2.annotate(f"{up:.0f}%", xy=(xi, up), xytext=(0, -9),
                   textcoords="offset points",
                   ha="center", va="top", fontsize=6.0,
                   color=ACC_LO_COLOR, fontweight="bold")

ax_c.set_ylim(20, 60)
ax_c.set_yticks([20, 30, 40, 50, 60])
ax_c2.set_ylim(15, 50)
ax_c2.set_yticks([15, 25, 35, 45])
ax_c2.grid(False)

ax_c.set_xticks(x_c)
ax_c.set_xticklabels(THROTTLE_CFGS, fontsize=6.5)
ax_c.set_xlabel("Throttle Configuration", fontsize=7.5, labelpad=2)
ax_c.set_ylabel("Speedup (%)", fontsize=7.5, color=GEO_COLOR)
ax_c2.set_ylabel("Useless PF (%)", fontsize=7.5, color=ACC_LO_COLOR)
ax_c.tick_params(axis="y", labelsize=7, labelcolor=GEO_COLOR)
ax_c2.tick_params(axis="y", labelsize=7, labelcolor=ACC_LO_COLOR)

legend_c = [
    Line2D([0], [0], color=GEO_COLOR, marker="o", markersize=4.5,
           linewidth=1.6, markeredgecolor="white", markeredgewidth=0.4,
           label="Speedup"),
    Line2D([0], [0], color=ACC_LO_COLOR, marker="s", markersize=4.5,
           linewidth=1.4, linestyle="--", markeredgecolor="white",
           markeredgewidth=0.4, label="Useless PF"),
]
ax_c.legend(handles=legend_c, fontsize=5.5, frameon=False,
            loc="lower left", handlelength=1.4,
            handletextpad=0.3, labelspacing=0.2)

subplot_label(ax_c, "(c) Throttle Control", y=-0.36)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_C_sens", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.4 Layout C (sensitivity panel) — 1x3 ===")
print()
print("(a) Distance — geomean speedup at D=1..8:")
for d, g in zip(DISTANCES, dist_geom):
    star = "  *" if d == 1 else ""
    print(f"   D={d}  geomean={g:.3f}x{star}")
print()
print("(b) Storage — geomean speedup at S1..S4:")
for lab, g in zip(["S1", "S2", "S3", "S4"], stor_geom):
    star = "  *" if lab == "S1" else ""
    print(f"   {lab}   geomean={g:.3f}x{star}")
print()
print("(c) Throttle — mean Speedup% / Useless-PF% across 8 workloads:")
for cfg, sp, up in zip(THROTTLE_KEYS, sp_mean, upf_mean):
    star = "  *" if cfg == "D5b" else ""
    print(f"   {cfg:<8s}  Speedup={sp:5.1f}%   UselessPF={up:4.1f}%{star}")
print()
print(f"Saved to {out_dir}/proto_r4_54_C_sens.{{pdf,svg}}")
