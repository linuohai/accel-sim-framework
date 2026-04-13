#!/usr/bin/env python3
"""Fig B-2: Prefetch Quality Metrics — 15 Representative Workloads + GMEAN.

Three vertically stacked subplots (shared x-axis):
  (a) Coverage (%) — paired bars: Index Coverage, Data Coverage
  (b) Timeliness (%) — paired bars: Index Timeliness, Data Timeliness
  (c) Accuracy (%) — single bar per workload

Selection rationale:
  - web-Google (6): high speedup, demonstrates GRASP strength
  - flickr (5): dense graph, high coverage
  - cc_cit_sym (1): negative case (CC on cit-Patents loses IPC)
  - Extended (2): pann_mis_flickr, pann_color_eco
  - GMEAN: geometric mean of all 27 workloads from B-1
"""

import sys
from pathlib import Path
from collections import OrderedDict

import numpy as np

# ── Project style ────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, save_fig, CB10, legend_below

import matplotlib.pyplot as plt

apply_style()

OUT_DIR = Path(__file__).resolve().parent

# ── Full dataset (from B-1) for GMEAN computation ───────────────────────
# (idx_cov%, data_cov%, idx_time%, data_time%, acc%)
ALL_DATA = OrderedDict([
    # cit-Patents
    ("bfs_cit",      (34.3, 38.3, 94.20, 46.15, 99.88)),
    ("sssp_cit",     (31.6, 37.1, 94.96, 44.47, 99.70)),
    ("bc_cit",       (10.4, 40.4, 97.37, 58.79, 99.59)),
    ("cc_cit",       (-10.1, 10.7, 95.94, 91.69, 47.93)),
    ("spmv_cit",     (7.1, 2.4, 24.40, 55.21, 18.46)),
    ("vc_cit",       (2.7, 5.5, 56.85, 34.06, 23.70)),
    # web-Google
    ("bfs_web",      (24.0, 35.5, 86.47, 77.33, 64.46)),
    ("sssp_web",     (16.8, 31.7, 88.67, 77.36, 66.60)),
    ("bc_web",       (5.1, 38.0, 96.60, 87.88, 64.03)),
    ("cc_web",       (25.6, 36.4, 96.22, 91.26, 60.05)),
    ("spmv_web",     (17.2, 10.8, 57.09, 91.64, 57.48)),
    ("vc_web",       (7.2, 9.7, 61.87, 57.86, 49.78)),
    # flickr
    ("bfs_flickr",   (34.3, 68.7, 91.31, 88.74, 76.37)),
    ("sssp_flickr",  (32.1, 65.9, 92.93, 90.62, 81.68)),
    ("bc_flickr",    (11.4, 63.2, 98.48, 94.54, 85.04)),
    ("cc_flickr",    (39.6, 76.4, 95.54, 93.64, 79.55)),
    ("spmv_flickr",  (26.7, 54.1, 62.16, 89.38, 68.83)),
    # roadNet-CA
    ("bfs_road",     (17.5, 42.8, 88.21, 59.82, 100.00)),
    ("sssp_road",    (8.0, 52.1, 94.22, 68.37, 100.00)),
    ("bc_road",      (16.3, 55.1, 88.41, 75.11, 98.99)),
    ("cc_road",      (17.4, 85.7, 93.35, 89.57, 88.96)),
    ("spmv_road",    (20.9, 78.4, 89.12, 84.16, 87.42)),
    ("vc_road",      (3.6, 58.4, 89.16, 67.81, 68.98)),
    # soc-LJ1
    ("bfs_socLJ",    (20.3, 23.4, 87.54, 84.11, 49.05)),
    ("spmv_socLJ",   (13.1, 3.2, 43.51, 71.06, 44.25)),
    # Pannotia extended
    ("mis_flickr",   (None, None, 58.67, 82.99, 67.91)),
    ("color_eco",    (8.7, 24.9, 98.20, 69.59, 66.57)),
])


