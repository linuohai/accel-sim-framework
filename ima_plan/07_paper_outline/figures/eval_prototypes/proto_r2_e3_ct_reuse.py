#!/usr/bin/env python3
"""Round-2 Effectiveness Fig E3: CT Entry Reuse Rate.

Horizontal bar chart, log-scale x-axis, of CT reuse per entry:

    reuse = pf_useful / ct_peak

A 5-25-entry Chain Table drives 10^4 .. 10^7 prefetches per workload —
demonstrating that GRASP's tiny storage footprint pays for itself
many orders of magnitude over.

Bars are coloured by `ct_peak`:
  *  ≤ 8 entries → green (small)
  *  ≤ 16        → orange (medium)
  *  > 16        → red    (large)

Annotations: CT peak count next to each bar (e.g. "CT=6").

Data source: ima_plan/07_paper_outline/figures/effectiveness_data.json
            (`derived.ct_reuse_per_entry`, `grasp.grasp_storage.ct_peak`)
Workload: ORDERED_27 minus the one with no CT data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Plot style ───────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig                          # noqa: E402
from workload_names import ORDERED_27, SHORT_NAME                    # noqa: E402

apply_style()
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import Patch                                 # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"

# ── Colours ──────────────────────────────────────────────────────────────────
C_SMALL = "#2CA02C"   # ≤  8 entries
C_MED   = "#FF800E"   # ≤ 16
C_BIG   = "#D62728"   # >  16


def color_for(ct):
    if ct <= 8:  return C_SMALL
    if ct <= 16: return C_MED
    return C_BIG


# ── Load ─────────────────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]

rows: list[tuple[str, int, float]] = []     # (key, ct_peak, reuse)
skipped = []
for k in ORDERED_27:
    rec = DATA.get(k) or {}
    storage = (rec.get("grasp") or {}).get("grasp_storage")
    derived = rec.get("derived") or {}
    reuse = derived.get("ct_reuse_per_entry")
    if not storage or reuse is None or reuse <= 0:
        skipped.append(k)
        continue
    rows.append((k, int(storage["ct_peak"]), float(reuse)))

# Sort high → low so the most reused workloads are at the top.
rows.sort(key=lambda r: r[2], reverse=True)

n = len(rows)
keys   = [r[0] for r in rows]
labels = [SHORT_NAME[k] for k in keys]
cts    = np.array([r[1] for r in rows])
reuses = np.array([r[2] for r in rows])
colors = [color_for(c) for c in cts]

# ── Plot ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.0, 2.94), constrained_layout=True)

y = np.arange(n)
bars = ax.barh(
    y, reuses, 0.72,
    color=colors, edgecolor="black", linewidth=0.4,
    zorder=3,
)

# Annotate "CT=N" inside (or right of) each bar
for bar, c, r in zip(bars, cts, reuses):
    txt = f"CT={c}"
    # Place outside the bar end with small margin (log scale).
    ax.text(
        r * 1.18, bar.get_y() + bar.get_height() / 2,
        txt, ha="left", va="center", fontsize=5.5, color="black",
        zorder=6,
    )

ax.set_xscale("log")
ax.set_xlim(1e3, max(reuses.max() * 4, 1e8))
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=6.5)
ax.invert_yaxis()
ax.set_xlabel("Prefetches per CT entry  (log scale)", fontsize=7)
ax.tick_params(axis="x", labelsize=7)
ax.tick_params(axis="y", labelsize=6.5)

# Geomean reference line
log_geo = float(np.exp(np.mean(np.log(reuses))))
ax.axvline(x=log_geo, color="#444444", linestyle="--",
           linewidth=0.7, alpha=0.8, zorder=2)
# Place the label *above* the topmost data row to avoid overlap with any bar.
ax.text(
    log_geo, -0.35, f"  geo-mean = {log_geo:,.0f}",
    ha="left", va="bottom", fontsize=6, color="#444444",
)

# Legend (CT-size buckets)
legend_handles = [
    Patch(facecolor=C_SMALL, edgecolor="black", label="CT $\\leq$ 8"),
    Patch(facecolor=C_MED,   edgecolor="black", label="9 $\\leq$ CT $\\leq$ 16"),
    Patch(facecolor=C_BIG,   edgecolor="black", label="CT $>$ 16"),
]
ax.legend(
    handles=legend_handles,
    ncol=3, fontsize=6.5, frameon=False,
    loc="upper right", bbox_to_anchor=(1.0, 1.10),
    handlelength=1.2, handleheight=0.9,
    columnspacing=1.2,
)

ax.set_title(
    "CT Entry Reuse Rate "
    "(small CT, millions of prefetches)",
    fontsize=8, pad=14,
)

save_fig(fig, "proto_r2_e3_ct_reuse", OUT_DIR)
plt.close(fig)

# ── Verification ─────────────────────────────────────────────────────────────
print(f"Saved: {OUT_DIR}/proto_r2_e3_ct_reuse.{{pdf,svg}}")
print(f"workloads = {n}   skipped = {skipped}")
print(f"reuse range:  min = {reuses.min():,.0f}    max = {reuses.max():,.0f}")
print(f"reuse geomean = {log_geo:,.0f}")
print(f"CT-peak range: min = {cts.min()}    max = {cts.max()}")
print()
print("Top-5 reuse (CT, reuse):")
for k, c, r in rows[:5]:
    print(f"  {SHORT_NAME[k]:9s}  CT={c:>2}   reuse = {r:>12,.0f}")
print("\nBottom-5 reuse:")
for k, c, r in rows[-5:]:
    print(f"  {SHORT_NAME[k]:9s}  CT={c:>2}   reuse = {r:>12,.0f}")
