#!/usr/bin/env python3
"""
Round 4 §5.3 Layout B (Mechanism standalone): 1x3 panel.

  (a) L1 IMA Miss Reduction (%)
  (b) Pipeline Funnel — stacked vertical bars
  (c) CT Entry Reuse — log-scale bars

Workload axis: ORDERED_27 (MST excluded).

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT — green palette[0] for the GRASP bars
  - HATCHES_DENSE for the funnel components (5 stacks)
  - Subplot labels (a)(b)(c) BELOW each axis
  - Path depth: parents[5]
  - CT Reuse uses log scale; geomean reference line

Output: proto_r4_53_B_mech.{pdf,svg} in this directory.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np

# NOTE: round4/ is 5 levels deep from repo root.
_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, save_fig,
    PALETTE_TOL_BRIGHT, HATCHES_DENSE, subplot_label,
)
from workload_names import (  # noqa: E402
    ORDERED_27, SHORT_NAME, group_separator_positions,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402


# ── Path constants ───────────────────────────────────────────────────────────
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"
OUT_DIR = Path(__file__).resolve().parent

DATA = json.loads(DATA_JSON.read_text())["workloads"]


# ── Per-metric extractors ────────────────────────────────────────────────────
def funnel_components(rec):
    f = (rec.get("grasp") or {}).get("grasp_funnel")
    if not f or f.get("idx_attempted", 0) == 0:
        return None
    ia = float(f["idx_attempted"])
    delivered = float(f["data_got_data"])
    throttled = float(f["data_throttled"])
    idx_rf = float(f["idx_rfail"])
    dat_rf = float(f["data_rfail"])
    other = max(ia - delivered - throttled - idx_rf - dat_rf, 0.0)
    return (
        delivered / ia * 100,
        throttled / ia * 100,
        idx_rf    / ia * 100,
        dat_rf    / ia * 100,
        other     / ia * 100,
    )


# ── Build per-workload arrays in canonical order ─────────────────────────────
n = len(ORDERED_27)
labels = [SHORT_NAME[k] for k in ORDERED_27]
xs = np.arange(n)

ima_total_red = np.array([
    (DATA.get(k) or {}).get("derived", {}).get("ima_total_reduction_pct", np.nan)
    for k in ORDERED_27
])
ct_arr = np.array([
    (DATA.get(k) or {}).get("derived", {}).get("ct_reuse_per_entry", np.nan) or np.nan
    for k in ORDERED_27
])
funnel_rows = [funnel_components(DATA.get(k) or {}) for k in ORDERED_27]
funnel_arr = np.array([
    r if r is not None else (np.nan,) * 5 for r in funnel_rows
])  # (n, 5): delivered, throttled, idx_rf, dat_rf, other


def nm(arr):
    valid = arr[~np.isnan(arr)]
    return float(np.mean(valid)) if valid.size else 0.0


def gm(arr):
    valid = arr[~np.isnan(arr) & (arr > 0)]
    return float(np.exp(np.mean(np.log(valid)))) if valid.size else 0.0


miss_red_mean = nm(ima_total_red)
delivery_mean = nm(funnel_arr[:, 0])
ct_geomean    = gm(ct_arr)


# ── Colours ──────────────────────────────────────────────────────────────────
C_GRASP   = PALETTE_TOL_BRIGHT[0]   # green
C_DELIVER = PALETTE_TOL_BRIGHT[0]   # green — delivered
C_THROT   = PALETTE_TOL_BRIGHT[3]   # yellow
C_IDX_RF  = PALETTE_TOL_BRIGHT[1]   # red
C_DAT_RF  = PALETTE_TOL_BRIGHT[2]   # purple
C_OTHER   = PALETTE_TOL_BRIGHT[4]   # gray
C_REGR    = PALETTE_TOL_BRIGHT[1]   # red for negative bars
C_REF     = "#444444"


# ── Figure layout ────────────────────────────────────────────────────────────
fig, axes = plt.subplots(
    nrows=1, ncols=3, figsize=(7.0, 2.2),
    constrained_layout=True,
)

sep_positions = group_separator_positions(ORDERED_27)


def style_xaxis(ax):
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=5.5)
    ax.set_xlim(-0.7, n - 0.3)
    ax.tick_params(axis="x", pad=1)
    for sp in sep_positions:
        ax.axvline(x=sp, color="#999999", linestyle="--",
                   linewidth=0.4, alpha=0.7, zorder=1)


def annotate_outliers(ax, values, hi_thresh, lo_thresh):
    for i, v in enumerate(values):
        if np.isnan(v):
            continue
        if v > hi_thresh or v < lo_thresh:
            offset = 1.5 if v >= 0 else -1.5
            va = "bottom" if v >= 0 else "top"
            ax.text(
                i, v + offset, f"{v:.0f}",
                ha="center", va=va, fontsize=5.0, color="black",
                zorder=6,
            )


# ────────────────────────────────────────────────────────────────────────────
# (a) L1 IMA Miss Reduction
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0]
colors = [C_GRASP if v >= 0 else C_REGR for v in ima_total_red]
ax.bar(xs, ima_total_red, 0.70,
       color=colors, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(miss_red_mean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
annotate_outliers(ax, ima_total_red, hi_thresh=45.0, lo_thresh=-3.0)
ax.set_ylim(-15, 70)
ax.set_yticks([-10, 0, 15, 30, 45, 60])
ax.set_ylabel("IMA Miss Reduction (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax)
subplot_label(ax,
              f"(a) L1 IMA Miss Reduction  (avg = {miss_red_mean:.0f}%)",
              y=-0.62)


# ────────────────────────────────────────────────────────────────────────────
# (b) Pipeline Funnel — stacked
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1]

bottoms = np.zeros(n)
def _stack(values, color, hatch, label):
    global bottoms
    ax.bar(xs, values, 0.70, bottom=bottoms,
           color=color, hatch=hatch, edgecolor="black", linewidth=0.3,
           zorder=3, label=label)
    bottoms = bottoms + values

delivered = funnel_arr[:, 0]
throttled = funnel_arr[:, 1]
idx_rf    = funnel_arr[:, 2]
dat_rf    = funnel_arr[:, 3]
other_loss= funnel_arr[:, 4]

_stack(delivered, C_DELIVER, HATCHES_DENSE[0], "Delivered")
_stack(throttled, C_THROT,   HATCHES_DENSE[3], "Throttled")
_stack(idx_rf,    C_IDX_RF,  HATCHES_DENSE[1], "Idx RFAIL")
_stack(dat_rf,    C_DAT_RF,  HATCHES_DENSE[2], "Data RFAIL")
_stack(other_loss,C_OTHER,   HATCHES_DENSE[4], "Other")

ax.axhline(100, color="black", linewidth=0.4, alpha=0.6, zorder=4)
ax.set_ylim(0, 108)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Funnel Share (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax)

# Compact legend ABOVE the panel
ax.legend(
    ncol=5, fontsize=5.0, frameon=False,
    loc="lower center", bbox_to_anchor=(0.5, 1.00),
    handlelength=1.0, handleheight=0.7,
    columnspacing=0.5, handletextpad=0.25,
)
subplot_label(ax,
              f"(b) Pipeline Funnel  (delivered avg = {delivery_mean:.0f}%)",
              y=-0.62)


# ────────────────────────────────────────────────────────────────────────────
# (c) CT Entry Reuse — log scale
# ────────────────────────────────────────────────────────────────────────────
ax = axes[2]
ax.bar(xs, ct_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(ct_geomean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
ax.set_yscale("log")
ymin = max(np.nanmin(ct_arr) / 5.0, 1.0) if np.any(~np.isnan(ct_arr)) else 1.0
ymax = float(np.nanmax(ct_arr) * 4.0) if np.any(~np.isnan(ct_arr)) else 1e8
ax.set_ylim(ymin, ymax)
ax.set_ylabel("CT Reuse (pf / entry)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5, which="both")
style_xaxis(ax)

subplot_label(ax,
              f"(c) CT Entry Reuse  (geo-mean = {ct_geomean:,.0f})",
              y=-0.62)


# ── Save ────────────────────────────────────────────────────────────────────
save_fig(fig, "proto_r4_53_B_mech", OUT_DIR)
plt.close(fig)


# ── Console summary ────────────────────────────────────────────────────────
print("=== Round 4 §5.3 Layout B (Mechanism) — 1x3 ===")
print(f"workloads = {n}")
print(f"  IMA Tot Red    avg = {miss_red_mean:5.1f}%   "
      f"min = {np.nanmin(ima_total_red):5.1f}%  max = {np.nanmax(ima_total_red):5.1f}%")
print(f"  Funnel deliv.  avg = {delivery_mean:5.1f}%   "
      f"min = {np.nanmin(delivered):5.1f}%  max = {np.nanmax(delivered):5.1f}%")
print(f"  CT Reuse  geo-mean = {ct_geomean:,.0f}   "
      f"min = {np.nanmin(ct_arr):,.0f}  max = {np.nanmax(ct_arr):,.0f}")
print(f"\nSaved to {OUT_DIR}/proto_r4_53_B_mech.{{pdf,svg}}")
