#!/usr/bin/env python3
"""Fig F: Dynamic Throttle Control — Timeline Diagram.

Shows how GRASP's dynamic throttle (mode=5) adapts over time:
- Top: MSHR Occupancy vs dynamic Effective Threshold + Cooldown shading
- Middle strip: DATA_PF activity (issued vs suppressed)
- Bottom: Window Accuracy driving threshold adaptation
"""
import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, save_fig, CB10
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

apply_style()

# ── Colors ──────────────────────────────────────────────────
C_MSHR      = CB10[0]       # #006BA4 blue — MSHR Occupancy
C_MSHR_NT   = CB10[2]       # #ABABAB gray — Without Throttle baseline
C_THRESHOLD = '#C0392B'     # red — Effective Threshold
C_COOLDOWN  = '#FADBD8'     # light red — Cooldown shading
C_ACTIVE    = '#D6EAF8'     # light blue — DATA_PF active region
C_ACCURACY  = '#5AA469'     # green — Window Accuracy
C_ACC_FILL  = '#D5F5E3'     # light green — accuracy fill
C_SUPPRESS  = '#E74C3C'     # red — suppressed marker
C_ISSUED    = '#2D8653'     # dark green — issued marker
C_INDEX     = CB10[0]       # blue — INDEX_PF band
C_PARAM     = '#7B68AE'     # purple — parameter annotations

# ── Synthetic Data ──────────────────────────────────────────
np.random.seed(42)
TOTAL_CYCLES = 25000
WINDOW_SIZE = 5000
dt = 50  # sample every 50 cycles
t = np.arange(0, TOTAL_CYCLES, dt)

# Window Accuracy: piecewise to show dynamic changes
# Starts ~55%, drops to ~20% around 5K-8K, recovers to ~65% at 12K,
# dips to ~25% at 17K-20K, then recovers to ~70%
accuracy_base = np.piecewise(t.astype(float),
    [t < 3000,
     (t >= 3000) & (t < 6000),
     (t >= 6000) & (t < 9000),
     (t >= 9000) & (t < 13000),
     (t >= 13000) & (t < 16000),
     (t >= 16000) & (t < 20000),
     t >= 20000],
    [55, lambda x: 55 - 35 * (x - 3000) / 3000,
     lambda x: 20 + 45 * (x - 6000) / 3000,
     65,
     lambda x: 65 - 40 * (x - 13000) / 3000,
     lambda x: 25 + 45 * (x - 16000) / 4000,
     70])
accuracy_noise = np.random.normal(0, 3, len(t))
accuracy = np.clip(accuracy_base + accuracy_noise, 5, 95)

# Smooth accuracy (simulating sliding window averaging)
from scipy.ndimage import uniform_filter1d
accuracy_smooth = uniform_filter1d(accuracy, size=20)

# Effective Threshold: mapped from accuracy via linear interpolation
ACC_LO, ACC_HI = 30, 60
THR_LO, THR_HI = 50, 90

def acc_to_threshold(acc):
    t_val = np.clip((acc - ACC_LO) / (ACC_HI - ACC_LO), 0, 1)
    return THR_LO + t_val * (THR_HI - THR_LO)

eff_threshold = acc_to_threshold(accuracy_smooth)

# MSHR Occupancy: fluctuating, with peaks that trigger cooldown
mshr_base = np.piecewise(t.astype(float),
    [t < 2000,
     (t >= 2000) & (t < 5000),
     (t >= 5000) & (t < 8000),
     (t >= 8000) & (t < 11000),
     (t >= 11000) & (t < 14000),
     (t >= 14000) & (t < 18000),
     (t >= 18000) & (t < 22000),
     t >= 22000],
    [35, lambda x: 35 + 40 * (x - 2000) / 3000,
     lambda x: 75 - 30 * (x - 5000) / 3000,
     40,
     lambda x: 40 + 35 * (x - 11000) / 3000,
     lambda x: 75 - 25 * (x - 14000) / 4000,
     lambda x: 45 + 25 * (x - 18000) / 4000,
     55])
mshr_noise = np.random.normal(0, 5, len(t))
mshr = np.clip(mshr_base + mshr_noise, 10, 95)
mshr_smooth = uniform_filter1d(mshr, size=10)

# "Without Throttle" baseline: higher, more peaks, more pollution
mshr_no_throttle = np.clip(mshr_smooth + 15 + np.random.normal(0, 3, len(t)), 10, 98)
mshr_no_throttle = uniform_filter1d(mshr_no_throttle, size=10)

# Cooldown state machine simulation
COOLDOWN_DURATION = 200  # cycles
cooldown_until = 0
in_cooldown = np.zeros(len(t), dtype=bool)
suppress_events = []
issue_events = []