def gmean_positive(vals):
    """Geometric mean of positive values only (skip None and <=0)."""
    pos = [v for v in vals if v is not None and v > 0]
    if not pos:
        return 0.0
    return float(np.exp(np.mean(np.log(pos))))


# ── Compute GMEAN across all 27 workloads ────────────────────────────────
all_vals = list(ALL_DATA.values())
gmean_idx_cov   = gmean_positive([d[0] for d in all_vals])
gmean_data_cov  = gmean_positive([d[1] for d in all_vals])
gmean_idx_time  = gmean_positive([d[2] for d in all_vals])
gmean_data_time = gmean_positive([d[3] for d in all_vals])
gmean_acc       = gmean_positive([d[4] for d in all_vals])

# ── Representative 15 workloads + GMEAN ──────────────────────────────────
DATA = OrderedDict([
    # web-Google (6) — high speedup showcase
    ("BFS\nweb",      ALL_DATA["bfs_web"]),
    ("SSSP\nweb",     ALL_DATA["sssp_web"]),
    ("BC\nweb",       ALL_DATA["bc_web"]),
    ("CC\nweb",       ALL_DATA["cc_web"]),
    ("SpMV\nweb",     ALL_DATA["spmv_web"]),
    ("VC\nweb",       ALL_DATA["vc_web"]),

    # flickr (5) — dense graph, high coverage
    ("BFS\nflickr",   ALL_DATA["bfs_flickr"]),
    ("SSSP\nflickr",  ALL_DATA["sssp_flickr"]),
    ("BC\nflickr",    ALL_DATA["bc_flickr"]),
    ("CC\nflickr",    ALL_DATA["cc_flickr"]),
    ("SpMV\nflickr",  ALL_DATA["spmv_flickr"]),

    # Negative case
    ("CC\ncit",       ALL_DATA["cc_cit"]),

    # Extended
    ("MIS\nflickr",   ALL_DATA["mis_flickr"]),
    ("Color\neco",    ALL_DATA["color_eco"]),

    # GMEAN
    ("GMEAN",         (gmean_idx_cov, gmean_data_cov,
                       gmean_idx_time, gmean_data_time, gmean_acc)),
])

# Group boundaries: web(6) | flickr(5) | negative(1) | extended(2) | gmean(1)
GROUP_BOUNDARIES = [6, 11, 12, 14]

# ── Unpack ────────────────────────────────────────────────────────────────
labels = list(DATA.keys())
idx_cov   = [d[0] for d in DATA.values()]
data_cov  = [d[1] for d in DATA.values()]
idx_time  = [d[2] for d in DATA.values()]
data_time = [d[3] for d in DATA.values()]
accuracy  = [d[4] for d in DATA.values()]


def safe_val(v):
    """Convert None to 0 for plotting."""
    return 0.0 if v is None else v


# ── Plot ──────────────────────────────────────────────────────────────────
n = len(labels)
x = np.arange(n)
bar_w = 0.35

fig, axes = plt.subplots(
    3, 1, figsize=figsize_full(aspect=0.55),
    constrained_layout=True, sharex=True,
)
ax_cov, ax_time, ax_acc = axes

# ── (a) Coverage ─────────────────────────────────────────────────────────
bars_ic = ax_cov.bar(x - bar_w / 2, [safe_val(v) for v in idx_cov],
                     bar_w, color=CB10[0], edgecolor="black", linewidth=0.3,
                     label="Index Coverage")
bars_dc = ax_cov.bar(x + bar_w / 2, [safe_val(v) for v in data_cov],
                     bar_w, color=CB10[1], edgecolor="black", linewidth=0.3,
                     label="Data Coverage")

# Mark negative coverage (cc_cit Idx Cov = -10.1%)
for i, v in enumerate(idx_cov):
    if v is not None and v < 0:
        ax_cov.bar(x[i] - bar_w / 2, abs(v), bar_w,
                   color=CB10[0], edgecolor="black", linewidth=0.3,
                   hatch="xx", alpha=0.5)
        ax_cov.text(x[i] - bar_w / 2, 2, f"{v:.0f}%",
                    ha="center", va="bottom", fontsize=5.5, color="red")

