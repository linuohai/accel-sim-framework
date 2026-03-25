"""
Generate paper-quality figures from real GRASP project data.
Demonstrates: bar chart, grouped bar, stacked bar, line plot.
"""
import sys
from pathlib import Path
import csv

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_util import (
    apply_style, figsize_col, figsize_full, save_fig, CB10,
    COLORS_L1_STATUS, COLORS_IMA_ROLE, annotate_bars,
)

apply_style()

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "_demo_figures"
OUT.mkdir(exist_ok=True)

DATA_DIR = _REPO / "ima_plan"

# ══════════════════════════════════════════════════════════════════════════════
# Helper: read CSV into list of dicts
# ══════════════════════════════════════════════════════════════════════════════

def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))

# ══════════════════════════════════════════════════════════════════════════════
# Figure 1: IMA Load Share — static instruction mix (motivation)
# ══════════════════════════════════════════════════════════════════════════════

def fig1_instruction_mix():
    rows = read_csv(DATA_DIR / "01_ima_characterization/l1_miss_breakdown/data/instruction_mix_summary.csv")

    workloads = []
    regular_share = []
    stride_share = []
    ima_share = []

    for r in rows:
        wl = r["workload"].replace("_ima_high", "").upper()
        total_ld = int(r["main_kernel_load_count"])
        regular = int(r["regular_load_count"])
        stride = int(r["stride_load_count"])
        ima = int(r["ima_load_count"])
        workloads.append(wl)
        regular_share.append(regular / total_ld)
        stride_share.append(stride / total_ld)
        ima_share.append(ima / total_ld)

    fig, ax = plt.subplots(figsize=figsize_col(aspect=0.75))
    x = np.arange(len(workloads))
    w = 0.55

    b1 = np.array(regular_share)
    b2 = np.array(stride_share)
    b3 = np.array(ima_share)

    ax.bar(x, b1, w, label="Regular", color=CB10[2], edgecolor="black", linewidth=0.3)
    ax.bar(x, b2, w, bottom=b1, label="Stride", color=CB10[4], edgecolor="black", linewidth=0.3)
    ax.bar(x, b3, w, bottom=b1+b2, label="IMA", color=CB10[0], edgecolor="black", linewidth=0.3)

    ax.set_ylabel("Share of Load Instructions")
    ax.set_xticks(x)
    ax.set_xticklabels(workloads)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right")

    save_fig(fig, "fig1_instruction_mix", OUT)
    plt.close(fig)
    print("Fig 1: Instruction mix — done")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 2: Index vs Data Load Hit Rate (prefetcher design motivation)
# ══════════════════════════════════════════════════════════════════════════════

def fig2_index_vs_data_hit_rate():
    rows = read_csv(
        DATA_DIR / "04_prefetcher_design/extra_pattern/small_1sm_cta5/prefetch_design_summary_lrr.csv"
    )

    DISPLAY = {
        "bfs_ima_small": "BFS",
        "sssp_ima_small": "SSSP",
        "bc_ima_small_forward": "BC(f)",
        "bc_ima_small_reverse": "BC(r)",
        "cc_ima_small": "CC",
        "spmv_ima_small": "SpMV",
    }

    workloads = []
    idx_hr = []
    data_hr = []

    for r in rows:
        wl = r["workload"]
        if wl in DISPLAY:
            workloads.append(DISPLAY[wl])
            idx_hr.append(float(r["index_hit_rate"]))
            data_hr.append(float(r["data_hit_rate"]))

    fig, ax = plt.subplots(figsize=figsize_col(aspect=0.75))
    x = np.arange(len(workloads))
    w = 0.32

    bars1 = ax.bar(x - w/2, idx_hr, w, label="Index Load",
                   color=COLORS_IMA_ROLE["index_load"], edgecolor="black", linewidth=0.3)
    bars2 = ax.bar(x + w/2, data_hr, w, label="Data Load",
                   color=COLORS_IMA_ROLE["data_load"], edgecolor="black", linewidth=0.3)

    ax.set_ylabel("L1 Hit Rate")
    ax.set_xticks(x)
    ax.set_xticklabels(workloads)
    ax.set_ylim(0, 1.0)
    ax.legend(loc="upper right")

    # Add percentage labels
    for bars in [bars1, bars2]:
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.015,
                    f"{h:.0%}", ha="center", va="bottom", fontsize=5.5)

    save_fig(fig, "fig2_index_vs_data_hitrate", OUT)
    plt.close(fig)
    print("Fig 2: Index vs Data hit rate — done")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 3: Data Load Latency Distribution (p50 vs p90) — shows prefetch need