for i, (cycle, occ, thr) in enumerate(zip(t, mshr_smooth, eff_threshold)):
    if cycle < cooldown_until:
        in_cooldown[i] = True
        if np.random.random() < 0.3:  # some DATA_PF attempted
            suppress_events.append(cycle)
    elif occ >= thr:
        in_cooldown[i] = True
        cooldown_until = cycle + COOLDOWN_DURATION
        suppress_events.append(cycle)
    else:
        if np.random.random() < 0.15:  # DATA_PF issued normally
            issue_events.append(cycle)

# Subsample events for plotting (avoid clutter)
suppress_events = suppress_events[::2][:40]
issue_events = issue_events[::2][:50]

# ── Figure ──────────────────────────────────────────────────
fig = plt.figure(figsize=figsize_full(aspect=0.52), constrained_layout=False)

# GridSpec: top chart (55%), middle strip (8%), bottom chart (30%), legend gap (7%)
gs = fig.add_gridspec(3, 1, height_ratios=[55, 8, 30],
                      hspace=0.08, left=0.08, right=0.82,
                      top=0.95, bottom=0.08)

ax_mshr = fig.add_subplot(gs[0])
ax_strip = fig.add_subplot(gs[1], sharex=ax_mshr)
ax_acc = fig.add_subplot(gs[2], sharex=ax_mshr)

# ── Top: MSHR Occupancy ────────────────────────────────────
# Background: light blue for active, light red for cooldown
for i in range(len(t) - 1):
    color = C_COOLDOWN if in_cooldown[i] else C_ACTIVE
    ax_mshr.axvspan(t[i], t[i + 1], alpha=0.4, color=color, linewidth=0)

# Reference lines
ax_mshr.axhline(THR_LO, color=C_PARAM, linestyle=':', linewidth=0.8, alpha=0.6)
ax_mshr.axhline(THR_HI, color=C_PARAM, linestyle=':', linewidth=0.8, alpha=0.6)

# Without Throttle baseline
ax_mshr.plot(t, mshr_no_throttle, color=C_MSHR_NT, linewidth=1.0,
             linestyle='--', alpha=0.7, label='Without Throttle')

# MSHR Occupancy
ax_mshr.plot(t, mshr_smooth, color=C_MSHR, linewidth=1.5, label='MSHR Occupancy')

# Effective Threshold
ax_mshr.plot(t, eff_threshold, color=C_THRESHOLD, linewidth=1.2,
             linestyle='--', label='Effective Threshold')

# Parameter labels on right side
ax_mshr.text(TOTAL_CYCLES * 1.01, THR_HI, f'Threshold\nHigh ({THR_HI}%)',
             fontsize=6.5, color=C_PARAM, va='center', ha='left')
ax_mshr.text(TOTAL_CYCLES * 1.01, THR_LO, f'Threshold\nLow ({THR_LO}%)',
             fontsize=6.5, color=C_PARAM, va='center', ha='left')

# Cooldown Duration annotation (just once, on first cooldown)
cooldown_starts = []
prev_cd = False
for i in range(len(t)):
    if in_cooldown[i] and not prev_cd:
        cooldown_starts.append(t[i])
    prev_cd = in_cooldown[i]

if len(cooldown_starts) >= 2:
    cs = cooldown_starts[1]  # second cooldown for annotation
    ax_mshr.annotate('', xy=(cs + COOLDOWN_DURATION, 92), xytext=(cs, 92),
                     arrowprops=dict(arrowstyle='<->', color='#333333', lw=1.0))
    ax_mshr.text(cs + COOLDOWN_DURATION / 2, 95, 'Cooldown\nDuration',
                 fontsize=6, ha='center', va='bottom', color='#333333',
                 fontweight='bold')

# INDEX_PF: single thin line at the top with one label
ax_mshr.axhline(97, color=C_INDEX, linewidth=2.5, alpha=0.5, solid_capstyle='butt')
ax_mshr.text(TOTAL_CYCLES * 0.5, 98.5, 'INDEX_PF: Never Throttled',
             fontsize=6.5, color=C_INDEX, ha='center', va='bottom',
             fontstyle='italic')

ax_mshr.set_ylabel('MSHR Occupancy (%)', fontsize=8)
ax_mshr.set_ylim(0, 105)
ax_mshr.set_xlim(0, TOTAL_CYCLES)
ax_mshr.tick_params(labelbottom=False)

# ── Middle: DATA_PF Activity Strip ─────────────────────────
ax_strip.set_ylim(0, 1)
ax_strip.set_yticks([])
ax_strip.set_ylabel('DATA_PF', fontsize=7, rotation=0, labelpad=25, va='center')

# Background same as top chart
for i in range(len(t) - 1):
    color = C_COOLDOWN if in_cooldown[i] else C_ACTIVE
    ax_strip.axvspan(t[i], t[i + 1], alpha=0.3, color=color, linewidth=0)

# Issued ticks (green)
for ev in issue_events:
    ax_strip.plot(ev, 0.5, marker='|', color=C_ISSUED, markersize=6, markeredgewidth=1.2)

