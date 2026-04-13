#!/usr/bin/env python3
"""
Round 4 §5.3 Layout C: Compact 2x2 — most informative four panels.

  (a) Index Coverage (%)        (b) Index Timeliness (%)
  (c) L1 IMA Miss Reduction (%) (d) Pipeline Funnel (stacked)

Drops Data Coverage and CT Reuse (those go in the appendix). Workload axis:
ORDERED_27 (MST excluded — no IMA prefetches).

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT — green palette[0] for the GRASP bars
  - HATCHES_DENSE for the funnel components (5 stacks)
  - Subplot labels (a)-(d) BELOW each axis
  - Path depth: parents[5]
  - Group-separator vertical dashed lines and per-panel mean reference line

Output: proto_r4_53_C.{pdf,svg} in this directory.
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
def idx_coverage(rec):
    base = rec.get("baseline") or {}
    g = rec.get("grasp") or {}
    bm, gm = base.get("ima_idx_misses"), g.get("ima_idx_misses")
    if bm is None or gm is None or bm == 0:
        return None
    return (bm - gm) / bm * 100.0


def idx_timeliness(rec):
    g = rec.get("grasp") or {}
    tl = g.get("ima_timeliness") or {}
    return tl.get("index_pct")


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

idx_cov_arr = np.array([
    idx_coverage(DATA.get(k) or {}) if idx_coverage(DATA.get(k) or {}) is not None else np.nan
    for k in ORDERED_27
])
tl_arr = np.array([
    idx_timeliness(DATA.get(k) or {}) if idx_timeliness(DATA.get(k) or {}) is not None else np.nan
    for k in ORDERED_27
])
ima_total_red = np.array([
    (DATA.get(k) or {}).get("derived", {}).get("ima_total_reduction_pct", np.nan)
    for k in ORDERED_27
])
funnel_rows = [funnel_components(DATA.get(k) or {}) for k in ORDERED_27]
funnel_arr = np.array([
    r if r is not None else (np.nan,) * 5 for r in funnel_rows
])  # (n, 5): delivered, throttled, idx_rf, dat_rf, other


def nm(arr):
    valid = arr[~np.isnan(arr)]
    return float(np.mean(valid)) if valid.size else 0.0


idx_cov_mean = nm(idx_cov_arr)
tl_mean      = nm(tl_arr)
miss_red_mean = nm(ima_total_red)
delivery_mean = nm(funnel_arr[:, 0])


# ── Colours ──────────────────────────────────────────────────────────────────
C_GRASP   = PALETTE_TOL_BRIGHT[0]   # green
C_DELIVER = PALETTE_TOL_BRIGHT[0]   # green
C_THROT   = PALETTE_TOL_BRIGHT[3]   # yellow
C_IDX_RF  = PALETTE_TOL_BRIGHT[1]   # red
C_DAT_RF  = PALETTE_TOL_BRIGHT[2]   # purple
C_OTHER   = PALETTE_TOL_BRIGHT[4]   # gray
C_REGR    = PALETTE_TOL_BRIGHT[1]   # red for negative miss-reduction bars
C_REF     = "#444444"


# ── Figure layout ────────────────────────────────────────────────────────────
fig, axes = plt.subplots(
    nrows=2, ncols=2, figsize=(7.0, 3.7),
    constrained_layout=True,
)

sep_positions = group_separator_positions(ORDERED_27)


def style_xaxis(ax, with_ticks=True):
    ax.set_xticks(xs)
    if with_ticks:
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=5.5)
    else:
        ax.set_xticklabels([])
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
# (a) Index Coverage  (top-left, no x-tick labels — share with row below)
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0, 0]
ax.bar(xs, idx_cov_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(idx_cov_mean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
annotate_outliers(ax, idx_cov_arr, hi_thresh=42.0, lo_thresh=2.0)
ax.set_ylim(-5, 70)
ax.set_yticks([0, 15, 30, 45, 60])
ax.set_ylabel("Index Cov. (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax, with_ticks=False)
subplot_label(ax,
              f"(a) Index Coverage  (avg = {idx_cov_mean:.0f}%)",
              y=-0.20)


# ────────────────────────────────────────────────────────────────────────────
# (b) Index Timeliness  (top-right, no x-tick labels)
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0, 1]
ax.bar(xs, tl_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(tl_mean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
annotate_outliers(ax, tl_arr, hi_thresh=98.0, lo_thresh=30.0)
ax.set_ylim(0, 110)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Idx Timeliness (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax, with_ticks=False)
subplot_label(ax,
              f"(b) Index Timeliness  (avg = {tl_mean:.0f}%)",
              y=-0.20)


# ────────────────────────────────────────────────────────────────────────────
# (c) L1 IMA Miss Reduction  (bottom-left)
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1, 0]
colors_c = [C_GRASP if v >= 0 else C_REGR for v in ima_total_red]
ax.bar(xs, ima_total_red, 0.70,
       color=colors_c, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(miss_red_mean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
annotate_outliers(ax, ima_total_red, hi_thresh=45.0, lo_thresh=-3.0)
ax.set_ylim(-15, 70)
ax.set_yticks([-10, 0, 15, 30, 45, 60])
ax.set_ylabel("IMA Miss Red. (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax, with_ticks=True)
subplot_label(ax,
              f"(c) L1 IMA Miss Reduction  (avg = {miss_red_mean:.0f}%)",
              y=-0.78)


# ────────────────────────────────────────────────────────────────────────────
# (d) Pipeline Funnel  (bottom-right)
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1, 1]

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
style_xaxis(ax, with_ticks=True)

# Compact legend ABOVE this panel
ax.legend(
    ncol=5, fontsize=5.0, frameon=False,
    loc="lower center", bbox_to_anchor=(0.5, 1.00),
    handlelength=1.0, handleheight=0.7,
    columnspacing=0.5, handletextpad=0.25,
)
subplot_label(ax,
              f"(d) Pipeline Funnel  (delivered avg = {delivery_mean:.0f}%)",
              y=-0.78)


# ── Save ────────────────────────────────────────────────────────────────────
save_fig(fig, "proto_r4_53_C", OUT_DIR)
plt.close(fig)


# ── Console summary ────────────────────────────────────────────────────────
print("=== Round 4 §5.3 Layout C — Compact 2x2 ===")
print(f"workloads = {n}")
print(f"  Idx Coverage   avg = {idx_cov_mean:5.1f}%   "
      f"min = {np.nanmin(idx_cov_arr):5.1f}%  max = {np.nanmax(idx_cov_arr):5.1f}%")
print(f"  Idx Timeliness avg = {tl_mean:5.1f}%   "
      f"min = {np.nanmin(tl_arr):5.1f}%  max = {np.nanmax(tl_arr):5.1f}%")
print(f"  IMA Tot Red    avg = {miss_red_mean:5.1f}%   "
      f"min = {np.nanmin(ima_total_red):5.1f}%  max = {np.nanmax(ima_total_red):5.1f}%")
print(f"  Funnel deliv.  avg = {delivery_mean:5.1f}%   "
      f"min = {np.nanmin(delivered):5.1f}%  max = {np.nanmax(delivered):5.1f}%")
print(f"\nSaved to {OUT_DIR}/proto_r4_53_C.{{pdf,svg}}")
