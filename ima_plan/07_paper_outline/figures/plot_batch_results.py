#!/usr/bin/env python3
"""Plot GRASP evaluation results — grouped bar chart by dataset category.

Reads completed experiment logs and produces:
  Fig 1: IPC Speedup (%) — grouped by dataset, one bar per algorithm
  Fig 2: Timeliness — index vs data, grouped bar
"""

import sys
from pathlib import Path
import re
import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, save_fig, CB10, HATCHES, annotate_bars

apply_style()
import matplotlib.pyplot as plt

LOG_DIR = REPO / "result" / "log"
OUT_DIR = Path(__file__).resolve().parent


# ── Data Extraction ──────────────────────────────────────────────────────────

def extract_from_log(logfile):
    """Extract final_ipc, IMA_TIMELINESS, accuracy, status from a log file."""
    if not logfile.exists():
        return None
    text = logfile.read_text(errors="ignore")
    result = {}

    m = re.search(r"^status=(\w+)", text, re.M)
    result["status"] = m.group(1) if m else "UNKNOWN"

    # Prefer final_ipc from EXPERIMENT SUMMARY (only written on completion)
    m = re.search(r"^final_ipc=([\d.]+)", text, re.M)
    result["ipc"] = float(m.group(1)) if m else None

    m = re.search(r"^IMA_TIMELINESS:.*index=([\d.]+)%.*data=([\d.]+)%", text, re.M)
    if m:
        result["idx_timeliness"] = float(m.group(1))
        result["data_timeliness"] = float(m.group(2))

    # Accuracy from GRASP_EFFECT (any SM, take last)
    for m in re.finditer(r"GRASP_EFFECT.*accuracy=([\d.]+)%", text):
        result["accuracy"] = float(m.group(1))

    return result


def find_baseline(key):
    """Find a completed baseline log for a given key.

    Supports both new format (final_ipc=) and old format (gpu_tot_ipc).
    """
    for suffix in ["_baseline", ""]:
        lf = LOG_DIR / f"{key}{suffix}.log"
        if not lf.exists():
            continue
        text = lf.read_text(errors="ignore")
        if "grasp_enabled=true" in text:
            continue

        result = {}
        # New format: has EXPERIMENT SUMMARY with status=COMPLETE
        if "status=COMPLETE" in text:
            return extract_from_log(lf)

        # Old format: no EXPERIMENT SUMMARY, but has gpu_tot_ipc
        # Use LAST occurrence (final total, not per-kernel intermediate)
        matches = re.findall(r"gpu_tot_ipc\s*=\s*([\d.]+)", text)
        if matches:
            result["ipc"] = float(matches[-1])
            result["status"] = "COMPLETE_OLD"
            # Also try to get IMA_DEMAND
            m2 = re.search(r"^IMA_DEMAND:.*", text, re.M)
            if m2:
                result["ima_demand"] = m2.group(0)
            return result
    return None


# ── Define Workloads ─────────────────────────────────────────────────────────