# ══════════════════════════════════════════════════════════════════════════════

def fig3_latency_distribution():
    rows = read_csv(
        DATA_DIR / "04_prefetcher_design/extra_pattern/small_1sm_cta5/prefetch_design_summary_lrr.csv"
    )

    DISPLAY = {
        "bfs_ima_small": "BFS",
        "sssp_ima_small": "SSSP",
        "bc_ima_small_forward": "BC(f)",
        "bc_ima_small_reverse": "BC(r)",
        "cc_ima_small": "CC",
        "spmv_ima_small": "SpMV",
    }

    workloads = []
    idx_p50 = []
    idx_p90 = []
    data_p50 = []
    data_p90 = []

    for r in rows:
        wl = r["workload"]
        if wl in DISPLAY:
            workloads.append(DISPLAY[wl])
            idx_p50.append(float(r["index_issue_to_refill_p50"]))
            idx_p90.append(float(r["index_issue_to_refill_p90"]))
            data_p50.append(float(r["data_issue_to_refill_p50"]))
            data_p90.append(float(r["data_issue_to_refill_p90"]))

    fig, ax = plt.subplots(figsize=figsize_col(aspect=0.8))
    x = np.arange(len(workloads))
    w = 0.2

    ax.bar(x - 1.5*w, idx_p50, w, label="Index p50",
           color=COLORS_IMA_ROLE["index_load"], edgecolor="black", linewidth=0.3)
    ax.bar(x - 0.5*w, idx_p90, w, label="Index p90",
           color=COLORS_IMA_ROLE["index_load"], edgecolor="black", linewidth=0.3,
           alpha=0.55, hatch="//")
    ax.bar(x + 0.5*w, data_p50, w, label="Data p50",
           color=COLORS_IMA_ROLE["data_load"], edgecolor="black", linewidth=0.3)
    ax.bar(x + 1.5*w, data_p90, w, label="Data p90",
           color=COLORS_IMA_ROLE["data_load"], edgecolor="black", linewidth=0.3,
           alpha=0.55, hatch="//")

    ax.set_ylabel("Issue-to-Refill Latency (cycles)")
    ax.set_xticks(x)
    ax.set_xticklabels(workloads)
    ax.legend(loc="upper left", fontsize=6, ncol=2)

    save_fig(fig, "fig3_latency_p50_p90", OUT)
    plt.close(fig)
    print("Fig 3: Latency p50/p90 — done")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 4: Data Load Miss Breakdown (sector miss vs full miss)
# ══════════════════════════════════════════════════════════════════════════════

