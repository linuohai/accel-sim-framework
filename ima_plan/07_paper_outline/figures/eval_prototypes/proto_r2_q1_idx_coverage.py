#!/usr/bin/env python3
"""Round-2 Quality Fig (a): Index Coverage — full 27 workloads (MST excluded).

Single-row, full-width (7.0 x 1.8) bar chart of GRASP Index Coverage (%):

    idx_coverage = (baseline.ima_idx_misses - grasp.ima_idx_misses)
                   / baseline.ima_idx_misses * 100

Source: ima_plan/07_paper_outline/figures/effectiveness_data.json
Workload order:  workload_names.ORDERED_27 (MST removed because it issues
no IMA prefetches).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Project plot style ──────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10              # noqa: E402
from workload_names import (                                    # noqa: E402
    ORDERED_27,
    SHORT_NAME,
    group_separator_positions,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"


# ── Load & compute ──────────────────────────────────────────────────────────
with open(DATA_JSON) as fh:
    DATA = json.load(fh)["workloads"]


def compute_idx_coverage(key: str):
    """Return idx coverage % or None if baseline IMA data missing."""
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


values: list[float | None] = [compute_idx_coverage(k) for k in ORDERED_27]
labels: list[str] = [SHORT_NAME[k] for k in ORDERED_27]

skipped = [k for k, v in zip(ORDERED_27, values) if v is None]
if skipped:
    print(f"[skipped — no baseline IMA data] {skipped}")

# Replace None with NaN for plotting purposes (bar simply not drawn).
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
    color=CB10[0], edgecolor="black", linewidth=0.4,
    zorder=3,
)

# Average horizontal line. Label is placed in the title row (above the
# axes) so it can never collide with bars or annotations.
ax.axhline(
    y=avg_value, color="#C85200", linestyle="--",
    linewidth=0.9, alpha=0.9, zorder=4,
)

# Annotate exceptional bars (>90% or <10%, ignoring NaN)
for i, v in enumerate(plot_values):
    if np.isnan(v):
        continue
    if v > 90.0 or v < 10.0:
        offset = 1.5 if v >= 0 else -1.5
        va = "bottom" if v >= 0 else "top"
        ax.text(
            i, v + offset,
            f"{v:.0f}",
            ha="center", va=va,
            fontsize=5.5, color="black", zorder=6,
        )

# Mark skipped workloads with grey "N/A"
for i, v in enumerate(values):
    if v is None:
        ax.text(
            i, 2,
            "N/A", ha="center", va="bottom",
            fontsize=5.5, color="gray", zorder=6,
        )

# Vertical group separators
for sep in group_separator_positions(ORDERED_27):
    ax.axvline(
        x=sep, color="#999999", linestyle="--",
        linewidth=0.5, alpha=0.6, zorder=1,
    )

# Axes formatting
ax.set_ylabel("Index Coverage (%)", fontsize=7)
ax.set_ylim(-10, 100)
ax.set_xlim(-0.6, n - 0.4)
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.5)
ax.tick_params(axis="y", labelsize=7)
ax.axhline(y=0, color="black", linewidth=0.5, zorder=2)
ax.set_title(
    f"(a) Index Coverage   (avg = {avg_value:.1f}%)",
    fontsize=8, pad=3,
)

save_fig(fig, "proto_r2_q1_idx_coverage", OUT_DIR)
plt.close(fig)

print(f"Saved: {OUT_DIR}/proto_r2_q1_idx_coverage.{{pdf,svg}}")
print(f"workloads={n} skipped={len(skipped)} avg={avg_value:.2f}%  "
      f"min={np.nanmin(plot_values):.1f}%  max={np.nanmax(plot_values):.1f}%")
