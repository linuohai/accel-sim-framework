#!/usr/bin/env python3
"""Cross-compare PT miss addresses with runtime pair table dump.

Reads:
  - pt_miss_full.txt: GRASP_PT_MISS lines from simulation log
  - bfs_1sm_rootcause_pair_table.csv: runtime pair table dump

Classifies each PT miss into:
  1. same_warp_has:   idx_addr found in same warp's pair table (timing boundary)
  2. other_warp_has:  idx_addr found in other warp's pair table (per-warp scope)
  3. nobody_has:      idx_addr not in any warp's pair table (addr_map not populated)
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

DIR = Path(__file__).resolve().parent

def load_pair_table(path):
    """Build idx_addr -> set(warp_id) mapping from runtime PT dump."""
    idx_to_warps = defaultdict(set)
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx_addr = int(row["idx_addr"], 16)
            warp_id = int(row["warp_id"])
            idx_to_warps[idx_addr].add(warp_id)
    return idx_to_warps

PT_MISS_RE = re.compile(
    r"GRASP_PT_MISS: sm=(\d+) warp=(\d+) sector=(0x[0-9a-f]+) "
    r"lane_addrs=\[([^\]]+)\] chains=\[([^\]]+)\]"
)

def parse_pt_miss(path):
    """Yield (warp_id, [lane_addrs]) from PT miss log."""
    with open(path) as f:
        for line in f:
            m = PT_MISS_RE.match(line.strip())
            if not m:
                continue
            warp_id = int(m.group(2))
            lane_addrs = [int(a.strip(), 16) for a in m.group(4).split(",")]
            yield warp_id, lane_addrs

def main():
    pt_path = DIR / "bfs_1sm_rootcause_pair_table.csv"
    miss_path = DIR / "pt_miss_full.txt"

    print(f"Loading pair table from {pt_path} ...")
    idx_to_warps = load_pair_table(pt_path)
    print(f"  Unique idx_addr entries: {len(idx_to_warps)}")

    same_warp = 0
    other_warp = 0
    nobody = 0
    total = 0

    for warp_id, lane_addrs in parse_pt_miss(miss_path):
        total += 1
        # Check if ANY lane_addr exists in the pair table
        found_same = False
        found_other = False
        for la in lane_addrs:
            warps = idx_to_warps.get(la)
            if warps is None:
                continue
            if warp_id in warps:
                found_same = True
                break  # best case
            else:
                found_other = True

        if found_same:
            same_warp += 1
        elif found_other:
            other_warp += 1
        else:
            nobody += 1

    print(f"\nPT miss cross-comparison results (total={total}):")
    print(f"  same_warp_has:  {same_warp:>7} ({100*same_warp/total:.1f}%)  — timing boundary")
    print(f"  other_warp_has: {other_warp:>7} ({100*other_warp/total:.1f}%)  — per-warp scope")
    print(f"  nobody_has:     {nobody:>7} ({100*nobody/total:.1f}%)  — addr_map not populated")

if __name__ == "__main__":
    main()
