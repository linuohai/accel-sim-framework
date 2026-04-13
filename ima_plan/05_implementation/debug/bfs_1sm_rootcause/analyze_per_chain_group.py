#!/usr/bin/env python3
"""Analyze GRASP metrics split by chain group.

Group A: chain 0-1 (idx_pc=0xc0, data_pc=0xf0/0x100)
Group B: chain 2-6 (idx_pc=0x1d0/0x640/0x9a0/0xd00/0x1060)

Uses:
  - GRASP trace CSV: link events via prb_id to determine chain group
  - L1 trace CSV: demand IMA stats per chain group
  - Root cause detail CSV: root cause distribution per chain group
"""

import csv
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

DIR = Path(__file__).resolve().parent

# Chain group definitions
CHAIN01_IDX_PCS = {0xc0}
CHAIN01_DATA_PCS = {0xf0, 0x100}
CHAIN26_IDX_PCS = {0x1d0, 0x640, 0x9a0, 0xd00, 0x1060}
CHAIN26_DATA_PCS = {0x200, 0x670, 0x9d0, 0xd30, 0x1090}

ALL_IDX_PCS = CHAIN01_IDX_PCS | CHAIN26_IDX_PCS
ALL_DATA_PCS = CHAIN01_DATA_PCS | CHAIN26_DATA_PCS


def parse_detail(detail_str):
    """Parse 'key=val;key=val' into dict."""
    d = {}
    for part in detail_str.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def classify_pc(pc_val, idx_pcs, data_pcs):
    """Return 'index', 'data', or None."""
    if pc_val in idx_pcs:
        return "index"
    if pc_val in data_pcs:
        return "data"
    return None


def analyze_l1_trace(path, label):
    """Count IMA demand stats from L1 trace, split by chain group."""
    stats = {
        "chain01": {"index": Counter(), "data": Counter()},
        "chain26": {"index": Counter(), "data": Counter()},
    }

    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pc_str = row["pc"]
            if pc_str == "NA":
                continue
            pc = int(pc_str, 16)
            status = row["l1_status"]
            is_pf = row.get("is_pf", "0")

            # Skip prefetch and FILL entries
            if is_pf == "1" or status == "FILL":
                continue

            # Determine chain group and role
            if pc in CHAIN01_IDX_PCS:
                group, role = "chain01", "index"
            elif pc in CHAIN01_DATA_PCS:
                group, role = "chain01", "data"
            elif pc in CHAIN26_IDX_PCS:
                group, role = "chain26", "index"
            elif pc in CHAIN26_DATA_PCS:
                group, role = "chain26", "data"
            else:
                continue

            # Skip RESERVATION_FAIL (matches shader.cc IMA_DEMAND logic)
            if status == "RESERVATION_FAIL":
                continue

            stats[group][role]["reads"] += 1
            if status == "HIT":
                stats[group][role]["hits"] += 1
            elif status == "HIT_RESERVED":
                stats[group][role]["hit_reserved"] += 1
            elif status in ("MISS", "SECTOR_MISS"):
                stats[group][role]["misses"] += 1

    print(f"\n=== L1 Trace IMA Demand: {label} ===")
    for group in ["chain01", "chain26"]:
        gname = "Chain 0-1" if group == "chain01" else "Chain 2-6"
        for role in ["index", "data"]:
            s = stats[group][role]
            r = s["reads"]
            if r == 0:
                print(f"  {gname} {role}: no reads")
                continue
            h = s["hits"]
            hr = s["hit_reserved"]
            m = s["misses"]
            print(f"  {gname} {role}: reads={r} hits={h}({100*h/r:.1f}%) "
                  f"hit_res={hr}({100*hr/r:.1f}%) misses={m}({100*m/r:.1f}%)")
    return stats


