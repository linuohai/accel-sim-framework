#!/usr/bin/env python3
"""Round-2 Effectiveness Fig E2: GRASP Pipeline Funnel.

Horizontal stacked bar (one row per workload) — every row sums to 100% of
`idx_attempted` and is partitioned into five fates:

  * Delivered            data_got_data                  (green)   — GOOD
  * Throttled            data_throttled                 (orange)  — bad
  * Index RFAIL          idx_rfail                      (red)     — bad
  * Data  RFAIL          data_rfail                     (#C85200) — bad
  * Other (pipeline loss)idx_attempted - {sum above}     (gray)   — bad
                          (clamped to 0 if negative; this happens for
                           CC/SpMV/VC where DPU fan-out makes data_got_data
                           larger than what naive accounting predicts —
                           a sign that pipeline coordination is amplifying
                           prefetches.  We report it under "Bonus" if so.)

Workloads: ORDERED_27 (MST excluded — null funnel).
Sorted by delivery rate (good = top) for an immediate visual ranking.

Data source: ima_plan/07_paper_outline/figures/effectiveness_data.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# ── Plot style ───────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig                          # noqa: E402
from workload_names import ORDERED_27, SHORT_NAME                    # noqa: E402

apply_style()
import matplotlib.pyplot as plt                                      # noqa: E402
from matplotlib.patches import Patch                                 # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_JSON = _REPO / "ima_plan/07_paper_outline/figures/effectiveness_data.json"

# ── Colours (semantic) ──────────────────────────────────────────────────────
C_DELIVERED = "#2CA02C"   # green  — successfully delivered
C_THROTTLE  = "#FF800E"   # orange — throttled at data stage
C_IDX_RFAIL = "#D62728"   # red    — index reservation fail
C_DAT_RFAIL = "#C85200"   # dark orange — data reservation fail
C_OTHER     = "#999999"   # gray   — other pipeline loss
C_BONUS     = "#5F9ED1"   # light blue — bonus (delivered > attempted, fan-out)

# ── Load data ────────────────────────────────────────────────────────────────
DATA = json.loads(DATA_JSON.read_text())["workloads"]


def funnel_buckets(rec):
    """Return dict of fractions of idx_attempted for each fate, or None."""
    f = (rec.get("grasp") or {}).get("grasp_funnel")
    if not f or f.get("idx_attempted", 0) == 0:
        return None
    ia = float(f["idx_attempted"])
    delivered = float(f["data_got_data"])
    throttled = float(f["data_throttled"])
    idx_rfail = float(f["idx_rfail"])
    data_rfail = float(f["data_rfail"])
    accounted = delivered + throttled + idx_rfail + data_rfail
    other = ia - accounted              # may be negative for fan-out workloads
    return {
        "ia": ia,
        "delivered_pct":  delivered  / ia * 100,
        "throttled_pct":  throttled  / ia * 100,
        "idx_rfail_pct":  idx_rfail  / ia * 100,
        "data_rfail_pct": data_rfail / ia * 100,
        "other_pct":      other      / ia * 100,    # signed
    }


rows: list[tuple[str, dict]] = []
skipped = []
for k in ORDERED_27:
    rec = DATA.get(k) or {}
    b = funnel_buckets(rec)
    if b is None:
        skipped.append(k)
        continue
    rows.append((k, b))

# Sort by delivery rate (high = good, top of plot)
rows.sort(key=lambda r: r[1]["delivered_pct"], reverse=True)

n = len(rows)
labels = [SHORT_NAME[k] for k, _ in rows]
delivered  = np.array([r["delivered_pct"]   for _, r in rows])
throttled  = np.array([r["throttled_pct"]   for _, r in rows])
idx_rfail  = np.array([r["idx_rfail_pct"]   for _, r in rows])
data_rfail = np.array([r["data_rfail_pct"]  for _, r in rows])
other_raw  = np.array([r["other_pct"]       for _, r in rows])
# Split "other": positive part = "Other loss" (gray), negative = "Bonus" (blue)
other_loss  = np.where(other_raw > 0, other_raw, 0.0)
bonus       = np.where(other_raw < 0, -other_raw, 0.0)

# ── Plot: horizontal stacked bar ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.0, 3.50), constrained_layout=True)

y = np.arange(n)
bar_h = 0.72

# stack from left → right: Delivered | Throttled | Idx RFAIL | Data RFAIL | Other
left = np.zeros(n)
ax.barh(y, delivered, bar_h, left=left,
        color=C_DELIVERED, edgecolor="black", linewidth=0.3,
        label="Delivered", zorder=3)
left += delivered
ax.barh(y, throttled, bar_h, left=left,
        color=C_THROTTLE, edgecolor="black", linewidth=0.3,
        label="Throttled", zorder=3)
left += throttled
ax.barh(y, idx_rfail, bar_h, left=left,
        color=C_IDX_RFAIL, edgecolor="black", linewidth=0.3,
        label="Idx RFAIL", zorder=3)
left += idx_rfail
ax.barh(y, data_rfail, bar_h, left=left,
        color=C_DAT_RFAIL, edgecolor="black", linewidth=0.3,
        label="Data RFAIL", zorder=3)
left += data_rfail
ax.barh(y, other_loss, bar_h, left=left,
        color=C_OTHER, edgecolor="black", linewidth=0.3,
        label="Other loss", zorder=3)
left += other_loss
# Bonus (DPU fan-out) sits *outside* the 100% line (extends past x=100)
ax.barh(y, bonus, bar_h, left=left,
        color=C_BONUS, edgecolor="black", linewidth=0.3,
        label="DPU fan-out bonus", zorder=3, alpha=0.85)

# 100% reference line
ax.axvline(x=100, color="black", linewidth=0.6, alpha=0.6, zorder=2)

# Annotate Delivered % at the right edge of each delivered segment.
# If the segment is too narrow to fit the label inside, place it outside
# (right side, in green) so it stays readable.
for i, d in enumerate(delivered):
    txt = f"{d:.0f}%"
    if d >= 8.0:
        ax.text(d - 1.5, i, txt, ha="right", va="center",
                fontsize=5.5, color="white", fontweight="bold", zorder=6)
    else:
        ax.text(d + 1.0, i, txt, ha="left", va="center",
                fontsize=5.5, color=C_DELIVERED, fontweight="bold", zorder=6)

# ── Axes formatting ──────────────────────────────────────────────────────────
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=6.5)
ax.invert_yaxis()                       # best workload at top
ax.set_xlim(0, max(125, float(left.max()) + 5))
ax.set_xlabel("Fraction of idx_attempted (%)", fontsize=7)
ax.tick_params(axis="x", labelsize=7)
ax.tick_params(axis="y", labelsize=6.5)

# Legend on top in 6 columns
ax.legend(
    ncol=6, fontsize=6.0, frameon=False,
    loc="upper left", bbox_to_anchor=(0.0, 1.07),
    handlelength=1.2, handleheight=0.9,
    columnspacing=1.0,
)

mean_d = float(np.mean(delivered))
ax.set_title(
    f"GRASP Pipeline Funnel: Idx Attempted -> Delivered (mean delivery = {mean_d:.0f}%)",
    fontsize=8, pad=14,
)

save_fig(fig, "proto_r2_e2_pipeline_funnel", OUT_DIR)
plt.close(fig)

# ── Verification ─────────────────────────────────────────────────────────────
print(f"Saved: {OUT_DIR}/proto_r2_e2_pipeline_funnel.{{pdf,svg}}")
print(f"workloads = {n}   skipped = {skipped}")
print(f"delivery%: mean = {mean_d:6.2f}   min = {delivered.min():6.2f}   "
      f"max = {delivered.max():6.2f}")
print(f"throttle%: mean = {throttled.mean():6.2f}   "
      f"max = {throttled.max():6.2f}")
print(f"idx rfail%:mean = {idx_rfail.mean():6.2f}   "
      f"max = {idx_rfail.max():6.2f}")
print()
print("Top-5 delivery:")
for k, r in rows[:5]:
    print(f"  {SHORT_NAME[k]:9s}  delivered = {r['delivered_pct']:5.1f}%   "
          f"throttled = {r['throttled_pct']:5.1f}%   "
          f"idx_rfail = {r['idx_rfail_pct']:5.1f}%")
print("\nBottom-5 delivery:")
for k, r in rows[-5:]:
    print(f"  {SHORT_NAME[k]:9s}  delivered = {r['delivered_pct']:5.1f}%   "
          f"throttled = {r['throttled_pct']:5.1f}%   "
          f"idx_rfail = {r['idx_rfail_pct']:5.1f}%")
