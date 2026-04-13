#!/usr/bin/env python3
"""
Round 4 §5.5 Layout B: Hardware storage visualization (single column).

Two-panel single-column figure (3.5" wide):
  (a) GRASP per-SM storage breakdown — horizontal stacked bar (6 components)
  (b) Storage per-thread comparison vs SOTA prefetchers — vertical bar chart
      with GRASP highlighted in palette[0] green.

Round 4 conventions:
  - PALETTE_TOL_BRIGHT (greens/reds/purples) — same family as r4 §5.2/5.3
  - HATCHES_DENSE for B&W readability
  - GRASP = palette[0] green, no hatch (solid) — stands out from baselines
  - Subplot labels (a)/(b) BELOW the axis via subplot_label()
  - parents[5] path depth (round4/ is 5 levels deep from repo root)

============================================================================
Data source & assumptions
============================================================================

Numbers below match proto_r4_55_A.tex exactly. They trace to:
  ima_plan/07_paper_outline/paper_structure.md  §3.7 Table 2 (lines 402-416)
  ima_plan/07_paper_outline/paper_structure.md  §5.6 Table 4 (lines 565-579)

GRASP per-SM storage breakdown (SM80_A100 config):
  CD FIFO   20 entries × 16 B =  320 B  — register dependency tracking
  CT        32 entries × 16 B =  512 B  — indexed IMA chain storage
  TT         8 entries ×  8 B =   64 B  — data PC + offset
  IST       64 entries × 16 B = 1024 B  — per-PC iteration stride
  PRB       32 entries ×  8 B =  256 B  — pending prefetch requests
  Misc                          ~100 B  — throttle ctrl + counters
  --------------------------------------------------------------------
  TOTAL                         ~2276 B ≈ 2.3 KB / SM ≈ 36 B / warp

Comparison baselines (per-thread effective):
  IMP    [MICRO'15]  900  B / core    (CPU, dedicated)
  DMP    [HPCA'24]   900  B / core    (CPU, dedicated)
  Tyche  [TACO'24]   570  B / core    (CPU, dedicated)
  Snake  [MICRO'23]   12  B / warp    (GPU, ≈ 800 B / SM)
  GRASP  (this work)  36  B / warp    (GPU, 2276 B / SM, this paper)

Note: CPU "per-core" and GPU "per-warp" use different normalisations. Numbers
are reproduced from prior-work papers and from paper_structure.md's tables —
update both files in lock-step if values change.
============================================================================
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np

# round4/ is 5 levels deep from repo root
_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, save_fig,
    PALETTE_TOL_BRIGHT, HATCHES_DENSE, subplot_label,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Data ─────────────────────────────────────────────────────────────────────
# (a) GRASP per-SM breakdown (bytes, ordered for stacked-bar readability)
GRASP_COMPONENTS = [
    ("CD FIFO",  320),
    ("CT",       512),
    ("TT",        64),
    ("IST",     1024),
    ("PRB",      256),
    ("Misc",     100),
]
GRASP_TOTAL_B = sum(b for _, b in GRASP_COMPONENTS)  # 2276 B
assert GRASP_TOTAL_B == 2276, f"sanity: total={GRASP_TOTAL_B}"

# (b) Per-thread comparison: "thread" means a CPU core for IMP/DMP/Tyche
# and a GPU warp for Snake/GRASP. Numbers in BYTES.
BASELINES = [
    ("IMP",      900,  False),  # MICRO'15 — CPU per-core
    ("DMP",      900,  False),  # HPCA'24  — CPU per-core
    ("Tyche",    570,  False),  # TACO'24  — CPU per-core
    ("Snake",     12,  False),  # MICRO'23 — GPU per-warp
    ("GRASP",     36,  True),   # ours     — GPU per-warp
]


# ── Figure ───────────────────────────────────────────────────────────────────
# Single-column, two-panel stack. Panel (a) is a horizontal stacked bar with
# the legend on the right side. Panel (b) is a compact vertical bar chart
# with bracket annotations under the x labels.
fig, axes = plt.subplots(
    nrows=2, ncols=1,
    figsize=(3.5, 3.3),
    constrained_layout=True,
    gridspec_kw={"height_ratios": [1.0, 1.85]},
)
ax_a, ax_b = axes
fig.set_constrained_layout_pads(h_pad=0.05, hspace=0.05)


# ── Panel (a): GRASP storage breakdown — horizontal stacked bar ─────────────
# We map each component to a different palette color + hatch so the bar
# segments remain distinguishable in B&W printing.
COMPONENT_STYLE = [
    # (color,                          hatch)
    (PALETTE_TOL_BRIGHT[0], HATCHES_DENSE[0]),  # CD FIFO  — green solid
    (PALETTE_TOL_BRIGHT[1], HATCHES_DENSE[1]),  # CT       — red /
    (PALETTE_TOL_BRIGHT[2], HATCHES_DENSE[2]),  # TT       — purple \
    (PALETTE_TOL_BRIGHT[3], HATCHES_DENSE[3]),  # IST      — yellow x
    (PALETTE_TOL_BRIGHT[4], HATCHES_DENSE[4]),  # PRB      — gray .
    ("#BFBFBF",             HATCHES_DENSE[5]),  # Misc     — light gray +
]

cum = 0.0
y_bar = 0.5  # single horizontal bar centered
bar_h = 0.50
for (name, val), (color, hatch) in zip(GRASP_COMPONENTS, COMPONENT_STYLE):
    ax_a.barh(
        y_bar, val, left=cum, height=bar_h,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.5,
        label=f"{name} ({val} B)",
    )
    # In-bar size annotation if segment wide enough; otherwise skip to keep
    # the figure clean (the legend already lists all numbers).
    if val >= 240:
        ax_a.text(
            cum + val / 2, y_bar,
            f"{val}",
            ha="center", va="center",
            fontsize=6, color="white" if name in ("CD FIFO", "IST") else "black",
            fontweight="bold",
        )
    cum += val

# Total annotation ABOVE the bar (centered).
ax_a.annotate(
    f"Total: {GRASP_TOTAL_B} B  $\\approx$  2.3 KB / SM",
    xy=(GRASP_TOTAL_B / 2, y_bar + bar_h / 2),
    xytext=(0, 5), textcoords="offset points",
    ha="center", va="bottom",
    fontsize=7, fontweight="bold", color="#222222",
)

ax_a.set_xlim(0, GRASP_TOTAL_B * 1.05)
ax_a.set_ylim(0.0, 1.10)
ax_a.set_yticks([])
ax_a.set_xlabel("Storage (Bytes per SM)", fontsize=7.5, labelpad=2)
ax_a.tick_params(axis="x", labelsize=6.5)
# Hide left/right/top spines so the bar visually floats
for side in ("left", "right", "top"):
    ax_a.spines[side].set_visible(False)

# Legend OUTSIDE-RIGHT of panel (a) so it doesn't compete with the
# subplot label below the axis. Use a 1-column compact legend.
leg = ax_a.legend(
    loc="center left", bbox_to_anchor=(1.01, 0.5),
    ncol=1, fontsize=5.6, frameon=False,
    handlelength=1.2, handleheight=0.8,
    handletextpad=0.3, labelspacing=0.30,
    borderaxespad=0,
)
# Subplot label below x-axis (paper convention).
# y in axes-fraction; -0.55 sits just below the x-axis label.
subplot_label(ax_a, "(a) GRASP per-SM Storage Breakdown", y=-0.62)


# ── Panel (b): Per-thread comparison ────────────────────────────────────────
# Vertical bars on a log scale (CPU schemes are 25x larger than GPU per-warp).
labels = [name for name, _, _ in BASELINES]
values = np.array([v for _, v, _ in BASELINES], dtype=float)
is_ours = np.array([flag for _, _, flag in BASELINES])

# Color/hatch: GRASP gets palette[0] green solid, others use palette[1..4]
colors = [
    PALETTE_TOL_BRIGHT[1],  # IMP   — red
    PALETTE_TOL_BRIGHT[2],  # DMP   — purple
    PALETTE_TOL_BRIGHT[3],  # Tyche — yellow
    PALETTE_TOL_BRIGHT[4],  # Snake — gray
    PALETTE_TOL_BRIGHT[0],  # GRASP — green
]
hatches = [
    HATCHES_DENSE[1],
    HATCHES_DENSE[2],
    HATCHES_DENSE[3],
    HATCHES_DENSE[4],
    HATCHES_DENSE[0],  # solid for GRASP
]

x = np.arange(len(labels))
bars = ax_b.bar(
    x, values, width=0.62,
    color=colors, hatch=hatches,
    edgecolor="black", linewidth=0.5,
    zorder=3,
)

# Highlight GRASP with a thicker outline
for bar, flag in zip(bars, is_ours):
    if flag:
        bar.set_linewidth(1.2)
        bar.set_edgecolor("black")

# Log scale because 12 B vs 900 B differs by ~75x
ax_b.set_yscale("log")
ax_b.set_ylim(5, 3000)
ax_b.set_ylabel("Storage / Thread (B, log)", fontsize=7.5)
ax_b.tick_params(axis="y", labelsize=6.5)

# Bar value annotations
for bar, v in zip(bars, values):
    cx = bar.get_x() + bar.get_width() / 2
    ax_b.annotate(
        f"{int(v)}",
        xy=(cx, v),
        xytext=(0, 2), textcoords="offset points",
        ha="center", va="bottom",
        fontsize=6.0, fontweight="bold",
    )

# Group annotations: bracket "CPU per-core" and "GPU per-warp" under the
# x labels so the reader knows the units differ across baselines.
ax_b.set_xticks(x)
ax_b.set_xticklabels(labels, fontsize=7)
ax_b.set_xlim(-0.6, len(labels) - 0.4)

# CPU bracket spans IMP, DMP, Tyche (indices 0..2)
# GPU bracket spans Snake, GRASP (indices 3..4)
# Bracket sits below the x tick labels (negative axes fraction)
def _bracket(ax, x0, x1, label, y_axfrac=-0.32, color="#444444"):
    ax.annotate(
        "", xy=(x0, y_axfrac), xytext=(x1, y_axfrac),
        xycoords=("data", "axes fraction"),
        textcoords=("data", "axes fraction"),
        arrowprops=dict(arrowstyle="-", color=color, lw=0.7),
        annotation_clip=False,
    )
    ax.annotate(
        label,
        xy=((x0 + x1) / 2, y_axfrac - 0.06),
        xycoords=("data", "axes fraction"),
        ha="center", va="top",
        fontsize=6.5, color=color, fontstyle="italic",
        annotation_clip=False,
    )


_bracket(ax_b, -0.30, 2.30, "CPU per-core")
_bracket(ax_b,  2.70, 4.30, "GPU per-warp")

subplot_label(ax_b, "(b) Storage per Thread vs Prior Work", y=-0.65)


# ── Save & Close ────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_55_B", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== Round 4 §5.5 Layout B — Hardware Cost Visualization ===")
print()
print("(a) GRASP per-SM breakdown:")
for name, val in GRASP_COMPONENTS:
    pct = 100.0 * val / GRASP_TOTAL_B
    print(f"  {name:8s}  {val:5d} B  ({pct:5.1f} %)")
print(f"  {'TOTAL':8s}  {GRASP_TOTAL_B:5d} B  (100.0 %)  "
      f"≈ {GRASP_TOTAL_B/1024:.2f} KB / SM")
print()
print("(b) Per-thread comparison (B):")
for name, val, flag in BASELINES:
    marker = "  *" if flag else "   "
    print(f"  {name:6s} {val:5d} B {marker}")
print()
print(f"GRASP / IMP    : {36 / 900:.3f}x   (GRASP uses {(1 - 36/900)*100:.0f}% less per thread)")
print(f"GRASP / Snake  : {36 / 12:.2f}x    (GRASP uses {(36/12 - 1)*100:.0f}% more per thread)")
print(f"\nSaved to {out_dir}/proto_r4_55_B.{{pdf,svg}}")
