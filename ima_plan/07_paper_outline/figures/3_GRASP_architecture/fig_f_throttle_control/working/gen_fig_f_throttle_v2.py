#!/usr/bin/env python3
"""Fig F V2: Dynamic Throttle Control — Timeline Diagram.

Gemini-optimized layout (layout_v2.txt + style_spec_v2.txt).
Two vertically stacked charts: MSHR Occupancy + Window Accuracy.
Key message: sliding window accuracy drives adaptive MSHR threshold.
"""
import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch
from matplotlib.ticker import FuncFormatter
from scipy.ndimage import uniform_filter1d

apply_style()

# ── Synthetic Data ──────────────────────────────────────────
np.random.seed(42)
TOTAL = 25000
dt = 50
t = np.arange(0, TOTAL, dt)

# Window Accuracy: shaped to show clear drops → threshold adaptation
acc_base = np.piecewise(t.astype(float),
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
accuracy = np.clip(acc_base + np.random.normal(0, 3, len(t)), 5, 95)
accuracy = uniform_filter1d(accuracy, size=20)

# Effective Threshold: linear map from accuracy
ACC_LO, ACC_HI = 30, 60
THR_LO, THR_HI = 50, 90
thr_t = np.clip((accuracy - ACC_LO) / (ACC_HI - ACC_LO), 0, 1)
eff_threshold = THR_LO + thr_t * (THR_HI - THR_LO)

# MSHR Occupancy
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
mshr = np.clip(mshr_base + np.random.normal(0, 5, len(t)), 10, 95)
mshr = uniform_filter1d(mshr, size=10)

# Without Throttle baseline: higher, more volatile
mshr_nt = np.clip(mshr + 15 + np.random.normal(0, 3, len(t)), 10, 98)
mshr_nt = uniform_filter1d(mshr_nt, size=10)

# Cooldown simulation
COOLDOWN_DUR = 200
cooldown_until = 0
in_cooldown = np.zeros(len(t), dtype=bool)
for i, (cyc, occ, thr) in enumerate(zip(t, mshr, eff_threshold)):
    if cyc < cooldown_until:
        in_cooldown[i] = True
    elif occ >= thr:
        in_cooldown[i] = True
        cooldown_until = cyc + COOLDOWN_DUR

# Extract cooldown intervals
cooldown_intervals = []
start = None
for i in range(len(t)):
    if in_cooldown[i] and start is None:
        start = t[i]
    elif not in_cooldown[i] and start is not None:
        cooldown_intervals.append((start, t[i]))
        start = None
if start is not None:
    cooldown_intervals.append((start, t[-1]))

# ── Figure (Gemini spec) ───────────────────────────────────
fig = plt.figure(figsize=(7.0, 3.5))
gs = fig.add_gridspec(2, 1, height_ratios=[2.2, 1.0], hspace=0.1)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1], sharex=ax1)
plt.subplots_adjust(left=0.07, right=0.82, top=0.92, bottom=0.18)

# ── Top Chart: MSHR Occupancy ──────────────────────────────
# Reference lines (below data)
ax1.axhline(THR_HI, color='#7f7f7f', ls=':', lw=1.0, alpha=0.8, zorder=1)
ax1.axhline(THR_LO, color='#7f7f7f', ls=':', lw=1.0, alpha=0.8, zorder=1)

# Cooldown shading (both axes)
for s, e in cooldown_intervals:
    ax1.axvspan(s, e, color='#ff9896', alpha=0.25, lw=0, zorder=1)
    ax2.axvspan(s, e, color='#ff9896', alpha=0.25, lw=0, zorder=1)

# Baseline (no throttle)
ax1.plot(t, mshr_nt, color='#7f7f7f', lw=1.2, ls=':', alpha=0.7, zorder=2)

# MSHR Occupancy
ax1.plot(t, mshr, color='#1f77b4', lw=1.5, ls='-', zorder=3)

# Effective Threshold
ax1.plot(t, eff_threshold, color='#d62728', lw=2.0, ls='--', zorder=4)

# Right-side labels: direct line labeling
# Direct line labels — avoid overlap by checking distance
mshr_end = mshr[-1]
thr_end = eff_threshold[-1]
if abs(mshr_end - thr_end) < 12:
    thr_end = mshr_end + 14  # push apart
ax1.text(1.02, mshr_end, 'MSHR\nOccupancy', transform=ax1.get_yaxis_transform(),
         color='#1f77b4', fontsize=7, fontweight='bold', va='center')
ax1.text(1.02, thr_end, 'Effective\nThreshold', transform=ax1.get_yaxis_transform(),
         color='#d62728', fontsize=7, fontweight='bold', va='center')
ax1.text(1.02, THR_HI, 'Threshold\nHigh (90%)', transform=ax1.get_yaxis_transform(),
         fontsize=6.5, va='center', color='#555555')
ax1.text(1.02, THR_LO, 'Threshold\nLow (50%)', transform=ax1.get_yaxis_transform(),
         fontsize=6.5, va='center', color='#555555')