def fig4_data_miss_breakdown():
    rows = read_csv(
        DATA_DIR / "04_prefetcher_design/extra_pattern/small_1sm_cta5/prefetch_design_summary_lrr.csv"
    )

    DISPLAY = {
        "bfs_ima_small": "BFS",
        "sssp_ima_small": "SSSP",
        "bc_ima_small_forward": "BC(f)",
        "bc_ima_small_reverse": "BC(r)",
        "cc_ima_small": "CC",
        "spmv_ima_small": "SpMV",
    }

    workloads = []
    data_hit = []
    data_partial_miss = []
    data_full_miss = []

    for r in rows:
        wl = r["workload"]
        if wl in DISPLAY:
            workloads.append(DISPLAY[wl])
            hr = float(r["data_hit_rate"]) + float(r["data_hit_reserved_rate"])
            pm = float(r["data_partial_miss_issue_rate"])
            fm = float(r["data_full_miss_issue_rate"])
            # Normalize to sum = 1 for the miss portion
            total = hr + pm + fm
            data_hit.append(hr / total if total > 0 else 0)
            data_partial_miss.append(pm / total if total > 0 else 0)
            data_full_miss.append(fm / total if total > 0 else 0)

    fig, ax = plt.subplots(figsize=figsize_col(aspect=0.75))
    x = np.arange(len(workloads))
    w = 0.55

    dh = np.array(data_hit)
    dpm = np.array(data_partial_miss)
    dfm = np.array(data_full_miss)

    ax.bar(x, dh, w, label="Hit + Hit Reserved",
           color=COLORS_L1_STATUS["HIT"], edgecolor="black", linewidth=0.3)
    ax.bar(x, dpm, w, bottom=dh, label="Partial Miss (sector)",
           color=COLORS_L1_STATUS["MSHR_HIT"], edgecolor="black", linewidth=0.3)
    ax.bar(x, dfm, w, bottom=dh+dpm, label="Full Miss",
           color=COLORS_L1_STATUS["MISS"], edgecolor="black", linewidth=0.3)

    ax.set_ylabel("Fraction of Data Load Accesses")
    ax.set_xticks(x)
    ax.set_xticklabels(workloads)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper right", fontsize=6)

    save_fig(fig, "fig4_data_miss_breakdown", OUT)
    plt.close(fig)
    print("Fig 4: Data load miss breakdown — done")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 5: GRASP Prefetch Activity Over Time (SpMV 5CTA iteration summary)
# ══════════════════════════════════════════════════════════════════════════════

def fig5_grasp_activity_timeline():
    rows = read_csv(
        DATA_DIR / "05_implementation/spmv_deep_dive/results/5cta/iteration_summary.csv"
    )

    # Filter to iterations with actual activity
    iters = []
    idx_inject = []
    data_inject = []
    demand_miss = []
    demand_hit = []

    for r in rows:
        it = int(r["iter"])
        ii = int(r["idx_pf_inject"])
        di = int(r["data_pf_inject"])
        dm = int(r["demand_miss"])
        dh = int(r["demand_hit"]) + int(r["demand_hit_reserved"]) + int(r["demand_mshr_hit"])

        if ii + di + dm + dh > 0:  # skip empty iters
            iters.append(it)
            idx_inject.append(ii)
            data_inject.append(di)
            demand_miss.append(dm)
            demand_hit.append(dh)

    # Limit to first 60 active iterations for readability
    N = min(60, len(iters))
    iters = iters[:N]
    idx_inject = np.array(idx_inject[:N])
    data_inject = np.array(data_inject[:N])
    demand_miss = np.array(demand_miss[:N])
    demand_hit = np.array(demand_hit[:N])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize_full(aspect=0.5),
                                     sharex=True, gridspec_kw={"hspace": 0.08})

    x = np.arange(N)

    # Top: prefetch injections
    ax1.bar(x, idx_inject, 0.8, label="Index PF Inject",
            color=COLORS_IMA_ROLE["index_load"], edgecolor="none", linewidth=0)
    ax1.bar(x, data_inject, 0.8, bottom=idx_inject, label="Data PF Inject",
            color=COLORS_IMA_ROLE["data_load"], edgecolor="none", linewidth=0)
    ax1.set_ylabel("PF Injections")
    ax1.legend(loc="upper right", fontsize=6)

    # Bottom: demand outcomes
    ax2.bar(x, demand_hit, 0.8, label="Demand Hit",
            color=COLORS_L1_STATUS["HIT"], edgecolor="none", linewidth=0)
    ax2.bar(x, demand_miss, 0.8, bottom=demand_hit, label="Demand Miss",
            color=COLORS_L1_STATUS["MISS"], edgecolor="none", linewidth=0)
    ax2.set_ylabel("Demand Accesses")
    ax2.set_xlabel("Iteration (SpMV, 5 CTAs)")
    ax2.legend(loc="upper right", fontsize=6)

    # X ticks: show every 10th
    tick_pos = list(range(0, N, 10))
    ax2.set_xticks(tick_pos)
    ax2.set_xticklabels([str(iters[i]) for i in tick_pos], fontsize=6)

    save_fig(fig, "fig5_grasp_activity_timeline", OUT)
    plt.close(fig)
    print("Fig 5: GRASP activity timeline — done")


