#!/usr/bin/env python3
"""Fig B-1: Prefetch Quality Metrics — Full 27 Workloads.

Three vertically stacked subplots (shared x-axis):
  (a) Coverage (%) — paired bars: Index Coverage, Data Coverage
  (b) Timeliness (%) — paired bars: Index Timeliness, Data Timeliness
  (c) Accuracy (%) — single bar per workload

Data priority: D5b config for 23 Gardenia workloads, Default for soc-LJ,
               extra_case_results.csv for MIS/Color.
Idx Coverage from experiment_results.md (approx — does not vary much with TC).
MST excluded (0 prefetches).
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

# ── Data ─────────────────────────────────────────────────────────────────
# Each entry: (idx_cov%, data_cov%, idx_time%, data_time%, acc%)
#
# Coverage: Idx Cov% from experiment_results.md (Default config).
#           Data Cov% from D5b (throttle_control_results.md) where available,
#           otherwise from experiment_results.md / extra_case_results.csv.
# Timeliness & Accuracy: D5b values for 23 Gardenia, Default for soc-LJ,
#                        extra_case for MIS/Color.

DATA = OrderedDict([
    # --- cit-Patents (dir for BFS/SSSP/BC, sym for CC/SpMV/VC) ---
    ("BFS\ncit",      (34.3, 38.3, 94.20, 46.15, 99.88)),
    ("SSSP\ncit",     (31.6, 37.1, 94.96, 44.47, 99.70)),
    ("BC\ncit",       (10.4, 40.4, 97.37, 58.79, 99.59)),
    ("CC\ncit",       (-10.1, 10.7, 95.94, 91.69, 47.93)),
    ("SpMV\ncit",     (7.1, 2.4, 24.40, 55.21, 18.46)),
    ("VC\ncit",       (2.7, 5.5, 56.85, 34.06, 23.70)),

    # --- web-Google (sym) ---
    ("BFS\nweb",      (24.0, 35.5, 86.47, 77.33, 64.46)),
    ("SSSP\nweb",     (16.8, 31.7, 88.67, 77.36, 66.60)),
    ("BC\nweb",       (5.1, 38.0, 96.60, 87.88, 64.03)),
    ("CC\nweb",       (25.6, 36.4, 96.22, 91.26, 60.05)),
    ("SpMV\nweb",     (17.2, 10.8, 57.09, 91.64, 57.48)),
    ("VC\nweb",       (7.2, 9.7, 61.87, 57.86, 49.78)),

    # --- flickr (sym) ---
    ("BFS\nflickr",   (34.3, 68.7, 91.31, 88.74, 76.37)),
    ("SSSP\nflickr",  (32.1, 65.9, 92.93, 90.62, 81.68)),
    ("BC\nflickr",    (11.4, 63.2, 98.48, 94.54, 85.04)),
    ("CC\nflickr",    (39.6, 76.4, 95.54, 93.64, 79.55)),
    ("SpMV\nflickr",  (26.7, 54.1, 62.16, 89.38, 68.83)),

    # --- roadNet-CA (sym) ---
    ("BFS\nroad",     (17.5, 42.8, 88.21, 59.82, 100.00)),
    ("SSSP\nroad",    (8.0, 52.1, 94.22, 68.37, 100.00)),
    ("BC\nroad",      (16.3, 55.1, 88.41, 75.11, 98.99)),
    ("CC\nroad",      (17.4, 85.7, 93.35, 89.57, 88.96)),
    ("SpMV\nroad",    (20.9, 78.4, 89.12, 84.16, 87.42)),
    ("VC\nroad",      (3.6, 58.4, 89.16, 67.81, 68.98)),

    # --- soc-LJ1 (Default config — no D5b yet) ---
    ("BFS\nsocLJ",    (20.3, 23.4, 87.54, 84.11, 49.05)),
    ("SpMV\nsocLJ",   (13.1, 3.2, 43.51, 71.06, 44.25)),

    # --- Pannotia extended ---
    ("MIS\nflickr",   (None, None, 58.67, 82.99, 67.91)),   # coverage N/A
    ("Color\neco",    (8.7, 24.9, 98.20, 69.59, 66.57)),
])

# ── Group separator positions (between algorithm groups) ─────────────────
# Groups: cit(6) | web(6) | flickr(5) | road(6) | socLJ(2) | extra(2)
GROUP_BOUNDARIES = [6, 12, 17, 23, 25]  # indices where new groups start

# ── Unpack ────────────────────────────────────────────────────────────────
labels = list(DATA.keys())
idx_cov   = [d[0] for d in DATA.values()]
data_cov  = [d[1] for d in DATA.values()]
idx_time  = [d[2] for d in DATA.values()]
data_time = [d[3] for d in DATA.values()]
accuracy  = [d[4] for d in DATA.values()]


def safe_val(v):
    """Convert None to 0 for plotting, keeping track for annotation."""
    return 0.0 if v is None else v


# ── Plot ──────────────────────────────────────────────────────────────────
n = len(labels)
x = np.arange(n)
bar_w = 0.35

fig, axes = plt.subplots(
    3, 1, figsize=figsize_full(aspect=0.60),
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
                    ha="center", va="bottom", fontsize=5, color="red")

# Mark N/A coverage
for i, (ic, dc) in enumerate(zip(idx_cov, data_cov)):
    if ic is None:
        ax_cov.text(x[i], 2, "N/A", ha="center", va="bottom",
                    fontsize=5, color="gray")

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
ax_time.set_ylabel("Timeliness (%)")
ax_time.set_ylim(0, 110)
ax_time.set_title("(b) Timeliness (%)", fontsize=8, pad=4)

# ── (c) Accuracy ─────────────────────────────────────────────────────────
ax_acc.bar(x, accuracy, bar_w * 1.5, color=CB10[2], edgecolor="black",
           linewidth=0.3, label="Accuracy")
ax_acc.set_ylabel("Accuracy (%)")
ax_acc.set_ylim(0, 110)
ax_acc.set_title("(c) Accuracy (%)", fontsize=8, pad=4)

# ── Shared formatting ────────────────────────────────────────────────────
ax_acc.set_xticks(x)
ax_acc.set_xticklabels(labels, fontsize=5.5, rotation=45, ha="right")

# Vertical group separators
for ax in axes:
    for b in GROUP_BOUNDARIES:
        ax.axvline(x=b - 0.5, color="gray", linestyle="--",
                   linewidth=0.5, alpha=0.5)

# Shared legend below figure
legend_below(fig, axes, ncol=4, y=-0.02, fontsize=7)

# ── Save ──────────────────────────────────────────────────────────────────
save_fig(fig, "proto_figB1_quality_full", OUT_DIR)
plt.close(fig)

print(f"Saved: {OUT_DIR}/proto_figB1_quality_full.pdf + .svg")
print(f"Workloads: {n}")

# Summary stats
valid_acc = [a for a in accuracy if a is not None]
valid_dc = [d for d in data_cov if d is not None and d > 0]
valid_ic = [d for d in idx_cov if d is not None and d > 0]
print(f"Accuracy  range: {min(valid_acc):.1f}--{max(valid_acc):.1f}%  "
      f"median={np.median(valid_acc):.1f}%")
print(f"Data Cov  range: {min(valid_dc):.1f}--{max(valid_dc):.1f}%  "
      f"median={np.median(valid_dc):.1f}%")
print(f"Idx Time  range: {min(idx_time):.1f}--{max(idx_time):.1f}%  "
      f"median={np.median(idx_time):.1f}%")
print(f"Data Time range: {min(data_time):.1f}--{max(data_time):.1f}%  "
      f"median={np.median(data_time):.1f}%")
