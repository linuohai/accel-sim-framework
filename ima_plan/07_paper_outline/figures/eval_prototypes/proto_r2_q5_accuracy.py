#!/usr/bin/env python3
"""Round-2 Quality Fig (e): Accuracy — full 27 workloads (MST excluded).

Single-row, full-width (7.0 x 1.8) bar chart of GRASP Prefetch Accuracy (%).
Source field: ``grasp.grasp_effect.accuracy_pct`` from
``effectiveness_data.json`` (sum across SMs of GRASP_EFFECT pf_useful /
(pf_useful + pf_useless), parsed in extract_effectiveness.py).
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


def get_accuracy(key: str):
    rec = DATA.get(key)
    if rec is None:
        return None
    g = rec.get("grasp") or {}
    eff = g.get("grasp_effect")
    if not eff:
        return None
    return eff.get("accuracy_pct")


values: list[float | None] = [get_accuracy(k) for k in ORDERED_27]
labels: list[str] = [SHORT_NAME[k] for k in ORDERED_27]

skipped = [k for k, v in zip(ORDERED_27, values) if v is None]
if skipped:
    print(f"[skipped — no GRASP accuracy] {skipped}")

plot_values = np.array([np.nan if v is None else v for v in values], dtype=float)
valid_values = plot_values[~np.isnan(plot_values)]
avg_value = float(np.mean(valid_values)) if valid_values.size else 0.0

# ── Plot ────────────────────────────────────────────────────────────────────
n = len(ORDERED_27)
x = np.arange(n)
bar_w = 0.65

fig, ax = plt.subplots(figsize=(7.0, 1.8), constrained_layout=True)

ax.bar(
    x, plot_values, bar_w,
    color=CB10[2], edgecolor="black", linewidth=0.4,
    zorder=3,
)

ax.axhline(
    y=avg_value, color="#C85200", linestyle="--",
    linewidth=0.9, alpha=0.9, zorder=4,
)

# Annotate exceptional bars (>90% or <20%; accuracy lower bound is more
# permissive than the other quality metrics because some workloads sit
# legitimately in the 15-20% range — see spmv_cit_sym at 18.5%).
for i, v in enumerate(plot_values):
    if np.isnan(v):
        continue
    if v > 90.0 or v < 20.0:
        offset = 1.5 if v >= 0 else -1.5
        va = "bottom" if v >= 0 else "top"
        ax.text(
            i, v + offset,
            f"{v:.0f}",
            ha="center", va=va,
            fontsize=5.5, color="black", zorder=6,
        )

for i, v in enumerate(values):
    if v is None:
        ax.text(
            i, 2,
            "N/A", ha="center", va="bottom",
            fontsize=5.5, color="gray", zorder=6,
        )

for sep in group_separator_positions(ORDERED_27):
    ax.axvline(
        x=sep, color="#999999", linestyle="--",
        linewidth=0.5, alpha=0.6, zorder=1,
    )

ax.set_ylabel("Accuracy (%)", fontsize=7)
ax.set_ylim(0, 110)
ax.set_xlim(-0.6, n - 0.4)
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.5)
ax.tick_params(axis="y", labelsize=7)
ax.set_title(
    f"(e) Accuracy   (avg = {avg_value:.1f}%)",
    fontsize=8, pad=3,
)

save_fig(fig, "proto_r2_q5_accuracy", OUT_DIR)
plt.close(fig)

print(f"Saved: {OUT_DIR}/proto_r2_q5_accuracy.{{pdf,svg}}")
print(f"workloads={n} skipped={len(skipped)} avg={avg_value:.2f}%  "
      f"min={np.nanmin(plot_values):.1f}%  max={np.nanmax(plot_values):.1f}%")