# ══════════════════════════════════════════════════════════════════════════════
# Figure 6: Full-width — Cross-workload IMA Characterization Summary
# ══════════════════════════════════════════════════════════════════════════════

def fig6_cross_workload_summary():
    mix_rows = read_csv(DATA_DIR / "01_ima_characterization/l1_miss_breakdown/data/instruction_mix_summary.csv")
    design_rows = read_csv(DATA_DIR / "04_prefetcher_design/extra_pattern/small_1sm_cta5/prefetch_design_summary_lrr.csv")

    DISPLAY_MIX = {"bfs_ima_high": "BFS", "sssp_ima_high": "SSSP", "bc_ima_high": "BC",
                   "cc_ima_high": "CC", "spmv_ima_high": "SpMV"}
    DISPLAY_DESIGN = {"bfs_ima_small": "BFS", "sssp_ima_small": "SSSP",
                      "cc_ima_small": "CC", "spmv_ima_small": "SpMV"}

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=figsize_full(aspect=0.4))

    # Panel A: IMA share of loads
    wl_a, vals_a = [], []
    for r in mix_rows:
        wl = r["workload"]
        if wl in DISPLAY_MIX:
            wl_a.append(DISPLAY_MIX[wl])
            vals_a.append(float(r["ima_load_share_of_loads"]))
    x = np.arange(len(wl_a))
    bars = ax1.bar(x, vals_a, 0.55, color=CB10[0], edgecolor="black", linewidth=0.3)
    annotate_bars(ax1, bars, fmt="{:.0%}", fontsize=5.5, offset=0.01)
    ax1.set_ylabel("IMA Share of Loads")
    ax1.set_xticks(x)
    ax1.set_xticklabels(wl_a)
    ax1.set_ylim(0, 0.75)
    ax1.set_title("(a) Static IMA Ratio", fontsize=8)

    # Panel B: Data load miss rate
    wl_b, miss_b = [], []
    for r in design_rows:
        wl = r["workload"]
        if wl in DISPLAY_DESIGN:
            wl_b.append(DISPLAY_DESIGN[wl])
            miss_b.append(float(r["data_miss_like_rate"]))
    x = np.arange(len(wl_b))
    bars = ax1.bar(x, vals_a[:len(wl_b)], 0.55, color=CB10[0], edgecolor="black", linewidth=0.3)  # placeholder
    bars2 = ax2.bar(x, miss_b, 0.55, color=COLORS_IMA_ROLE["data_load"], edgecolor="black", linewidth=0.3)
    annotate_bars(ax2, bars2, fmt="{:.0%}", fontsize=5.5, offset=0.01)
    ax2.set_ylabel("Data Load Miss Rate")
    ax2.set_xticks(x)
    ax2.set_xticklabels(wl_b)
    ax2.set_ylim(0, 1.15)
    ax2.set_title("(b) Data Load L1 Miss Rate", fontsize=8)

    # Panel C: Data load p50 latency
    wl_c, lat_c = [], []
    for r in design_rows:
        wl = r["workload"]
        if wl in DISPLAY_DESIGN:
            wl_c.append(DISPLAY_DESIGN[wl])
            lat_c.append(float(r["data_issue_to_refill_p50"]))
    x = np.arange(len(wl_c))
    bars3 = ax3.bar(x, lat_c, 0.55, color=CB10[3], edgecolor="black", linewidth=0.3)
    annotate_bars(ax3, bars3, fmt="{:.0f}", fontsize=5.5, offset=10)
    ax3.set_ylabel("P50 Latency (cycles)")
    ax3.set_xticks(x)
    ax3.set_xticklabels(wl_c)
    ax3.set_title("(c) Data Load Refill Latency", fontsize=8)

    fig.tight_layout()
    save_fig(fig, "fig6_cross_workload_summary", OUT)
    plt.close(fig)
    print("Fig 6: Cross-workload summary — done")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    fig1_instruction_mix()
    fig2_index_vs_data_hit_rate()
    fig3_latency_distribution()
    fig4_data_miss_breakdown()
    fig5_grasp_activity_timeline()
    fig6_cross_workload_summary()
    print(f"\nAll figures saved to: {OUT}/")
