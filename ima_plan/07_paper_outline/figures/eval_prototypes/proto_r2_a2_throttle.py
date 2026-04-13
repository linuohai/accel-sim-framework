#!/usr/bin/env python3
"""Round-2 Fig A2: Throttle Control Ablation — Default vs D5b vs T40C200.

Two vertically stacked subplots (shared x-axis):
  (a) IPC Speedup (%) — grouped bars per workload
  (b) Data Coverage (%) — grouped bars per workload (same 3 schemes)

Key insight: D5b improves Data Coverage *dramatically* while keeping similar
IPC speedup vs Default. T40C200 sits in between. This shows TC's primary
value is *quality control* (coverage) rather than raw IPC.

Data source:
  ima_plan/06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md
  §Exp-B "Throttle Control Ablation":
    - "IPC Speedup% (22 workloads)"
    - "Data Coverage%"

Workload subset: same 13 representative workloads as proto_r2_a1_component +
GMEAN bar at the right.
"""

import sys
from pathlib import Path

import numpy as np

# ── Plot style import ────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, CB10, HATCHES
from workload_names import SHORT_NAME

apply_style()
import matplotlib.pyplot as plt

OUT_DIR = Path(__file__).resolve().parent

# ── Data: §Exp-B IPC Speedup% ────────────────────────────────────────────────
# (default_pct, d5b_pct, t40c200_pct)
SPEEDUP = {
    "bfs_cit_dir":     (+13.6, +13.9, +14.0),
    "sssp_cit_dir":    (+11.0, +10.8, +10.8),
    "bc_cit_dir":      (+9.8,  +9.8,  +9.8),
    "bfs_web_sym":     (+56.1, +56.4, +56.2),
    "sssp_web_sym":    (+46.6, +46.9, +46.9),
    "bc_web_sym":      (+10.9, +10.7, +14.2),
    "cc_web_sym":      (+93.6, +70.9, +69.8),
    "spmv_web_sym":    (+40.1, +36.7, +40.2),
    "bfs_flickr_sym":  (+27.0, +27.2, +27.2),
    "sssp_flickr_sym": (+19.9, +20.0, +20.0),
    "bc_flickr_sym":   (+21.8, +21.9, +23.6),
    "cc_flickr_sym":   (+138.6, +122.0, +102.5),
    "spmv_flickr_sym": (+38.0, +37.2, +37.8),
}

# ── Data: §Exp-B Data Coverage% ──────────────────────────────────────────────
# (default_pct, d5b_pct, t40c200_pct)
COVERAGE = {
    "bfs_cit_dir":     (18.3, 38.3, 38.3),
    "sssp_cit_dir":    (17.2, 37.1, 37.0),
    "bc_cit_dir":      ( 5.6, 40.4, 40.4),
    "bfs_web_sym":     (26.9, 35.5, 34.4),
    "sssp_web_sym":    (23.1, 31.7, 31.1),
    "bc_web_sym":      ( 5.5, 38.0, 37.9),
    "cc_web_sym":      (34.1, 36.4, 36.2),
    "spmv_web_sym":    ( 5.9, 10.8,  8.2),
    "bfs_flickr_sym":  (48.8, 68.7, 67.6),
    "sssp_flickr_sym": (47.5, 65.9, 65.4),
    "bc_flickr_sym":   (16.6, 63.2, 63.2),
    "cc_flickr_sym":   (59.0, 76.4, 71.1),
    "spmv_flickr_sym": (24.2, 54.1, 51.1),
}

# ── Display order (algorithm-grouped, matches proto_r2_a1) ───────────────────
ORDERED = [
    "bfs_cit_dir",
    "bfs_web_sym",
    "bfs_flickr_sym",
    "sssp_cit_dir",
    "sssp_web_sym",
    "sssp_flickr_sym",
    "bc_cit_dir",
    "bc_web_sym",
    "bc_flickr_sym",
    "cc_web_sym",
    "cc_flickr_sym",
    "spmv_web_sym",
    "spmv_flickr_sym",
]
assert set(ORDERED) == set(SPEEDUP.keys()) == set(COVERAGE.keys())

# Algorithm group boundaries
GROUPS = [
    ("BFS",  3),
    ("SSSP", 3),
    ("BC",   3),
    ("CC",   2),
    ("SpMV", 2),
]

