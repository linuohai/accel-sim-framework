#!/usr/bin/env python3
"""
Proto Figure A: IPC Speedup (%) — 28 workloads × 3 schemes.

Grouped bar chart (full-width, 7.0") showing:
  No-PF (baseline=0), GRASP (D5b), Ideal L1D

Data sources:
  - D5b GRASP:  ima_plan/06_evaluation_plan/throttle_control_results.md
  - Ideal L1D:  ima_plan/06_evaluation_plan/experiment_results.md
  - soc-LJ1:    experiment_results.md (Default config)
  - Extended:    ima_plan/06_evaluation_plan/extra_case/extra_case_results.csv
"""

import sys
from pathlib import Path
import numpy as np

# ── Plot style import ────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, CB10, HATCHES, save_fig

apply_style()
import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms

# ── Hardcoded data (extracted from source files) ─────────────────────────────
# Each entry: (key, base_ipc, grasp_ipc, ideal_ipc_or_nan)
# GRASP IPC from D5b section of throttle_control_results.md
# Ideal IPC from experiment_results.md
# soc-LJ1: Default config from experiment_results.md
# Extended: extra_case_results.csv (no Ideal L1D available)

DATA = [
    # --- BFS group ---
    ("bfs_cit_dir",      5.3349,    6.0789,    7.3081),
    ("bfs_web_sym",      7.3528,   11.4992,   10.3539),
    ("bfs_flickr_sym",   9.7943,   12.4545,   14.5998),
    ("bfs_road_sym",    14.3030,   15.5202,   21.4960),
    ("bfs_socLJ_sym",   22.2490,   29.1730,   33.8400),
    # --- SSSP group ---
    ("sssp_cit_dir",     5.9499,    6.5920,    8.2054),
    ("sssp_web_sym",     9.5580,   14.0398,   13.9142),
    ("sssp_flickr_sym", 11.7493,   14.0946,   18.7164),
    ("sssp_road_sym",   17.5696,   18.6726,   24.9953),
    # --- BC group ---
    ("bc_cit_dir",      95.2826,  104.6116,  168.6582),
    ("bc_web_sym",      10.8322,   11.9936,   19.3066),
    ("bc_flickr_sym",   13.4772,   16.4246,   23.1370),
    ("bc_road_sym",     18.4855,   19.3477,   29.4113),
    # --- CC group ---
    ("cc_cit_sym",     426.7173,  410.5897,  950.4574),
    ("cc_web_sym",      50.7687,   86.7824,  166.7668),
    ("cc_flickr_sym",   46.8674,  104.0304,  132.1259),
    ("cc_road_sym",   1490.0549, 1491.3196, 2018.8964),
    # --- SpMV group ---
    ("spmv_cit_sym",   373.9836,  367.6747,  857.0579),
    ("spmv_web_sym",   129.6846,  177.2448,  461.7527),
    ("spmv_flickr_sym", 79.2566,  108.7362,  253.7695),
    ("spmv_road_sym", 1262.7443, 1249.5670, 2977.0181),
    ("spmv_socLJ_sym", 138.3245,  162.9411,  551.1573),
    # --- VC group ---
    ("vc_cit_sym",     341.7518,  348.2836,  692.7794),
    ("vc_web_sym",      52.3822,   53.3770,  141.6423),
    ("vc_road_sym",    564.1312,  566.0939,  787.0948),
    # --- Extended group ---
    ("pann_mis_flickr", 121.9414, 156.1436,   np.nan),
    ("pann_color_eco",  544.6149, 544.5200,   np.nan),
    ("ls_mst_rmat12",   134.2416, 134.2416,   np.nan),
]

# ── Compute speedup percentages ──────────────────────────────────────────────
keys = [d[0] for d in DATA]
base_ipc = np.array([d[1] for d in DATA])
grasp_ipc = np.array([d[2] for d in DATA])
ideal_ipc = np.array([d[3] for d in DATA])

grasp_speedup = (grasp_ipc - base_ipc) / base_ipc * 100.0
ideal_headroom = (ideal_ipc - base_ipc) / base_ipc * 100.0  # NaN for extended