def analyze_grasp_trace(path):
    """Analyze GRASP pipeline funnel split by chain group via prb_id linking."""
    # Track prb_id -> chain group mapping
    # When IDX_PF_ENQUEUE happens with prb=X, record which group
    prb_group = {}  # prb_id -> "chain01" or "chain26"

    # Counters per group
    funnel = {
        "chain01": {
            "idx_enqueue": 0,
            "idx_l1_hit": 0, "idx_l1_miss": 0,
            "idx_l1_mshr": 0, "idx_l1_rfail": 0,
            "fill_dispatch": 0, "fill_targets0": 0, "fill_targets_pos": 0,
            "data_enqueue": 0,
            "data_l1_hit": 0, "data_l1_miss": 0,
            "data_l1_mshr": 0, "data_l1_rfail": 0,
        },
        "chain26": {
            "idx_enqueue": 0,
            "idx_l1_hit": 0, "idx_l1_miss": 0,
            "idx_l1_mshr": 0, "idx_l1_rfail": 0,
            "fill_dispatch": 0, "fill_targets0": 0, "fill_targets_pos": 0,
            "data_enqueue": 0,
            "data_l1_hit": 0, "data_l1_miss": 0,
            "data_l1_mshr": 0, "data_l1_rfail": 0,
        },
        "unknown": {
            "idx_enqueue": 0,
            "idx_l1_hit": 0, "idx_l1_miss": 0,
            "idx_l1_mshr": 0, "idx_l1_rfail": 0,
            "fill_dispatch": 0, "fill_targets0": 0, "fill_targets_pos": 0,
            "data_enqueue": 0,
            "data_l1_hit": 0, "data_l1_miss": 0,
            "data_l1_mshr": 0, "data_l1_rfail": 0,
        },
    }

    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            event = row["event"]
            detail = parse_detail(row.get("detail", ""))

            if event == "IDX_PF_ENQUEUE":
                pc = int(row["pc"], 16)
                prb_id_str = detail.get("prb")
                if prb_id_str is not None:
                    prb_id = int(prb_id_str)
                    if pc in CHAIN01_IDX_PCS:
                        prb_group[prb_id] = "chain01"
                    elif pc in CHAIN26_IDX_PCS:
                        prb_group[prb_id] = "chain26"
                    else:
                        prb_group[prb_id] = "unknown"

                group = "unknown"
                if pc in CHAIN01_IDX_PCS:
                    group = "chain01"
                elif pc in CHAIN26_IDX_PCS:
                    group = "chain26"
                funnel[group]["idx_enqueue"] += 1

            elif event == "IDX_PF_INJECT":
                prb_id = int(detail.get("prb_id", -1))
                group = prb_group.get(prb_id, "unknown")
                # INJECT is counted but we track result via L1_RESULT

            elif event.startswith("L1_RESULT_"):
                kind = detail.get("kind", "")
                prb_id_str = detail.get("prb_id")
                if prb_id_str is not None:
                    prb_id = int(prb_id_str)
                    group = prb_group.get(prb_id, "unknown")
                else:
                    group = "unknown"

                result = event.replace("L1_RESULT_", "")
                if kind == "INDEX":
                    if result == "HIT":
                        funnel[group]["idx_l1_hit"] += 1
                    elif result == "MISS":
                        funnel[group]["idx_l1_miss"] += 1
                    elif result == "MSHR":
                        funnel[group]["idx_l1_mshr"] += 1
                    elif result == "RFAIL":
                        funnel[group]["idx_l1_rfail"] += 1
                elif kind == "DATA":
                    if result == "HIT":
                        funnel[group]["data_l1_hit"] += 1
                    elif result == "MISS":
                        funnel[group]["data_l1_miss"] += 1
                    elif result == "MSHR":
                        funnel[group]["data_l1_mshr"] += 1
                    elif result == "RFAIL":
                        funnel[group]["data_l1_rfail"] += 1

            elif event == "FILL_DISPATCH":
                prb_id_str = detail.get("prb_id")
                if prb_id_str is not None:
                    prb_id = int(prb_id_str)
                    group = prb_group.get(prb_id, "unknown")
                else:
                    group = "unknown"

                funnel[group]["fill_dispatch"] += 1
                targets = int(detail.get("num_targets", 0))
                if targets == 0:
                    funnel[group]["fill_targets0"] += 1
                else:
                    funnel[group]["fill_targets_pos"] += 1

            elif event == "DATA_PF_ENQUEUE":
                chain_id_str = detail.get("chain_id")
                prb_id_str = detail.get("prb_id")
                # Use prb_id for group linkage
                group = "unknown"
                if prb_id_str is not None:
                    prb_id = int(prb_id_str)
                    group = prb_group.get(prb_id, "unknown")
                funnel[group]["data_enqueue"] += 1

    print("\n=== GRASP Pipeline Funnel by Chain Group ===")
    for group in ["chain01", "chain26", "unknown"]:
        f = funnel[group]
        gname = {"chain01": "Chain 0-1", "chain26": "Chain 2-6",
                 "unknown": "Unknown"}[group]

        idx_total = (f["idx_l1_hit"] + f["idx_l1_miss"] +
                     f["idx_l1_mshr"] + f["idx_l1_rfail"])
        data_total = (f["data_l1_hit"] + f["data_l1_miss"] +
                      f["data_l1_mshr"] + f["data_l1_rfail"])

        print(f"\n--- {gname} ---")
        print(f"  IDX_PF_ENQUEUE: {f['idx_enqueue']}")
        print(f"  Index PF L1 injection ({idx_total}):")
        print(f"    HIT={f['idx_l1_hit']}  MISS(issued)={f['idx_l1_miss']}  "
              f"RFAIL={f['idx_l1_rfail']}  MSHR={f['idx_l1_mshr']}")
        print(f"  FILL_DISPATCH: {f['fill_dispatch']}  "
              f"(targets=0: {f['fill_targets0']}, targets>0: {f['fill_targets_pos']})")
        print(f"  DATA_PF_ENQUEUE: {f['data_enqueue']}")
        print(f"  Data PF L1 injection ({data_total}):")
        print(f"    HIT={f['data_l1_hit']}  MISS(issued)={f['data_l1_miss']}  "
              f"RFAIL={f['data_l1_rfail']}  MSHR={f['data_l1_mshr']}")

    return funnel


