#!/usr/bin/env python3
"""Round-3 Reduce Variant V1: Index Coverage — full 27 workloads (reference).

Reference baseline for the round-3 "reduce clutter" exploration.  Same data
as Round-2 q1 (proto_r2_q1_idx_coverage.py) but the y-axis is tightened
to 0–50 % so that the actual data fills 70-80 % of the panel height
(previous version used 0–100 % which left ~half the panel empty).

Subplot label sits BELOW the axis via plot_util.subplot_label() so the
title row of the page can carry the section heading.

Metric:
    idx_coverage = (baseline.ima_idx_misses - grasp.ima_idx_misses)
                   / baseline.ima_idx_misses * 100

Source: ima_plan/07_paper_outline/figures/effectiveness_data.json
Workload set: workload_names.ORDERED_27 (MST excluded — no IMA chain).
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
from workload_names import (                                         # noqa: E402
    ORDERED_27,
    SHORT_NAME,
    group_separator_positions,
)

apply_style()
import matplotlib.pyplot as plt                                      # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"


# ── Load & compute ──────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]


def idx_coverage(key: str):
    """Return idx coverage % (or None if baseline IMA data missing)."""
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


values = [idx_coverage(k) for k in ORDERED_27]
labels = [SHORT_NAME[k] for k in ORDERED_27]

skipped = [k for k, v in zip(ORDERED_27, values) if v is None]

plot_values = np.array([np.nan if v is None else v for v in values], dtype=float)
valid_values = plot_values[~np.isnan(plot_values)]
avg_value = float(np.mean(valid_values)) if valid_values.size else 0.0


# ── Plot ────────────────────────────────────────────────────────────────────
n = len(ORDERED_27)
x = np.arange(n)
bar_w = 0.65

fig, ax = plt.subplots(figsize=(7.0, 1.8), constrained_layout=True)

bars = ax.bar(
    x, plot_values, bar_w,
    color=PALETTE_JEWEL[0], edgecolor="black", linewidth=0.4,
    zorder=3,
)

# Average horizontal line
ax.axhline(
    y=avg_value, color="#C85200", linestyle="--",
    linewidth=0.9, alpha=0.9, zorder=4,
)
# Inline label for the average line, anchored to the right edge
ax.text(
    n - 0.6, avg_value + 1.2,
    f"avg = {avg_value:.1f}%",
    ha="right", va="bottom",
    fontsize=6, color="#C85200", zorder=5,
)

# Annotate outliers only (extreme high CC-fl, MIS-fl and the single
# negative CC-cp); the rest stay clean
for i, v in enumerate(plot_values):
    if np.isnan(v):
        continue
    if v >= 40.0 or v < 0.0:
        offset = 1.0 if v >= 0 else -1.0
        va = "bottom" if v >= 0 else "top"
        ax.text(
            i, v + offset,
            f"{v:.0f}",
            ha="center", va=va,
            fontsize=5.5, color="black", zorder=6,
        )

# Vertical algorithm-group separators
for sep in group_separator_positions(ORDERED_27):
    ax.axvline(
        x=sep, color="#999999", linestyle="--",
        linewidth=0.5, alpha=0.6, zorder=1,
    )

# ── Axes formatting ────────────────────────────────────────────────────────
ax.set_ylabel("Index Coverage (%)", fontsize=7)
ax.set_ylim(-5, 50)
ax.set_yticks([0, 10, 20, 30, 40, 50])
ax.set_xlim(-0.6, n - 0.4)
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.5)
ax.tick_params(axis="y", labelsize=7)
ax.axhline(y=0, color="black", linewidth=0.5, zorder=2)

# Subplot label BELOW the axis (paper convention)
subplot_label(ax, "(a) All 27 workloads", y=-0.62)

save_fig(fig, "proto_r3_reduce_v1_full", OUT_DIR)
plt.close(fig)

print(f"Saved: {OUT_DIR}/proto_r3_reduce_v1_full.{{pdf,svg}}")
print(f"workloads={n}  skipped={len(skipped)}  "
      f"avg={avg_value:.2f}%  min={np.nanmin(plot_values):.1f}%  "
      f"max={np.nanmax(plot_values):.1f}%")