# ── Algorithm group boundaries ───────────────────────────────────────────────
GROUPS = [
    ("BFS",  5),
    ("SSSP", 4),
    ("BC",   4),
    ("CC",   4),
    ("SpMV", 5),
    ("VC",   3),
    ("Ext.", 3),
]

# Short x-labels: dataset abbreviation only (algo shown by group label)
DATASET_ABBREV = {
    "cit_dir": "cit",
    "cit_sym": "cit",
    "web_sym": "web",
    "flickr_sym": "flk",
    "road_sym": "road",
    "socLJ_sym": "sLJ",
    "mis_flickr": "MIS",
    "color_eco": "Color",
    "mst_rmat12": "MST",
}


def short_label(key):
    """Convert key like 'bfs_cit_dir' to 'cit'."""
    if key.startswith("pann_"):
        return DATASET_ABBREV.get(key[len("pann_"):], key)
    if key.startswith("ls_"):
        return DATASET_ABBREV.get(key[len("ls_"):], key)
    parts = key.split("_", 1)
    suffix = parts[1] if len(parts) > 1 else key
    return DATASET_ABBREV.get(suffix, suffix)


xlabels = [short_label(k) for k in keys]

# ── Geometric mean ───────────────────────────────────────────────────────────
grasp_ratios = grasp_ipc / base_ipc
ideal_ratios = ideal_ipc / base_ipc

valid_grasp = grasp_ratios[~np.isnan(grasp_ratios)]
valid_ideal = ideal_ratios[~np.isnan(ideal_ratios)]

gmean_grasp = np.exp(np.mean(np.log(valid_grasp)))
gmean_ideal = np.exp(np.mean(np.log(valid_ideal)))
gmean_grasp_pct = (gmean_grasp - 1.0) * 100.0
gmean_ideal_pct = (gmean_ideal - 1.0) * 100.0

# ── Plot ─────────────────────────────────────────────────────────────────────
n = len(DATA)
x = np.arange(n + 1)  # +1 for GMEAN
bar_w = 0.30

fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.42),
    constrained_layout=True,
)

# Two active schemes (No-PF is the 0-line baseline, shown only in legend)
scheme_grasp = ("GRASP",     CB10[0], HATCHES[0])   # blue, solid
scheme_ideal = ("Ideal L1D", CB10[4], HATCHES[2])   # light blue, \\

# Build arrays with GMEAN appended
grasp_vals = np.append(grasp_speedup, gmean_grasp_pct)
ideal_vals = np.append(ideal_headroom, gmean_ideal_pct)

# Cap: show all GRASP bars at true height (max 122%), only clip Ideal outliers
Y_CAP = 130.0

# ── Draw bars ────────────────────────────────────────────────────────────────
bar_containers = {}
for shift, (label, color, hatch), vals in [
    (-0.5, scheme_grasp, grasp_vals),
    (+0.5, scheme_ideal, ideal_vals),
]:
    offset = shift * bar_w
    display = np.where(np.isnan(vals), np.nan, np.minimum(vals, Y_CAP))
    bars = ax.bar(
        x + offset, display, bar_w,
        label=label, color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )
    bar_containers[label] = (bars, vals, color)

# ── Annotate capped Ideal bars ───────────────────────────────────────────────
# Only annotate Ideal L1D bars that exceed Y_CAP.
_, ideal_orig, ideal_color = bar_containers["Ideal L1D"]
for j, bar in enumerate(bar_containers["Ideal L1D"][0]):
    orig = ideal_orig[j]
    if np.isnan(orig) or orig <= Y_CAP:
        continue
    ax.annotate(
        f"{orig:.0f}",
        xy=(bar.get_x() + bar.get_width() / 2, Y_CAP),
        xytext=(0, 2), textcoords="offset points",
        ha="center", va="bottom",
        fontsize=5, color=ideal_color,
        zorder=5,
    )

# ── Annotate GMEAN bars with values ─────────────────────────────────────────
# Place a combined annotation just left of the GMEAN separator to avoid any
# right-edge clipping. Stacked vertically: Ideal on top, GRASP below.
gmean_idx = n
sep_x = n - 0.5  # x-position of the separator line
_, grasp_arr, grasp_clr = bar_containers["GRASP"]
_, ideal_arr, ideal_clr = bar_containers["Ideal L1D"]
grasp_v = grasp_arr[gmean_idx]
ideal_v = ideal_arr[gmean_idx]