def analyze_rootcause(path):
    """Split root cause detail by chain group."""
    rc_counts = {"chain01": Counter(), "chain26": Counter()}

    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pc = int(row["pc"], 16)
            rc = row["root_cause"]
            if pc in CHAIN01_DATA_PCS:
                rc_counts["chain01"][rc] += 1
            elif pc in CHAIN26_DATA_PCS:
                rc_counts["chain26"][rc] += 1

    print("\n=== Root Cause Distribution by Chain Group ===")
    for group in ["chain01", "chain26"]:
        gname = "Chain 0-1" if group == "chain01" else "Chain 2-6"
        total = sum(rc_counts[group].values())
        print(f"\n--- {gname} (total={total}) ---")
        for rc, cnt in rc_counts[group].most_common():
            print(f"  {rc:<25s} {cnt:>7d} ({100*cnt/total:.1f}%)")

    return rc_counts


def main():
    grasp_l1 = DIR / "bfs_1sm_rootcause_l1.csv"
    baseline_l1 = DIR / "baseline" / "bfs_1sm_baseline_l1.csv"
    grasp_trace = DIR / "bfs_1sm_rootcause_grasp.csv"
    detail_csv = DIR / "bfs_1sm_rootcause_detail.csv"

    # 1. L1 trace IMA demand
    if baseline_l1.exists():
        analyze_l1_trace(baseline_l1, "Baseline")
    analyze_l1_trace(grasp_l1, "GRASP")

    # 2. Pipeline funnel
    analyze_grasp_trace(grasp_trace)

    # 3. Root cause
    analyze_rootcause(detail_csv)


if __name__ == "__main__":
    main()