# Suppressed ticks (red X)
for ev in suppress_events:
    ax_strip.plot(ev, 0.5, marker='x', color=C_SUPPRESS, markersize=4, markeredgewidth=1.2)

ax_strip.tick_params(labelbottom=False)
# Border
for spine in ax_strip.spines.values():
    spine.set_linewidth(0.5)

# ── Bottom: Window Accuracy ────────────────────────────────
ax_acc.fill_between(t, 0, accuracy_smooth, color=C_ACC_FILL, alpha=0.6)
ax_acc.plot(t, accuracy_smooth, color=C_ACCURACY, linewidth=1.2)

# Reference lines
ax_acc.axhline(ACC_LO, color=C_PARAM, linestyle=':', linewidth=0.8, alpha=0.6)
ax_acc.axhline(ACC_HI, color=C_PARAM, linestyle=':', linewidth=0.8, alpha=0.6)

# Labels on right
ax_acc.text(TOTAL_CYCLES * 1.01, ACC_HI, f'Accuracy\nHigh ({ACC_HI}%)',
            fontsize=6.5, color=C_PARAM, va='center', ha='left')
ax_acc.text(TOTAL_CYCLES * 1.01, ACC_LO, f'Accuracy\nLow ({ACC_LO}%)',
            fontsize=6.5, color=C_PARAM, va='center', ha='left')

ax_acc.set_ylabel('Window\nAccuracy (%)', fontsize=8)
ax_acc.set_xlabel('Cycles', fontsize=8)
ax_acc.set_ylim(0, 100)
ax_acc.set_xlim(0, TOTAL_CYCLES)

# X-axis ticks
ax_acc.set_xticks([0, 5000, 10000, 15000, 20000, 25000])
ax_acc.set_xticklabels(['0', '5K', '10K', '15K', '20K', '25K'])

# ── Causal Arrows (accuracy ↔ threshold) ───────────────────
# Find key moments where accuracy drops → threshold drops
# Arrow 1: around 4K-5K where accuracy drops sharply
fig.canvas.draw()  # needed for coordinate transforms
from matplotlib.patches import FancyArrowPatch

# Use fig.transFigure for cross-axes arrows
# Arrow: accuracy drop at ~5K → threshold drop at ~5K
arrow1_x = 5000
# Get normalized positions
def data_to_fig(ax, x, y):
    """Convert data coords to figure coords."""
    display = ax.transData.transform((x, y))
    return fig.transFigure.inverted().transform(display)

# ── Mapping Box (right side) ───────────────────────────────
box_text = (
    "Feedback Mapping\n"
    "─────────────────\n"
    "Low Accuracy\n"
    "  → Low Threshold\n"
    "     (Tight Throttle)\n"
    "\n"
    "High Accuracy\n"
    "  → High Threshold\n"
    "     (Loose Throttle)"
)
fig.text(0.86, 0.55, box_text, fontsize=6.5, va='center', ha='left',
         family='monospace',
         bbox=dict(boxstyle='round,pad=0.5', facecolor='#F8F9FA',
                   edgecolor=C_PARAM, linewidth=1.0, alpha=0.9))

# ── Legend ──────────────────────────────────────────────────
legend_elements = [
    Line2D([0], [0], color=C_MSHR, linewidth=1.5, label='MSHR Occupancy'),
    Line2D([0], [0], color=C_MSHR_NT, linewidth=1.0, linestyle='--', label='Without Throttle'),
    Line2D([0], [0], color=C_THRESHOLD, linewidth=1.2, linestyle='--', label='Effective Threshold'),
    Line2D([0], [0], color=C_ACCURACY, linewidth=1.2, label='Window Accuracy'),
    mpatches.Patch(facecolor=C_COOLDOWN, alpha=0.4, label='Cooldown (Suppress)'),
    mpatches.Patch(facecolor=C_ACTIVE, alpha=0.4, label='Active (Allow)'),
    Line2D([0], [0], marker='|', color=C_ISSUED, linestyle='None',
           markersize=6, markeredgewidth=1.2, label='DATA_PF Issued'),
    Line2D([0], [0], marker='x', color=C_SUPPRESS, linestyle='None',
           markersize=5, markeredgewidth=1.2, label='DATA_PF Suppressed'),
]
fig.legend(handles=legend_elements, loc='lower center', ncol=4,
           fontsize=6.5, frameon=True, fancybox=False,
           edgecolor='#CCCCCC', bbox_to_anchor=(0.45, -0.02))

# ── Save ────────────────────────────────────────────────────
out_dir = Path(__file__).parent
save_fig(fig, 'fig_f_throttle_v1', out_dir)
# Also save PNG for quick preview
fig.savefig(out_dir / 'fig_f_throttle_v1.png', dpi=200, bbox_inches='tight',
            facecolor='white')
plt.close(fig)
print(f"Saved to {out_dir}/fig_f_throttle_v1.{{pdf,svg,png}}")