# Mark N/A coverage (MIS flickr)
for i, (ic, dc) in enumerate(zip(idx_cov, data_cov)):
    if ic is None:
        ax_cov.text(x[i], 2, "N/A", ha="center", va="bottom",
                    fontsize=5.5, color="gray")

# Highlight GMEAN bar
gmean_idx = n - 1
ax_cov.bar(x[gmean_idx] - bar_w / 2, safe_val(idx_cov[gmean_idx]),
           bar_w, color=CB10[0], edgecolor="black", linewidth=0.6,
           alpha=0.6, hatch="//")
ax_cov.bar(x[gmean_idx] + bar_w / 2, safe_val(data_cov[gmean_idx]),
           bar_w, color=CB10[1], edgecolor="black", linewidth=0.6,
           alpha=0.6, hatch="//")

ax_cov.set_ylabel("Coverage (%)")
ax_cov.set_ylim(-5, 100)
ax_cov.set_title("(a) Coverage (%)", fontsize=8, pad=4)

# ── (b) Timeliness ───────────────────────────────────────────────────────
ax_time.bar(x - bar_w / 2, idx_time, bar_w,
            color=CB10[0], edgecolor="black", linewidth=0.3,
            label="Index Timeliness")
ax_time.bar(x + bar_w / 2, data_time, bar_w,
            color=CB10[1], edgecolor="black", linewidth=0.3,
            label="Data Timeliness")

# GMEAN hatch overlay
ax_time.bar(x[gmean_idx] - bar_w / 2, idx_time[gmean_idx],
            bar_w, color=CB10[0], edgecolor="black", linewidth=0.6,
            alpha=0.6, hatch="//")
ax_time.bar(x[gmean_idx] + bar_w / 2, data_time[gmean_idx],
            bar_w, color=CB10[1], edgecolor="black", linewidth=0.6,
            alpha=0.6, hatch="//")

ax_time.set_ylabel("Timeliness (%)")
ax_time.set_ylim(0, 110)
ax_time.set_title("(b) Timeliness (%)", fontsize=8, pad=4)

# ── (c) Accuracy ─────────────────────────────────────────────────────────
ax_acc.bar(x, accuracy, bar_w * 1.5, color=CB10[2], edgecolor="black",
           linewidth=0.3, label="Accuracy")

# GMEAN hatch overlay
ax_acc.bar(x[gmean_idx], accuracy[gmean_idx], bar_w * 1.5,
           color=CB10[2], edgecolor="black", linewidth=0.6,
           alpha=0.6, hatch="//")

ax_acc.set_ylabel("Accuracy (%)")
ax_acc.set_ylim(0, 110)
ax_acc.set_title("(c) Accuracy (%)", fontsize=8, pad=4)

# ── Shared formatting ────────────────────────────────────────────────────
ax_acc.set_xticks(x)
ax_acc.set_xticklabels(labels, fontsize=6.5, rotation=45, ha="right")

# Vertical group separators
for ax in axes:
    for b in GROUP_BOUNDARIES:
        ax.axvline(x=b - 0.5, color="gray", linestyle="--",
                   linewidth=0.5, alpha=0.5)

# Shared legend below figure
legend_below(fig, axes, ncol=4, y=-0.02, fontsize=7)

# ── Save ──────────────────────────────────────────────────────────────────
save_fig(fig, "proto_figB2_quality_repr", OUT_DIR)
plt.close(fig)

print(f"Saved: {OUT_DIR}/proto_figB2_quality_repr.pdf + .svg")
print(f"Workloads: {n} (including GMEAN)")
print(f"\nGMEAN values:")
print(f"  Idx Coverage:  {gmean_idx_cov:.1f}%")
print(f"  Data Coverage: {gmean_data_cov:.1f}%")
print(f"  Idx Timeliness:  {gmean_idx_time:.1f}%")
print(f"  Data Timeliness: {gmean_data_time:.1f}%")
print(f"  Accuracy:        {gmean_acc:.1f}%")