# ── Extract arrays ───────────────────────────────────────────────────────────
sp_default = np.array([SPEEDUP[k][0] for k in ORDERED])
sp_d5b     = np.array([SPEEDUP[k][1] for k in ORDERED])
sp_t40     = np.array([SPEEDUP[k][2] for k in ORDERED])

cv_default = np.array([COVERAGE[k][0] for k in ORDERED])
cv_d5b     = np.array([COVERAGE[k][1] for k in ORDERED])
cv_t40     = np.array([COVERAGE[k][2] for k in ORDERED])


# ── Mean helpers ─────────────────────────────────────────────────────────────
def gmean_pct(pct_arr):
    ratios = 1.0 + pct_arr / 100.0
    return (np.exp(np.mean(np.log(ratios))) - 1.0) * 100.0


sp_gmean_default = gmean_pct(sp_default)
sp_gmean_d5b     = gmean_pct(sp_d5b)
sp_gmean_t40     = gmean_pct(sp_t40)

cv_amean_default = float(np.mean(cv_default))
cv_amean_d5b     = float(np.mean(cv_d5b))
cv_amean_t40     = float(np.mean(cv_t40))

# Append GMEAN/Avg as last bar
sp_default_p = np.append(sp_default, sp_gmean_default)
sp_d5b_p     = np.append(sp_d5b,     sp_gmean_d5b)
sp_t40_p     = np.append(sp_t40,     sp_gmean_t40)
cv_default_p = np.append(cv_default, cv_amean_default)
cv_d5b_p     = np.append(cv_d5b,     cv_amean_d5b)
cv_t40_p     = np.append(cv_t40,     cv_amean_t40)

# ── Plot setup ───────────────────────────────────────────────────────────────
n = len(ORDERED)
n_total = n + 1  # + GMEAN
x = np.arange(n_total)
bar_w = 0.27

fig, axes = plt.subplots(
    2, 1, figsize=(7.0, 4.0),
    constrained_layout=True, sharex=True,
)
ax_sp, ax_cv = axes

# Color/hatch scheme
COL_DEFAULT = CB10[7]   # light blue / muted
COL_D5B     = CB10[0]   # primary blue (our work)
COL_T40     = CB10[2]   # gray
HATCH_DEFAULT = HATCHES[1]   # //
HATCH_D5B     = HATCHES[0]   # solid (our work)
HATCH_T40     = HATCHES[2]   # \\

schemes = [
    (-1, "Default",  COL_DEFAULT, HATCH_DEFAULT,
     sp_default_p, cv_default_p),
    ( 0, "D5b (ours)", COL_D5B,    HATCH_D5B,
     sp_d5b_p,     cv_d5b_p),
    (+1, "T40C200",  COL_T40,     HATCH_T40,
     sp_t40_p,     cv_t40_p),
]

# ── (a) IPC Speedup ──────────────────────────────────────────────────────────
for shift, label, color, hatch, sp_vals, _ in schemes:
    ax_sp.bar(
        x + shift * bar_w, sp_vals, bar_w,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        label=label,
        zorder=3,
    )

ax_sp.axhline(y=0, color="black", linewidth=0.6, zorder=2)
ax_sp.set_ylabel("Speedup (%)")
ymax = max(sp_default_p.max(), sp_d5b_p.max(), sp_t40_p.max())
ax_sp.set_ylim(-3, ymax * 1.18)
ax_sp.set_title("(a) IPC Speedup vs Baseline", fontsize=8, pad=4)

# Legend at top with averages
labels_with_avg = [
    f"Default (avg {sp_gmean_default:+.1f}%)",
    f"D5b ours (avg {sp_gmean_d5b:+.1f}%)",
    f"T40C200 (avg {sp_gmean_t40:+.1f}%)",
]
handles = []
from matplotlib.patches import Patch
for (shift, _, color, hatch, _, _), lbl in zip(schemes, labels_with_avg):
    handles.append(
        Patch(facecolor=color, edgecolor="black", hatch=hatch,
              linewidth=0.4, label=lbl)
    )
ax_sp.legend(
    handles=handles, ncol=3, fontsize=6.5, frameon=False,
    loc="upper left", bbox_to_anchor=(0.0, 1.0),
    handlelength=1.4, handleheight=0.9, columnspacing=1.4,
)

# ── (b) Data Coverage ────────────────────────────────────────────────────────
for shift, label, color, hatch, _, cv_vals in schemes:
    ax_cv.bar(
        x + shift * bar_w, cv_vals, bar_w,
        color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )

