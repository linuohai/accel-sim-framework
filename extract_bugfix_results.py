#!/usr/bin/env python3
"""Extract IPC from G1/G2 experiments and print comparison table."""
import re, os, sys

LOG_DIR = "result/log"

# Old GRASP IPC from experiment_results.md (baseline reference)
OLD_GRASP = {
    "bfs_cit_sym": 108.6590, "sssp_cit_sym": 92.6932, "bc_cit_sym": 105.7574,
    "cc_cit_sym": 396.7720, "spmv_cit_sym": 373.9898, "vc_cit_sym": 348.1072,
    "bfs_cit_dir": 6.0582, "sssp_cit_dir": 6.6036, "bc_cit_dir": 104.5995,
    "bfs_web_sym": 11.4803, "sssp_web_sym": 14.0103, "bc_web_sym": 12.0137,
    "cc_web_sym": 98.2785, "spmv_web_sym": 181.6270, "vc_web_sym": 52.8224,
    "bfs_web_dir": 30.3437, "sssp_web_dir": 35.2638, "bc_web_dir": 40.6961,
    "bfs_flickr_sym": 12.4394, "sssp_flickr_sym": 14.0832, "bc_flickr_sym": 16.4193,
    "cc_flickr_sym": 111.8395, "spmv_flickr_sym": 109.3995,
    "bfs_flickr_dir": 10.4393, "sssp_flickr_dir": 11.9255, "bc_flickr_dir": 13.4415,
    "bfs_road_sym": 14.7858, "sssp_road_sym": 17.9242, "bc_road_sym": 18.8052,
    "cc_road_sym": 1489.4384, "spmv_road_sym": 1250.5500,
    "bfs_road_dir": 0.3776, "sssp_road_dir": 0.4094, "bc_road_dir": 68.1183,
    "bfs_socLJ_sym": 29.1730, "bfs_socLJ_dir": 27.7606, "spmv_socLJ_sym": 162.9411,
}

BASELINE = {
    "bfs_cit_sym": 102.3376, "sssp_cit_sym": 90.4341, "bc_cit_sym": 104.0350,
    "cc_cit_sym": 426.7173, "spmv_cit_sym": 373.9836, "vc_cit_sym": 341.7518,
    "bfs_cit_dir": 5.3349, "sssp_cit_dir": 5.9499, "bc_cit_dir": 95.2826,
    "bfs_web_sym": 7.3528, "sssp_web_sym": 9.5580, "bc_web_sym": 10.8322,
    "cc_web_sym": 50.7687, "spmv_web_sym": 129.6846, "vc_web_sym": 52.3822,
    "bfs_web_dir": 23.5588, "sssp_web_dir": 28.8141, "bc_web_dir": 37.6489,
    "bfs_flickr_sym": 9.7943, "sssp_flickr_sym": 11.7493, "bc_flickr_sym": 13.4772,
    "cc_flickr_sym": 46.8674, "spmv_flickr_sym": 79.2566,
    "bfs_flickr_dir": 8.3156, "sssp_flickr_dir": 10.0362, "bc_flickr_dir": 11.9542,
    "bfs_road_sym": 14.3030, "sssp_road_sym": 17.5696, "bc_road_sym": 18.4855,
    "cc_road_sym": 1490.0549, "spmv_road_sym": 1262.7443,
    "bfs_road_dir": 0.3776, "sssp_road_dir": 0.4094, "bc_road_dir": 68.0938,
    "bfs_socLJ_sym": 22.2490, "bfs_socLJ_dir": 23.2595, "spmv_socLJ_sym": 138.3245,
}

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

def get_ipc(log_path):
    """Extract final gpu_tot_ipc from log, return None if not COMPLETE."""
    if not os.path.exists(log_path):
        return None
    with open(log_path) as f:
        content = f.read()
    if "status=COMPLETE" not in content:
        return None
    matches = re.findall(r"gpu_tot_ipc\s*=\s*([\d.]+)", content)
    return float(matches[-1]) if matches else None

def pct(new, old):
    if old is None or old == 0:
        return "—"
    return f"{(new/old - 1)*100:+.1f}%"

# Collect results
g1_results = {}
g2_results = {}
for wl in WORKLOADS:
    g1_results[wl] = get_ipc(f"{LOG_DIR}/{wl}_g1_bugfix.log")
    g2_results[wl] = get_ipc(f"{LOG_DIR}/{wl}_g2_specstride.log")

# Print summary
g1_done = sum(1 for v in g1_results.values() if v is not None)
g2_done = sum(1 for v in g2_results.values() if v is not None)
print(f"G1: {g1_done}/38 complete, G2: {g2_done}/38 complete\n")

print(f"{'Key':<22} {'Base':>10} {'OldGRASP':>10} {'G1':>10} {'G1vsBase':>10} {'G1vsOld':>10} {'G2':>10} {'G2vsBase':>10} {'G2vsG1':>10}")
print("-" * 112)

for wl in WORKLOADS:
    base = BASELINE.get(wl)
    old = OLD_GRASP.get(wl)
    g1 = g1_results[wl]
    g2 = g2_results[wl]

    base_s = f"{base:.4f}" if base else "—"
    old_s = f"{old:.4f}" if old else "—"
    g1_s = f"{g1:.4f}" if g1 else "⏳"
    g2_s = f"{g2:.4f}" if g2 else "⏳"

    g1vb = pct(g1, base) if g1 and base else "—"
    g1vo = pct(g1, old) if g1 and old else "—"
    g2vb = pct(g2, base) if g2 and base else "—"
    g2vg1 = pct(g2, g1) if g2 and g1 else "—"

    print(f"{wl:<22} {base_s:>10} {old_s:>10} {g1_s:>10} {g1vb:>10} {g1vo:>10} {g2_s:>10} {g2vb:>10} {g2vg1:>10}")