# Structure: dataset_label -> list of (algo_label, trace_key)
# Use the "best" sym variant per our dual-variant strategy
DATASETS = {
    "cit-Patents": [
        ("BFS",   "bfs_ima_high"),
        ("SSSP",  "sssp_ima_high"),
        ("BC",    "bc_ima_high"),
        ("CC",    "cc_ima_high"),
        ("SpMV",  "spmv_ima_high"),
        ("PR",    "pr_ima_high"),
        ("VC",    "vc_ima_high"),
        ("SymGS", "symgs_ima_high"),
        # directed variants
        ("BFS-d",   "bfs_cit_dir"),
        ("SSSP-d",  "sssp_cit_dir"),
        ("BC-d",    "bc_cit_dir"),
        ("PR-d",    "pr_cit_dir"),
        ("SymGS-d", "symgs_cit_dir"),
    ],
    "web-Google": [
        ("BFS",   "bfs_ima_med"),
        ("SSSP",  "sssp_ima_med"),
        ("BC",    "bc_ima_med"),
        ("CC",    "cc_ima_med"),
        ("SpMV",  "spmv_ima_med"),
        ("PR",    "pr_ima_med"),
        ("VC",    "vc_ima_med"),
        ("SymGS", "symgs_ima_med"),
        ("BFS-d",   "bfs_web_dir"),
        ("SSSP-d",  "sssp_web_dir"),
        ("BC-d",    "bc_web_dir"),
        ("PR-d",    "pr_web_dir"),
        ("SymGS-d", "symgs_web_dir"),
    ],
    "flickr": [
        ("BFS",   "bfs_flickr_sym"),
        ("SSSP",  "sssp_flickr_sym"),
        ("BC",    "bc_flickr_sym"),
        ("CC",    "cc_flickr"),
        ("SpMV",  "spmv_flickr"),
        ("PR",    "pr_flickr_sym"),
        ("BFS-d",   "bfs_flickr_dir"),
        ("SSSP-d",  "sssp_flickr_dir"),
        ("BC-d",    "bc_flickr_dir"),
        ("PR-d",    "pr_flickr_dir"),
    ],
    "roadNet-CA": [
        ("BFS",   "bfs_road_sym"),
        ("SSSP",  "sssp_road_sym"),
        ("BC",    "bc_road_sym"),
        ("CC",    "cc_road"),
        ("SpMV",  "spmv_road"),
        ("PR",    "pr_road_sym"),
        ("SymGS", "symgs_road_dir"),
        ("BFS-d",   "bfs_road_dir"),
        ("SSSP-d",  "sssp_road_dir"),
        ("BC-d",    "bc_road_dir"),
        ("PR-d",    "pr_road_dir"),
    ],
}

# For the main figure: only sym=1 (or best variant), core algorithms
MAIN_ALGOS = ["BFS", "SSSP", "BC", "CC", "SpMV", "PR", "VC", "SymGS"]
MAIN_DATASETS = ["cit-Patents", "web-Google", "flickr", "roadNet-CA"]


# ── Collect Data ─────────────────────────────────────────────────────────────

def collect_speedup_data():
    """Collect speedup data for the main figure."""
    data = {}  # dataset -> algo -> speedup
    timeliness = {}  # dataset -> algo -> (idx_t, data_t)
    accuracies = {}  # dataset -> algo -> accuracy

    for ds, workloads in DATASETS.items():
        data[ds] = {}
        timeliness[ds] = {}
        accuracies[ds] = {}
        for algo, key in workloads:
            if algo not in MAIN_ALGOS:
                continue
            grasp_log = LOG_DIR / f"{key}_grasp.log"
            grasp = extract_from_log(grasp_log)
            base = find_baseline(key)

            # Only use results with COMPLETE status (not partial runs)
            if grasp and grasp.get("status") == "COMPLETE" and grasp.get("ipc"):
                if base and base.get("ipc") and base["ipc"] > 0:
                    speedup = (grasp["ipc"] - base["ipc"]) / base["ipc"] * 100
                    data[ds][algo] = speedup
                else:
                    data[ds][algo] = None  # GRASP done but no baseline

                if "idx_timeliness" in grasp:
                    timeliness[ds][algo] = (
                        grasp["idx_timeliness"],
                        grasp["data_timeliness"],
                    )
                if "accuracy" in grasp:
                    accuracies[ds][algo] = grasp["accuracy"]

    return data, timeliness, accuracies


# ── Shared: uniform subplot with all 8 algos on x-axis ──────────────────────

