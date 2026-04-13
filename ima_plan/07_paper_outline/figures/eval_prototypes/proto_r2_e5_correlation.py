#!/usr/bin/env python3
"""Round-2 Effectiveness Fig E5: IMA Miss Reduction vs Speedup correlation.

Single-column scatter showing the causal chain:
       IMA Miss Reduction (%)  ->  IPC Speedup (%)

  * One point per workload (those with valid IMA reduction data)
  * Coloured by algorithm group
  * Linear regression line + R^2
  * Top-3 outliers (largest |residual|) annotated with short name

Data source: ima_plan/07_paper_outline/figures/effectiveness_data.json
            (`derived.ima_total_reduction_pct`, `derived.speedup_pct`,
             algorithm group from workload_names.ALG_OF)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Plot style ───────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_col, save_fig, CB10        # noqa: E402
from workload_names import ORDERED_28, SHORT_NAME, ALG_OF, ALG_GROUPS  # noqa: E402

apply_style()
import matplotlib.pyplot as plt                                       # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"

# ── Algorithm-group colour map (consistent across paper) ─────────────────────
ALG_COLOR = {
    "BFS":  CB10[0],   # blue
    "SSSP": CB10[1],   # orange
    "BC":   CB10[3],   # dark gray
    "CC":   CB10[5],   # red-orange
    "SpMV": CB10[4],   # light blue
    "VC":   CB10[8],   # light orange
    "Ext.": CB10[2],   # mid gray
}

# Marker per algorithm — improves disambiguation if grayscale-printed
ALG_MARKER = {
    "BFS": "o", "SSSP": "s", "BC": "^", "CC": "D",
    "SpMV": "v", "VC": "P", "Ext.": "X",
}

# ── Load ─────────────────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]

points = []      # list of (key, alg, ima_red, speedup)
skipped = []
for k in ORDERED_28:
    rec = DATA.get(k) or {}
    d = rec.get("derived") or {}
    ima_red = d.get("ima_total_reduction_pct")
    sp = d.get("speedup_pct")
    if ima_red is None or sp is None:
        skipped.append(k)
        continue
    points.append((k, ALG_OF.get(k, "Ext."), float(ima_red), float(sp)))

x_arr = np.array([p[2] for p in points])
y_arr = np.array([p[3] for p in points])

# ── Linear regression ───────────────────────────────────────────────────────
slope, intercept = np.polyfit(x_arr, y_arr, 1)
y_pred = slope * x_arr + intercept
ss_res = np.sum((y_arr - y_pred) ** 2)
ss_tot = np.sum((y_arr - y_arr.mean()) ** 2)
r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
# Pearson r (sign of slope agreement)
r = float(np.corrcoef(x_arr, y_arr)[0, 1])

# Top-3 outliers by |residual|
residuals = y_arr - y_pred
outlier_idx = np.argsort(-np.abs(residuals))[:3]

# ── Plot ─────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=figsize_col(aspect=0.85), constrained_layout=True)

for k, alg, xv, yv in points:
    ax.scatter(
        xv, yv,
        c=ALG_COLOR.get(alg, "#333333"),
        marker=ALG_MARKER.get(alg, "o"),
        s=24, edgecolors="black", linewidths=0.4,
        zorder=4,
    )

# Regression line over the data range
xs = np.linspace(x_arr.min() - 2, x_arr.max() + 2, 50)
ax.plot(
    xs, slope * xs + intercept,
    color="#444444", linestyle="--", linewidth=0.9, alpha=0.9,
    zorder=2,
)

# Reference: y = x (1:1 line) — sanity for "1 % miss saved -> 1 % speedup"
ax.plot(
    xs, xs,
    color="#999999", linestyle=":", linewidth=0.6, alpha=0.6,
    zorder=2,
)

# Annotate top-3 outliers — use a small per-outlier offset table to avoid
# label overlap for clusters at the same y (e.g. CC-rd & SpM-rd both ~0%).
# Offset chosen by data position: positive residuals → label above-right,
# negative residuals → label below; horizontal direction alternates so
# multiple bottom outliers don't stack.
_offsets_taken: list[tuple[float, float]] = []
for rank, i in enumerate(outlier_idx):
    k, alg, xv, yv = points[i]
    short = SHORT_NAME[k]
    if residuals[i] >= 0:
        dx, dy = -3.5, 8.0
        ha, va = "right", "bottom"
    else:
        # Alternate sides for stacked low-y outliers
        dx = -7.0 if rank % 2 == 0 else 6.0
        dy = -10.0
        ha = "right" if dx < 0 else "left"
        va = "top"
    ax.annotate(
        short, xy=(xv, yv), xytext=(dx, dy),
        textcoords="offset points",
        fontsize=5.5, color="black", ha=ha, va=va,
        arrowprops=dict(arrowstyle="-", color="#666", lw=0.5),
        zorder=6,
    )

# Stats text box (top-left)
stats = (
    f"Pearson r = {r:+.3f}\n"
    f"R$^2$       = {r2:.3f}\n"
    f"slope     = {slope:+.2f}\n"
    f"n         = {len(points)}"
)
ax.text(
    0.04, 0.96, stats,
    transform=ax.transAxes, ha="left", va="top",
    fontsize=6, family="monospace",
    bbox=dict(boxstyle="round,pad=0.3",
              facecolor="white", edgecolor="#bbb", linewidth=0.5),
    zorder=8,
)

# Axes
ax.set_xlabel("L1 IMA total miss reduction (%)", fontsize=7)
ax.set_ylabel("IPC speedup (%)", fontsize=7)
ax.tick_params(axis="both", labelsize=6.5)
ax.axhline(y=0, color="black", linewidth=0.4, alpha=0.4)
ax.axvline(x=0, color="black", linewidth=0.4, alpha=0.4)

# Algorithm legend (compact)
seen = set()
handles = []
for alg in [g[0] for g in ALG_GROUPS]:
    if alg in seen or alg not in {p[1] for p in points}:
        continue
    seen.add(alg)
    handles.append(plt.scatter(
        [], [], c=ALG_COLOR[alg], marker=ALG_MARKER[alg],
        s=22, edgecolors="black", linewidths=0.4, label=alg,
    ))
ax.legend(
    handles=handles, ncol=2, fontsize=5.5, frameon=False,
    loc="lower right", bbox_to_anchor=(1.0, 0.0),
    handlelength=1.0, handleheight=0.9, columnspacing=0.8,
    labelspacing=0.25,
)

ax.set_title(
    f"IMA Miss Reduction $\\rightarrow$ Speedup",
    fontsize=8, pad=4,
)

save_fig(fig, "proto_r2_e5_correlation", OUT_DIR)
plt.close(fig)

# ── Verification ─────────────────────────────────────────────────────────────
print(f"Saved: {OUT_DIR}/proto_r2_e5_correlation.{{pdf,svg}}")
print(f"points = {len(points)}   skipped = {skipped}")
print(f"Pearson r = {r:+.4f}    R^2 = {r2:.4f}")
print(f"slope = {slope:+.4f}    intercept = {intercept:+.4f}")
print()
print("Top-3 outliers (|residual|):")
for i in outlier_idx:
    k, alg, xv, yv = points[i]
    print(f"  {SHORT_NAME[k]:9s}  ({alg})   ima_red = {xv:6.2f}%   "
          f"speedup = {yv:6.2f}%   residual = {residuals[i]:+6.2f}")
print()
print("All points (sorted by ima_red):")
for i in np.argsort(-x_arr):
    k, alg, xv, yv = points[i]
    print(f"  {SHORT_NAME[k]:9s}  ({alg:4s})   ima_red = {xv:6.2f}%   "
          f"speedup = {yv:6.2f}%")
