#!/usr/bin/env python3
"""
Round 5 §5.4 — Combined Throttle Policy figure (IPC Speedup + Coverage).

Single figure* with two stacked panels sharing the 22-workload x-axis (IPC superset):
  (a) IPC Speedup    — 22 workloads × 3 schemes (Default / D5b / T40C200)
  (b) Data Coverage  — 16 workloads (subset of 22) at aligned x-positions,
                       empty slots for 6 workloads without coverage data:
                       cc_cit, spmv_cit, vc_cit, vc_web, cc_road, spmv_road

Consolidates proto_r4_54_B_ipc.py and proto_r4_54_B_cov.py into a single
figure to reduce LaTeX float queue pressure in §5 Evaluation (per Gemini-3.1-Pro
layout advice, 2026-04-08).

Style: matches proto_r4_52_A_nohatch.py — PALETTE_TOL_BRIGHT, NO hatching,
vertical group separators, own GMEAN bar per panel.

Output: throttle.{pdf,svg}  (7.0" × 5.5" figure*)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

# NOTE: round5_eval/ is 5 levels deep from repo root
_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/figures/eval_prototypes/round4_54"))

from plot_util import (  # noqa: E402
    apply_style, save_fig,
    PALETTE_TOL_BRIGHT,
)
from workload_names import (  # noqa: E402
    ORDERED_27, SHORT_NAME, ALG_GROUPS,
)
from _data import (  # noqa: E402
    THROTTLE_IPC_PCT, THROTTLE_COV, pct_to_mult, gmean,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Master workload order: 22 from IPC (COV's 16 is strict subset) ────────
WORKLOADS = [k for k in ORDERED_27 if k in THROTTLE_IPC_PCT]
n_wkl = len(WORKLOADS)
assert n_wkl == 22, f"Expected 22 throttle IPC workloads, got {n_wkl}"

COV_WORKLOADS = [k for k in WORKLOADS if k in THROTTLE_COV]
assert len(COV_WORKLOADS) == 16, \
    f"Expected 16 throttle COV workloads, got {len(COV_WORKLOADS)}"


# ── IPC data (multiplier form) ─────────────────────────────────────────────
def ipc_mult(idx):
    return np.array([pct_to_mult(THROTTLE_IPC_PCT[k][idx]) for k in WORKLOADS])


ipc_default = ipc_mult(0)
ipc_d5b     = ipc_mult(1)
ipc_t40     = ipc_mult(2)
ipc_default_gm = gmean(ipc_default)
ipc_d5b_gm     = gmean(ipc_d5b)
ipc_t40_gm     = gmean(ipc_t40)


# ── COV data (percent form) — aligned to 22-wkl x-positions via NaN ────────
def cov_pct_aligned(idx):
    arr = np.full(n_wkl, np.nan, dtype=float)
    for i, k in enumerate(WORKLOADS):
        if k in THROTTLE_COV:
            arr[i] = THROTTLE_COV[k][idx]
    return arr


cov_default = cov_pct_aligned(0)
cov_d5b     = cov_pct_aligned(1)
cov_t40     = cov_pct_aligned(2)
# GMEAN computed only over the 16 available workloads
cov_default_gm = float(np.nanmean(cov_default))
cov_d5b_gm     = float(np.nanmean(cov_d5b))
cov_t40_gm     = float(np.nanmean(cov_t40))


labels = [SHORT_NAME[k] for k in WORKLOADS] + ["GMEAN"]


# ── Layout ─────────────────────────────────────────────────────────────────
n_total = n_wkl + 1
GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.25
offsets = np.array([-1.0, 0.0, 1.0]) * bar_w

# Panel A (IPC) y-axis
A_Y_LO, A_Y_HI = 0.90, 1.50
# Panel B (Coverage) y-axis
B_Y_LO, B_Y_HI = 0.0, 100.0


fig, axes = plt.subplots(
    nrows=2, ncols=1,
    figsize=(3.5, 3.8),
    sharex=True,
    constrained_layout=True,
)
ax_a, ax_b = axes


# ── Panel A — IPC Speedup ──────────────────────────────────────────────────
ipc_default_all = np.append(ipc_default, ipc_default_gm)
ipc_d5b_all     = np.append(ipc_d5b, ipc_d5b_gm)
ipc_t40_all     = np.append(ipc_t40, ipc_t40_gm)

ipc_schemes = [
    ("Default", ipc_default_all, PALETTE_TOL_BRIGHT[1]),  # red
    ("D5b",     ipc_d5b_all,     PALETTE_TOL_BRIGHT[0]),  # green
    ("T40C200", ipc_t40_all,     PALETTE_TOL_BRIGHT[3]),  # yellow
]

ipc_bars = {}
for i, (name, vals, color) in enumerate(ipc_schemes):
    clipped = np.minimum(vals, A_Y_HI)
    heights = clipped - A_Y_LO
    bars = ax_a.bar(
        x + offsets[i], heights, bar_w,
        bottom=A_Y_LO,
        color=color,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )
    ipc_bars[name] = (bars, vals, color)

# Annotate clipped IPC outliers (stacked if overlapping)
scheme_order = [s[0] for s in ipc_schemes]
for j in range(n_total):
    clipped_here = [(si, n, ipc_bars[n][1][j], ipc_bars[n][2])
                    for si, n in enumerate(scheme_order)
                    if ipc_bars[n][1][j] >= A_Y_HI]
    for stack_i, (si, name, v, color) in enumerate(clipped_here):
        bars, _, _ = ipc_bars[name]
        cx = bars[j].get_x() + bars[j].get_width() / 2
        y_offset = 1.5 + stack_i * 6.5
        ax_a.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, A_Y_HI),
            xytext=(0, y_offset), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.2, fontweight="bold", color=color,
            zorder=6,
        )

# Regression (below A_Y_LO)
for name, (bars, vals, color) in ipc_bars.items():
    for j, bar in enumerate(bars):
        v = vals[j]
        if v >= A_Y_LO:
            continue
        cx = bar.get_x() + bar.get_width() / 2
        ax_a.annotate(
            f"{v:.2f}\u00d7",
            xy=(cx, A_Y_LO + 0.002),
            xytext=(0, 1.5), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.2, fontweight="bold", color=color,
            zorder=6,
        )

ax_a.set_ylim(A_Y_LO, A_Y_HI + 0.03)
ax_a.set_ylabel("IPC Speedup (\u00d7)", fontsize=7.5, labelpad=2)
ax_a.set_yticks([0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
ax_a.set_yticklabels([f"{t:.1f}\u00d7" for t in
                      [0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5]], fontsize=6.5)
ax_a.tick_params(axis="y", length=2, pad=1)
ax_a.axhline(1.0, color="#888888", linewidth=0.5, linestyle=":",
             alpha=0.7, zorder=1)

# Inline panel title
ax_a.text(
    0.005, 0.94, "(a) IPC Speedup",
    transform=ax_a.transAxes,
    ha="left", va="top",
    fontsize=7.5, fontweight="bold",
    zorder=7,
)


# ── Panel B — Coverage ─────────────────────────────────────────────────────
cov_default_all = np.append(cov_default, cov_default_gm)
cov_d5b_all     = np.append(cov_d5b, cov_d5b_gm)
cov_t40_all     = np.append(cov_t40, cov_t40_gm)

cov_schemes = [
    ("Default", cov_default_all, PALETTE_TOL_BRIGHT[1]),
    ("D5b",     cov_d5b_all,     PALETTE_TOL_BRIGHT[0]),
    ("T40C200", cov_t40_all,     PALETTE_TOL_BRIGHT[3]),
]

for i, (name, vals, color) in enumerate(cov_schemes):
    # NaN bars automatically rendered as empty (no bar drawn)
    heights = np.where(np.isnan(vals), 0.0, vals - B_Y_LO)
    ax_b.bar(
        x + offsets[i], heights, bar_w,
        bottom=B_Y_LO,
        color=color,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )

ax_b.set_ylim(B_Y_LO, B_Y_HI + 3.0)
ax_b.set_ylabel("Data Coverage (%)", fontsize=7.5, labelpad=2)
ax_b.set_yticks([0, 25, 50, 75, 100])
ax_b.set_yticklabels([f"{t:d}%" for t in [0, 25, 50, 75, 100]], fontsize=6.5)
ax_b.tick_params(axis="y", length=2, pad=1)

ax_b.text(
    0.005, 0.94, "(b) Data Coverage",
    transform=ax_b.transAxes,
    ha="left", va="top",
    fontsize=7.5, fontweight="bold",
    zorder=7,
)

# Mark missing COV workloads with a light gray "n/a" annotation
missing_cov = [k for k in WORKLOADS if k not in THROTTLE_COV]
for k in missing_cov:
    j = WORKLOADS.index(k)
    ax_b.text(
        x[j], B_Y_LO + 2.0, "n/a",
        ha="center", va="bottom",
        fontsize=4.5, color="#888888", style="italic",
        zorder=4,
    )


# ── Group separators + labels (shared across both panels) ────────────────
sub_group_counts = []
for gname, gwkls in ALG_GROUPS:
    present = [w for w in gwkls if w in THROTTLE_IPC_PCT]
    if not present:
        continue
    sub_group_counts.append((gname, len(present)))

offset_i = 0
for idx, (gname, gsize) in enumerate(sub_group_counts):
    offset_i += gsize
    if idx < len(sub_group_counts) - 1:
        sep_x = offset_i - 0.5
        for ax in (ax_a, ax_b):
            ax.axvline(x=sep_x, color="#999999", linestyle="--",
                       linewidth=0.5, alpha=0.7, zorder=1)

gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
for ax in (ax_a, ax_b):
    ax.axvline(x=gmean_sep_x, color="black", linestyle="-",
               linewidth=0.8, alpha=0.8, zorder=1)
    ax.set_xlim(-0.7, x[-1] + 0.7)


# ── X-axis: bottom panel only ──────────────────────────────────────────────
ax_a.tick_params(axis="x", which="both", length=0)
ax_b.set_xticks(x)
ax_b.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.0)
ax_b.tick_params(axis="x", length=2, pad=1)

# Algorithm group labels (only under bottom panel)
cum = 0
for gname, gsize in sub_group_counts:
    centre = cum + (gsize - 1) / 2.0
    ax_b.annotate(
        gname,
        xy=(centre, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -26), textcoords="offset points",
        ha="center", va="top",
        fontsize=7, fontweight="bold",
        annotation_clip=False,
    )
    cum += gsize
ax_b.annotate(
    "Avg",
    xy=(x[-1], 0), xycoords=("data", "axes fraction"),
    xytext=(0, -26), textcoords="offset points",
    ha="center", va="top",
    fontsize=7, fontweight="bold",
    annotation_clip=False,
)


# ── Shared legend at top of figure ─────────────────────────────────────────
legend_patches = [
    Patch(facecolor=PALETTE_TOL_BRIGHT[1], edgecolor="black", linewidth=0.4,
          label="Default"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[0], edgecolor="black", linewidth=0.4,
          label="D5b"),
    Patch(facecolor=PALETTE_TOL_BRIGHT[3], edgecolor="black", linewidth=0.4,
          label="T40C200"),
]
fig.legend(
    handles=legend_patches, ncol=3, fontsize=6.5,
    loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False,
    handlelength=1.1, handleheight=0.8,
    columnspacing=0.9, handletextpad=0.3,
    borderaxespad=0,
)


# ── Save ───────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "throttle", out_dir)
plt.close(fig)


# ── Console summary ────────────────────────────────────────────────────────
print("=== Round 5 §5.4 Throttle Policy — 2-panel combined ===")
print(f"IPC panel: {n_wkl} workloads  (22 from THROTTLE_IPC_PCT)")
print(f"COV panel: {len(COV_WORKLOADS)} workloads  (16 from THROTTLE_COV, 6 n/a)")
print(f"\n(a) IPC Speedup GMEAN:")
print(f"  Default  {ipc_default_gm:.3f}\u00d7")
print(f"  D5b      {ipc_d5b_gm:.3f}\u00d7")
print(f"  T40C200  {ipc_t40_gm:.3f}\u00d7")
print(f"\n(b) Data Coverage avg (over 16 wkls):")
print(f"  Default  {cov_default_gm:5.2f}%")
print(f"  D5b      {cov_d5b_gm:5.2f}%")
print(f"  T40C200  {cov_t40_gm:5.2f}%")
print(f"\nMissing COV workloads: {missing_cov}")
print(f"\nSaved to {out_dir}/throttle.{{pdf,svg}}")