def _plot_metric_subplots(metric_data, ylabel, filename, two_series=False,
                          series_labels=None, ylim=(0, 105)):
    """Plot a 1×4 subplot grid with uniform x-axis (all MAIN_ALGOS in each panel).

    metric_data: dict  dataset -> algo -> value (single) or (val1, val2) if two_series
    """
    fig, axes = plt.subplots(1, len(MAIN_DATASETS), figsize=figsize_full(0.45),
                             constrained_layout=True, sharey=True)
    x = np.arange(len(MAIN_ALGOS))

    for ax, ds in zip(axes, MAIN_DATASETS):
        if two_series:
            v1 = [metric_data.get(ds, {}).get(a, (None, None))[0] for a in MAIN_ALGOS]
            v2 = [metric_data.get(ds, {}).get(a, (None, None))[1] for a in MAIN_ALGOS]
            w = 0.35
            bars1 = []
            bars2 = []
            for i, (a, b) in enumerate(zip(v1, v2)):
                c1 = CB10[0] if a is not None else "#eeeeee"
                c2 = CB10[1] if b is not None else "#eeeeee"
                h1 = a if a is not None else 0
                h2 = b if b is not None else 0
                ax.bar(x[i] - w/2, h1, w, color=c1, edgecolor="white", linewidth=0.3,
                       label=series_labels[0] if i == 0 else "")
                ax.bar(x[i] + w/2, h2, w, color=c2, edgecolor="white", linewidth=0.3,
                       label=series_labels[1] if i == 0 else "")
                if a is None:
                    ax.text(x[i] - w/2, 1, "?", ha="center", va="bottom", fontsize=4, color="#aaa")
                if b is None:
                    ax.text(x[i] + w/2, 1, "?", ha="center", va="bottom", fontsize=4, color="#aaa")
        else:
            vals = [metric_data.get(ds, {}).get(a) for a in MAIN_ALGOS]
            for i, v in enumerate(vals):
                c = CB10[0] if v is not None else "#eeeeee"
                h = v if v is not None else 0
                ax.bar(x[i], h, 0.7, color=c, edgecolor="white", linewidth=0.3)
                if v is None:
                    ax.text(x[i], 1, "?", ha="center", va="bottom", fontsize=4, color="#aaa")

        ax.set_xticks(x)
        ax.set_xticklabels(MAIN_ALGOS, rotation=45, ha="right", fontsize=5.5)
        ax.set_title(ds, fontsize=7)
        if ylim:
            ax.set_ylim(ylim)

    axes[0].set_ylabel(ylabel)
    if two_series and series_labels:
        axes[-1].legend(loc="lower right", fontsize=6)

    save_fig(fig, filename, OUT_DIR)
    print(f"Saved: {OUT_DIR}/{filename}.pdf")
    plt.close(fig)


# ── Fig 1: Speedup Bar Chart ────────────────────────────────────────────────

def plot_speedup(data):
    fig, ax = plt.subplots(figsize=figsize_full(0.45), constrained_layout=True)

    n_ds = len(MAIN_DATASETS)
    n_algo = len(MAIN_ALGOS)
    bar_w = 0.8 / n_algo
    x_base = np.arange(n_ds)

    for i, algo in enumerate(MAIN_ALGOS):
        vals = []
        for ds in MAIN_DATASETS:
            v = data.get(ds, {}).get(algo)
            vals.append(v if v is not None else 0)

        x = x_base + (i - n_algo / 2 + 0.5) * bar_w
        color = CB10[i % len(CB10)]
        bars = ax.bar(x, vals, bar_w * 0.9, label=algo, color=color,
                      edgecolor="white", linewidth=0.3)

        for j, v in enumerate(vals):
            dv = data.get(MAIN_DATASETS[j], {}).get(algo)
            if dv is None:
                ax.text(x[j], 1, "?", ha="center", va="bottom",
                        fontsize=5, color="#999999")

    ax.set_xticks(x_base)
    ax.set_xticklabels(MAIN_DATASETS)
    ax.set_ylabel("GRASP Speedup (%)")
    ax.axhline(y=0, color="black", linewidth=0.5)

    all_vals = [v for ds in data.values() for v in ds.values() if v is not None]
    if all_vals:
        ymax = max(all_vals) * 1.25
        ymin = min(min(all_vals), 0) * 1.1
        ax.set_ylim(ymin, ymax)

    ax.legend(loc="upper left", ncol=4, fontsize=6, frameon=True,
              fancybox=False, edgecolor="#cccccc")

    save_fig(fig, "grasp_speedup_by_dataset", OUT_DIR)
    print(f"Saved: {OUT_DIR}/grasp_speedup_by_dataset.pdf")
    plt.close(fig)


# ── Fig 2: Timeliness (Index vs Data, all 8 algos uniform) ──────────────────

def plot_timeliness(timeliness):
    _plot_metric_subplots(
        timeliness, "Timeliness (%)", "grasp_timeliness_by_dataset",
        two_series=True, series_labels=["Index", "Data"], ylim=(0, 105),
    )


# ── Fig 3: Accuracy (single series, all 8 algos uniform) ────────────────────

def plot_accuracy(accuracies):
    _plot_metric_subplots(
        accuracies, "Accuracy (%)", "grasp_accuracy_by_dataset",
        two_series=False, ylim=(0, 105),
    )


