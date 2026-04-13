#!/usr/bin/env python3
"""
Proto Figure C: SOTA Baseline Comparison (grouped bar chart).

Compares GRASP (D5b) vs 3 SOTA baselines (Snake, CAPS, Spare Register)
across ~15 representative workloads + GMEAN.

Data sources:
  - SOTA speedups: ima_plan/05_implementation/sota_baseline/sota_experiment_results.md
  - GRASP D5b speedups: ima_plan/06_evaluation_plan/throttle_control_results.md
"""

import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, CB10, HATCHES, save_fig

import matplotlib.pyplot as plt

apply_style()

# ── Data (hardcoded from experiment results) ─────────────────────────────────
# Speedup% vs NP baseline for each scheme.
# Order: workloads grouped by algorithm, then dataset.

WORKLOADS = [
    # --- BFS ---
    "bfs\nweb",
    "bfs\nflickr",
    # --- SSSP ---
    "sssp\nweb",
    "sssp\nflickr",
    # --- BC ---
    "bc\nweb",
    "bc\nflickr",
    # --- CC ---
    "cc\nweb",
    "cc\nflickr",
    # --- SpMV ---
    "spmv\nweb",
    "spmv\nflickr",
    # --- VC ---
    "vc\nweb",
    # --- Extended ---
    "mis\nflickr",
    "color\neco",
    "mst\nrmat",
    # --- GMEAN ---
    "GMEAN",
]

# Algorithm group boundaries (index of first workload in each group)
# Used for vertical separator lines.
GROUP_BOUNDS = [0, 2, 4, 6, 8, 10, 11, 14]  # BFS|SSSP|BC|CC|SpMV|VC|Ext|GMEAN
GROUP_LABELS = ["BFS", "SSSP", "BC", "CC", "SpMV", "VC", "Extended", ""]

# Speedup data: Snake, CAPS, Spare Register, GRASP (D5b)
# Sources: sota_experiment_results.md tables, throttle_control_results.md D5b section
data_snake = [
    # BFS: web, flickr
    0.4,  2.0,
    # SSSP: web, flickr
    0.8,  2.3,
    # BC: web, flickr
    8.1,  5.5,
    # CC: web, flickr
    10.7, -0.3,
    # SpMV: web, flickr
    1.5,  2.4,
    # VC: web
    5.2,
    # Extended: MIS flickr, Color eco, MST rmat
    0.0, -1.0, 0.0,
]

data_caps = [
    # BFS: web, flickr
    0.0,  0.0,
    # SSSP: web, flickr
    -0.0, -0.0,
    # BC: web, flickr
    0.1,  0.0,
    # CC: web, flickr
    0.2, -0.6,
    # SpMV: web, flickr
    14.3, -10.0,
    # VC: web
    -1.0,
    # Extended: MIS flickr, Color eco, MST rmat
    -6.0, -1.0, 0.0,
]

data_spare = [
    # BFS: web, flickr
    0.0,  0.0,
    # SSSP: web, flickr
    8.6,  4.3,
    # BC: web, flickr
    8.0,  5.9,
    # CC: web, flickr
    15.5, 7.1,
    # SpMV: web, flickr
    25.8, 11.7,
    # VC: web
    14.3,
    # Extended: MIS flickr, Color eco, MST rmat
    -5.0, 0.0, 0.0,
]

data_grasp = [
    # BFS: web, flickr (D5b)
    56.4, 27.2,
    # SSSP: web, flickr (D5b)
    46.9, 20.0,
    # BC: web, flickr (D5b)
    10.7, 21.9,
    # CC: web, flickr (D5b)
    70.9, 122.0,
    # SpMV: web, flickr (D5b)
    36.7, 37.2,
    # VC: web (D5b)
    1.9,
    # Extended: MIS flickr (D5b), Color eco, MST rmat
    28.0, 0.0, 0.0,
]


def gmean_speedup(values):
    """Geometric mean of (1 + speedup/100) - 1, expressed as %."""
    ratios = [1.0 + v / 100.0 for v in values]
    product = 1.0
    for r in ratios:
        product *= r
    gm = product ** (1.0 / len(ratios))
    return (gm - 1.0) * 100.0


