#!/usr/bin/env python3
"""
Round 5 §5.2 — Mechanism (single-column, 2x1 stacked).

Forked from round4/proto_r4_53_mechanism.py but laid out as two stacked
panels for a single-column figure (3.5in wide):
  (a) L1 IMA Miss Reduction per algorithm
  (b) Pipeline Funnel per algorithm

Output: mechanism.{pdf,svg}
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, save_fig, PALETTE_TOL_BRIGHT,
)
from workload_names import ALG_GROUPS  # noqa: E402

apply_style()
import matplotlib.pyplot as plt  # noqa: E402


EFF_JSON = (_REPO /
            "ima_plan/07_paper_outline/figures/effectiveness_data.json")
DATA = json.loads(EFF_JSON.read_text())["workloads"]


# ── Algorithm list (split Ext. into MIS/CLR, drop MST) ──────────────────────
ALGORITHMS = [
    ("BFS",  ALG_GROUPS[0][1]),
    ("SSSP", ALG_GROUPS[1][1]),
    ("BC",   ALG_GROUPS[2][1]),
    ("CC",   ALG_GROUPS[3][1]),
    ("SpMV", ALG_GROUPS[4][1]),
    ("VC",   ALG_GROUPS[5][1]),
    ("MIS",  ["pann_mis_flickr"]),
    ("CLR",  ["pann_color_eco"]),
]
n_alg = len(ALGORITHMS)
alg_labels = [name for name, _ in ALGORITHMS]
xs = np.arange(n_alg, dtype=float)


# ── Metric extractors ──────────────────────────────────────────────────────
def ima_total_red(rec):
    return (rec.get("derived") or {}).get("ima_total_reduction_pct")


def funnel_pcts(rec):
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


def alg_mean(metric_fn, wkls):
    vals = []
    for w in wkls:
        rec = DATA.get(w) or {}
        v = metric_fn(rec)
        if v is not None:
            vals.append(v)
    return float(np.mean(vals)) if vals else 0.0


def alg_funnel_mean(wkls):
    rows = []
    for w in wkls:
        r = funnel_pcts(DATA.get(w) or {})
        if r is not None:
            rows.append(r)
    if not rows:
        return (0.0, 0.0, 0.0, 0.0, 0.0)
    arr = np.array(rows)
    return tuple(float(x) for x in arr.mean(axis=0))


miss_red_alg = np.array([alg_mean(ima_total_red, wkls) for _, wkls in ALGORITHMS])
funnel_alg_rows = [alg_funnel_mean(wkls) for _, wkls in ALGORITHMS]
funnel_alg = np.array(funnel_alg_rows)  # shape (n_alg, 5)


# ── Colors ──────────────────────────────────────────────────────────────────
C_GRASP   = PALETTE_TOL_BRIGHT[0]  # green
C_DELIVER = PALETTE_TOL_BRIGHT[0]  # green — got data
C_THROT   = PALETTE_TOL_BRIGHT[3]  # yellow — throttled
C_IDX_RF  = PALETTE_TOL_BRIGHT[1]  # red
C_DAT_RF  = PALETTE_TOL_BRIGHT[2]  # purple
C_OTHER   = PALETTE_TOL_BRIGHT[4]  # gray


# ── Figure (stacked 2x1) ────────────────────────────────────────────────────
fig, axes = plt.subplots(
    nrows=2, ncols=1,
    figsize=(3.5, 3.3),
    constrained_layout=True,
)

bar_w = 0.65


def style_xaxis(ax):
    ax.set_xticks(xs)
    ax.set_xticklabels(alg_labels, rotation=0, ha="center", fontsize=6.0)
    ax.set_xlim(-0.7, n_alg - 0.3)
    ax.tick_params(axis="x", length=2, pad=1)


# (a) L1 IMA Miss Reduction
ax = axes[0]
Y_LO_A, Y_HI_A = 0.0, 50.0
heights_a = np.minimum(np.maximum(miss_red_alg, Y_LO_A), Y_HI_A) - Y_LO_A
ax.bar(xs, heights_a, bar_w, bottom=Y_LO_A,
       color=C_GRASP, edgecolor="black", linewidth=0.35, zorder=3)
ax.set_ylim(Y_LO_A, Y_HI_A + 3.0)
ax.set_yticks([0, 20, 40])
ax.set_yticklabels(["0%", "20%", "40%"], fontsize=6.0)
ax.set_ylabel("L1 Miss\nReduction", fontsize=6.5, labelpad=2)
ax.tick_params(axis="y", length=2, pad=1)
ax.text(
    0.02, 0.96, "(a) L1 Miss Reduction",
    transform=ax.transAxes,
    ha="left", va="top",
    fontsize=6.5, fontweight="bold",
    bbox=dict(facecolor="white", edgecolor="none", pad=1.2, alpha=0.85),
    zorder=7,
)
style_xaxis(ax)


# (b) Pipeline Funnel — stacked
ax = axes[1]
Y_LO_B, Y_HI_B = 0.0, 100.0
delivered  = funnel_alg[:, 0]
throttled  = funnel_alg[:, 1]
idx_rfail  = funnel_alg[:, 2]
data_rfail = funnel_alg[:, 3]
other_loss = funnel_alg[:, 4]
bottoms = np.zeros(n_alg)


def _stack(values, color, label):
    global bottoms
    ax.bar(xs, values, bar_w, bottom=bottoms,
           color=color, edgecolor="black", linewidth=0.35,
           label=label, zorder=3)
    bottoms = bottoms + values


_stack(delivered,  C_DELIVER, "Got Data")
_stack(throttled,  C_THROT,   "Throttled")
_stack(idx_rfail,  C_IDX_RF,  "Idx RFAIL")
_stack(data_rfail, C_DAT_RF,  "Data RFAIL")
_stack(other_loss, C_OTHER,   "Other")

ax.set_ylim(Y_LO_B, Y_HI_B + 5.0)
ax.set_yticks([0, 50, 100])
ax.set_yticklabels(["0%", "50%", "100%"], fontsize=6.0)
ax.set_ylabel("Funnel\nShare", fontsize=6.5, labelpad=2)
ax.tick_params(axis="y", length=2, pad=1)
ax.text(
    0.02, 0.96, "(b) Pipeline Funnel",
    transform=ax.transAxes,
    ha="left", va="top",
    fontsize=6.5, fontweight="bold",
    bbox=dict(facecolor="white", edgecolor="none", pad=1.2, alpha=0.85),
    zorder=7,
)
style_xaxis(ax)

# Legend inside panel (b), 5 entries single row
ax.legend(
    ncol=5, fontsize=4.6, frameon=False,
    loc="lower center", bbox_to_anchor=(0.5, 1.01),
    handlelength=0.7, handleheight=0.6,
    columnspacing=0.35, handletextpad=0.2,
    borderaxespad=0,
)


out_dir = Path(__file__).resolve().parent
save_fig(fig, "mechanism", out_dir)
plt.close(fig)


print("=== Round 5 §5.2 Mechanism (single-col, 2x1) ===")
for name, red in zip(alg_labels, miss_red_alg):
    print(f"  {name:5s}  L1 reduction = {red:5.1f}%")
print(f"\nSaved to {out_dir}/mechanism.{{pdf,svg}}")
