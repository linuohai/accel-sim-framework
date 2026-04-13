"""
Shared data for Round 5 §5.4 Sensitivity + Ablation nohatch prototypes.

All numbers are copied from
  ima_plan/06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md

Exp-A: Component Ablation (20 workloads)
Exp-B: Throttle Ablation  (22 wkl IPC | 15 wkl Accuracy | 16 wkl Coverage)
Exp-C: Prefetch Distance  (20 workloads)
Exp-D: Storage Budget     (20 workloads)

Each dict is keyed by canonical workload key (matches workload_names.ORDERED_27).
"""
from __future__ import annotations
import numpy as np

# ---------------------------------------------------------------------------
# Exp-A: Component Ablation — Speedup% vs NoPF baseline (20 workloads)
# Source MD §Exp-A "结果：Speedup%" (lines ~247-268)
# Columns: (Data-Only %, Index-Only %, Full GRASP %)
# ---------------------------------------------------------------------------
ABLATION_PCT = {
    "bfs_cit_dir":     (10.2, 3.5, 14.0),
    "sssp_cit_dir":    (10.4, 2.5, 10.8),
    "bc_cit_dir":      (8.0,  2.0, 9.8),
    "spmv_web_sym":    (0.5,  22.4, 40.2),
    "bfs_web_sym":     (43.5, 6.4,  56.2),
    "cc_flickr_sym":   (53.4, 36.9, 102.5),
    "spmv_flickr_sym": (8.6,  22.5, 37.8),
    "bfs_flickr_sym":  (13.4, 11.1, 27.2),
    "bfs_road_sym":    (1.9,  6.7,  8.5),
    "sssp_road_sym":   (2.1,  5.4,  6.3),
    "cc_road_sym":     (1.1,  -0.1, -0.7),
    "bc_road_sym":     (1.4,  3.3,  4.7),
    "sssp_flickr_sym": (18.4, 5.6,  20.0),
    "sssp_web_sym":    (45.1, 4.6,  46.9),
    "vc_web_sym":      (0.6,  3.1,  2.5),
    "spmv_cit_sym":    (-1.1, -0.7, -1.3),
    "bc_flickr_sym":   (14.9, 11.3, 23.6),
    "bc_web_sym":      (7.6,  3.0,  14.2),
    "vc_cit_sym":      (1.0,  0.5,  1.9),
    "cc_web_sym":      (51.5, 17.5, 69.9),
}


# ---------------------------------------------------------------------------
# Exp-B: Throttle IPC Speedup% (22 workloads)
# Source MD §Exp-B "结果：IPC Speedup%" (lines ~307-330)
# Columns: (Default %, D5b %, T40C200 %)
# ---------------------------------------------------------------------------
THROTTLE_IPC_PCT = {
    "bfs_cit_dir":     (13.6, 13.9, 14.0),
    "sssp_cit_dir":    (11.0, 10.8, 10.8),
    "bc_cit_dir":      (9.8,  9.8,  9.8),
    "cc_cit_sym":      (-7.0, -3.8, 4.4),
    "spmv_cit_sym":    (0.0,  -1.7, -1.1),
    "vc_cit_sym":      (1.9,  1.9,  1.9),
    "bfs_web_sym":     (56.1, 56.4, 56.2),
    "sssp_web_sym":    (46.6, 46.9, 46.9),
    "bc_web_sym":      (10.9, 10.7, 14.2),
    "cc_web_sym":      (93.6, 70.9, 69.8),
    "spmv_web_sym":    (40.1, 36.7, 40.2),
    "vc_web_sym":      (0.8,  1.9,  2.5),
    "bfs_flickr_sym":  (27.0, 27.2, 27.2),
    "sssp_flickr_sym": (19.9, 20.0, 20.0),
    "bc_flickr_sym":   (21.8, 21.9, 23.6),
    "cc_flickr_sym":   (138.6, 122.0, 102.5),
    "spmv_flickr_sym": (38.0, 37.2, 37.8),
    "bfs_road_sym":    (3.4,  8.5,  8.5),
    "sssp_road_sym":   (2.0,  6.3,  6.3),
    "bc_road_sym":     (1.7,  4.7,  4.7),
    "cc_road_sym":     (-0.0, 0.1,  -0.7),
    "spmv_road_sym":   (-1.0, -1.0, -1.0),
}