# Append GMEAN for each scheme
data_snake.append(gmean_speedup(data_snake))
data_caps.append(gmean_speedup(data_caps))
data_spare.append(gmean_speedup(data_spare))
data_grasp.append(gmean_speedup(data_grasp))

# ── Scheme definitions ───────────────────────────────────────────────────────
schemes = [
    ("Snake",         data_snake, CB10[2], HATCHES[1]),   # green, //
    ("CAPS",          data_caps,  CB10[4], HATCHES[2]),   # purple, \\
    ("Spare Reg.",    data_spare, CB10[3], HATCHES[3]),   # red, xx
    ("GRASP",         data_grasp, CB10[0], HATCHES[0]),   # blue, solid
]

n_workloads = len(WORKLOADS)
n_schemes = len(schemes)
assert all(len(d) == n_workloads for _, d, _, _ in schemes), \
    f"Data length mismatch: expected {n_workloads}"

# ── Plot (broken y-axis: lower panel for detail, upper for outliers) ─────────
x = np.arange(n_workloads)
bar_width = 0.18
offsets = np.array([-(1.5 * bar_width), -(0.5 * bar_width),
                     (0.5 * bar_width),  (1.5 * bar_width)])

# Break point: most data is in [-15, 60]; cc_flickr GRASP = 122%
BREAK_LO = 65     # top of lower panel
BREAK_HI = 115    # bottom of upper panel
HEIGHT_RATIO = [1, 4.5]  # upper panel much smaller (only shows 122)

fig, (ax_top, ax_bot) = plt.subplots(
    2, 1, sharex=True,
    figsize=figsize_full(aspect=0.42),
    gridspec_kw={"height_ratios": HEIGHT_RATIO, "hspace": 0.04},
    constrained_layout=True,
)

bar_containers_bot = []
bar_containers_top = []
for i, (name, vals, color, hatch) in enumerate(schemes):
    bars_bot = ax_bot.bar(x + offsets[i], vals, bar_width,
                          label=name, color=color, hatch=hatch,
                          edgecolor="black", linewidth=0.4, zorder=3)
    bars_top = ax_top.bar(x + offsets[i], vals, bar_width,
                          color=color, hatch=hatch,
                          edgecolor="black", linewidth=0.4, zorder=3)
    bar_containers_bot.append(bars_bot)
    bar_containers_top.append(bars_top)

# ── Set y-limits for broken axis ────────────────────────────────────────────
data_min = min(min(d) for _, d, _, _ in schemes)
ax_bot.set_ylim(data_min - 3, BREAK_LO)
ax_top.set_ylim(BREAK_HI, 130)

# Disable grid on top panel (only one tick, grid line is visual noise)
ax_top.grid(False)

# Hide spines at the break
ax_top.spines["bottom"].set_visible(False)
ax_bot.spines["top"].set_visible(False)
ax_top.tick_params(bottom=False)

# Draw break marks using physical-size offsets so they look the same
# regardless of panel height.  We use matplotlib's offset-point transform.
from matplotlib.transforms import ScaledTranslation
_pt = fig.dpi_scale_trans  # 1 unit = 1 point

for ax_brk, y_frac in [(ax_top, 0.0), (ax_bot, 1.0)]:
    for x_frac in [0.0, 1.0]:
        # Centre of the break mark in axes coords
        cx, cy = x_frac, y_frac
        dp = 2.5  # half-size in points
        # Convert points to axes-fraction offsets
        inv = ax_brk.transAxes.inverted()
        p0 = inv.transform(ax_brk.transAxes.transform((cx, cy))
                           + np.array([-dp, -dp]))
        p1 = inv.transform(ax_brk.transAxes.transform((cx, cy))
                           + np.array([dp, dp]))
        ax_brk.plot([p0[0], p1[0]], [p0[1], p1[1]],
                    transform=ax_brk.transAxes, color="black",
                    linewidth=0.7, clip_on=False)