# Annotations: DATA_PF Suppressed (in widest cooldown)
widest = max(cooldown_intervals, key=lambda iv: iv[1] - iv[0])
cx = (widest[0] + widest[1]) / 2
ax1.text(cx, 72, 'DATA_PF\nSuppressed', fontsize=7.5, color='#c0392b',
         ha='center', va='center', fontweight='bold',
         bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=1.5))

# INDEX_PF label (once, in a non-cooldown region)
# Find first non-cooldown region with low MSHR
for i in range(len(t)):
    if not in_cooldown[i] and mshr[i] < 40 and t[i] > 2000:
        ax1.text(t[i], 15, 'INDEX_PF Active', fontsize=7.5, color='#2ca02c',
                 ha='center', va='center', fontweight='bold',
                 bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=1.5))
        break

# Cooldown Duration bracket (on second cooldown if exists)
if len(cooldown_intervals) >= 2:
    cs, ce = cooldown_intervals[1]
    ax1.annotate('', xy=(ce, 96), xytext=(cs, 96),
                 arrowprops=dict(arrowstyle='|-|', color='black', lw=1.0))
    ax1.text((cs + ce) / 2, 99, 'Cooldown\nDuration', fontsize=6.5,
             ha='center', va='bottom', color='#333333')

ax1.set_ylim(0, 105)
ax1.set_xlim(0, TOTAL)
ax1.set_ylabel('MSHR Occupancy (%)', fontsize=9, labelpad=4)
plt.setp(ax1.get_xticklabels(), visible=False)
ax1.tick_params(axis='x', length=0)

# ── Bottom Chart: Window Accuracy ──────────────────────────
ax2.axhline(ACC_HI, color='#7f7f7f', ls=':', lw=1.0, alpha=0.8, zorder=1)
ax2.axhline(ACC_LO, color='#7f7f7f', ls=':', lw=1.0, alpha=0.8, zorder=1)

ax2.fill_between(t, 0, accuracy, color='#2ca02c', alpha=0.2, zorder=2)
ax2.plot(t, accuracy, color='#2ca02c', lw=1.5, zorder=3)

ax2.text(1.02, ACC_HI, 'Accuracy\nHigh (60%)', transform=ax2.get_yaxis_transform(),
         fontsize=6.5, va='center', color='#555555')
ax2.text(1.02, ACC_LO, 'Accuracy\nLow (30%)', transform=ax2.get_yaxis_transform(),
         fontsize=6.5, va='center', color='#555555')

ax2.set_ylim(0, 100)
ax2.set_ylabel('Window\nAccuracy (%)', fontsize=9, labelpad=4)
ax2.set_xlabel('Execution Timeline (Cycles)', fontsize=9, labelpad=4)
ax2.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f'{int(x/1000)}K' if x > 0 else '0'))

# ── Causal Arrow: accuracy drop → threshold drop ───────────
# Find the sharpest accuracy drop point (around 4K-6K)
drop_idx = np.argmin(np.diff(accuracy[:200])) + 1  # first 10K cycles
drop_x = t[drop_idx + 50]  # offset a bit for visibility
# Use ConnectionPatch to cross axes
con = ConnectionPatch(
    xyA=(drop_x, eff_threshold[drop_idx + 50]), coordsA="data", axesA=ax1,
    xyB=(drop_x, accuracy[drop_idx + 50]), coordsB="data", axesB=ax2,
    arrowstyle="<-", color="black", alpha=0.5, linestyle="--", lw=1.0)
ax1.add_artist(con)

# Second causal arrow around 14K-16K
drop_idx2 = 260 + np.argmin(np.diff(accuracy[260:360]))
drop_x2 = t[drop_idx2 + 1]
con2 = ConnectionPatch(
    xyA=(drop_x2, eff_threshold[drop_idx2 + 1]), coordsA="data", axesA=ax1,
    xyB=(drop_x2, accuracy[drop_idx2 + 1]), coordsB="data", axesB=ax2,
    arrowstyle="<-", color="black", alpha=0.5, linestyle="--", lw=1.0)
ax1.add_artist(con2)

# ── Mapping Box (right margin) ─────────────────────────────
fig.text(0.835, 0.48,
         "Feedback Mapping\n"
         "Low Acc  \u2192  Tight Throttle\n"
         "High Acc \u2192  Loose Throttle",
         fontsize=7.5, va='center', ha='left', family='sans-serif',
         linespacing=1.6,
         bbox=dict(facecolor='#F8F9FA', edgecolor='#999999',
                   boxstyle='round,pad=0.5', lw=0.8))

# ── Legend (simplified per Gemini) ─────────────────────────
baseline_h = Line2D([], [], color='#7f7f7f', ls=':', lw=1.2, label='Without Throttle')
cooldown_h = mpatches.Patch(color='#ff9896', alpha=0.4, label='Cooldown (Suppress)')
fig.legend(handles=[baseline_h, cooldown_h], loc='lower center',
           bbox_to_anchor=(0.45, 0.02), ncol=2, fontsize=8,
           frameon=False, handlelength=2.5)

# ── Save ────────────────────────────────────────────────────
out = Path(__file__).parent
save_fig(fig, 'fig_f_throttle_v2', out)
fig.savefig(out / 'fig_f_throttle_v2.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved to {out}/fig_f_throttle_v2.{{pdf,svg,png}}")
