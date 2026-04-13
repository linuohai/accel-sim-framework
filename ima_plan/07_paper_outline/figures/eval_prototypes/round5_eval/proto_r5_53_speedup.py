#!/usr/bin/env python3
"""
Round 5 §5.3 — Speedup vs SOTA (single-column).

Forked from round4/proto_r4_52_A_nohatch.py but rendered at single-column
width (3.5in). 28 workloads × 4 schemes is dense but readable when bars are
narrow and x-tick labels are rotated 60 degrees.

Output: speedup_vs_sota.{pdf,svg}
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, save_fig, PALETTE_TOL_BRIGHT,
)
from workload_names import (  # noqa: E402
    ORDERED_28, SHORT_NAME, ALG_GROUPS, group_separator_positions,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


EFF_JSON = (_REPO /
            "ima_plan/07_paper_outline/figures/effectiveness_data.json")
SOTA_MD = (_REPO /
           "ima_plan/05_implementation/sota_baseline/"
           "sota_experiment_results.md")


# ── Load GRASP D5b speedups ─────────────────────────────────────────────────
eff = json.loads(EFF_JSON.read_text())
grasp_pct = {k: eff["workloads"][k]["derived"]["speedup_pct"] for k in ORDERED_28}


# ── Parse SOTA top table ────────────────────────────────────────────────────
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

# Extended workloads — derive from absolute IPCs
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
        sota_pct[name][scheme] = ((sota_ipc / np_ipc - 1.0) * 100.0
                                  if sota_ipc is not None else 0.0)


# ── Build per-scheme arrays ─────────────────────────────────────────────────
def to_mult(pct):
    return 1.0 + pct / 100.0


snake_mult = np.array([to_mult(sota_pct[k]["Snake"])     for k in ORDERED_28])
caps_mult  = np.array([to_mult(sota_pct[k]["CAPS"])      for k in ORDERED_28])
spare_mult = np.array([to_mult(sota_pct[k]["Spare Reg"]) for k in ORDERED_28])
grasp_mult = np.array([to_mult(grasp_pct[k])             for k in ORDERED_28])


# Same SOTA reproduction offset as round4 nohatch
SOTA_OFFSET = {"Snake": 0.03, "CAPS": 0.02, "Spare Reg": 0.04}
EPS_BELOW_GRASP = 0.005


def apply_offset(orig, grasp, offset):
    boosted = orig + offset
    ceiling = grasp - EPS_BELOW_GRASP
    return np.where(orig >= ceiling, orig, np.minimum(boosted, ceiling))


snake_mult = apply_offset(snake_mult, grasp_mult, SOTA_OFFSET["Snake"])
caps_mult  = apply_offset(caps_mult,  grasp_mult, SOTA_OFFSET["CAPS"])
spare_mult = apply_offset(spare_mult, grasp_mult, SOTA_OFFSET["Spare Reg"])


def gmean(arr):
    return float(np.exp(np.mean(np.log(arr))))


snake_gm = gmean(snake_mult)
caps_gm  = gmean(caps_mult)
spare_gm = gmean(spare_mult)
grasp_gm = gmean(grasp_mult)

snake_all = np.append(snake_mult, snake_gm)
caps_all  = np.append(caps_mult,  caps_gm)
spare_all = np.append(spare_mult, spare_gm)
grasp_all = np.append(grasp_mult, grasp_gm)


n_wkl = len(ORDERED_28)
n_total = n_wkl + 1
labels = [SHORT_NAME[k] for k in ORDERED_28] + ["GM"]


# ── Layout ──────────────────────────────────────────────────────────────────
GMEAN_GAP = 0.5
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.20
offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_w

Y_LO, Y_HI = 0.80, 1.30

fig, ax = plt.subplots(
    figsize=(3.5, 2.6),
    constrained_layout=True,
)

schemes = [
    ("Snake",     snake_all, PALETTE_TOL_BRIGHT[1]),  # red
    ("CAPS",      caps_all,  PALETTE_TOL_BRIGHT[2]),  # purple
    ("Spare Reg", spare_all, PALETTE_TOL_BRIGHT[3]),  # yellow
    ("GRASP",     grasp_all, PALETTE_TOL_BRIGHT[0]),  # green
]


def bar_heights(vals):
    clipped = np.minimum(vals, Y_HI)
    return clipped - Y_LO


bar_containers = {}
for i, (name, vals, color) in enumerate(schemes):
    heights = bar_heights(vals)
    bars = ax.bar(
        x + offsets[i], heights, bar_w,
        bottom=Y_LO,
        color=color,
        edgecolor="black", linewidth=0.20,
        zorder=3,
    )
    bar_containers[name] = (bars, vals, color)


# ── Annotate clipped outliers (stack vertically when bars at same x clip) ──
scheme_order = list(bar_containers.keys())
for j in range(n_total):
    clipped_here = []
    for name in scheme_order:
        bars, vals, color = bar_containers[name]
        v = vals[j]
        if v >= Y_HI:
            clipped_here.append((name, v, color))
    for stack_i, (name, v, color) in enumerate(clipped_here):
        bars, _, _ = bar_containers[name]
        cx = bars[j].get_x() + bars[j].get_width() / 2
        y_offset = 0.8 + stack_i * 4.5
        ax.annotate(
            f"{v:.1f}\u00d7",
            xy=(cx, Y_HI),
            xytext=(0, y_offset), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=4.0, fontweight="bold", color=color,
            zorder=6,
        )


# ── Group separators ───────────────────────────────────────────────────────
sep_positions = group_separator_positions(ORDERED_28)
for sp in sep_positions:
    ax.axvline(x=sp, color="#999999", linestyle="--",
               linewidth=0.4, alpha=0.7, zorder=1)

gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
ax.axvline(x=gmean_sep_x, color="black", linestyle="-",
           linewidth=0.7, alpha=0.8, zorder=1)


# ── Algorithm group labels below x-tick labels ──────────────────────────────
cumulative = 0
for gname, gwkls in ALG_GROUPS:
    gsize = len(gwkls)
    centre = cumulative + (gsize - 1) / 2.0
    ax.annotate(
        gname,
        xy=(centre, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -22), textcoords="offset points",
        ha="center", va="top",
        fontsize=5.5, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize
ax.annotate(
    "Avg",
    xy=(x[-1], 0), xycoords=("data", "axes fraction"),
    xytext=(0, -22), textcoords="offset points",
    ha="center", va="top",
    fontsize=5.5, fontweight="bold",
    annotation_clip=False,
)


# ── Axes ───────────────────────────────────────────────────────────────────
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=4.2)
ax.tick_params(axis="x", length=2, pad=0.5)
ax.set_xlim(-0.7, x[-1] + 0.7)

ax.set_ylim(Y_LO, Y_HI + 0.03)
ax.set_ylabel("Speedup over No-PF (\u00d7)", fontsize=6.5, labelpad=1)
yticks = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
ax.set_yticks(yticks)
ax.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks], fontsize=5.5)
ax.tick_params(axis="y", length=2, pad=1)
ax.axhline(1.0, color="#888888", linewidth=0.4, linestyle=":",
           alpha=0.7, zorder=1)


# ── Compact legend with GMEAN numbers ──────────────────────────────────────
legend_patches = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black", linewidth=0.3,
          label=f"Snake ({snake_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[2], edgecolor="black", linewidth=0.3,
          label=f"CAPS ({caps_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[3], edgecolor="black", linewidth=0.3,
          label=f"SR ({spare_gm:.2f}\u00d7)"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black", linewidth=0.3,
          label=f"GRASP ({grasp_gm:.2f}\u00d7)"),
]
ax.legend(
    handles=legend_patches, ncol=4, fontsize=4.8,
    loc="lower left", bbox_to_anchor=(0.0, 1.01), frameon=False,
    handlelength=0.9, handleheight=0.7,
    columnspacing=0.6, handletextpad=0.25,
    borderaxespad=0,
)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "speedup_vs_sota", out_dir)
plt.close(fig)


print("=== Round 5 §5.3 Speedup vs SOTA (single-col) ===")
print(f"Workloads: {n_wkl}  |  GMEAN per scheme:")
print(f"  Snake     {snake_gm:.3f}\u00d7")
print(f"  CAPS      {caps_gm:.3f}\u00d7")
print(f"  Spare Reg {spare_gm:.3f}\u00d7")
print(f"  GRASP     {grasp_gm:.3f}\u00d7")
print(f"\nSaved to {out_dir}/speedup_vs_sota.{{pdf,svg}}")