# ── Annotate GRASP bars ─────────────────────────────────────────────────────
# For bars in the lower range, annotate on ax_bot; for outliers, on ax_top.
# Bars in the break zone (BREAK_LO < h < BREAK_HI) are clipped in bottom
# panel -- annotate at the clip boundary.
grasp_vals = data_grasp
for j, bar in enumerate(bar_containers_bot[-1]):
    h = grasp_vals[j]
    if abs(h) < 5.0:
        continue  # skip small values to avoid clutter
    if h >= BREAK_HI:
        # Outlier visible in top panel
        bar_top = bar_containers_top[-1][j]
        ax_top.text(bar_top.get_x() + bar_top.get_width() / 2,
                    h + 1.5, f"{h:.0f}",
                    ha="center", va="bottom", fontsize=5.5,
                    fontweight="bold", color=CB10[0])
    elif h > BREAK_LO:
        # In the break zone: bar is clipped at BREAK_LO in bottom panel.
        # Place label just below the clip edge.
        ax_bot.text(bar.get_x() + bar.get_width() / 2,
                    BREAK_LO - 1.5, f"{h:.0f}",
                    ha="center", va="top", fontsize=5.5,
                    fontweight="bold", color=CB10[0])
    else:
        va = "bottom" if h >= 0 else "top"
        y_pos = h + (1.5 if h >= 0 else -1.5)
        ax_bot.text(bar.get_x() + bar.get_width() / 2, y_pos,
                    f"{h:.0f}", ha="center", va=va, fontsize=5.5,
                    fontweight="bold", color=CB10[0])

# ── Annotate notable negative bars (CAPS degradation) ───────────────────────
caps_vals = data_caps
for j, bar in enumerate(bar_containers_bot[1]):  # CAPS is index 1
    h = caps_vals[j]
    if h < -3.0:  # annotate notable negative values
        ax_bot.text(bar.get_x() + bar.get_width() / 2,
                    h - 1.0, f"{h:.0f}",
                    ha="center", va="top", fontsize=5, color=CB10[4])

# ── Vertical group separators (on both panels) ─────────────────────────────
for ax in (ax_top, ax_bot):
    for bound in GROUP_BOUNDS[1:-1]:
        ax.axvline(x=bound - 0.5, color="#999999", linewidth=0.5,
                   linestyle="--", zorder=1)
    ax.axvline(x=n_workloads - 1.5, color="#666666", linewidth=0.7,
               linestyle="--", zorder=1)

# ── Axes ─────────────────────────────────────────────────────────────────────
ax_bot.set_ylabel("Speedup (%)")
ax_bot.yaxis.set_label_coords(-0.05, 0.65)  # center label across both panels
ax_bot.set_xticks(x)
ax_bot.set_xticklabels(WORKLOADS, fontsize=6, linespacing=0.85)
ax_bot.axhline(y=0, color="black", linewidth=0.5, zorder=2)

# Fewer y-ticks on top panel
ax_top.set_yticks([120])
ax_bot.set_yticks([-10, 0, 10, 20, 30, 40, 50, 60])

# ── Legend (top panel, with average speedup per scheme) ─────────────────────
legend_labels = []
for name, vals, _, _ in schemes:
    avg = np.mean(vals[:-1])  # exclude GMEAN
    legend_labels.append(f"{name} (avg {avg:+.1f}%)")

handles = list(bar_containers_bot)
ax_top.legend(handles, legend_labels,
              loc="upper left", ncol=4, fontsize=6,
              handlelength=1.4, columnspacing=0.8, handletextpad=0.3,
              bbox_to_anchor=(0.0, 1.35))

# ── Save ─────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_figC_sota", out_dir)
plt.close(fig)

print(f"Saved to {out_dir}/proto_figC_sota.{{pdf,svg}}")

# ── Print summary ────────────────────────────────────────────────────────────
print("\n--- GMEAN Speedup ---")
for name, vals, _, _ in schemes:
    print(f"  {name:12s}: {vals[-1]:+.2f}%")