# ── Fig 4: Coverage (Index vs Data) ─────────────────────────────────────────

def collect_coverage(timeliness):
    """Compute coverage from baseline and GRASP IMA_DEMAND misses.

    Coverage = (baseline_misses - grasp_misses) / baseline_misses * 100
    Requires both baseline and GRASP IMA_DEMAND data.
    """
    coverage = {}
    for ds, workloads in DATASETS.items():
        coverage[ds] = {}
        for algo, key in workloads:
            if algo not in MAIN_ALGOS:
                continue
            glog = LOG_DIR / f"{key}_grasp.log"
            if not glog.exists():
                continue
            gtext = glog.read_text(errors="ignore")
            if "status=COMPLETE" not in gtext:
                continue

            # GRASP IMA_DEMAND
            gm = re.search(
                r"^IMA_DEMAND:.*index_misses=(\d+).*data_misses=(\d+)", gtext, re.M
            )
            if not gm:
                continue
            g_idx_miss = int(gm.group(1))
            g_data_miss = int(gm.group(2))

            # Find baseline IMA_DEMAND
            blog = None
            for suf in ["_baseline", ""]:
                bf = LOG_DIR / f"{key}{suf}.log"
                if bf.exists():
                    bt = bf.read_text(errors="ignore")
                    if "grasp_enabled=true" not in bt:
                        bm = re.search(
                            r"IMA_DEMAND:.*index_misses=(\d+).*data_misses=(\d+)", bt
                        )
                        if bm:
                            blog = bf
                            b_idx_miss = int(bm.group(1))
                            b_data_miss = int(bm.group(2))
                            break

            if blog is None:
                continue

            idx_cov = (b_idx_miss - g_idx_miss) / b_idx_miss * 100 if b_idx_miss > 0 else 0
            data_cov = (b_data_miss - g_data_miss) / b_data_miss * 100 if b_data_miss > 0 else 0
            coverage[ds][algo] = (idx_cov, data_cov)

    return coverage


def plot_coverage(coverage):
    _plot_metric_subplots(
        coverage, "Coverage (%)", "grasp_coverage_by_dataset",
        two_series=True, series_labels=["Index", "Data"], ylim=None,
    )


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    data, timeliness, accuracies = collect_speedup_data()

    # Print summary table
    print("=== Speedup Data ===")
    for ds in MAIN_DATASETS:
        print(f"\n{ds}:")
        for algo in MAIN_ALGOS:
            v = data.get(ds, {}).get(algo)
            t = timeliness.get(ds, {}).get(algo)
            a = accuracies.get(ds, {}).get(algo)
            status = f"{v:+.1f}%" if v is not None else "pending"
            t_str = f"idx={t[0]:.0f}% data={t[1]:.0f}%" if t else ""
            a_str = f"acc={a:.0f}%" if a is not None else ""
            print(f"  {algo:6s}: {status:>10s}  {t_str}  {a_str}")

    coverage = collect_coverage(timeliness)

    plot_speedup(data)
    plot_timeliness(timeliness)
    plot_accuracy(accuracies)
    plot_coverage(coverage)

    # Print markdown table for the paper
    print("\n\n=== Paper Table (Markdown) ===\n")
    print("| Dataset | Algo | Speedup | Idx T. | Data T. | Acc. | Idx Cov. | Data Cov. |")
    print("|---------|------|--------:|-------:|--------:|-----:|---------:|----------:|")
    for ds in MAIN_DATASETS:
        for algo in MAIN_ALGOS:
            sp = data.get(ds, {}).get(algo)
            t = timeliness.get(ds, {}).get(algo)
            a = accuracies.get(ds, {}).get(algo)
            c = coverage.get(ds, {}).get(algo)
            sp_s = f"{sp:+.1f}%" if sp is not None else "—"
            it_s = f"{t[0]:.1f}%" if t else "—"
            dt_s = f"{t[1]:.1f}%" if t else "—"
            a_s = f"{a:.1f}%" if a is not None else "—"
            ic_s = f"{c[0]:+.1f}%" if c else "—"
            dc_s = f"{c[1]:+.1f}%" if c else "—"
            print(f"| {ds} | {algo} | {sp_s} | {it_s} | {dt_s} | {a_s} | {ic_s} | {dc_s} |")
