#!/usr/bin/env python3
"""
Round 4 §5.2 Layout B: Two-row composite (per-workload bars + per-algorithm boxes).

Row 1: Same as L-5.2-A — per-workload grouped bars (4 schemes x 28 wkl + GMEAN)
Row 2: 1x7 box plots — distribution of speedup across workloads inside each
       algorithm group, with 4 schemes side-by-side. The "Ext." group bundles
       pann_mis + pann_color + ls_mst, where ls_mst has no SOTA data for
       Snake/CAPS/Spare and is excluded via NaN.

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT (greens/reds/purples) — no blue/orange
  - HATCHES_DENSE for B&W readability
  - GRASP = green (palette[0]) + solid (HATCHES_DENSE[0])
  - Subplot labels (a)/(b) BELOW axes via subplot_label helper
  - Path depth: parents[5]

Output: proto_r4_52_B.{pdf,svg} in this directory.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import numpy as np

# NOTE: round4/ is 5 levels deep from repo root
_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, FULL_WIDTH, save_fig,
    PALETTE_TOL_BRIGHT, HATCHES_DENSE, subplot_label,
)
from workload_names import (  # noqa: E402
    ORDERED_28, SHORT_NAME, ALG_GROUPS, group_separator_positions,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Path constants ───────────────────────────────────────────────────────────
EFF_JSON = (_REPO /
            "ima_plan/07_paper_outline/figures/effectiveness_data.json")
SOTA_MD = (_REPO /
           "ima_plan/05_implementation/sota_baseline/"
           "sota_experiment_results.md")


# ── Step 1: Load GRASP D5b speedups ──────────────────────────────────────────
eff = json.loads(EFF_JSON.read_text())
grasp_pct = {}
for k in ORDERED_28:
    grasp_pct[k] = eff["workloads"][k]["derived"]["speedup_pct"]


# ── Step 2: Parse SOTA top table ─────────────────────────────────────────────
sota_text = SOTA_MD.read_text()
row_re = re.compile(
    r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
)
sota_pct = {}
for m in row_re.finditer(sota_text):
    name = m.group(1)
    sota_pct[name] = {
        "Snake":     float(m.group(2)),
        "CAPS":      float(m.group(3)),
        "Spare Reg": float(m.group(4)),
    }


# ── Step 3: Extended workloads ───────────────────────────────────────────────
ext_re = re.compile(
    r"\|\s*`(pann_\w+|ls_\w+)`\s*\|[^|]*\|[^|]*\|\s*"
    r"(Snake|CAPS|Spare Reg)\s*\|\s*([\d\.]+)\s*\|"
)
ext_sota_ipc = {}
for m in ext_re.finditer(sota_text):
    name, scheme, ipc = m.group(1), m.group(2), float(m.group(3))
    ext_sota_ipc.setdefault(name, {})[scheme] = ipc

# Use NaN for missing extended-workload SOTA so the box plot in row 2
# excludes them gracefully (np.nanmean / np.nanpercentile).
NAN_SENTINEL = float("nan")
for name in ("pann_mis_flickr", "pann_color_eco", "ls_mst_rmat12"):
    np_ipc = eff["workloads"][name]["baseline"]["ipc"]
    sota_pct[name] = {}
    for scheme in ("Snake", "CAPS", "Spare Reg"):
        sota_ipc = ext_sota_ipc.get(name, {}).get(scheme)
        if sota_ipc is None:
            sota_pct[name][scheme] = NAN_SENTINEL
        else:
            sota_pct[name][scheme] = (sota_ipc / np_ipc - 1.0) * 100.0


# ── Step 4: Build per-scheme arrays ──────────────────────────────────────────
def to_mult(pct):
    if pct != pct:  # NaN check
        return float("nan")
    return 1.0 + pct / 100.0


snake_mult = np.array([to_mult(sota_pct[k]["Snake"])     for k in ORDERED_28])
caps_mult  = np.array([to_mult(sota_pct[k]["CAPS"])      for k in ORDERED_28])
spare_mult = np.array([to_mult(sota_pct[k]["Spare Reg"]) for k in ORDERED_28])
grasp_mult = np.array([to_mult(grasp_pct[k])             for k in ORDERED_28])


def gmean_nan(arr: np.ndarray) -> float:
    """Geometric mean over positive values, ignoring NaN."""
    a = arr[~np.isnan(arr)]
    return float(np.exp(np.mean(np.log(a))))


snake_gm = gmean_nan(snake_mult)
caps_gm  = gmean_nan(caps_mult)
spare_gm = gmean_nan(spare_mult)
grasp_gm = gmean_nan(grasp_mult)

# Append GMEAN
snake_all = np.append(snake_mult, snake_gm)
caps_all  = np.append(caps_mult,  caps_gm)
spare_all = np.append(spare_mult, spare_gm)
grasp_all = np.append(grasp_mult, grasp_gm)

n_wkl = len(ORDERED_28)
n_total = n_wkl + 1
labels = [SHORT_NAME[k] for k in ORDERED_28] + ["GMEAN"]


# ── Figure layout ────────────────────────────────────────────────────────────
fig = plt.figure(
    figsize=(FULL_WIDTH, 4.5),
    constrained_layout=True,
)
gs = fig.add_gridspec(
    nrows=2, ncols=1,
    height_ratios=[2.3, 2.0],
    hspace=0.55,
)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])


# ────────────────────────────────────────────────────────────────────────────
# Row 1 — Per-workload grouped bars (same data as L-5.2-A)
# ────────────────────────────────────────────────────────────────────────────
GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.20
offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_w

Y_LO, Y_HI = 0.85, 1.72

schemes_row1 = [
    ("Snake",     snake_all, PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),
    ("CAPS",      caps_all,  PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),
    ("Spare Reg", spare_all, PALETTE_TOL_BRIGHT[3], HATCHES_DENSE[3]),
    ("GRASP",     grasp_all, PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),
]


def height_from_baseline(vals: np.ndarray) -> np.ndarray:
    safe = np.where(np.isnan(vals), 1.0, vals)
    clipped = np.minimum(safe, Y_HI)
    return clipped - 1.0


bar_containers = {}
for i, (name, vals, color, hatch) in enumerate(schemes_row1):
    heights = height_from_baseline(vals)
    # Hide bars where the source data is NaN (missing SOTA)
    nan_mask = np.isnan(vals)
    drawn = ax1.bar(
        x + offsets[i], heights, bar_w,
        bottom=1.0,
        label=name, color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )
    for j, b in enumerate(drawn):
        if nan_mask[j]:
            b.set_visible(False)
    bar_containers[name] = (drawn, vals, color)

# Annotate clipped outliers (>= Y_HI)
for name, (bars, vals, color) in bar_containers.items():
    for j, bar in enumerate(bars):
        v = vals[j]
        if np.isnan(v) or v < Y_HI:
            continue
        cx = bar.get_x() + bar.get_width() / 2
        ax1.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, Y_HI),
            xytext=(0, 1.5), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.5, fontweight="bold", color=color,
            zorder=6,
        )
        ax1.annotate(
            "",
            xy=(cx, Y_HI + 0.012), xytext=(cx, Y_HI - 0.005),
            arrowprops=dict(arrowstyle="->", color=color,
                            lw=0.6, shrinkA=0, shrinkB=0),
            zorder=5,
        )

# Baseline 1.0x line + label
ax1.axhline(1.0, color="black", linestyle="--", linewidth=0.7, zorder=2)
ax1.text(
    -0.6, 1.005, "NoPF = 1.0\u00d7",
    fontsize=5.5, color="black", ha="left", va="bottom",
    style="italic", zorder=2,
)

# Vertical separators between alg groups
for sp in group_separator_positions(ORDERED_28):
    ax1.axvline(x=sp, color="#999999", linestyle="--",
                linewidth=0.5, alpha=0.7, zorder=1)
gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
ax1.axvline(x=gmean_sep_x, color="black", linestyle="-",
            linewidth=0.8, alpha=0.8, zorder=1)

# Algorithm group labels under x-tick labels (row 1)
cumulative = 0
for gname, gwkls in ALG_GROUPS:
    gsize = len(gwkls)
    centre = cumulative + (gsize - 1) / 2.0
    ax1.annotate(
        gname,
        xy=(centre, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -28), textcoords="offset points",
        ha="center", va="top",
        fontsize=6.5, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize
ax1.annotate(
    "Avg",
    xy=(x[-1], 0), xycoords=("data", "axes fraction"),
    xytext=(0, -28), textcoords="offset points",
    ha="center", va="top",
    fontsize=6.5, fontweight="bold",
    annotation_clip=False,
)

ax1.set_xticks(x)
ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=5.5)
ax1.set_xlim(-0.7, x[-1] + 0.7)
ax1.set_ylim(Y_LO, Y_HI + 0.05)
ax1.set_ylabel("Speedup over No-PF (\u00d7)")
yticks_row1 = [0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]
ax1.set_yticks(yticks_row1)
ax1.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks_row1])

# Legend (row 1) with per-scheme geomean inline
legend_patches_row1 = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black",
          hatch=HATCHES_DENSE[1], linewidth=0.4,
          label=f"Snake ({snake_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[2], edgecolor="black",
          hatch=HATCHES_DENSE[2], linewidth=0.4,
          label=f"CAPS ({caps_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[3], edgecolor="black",
          hatch=HATCHES_DENSE[3], linewidth=0.4,
          label=f"Spare Reg ({spare_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black",
          hatch=HATCHES_DENSE[0], linewidth=0.4,
          label=f"GRASP ({grasp_gm:.2f}\u00d7)"),
]
ax1.legend(
    handles=legend_patches_row1, ncol=4, fontsize=6.0,
    loc="lower left", bbox_to_anchor=(0.0, 1.02), frameon=False,
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.2, handletextpad=0.4,
    borderaxespad=0,
)
subplot_label(ax1, "(a) Per-Workload IPC Speedup vs SOTA Prefetchers",
              y=-0.55)


# ────────────────────────────────────────────────────────────────────────────
# Row 2 — Per-algorithm box plots (4 schemes side-by-side per group)
# ────────────────────────────────────────────────────────────────────────────
# Build a wkl -> idx map then group by ALG_GROUPS.
key_to_idx = {k: i for i, k in enumerate(ORDERED_28)}

scheme_arrays = {
    "Snake":     snake_mult,
    "CAPS":      caps_mult,
    "Spare Reg": spare_mult,
    "GRASP":     grasp_mult,
}
scheme_styles = {
    "Snake":     (PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),
    "CAPS":      (PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),
    "Spare Reg": (PALETTE_TOL_BRIGHT[3], HATCHES_DENSE[3]),
    "GRASP":     (PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),
}
scheme_order = ["Snake", "CAPS", "Spare Reg", "GRASP"]

# Per-(group, scheme) value list, NaN-stripped
group_scheme_vals = {}  # (gname, scheme) -> np.ndarray
for gname, gwkls in ALG_GROUPS:
    idxs = [key_to_idx[k] for k in gwkls]
    for scheme in scheme_order:
        arr = scheme_arrays[scheme][idxs]
        arr = arr[~np.isnan(arr)]
        group_scheme_vals[(gname, scheme)] = arr

# X positions: 7 groups × 4 box positions per group, with intra-group offsets
n_groups = len(ALG_GROUPS)
group_centres = np.arange(n_groups, dtype=float)
box_w = 0.18
box_offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * box_w

# Y range for row 2: GRASP CC-fl is the only > 1.7 outlier; clip at 1.72.
Y2_LO, Y2_HI = 0.78, 1.72
ax2.set_ylim(Y2_LO, Y2_HI + 0.05)
ax2.axhline(1.0, color="black", linestyle="--", linewidth=0.7, zorder=2)

for s_i, scheme in enumerate(scheme_order):
    color, hatch = scheme_styles[scheme]
    positions = group_centres + box_offsets[s_i]
    data = []
    for gname, _ in ALG_GROUPS:
        vals = group_scheme_vals[(gname, scheme)]
        # Clip to Y2_HI for box rendering; outliers will be marked with arrows.
        vals_clipped = np.minimum(vals, Y2_HI) if vals.size else vals
        data.append(vals_clipped if vals_clipped.size else np.array([1.0]))

    bp = ax2.boxplot(
        data, positions=positions, widths=box_w * 0.92,
        patch_artist=True, manage_ticks=False,
        showfliers=False,
        medianprops=dict(color="black", linewidth=0.9),
        whiskerprops=dict(color="black", linewidth=0.6),
        capprops=dict(color="black", linewidth=0.6),
        boxprops=dict(linewidth=0.4),
    )
    for patch in bp["boxes"]:
        patch.set_facecolor(color)
        patch.set_edgecolor("black")
        patch.set_hatch(hatch)

    # Outlier annotation: any raw value > Y2_HI is plotted as an "↑X.XX×" tag
    for gi, (gname, _) in enumerate(ALG_GROUPS):
        raw_vals = group_scheme_vals[(gname, scheme)]
        outliers = raw_vals[raw_vals > Y2_HI]
        if outliers.size == 0:
            continue
        max_v = float(outliers.max())
        ax2.annotate(
            f"{max_v:.2f}\u00d7",
            xy=(positions[gi], Y2_HI),
            xytext=(0, 1.5), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.5, fontweight="bold", color=color,
            zorder=6,
        )

# Group separators between algorithms
for k in range(1, n_groups):
    ax2.axvline(k - 0.5, color="#999999", linestyle="--",
                linewidth=0.5, alpha=0.7, zorder=1)

# X-axis: algorithm group names
ax2.set_xticks(group_centres)
ax2.set_xticklabels([g for g, _ in ALG_GROUPS], fontsize=7.5, fontweight="bold")
ax2.set_xlim(-0.6, n_groups - 0.4)

# Y-axis
ax2.set_ylabel("Speedup over No-PF (\u00d7)")
yticks_row2 = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]
ax2.set_yticks(yticks_row2)
ax2.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks_row2])

subplot_label(ax2,
              "(b) Per-Algorithm Distribution (box: Q1/median/Q3, whiskers: min/max)",
              y=-0.32)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_52_B", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.2 Layout B — Bar + Box ===")
print(f"Workloads: {n_wkl}  |  GMEAN per scheme (NaN-stripped):")
print(f"  Snake     {snake_gm:.3f}\u00d7")
print(f"  CAPS      {caps_gm:.3f}\u00d7")
print(f"  Spare Reg {spare_gm:.3f}\u00d7")
print(f"  GRASP     {grasp_gm:.3f}\u00d7")
print()

print("Per-algorithm GRASP median:")
for gname, _ in ALG_GROUPS:
    vals = group_scheme_vals[(gname, "GRASP")]
    if vals.size:
        print(f"  {gname:5s}  median={np.median(vals):.3f}\u00d7  n={vals.size}")

print(f"\nMissing-SOTA (NaN) workloads:")
for k in ORDERED_28:
    for scheme in scheme_order:
        v = scheme_arrays[scheme][key_to_idx[k]]
        if np.isnan(v):
            print(f"  {scheme:9s}  {k}")

print(f"\nSaved to {out_dir}/proto_r4_52_B.{{pdf,svg}}")
