#!/usr/bin/env python3
"""
Round 4 §5.3 Layout A: 2x3 merged figure (Quality + Mechanism).

Single full-width figure organised as:

  Row 1 (Prefetch Quality)        Row 2 (Mechanism Effectiveness)
  ----------------------------    -------------------------------------
  (a) Index Coverage (%)          (d) L1 IMA-Miss Reduction (%)
  (b) Data Coverage  (%)          (e) Pipeline Funnel (stacked, % attempted)
  (c) Timeliness     (%)          (f) CT Entry Reuse (log scale)

Workload axis: ORDERED_27 (MST excluded — no IMA prefetches).

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT (greens/reds/purples/yellows) — no blue/orange
  - HATCHES_DENSE for B&W readability where multiple bars are grouped
  - GRASP-the-only-bar panels use the green palette[0] solid
  - Subplot labels (a)-(f) BELOW each axis via subplot_label helper
  - Path depth: parents[5]
  - Group-separator vertical dashed lines and per-panel mean reference line

Output: proto_r4_53_A.{pdf,svg} in this directory.
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
from matplotlib.patches import Patch  # noqa: E402


# ── Path constants ───────────────────────────────────────────────────────────
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"
OUT_DIR = Path(__file__).resolve().parent

DATA = json.loads(DATA_JSON.read_text())["workloads"]


# ── Per-metric extractors (return None if data is missing) ───────────────────
def idx_coverage(rec):
    base = rec.get("baseline") or {}
    g = rec.get("grasp") or {}
    bm, gm = base.get("ima_idx_misses"), g.get("ima_idx_misses")
    if bm is None or gm is None or bm == 0:
        return None
    return (bm - gm) / bm * 100.0


def data_coverage(rec):
    base = rec.get("baseline") or {}
    g = rec.get("grasp") or {}
    bm, gm = base.get("ima_data_misses"), g.get("ima_data_misses")
    if bm is None or gm is None or bm == 0:
        return None
    return (bm - gm) / bm * 100.0


def idx_timeliness(rec):
    g = rec.get("grasp") or {}
    tl = g.get("ima_timeliness") or {}
    return tl.get("index_pct")


def l1_miss_reduction(rec):
    return (rec.get("derived") or {}).get("l1_miss_reduction_pct")


def funnel_components(rec):
    """Return (delivered, throttled, idx_rfail, data_rfail, other) % of attempted, or None."""
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


def ct_reuse(rec):
    return (rec.get("derived") or {}).get("ct_reuse_per_entry")


# ── Build per-workload arrays in canonical order ─────────────────────────────
n = len(ORDERED_27)
labels = [SHORT_NAME[k] for k in ORDERED_27]
xs = np.arange(n)

idx_cov_arr  = np.array([idx_coverage   (DATA.get(k) or {}) or np.nan for k in ORDERED_27])
dat_cov_arr  = np.array([data_coverage  (DATA.get(k) or {}) or np.nan for k in ORDERED_27])
tl_arr       = np.array([idx_timeliness (DATA.get(k) or {}) or np.nan for k in ORDERED_27])
miss_red_arr = np.array([l1_miss_reduction(DATA.get(k) or {}) if l1_miss_reduction(DATA.get(k) or {}) is not None else np.nan for k in ORDERED_27])
ct_arr       = np.array([ct_reuse       (DATA.get(k) or {}) if ct_reuse(DATA.get(k) or {}) else np.nan for k in ORDERED_27])

funnel_rows = [funnel_components(DATA.get(k) or {}) for k in ORDERED_27]
funnel_arr = np.array([
    r if r is not None else (np.nan,) * 5 for r in funnel_rows
])  # shape (n, 5): delivered, throttled, idx_rf, dat_rf, other


# ── Helper: workload mean ignoring NaN ───────────────────────────────────────
def nm(arr):
    valid = arr[~np.isnan(arr)]
    return float(np.mean(valid)) if valid.size else 0.0


def gm(arr):  # geometric mean for log-scale CT reuse
    valid = arr[~np.isnan(arr) & (arr > 0)]
    return float(np.exp(np.mean(np.log(valid)))) if valid.size else 0.0


idx_cov_mean = nm(idx_cov_arr)
dat_cov_mean = nm(dat_cov_arr)
tl_mean      = nm(tl_arr)
miss_red_mean = nm(miss_red_arr)
delivery_mean = nm(funnel_arr[:, 0])
ct_geomean   = gm(ct_arr)


# ── Colours from palette (avoid blue/orange) ─────────────────────────────────
C_GRASP   = PALETTE_TOL_BRIGHT[0]   # green
C_DELIVER = PALETTE_TOL_BRIGHT[0]   # green — good
C_THROT   = PALETTE_TOL_BRIGHT[3]   # yellow — throttled
C_IDX_RF  = PALETTE_TOL_BRIGHT[1]   # red — bad
C_DAT_RF  = PALETTE_TOL_BRIGHT[2]   # purple — bad
C_OTHER   = PALETTE_TOL_BRIGHT[4]   # gray — slack
C_REF     = "#444444"               # dashed mean line


# ── Figure layout ────────────────────────────────────────────────────────────
fig, axes = plt.subplots(
    nrows=2, ncols=3, figsize=(7.0, 4.6),
    constrained_layout=True,
)

sep_positions = group_separator_positions(ORDERED_27)


def style_xaxis(ax, with_ticks=True):
    if with_ticks:
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=4.5)
    else:
        ax.set_xticks(xs)
        ax.set_xticklabels([])
    ax.set_xlim(-0.7, n - 0.3)
    ax.tick_params(axis="x", pad=1)
    for sp in sep_positions:
        ax.axvline(x=sp, color="#999999", linestyle="--",
                   linewidth=0.4, alpha=0.7, zorder=1)


def annotate_outliers(ax, values, hi_thresh=92.0, lo_thresh=10.0, fmt="{:.0f}"):
    for i, v in enumerate(values):
        if np.isnan(v):
            continue
        if v > hi_thresh or v < lo_thresh:
            offset = 1.5 if v >= 0 else -1.5
            va = "bottom" if v >= 0 else "top"
            ax.text(
                i, v + offset, fmt.format(v),
                ha="center", va=va, fontsize=4.5, color="black",
                zorder=6,
            )


# ────────────────────────────────────────────────────────────────────────────
# (a) Index Coverage
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0, 0]
ax.bar(xs, idx_cov_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(idx_cov_mean, color=C_REF, linestyle="--", linewidth=0.7,
           alpha=0.85, zorder=4)
annotate_outliers(ax, idx_cov_arr, hi_thresh=92.0, lo_thresh=8.0)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
ax.set_ylim(-5, 110)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Index Cov. (%)", fontsize=6.5, labelpad=1)
ax.tick_params(axis="y", labelsize=6)
style_xaxis(ax, with_ticks=False)
subplot_label(ax,
              f"(a) Index Coverage  (avg = {idx_cov_mean:.0f}%)",
              y=-0.20)


# ────────────────────────────────────────────────────────────────────────────
# (b) Data Coverage
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0, 1]
ax.bar(xs, dat_cov_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(dat_cov_mean, color=C_REF, linestyle="--", linewidth=0.7,
           alpha=0.85, zorder=4)
annotate_outliers(ax, dat_cov_arr, hi_thresh=92.0, lo_thresh=5.0)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
ax.set_ylim(-5, 110)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Data Cov. (%)", fontsize=6.5, labelpad=1)
ax.tick_params(axis="y", labelsize=6)
style_xaxis(ax, with_ticks=False)
subplot_label(ax,
              f"(b) Data Coverage  (avg = {dat_cov_mean:.0f}%)",
              y=-0.20)


# ────────────────────────────────────────────────────────────────────────────
# (c) Index Timeliness
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0, 2]
ax.bar(xs, tl_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(tl_mean, color=C_REF, linestyle="--", linewidth=0.7,
           alpha=0.85, zorder=4)
annotate_outliers(ax, tl_arr, hi_thresh=95.0, lo_thresh=15.0)
ax.set_ylim(0, 110)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Idx Timeliness (%)", fontsize=6.5, labelpad=1)
ax.tick_params(axis="y", labelsize=6)
style_xaxis(ax, with_ticks=False)
subplot_label(ax,
              f"(c) Index Timeliness  (avg = {tl_mean:.0f}%)",
              y=-0.20)


# ────────────────────────────────────────────────────────────────────────────
# (d) L1 IMA Miss Reduction
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1, 0]
# Use total IMA reduction (combined idx + data) which correlates with the
# downstream L1 hit rate. Read directly from `derived.ima_total_reduction_pct`.
ima_total_red = np.array([
    (DATA.get(k) or {}).get("derived", {}).get("ima_total_reduction_pct", np.nan)
    for k in ORDERED_27
])
ima_total_mean = nm(ima_total_red)
colors_d = [
    C_GRASP if v >= 0 else PALETTE_TOL_BRIGHT[1]   # red for regressions
    for v in ima_total_red
]
ax.bar(xs, ima_total_red, 0.70,
       color=colors_d, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(ima_total_mean, color=C_REF, linestyle="--", linewidth=0.7,
           alpha=0.85, zorder=4)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
annotate_outliers(ax, ima_total_red, hi_thresh=80.0, lo_thresh=-5.0)
ax.set_ylim(-15, 100)
ax.set_yticks([-10, 0, 25, 50, 75, 100])
ax.set_ylabel("IMA Miss Red. (%)", fontsize=6.5, labelpad=1)
ax.tick_params(axis="y", labelsize=6)
style_xaxis(ax, with_ticks=True)
subplot_label(ax,
              f"(d) L1 IMA Miss Reduction  (avg = {ima_total_mean:.0f}%)",
              y=-0.78)


# ────────────────────────────────────────────────────────────────────────────
# (e) Pipeline Funnel — stacked vertical bars (each bar = 100%)
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1, 1]

bottoms = np.zeros(n)
def _stack(values, color, hatch, label):
    global bottoms
    ax.bar(xs, values, 0.70, bottom=bottoms,
           color=color, hatch=hatch, edgecolor="black", linewidth=0.3,
           zorder=3, label=label)
    bottoms = bottoms + values

# Order: GotData (good, bottom), Throttled, IdxRFAIL, DataRFAIL, Other (top)
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
ax.set_ylabel("Funnel Share (%)", fontsize=6.5, labelpad=1)
ax.tick_params(axis="y", labelsize=6)
style_xaxis(ax, with_ticks=True)

# Compact legend INSIDE the panel above the bars (5 small boxes)
ax.legend(
    ncol=5, fontsize=4.5, frameon=False,
    loc="lower center", bbox_to_anchor=(0.5, 1.00),
    handlelength=1.0, handleheight=0.7,
    columnspacing=0.5, handletextpad=0.25,
)
subplot_label(ax,
              f"(e) Pipeline Funnel  (delivered avg = {delivery_mean:.0f}%)",
              y=-0.78)


# ────────────────────────────────────────────────────────────────────────────
# (f) CT Entry Reuse — log scale
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1, 2]
ax.bar(xs, ct_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(ct_geomean, color=C_REF, linestyle="--", linewidth=0.7,
           alpha=0.85, zorder=4)
ax.set_yscale("log")
ymin = max(np.nanmin(ct_arr) / 5.0, 1.0) if np.any(~np.isnan(ct_arr)) else 1.0
ymax = float(np.nanmax(ct_arr) * 4.0) if np.any(~np.isnan(ct_arr)) else 1e8
ax.set_ylim(ymin, ymax)
ax.set_ylabel("CT Reuse (pf/entry)", fontsize=6.5, labelpad=1)
ax.tick_params(axis="y", labelsize=6, which="both")
style_xaxis(ax, with_ticks=True)

subplot_label(ax,
              f"(f) CT Entry Reuse  (geo-mean = {ct_geomean:,.0f})",
              y=-0.78)


# ── Save ────────────────────────────────────────────────────────────────────
save_fig(fig, "proto_r4_53_A", OUT_DIR)
plt.close(fig)


# ── Console summary ────────────────────────────────────────────────────────
print("=== Round 4 §5.3 Layout A — 2x3 Merged ===")
print(f"workloads = {n}")
print(f"  Idx Coverage   avg = {idx_cov_mean:5.1f}%   "
      f"min = {np.nanmin(idx_cov_arr):5.1f}%  max = {np.nanmax(idx_cov_arr):5.1f}%")
print(f"  Data Coverage  avg = {dat_cov_mean:5.1f}%   "
      f"min = {np.nanmin(dat_cov_arr):5.1f}%  max = {np.nanmax(dat_cov_arr):5.1f}%")
print(f"  Idx Timeliness avg = {tl_mean:5.1f}%   "
      f"min = {np.nanmin(tl_arr):5.1f}%  max = {np.nanmax(tl_arr):5.1f}%")
print(f"  IMA Tot Red    avg = {ima_total_mean:5.1f}%   "
      f"min = {np.nanmin(ima_total_red):5.1f}%  max = {np.nanmax(ima_total_red):5.1f}%")
print(f"  Funnel deliv.  avg = {delivery_mean:5.1f}%   "
      f"min = {np.nanmin(delivered):5.1f}%  max = {np.nanmax(delivered):5.1f}%")
print(f"  CT Reuse  geo-mean = {ct_geomean:,.0f}   "
      f"max = {np.nanmax(ct_arr):,.0f}")
print(f"\nSaved to {OUT_DIR}/proto_r4_53_A.{{pdf,svg}}")
