#!/usr/bin/env python3
"""Fig F Base: Clean curves + fills only, NO text annotations.

User will add annotations manually based on nano-banana reference.
"""
import sys
from pathlib import Path
import numpy as np

_REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from scipy.ndimage import uniform_filter1d

apply_style()

# ── Synthetic Data ──────────────────────────────────────────
np.random.seed(42)
TOTAL = 25000
dt = 50
t = np.arange(0, TOTAL, dt)

# Window Accuracy
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

# Effective Threshold
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

# Without Throttle baseline
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

# ── Figure ──────────────────────────────────────────────────
fig = plt.figure(figsize=(7.0, 3.5))
gs = fig.add_gridspec(2, 1, height_ratios=[2.2, 1.0], hspace=0.12)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1], sharex=ax1)
plt.subplots_adjust(left=0.08, right=0.92, top=0.95, bottom=0.12)

# ── Top: MSHR Occupancy (curves + shading only) ────────────
# Reference lines
ax1.axhline(THR_HI, color='#AAAAAA', ls=':', lw=0.8, zorder=1)
ax1.axhline(THR_LO, color='#AAAAAA', ls=':', lw=0.8, zorder=1)

# Cooldown shading (both axes)
for s, e in cooldown_intervals:
    ax1.axvspan(s, e, color='#ff9896', alpha=0.3, lw=0, zorder=1)
    ax2.axvspan(s, e, color='#ff9896', alpha=0.3, lw=0, zorder=1)

# Without Throttle baseline
ax1.plot(t, mshr_nt, color='#999999', lw=1.0, ls='--', alpha=0.6, zorder=2)

# MSHR Occupancy
ax1.plot(t, mshr, color='#1f77b4', lw=1.8, zorder=3)

# Effective Threshold
ax1.plot(t, eff_threshold, color='#d62728', lw=1.5, ls='--', zorder=4)

ax1.set_ylim(0, 100)
ax1.set_xlim(0, TOTAL)
ax1.set_ylabel('MSHR Occupancy (%)', fontsize=9)
ax1.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f'{int(x/1000)}K' if x > 0 else '0'))

# ── Bottom: Window Accuracy (fill only) ────────────────────
ax2.axhline(ACC_HI, color='#AAAAAA', ls=':', lw=0.8, zorder=1)
ax2.axhline(ACC_LO, color='#AAAAAA', ls=':', lw=0.8, zorder=1)

ax2.fill_between(t, 0, accuracy, color='#1B7A2B', alpha=0.45, zorder=2)
ax2.plot(t, accuracy, color='#1B7A2B', lw=1.4, zorder=3)

ax2.set_ylim(0, 100)
ax2.set_ylabel('Accuracy (%)', fontsize=9)
ax2.set_xlabel('Cycles', fontsize=9)
ax2.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f'{int(x/1000)}K' if x > 0 else '0'))

# ── Save ────────────────────────────────────────────────────
out = Path(__file__).parent
save_fig(fig, 'fig_f_base', out)
fig.savefig(out / 'fig_f_base.png', dpi=300, bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved to {out}/fig_f_base.{{pdf,svg,png}}")

# Print cooldown intervals for reference
print("\nCooldown intervals (for annotation):")
for i, (s, e) in enumerate(cooldown_intervals):
    print(f"  CD{i}: {s/1000:.1f}K - {e/1000:.1f}K  (duration: {(e-s)/1000:.1f}K)")
