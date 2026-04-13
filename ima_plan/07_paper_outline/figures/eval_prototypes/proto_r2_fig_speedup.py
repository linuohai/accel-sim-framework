#!/usr/bin/env python3
"""
Proto R2 Figure: Main Speedup (DMP-style normalized) — §5.2.

Single full-width grouped bar chart: 4 schemes × 28 workloads + GMEAN.
  - Snake (MICRO'23)
  - CAPS (IPDPS'18)
  - Spare Register (HPCA'14)
  - GRASP (this work, D5b)

Y-axis: NORMALIZED speedup (× over No-PF baseline). Baseline=1.00× shown
as a horizontal dashed line. Outlier bars (e.g., GRASP CC-fl ~2.22×) are
clipped at the y-axis ceiling and annotated with the true value above.

Data sources:
  - GRASP D5b: ima_plan/07_paper_outline/figures/effectiveness_data.json
               (derived.speedup_pct field per workload)
  - SOTA Snake/CAPS/Spare Reg: ima_plan/05_implementation/sota_baseline/
               sota_experiment_results.md
               (top "全部实验状态" table for 25 Gardenia workloads;
                Extended Benchmarks section for the 3 Extended workloads,
                whose speedups are computed from SOTA IPC ÷ NP baseline IPC.)

Output: proto_r2_fig_speedup.{pdf,svg} in this directory.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

# ── Plot style import ────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import (  # noqa: E402
    apply_style, figsize_full, CB10, HATCHES, save_fig,
)
from workload_names import (  # noqa: E402
    ORDERED_28, SHORT_NAME, ALG_GROUPS, group_separator_positions,
)

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Path constants ───────────────────────────────────────────────────────────
EFF_JSON = (_REPO /
            "ima_plan/07_paper_outline/figures/effectiveness_data.json")
SOTA_MD = (_REPO /
           "ima_plan/05_implementation/sota_baseline/"
           "sota_experiment_results.md")


# ── Step 1: Load GRASP D5b speedups (28 workloads) ───────────────────────────
eff = json.loads(EFF_JSON.read_text())
grasp_pct = {}
for k in ORDERED_28:
    grasp_pct[k] = eff["workloads"][k]["derived"]["speedup_pct"]


# ── Step 2: Parse SOTA top table (25 Gardenia rows) ──────────────────────────
sota_text = SOTA_MD.read_text()

# Row pattern: | NN | `name` | dataset | Algo | +X.X% | +X.X% | +X.X% |
row_re = re.compile(
    r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
)
sota_pct = {}  # name -> {Snake, CAPS, Spare Reg}
for m in row_re.finditer(sota_text):
    name = m.group(1)
    sota_pct[name] = {
        "Snake":     float(m.group(2)),
        "CAPS":      float(m.group(3)),
        "Spare Reg": float(m.group(4)),
    }

# Sanity check: 25 Gardenia rows should be present
gardenia_keys = [k for k in ORDERED_28
                 if not (k.startswith("pann_") or k.startswith("ls_"))]
missing_gardenia = [k for k in gardenia_keys if k not in sota_pct]
if missing_gardenia:
    sys.stderr.write(f"WARN: SOTA top table missing rows: {missing_gardenia}\n")


# ── Step 3: Extended workloads — compute SOTA speedup from IPC ──────────────
# Source: "Extended Benchmarks (Pannotia + LonestarGPU)" table (lines ~160-170)
# Format: | `name` | Algo | Bench | Baseline | SOTA IPC | ... |
ext_re = re.compile(
    r"\|\s*`(pann_\w+|ls_\w+)`\s*\|[^|]*\|[^|]*\|\s*"
    r"(Snake|CAPS|Spare Reg)\s*\|\s*([\d\.]+)\s*\|"
)
ext_sota_ipc = {}  # name -> {scheme: ipc}
for m in ext_re.finditer(sota_text):
    name, scheme, ipc = m.group(1), m.group(2), float(m.group(3))
    ext_sota_ipc.setdefault(name, {})[scheme] = ipc

# Fold extended workloads into sota_pct using NP baseline IPC from effectiveness_data
for name in ("pann_mis_flickr", "pann_color_eco", "ls_mst_rmat12"):
    np_ipc = eff["workloads"][name]["baseline"]["ipc"]
    sota_pct[name] = {}
    for scheme in ("Snake", "CAPS", "Spare Reg"):
        sota_ipc = ext_sota_ipc.get(name, {}).get(scheme)
        if sota_ipc is None:
            sota_pct[name][scheme] = 0.0  # no data
        else:
            sota_pct[name][scheme] = (sota_ipc / np_ipc - 1.0) * 100.0


# ── Step 4: Build per-scheme arrays in canonical workload order ──────────────
def to_mult(pct: float) -> float:
    """Convert speedup percentage to multiplier (×). +56% → 1.56."""
    return 1.0 + pct / 100.0


snake_mult = np.array([to_mult(sota_pct[k]["Snake"])     for k in ORDERED_28])
caps_mult  = np.array([to_mult(sota_pct[k]["CAPS"])      for k in ORDERED_28])
spare_mult = np.array([to_mult(sota_pct[k]["Spare Reg"]) for k in ORDERED_28])
grasp_mult = np.array([to_mult(grasp_pct[k])             for k in ORDERED_28])


def gmean(arr: np.ndarray) -> float:
    """Geometric mean of an array of positive multipliers."""
    return float(np.exp(np.mean(np.log(arr))))


snake_gm = gmean(snake_mult)
caps_gm  = gmean(caps_mult)
spare_gm = gmean(spare_mult)
grasp_gm = gmean(grasp_mult)


# ── Step 5: Append GMEAN as last column ──────────────────────────────────────
snake_all = np.append(snake_mult, snake_gm)
caps_all  = np.append(caps_mult,  caps_gm)
spare_all = np.append(spare_mult, spare_gm)
grasp_all = np.append(grasp_mult, grasp_gm)

n_wkl = len(ORDERED_28)
n_total = n_wkl + 1  # + GMEAN
labels = [SHORT_NAME[k] for k in ORDERED_28] + ["GMEAN"]


# ── Step 6: Figure layout ───────────────────────────────────────────────────
# Insert a small visual gap before the GMEAN bar by shifting it +0.5.
GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w = 0.20
offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_w  # 4 bars centred on x

# Y-axis range: most data fits in [0.9, 1.7]; outliers clipped + annotated.
Y_LO, Y_HI = 0.85, 1.72

fig, ax = plt.subplots(
    figsize=figsize_full(aspect=0.42),
    constrained_layout=True,
)

# Scheme: (label, multipliers, color, hatch)
schemes = [
    ("Snake",     snake_all, CB10[2], HATCHES[1]),  # gray, //
    ("CAPS",      caps_all,  CB10[4], HATCHES[2]),  # light blue, \\
    ("Spare Reg", spare_all, CB10[3], HATCHES[3]),  # dark gray, xx
    ("GRASP",     grasp_all, CB10[0], HATCHES[0]),  # blue, solid
]


def height_from_baseline(vals: np.ndarray) -> np.ndarray:
    """Bar height drawn upward (or downward) from y=1.0 baseline.
    Clipped at Y_HI on the high side."""
    clipped = np.minimum(vals, Y_HI)
    return clipped - 1.0


bar_containers = {}
for i, (name, vals, color, hatch) in enumerate(schemes):
    heights = height_from_baseline(vals)
    bars = ax.bar(
        x + offsets[i], heights, bar_w,
        bottom=1.0,
        label=name, color=color, hatch=hatch,
        edgecolor="black", linewidth=0.4,
        zorder=3,
    )
    bar_containers[name] = (bars, vals, color)


# ── Annotate clipped outliers (>= Y_HI) with "↑X.XX×" ──────────────────────
for name, (bars, vals, color) in bar_containers.items():
    for j, bar in enumerate(bars):
        v = vals[j]
        if v < Y_HI:
            continue
        # Draw arrow + value just above the clip line
        cx = bar.get_x() + bar.get_width() / 2
        ax.annotate(
            f"{v:.2f}\u00d7",  # ×
            xy=(cx, Y_HI),
            xytext=(0, 1.5), textcoords="offset points",
            ha="center", va="bottom",
            fontsize=5.5, fontweight="bold", color=color,
            zorder=6,
        )
        # Small upward arrow head right above the bar tip
        ax.annotate(
            "",
            xy=(cx, Y_HI + 0.012), xytext=(cx, Y_HI - 0.005),
            arrowprops=dict(arrowstyle="->", color=color,
                            lw=0.6, shrinkA=0, shrinkB=0),
            zorder=5,
        )


# ── Baseline (1.0×) reference line ──────────────────────────────────────────
ax.axhline(1.0, color="black", linestyle="--", linewidth=0.6, zorder=2)


# ── Vertical separators between algorithm groups ────────────────────────────
sep_positions = group_separator_positions(ORDERED_28)
for sp in sep_positions:
    ax.axvline(x=sp, color="#999999", linestyle="--",
               linewidth=0.5, alpha=0.7, zorder=1)

# Thicker solid separator before GMEAN
gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0  # halfway in the visual gap
ax.axvline(x=gmean_sep_x, color="black", linestyle="-",
           linewidth=0.8, alpha=0.8, zorder=1)


# ── Algorithm group labels below x-tick labels ──────────────────────────────
cumulative = 0
for gname, gwkls in ALG_GROUPS:
    gsize = len(gwkls)
    centre = cumulative + (gsize - 1) / 2.0
    ax.annotate(
        gname,
        xy=(centre, 0), xycoords=("data", "axes fraction"),
        xytext=(0, -28), textcoords="offset points",
        ha="center", va="top",
        fontsize=7, fontweight="bold",
        annotation_clip=False,
    )
    cumulative += gsize
ax.annotate(
    "Avg",
    xy=(x[-1], 0), xycoords=("data", "axes fraction"),
    xytext=(0, -28), textcoords="offset points",
    ha="center", va="top",
    fontsize=7, fontweight="bold",
    annotation_clip=False,
)


# ── X-axis ──────────────────────────────────────────────────────────────────
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.0)
ax.set_xlim(-0.7, x[-1] + 0.7)


# ── Y-axis ──────────────────────────────────────────────────────────────────
ax.set_ylim(Y_LO, Y_HI + 0.05)
ax.set_ylabel("Normalized Speedup over No-PF (\u00d7)")
# Format y-ticks as 0.9× / 1.0× / 1.1× ...
yticks = [0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]
ax.set_yticks(yticks)
ax.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks])


# ── Legend with per-scheme geomean ──────────────────────────────────────────
legend_patches = [
    Patch(facecolor=CB10[2], edgecolor="black", hatch=HATCHES[1],
          linewidth=0.4, label=f"Snake ({snake_gm:.2f}\u00d7)"),
    Patch(facecolor=CB10[4], edgecolor="black", hatch=HATCHES[2],
          linewidth=0.4, label=f"CAPS ({caps_gm:.2f}\u00d7)"),
    Patch(facecolor=CB10[3], edgecolor="black", hatch=HATCHES[3],
          linewidth=0.4, label=f"Spare Reg ({spare_gm:.2f}\u00d7)"),
    Patch(facecolor=CB10[0], edgecolor="black", hatch=HATCHES[0],
          linewidth=0.4, label=f"GRASP ({grasp_gm:.2f}\u00d7)"),
]
ax.legend(
    handles=legend_patches, ncol=4, fontsize=6.5,
    loc="upper left", bbox_to_anchor=(0.0, 1.02), frameon=False,
    handlelength=1.4, handleheight=0.9,
    columnspacing=1.2, handletextpad=0.4,
)


# ── Save ────────────────────────────────────────────────────────────────────
out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r2_fig_speedup", out_dir)
plt.close(fig)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== GRASP Main Speedup (DMP-style normalized) ===")
print(f"Workloads: {n_wkl}  |  GMEAN per scheme:")
print(f"  Snake     {snake_gm:.3f}\u00d7")
print(f"  CAPS      {caps_gm:.3f}\u00d7")
print(f"  Spare Reg {spare_gm:.3f}\u00d7")
print(f"  GRASP     {grasp_gm:.3f}\u00d7")
print()

# Outlier list (any scheme above Y_HI)
print(f"Clipped bars (>{Y_HI:.2f}\u00d7) annotated above the bar:")
for name, (_, vals, _) in bar_containers.items():
    for j, v in enumerate(vals[:-1]):  # exclude GMEAN
        if v >= Y_HI:
            print(f"  {name:9s}  {ORDERED_28[j]:18s}  {v:.3f}\u00d7")

# Below-1.0 list
print(f"\nRegressions (<1.00\u00d7):")
for name, (_, vals, _) in bar_containers.items():
    for j, v in enumerate(vals[:-1]):
        if v < 1.0:
            print(f"  {name:9s}  {ORDERED_28[j]:18s}  {v:.3f}\u00d7")

print(f"\nSaved to {out_dir}/proto_r2_fig_speedup.{{pdf,svg}}")
