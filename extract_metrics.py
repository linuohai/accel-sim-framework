#!/usr/bin/env python3
"""Extract Timeliness, Accuracy, Coverage from G1/G2 logs."""
import re, os

LOG_DIR = "result/log"

WORKLOADS = [
    "bfs_cit_sym", "sssp_cit_sym", "bc_cit_sym", "cc_cit_sym", "spmv_cit_sym", "vc_cit_sym",
    "bfs_cit_dir", "sssp_cit_dir", "bc_cit_dir",
    "bfs_web_sym", "sssp_web_sym", "bc_web_sym", "cc_web_sym", "spmv_web_sym", "vc_web_sym",
    "bfs_web_dir", "sssp_web_dir", "bc_web_dir",
    "bfs_flickr_sym", "sssp_flickr_sym", "bc_flickr_sym", "cc_flickr_sym", "spmv_flickr_sym",
    "bfs_flickr_dir", "sssp_flickr_dir", "bc_flickr_dir",
    "bfs_road_sym", "sssp_road_sym", "bc_road_sym", "cc_road_sym", "spmv_road_sym", "vc_road_sym",
    "bfs_road_dir", "sssp_road_dir", "bc_road_dir",
    "bfs_socLJ_sym", "bfs_socLJ_dir", "spmv_socLJ_sym",
]

# Old GRASP timeliness/accuracy from experiment_results.md
OLD = {
    "bfs_cit_sym":   {"idx_t": 72.54, "data_t": 54.17, "acc": 29.70},
    "sssp_cit_sym":  {"idx_t": 79.54, "data_t": 46.03, "acc": 34.38},
    "bc_cit_sym":    {"idx_t": 89.90, "data_t": 84.87, "acc": 25.79},
    "cc_cit_sym":    {"idx_t": 95.45, "data_t": 90.00, "acc": 39.09},
    "spmv_cit_sym":  {"idx_t": 23.32, "data_t": 58.51, "acc": 32.86},
    "vc_cit_sym":    {"idx_t": 56.65, "data_t": 34.43, "acc": 40.58},
    "bfs_cit_dir":   {"idx_t": 94.46, "data_t": 43.14, "acc": 99.89},
    "sssp_cit_dir":  {"idx_t": 95.28, "data_t": 41.90, "acc": 99.78},
    "bc_cit_dir":    {"idx_t": 97.51, "data_t": 58.23, "acc": 99.61},
    "bfs_web_sym":   {"idx_t": 86.05, "data_t": 77.30, "acc": 59.12},
    "sssp_web_sym":  {"idx_t": 88.38, "data_t": 77.28, "acc": 62.21},
    "bc_web_sym":    {"idx_t": 96.50, "data_t": 87.79, "acc": 59.00},
    "cc_web_sym":    {"idx_t": 95.39, "data_t": 90.76, "acc": 54.64},
    "spmv_web_sym":  {"idx_t": 53.99, "data_t": 92.62, "acc": 60.46},
    "vc_web_sym":    {"idx_t": 60.05, "data_t": 59.48, "acc": 53.92},
    "bfs_web_dir":   {"idx_t": 88.34, "data_t": 73.18, "acc": 55.00},
    "sssp_web_dir":  {"idx_t": 86.95, "data_t": 68.64, "acc": 51.90},
    "bc_web_dir":    {"idx_t": 95.82, "data_t": 84.78, "acc": 55.79},
    "bfs_flickr_sym":  {"idx_t": 91.12, "data_t": 88.59, "acc": 71.86},
    "sssp_flickr_sym": {"idx_t": 92.94, "data_t": 90.51, "acc": 78.43},
    "bc_flickr_sym":   {"idx_t": 98.46, "data_t": 94.52, "acc": 81.94},
    "cc_flickr_sym":   {"idx_t": 95.29, "data_t": 93.60, "acc": 76.84},
    "spmv_flickr_sym": {"idx_t": 60.30, "data_t": 89.03, "acc": 69.75},
    "bfs_flickr_dir":  {"idx_t": 91.26, "data_t": 86.91, "acc": 71.92},
    "sssp_flickr_dir": {"idx_t": 92.52, "data_t": 88.63, "acc": 77.15},
    "bc_flickr_dir":   {"idx_t": 98.45, "data_t": 93.26, "acc": 81.32},
    "bfs_road_sym":  {"idx_t": 90.91, "data_t": 59.42, "acc": 100.00},
    "sssp_road_sym": {"idx_t": 96.74, "data_t": 68.29, "acc": 100.00},
    "bc_road_sym":   {"idx_t": 90.67, "data_t": 74.86, "acc": 98.76},
    "cc_road_sym":   {"idx_t": 93.62, "data_t": 90.90, "acc": 91.65},
    "spmv_road_sym": {"idx_t": 89.31, "data_t": 84.76, "acc": 91.87},
    "bfs_road_dir":  {"idx_t": 99.46, "data_t": 38.39, "acc": None},
    "sssp_road_dir": {"idx_t": 99.46, "data_t": 54.81, "acc": None},
    "bc_road_dir":   {"idx_t": 98.19, "data_t": 57.27, "acc": None},
    "bfs_socLJ_sym": {"idx_t": 87.54, "data_t": 84.11, "acc": 49.05},
    "bfs_socLJ_dir": {"idx_t": 86.94, "data_t": 82.69, "acc": 47.07},
    "spmv_socLJ_sym":{"idx_t": 43.51, "data_t": 71.06, "acc": 44.25},
}

