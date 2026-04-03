#!/usr/bin/env python3
"""GRASP data miss root cause analysis.

Cross-references three data sources to classify every IMA data demand miss:
  1. Pair table CSV (ground truth: idx_addr → data_addr)
  2. L1 trace CSV (demand miss events)
  3. GRASP event trace CSV (prefetch pipeline events)

Usage:
  python analyze_data_miss_rootcause.py \
    --pair-table result/grasp_trace/bfs_1sm_rootcause_pair_table.csv \
    --l1-trace   result/L1cache_trace/bfs_1sm_rootcause_l1.csv \
    --grasp-trace result/grasp_trace/bfs_1sm_rootcause_grasp.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECTOR_SIZE = 32
SECTOR_MASK = ~(SECTOR_SIZE - 1)

# Default BFS chain PCs (override via --data-pcs / --index-pcs)
DEFAULT_DATA_PCS = "0x0200,0x0670,0x09d0,0x0d30,0x1090"
DEFAULT_INDEX_PCS = "0x01d0,0x0640,0x09a0,0x0d00,0x1060"

# Root cause categories
RC_NOT_IN_TABLE = "NOT_IN_PAIR_TABLE"
RC_STRIDE_NOT_CONVERGED = "STRIDE_NOT_CONVERGED"
RC_IDX_NOT_TRIGGERED = "IDX_NOT_TRIGGERED"
RC_IDX_RFAIL = "IDX_PF_RFAIL"
RC_IDX_PENDING = "IDX_PF_PENDING"
RC_PT_MISS = "PT_MISS"
RC_DATA_THROTTLED = "DATA_PF_THROTTLED"
RC_DATA_RFAIL = "DATA_PF_RFAIL"
RC_DATA_PENDING = "DATA_PF_PENDING"
RC_EVICTED = "EVICTED"
RC_UNKNOWN = "UNKNOWN"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DataMiss:
    cycle: int
    warp_id: int
    lane_id: int
    data_addr: int
    pc: int
    root_cause: str = RC_UNKNOWN
    evidence: str = ""


@dataclass
class GraspEvent:
    cycle: int
    sm_id: int
    warp_id: int
    event: str
    pc: int
    addr: int
    detail: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def parse_addr(s: str) -> int:
    """Parse hex or decimal address string."""
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    return int(s)


def load_pair_table(path: str) -> Tuple[dict, dict]:
    """Load ground truth pair table CSV.

    Returns:
        forward: (chain_id, idx_addr) → data_addr
        reverse: (data_sector, warp_id) → [(chain_id, idx_addr, idx_pc, data_pc)]
            Per-warp reverse map keyed by sector-aligned data address
            (L1 trace records sector addresses, pair table has byte addresses)
    """
    forward: Dict[Tuple[int, int], int] = {}
    reverse: Dict[Tuple[int, int], List[Tuple[int, int, int]]] = defaultdict(list)
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            chain_id = int(row["chain_id"])
            warp_id = int(row["warp_id"])
            idx_addr = parse_addr(row["idx_addr"])
            data_addr = parse_addr(row["data_addr"])
            idx_pc = parse_addr(row["idx_pc"])
            forward[(chain_id, idx_addr)] = data_addr
            data_pc = parse_addr(row["data_pc"])
            data_sector = data_addr & SECTOR_MASK
            reverse[(data_sector, warp_id)].append((chain_id, idx_addr, idx_pc, data_pc))
    return forward, reverse


def load_data_misses(path: str, data_pcs: Set[int]) -> List[DataMiss]:
    """Extract data demand misses from L1 trace CSV."""
    misses = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pc_str = row["pc"].strip()
            if pc_str == "NA":
                continue
            pc = parse_addr(pc_str)
            if pc not in data_pcs:
                continue
            status = row["l1_status"].strip()
            if status not in ("MISS", "SECTOR_MISS"):
                continue
            # Skip prefetch accesses (is_pf=1)
            if row.get("is_pf", "0").strip() == "1":
                continue
            misses.append(
                DataMiss(
                    cycle=int(row["cycle"]),
                    warp_id=int(row["warp_id"]),
                    lane_id=int(row["lane_id"]),
                    data_addr=parse_addr(row["address"]),
                    pc=pc,
                )
            )
    return misses


def load_grasp_events(path: str) -> List[GraspEvent]:
    """Load GRASP event trace CSV."""
    events = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            detail = {}
            detail_str = row.get("detail", "").strip()
            if detail_str:
                for kv in detail_str.split(";"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        detail[k.strip()] = v.strip()
            events.append(
                GraspEvent(
                    cycle=int(row["cycle"]),
                    sm_id=int(row["sm_id"]),
                    warp_id=int(row["warp_id"]),
                    event=row["event"].strip(),
                    pc=parse_addr(row["pc"]) if row["pc"].strip() != "0" else 0,
                    addr=parse_addr(row["addr"]),
                    detail=detail,
                )
            )
    return events


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------


def build_event_indices(events: List[GraspEvent]):
    """Build lookup indices from GRASP events for fast querying.

    Returns:
        by_warp_event: (warp_id, event_type) → [GraspEvent] sorted by cycle
        stride_converge: idx_pc → [cycle]  # earliest cycle where stride_valid=1 observed
        idx_enqueue_by_addr: (warp_id, sector_addr) → [GraspEvent]
        fill_dispatch_by_addr: sector_addr → [GraspEvent]
        data_enqueue_by_addr: sector_addr → [GraspEvent]
    """
    by_warp_event = defaultdict(list)
    stride_converge = defaultdict(list)
    idx_enqueue_by_addr = defaultdict(list)
    idx_inject_by_addr = defaultdict(list)
    l1_result_by_addr = defaultdict(list)
    fill_dispatch_by_addr = defaultdict(list)
    data_enqueue_by_addr = defaultdict(list)

    for e in events:
        by_warp_event[(e.warp_id, e.event)].append(e)
        if e.event == "STRIDE_CONVERGE":
            stride_converge[e.pc].append(e.cycle)
        elif e.event == "DEMAND_CT_HIT":
            # Fallback: stride may converge speculatively during CT_INSERT
            # without emitting STRIDE_CONVERGE.  Use stride_valid=1 from
            # DEMAND_CT_HIT as evidence of convergence.
            if e.detail.get("stride_valid") == "1":
                stride_converge[e.pc].append(e.cycle)
        elif e.event == "IDX_PF_ENQUEUE":
            sector = e.addr & SECTOR_MASK
            idx_enqueue_by_addr[(e.warp_id, sector)].append(e)
        elif e.event == "IDX_PF_INJECT":
            sector = e.addr & SECTOR_MASK
            idx_inject_by_addr[(e.warp_id, sector)].append(e)
        elif e.event.startswith("L1_RESULT_"):
            sector = e.addr & SECTOR_MASK
            l1_result_by_addr[sector].append(e)
        elif e.event == "FILL_DISPATCH":
            sector = e.addr & SECTOR_MASK
            fill_dispatch_by_addr[sector].append(e)
        elif e.event == "DATA_PF_ENQUEUE":
            sector = e.addr & SECTOR_MASK
            data_enqueue_by_addr[sector].append(e)

    return {
        "by_warp_event": by_warp_event,
        "stride_converge": stride_converge,
        "idx_enqueue": idx_enqueue_by_addr,
        "idx_inject": idx_inject_by_addr,
        "l1_result": l1_result_by_addr,
        "fill_dispatch": fill_dispatch_by_addr,
        "data_enqueue": data_enqueue_by_addr,
    }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_miss(
    miss: DataMiss,
    reverse_map: Dict[int, List[Tuple[int, int, int]]],
    indices: dict,
) -> str:
    """Classify a single data miss root cause.

    Traces back through the GRASP pipeline:
      1. Reverse lookup: data_addr → (chain_id, idx_addr, idx_pc)
      2. Was stride converged before this miss? (per-CT, SM-wide)
      3. Was an index PF enqueued for idx_addr's sector?
      4. Was the index PF injected? What L1 result?
      5. Was a fill dispatch triggered? Did pair table hit?
      6. Was a data PF enqueued for data_addr's sector?
      7. Was the data PF injected? What L1 result?
    """
    D = miss.data_addr
    warp = miss.warp_id
    miss_cycle = miss.cycle

    # --- Step 1: Reverse lookup (per-warp pair table, sector-aligned) ---
    data_sector = D & SECTOR_MASK
    key = (data_sector, warp)
    if key not in reverse_map:
        miss.evidence = f"data_addr=0x{D:x} sector=0x{data_sector:x} warp={warp} not in pair table"
        return RC_NOT_IN_TABLE

    # Filter by demand data PC to pick the correct chain (avoid ghost entries
    # from merged pair tables where the same data_addr appears under multiple chains).
    demand_pc = miss.pc
    candidates = [e for e in reverse_map[key] if e[3] == demand_pc]
    if not candidates:
        # Fallback: use first entry (may be cross-chain, but still valid for analysis)
        candidates = reverse_map[key]
    chain_id, idx_addr, idx_pc, _data_pc = candidates[0]
    idx_sector = idx_addr & SECTOR_MASK
    data_sector = D & SECTOR_MASK

    # --- Step 2: Stride convergence (CT is per-SM, check by index PC) ---
    converge_cycles = indices["stride_converge"].get(idx_pc, [])
    converged_before = any(c <= miss_cycle for c in converge_cycles)
    if not converged_before:
        miss.evidence = (
            f"chain={chain_id} idx_pc=0x{idx_pc:x} "
            f"no stride_valid=1 (STRIDE_CONVERGE or DEMAND_CT_HIT) before cycle {miss_cycle}"
        )
        return RC_STRIDE_NOT_CONVERGED

    # --- Step 3: Index PF enqueued? ---
    idx_enq = indices["idx_enqueue"].get((warp, idx_sector), [])
    # Find most recent enqueue before miss
    relevant_enq = [e for e in idx_enq if e.cycle < miss_cycle]
    if not relevant_enq:
        miss.evidence = (
            f"chain={chain_id} idx_sector=0x{idx_sector:x} "
            f"no IDX_PF_ENQUEUE before cycle {miss_cycle}"
        )
        return RC_IDX_NOT_TRIGGERED

    last_enq = relevant_enq[-1]

    # --- Step 4: Index PF injected? ---
    idx_inj = indices["idx_inject"].get((warp, idx_sector), [])
    relevant_inj = [e for e in idx_inj if last_enq.cycle <= e.cycle < miss_cycle]
    if not relevant_inj:
        # Enqueued but not yet injected
        miss.evidence = (
            f"chain={chain_id} idx_sector=0x{idx_sector:x} "
            f"IDX_ENQ@{last_enq.cycle} but no IDX_INJ before {miss_cycle}"
        )
        return RC_IDX_PENDING

    last_inj = relevant_inj[-1]

    # Check L1 result for index PF
    l1_results = indices["l1_result"].get(idx_sector, [])
    idx_l1 = [
        e
        for e in l1_results
        if last_inj.cycle <= e.cycle < miss_cycle
        and e.detail.get("kind") == "INDEX"
    ]
    if idx_l1 and idx_l1[0].event == "L1_RESULT_RFAIL":
        miss.evidence = (
            f"chain={chain_id} idx_sector=0x{idx_sector:x} "
            f"IDX_INJ@{last_inj.cycle} → L1_RFAIL@{idx_l1[0].cycle}"
        )
        return RC_IDX_RFAIL

    # --- Step 5: Fill dispatch? ---
    fills = indices["fill_dispatch"].get(idx_sector, [])
    relevant_fills = [e for e in fills if last_inj.cycle <= e.cycle < miss_cycle]
    if not relevant_fills:
        # Index PF injected but no fill yet → still pending
        miss.evidence = (
            f"chain={chain_id} idx_sector=0x{idx_sector:x} "
            f"IDX_INJ@{last_inj.cycle} no FILL_DISPATCH before {miss_cycle}"
        )
        return RC_IDX_PENDING

    last_fill = relevant_fills[-1]
    # Check pair table hit/miss via pair_hits in IDX_PF_INJECT detail
    pair_hits = int(last_inj.detail.get("pair_hits", "0"))
    if pair_hits == 0:
        miss.evidence = (
            f"chain={chain_id} idx_sector=0x{idx_sector:x} "
            f"IDX_INJ@{last_inj.cycle} pair_hits=0 → PT_MISS"
        )
        return RC_PT_MISS

    # --- Step 6: Data PF enqueued? ---
    data_enq = indices["data_enqueue"].get(data_sector, [])
    relevant_data_enq = [
        e for e in data_enq if last_fill.cycle <= e.cycle < miss_cycle
    ]
    if not relevant_data_enq:
        miss.evidence = (
            f"chain={chain_id} data_sector=0x{data_sector:x} "
            f"FILL@{last_fill.cycle} but no DATA_ENQ before {miss_cycle}"
        )
        # Could be throttled or PT miss for specific address
        return RC_DATA_THROTTLED

    # --- Step 7: Data PF result ---
    data_l1 = [
        e
        for e in indices["l1_result"].get(data_sector, [])
        if relevant_data_enq[0].cycle <= e.cycle < miss_cycle
        and e.detail.get("kind") == "DATA"
    ]
    if data_l1:
        if data_l1[0].event == "L1_RESULT_RFAIL":
            miss.evidence = (
                f"chain={chain_id} data_sector=0x{data_sector:x} "
                f"DATA_ENQ@{relevant_data_enq[0].cycle} → L1_RFAIL@{data_l1[0].cycle}"
            )
            return RC_DATA_RFAIL
        if data_l1[0].event in ("L1_RESULT_HIT", "L1_RESULT_MISS"):
            # PF was issued and got a result, but demand still missed →
            # data was filled then evicted before demand arrived
            miss.evidence = (
                f"chain={chain_id} data_sector=0x{data_sector:x} "
                f"DATA L1_{data_l1[0].event}@{data_l1[0].cycle} "
                f"but demand MISS@{miss_cycle} → evicted"
            )
            return RC_EVICTED

    # Data PF enqueued but no L1 result yet → still in flight
    miss.evidence = (
        f"chain={chain_id} data_sector=0x{data_sector:x} "
        f"DATA_ENQ@{relevant_data_enq[0].cycle} no L1 result before {miss_cycle}"
    )
    return RC_DATA_PENDING


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="GRASP data miss root cause analysis"
    )
    parser.add_argument(
        "--pair-table", required=True, help="Pair table CSV (ground truth)"
    )
    parser.add_argument("--l1-trace", required=True, help="L1 trace CSV")
    parser.add_argument(
        "--grasp-trace", required=True, help="GRASP event trace CSV"
    )
    parser.add_argument(
        "--data-pcs",
        default=DEFAULT_DATA_PCS,
        help="Comma-separated data load PCs (hex)",
    )
    parser.add_argument(
        "--index-pcs",
        default=DEFAULT_INDEX_PCS,
        help="Comma-separated index load PCs (hex)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output detailed CSV (default: print summary only)",
    )
    args = parser.parse_args()

    data_pcs = set(int(x, 16) for x in args.data_pcs.split(","))
    index_pcs = set(int(x, 16) for x in args.index_pcs.split(","))

    # --- Load data ---
    print("Loading pair table...", file=sys.stderr)
    forward, reverse = load_pair_table(args.pair_table)
    print(
        f"  Forward entries: {len(forward)}, "
        f"Reverse entries (data_sector, warp_id): {len(reverse)}",
        file=sys.stderr,
    )

    print("Loading L1 trace...", file=sys.stderr)
    misses = load_data_misses(args.l1_trace, data_pcs)
    print(f"  Data demand misses: {len(misses)}", file=sys.stderr)

    print("Loading GRASP events...", file=sys.stderr)
    events = load_grasp_events(args.grasp_trace)
    print(f"  Total events: {len(events)}", file=sys.stderr)

    # --- Coverage sanity check ---
    # Check that every (data_addr, warp_id) from L1 trace has a pair table entry
    data_pairs_in_l1 = set()
    with open(args.l1_trace) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pc_str = row["pc"].strip()
            if pc_str == "NA":
                continue
            pc = parse_addr(pc_str)
            if pc in data_pcs and row.get("is_pf", "0").strip() != "1":
                data_pairs_in_l1.add(
                    (parse_addr(row["address"]), int(row["warp_id"]))
                )
    not_in_table = data_pairs_in_l1 - set(reverse.keys())
    if not_in_table:
        print(
            f"  WARNING: {len(not_in_table)}/{len(data_pairs_in_l1)} "
            f"(data_addr, warp_id) pairs NOT in pair table",
            file=sys.stderr,
        )

    # --- Build indices ---
    print("Building event indices...", file=sys.stderr)
    indices = build_event_indices(events)

    # --- Classify each miss ---
    print("Classifying misses...", file=sys.stderr)
    for miss in misses:
        miss.root_cause = classify_miss(miss, reverse, indices)

    # --- Summary ---
    counts = Counter(m.root_cause for m in misses)
    total = len(misses)
    print(f"\n=== Data Miss Root Cause Summary ({total} misses) ===")
    print(f"{'Root Cause':<30s} {'Count':>6s} {'Pct':>7s}")
    print("-" * 45)
    for cause, count in counts.most_common():
        pct = 100 * count / total if total > 0 else 0
        print(f"{cause:<30s} {count:>6d} {pct:>6.1f}%")

    # --- Detailed CSV output ---
    if args.output:
        out_path = Path(args.output)
        with open(out_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "cycle",
                    "warp_id",
                    "lane_id",
                    "data_addr",
                    "pc",
                    "root_cause",
                    "evidence",
                ]
            )
            for m in sorted(misses, key=lambda x: x.cycle):
                writer.writerow(
                    [
                        m.cycle,
                        m.warp_id,
                        m.lane_id,
                        f"0x{m.data_addr:x}",
                        f"0x{m.pc:x}",
                        m.root_cause,
                        m.evidence,
                    ]
                )
        print(f"\nDetailed results → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