# ---------------------------------------------------------------------------
# Exp-B: Accuracy% (15 workloads)
# Source MD §Exp-B "结果：Accuracy%" (lines ~334-350)
# ---------------------------------------------------------------------------
THROTTLE_ACC = {
    "bfs_cit_dir":     (99.89, 99.88, 99.88),
    "sssp_cit_dir":    (99.78, 99.70, 99.70),
    "bc_cit_dir":      (99.61, 99.59, 99.53),
    "cc_cit_sym":      (39.09, 47.93, 60.49),
    "spmv_cit_sym":    (32.86, 18.46, 16.08),
    "bfs_web_sym":     (59.12, 64.46, 66.87),
    "sssp_web_sym":    (62.21, 66.60, 68.65),
    "bc_web_sym":      (59.00, 64.03, 64.14),
    "cc_web_sym":      (54.64, 60.05, 72.60),
    "spmv_web_sym":    (60.46, 57.48, 66.31),
    "bfs_flickr_sym":  (71.86, 76.37, 79.21),
    "sssp_flickr_sym": (78.43, 81.68, 83.42),
    "bc_flickr_sym":   (81.94, 85.04, 85.94),
    "cc_flickr_sym":   (76.84, 79.55, 88.93),
    "spmv_flickr_sym": (69.75, 68.83, 74.00),
}


# ---------------------------------------------------------------------------
# Exp-B: Data Coverage% (16 workloads)
# Source MD §Exp-B "结果：Data Coverage%" (lines ~354-371)
# ---------------------------------------------------------------------------
THROTTLE_COV = {
    "bfs_cit_dir":     (18.3, 38.3, 38.3),
    "sssp_cit_dir":    (17.2, 37.1, 37.0),
    "bc_cit_dir":      (5.6,  40.4, 40.4),
    "bfs_web_sym":     (26.9, 35.5, 34.4),
    "sssp_web_sym":    (23.1, 31.7, 31.1),
    "bc_web_sym":      (5.5,  38.0, 37.9),
    "cc_web_sym":      (34.1, 36.4, 36.2),
    "spmv_web_sym":    (5.9,  10.8, 8.2),
    "bfs_flickr_sym":  (48.8, 68.7, 67.6),
    "sssp_flickr_sym": (47.5, 65.9, 65.4),
    "bc_flickr_sym":   (16.6, 63.2, 63.2),
    "cc_flickr_sym":   (59.0, 76.4, 71.1),
    "spmv_flickr_sym": (24.2, 54.1, 51.1),
    "bfs_road_sym":    (13.4, 42.8, 42.5),
    "sssp_road_sym":   (11.4, 52.1, 52.1),
    "bc_road_sym":     (12.7, 55.1, 54.9),
}


# ---------------------------------------------------------------------------
# Exp-C: Distance sensitivity — IPC (20 workloads)
# Source MD §Exp-C "结果：IPC" (lines ~449-470)
# Columns: (D=1, D=2, D=4, D=8)
# ---------------------------------------------------------------------------
DISTANCE_IPC = {
    "bfs_cit_dir":     (6.0830,   6.0016,   5.8353,   5.6452),
    "sssp_cit_dir":    (6.5949,   6.5631,   6.4006,   6.2253),
    "bc_cit_dir":      (104.6244, 104.5427, 104.0702, 103.1893),
    "spmv_web_sym":    (181.8048, 177.6429, 176.4435, 174.1239),
    "bfs_web_sym":     (11.4819,  11.4908,  11.4573,  11.3891),
    "cc_flickr_sym":   (94.8873,  117.6036, 108.5085, 112.1545),
    "spmv_flickr_sym": (109.2283, 106.7236, 101.5856, 98.6639),
    "bfs_flickr_sym":  (12.4611,  12.6612,  12.5458,  12.4249),
    "bfs_road_sym":    (15.5226,  15.2976,  14.7518,  14.7166),
    "sssp_road_sym":   (18.6798,  18.5391,  18.0669,  18.0383),
    "cc_road_sym":     (1480.1456, 1491.3662, 1493.0670, 1494.1324),
    "bc_road_sym":     (19.3459,  19.2285,  18.9472,  18.9105),
    "sssp_flickr_sym": (14.0945,  14.0787,  14.0637,  14.0134),
    "sssp_web_sym":    (14.0433,  14.0184,  13.9785,  13.8944),
    "vc_web_sym":      (53.6679,  53.2977,  53.0010,  52.8152),
    "spmv_cit_sym":    (369.8046, 372.8049, 373.0233, 373.1912),
    "bc_flickr_sym":   (16.6540,  16.3987,  16.3653,  16.3397),
    "bc_web_sym":      (12.3684,  12.0075,  11.9156,  11.8279),
    "vc_cit_sym":      (348.1434, 350.0393, 349.6961, 349.2664),
    "cc_web_sym":      (86.2021,  88.1106,  88.7813,  99.4289),
}
DISTANCES = [1, 2, 4, 8]


