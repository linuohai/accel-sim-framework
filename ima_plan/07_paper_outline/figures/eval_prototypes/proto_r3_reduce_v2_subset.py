#!/usr/bin/env python3
"""Round-3 Reduce Variant V2: Index Coverage — representative 12 workloads.

Direct subset of 12 hand-picked workloads (2 per algorithm group, choosing
the most informative cases) instead of all 27.  This produces wider bars
and noticeably less x-axis clutter while still spanning the full BFS …
Extended algorithm range.

Subset selection rule: pick 2 per algorithm — typically one "best" and
one "worst" case so the dynamic range is preserved.

Metric: same as v1 / Round-2 q1 (idx coverage % from ima_idx_misses).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Project plot style ──────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (                                              # noqa: E402
    apply_style,
    save_fig,
    subplot_label,
    PALETTE_JEWEL,
)
from workload_names import SHORT_NAME, ALG_OF                        # noqa: E402

apply_style()
import matplotlib.pyplot as plt                                      # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"

# ── Subset definition (2 per algorithm) ────────────────────────────────────
SUBSET = [
    "bfs_web_sym",      # BFS — high speedup case
    "bfs_road_sym",     # BFS — low-degree (road) case
    "sssp_web_sym",     # SSSP — high
    "sssp_road_sym",    # SSSP — low
    "bc_web_sym",       # BC  — mid
    "bc_flickr_sym",    # BC  — high (dense flickr)
    "cc_flickr_sym",    # CC  — best case
    "cc_cit_sym",       # CC  — worst (negative coverage)
    "spmv_web_sym",     # SpMV — high (web)
    "spmv_cit_sym",     # SpMV — low (cit, x16-unroll edge case)
    "vc_web_sym",       # VC  — mid
    "pann_mis_flickr",  # Extended — MIS
]
assert len(SUBSET) == 12

# ── Load & compute ─────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]


def idx_coverage(key: str):
    rec = DATA.get(key)
    if rec is None:
        return None
    base = rec.get("baseline") or {}
    g = rec.get("grasp") or {}
    bm = base.get("ima_idx_misses")
    gm = g.get("ima_idx_misses")
    if bm is None or gm is None or bm == 0:
        return None
    return (bm - gm) / bm * 100.0


values = [idx_coverage(k) for k in SUBSET]
labels = [SHORT_NAME[k] for k in SUBSET]
plot_values = np.array([np.nan if v is None else v for v in values], dtype=float)
valid_values = plot_values[~np.isnan(plot_values)]
avg_value = float(np.mean(valid_values)) if valid_values.size else 0.0

# ── Group separators (recompute for the subset) ────────────────────────────
def seps_for(keys_subset):
    s = []
    for i in range(1, len(keys_subset)):
        if ALG_OF.get(keys_subset[i]) != ALG_OF.get(keys_subset[i - 1]):
            s.append(i - 0.5)
    return s


# ── Plot ───────────────────────────────────────────────────────────────────
n = len(SUBSET)
x = np.arange(n)
bar_w = 0.6                                       # wider than v1 (fewer bars)

fig, ax = plt.subplots(figsize=(7.0, 2.0), constrained_layout=True)

bars = ax.bar(
    x, plot_values, bar_w,
    color=PALETTE_JEWEL[0], edgecolor="black", linewidth=0.5,
    zorder=3,
)

# Average line
ax.axhline(
    y=avg_value, color="#C85200", linestyle="--",
    linewidth=0.9, alpha=0.9, zorder=4,
)
# Place the avg-line label above the negative CC-cp bar (index 7),
# where there is plenty of empty space above the avg line and no other
# annotation can collide with it.
ax.text(
    7.0, avg_value + 6.0,
    f"avg = {avg_value:.1f}%",
    ha="center", va="bottom",
    fontsize=6.5, color="#C85200", zorder=5,
)

# Annotate every bar (only 12, so this stays uncluttered).  When a bar
# is within ~3 % of the avg line we push the label upward so the text
# does not collide with the orange dashed line.
for i, v in enumerate(plot_values):
    if np.isnan(v):
        continue
    if v >= 0:
        if abs(v - avg_value) < 3.0:
            offset = 2.5                # extra clearance from avg line
        else:
            offset = 1.0
        va = "bottom"
    else:
        offset = -1.0
        va = "top"
    ax.text(
        i, v + offset,
        f"{v:.0f}",
        ha="center", va=va,
        fontsize=6, color="black", zorder=6,
    )

# Vertical algorithm-group separators
for sep in seps_for(SUBSET):
    ax.axvline(
        x=sep, color="#999999", linestyle="--",
        linewidth=0.5, alpha=0.6, zorder=1,
    )

# Axes formatting
ax.set_ylabel("Index Coverage (%)", fontsize=7)
ax.set_ylim(-5, 50)
ax.set_yticks([0, 10, 20, 30, 40, 50])
ax.set_xlim(-0.6, n - 0.4)
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
ax.tick_params(axis="y", labelsize=7)
ax.axhline(y=0, color="black", linewidth=0.5, zorder=2)

# Subplot label BELOW
subplot_label(ax, "(b) Representative subset (12 workloads)", y=-0.55)

save_fig(fig, "proto_r3_reduce_v2_subset", OUT_DIR)
plt.close(fig)

print(f"Saved: {OUT_DIR}/proto_r3_reduce_v2_subset.{{pdf,svg}}")
print(f"workloads={n}  avg={avg_value:.2f}%  "
      f"min={np.nanmin(plot_values):.1f}%  max={np.nanmax(plot_values):.1f}%")
print("Subset:")
for k, v in zip(SUBSET, values):
    print(f"  {SHORT_NAME[k]:9s}  ({k:18s})  coverage = {v:6.2f}%")
