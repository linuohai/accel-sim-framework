"""
Canonical workload naming and ordering for GRASP paper figures.

All §5 evaluation figures must use these short names and the canonical order
to maintain consistency across figures (writing rule E-11).

Usage:
    from workload_names import SHORT_NAME, ORDERED_28, ALG_GROUPS, ALG_OF
    label = SHORT_NAME["bfs_web_sym"]   # "BFS-wg"
    for key in ORDERED_28:
        ...
"""

# ── Dataset abbreviations (2 chars) ──────────────────────────────────────────
DATASET_ABBR = {
    "cit":   "cp",   # cit-Patents
    "web":   "wg",   # web-Google
    "flickr":"fl",   # flickr
    "road":  "rd",   # roadNet-CA
    "socLJ": "sl",   # soc-LiveJournal1
    "ec":    "ec",   # ecology1 (extended)
    "rmat12":"rm",   # rmat12   (extended)
}

# ── Algorithm short names ────────────────────────────────────────────────────
ALG_SHORT = {
    "bfs":  "BFS",
    "sssp": "SSSP",
    "bc":   "BC",
    "cc":   "CC",
    "spmv": "SpM",
    "vc":   "VC",
    "mis":  "MIS",
    "color":"CLR",
    "mst":  "MST",
}

# ── Per-workload short name (full table) ─────────────────────────────────────
SHORT_NAME = {
    # cit-Patents (BFS/SSSP/BC are dir, others sym)
    "bfs_cit_dir":     "BFS-cp",
    "sssp_cit_dir":    "SSSP-cp",
    "bc_cit_dir":      "BC-cp",
    "cc_cit_sym":      "CC-cp",
    "spmv_cit_sym":    "SpM-cp",
    "vc_cit_sym":      "VC-cp",
    # web-Google (all sym)
    "bfs_web_sym":     "BFS-wg",
    "sssp_web_sym":    "SSSP-wg",
    "bc_web_sym":      "BC-wg",
    "cc_web_sym":      "CC-wg",
    "spmv_web_sym":    "SpM-wg",
    "vc_web_sym":      "VC-wg",
    # flickr (all sym, no VC)
    "bfs_flickr_sym":  "BFS-fl",
    "sssp_flickr_sym": "SSSP-fl",
    "bc_flickr_sym":   "BC-fl",
    "cc_flickr_sym":   "CC-fl",
    "spmv_flickr_sym": "SpM-fl",
    # roadNet-CA (all sym)
    "bfs_road_sym":    "BFS-rd",
    "sssp_road_sym":   "SSSP-rd",
    "bc_road_sym":     "BC-rd",
    "cc_road_sym":     "CC-rd",
    "spmv_road_sym":   "SpM-rd",
    "vc_road_sym":     "VC-rd",
    # soc-LiveJournal1
    "bfs_socLJ_sym":   "BFS-sl",
    "spmv_socLJ_sym":  "SpM-sl",
    # Extended (Pannotia + LonestarGPU)
    "pann_mis_flickr": "MIS-fl",
    "pann_color_eco":  "CLR-ec",
    "ls_mst_rmat12":   "MST-rm",
}

# ── Canonical order (28 workloads, algorithm-primary sort) ───────────────────
ORDERED_28 = [
    # BFS group (5)
    "bfs_cit_dir", "bfs_web_sym", "bfs_flickr_sym", "bfs_road_sym", "bfs_socLJ_sym",
    # SSSP group (4)
    "sssp_cit_dir", "sssp_web_sym", "sssp_flickr_sym", "sssp_road_sym",
    # BC group (4)
    "bc_cit_dir", "bc_web_sym", "bc_flickr_sym", "bc_road_sym",
    # CC group (4)
    "cc_cit_sym", "cc_web_sym", "cc_flickr_sym", "cc_road_sym",
    # SpMV group (5)
    "spmv_cit_sym", "spmv_web_sym", "spmv_flickr_sym", "spmv_road_sym", "spmv_socLJ_sym",
    # VC group (3)
    "vc_cit_sym", "vc_web_sym", "vc_road_sym",
    # Extended (3)
    "pann_mis_flickr", "pann_color_eco", "ls_mst_rmat12",
]

# Sanity check
assert len(ORDERED_28) == 28, f"Expected 28 workloads, got {len(ORDERED_28)}"
assert set(ORDERED_28) == set(SHORT_NAME.keys()), "ORDERED_28 / SHORT_NAME mismatch"

# ── Algorithm groups (for vertical separator placement) ──────────────────────
# Each tuple: (algorithm label, list of workload keys in canonical order)
ALG_GROUPS = [
    ("BFS",  ["bfs_cit_dir", "bfs_web_sym", "bfs_flickr_sym", "bfs_road_sym", "bfs_socLJ_sym"]),
    ("SSSP", ["sssp_cit_dir", "sssp_web_sym", "sssp_flickr_sym", "sssp_road_sym"]),
    ("BC",   ["bc_cit_dir", "bc_web_sym", "bc_flickr_sym", "bc_road_sym"]),
    ("CC",   ["cc_cit_sym", "cc_web_sym", "cc_flickr_sym", "cc_road_sym"]),
    ("SpMV", ["spmv_cit_sym", "spmv_web_sym", "spmv_flickr_sym", "spmv_road_sym", "spmv_socLJ_sym"]),
    ("VC",   ["vc_cit_sym", "vc_web_sym", "vc_road_sym"]),
    ("Ext.", ["pann_mis_flickr", "pann_color_eco", "ls_mst_rmat12"]),
]

# Reverse map: workload -> algorithm label
ALG_OF = {wkl: alg for alg, wkls in ALG_GROUPS for wkl in wkls}

# ── Group separator x-positions (between consecutive groups) ─────────────────
def group_separator_positions(workloads=None):
    """Return x-axis positions where vertical dashed lines should be drawn
    between algorithm groups. Position = boundary between last bar of group N
    and first bar of group N+1, expressed as float index + 0.5.
    """
    if workloads is None:
        workloads = ORDERED_28
    seps = []
    for i in range(1, len(workloads)):
        if ALG_OF.get(workloads[i]) != ALG_OF.get(workloads[i - 1]):
            seps.append(i - 0.5)
    return seps


def short_label(key, fallback="?"):
    """Return short workload label, with optional fallback for unknown keys."""
    return SHORT_NAME.get(key, fallback)


# ── 27-workload variant (for Quality figures, MST excluded) ──────────────────
ORDERED_27 = [w for w in ORDERED_28 if w != "ls_mst_rmat12"]
assert len(ORDERED_27) == 27


if __name__ == "__main__":
    # Self-test: print all workloads with short labels
    print(f"Total workloads: {len(ORDERED_28)}")
    print(f"\nCanonical order:")
    for i, key in enumerate(ORDERED_28, 1):
        print(f"  {i:2d}. {key:20s} -> {SHORT_NAME[key]}")
    print(f"\nGroup separators: {group_separator_positions()}")