ax_cv.set_ylabel("Data Coverage (%)")
ax_cv.set_ylim(0, 100)
ax_cv.set_title(
    f"(b) Data Coverage  "
    f"(Default avg {cv_amean_default:.1f}%, D5b avg {cv_amean_d5b:.1f}%, "
    f"T40C200 avg {cv_amean_t40:.1f}%)",
    fontsize=8, pad=4,
)

# ── Annotate workloads where Coverage gap (D5b - Default) is largest ─────────
gap = cv_d5b - cv_default
top3 = np.argsort(-gap)[:3]
for idx in top3:
    factor = cv_d5b[idx] / max(cv_default[idx], 0.1)
    ax_cv.annotate(
        f"{factor:.1f}x",
        xy=(x[idx], cv_d5b[idx]),
        xytext=(0, 4), textcoords="offset points",
        ha="center", va="bottom",
        fontsize=6, fontweight="bold", color="#006400",
    )

# ── Vertical group separators ────────────────────────────────────────────────
cumulative = 0
for gname, gsize in GROUPS[:-1]:
    cumulative += gsize
    for ax in axes:
        ax.axvline(
            x=cumulative - 0.5, color="#999999",
            linestyle="--", linewidth=0.5, alpha=0.6, zorder=1,
        )

# Solid separator before GMEAN
for ax in axes:
    ax.axvline(
        x=n - 0.5, color="black", linestyle="-",
        linewidth=0.8, alpha=0.8, zorder=1,
    )

# ── Algorithm group labels under bottom subplot ──────────────────────────────
cumulative = 0
for gname, gsize in GROUPS:
    center = cumulative + (gsize - 1) / 2.0
    ax_cv.annotate(
        gname,
        xy=(center, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -32), textcoords="offset points",
        ha="center", va="top",
        fontsize=7, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize
ax_cv.annotate(
    "Avg",
    xy=(n, 0), xycoords=("data", "axes fraction"),
    xytext=(0, -32), textcoords="offset points",
    ha="center", va="top",
    fontsize=7, fontweight="bold",
    annotation_clip=False,
)

# ── X-axis tick labels (only on bottom subplot) ──────────────────────────────
xlabels = [SHORT_NAME[k] for k in ORDERED] + [""]
ax_cv.set_xticks(x)
ax_cv.set_xticklabels(xlabels, rotation=45, ha="right", fontsize=7)

for ax in axes:
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlim(-0.7, n_total - 0.3)

# ── Save ─────────────────────────────────────────────────────────────────────
save_fig(fig, "proto_r2_a2_throttle", OUT_DIR)
plt.close(fig)

# ── Verification print ──────────────────────────────────────────────────────
print(f"Saved: {OUT_DIR}/proto_r2_a2_throttle.{{pdf,svg}}")
print(f"Workloads: {n} + GMEAN")
print()
print("=== IPC Speedup (geomean) ===")
print(f"  Default : {sp_gmean_default:+6.2f}%")
print(f"  D5b     : {sp_gmean_d5b:+6.2f}%")
print(f"  T40C200 : {sp_gmean_t40:+6.2f}%")
print()
print("=== Data Coverage (arithmetic mean) ===")
print(f"  Default : {cv_amean_default:6.2f}%")
print(f"  D5b     : {cv_amean_d5b:6.2f}%  "
      f"(+{cv_amean_d5b - cv_amean_default:.1f} pp)")
print(f"  T40C200 : {cv_amean_t40:6.2f}%  "
      f"(+{cv_amean_t40 - cv_amean_default:.1f} pp)")
print()
print("=== Top-3 D5b vs Default coverage gain ===")
top3_idx = np.argsort(-(cv_d5b - cv_default))[:3]
for idx in top3_idx:
    name = SHORT_NAME[ORDERED[idx]]
    factor = cv_d5b[idx] / max(cv_default[idx], 0.1)
    print(f"  {name:9s}  {cv_default[idx]:5.1f}% -> {cv_d5b[idx]:5.1f}%  "
          f"(+{cv_d5b[idx] - cv_default[idx]:5.1f} pp, {factor:.1f}x)")
print()
print("=== KEY INSIGHT ===")
sp_delta = sp_gmean_d5b - sp_gmean_default
cv_delta = cv_amean_d5b - cv_amean_default
print(f"  D5b vs Default:  IPC {sp_delta:+.1f} pp,  "
      f"Coverage {cv_delta:+.1f} pp")
print(f"  -> D5b trades a small IPC change for a big coverage gain.")
