#!/usr/bin/env python3
"""
Round 4 §5.3 FINAL — Mechanism combined figure (2 panels).

1×2 horizontal subplot figure aggregating metrics per algorithm group
(across 8 algorithms — MST is excluded because it has no IMA data):

  (a) L1 IMA Miss Reduction (%) — arithmetic mean of
      derived.ima_total_reduction_pct per algorithm.
  (b) Pipeline Funnel (%)       — stacked bar breaking down
      grasp_funnel counts into Got Data / Throttled / Idx RFAIL /
      Data RFAIL / Other (residual), each as % of idx_attempted,
      averaged per algorithm.

CT Entry Reuse panel removed in Round 5 per user request.

Style strictly matches proto_r4_52_A_nohatch.py (DMP-style color-only):
PALETTE_TOL_BRIGHT, no hatching, constrained layout, parents[5].
Subplot labels (a)/(b) BELOW each axis via subplot_label.

Output: proto_r4_53_mechanism.{pdf,svg}
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import numpy as np

# NOTE: round4/ is 5 levels deep from repo root
_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, save_fig,
    PALETTE_TOL_BRIGHT, subplot_label,
)
from workload_names import ALG_GROUPS  # noqa: E402

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Path constants ───────────────────────────────────────────────────────────
EFF_JSON = (_REPO /
            "ima_plan/07_paper_outline/figures/effectiveness_data.json")

DATA = json.loads(EFF_JSON.read_text())["workloads"]


# ── Algorithm groups (MST excluded — no IMA data) ──────────────────────────
# ALG_GROUPS gives 7 entries including Ext. = [mis, color, mst]; split Ext.
# into MIS / CLR / MST so §5.3 can show per-algorithm bars.
ALG_GROUPS_BASE = list(ALG_GROUPS)
alg_base = [g for g in ALG_GROUPS_BASE if g[0] != "Ext."]
ext_group = next((g for g in ALG_GROUPS_BASE if g[0] == "Ext."), None)

ALGORITHMS = [
    ("BFS",  ALG_GROUPS_BASE[0][1]),
    ("SSSP", ALG_GROUPS_BASE[1][1]),
    ("BC",   ALG_GROUPS_BASE[2][1]),
    ("CC",   ALG_GROUPS_BASE[3][1]),
    ("SpMV", ALG_GROUPS_BASE[4][1]),
    ("VC",   ALG_GROUPS_BASE[5][1]),
    ("MIS",  ["pann_mis_flickr"]),
    ("CLR",  ["pann_color_eco"]),
    # MST excluded: ima_total_reduction_pct = null, no grasp_funnel, no CT.
]

n_alg = len(ALGORITHMS)
alg_labels = [name for name, _ in ALGORITHMS]
xs = np.arange(n_alg, dtype=float)


# ── Per-workload extractors ─────────────────────────────────────────────────
def ima_total_red(rec):
    return (rec.get("derived") or {}).get("ima_total_reduction_pct")


def ct_reuse(rec):
    return (rec.get("derived") or {}).get("ct_reuse_per_entry")


def funnel_pcts(rec):
    """Return funnel shares (got_data, throttled, idx_rf, data_rf, other)
    as % of idx_attempted, or None if funnel data is missing."""
    f = (rec.get("grasp") or {}).get("grasp_funnel")
    if not f:
        return None
    ia = float(f.get("idx_attempted") or 0.0)
    if ia <= 0:
        return None
    got    = float(f.get("data_got_data") or 0) / ia * 100.0
    throt  = float(f.get("data_throttled") or 0) / ia * 100.0
    idx_rf = float(f.get("idx_rfail") or 0) / ia * 100.0
    dat_rf = float(f.get("data_rfail") or 0) / ia * 100.0
    other  = max(100.0 - got - throt - idx_rf - dat_rf, 0.0)
    return (got, throt, idx_rf, dat_rf, other)


# ── Aggregate per algorithm ────────────────────────────────────────────────
def alg_mean(metric_fn, wkls):
    vals = []
    for w in wkls:
        rec = DATA.get(w) or {}
        v = metric_fn(rec)
        if v is not None:
            vals.append(v)
    return float(np.mean(vals)) if vals else 0.0


def alg_geomean(metric_fn, wkls):
    vals = []
    for w in wkls:
        rec = DATA.get(w) or {}
        v = metric_fn(rec)
        if v is not None and v > 0:
            vals.append(v)
    if not vals:
        return 0.0
    return float(math.exp(sum(math.log(v) for v in vals) / len(vals)))


def alg_funnel_mean(wkls):
    """Average the 5 funnel components across wkls."""
    rows = []
    for w in wkls:
        rec = DATA.get(w) or {}
        r = funnel_pcts(rec)
        if r is not None:
            rows.append(r)
    if not rows:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    arr = np.array(rows)  # shape (nw, 5)
    return tuple(float(x) for x in arr.mean(axis=0))


miss_red_alg = np.array([alg_mean(ima_total_red, wkls) for _, wkls in ALGORITHMS])
ct_reuse_alg = np.array([alg_geomean(ct_reuse, wkls) for _, wkls in ALGORITHMS])
funnel_alg_rows = [alg_funnel_mean(wkls) for _, wkls in ALGORITHMS]
funnel_alg = np.array(funnel_alg_rows)   # shape (n_alg, 5)


# ── Colors ──────────────────────────────────────────────────────────────────
C_GRASP   = PALETTE_TOL_BRIGHT[0]  # green  — good / primary
C_DELIVER = PALETTE_TOL_BRIGHT[0]  # green  — got data
C_THROT   = PALETTE_TOL_BRIGHT[3]  # yellow — throttled
C_IDX_RF  = PALETTE_TOL_BRIGHT[1]  # red    — idx reservation fail
C_DAT_RF  = PALETTE_TOL_BRIGHT[2]  # purple — data reservation fail
C_OTHER   = PALETTE_TOL_BRIGHT[4]  # gray   — residual / slack


# ── Figure layout ───────────────────────────────────────────────────────────
fig, axes = plt.subplots(
    nrows=1, ncols=2,
    figsize=(7.0, 2.2),
    constrained_layout=True,
    gridspec_kw={"width_ratios": [1.0, 1.4]},
)

bar_w = 0.65


def style_xaxis(ax):
    ax.set_xticks(xs)
    ax.set_xticklabels(alg_labels, rotation=0, ha="center", fontsize=6.5)
    ax.set_xlim(-0.7, n_alg - 0.3)
    ax.tick_params(axis="x", pad=1)


# ────────────────────────────────────────────────────────────────────────────
# (a) L1 IMA Miss Reduction (%) per algorithm
# ────────────────────────────────────────────────────────────────────────────
ax = axes[0]
Y_LO_A, Y_HI_A = 0.0, 50.0
# Bars sit on Y_LO_A. Clip anything > Y_HI_A.
heights_a = np.minimum(np.maximum(miss_red_alg, Y_LO_A), Y_HI_A) - Y_LO_A
ax.bar(
    xs, heights_a, bar_w,
    bottom=Y_LO_A,
    color=C_GRASP,
    edgecolor="black", linewidth=0.4,
    zorder=3,
)
# Annotate clipped bars
for i, v in enumerate(miss_red_alg):
    if v > Y_HI_A:
        ax.annotate(
            f"{v:.0f}%",
            xy=(xs[i], Y_HI_A), xytext=(0, 1.5),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.5, fontweight="bold", color=C_GRASP,
            zorder=6,
        )
        ax.annotate(
            "",
            xy=(xs[i], Y_HI_A + 1.5), xytext=(xs[i], Y_HI_A - 0.5),
            arrowprops=dict(arrowstyle="->", color=C_GRASP,
                            lw=0.6, shrinkA=0, shrinkB=0),
            zorder=5,
        )

ax.set_ylim(Y_LO_A, Y_HI_A + 3.0)
ax.set_yticks([0, 10, 20, 30, 40, 50])
ax.set_yticklabels([f"{t:d}%" for t in [0, 10, 20, 30, 40, 50]])
ax.set_ylabel("IMA Miss Reduction", fontsize=7, labelpad=2)
ax.tick_params(axis="y", labelsize=6)
style_xaxis(ax)
subplot_label(ax, "(a) L1 Miss Reduction", y=-0.30)


# ────────────────────────────────────────────────────────────────────────────
# (b) Pipeline Funnel — stacked per-algorithm bar summing to 100%
# ────────────────────────────────────────────────────────────────────────────
ax = axes[1]
Y_LO_B, Y_HI_B = 0.0, 100.0

# Stack order (bottom → top): Got Data, Throttled, Idx RFAIL, Data RFAIL, Other
delivered  = funnel_alg[:, 0]
throttled  = funnel_alg[:, 1]
idx_rfail  = funnel_alg[:, 2]
data_rfail = funnel_alg[:, 3]
other_loss = funnel_alg[:, 4]

bottoms = np.zeros(n_alg)


def _stack(values, color, label):
    global bottoms
    ax.bar(
        xs, values, bar_w,
        bottom=bottoms,
        color=color,
        edgecolor="black", linewidth=0.4,
        label=label, zorder=3,
    )
    bottoms = bottoms + values


_stack(delivered,  C_DELIVER, "Got Data")
_stack(throttled,  C_THROT,   "Throttled")
_stack(idx_rfail,  C_IDX_RF,  "Idx RFAIL")
_stack(data_rfail, C_DAT_RF,  "Data RFAIL")
_stack(other_loss, C_OTHER,   "Other")

ax.set_ylim(Y_LO_B, Y_HI_B + 5.0)
ax.set_yticks([0, 25, 50, 75, 100])
ax.set_yticklabels([f"{t:d}%" for t in [0, 25, 50, 75, 100]])
ax.set_ylabel("Funnel Share", fontsize=7, labelpad=2)
ax.tick_params(axis="y", labelsize=6)
style_xaxis(ax)
subplot_label(ax, "(b) Pipeline Funnel", y=-0.30)

# Legend inside top of panel (small, 5 entries, single row)
ax.legend(
    ncol=5, fontsize=5.2, frameon=False,
    loc="lower center", bbox_to_anchor=(0.5, 1.01),
    handlelength=0.9, handleheight=0.7,
    columnspacing=0.5, handletextpad=0.25,
    borderaxespad=0,
)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_53_mechanism", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.3 Mechanism — per-algorithm aggregation ===")
print(f"algorithms = {n_alg} (MST excluded — no IMA data)")
print()
print("(a) L1 IMA Miss Reduction (%) — arith mean per alg:")
for name, v in zip(alg_labels, miss_red_alg):
    print(f"   {name:5s}  {v:6.2f}%")
print(f"   ---- overall avg = {float(np.mean(miss_red_alg)):6.2f}%")
print()
print("(b) Pipeline Funnel shares (%) — avg of components per alg:")
print("        GotData  Throttled  IdxRFAIL  DataRFAIL  Other")
for name, row in zip(alg_labels, funnel_alg_rows):
    print(f"   {name:5s}  "
          f"{row[0]:7.1f}  {row[1]:9.1f}  {row[2]:8.1f}  "
          f"{row[3]:9.1f}  {row[4]:5.1f}")
# MST note (for transparency — the skipped algorithm)
mst_rec = DATA.get("ls_mst_rmat12") or {}
mst_ima = (mst_rec.get("derived") or {}).get("ima_total_reduction_pct")
print()
print("Note: MST (ls_mst_rmat12) excluded because it has no IMA data "
      f"(ima_total_reduction_pct = {mst_ima}).")

print(f"\nSaved to {out_dir}/proto_r4_53_mechanism.{{pdf,svg}}")
