#!/usr/bin/env python3
"""
Round 4 §5.4 Layout A: 2x2 Sensitivity + Ablation Composite.

Subplots:
  (a) Prefetch Distance sensitivity (line plot, x = D=1..8)
  (b) Storage Budget sensitivity     (line plot, x = S1..S4)
  (c) Throttle Control               (dual-axis line: speedup% + useless-pf%)
  (d) Component Ablation             (grouped bar: Index/Data/Full)

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT (greens/reds/purples) — no blue/orange
  - HATCHES_DENSE for the ablation bars (B&W readability)
  - GRASP / Full = palette[0] green + solid (HATCHES_DENSE[0])
  - Subplot labels (a)..(d) BELOW axes via subplot_label helper
  - Tight y-axis (~70-80% fill) without flat-line collapse
  - Path depth: parents[5]

Data source:
  ima_plan/06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md
  (Exp-A through Exp-D, IPC + Speedup% + Accuracy tables)
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


# ── Exp-C: Distance IPC (D=1, 2, 4, 8) ───────────────────────────────────────
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


# ── Exp-D: Storage IPC (S1=712B, S2=1.1KB, S3=1.9KB, S4=3.6KB) ──────────────
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


# ── Exp-B: Throttle Speedup% (Default, D5b, T40C200) ────────────────────────
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
# Exp-B: Accuracy% — used to derive Useless-PF% = 100 - accuracy
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
THROTTLE_CFGS = ["Default", "D5b\n(ours)", "T40\nC200"]
THROTTLE_KEYS = ["Default", "D5b", "T40C200"]


# ── Exp-A: Component Ablation IPC (Index-Only, Data-Only, Full GRASP) ───────
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
def ipc_to_speedup_pct(ipc, base):
    return (ipc - base) / base * 100.0


def ipc_to_norm(ipc, base):
    return ipc / base


def gmean_norm(per_wl_tuples, idx):
    vals = np.array([per_wl_tuples[wl][idx] for wl in WORKLOADS])
    return float(np.exp(np.mean(np.log(vals))))


# ── Build Figure ─────────────────────────────────────────────────────────────
fig, axes = plt.subplots(
    nrows=2, ncols=2,
    figsize=(7.0, 4.5),
    constrained_layout=True,
)

# Marker sequence for line plots
MARKERS = ["o", "s", "^", "D", "v", "*", "P", "X"]

# Per-workload + geomean colors:
#   workloads: gray-ish background series
#   geomean (and "this work" markers): GRASP green
WL_COLOR = "#AAAAAA"
GEO_COLOR = PALETTE_TOL_BRIGHT[0]    # green = GRASP/this-work color
ACC_LO_COLOR = PALETTE_TOL_BRIGHT[1]  # red — secondary axis
SEL_LINE_COLOR = "#444444"


# ────────────────────────────────────────────────────────────────────────────
# (a) Prefetch Distance — line plot
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0, 0]

# Compute normalized speedup (1.0 = baseline)
dist_norm = {wl: tuple(ipc_to_norm(v, BASELINE_IPC[wl])
                       for v in DISTANCE_IPC[wl])
             for wl in WORKLOADS}
dist_geom = [gmean_norm(dist_norm, i) for i in range(len(DISTANCES))]

x_d = np.arange(len(DISTANCES))
for i, wl in enumerate(WORKLOADS):
    ax.plot(
        x_d, dist_norm[wl],
        marker=MARKERS[i], color=WL_COLOR,
        markersize=3.6, linewidth=0.8, alpha=0.65,
        markeredgecolor="white", markeredgewidth=0.3,
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

# Tight y-axis (data range ~0.95-1.95). Use 0.92-1.95 to fill ~80%.
y_lo_a, y_hi_a = 0.92, 1.95
ax.set_ylim(y_lo_a, y_hi_a)
ax.annotate(
    "D=1 (sel.)",
    xy=(0, 1.55), xytext=(0.55, 1.78),
    fontsize=6.5, color="#222222",
    arrowprops=dict(arrowstyle="->", color=SEL_LINE_COLOR, lw=0.6),
    ha="left", va="center",
)

ax.set_xticks(x_d)
ax.set_xticklabels([f"D={d}" for d in DISTANCES], fontsize=7)
ax.set_xlabel("Prefetch Distance", fontsize=7.5, labelpad=2)
ax.set_ylabel("Normalized Speedup", fontsize=7.5)
ax.tick_params(axis="y", labelsize=7)
subplot_label(ax, "(a) Prefetch Distance", y=-0.36)


# ────────────────────────────────────────────────────────────────────────────
# (b) Storage Budget — line plot
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0, 1]
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
        markersize=4.5 if is_spmv_wg else 3.6,
        linewidth=1.4 if is_spmv_wg else 0.8,
        alpha=1.0 if is_spmv_wg else 0.55,
        markeredgecolor="white", markeredgewidth=0.3,
        zorder=8 if is_spmv_wg else 3,
    )
ax.plot(
    x_s, stor_geom,
    marker="o", color=GEO_COLOR,
    markersize=5.5, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.6,
    label="Geomean", zorder=10,
)
ax.axhline(1.0, color="#888888", linewidth=0.7, linestyle=":", zorder=1)
ax.axvline(0, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=2)

# Tight y-axis (data ranges 1.0-1.40)
y_lo_b, y_hi_b = 1.00, 1.55
ax.set_ylim(y_lo_b, y_hi_b)
ax.annotate(
    "S1 (sel.)\n6/8 flat",
    xy=(0, stor_geom[0] + 0.015),
    xytext=(0.4, 1.46),
    fontsize=6.5, color="#222222",
    arrowprops=dict(arrowstyle="->", color=SEL_LINE_COLOR, lw=0.6,
                    connectionstyle="arc3,rad=-0.15"),
    ha="left", va="center",
)
# Tag the SpM-wg outlier line
ax.text(
    x_s[-1] + 0.05, stor_norm["spmv_web_sym"][-1] - 0.02,
    "SpM-wg",
    fontsize=6, color=PALETTE_TOL_BRIGHT[2], fontweight="bold",
    ha="left", va="center",
)
ax.set_xticks(x_s)
ax.set_xticklabels(STORAGE_LABELS, fontsize=6.5)
ax.set_xlabel("Per-SM Storage Budget", fontsize=7.5, labelpad=2)
ax.set_ylabel("Normalized Speedup", fontsize=7.5)
ax.tick_params(axis="y", labelsize=7)
subplot_label(ax, "(b) Storage Budget", y=-0.36)


# ────────────────────────────────────────────────────────────────────────────
# (c) Throttle Control — dual-axis (speedup% + useless PF%)
# ────────────────────────────────────────────────────────────────────────────
ax_c = axes[1, 0]
ax_c2 = ax_c.twinx()

# Aggregate across the 8 workloads (geomean for speedup, mean for useless%)
# Speedup% -> use the per-workload mean (arithmetic, not geomean) since values
# include very large outliers (cc_flickr 138%) — we want a representative
# overall trend.
sp_mean = []
upf_mean = []
for ci in range(len(THROTTLE_CFGS)):
    spv = np.array([THROTTLE_SPEEDUP[wl][ci] for wl in WORKLOADS])
    accv = np.array([THROTTLE_ACCURACY[wl][ci] for wl in WORKLOADS])
    sp_mean.append(float(np.mean(spv)))
    upf_mean.append(float(np.mean(100.0 - accv)))

x_c = np.arange(len(THROTTLE_CFGS))

# Speedup% line (left axis, GRASP green)
l1 = ax_c.plot(
    x_c, sp_mean,
    marker="o", color=GEO_COLOR,
    markersize=6.0, linewidth=2.0,
    markeredgecolor="white", markeredgewidth=0.6,
    label="Mean Speedup (%)",
    zorder=10,
)
# Useless PF% line (right axis, red)
l2 = ax_c2.plot(
    x_c, upf_mean,
    marker="s", color=ACC_LO_COLOR,
    markersize=5.5, linewidth=1.6, linestyle="--",
    markeredgecolor="white", markeredgewidth=0.6,
    label="Mean Useless PF (%)",
    zorder=10,
)

# Highlight the selected D5b config
sel_c = 1
ax_c.axvline(sel_c, color=SEL_LINE_COLOR, linewidth=0.9, linestyle="--", zorder=1)

# Annotate values just above each line marker
for xi, sp, up in zip(x_c, sp_mean, upf_mean):
    ax_c.annotate(f"{sp:.0f}%", xy=(xi, sp), xytext=(0, 4),
                  textcoords="offset points",
                  ha="center", va="bottom", fontsize=6.0,
                  color=GEO_COLOR, fontweight="bold")
    ax_c2.annotate(f"{up:.0f}%", xy=(xi, up), xytext=(0, -9),
                   textcoords="offset points",
                   ha="center", va="top", fontsize=6.0,
                   color=ACC_LO_COLOR, fontweight="bold")

# Tight y-limits ~ 70% data fill
ax_c.set_ylim(20, 60)
ax_c.set_yticks([20, 30, 40, 50, 60])
ax_c2.set_ylim(15, 50)
ax_c2.set_yticks([15, 25, 35, 45])
ax_c2.grid(False)

ax_c.set_xticks(x_c)
ax_c.set_xticklabels(THROTTLE_CFGS, fontsize=6.5)
ax_c.set_xlabel("Throttle Configuration", fontsize=7.5, labelpad=2)
ax_c.set_ylabel("Mean Speedup (%)", fontsize=7.5, color=GEO_COLOR)
ax_c2.set_ylabel("Useless PF (%)", fontsize=7.5, color=ACC_LO_COLOR)
ax_c.tick_params(axis="y", labelsize=7, labelcolor=GEO_COLOR)
ax_c2.tick_params(axis="y", labelsize=7, labelcolor=ACC_LO_COLOR)

# Legend (lines) inside upper-left
legend_lines = [
    Line2D([0], [0], color=GEO_COLOR, marker="o", markersize=4.5,
           linewidth=1.6, markeredgecolor="white", markeredgewidth=0.4,
           label="Speedup"),
    Line2D([0], [0], color=ACC_LO_COLOR, marker="s", markersize=4.5,
           linewidth=1.4, linestyle="--", markeredgecolor="white",
           markeredgewidth=0.4, label="Useless PF"),
]
ax_c.legend(handles=legend_lines, fontsize=6.0, frameon=True, framealpha=0.9,
            loc="upper right", handlelength=1.4, borderaxespad=0.4)

subplot_label(ax_c, "(c) Throttle Control", y=-0.36)


# ────────────────────────────────────────────────────────────────────────────
# (d) Component Ablation — grouped bar
# ────────────────────────────────────────────────────────────────────────────
ax_d = axes[1, 1]

ablation_pct = {
    wl: tuple(ipc_to_speedup_pct(v, BASELINE_IPC[wl])
              for v in ABLATION_IPC[wl])
    for wl in WORKLOADS
}

n_groups = 3
bar_w = 0.26
x_d_b = np.arange(len(WORKLOADS))

# Components: Index-Only / Data-Only / Full GRASP
schemes_d = [
    ("Index-Only", PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),  # red
    ("Data-Only",  PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),  # purple
    ("Full GRASP", PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),  # green solid
]

for i, (label, color, hatch) in enumerate(schemes_d):
    vals = [ablation_pct[wl][i] for wl in WORKLOADS]
    offset = (i - (n_groups - 1) / 2) * bar_w
    ax_d.bar(
        x_d_b + offset, vals, bar_w,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        label=label, zorder=3,
    )

ax_d.axhline(0, color="black", linewidth=0.6, zorder=2)

# Tight y-limit (data range -1 to 102%)
ax_d.set_ylim(-5, 120)
ax_d.set_yticks([0, 30, 60, 90, 120])

ax_d.set_xticks(x_d_b)
ax_d.set_xticklabels(SHORT, rotation=45, ha="right", fontsize=6.5)
ax_d.set_ylabel("Speedup (%)", fontsize=7.5)
ax_d.tick_params(axis="y", labelsize=7)

# Legend at top of subplot
legend_d = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black",
          hatch=HATCHES_DENSE[1], linewidth=0.4, label="Index-Only"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[2], edgecolor="black",
          hatch=HATCHES_DENSE[2], linewidth=0.4, label="Data-Only"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black",
          hatch=HATCHES_DENSE[0], linewidth=0.4, label="Full GRASP"),
]
ax_d.legend(handles=legend_d, ncol=3, fontsize=5.5, frameon=False,
            loc="upper left", bbox_to_anchor=(0.0, 1.02),
            handlelength=1.2, columnspacing=0.8, handletextpad=0.3)

subplot_label(ax_d, "(d) Component Ablation", y=-0.55)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_54_A", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.4 Layout A — 2x2 Grid ===")
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
print("(d) Component ablation — mean speedup% per scheme:")
for i, (label, _, _) in enumerate(schemes_d):
    vals = [ablation_pct[wl][i] for wl in WORKLOADS]
    print(f"   {label:<11s}  arith.mean={np.mean(vals):+6.2f}%")
print()
print(f"Saved to {out_dir}/proto_r4_54_A.{{pdf,svg}}")
