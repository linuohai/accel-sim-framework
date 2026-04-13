#!/usr/bin/env python3
"""
Round 4 §5.2 Layout C: Side-by-side composite (per-workload bars + per-alg GMEAN bars).

Two columns with width ratio 2.5:1
  Left  (a): Full 28-workload x 4-scheme grouped bars (squeezed to ~5" wide)
  Right (b): Per-algorithm GMEAN x 4-scheme grouped bars (7 alg groups x 4 bars)

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT (greens/reds/purples) — no blue/orange
  - HATCHES_DENSE for B&W readability
  - GRASP = green (palette[0]) + solid (HATCHES_DENSE[0])
  - Subplot labels (a)/(b) BELOW axes via subplot_label helper
  - Path depth: parents[5]

Output: proto_r4_52_C.{pdf,svg} in this directory.
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
    apply_style, figsize_full, save_fig,
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

for name in ("pann_mis_flickr", "pann_color_eco", "ls_mst_rmat12"):
    np_ipc = eff["workloads"][name]["baseline"]["ipc"]
    sota_pct[name] = {}
    for scheme in ("Snake", "CAPS", "Spare Reg"):
        sota_ipc = ext_sota_ipc.get(name, {}).get(scheme)
        if sota_ipc is None:
            sota_pct[name][scheme] = 0.0
        else:
            sota_pct[name][scheme] = (sota_ipc / np_ipc - 1.0) * 100.0


# ── Step 4: Build per-scheme arrays ──────────────────────────────────────────
def to_mult(pct: float) -> float:
    return 1.0 + pct / 100.0


snake_mult = np.array([to_mult(sota_pct[k]["Snake"])     for k in ORDERED_28])
caps_mult  = np.array([to_mult(sota_pct[k]["CAPS"])      for k in ORDERED_28])
spare_mult = np.array([to_mult(sota_pct[k]["Spare Reg"]) for k in ORDERED_28])
grasp_mult = np.array([to_mult(grasp_pct[k])             for k in ORDERED_28])


def gmean(arr: np.ndarray) -> float:
    return float(np.exp(np.mean(np.log(arr))))


snake_gm = gmean(snake_mult)
caps_gm  = gmean(caps_mult)
spare_gm = gmean(spare_mult)
grasp_gm = gmean(grasp_mult)

# Append global GMEAN as last column on the LEFT panel
snake_all = np.append(snake_mult, snake_gm)
caps_all  = np.append(caps_mult,  caps_gm)
spare_all = np.append(spare_mult, spare_gm)
grasp_all = np.append(grasp_mult, grasp_gm)

n_wkl = len(ORDERED_28)
n_total = n_wkl + 1
labels = [SHORT_NAME[k] for k in ORDERED_28] + ["GMEAN"]


# ── Per-algorithm GMEAN (RIGHT panel) ────────────────────────────────────────
key_to_idx = {k: i for i, k in enumerate(ORDERED_28)}
alg_names = [g for g, _ in ALG_GROUPS]


def alg_gmean(arr: np.ndarray, gwkls) -> float:
    idxs = [key_to_idx[k] for k in gwkls]
    sub = arr[idxs]
    return float(np.exp(np.mean(np.log(sub))))


snake_alg = np.array([alg_gmean(snake_mult, gw) for _, gw in ALG_GROUPS])
caps_alg  = np.array([alg_gmean(caps_mult,  gw) for _, gw in ALG_GROUPS])
spare_alg = np.array([alg_gmean(spare_mult, gw) for _, gw in ALG_GROUPS])
grasp_alg = np.array([alg_gmean(grasp_mult, gw) for _, gw in ALG_GROUPS])


# ── Figure layout: 1 row × 2 cols (width_ratios=[2.5, 1]) ───────────────────
fig = plt.figure(
    figsize=figsize_full(aspect=0.40),
    constrained_layout=True,
)
gs = fig.add_gridspec(
    nrows=1, ncols=2,
    width_ratios=[2.5, 1.0],
    wspace=0.06,
)
ax_left = fig.add_subplot(gs[0])
ax_right = fig.add_subplot(gs[1])


# ────────────────────────────────────────────────────────────────────────────
# LEFT — Per-workload grouped bars (squeezed)
# ────────────────────────────────────────────────────────────────────────────
GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.21
offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_w

Y_LO, Y_HI = 0.85, 1.72

schemes = [
    ("Snake",     snake_all, PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),
    ("CAPS",      caps_all,  PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),
    ("Spare Reg", spare_all, PALETTE_TOL_BRIGHT[3], HATCHES_DENSE[3]),
    ("GRASP",     grasp_all, PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),
]


def height_from_baseline(vals: np.ndarray) -> np.ndarray:
    clipped = np.minimum(vals, Y_HI)
    return clipped - 1.0


bar_containers = {}
for i, (name, vals, color, hatch) in enumerate(schemes):
    heights = height_from_baseline(vals)
    bars = ax_left.bar(
        x + offsets[i], heights, bar_w,
        bottom=1.0,
        label=name, color=color, hatch=hatch,
        edgecolor="black", linewidth=0.35,
        zorder=3,
    )
    bar_containers[name] = (bars, vals, color)

# Annotate clipped outliers
for name, (bars, vals, color) in bar_containers.items():
    for j, bar in enumerate(bars):
        v = vals[j]
        if v < Y_HI:
            continue
        cx = bar.get_x() + bar.get_width() / 2
        ax_left.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, Y_HI),
            xytext=(0, 1.2), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.0, fontweight="bold", color=color,
            zorder=6,
        )
        ax_left.annotate(
            "",
            xy=(cx, Y_HI + 0.012), xytext=(cx, Y_HI - 0.005),
            arrowprops=dict(arrowstyle="->", color=color,
                            lw=0.5, shrinkA=0, shrinkB=0),
            zorder=5,
        )

# Baseline reference line + label
ax_left.axhline(1.0, color="black", linestyle="--", linewidth=0.7, zorder=2)
ax_left.text(
    -0.6, 1.005, "NoPF = 1.0\u00d7",
    fontsize=5.0, color="black", ha="left", va="bottom",
    style="italic", zorder=2,
)

# Group separators
for sp in group_separator_positions(ORDERED_28):
    ax_left.axvline(x=sp, color="#999999", linestyle="--",
                    linewidth=0.5, alpha=0.7, zorder=1)
gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
ax_left.axvline(x=gmean_sep_x, color="black", linestyle="-",
                linewidth=0.8, alpha=0.8, zorder=1)

# Algorithm group labels under x-tick labels
cumulative = 0
for gname, gwkls in ALG_GROUPS:
    gsize = len(gwkls)
    centre = cumulative + (gsize - 1) / 2.0
    ax_left.annotate(
        gname,
        xy=(centre, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -25), textcoords="offset points",
        ha="center", va="top",
        fontsize=6.0, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize
ax_left.annotate(
    "Avg",
    xy=(x[-1], 0), xycoords=("data", "axes fraction"),
    xytext=(0, -25), textcoords="offset points",
    ha="center", va="top",
    fontsize=6.0, fontweight="bold",
    annotation_clip=False,
)

ax_left.set_xticks(x)
ax_left.set_xticklabels(labels, rotation=45, ha="right", fontsize=5.0)
ax_left.set_xlim(-0.7, x[-1] + 0.7)
ax_left.set_ylim(Y_LO, Y_HI + 0.05)
ax_left.set_ylabel("Speedup over No-PF (\u00d7)")
yticks = [0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]
ax_left.set_yticks(yticks)
ax_left.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks])

# Legend (above left panel) with per-scheme global GMEAN inline
legend_patches = [
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
ax_left.legend(
    handles=legend_patches, ncol=4, fontsize=5.5,
    loc="lower left", bbox_to_anchor=(0.0, 1.04), frameon=False,
    handlelength=1.2, handleheight=0.85,
    columnspacing=0.9, handletextpad=0.35,
    borderaxespad=0,
)
subplot_label(ax_left, "(a) Per-Workload Speedup", y=-0.55)


# ────────────────────────────────────────────────────────────────────────────
# RIGHT — Per-algorithm GMEAN grouped bars
# ────────────────────────────────────────────────────────────────────────────
n_alg = len(ALG_GROUPS)
xa = np.arange(n_alg, dtype=float)
bar_wa = 0.20
offsets_a = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_wa

Y2_HI = 1.72  # match left panel ceiling

schemes_alg = [
    ("Snake",     snake_alg, PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),
    ("CAPS",      caps_alg,  PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),
    ("Spare Reg", spare_alg, PALETTE_TOL_BRIGHT[3], HATCHES_DENSE[3]),
    ("GRASP",     grasp_alg, PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),
]

for i, (name, vals, color, hatch) in enumerate(schemes_alg):
    heights = np.minimum(vals, Y2_HI) - 1.0
    bars_a = ax_right.bar(
        xa + offsets_a[i], heights, bar_wa,
        bottom=1.0,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.35,
        zorder=3,
    )
    # Outlier annotation
    for j, bar in enumerate(bars_a):
        v = vals[j]
        if v < Y2_HI:
            continue
        cx = bar.get_x() + bar.get_width() / 2
        ax_right.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, Y2_HI),
            xytext=(0, 1.2), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.0, fontweight="bold", color=color,
            zorder=6,
        )

ax_right.axhline(1.0, color="black", linestyle="--", linewidth=0.7, zorder=2)

# Group separators between algorithms
for k in range(1, n_alg):
    ax_right.axvline(k - 0.5, color="#999999", linestyle="--",
                     linewidth=0.5, alpha=0.7, zorder=1)

ax_right.set_xticks(xa)
ax_right.set_xticklabels(alg_names, rotation=45, ha="right",
                         fontsize=6.0, fontweight="bold")
ax_right.set_xlim(-0.6, n_alg - 0.4)
ax_right.set_ylim(Y_LO, Y_HI + 0.05)
ax_right.set_yticks(yticks)
# Compact y-axis: hide tick labels (shared semantics with left panel)
ax_right.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks], fontsize=5.5)
ax_right.tick_params(axis="y", pad=1)

subplot_label(ax_right, "(b) Per-Algorithm GMEAN", y=-0.55)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_52_C", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.2 Layout C — Side-by-side ===")
print(f"Workloads: {n_wkl}  |  Global GMEAN per scheme:")
print(f"  Snake     {snake_gm:.3f}\u00d7")
print(f"  CAPS      {caps_gm:.3f}\u00d7")
print(f"  Spare Reg {spare_gm:.3f}\u00d7")
print(f"  GRASP     {grasp_gm:.3f}\u00d7")
print()

print("Per-algorithm GMEAN (right panel):")
print(f"  {'group':6s}  {'Snake':>8s}  {'CAPS':>8s}  {'SR':>8s}  {'GRASP':>8s}")
for i, gn in enumerate(alg_names):
    print(f"  {gn:6s}  {snake_alg[i]:>7.3f}\u00d7  {caps_alg[i]:>7.3f}\u00d7  "
          f"{spare_alg[i]:>7.3f}\u00d7  {grasp_alg[i]:>7.3f}\u00d7")

print(f"\nClipped bars (>{Y_HI:.2f}\u00d7) annotated above the bar:")
for name, (_, vals, _) in bar_containers.items():
    for j, v in enumerate(vals[:-1]):
        if v >= Y_HI:
            print(f"  {name:9s}  {ORDERED_28[j]:18s}  {v:.3f}\u00d7")

print(f"\nSaved to {out_dir}/proto_r4_52_C.{{pdf,svg}}")
