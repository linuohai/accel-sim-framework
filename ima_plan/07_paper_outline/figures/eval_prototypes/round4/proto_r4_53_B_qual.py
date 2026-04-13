#!/usr/bin/env python3
"""
Round 4 §5.3 Layout B (Quality standalone): 1x3 panel.

  (a) Index Coverage (%)   (b) Data Coverage (%)   (c) Index Timeliness (%)

Workload axis: ORDERED_27 (MST excluded — no IMA prefetches).

Round 4 visual rules:
  - PALETTE_TOL_BRIGHT — green palette[0] for the GRASP bars
  - Subplot labels (a)(b)(c) BELOW each axis via subplot_label helper
  - Path depth: parents[5]
  - Group-separator vertical dashed lines and per-panel mean reference line
  - Tight y-axis (~70 percent fill) and only outliers annotated

Output: proto_r4_53_B_qual.{pdf,svg} in this directory.
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
    PALETTE_TOL_BRIGHT, subplot_label,
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


# ── Build per-workload arrays in canonical order ─────────────────────────────
n = len(ORDERED_27)
labels = [SHORT_NAME[k] for k in ORDERED_27]
xs = np.arange(n)

idx_cov_arr = np.array([
    idx_coverage(DATA.get(k) or {}) if idx_coverage(DATA.get(k) or {}) is not None else np.nan
    for k in ORDERED_27
])
dat_cov_arr = np.array([
    data_coverage(DATA.get(k) or {}) if data_coverage(DATA.get(k) or {}) is not None else np.nan
    for k in ORDERED_27
])
tl_arr = np.array([
    idx_timeliness(DATA.get(k) or {}) if idx_timeliness(DATA.get(k) or {}) is not None else np.nan
    for k in ORDERED_27
])


def nm(arr):
    valid = arr[~np.isnan(arr)]
    return float(np.mean(valid)) if valid.size else 0.0


idx_cov_mean = nm(idx_cov_arr)
dat_cov_mean = nm(dat_cov_arr)
tl_mean      = nm(tl_arr)


# ── Colours ──────────────────────────────────────────────────────────────────
C_GRASP = PALETTE_TOL_BRIGHT[0]   # green
C_REF   = "#444444"


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
# (a) Index Coverage
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0]
ax.bar(xs, idx_cov_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(idx_cov_mean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
annotate_outliers(ax, idx_cov_arr, hi_thresh=40.0, lo_thresh=2.0)
ax.set_ylim(-5, 70)
ax.set_yticks([0, 15, 30, 45, 60])
ax.set_ylabel("Index Coverage (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax)
subplot_label(ax,
              f"(a) Index Coverage  (avg = {idx_cov_mean:.0f}%)",
              y=-0.62)


# ────────────────────────────────────────────────────────────────────────────
# (b) Data Coverage
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1]
ax.bar(xs, dat_cov_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(dat_cov_mean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
ax.axhline(0, color="black", linewidth=0.4, zorder=2)
annotate_outliers(ax, dat_cov_arr, hi_thresh=50.0, lo_thresh=2.0)
ax.set_ylim(-5, 70)
ax.set_yticks([0, 15, 30, 45, 60])
ax.set_ylabel("Data Coverage (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax)
subplot_label(ax,
              f"(b) Data Coverage  (avg = {dat_cov_mean:.0f}%)",
              y=-0.62)


# ────────────────────────────────────────────────────────────────────────────
# (c) Index Timeliness
# ────────────────────────────────────────────────────────────────────────────
ax = axes[2]
ax.bar(xs, tl_arr, 0.70,
       color=C_GRASP, edgecolor="black", linewidth=0.3, zorder=3)
ax.axhline(tl_mean, color=C_REF, linestyle="--", linewidth=0.8,
           alpha=0.85, zorder=4)
annotate_outliers(ax, tl_arr, hi_thresh=98.0, lo_thresh=30.0)
ax.set_ylim(0, 110)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_ylabel("Index Timeliness (%)", fontsize=7, labelpad=1)
ax.tick_params(axis="y", labelsize=6.5)
style_xaxis(ax)
subplot_label(ax,
              f"(c) Index Timeliness  (avg = {tl_mean:.0f}%)",
              y=-0.62)


# ── Save ────────────────────────────────────────────────────────────────────
save_fig(fig, "proto_r4_53_B_qual", OUT_DIR)
plt.close(fig)


# ── Console summary ────────────────────────────────────────────────────────
print("=== Round 4 §5.3 Layout B (Quality) — 1x3 ===")
print(f"workloads = {n}")
print(f"  Idx Coverage   avg = {idx_cov_mean:5.1f}%   "
      f"min = {np.nanmin(idx_cov_arr):5.1f}%  max = {np.nanmax(idx_cov_arr):5.1f}%")
print(f"  Data Coverage  avg = {dat_cov_mean:5.1f}%   "
      f"min = {np.nanmin(dat_cov_arr):5.1f}%  max = {np.nanmax(dat_cov_arr):5.1f}%")
print(f"  Idx Timeliness avg = {tl_mean:5.1f}%   "
      f"min = {np.nanmin(tl_arr):5.1f}%  max = {np.nanmax(tl_arr):5.1f}%")
print(f"\nSaved to {OUT_DIR}/proto_r4_53_B_qual.{{pdf,svg}}")