# GRASP annotation: above its bar, left of separator
ax.text(sep_x - 0.15, min(grasp_v, Y_CAP) + 3,
        f"+{grasp_v:.1f}%", ha="right", va="bottom",
        fontsize=5.5, fontweight="bold", color=grasp_clr, zorder=5)
# Ideal annotation: above its bar, left of separator
ax.text(sep_x - 0.15, min(ideal_v, Y_CAP) + 3,
        f"+{ideal_v:.1f}%", ha="right", va="bottom",
        fontsize=5.5, fontweight="bold", color=ideal_clr, zorder=5)

# ── Vertical dashed lines between algorithm groups ───────────────────────────
cumulative = 0
for gname, gsize in GROUPS[:-1]:
    cumulative += gsize
    ax.axvline(x=cumulative - 0.5, color="#999999", linestyle="--",
               linewidth=0.5, alpha=0.6, zorder=1)

# ── GMEAN separator ─────────────────────────────────────────────────────────
ax.axvline(x=n - 0.5, color="black", linestyle="-",
           linewidth=0.8, alpha=0.8, zorder=1)

# ── Group labels below x-tick labels ────────────────────────────────────────
cumulative = 0
for gname, gsize in GROUPS:
    center = cumulative + (gsize - 1) / 2.0
    ax.annotate(
        gname,
        xy=(center, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -28), textcoords="offset points",
        ha="center", va="top",
        fontsize=7, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize
ax.annotate(
    "Avg",
    xy=(n, 0), xycoords=("data", "axes fraction"),
    xytext=(0, -28), textcoords="offset points",
    ha="center", va="top",
    fontsize=7, fontweight="bold",
    annotation_clip=False,
)

# ── Axes formatting ──────────────────────────────────────────────────────────
ax.set_ylabel("IPC Speedup (%)")
ax.set_ylim(-8, Y_CAP + 12)
ax.set_xlim(-0.6, n + 1.0)

# X-tick labels
xtick_labels = xlabels + [""]
ax.set_xticks(x)
ax.set_xticklabels(xtick_labels, rotation=45, ha="right", fontsize=5.5)

# Baseline at y=0
ax.axhline(y=0, color="black", linewidth=0.6, zorder=2)

# ── Legend ───────────────────────────────────────────────────────────────────
from matplotlib.patches import Patch
legend_patches = [
    Patch(facecolor=CB10[7], edgecolor="black", hatch=HATCHES[1],
          linewidth=0.4, label="No-PF (1.00x)"),
    Patch(facecolor=CB10[0], edgecolor="black", hatch=HATCHES[0],
          linewidth=0.4, label=f"GRASP ({gmean_grasp:.2f}x)"),
    Patch(facecolor=CB10[4], edgecolor="black", hatch=HATCHES[2],
          linewidth=0.4, label=f"Ideal L1D ({gmean_ideal:.2f}x)"),
]
ax.legend(
    handles=legend_patches, ncol=3, fontsize=6.5,
    loc="upper left", frameon=False,
    handlelength=1.4, handleheight=0.9,
    bbox_to_anchor=(0.0, 1.01),
)

# ── Save ─────────────────────────────────────────────────────────────────────
# Override pad_inches (mplstyle default 0.02 is too tight for edge annotations)
out_dir = Path(__file__).resolve().parent
out_dir.mkdir(parents=True, exist_ok=True)
for fmt in ("pdf", "svg"):
    fig.savefig(out_dir / f"proto_figA_speedup.{fmt}", format=fmt,
                pad_inches=0.05)
plt.close(fig)

print(f"GMEAN GRASP speedup: {gmean_grasp_pct:.1f}% ({gmean_grasp:.3f}x)")
print(f"GMEAN Ideal headroom: {gmean_ideal_pct:.1f}% ({gmean_ideal:.3f}x)")
print(f"Saved to {out_dir}/proto_figA_speedup.{{pdf,svg}}")