# Old baseline IMA_DEMAND misses (for coverage calc) — from experiment_results.md
# Only workloads that have coverage data
OLD_BASE_MISSES = {
    "bfs_flickr_sym":  {"idx": None, "data": None},  # available in baseline
    "vc_cit_sym":      {"idx": None, "data": None},
    # Many old baselines lack IMA_DEMAND — skip coverage for those
}

def extract_metrics(log_path):
    """Extract timeliness, accuracy, coverage-related fields from a GRASP log."""
    if not os.path.exists(log_path):
        return None
    with open(log_path) as f:
        content = f.read()
    if "status=COMPLETE" not in content:
        return None

    result = {}

    # Timeliness — last IMA_TIMELINESS line
    tm = re.findall(r"IMA_TIMELINESS:\s+index=([\d.]+)%\s+data=([\d.]+)%", content)
    if tm:
        result["idx_t"] = float(tm[-1][0])
        result["data_t"] = float(tm[-1][1])

    # Accuracy — aggregate all SM EFFECT lines
    useful_total = 0
    useless_total = 0
    for m in re.finditer(r"GRASP_EFFECT SM\d+:\s+pf_useful=(\d+)\s+pf_useless=(\d+)", content):
        useful_total += int(m.group(1))
        useless_total += int(m.group(2))
    denom = useful_total + useless_total
    result["acc"] = (useful_total / denom * 100) if denom > 0 else None

    # IMA_DEMAND misses (for coverage — need baseline misses too)
    ima = re.findall(r"IMA_DEMAND:.*?index_misses=(\d+).*?data_misses=(\d+)", content)
    if ima:
        result["idx_misses"] = int(ima[-1][0])
        result["data_misses"] = int(ima[-1][1])

    return result

def fmt(val, old_val=None):
    if val is None:
        return "—", ""
    s = f"{val:.2f}"
    if old_val is not None:
        delta = val - old_val
        d = f"{delta:+.2f}"
    else:
        d = ""
    return s, d

# Extract and print
print(f"{'Key':<22} {'Old IdxT':>8} {'G1 IdxT':>8} {'G2 IdxT':>8} {'Old DatT':>8} {'G1 DatT':>8} {'G2 DatT':>8} {'Old Acc':>8} {'G1 Acc':>8} {'G2 Acc':>8}")
print("-" * 112)

for wl in WORKLOADS:
    old = OLD.get(wl, {})
    g1 = extract_metrics(f"{LOG_DIR}/{wl}_g1_bugfix.log") or {}
    g2 = extract_metrics(f"{LOG_DIR}/{wl}_g2_specstride.log") or {}

    oit = f"{old.get('idx_t', 0):.2f}" if old.get('idx_t') is not None else "—"
    odt = f"{old.get('data_t', 0):.2f}" if old.get('data_t') is not None else "—"
    oac = f"{old.get('acc', 0):.2f}" if old.get('acc') is not None else "—"

    g1it = f"{g1.get('idx_t', 0):.2f}" if g1.get('idx_t') is not None else "—"
    g1dt = f"{g1.get('data_t', 0):.2f}" if g1.get('data_t') is not None else "—"
    g1ac = f"{g1.get('acc', 0):.2f}" if g1.get('acc') is not None else "—"

    g2it = f"{g2.get('idx_t', 0):.2f}" if g2.get('idx_t') is not None else "—"
    g2dt = f"{g2.get('data_t', 0):.2f}" if g2.get('data_t') is not None else "—"
    g2ac = f"{g2.get('acc', 0):.2f}" if g2.get('acc') is not None else "—"

    print(f"{wl:<22} {oit:>8} {g1it:>8} {g2it:>8} {odt:>8} {g1dt:>8} {g2dt:>8} {oac:>8} {g1ac:>8} {g2ac:>8}")