# ---------------------------------------------------------------------------
# Exp-D: Storage sensitivity — IPC (20 workloads)
# Source MD §Exp-D "结果：IPC" (lines ~590-611)
# Columns: (S1 712B, S2 1.1KB, S3 1.9KB, S4 3.6KB)
# ---------------------------------------------------------------------------
STORAGE_IPC = {
    "bfs_cit_dir":     (6.0789,   6.0789,   6.0789,   6.0789),
    "sssp_cit_dir":    (6.5920,   6.5920,   6.5920,   6.5920),
    "bc_cit_dir":      (104.6116, 104.6116, 104.6116, 104.6116),
    "spmv_web_sym":    (165.4689, 169.3697, 167.6819, 179.5210),
    "bfs_web_sym":     (11.4964,  11.4964,  11.4964,  11.4964),
    "cc_flickr_sym":   (111.1339, 111.1339, 111.1339, 111.1339),
    "spmv_flickr_sym": (98.2555,  99.5312,  97.0296,  98.1003),
    "bfs_flickr_sym":  (12.4521,  12.4521,  12.4521,  12.4521),
    "bfs_road_sym":    (15.5202,  15.5202,  15.5202,  15.5202),
    "sssp_road_sym":   (18.6726,  18.6726,  18.6726,  18.6726),
    "cc_road_sym":     (1491.8667, 1491.8667, 1491.8667, 1491.8667),
    "bc_road_sym":     (19.3493,  19.3493,  19.3493,  19.3493),
    "sssp_flickr_sym": (14.0887,  14.0887,  14.0887,  14.0887),
    "sssp_web_sym":    (14.0383,  14.0383,  14.0383,  14.0383),
    "vc_web_sym":      (52.6012,  53.1145,  52.7116,  52.8377),
    "spmv_cit_sym":    (372.6010, 370.1086, 375.3021, 371.8455),
    "bc_flickr_sym":   (16.4228,  16.4228,  16.4228,  16.4228),
    "bc_web_sym":      (12.0113,  12.0113,  12.0113,  12.0113),
    "vc_cit_sym":      (348.1185, 349.1956, 348.2394, 347.8958),
    "cc_web_sym":      (94.0677,  94.0677,  94.0677,  94.0677),
}
STORAGE_BYTES  = [712, 1100, 1900, 3600]
STORAGE_LABELS = ["S1\n712B", "S2\n1.1KB", "S3\n1.9KB", "S4\n3.6KB"]


# ---------------------------------------------------------------------------
# Algorithm aggregation for sensitivity line plots
# Uses only workloads present in the experiment tables (intersection with
# Exp-C / Exp-D 20-workload set).
# ---------------------------------------------------------------------------
SENS_ALGORITHMS = [
    ("BFS",  ["bfs_cit_dir", "bfs_web_sym", "bfs_flickr_sym", "bfs_road_sym"]),
    ("SSSP", ["sssp_cit_dir", "sssp_web_sym", "sssp_flickr_sym", "sssp_road_sym"]),
    ("BC",   ["bc_cit_dir", "bc_web_sym", "bc_flickr_sym", "bc_road_sym"]),
    ("CC",   ["cc_web_sym", "cc_flickr_sym", "cc_road_sym"]),
    ("SpMV", ["spmv_cit_sym", "spmv_web_sym", "spmv_flickr_sym"]),
    ("VC",   ["vc_cit_sym", "vc_web_sym"]),
]


def gmean(arr) -> float:
    arr = np.asarray(arr, dtype=float)
    return float(np.exp(np.mean(np.log(arr))))


def pct_to_mult(p: float) -> float:
    return 1.0 + p / 100.0


def sensitivity_normalized(ipc_dict, workloads):
    """Return dict[wl] -> np.array normalized to col 0 (first column)."""
    out = {}
    for wl in workloads:
        t = np.asarray(ipc_dict[wl], dtype=float)
        out[wl] = t / t[0]
    return out


def algorithm_gmean_lines(norm_dict, algorithms):
    """Return list of (name, np.array) — one gmean line per algorithm."""
    lines = []
    for name, wkls in algorithms:
        present = [wl for wl in wkls if wl in norm_dict]
        if not present:
            continue
        stack = np.stack([norm_dict[wl] for wl in present], axis=0)
        # Geometric mean column-wise
        logs = np.log(stack)
        gm = np.exp(np.mean(logs, axis=0))
        lines.append((name, gm, len(present)))
    return lines


def overall_gmean_line(norm_dict):
    stack = np.stack(list(norm_dict.values()), axis=0)
    return np.exp(np.mean(np.log(stack), axis=0))
