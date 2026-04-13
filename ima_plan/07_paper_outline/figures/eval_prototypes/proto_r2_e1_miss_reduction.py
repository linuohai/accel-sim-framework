#!/usr/bin/env python3
"""Round-2 Effectiveness Fig E1: IMA Miss Reduction (normalized stacked bars).

For each workload (27, MST excluded — no IMA), draw a pair of stacked bars:
  Left  bar: BASELINE -> idx_misses + data_misses, normalized to baseline total = 1.0
  Right bar: GRASP    -> idx_misses + data_misses, in same units (so its
            total height equals the GRASP residual fraction).

This shows where the misses went: shorter GRASP bars = larger total reduction;
the split between idx (blue) and data (orange) shows which axis dominates.

Data source: ima_plan/07_paper_outline/figures/effectiveness_data.json
Workload order: workload_names.ORDERED_27 (MST removed).
Skipped: pann_mis_flickr (no IMA chain — baseline IMA reads are null).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Plot style ───────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10                  # noqa: E402
from workload_names import (                                        # noqa: E402
    ORDERED_27, SHORT_NAME, group_separator_positions,
)

apply_style()
import matplotlib.pyplot as plt                                     # noqa: E402
from matplotlib.patches import Patch                                # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"

# ── Colours ──────────────────────────────────────────────────────────────────
C_IDX  = CB10[0]   # blue
C_DATA = CB10[1]   # orange

# ── Load ─────────────────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]


def get_misses(rec, side):
    """Return (idx, data) miss counts as floats, or (None, None)."""
    s = rec.get(side) or {}
    i, d = s.get("ima_idx_misses"), s.get("ima_data_misses")
    if i is None or d is None:
        return None, None
    return float(i), float(d)


keys, base_idx, base_dat, gr_idx, gr_dat = [], [], [], [], []
skipped = []
for k in ORDERED_27:
    rec = DATA.get(k, {}) or {}
    bi, bd = get_misses(rec, "baseline")
    gi, gd = get_misses(rec, "grasp")
    if bi is None or gi is None or (bi + bd) == 0:
        skipped.append(k)
        continue
    keys.append(k)
    base_idx.append(bi); base_dat.append(bd)
    gr_idx.append(gi);   gr_dat.append(gd)

base_idx = np.array(base_idx); base_dat = np.array(base_dat)
gr_idx   = np.array(gr_idx);   gr_dat   = np.array(gr_dat)

base_tot = base_idx + base_dat
# Normalize so each workload's baseline total = 1.0
nb_idx = base_idx / base_tot
nb_dat = base_dat / base_tot
ng_idx = gr_idx   / base_tot
ng_dat = gr_dat   / base_tot
ng_tot = ng_idx + ng_dat            # GRASP residual fraction
red_pct = (1.0 - ng_tot) * 100.0    # reduction% per workload (display)

n = len(keys)
x = np.arange(n)
bar_w = 0.36

fig, ax = plt.subplots(figsize=(7.0, 3.10))

# ── Baseline (left) bars ─────────────────────────────────────────────────────
b1 = ax.bar(
    x - bar_w / 2, nb_idx, bar_w,
    color=C_IDX, edgecolor="black", linewidth=0.4,
    label="Index miss", zorder=3,
)
b2 = ax.bar(
    x - bar_w / 2, nb_dat, bar_w, bottom=nb_idx,
    color=C_DATA, edgecolor="black", linewidth=0.4,
    label="Data miss",  zorder=3,
)

# ── GRASP (right) bars ───────────────────────────────────────────────────────
g1 = ax.bar(
    x + bar_w / 2, ng_idx, bar_w,
    color=C_IDX, edgecolor="black", linewidth=0.4,
    hatch="//", zorder=3,
)
g2 = ax.bar(
    x + bar_w / 2, ng_dat, bar_w, bottom=ng_idx,
    color=C_DATA, edgecolor="black", linewidth=0.4,
    hatch="//", zorder=3,
)

# ── Reduction-% annotation above each GRASP bar ──────────────────────────────
for i, (h, r) in enumerate(zip(ng_tot, red_pct)):
    ax.text(
        x[i] + bar_w / 2, h + 0.025,
        f"{int(round(r))}",
        ha="center", va="bottom", fontsize=5.5,
        color="#2CA02C" if r >= 0 else "#D62728",
        fontweight="bold", zorder=6,
    )

# Reference line at 1.0 (baseline)
ax.axhline(y=1.0, color="black", linewidth=0.4, alpha=0.4, zorder=2)

# Vertical algorithm group separators (only for the kept keys → recompute)
def seps_for(keys_subset):
    from workload_names import ALG_OF
    s = []
    for i in range(1, len(keys_subset)):
        if ALG_OF.get(keys_subset[i]) != ALG_OF.get(keys_subset[i - 1]):
            s.append(i - 0.5)
    return s

for sep in seps_for(keys):
    ax.axvline(x=sep, color="#999999", linestyle="--",
               linewidth=0.5, alpha=0.6, zorder=1)

# ── Axes formatting ──────────────────────────────────────────────────────────
ax.set_ylabel("L1 IMA misses\n(normalized to baseline)", fontsize=7)
ax.set_ylim(0, 1.22)
ax.set_xlim(-0.7, n - 0.3)
ax.set_xticks(x)
ax.set_xticklabels([SHORT_NAME[k] for k in keys],
                   rotation=45, ha="right", fontsize=6.5)
ax.tick_params(axis="y", labelsize=7)

# ── Legend (4 entries) — placed below title via figure-level legend ─────────
legend_handles = [
    Patch(facecolor=C_IDX,  edgecolor="black", label="Index miss (baseline)"),
    Patch(facecolor=C_DATA, edgecolor="black", label="Data miss (baseline)"),
    Patch(facecolor=C_IDX,  edgecolor="black", hatch="//",
          label="Index miss (GRASP)"),
    Patch(facecolor=C_DATA, edgecolor="black", hatch="//",
          label="Data miss (GRASP)"),
]

mean_red = float(np.mean(red_pct))
# Title goes inside the axes (top of plot) so the legend can sit above it
ax.set_title(
    f"L1 IMA Miss Reduction (baseline = 1.0; numbers = % reduced; mean = {mean_red:.1f}%)",
    fontsize=8, pad=4,
)
# Legend lives on the figure so it can claim its own slot above the title
fig.legend(
    handles=legend_handles,
    ncol=4, fontsize=6.5, frameon=False,
    loc="upper center", bbox_to_anchor=(0.5, 0.99),
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.4,
)
# Manual layout because constrained_layout doesn't reserve room for fig.legend
fig.subplots_adjust(left=0.085, right=0.99, top=0.86, bottom=0.20)

# ── Save & report ────────────────────────────────────────────────────────────
save_fig(fig, "proto_r2_e1_miss_reduction", OUT_DIR)
plt.close(fig)

print(f"Saved: {OUT_DIR}/proto_r2_e1_miss_reduction.{{pdf,svg}}")
print(f"workloads plotted = {n}    skipped = {skipped}")
print(f"miss reduction:  mean = {mean_red:6.2f}%   "
      f"min = {red_pct.min():6.2f}%   max = {red_pct.max():6.2f}%")
print()
print("Per-workload:")
for k, r, gtot in zip(keys, red_pct, ng_tot):
    print(f"  {SHORT_NAME[k]:9s}  reduction = {r:6.2f}%   "
          f"GRASP residual = {gtot:.3f}")
