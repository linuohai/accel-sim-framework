#!/usr/bin/env python3
"""
Hatching alternative preview for proto_r4_52_A (Round 2).

Borrows from the hatching styles of three reference papers:
  - RICH (MICRO'25)           — color-dominated, minimal hatching
  - DMP (IEEE'24)             — color-only, no hatching
  - Magellan (ISCA'25) ⭐     — B&W with traditional hatching; our domain peer

Magellan's Fig 15 (4 schemes: SW Prefetch / Intel OneAPI / APT-GET / Magellan)
uses: empty (white) / dots / diagonal / solid black. "Our work" is solid black.
Fig 18 (7 schemes) adds vertical lines and grayscale fills.

This preview renders 5 hatching SETS so the user can pick one that best fits
the MICRO aesthetic:

  B  Current (shapes: O / * / + / .)    — visually distinct, but not MICRO-y
  M1 Magellan-literal                    — GRASP solid, rest /.//dots/\\
  M2 Magellan-classic                    — 3 line-directions + GRASP dots
  M3 Magellan-hybrid                     — crosshatch for CAPS, GRASP dots
  M4 Magellan-inverse                    — GRASP solid, SOTA carry all hatches

Output: proto_r4_52_A_hatch_preview.{pdf,svg}
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig, PALETTE_TOL_BRIGHT  # noqa: E402

apply_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402


# ── Hatching option sets ────────────────────────────────────────────────────
# Each option is (Snake, CAPS, Spare Reg, GRASP) hatches.
OPTIONS = {
    "B   CURRENT — shapes-only "
    "(Snake=O / CAPS=* / SR=+ / GRASP=·)":
        ("OOOOO", "*****", "+++++", "....."),

    "M1  Magellan-literal — GRASP solid "
    "(Snake=/ / CAPS=· / SR=\\\\ / GRASP=solid)":
        ("/////", ".....", "\\\\\\\\\\", ""),

    "M2  Magellan-classic — 3 line dirs + GRASP dots "
    "(Snake=/ / CAPS=| / SR=\\\\ / GRASP=·)":
        ("/////", "|||||", "\\\\\\\\\\", "....."),

    "M3  Magellan-hybrid — crosshatch for CAPS "
    "(Snake=/ / CAPS=x / SR=| / GRASP=·)":
        ("/////", "xxxxx", "|||||", "....."),

    "M4  Magellan-inverse — SOTA carries all hatches "
    "(Snake=/ / CAPS=x / SR=\\\\ / GRASP=solid)":
        ("/////", "xxxxx", "\\\\\\\\\\", ""),
}


SCHEMES = ["Snake", "CAPS", "Spare Reg", "GRASP"]
COLORS = [
    PALETTE_TOL_BRIGHT[1],  # Snake   — red
    PALETTE_TOL_BRIGHT[2],  # CAPS    — purple
    PALETTE_TOL_BRIGHT[3],  # SR      — yellow
    PALETTE_TOL_BRIGHT[0],  # GRASP   — green
]

# Fake speedup data for 5 representative workloads (per scheme)
fake_wkls = ["BFS-wg", "SSSP-cp", "CC-fl", "SpM-rd", "VC-wg"]
data = {
    "Snake":     [1.04, 1.03, 1.01, 1.00, 1.05],
    "CAPS":      [1.02, 1.00, 0.98, 0.99, 1.01],
    "Spare Reg": [1.06, 1.07, 1.03, 1.01, 1.14],
    "GRASP":     [1.20, 1.18, 1.25, 1.15, 1.08],
}


# ── Plot ────────────────────────────────────────────────────────────────────
n_opts = len(OPTIONS)
fig, axes = plt.subplots(
    nrows=n_opts, ncols=1,
    figsize=(7.0, 1.55 * n_opts + 0.4),
    constrained_layout=True,
)

bar_w = 0.18
offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_w
x = np.arange(len(fake_wkls), dtype=float)
Y_LO, Y_HI = 0.80, 1.30


def bar_heights(vals):
    clipped = np.minimum(vals, Y_HI)
    return clipped - Y_LO


for ax, (title, hatches) in zip(axes, OPTIONS.items()):
    ax.set_title(title, fontsize=8, loc="left", pad=2)

    for i, (scheme, color, hatch) in enumerate(
            zip(SCHEMES, COLORS, hatches)):
        vals = np.array(data[scheme])
        ax.bar(
            x + offsets[i], bar_heights(vals), bar_w,
            bottom=Y_LO,
            label=scheme, color=color, hatch=hatch,
            edgecolor="black", linewidth=0.4,
            zorder=3,
        )

    ax.set_ylim(Y_LO, Y_HI + 0.02)
    ax.set_yticks([0.8, 0.9, 1.0, 1.1, 1.2, 1.3])
    ax.set_yticklabels(
        [f"{t:.1f}\u00d7" for t in [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]],
        fontsize=6.5,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(fake_wkls, fontsize=7)
    ax.set_xlim(-0.6, len(fake_wkls) - 0.4)
    ax.grid(True, axis="y", linestyle="--", linewidth=0.3,
            alpha=0.5, zorder=0)

    # Per-row legend placed to the right of the axis
    legend_patches = [
        Patch(facecolor=c, edgecolor="black",
              hatch=h, linewidth=0.4, label=s)
        for s, c, h in zip(SCHEMES, COLORS, hatches)
    ]
    ax.legend(
        handles=legend_patches, ncol=1, fontsize=6.5,
        loc="center left", bbox_to_anchor=(1.005, 0.5),
        frameon=False, handlelength=1.4, handleheight=1.1,
        labelspacing=0.5, handletextpad=0.4,
    )


out_dir = Path(__file__).resolve().parent
save_fig(fig, "proto_r4_52_A_hatch_preview", out_dir)
plt.close(fig)

print("Hatching comparison rendered.")
print(f"Options:")
for title, hatches in OPTIONS.items():
    print(f"  {title}")
print(f"\nSaved to {out_dir}/proto_r4_52_A_hatch_preview.{{pdf,svg}}")
