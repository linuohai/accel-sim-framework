#!/usr/bin/env python3
"""Round-2 Effectiveness Fig E4: Memwait/Stall Reduction Breakdown.

For each workload (28), draw a paired stacked bar:
  Left  bar (baseline) :  MEM_WAIT  +  Other stalls
  Right bar (GRASP)    :  MEM_WAIT  +  Other stalls

Both bars are normalized to baseline total stall events = 1.0
so the GRASP bar's height directly visualises *total* stall reduction
and the MEM_WAIT segment shrink visualises memory-wait reduction
specifically — that is the demonstrable causal effect of the prefetcher.

Workloads: ORDERED_28 (MST kept — has full stall breakdown).
Sorted by descending baseline MEM_WAIT fraction so that the
memory-bound cases dominate the left side of the plot.

Data source: ima_plan/07_paper_outline/figures/effectiveness_data.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Plot style ───────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10                    # noqa: E402
from workload_names import ORDERED_28, SHORT_NAME                    # noqa: E402

apply_style()
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import Patch                                 # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"

# ── Colours ──────────────────────────────────────────────────────────────────
C_MEMWAIT = CB10[0]   # blue
C_OTHER   = CB10[2]   # mid-gray

# ── Load ─────────────────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]


def stall_pair(rec, side):
    """Return (mem_wait_events, total_stall_events) or (None, None)."""
    sb = (rec.get(side) or {}).get("stall_breakdown")
    if not sb:
        return None, None
    total = sum((v or {}).get("events", 0) for v in sb.values())
    mw    = (sb.get("MEM_WAIT") or {}).get("events", 0)
    return float(mw), float(total)


rows = []
skipped = []
for k in ORDERED_28:
    rec = DATA.get(k) or {}
    bmw, btot = stall_pair(rec, "baseline")
    gmw, gtot = stall_pair(rec, "grasp")
    if btot in (None, 0) or gtot is None:
        skipped.append(k)
        continue
    rows.append((k, bmw, btot, gmw, gtot))

# Sort by descending baseline MEM_WAIT fraction
rows.sort(key=lambda r: r[1] / r[2], reverse=True)

n = len(rows)
keys = [r[0] for r in rows]
labels = [SHORT_NAME[k] for k in keys]

bmw  = np.array([r[1] for r in rows])
btot = np.array([r[2] for r in rows])
gmw  = np.array([r[3] for r in rows])
gtot = np.array([r[4] for r in rows])

# Normalize so each workload's baseline_total = 1.0
nb_mw   = bmw  / btot
nb_oth  = (btot - bmw) / btot
ng_mw   = gmw  / btot
ng_oth  = (gtot - gmw) / btot
ng_tot  = ng_mw + ng_oth

mw_red_pct = (1.0 - gmw / np.maximum(bmw, 1.0)) * 100.0   # mem-wait reduction
tot_red_pct = (1.0 - gtot / btot) * 100.0                  # total stall reduction

# ── Plot ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.0, 3.10))
x = np.arange(n)
bar_w = 0.36

# Baseline (left) bars
ax.bar(
    x - bar_w / 2, nb_mw, bar_w,
    color=C_MEMWAIT, edgecolor="black", linewidth=0.4,
    zorder=3,
)
ax.bar(
    x - bar_w / 2, nb_oth, bar_w, bottom=nb_mw,
    color=C_OTHER, edgecolor="black", linewidth=0.4,
    zorder=3,
)

# GRASP (right) bars (hatched to disambiguate)
ax.bar(
    x + bar_w / 2, ng_mw, bar_w,
    color=C_MEMWAIT, edgecolor="black", linewidth=0.4, hatch="//",
    zorder=3,
)
ax.bar(
    x + bar_w / 2, ng_oth, bar_w, bottom=ng_mw,
    color=C_OTHER, edgecolor="black", linewidth=0.4, hatch="//",
    zorder=3,
)

# MEM_WAIT reduction% annotation above each GRASP bar
for i, (h, r) in enumerate(zip(ng_tot, mw_red_pct)):
    color = "#2CA02C" if r > 0 else "#D62728"
    ax.text(
        x[i] + bar_w / 2, h + 0.025,
        f"{r:+.0f}",
        ha="center", va="bottom", fontsize=5.5,
        color=color, fontweight="bold", zorder=6,
    )

ax.axhline(y=1.0, color="black", linewidth=0.4, alpha=0.4, zorder=2)

# Axes formatting
ax.set_ylabel("Stall events\n(normalized to baseline)", fontsize=7)
ax.set_ylim(0, 1.30)
ax.set_xlim(-0.7, n - 0.3)
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.5)
ax.tick_params(axis="y", labelsize=7)

# Legend (4 entries) — placed via fig.legend so it gets its own row
legend_handles = [
    Patch(facecolor=C_MEMWAIT, edgecolor="black", label="MEM_WAIT (baseline)"),
    Patch(facecolor=C_OTHER,   edgecolor="black", label="Other (baseline)"),
    Patch(facecolor=C_MEMWAIT, edgecolor="black", hatch="//",
          label="MEM_WAIT (GRASP)"),
    Patch(facecolor=C_OTHER,   edgecolor="black", hatch="//",
          label="Other (GRASP)"),
]

mean_mw_red = float(np.mean(mw_red_pct))
ax.set_title(
    f"Stall Reduction (MEM_WAIT vs Other; numbers = MEM_WAIT % reduced; "
    f"mean = {mean_mw_red:+.1f}%)",
    fontsize=8, pad=4,
)
fig.legend(
    handles=legend_handles,
    ncol=4, fontsize=6.5, frameon=False,
    loc="upper center", bbox_to_anchor=(0.5, 0.99),
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.4,
)
fig.subplots_adjust(left=0.085, right=0.99, top=0.86, bottom=0.20)

save_fig(fig, "proto_r2_e4_stall_reduction", OUT_DIR)
plt.close(fig)

# ── Verification ─────────────────────────────────────────────────────────────
print(f"Saved: {OUT_DIR}/proto_r2_e4_stall_reduction.{{pdf,svg}}")
print(f"workloads = {n}   skipped = {skipped}")
print(f"MEM_WAIT reduction:  mean = {mean_mw_red:+6.2f}%   "
      f"min = {mw_red_pct.min():+6.2f}%   max = {mw_red_pct.max():+6.2f}%")
print(f"Total stall reduction:  mean = {tot_red_pct.mean():+6.2f}%   "
      f"max = {tot_red_pct.max():+6.2f}%")
print()
print("Top-5 by MEM_WAIT reduction:")
order = np.argsort(-mw_red_pct)
for i in order[:5]:
    print(f"  {labels[i]:9s}  baseline_mw_frac = {nb_mw[i]:5.2f}   "
          f"mw_red = {mw_red_pct[i]:+6.1f}%   "
          f"total_stall_red = {tot_red_pct[i]:+6.1f}%")
print("\nBottom-5 by MEM_WAIT reduction:")
for i in order[-5:]:
    print(f"  {labels[i]:9s}  baseline_mw_frac = {nb_mw[i]:5.2f}   "
          f"mw_red = {mw_red_pct[i]:+6.1f}%   "
          f"total_stall_red = {tot_red_pct[i]:+6.1f}%")
