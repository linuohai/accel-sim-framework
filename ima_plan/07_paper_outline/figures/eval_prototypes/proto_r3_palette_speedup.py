#!/usr/bin/env python3
"""
Proto R3 Figure: Main Speedup — palette comparison sweep.

Re-renders the §5.2 main speedup grouped bar chart in 6 different color
palettes so the user can pick the best one. Layout, data and bar placement
are reused from ``proto_r2_fig_speedup.py``; only colors, hatching density
and the y-axis range are changed.

Key changes vs. R2:
  * Tight y-axis: ylim=(0.85, 1.35) — most data fills the panel.
  * Bars above 1.35x are clipped at the ceiling and annotated with an
    upward arrow + numeric value (e.g. CC-fl GRASP 2.22x).
  * Bars below 1.0 (regressions) draw downward from the dashed baseline.
  * Numeric in-bar annotations on non-clipped bars are removed.
  * HATCHES_DENSE used (not HATCHES) for visibility at small bar widths.
  * Loops over PALETTES (current + 5 alternatives avoiding blue/orange).

Output: ``proto_r3_palette_<name>_speedup.{pdf,svg}`` for each palette.
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
    apply_style, figsize_full, save_fig, HATCHES_DENSE, PALETTES,
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
grasp_pct = {k: eff["workloads"][k]["derived"]["speedup_pct"] for k in ORDERED_28}


# ── Step 2: Parse SOTA top table (25 Gardenia rows) ──────────────────────────
sota_text = SOTA_MD.read_text()
row_re = re.compile(
    r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
    r"\s*([+-]?\d+\.\d+)%\s*\|"
)
sota_pct = {}
for m in row_re.finditer(sota_text):
    sota_pct[m.group(1)] = {
        "Snake":     float(m.group(2)),
        "CAPS":      float(m.group(3)),
        "Spare Reg": float(m.group(4)),
    }


# ── Step 3: Extended workloads — compute SOTA speedup from IPC ──────────────
ext_re = re.compile(
    r"\|\s*`(pann_\w+|ls_\w+)`\s*\|[^|]*\|[^|]*\|\s*"
    r"(Snake|CAPS|Spare Reg)\s*\|\s*([\d\.]+)\s*\|"
)
ext_sota_ipc = {}
for m in ext_re.finditer(sota_text):
    name, scheme, ipc = m.group(1), m.group(2), float(m.group(3))
    ext_sota_ipc.setdefault(name, {})[scheme] = ipc

for name in ("pann_mis_flickr", "pann_color_eco", "ls_mst_rmat12"):
    np_ipc = eff["workloads"][name]["baseline"]["ipc"]
    sota_pct[name] = {}
    for scheme in ("Snake", "CAPS", "Spare Reg"):
        sota_ipc = ext_sota_ipc.get(name, {}).get(scheme)
        sota_pct[name][scheme] = (
            0.0 if sota_ipc is None else (sota_ipc / np_ipc - 1.0) * 100.0
        )


# ── Step 4: Build per-scheme arrays in canonical order ───────────────────────
def to_mult(pct: float) -> float:
    return 1.0 + pct / 100.0


snake_mult = np.array([to_mult(sota_pct[k]["Snake"])     for k in ORDERED_28])
caps_mult  = np.array([to_mult(sota_pct[k]["CAPS"])      for k in ORDERED_28])
spare_mult = np.array([to_mult(sota_pct[k]["Spare Reg"]) for k in ORDERED_28])
grasp_mult = np.array([to_mult(grasp_pct[k])             for k in ORDERED_28])


def gmean(arr: np.ndarray) -> float:
    return float(np.exp(np.mean(np.log(arr))))


snake_gm = gmean(snake_mult)
caps_gm  = gmean(caps_mult)
spare_gm = gmean(spare_mult)
grasp_gm = gmean(grasp_mult)

snake_all = np.append(snake_mult, snake_gm)
caps_all  = np.append(caps_mult,  caps_gm)
spare_all = np.append(spare_mult, spare_gm)
grasp_all = np.append(grasp_mult, grasp_gm)

n_wkl   = len(ORDERED_28)
n_total = n_wkl + 1
labels  = [SHORT_NAME[k] for k in ORDERED_28] + ["GMEAN"]


# ── Layout constants (shared across all palettes) ────────────────────────────
GMEAN_GAP = 0.6
x = np.arange(n_total, dtype=float)
x[-1] += GMEAN_GAP

bar_w   = 0.20
offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_w  # 4 bars centred on x

# Tight y-axis: ~80% of bars fit; outliers get clipped + annotated.
Y_LO, Y_HI = 0.85, 1.35


def height_from_baseline(vals: np.ndarray) -> np.ndarray:
    """Bar drawn from y=1.0 baseline, clipped on the high side at Y_HI."""
    clipped = np.minimum(vals, Y_HI)
    return clipped - 1.0


def render_palette(palette_name: str, colors: list) -> Path:
    """Render the speedup figure with a given palette and save to disk."""
    # Map palette indices to schemes:
    #   colors[0] -> GRASP (our work, prominent)
    #   colors[1] -> Snake
    #   colors[2] -> CAPS
    #   colors[3] -> Spare Register
    grasp_color = colors[0]
    snake_color = colors[1]
    caps_color  = colors[2]
    spare_color = colors[3]

    # Schemes in DRAW order (Snake, CAPS, Spare, GRASP) — left-to-right
    # within each workload group, so GRASP is the rightmost bar.
    schemes = [
        ("Snake",     snake_all, snake_color, HATCHES_DENSE[1]),
        ("CAPS",      caps_all,  caps_color,  HATCHES_DENSE[2]),
        ("Spare Reg", spare_all, spare_color, HATCHES_DENSE[3]),
        ("GRASP",     grasp_all, grasp_color, HATCHES_DENSE[0]),
    ]

    fig, ax = plt.subplots(
        figsize=figsize_full(aspect=0.42),
        constrained_layout=True,
    )

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

    # Annotate clipped outliers (>= Y_HI) with arrow + value
    for name, (bars, vals, color) in bar_containers.items():
        for j, bar in enumerate(bars):
            v = vals[j]
            if v < Y_HI:
                continue
            cx = bar.get_x() + bar.get_width() / 2
            ax.annotate(
                f"\u2191{v:.2f}\u00d7",  # ↑X.XX×
                xy=(cx, Y_HI),
                xytext=(0, 1.5), textcoords="offset points",
                ha="center", va="bottom",
                fontsize=5.5, fontweight="bold", color=color,
                zorder=6,
                annotation_clip=False,
            )

    # Baseline (1.0×) reference line
    ax.axhline(1.0, color="black", linestyle="--", linewidth=0.6, zorder=2)

    # Vertical separators between algorithm groups
    sep_positions = group_separator_positions(ORDERED_28)
    for sp in sep_positions:
        ax.axvline(x=sp, color="#999999", linestyle="--",
                   linewidth=0.5, alpha=0.7, zorder=1)

    # Thicker solid separator before GMEAN
    gmean_sep_x = (n_wkl - 1) + (1 + GMEAN_GAP) / 2.0
    ax.axvline(x=gmean_sep_x, color="black", linestyle="-",
               linewidth=0.8, alpha=0.8, zorder=1)

    # Algorithm group labels below x-tick labels
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

    # X-axis
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=6.0)
    ax.set_xlim(-0.7, x[-1] + 0.7)

    # Y-axis (tight)
    ax.set_ylim(Y_LO, Y_HI)
    ax.set_ylabel("Normalized Speedup over No-PF (\u00d7)")
    yticks = [0.9, 1.0, 1.1, 1.2, 1.3]
    ax.set_yticks(yticks)
    ax.set_yticklabels([f"{t:.1f}\u00d7" for t in yticks])

    # Legend with per-scheme geomean (4 columns, top of plot)
    legend_patches = [
        Patch(facecolor=snake_color, edgecolor="black", hatch=HATCHES_DENSE[1],
              linewidth=0.4, label=f"Snake ({snake_gm:.2f}\u00d7)"),
        Patch(facecolor=caps_color, edgecolor="black", hatch=HATCHES_DENSE[2],
              linewidth=0.4, label=f"CAPS ({caps_gm:.2f}\u00d7)"),
        Patch(facecolor=spare_color, edgecolor="black", hatch=HATCHES_DENSE[3],
              linewidth=0.4, label=f"Spare Reg ({spare_gm:.2f}\u00d7)"),
        Patch(facecolor=grasp_color, edgecolor="black", hatch=HATCHES_DENSE[0],
              linewidth=0.4, label=f"GRASP ({grasp_gm:.2f}\u00d7)"),
    ]
    ax.legend(
        handles=legend_patches, ncol=4, fontsize=6.5,
        loc="upper left", bbox_to_anchor=(0.0, 1.02), frameon=False,
        handlelength=1.4, handleheight=0.9,
        columnspacing=1.2, handletextpad=0.4,
    )

    # Save
    out_dir = Path(__file__).resolve().parent
    stem = f"proto_r3_palette_{palette_name}_speedup"
    save_fig(fig, stem, out_dir)
    plt.close(fig)
    return out_dir / f"{stem}.pdf"


# ── Main: loop over palettes ────────────────────────────────────────────────
PALETTE_ORDER = [
    "current",        # CB10 blue/orange — reference
    "jewel",
    "tol_bright",
    "earth",
    "mono_contrast",
    "okabe_ito",
]

generated = []
for pname in PALETTE_ORDER:
    if pname not in PALETTES:
        sys.stderr.write(f"WARN: palette '{pname}' not in PALETTES, skipping\n")
        continue
    pdf_path = render_palette(pname, PALETTES[pname])
    generated.append(pdf_path)


# ── Console summary ─────────────────────────────────────────────────────────
print("=== GRASP Main Speedup — Palette Sweep ===")
print(f"Workloads: {n_wkl}  |  GMEAN per scheme:")
print(f"  Snake     {snake_gm:.3f}\u00d7")
print(f"  CAPS      {caps_gm:.3f}\u00d7")
print(f"  Spare Reg {spare_gm:.3f}\u00d7")
print(f"  GRASP     {grasp_gm:.3f}\u00d7")
print()
print(f"Y-axis: [{Y_LO}, {Y_HI}]  (tight; bars > {Y_HI} are clipped + annotated)")

# List clipped bars (>= Y_HI)
print(f"\nClipped bars (\u2265 {Y_HI:.2f}\u00d7) annotated above the bar:")
for name, vals_arr in [
    ("Snake", snake_all), ("CAPS", caps_all),
    ("Spare Reg", spare_all), ("GRASP", grasp_all),
]:
    for j, v in enumerate(vals_arr[:-1]):  # exclude GMEAN
        if v >= Y_HI:
            print(f"  {name:9s}  {SHORT_NAME[ORDERED_28[j]]:9s}  "
                  f"({ORDERED_28[j]:18s})  {v:.3f}\u00d7")

# List regressions (< 1.0)
print(f"\nRegressions (< 1.00\u00d7) — drawn below baseline:")
for name, vals_arr in [
    ("Snake", snake_all), ("CAPS", caps_all),
    ("Spare Reg", spare_all), ("GRASP", grasp_all),
]:
    for j, v in enumerate(vals_arr[:-1]):
        if v < 1.0:
            print(f"  {name:9s}  {SHORT_NAME[ORDERED_28[j]]:9s}  "
                  f"({ORDERED_28[j]:18s})  {v:.3f}\u00d7")

print(f"\nGenerated {len(generated)} palette variants:")
for p in generated:
    print(f"  {p}")
