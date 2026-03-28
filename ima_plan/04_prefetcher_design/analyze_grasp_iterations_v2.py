#!/usr/bin/env python3
"""Per-iteration analysis of GRASP prefetcher behavior — generalized version.

Unlike the tiny_case-specific v1, this version reads IMA chain PCs from
a chain CSV file instead of using hardcoded constants.

Produces output formats:
  summary   - Per-iteration summary table (txt + csv)
  timeline  - Detailed chronological event stream per iteration (txt)
  compare   - Baseline vs GRASP side-by-side comparison (txt)

An analysis_log.txt is always generated alongside the selected formats.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# PC Configuration (replaces hardcoded constants from v1)
# ---------------------------------------------------------------------------


@dataclass
class PcConfig:
    """Holds the set of PCs that identify IMA chain roles."""

    index_pcs: Set[int]
    data_pcs: Set[int]
    boundary_pcs: Set[int]  # subset of index_pcs for iteration boundary detection
    warmup_pc: Optional[int] = None
    tail_pcs: Set[int] = field(default_factory=set)
    labels: Dict[int, str] = field(default_factory=dict)

    @property
    def all_pcs(self) -> Set[int]:
        s = self.index_pcs | self.data_pcs | self.tail_pcs
        if self.warmup_pc is not None:
            s.add(self.warmup_pc)
        return s

    def label(self, pc: int) -> str:
        return self.labels.get(pc, f"0x{pc:03X}")


def load_chain_pcs(
    chain_csv: Path, algorithm: Optional[str] = None
) -> Tuple[Set[int], Set[int], Dict[int, str]]:
    """Read chain CSV, return (index_pcs, data_pcs, auto_labels)."""
    index_pcs: Set[int] = set()
    data_pcs: Set[int] = set()
    labels: Dict[int, str] = {}

    with open(chain_csv, newline="") as f:
        for row in csv.DictReader(f):
            if algorithm and row.get("algorithm", "") != algorithm:
                continue
            idx_pc = int(row["index_pc"], 16)
            dat_pc = int(row["data_pc"], 16)
            index_pcs.add(idx_pc)
            data_pcs.add(dat_pc)

            # Auto-generate labels from source info
            if idx_pc not in labels:
                src = row.get("index_source_file", "")
                line = row.get("index_source_line", "")
                if src:
                    labels[idx_pc] = f"idx@{Path(src).name}:{line}"
                else:
                    labels[idx_pc] = f"idx_{idx_pc:#05x}"
            if dat_pc not in labels:
                src = row.get("data_source_file", "")
                line = row.get("data_source_line", "")
                if src:
                    labels[dat_pc] = f"dat@{Path(src).name}:{line}"
                else:
                    labels[dat_pc] = f"dat_{dat_pc:#05x}"

    return index_pcs, data_pcs, labels


# ---------------------------------------------------------------------------
# Status Constants
# ---------------------------------------------------------------------------

MISS_STATUSES = {"MISS", "SECTOR_MISS"}
HIT_STATUSES = {"HIT"}
HITRES_STATUSES = {"HIT_RESERVED"}
RFAIL_STATUSES = {"RESERVATION_FAIL"}
FILL_STATUS = "FILL"

EVENT_ABBREV = {
    "CT_INSERT": "CT_INS",
    "DEMAND_CT_HIT": "CT_HIT",
    "STRIDE_UPDATE": "STR_UPD",
    "CHAIN_DETECT": "CD",
    "STRIDE_CONVERGE": "STR_CONV",
    "IDX_PF_ENQUEUE": "IDX_ENQ",
    "IDX_PF_INJECT": "IDX_INJ",
    "DATA_PF_ENQUEUE": "DAT_ENQ",
    "DATA_PF_INJECT": "DAT_INJ",
    "FILL_DISPATCH": "FILL_D",
    "L1_RESULT_HIT": "L1_HIT",
    "L1_RESULT_MISS": "L1_MISS",
    "L1_RESULT_RFAIL": "L1_RFAIL",
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class L1Event:
    cycle: int
    warp_id: int
    lane_id: int
    address: int
    l1_status: str
    pc: int


@dataclass
class GraspEvent:
    cycle: int
    warp_id: int
    event: str
    pc: int
    addr: int
    detail: str
    detail_dict: Dict[str, str] = field(default_factory=dict)


@dataclass
class DemandAccess:
    """A grouped demand access (one logical load instruction for one warp)."""

    pc: int
    role: str  # "index" or "data"
    first_cycle: int
    lane_statuses: Dict[int, List[str]] = field(default_factory=lambda: defaultdict(list))
    fill_cycles: Dict[int, int] = field(default_factory=dict)
    all_events: List[L1Event] = field(default_factory=list)

    @property
    def last_served_cycle(self) -> int:
        candidates = []
        for ev in self.all_events:
            if ev.l1_status == FILL_STATUS:
                candidates.append(ev.cycle)
            elif ev.l1_status in HIT_STATUSES | HITRES_STATUSES:
                candidates.append(ev.cycle)
        if not candidates:
            candidates = [ev.cycle for ev in self.all_events]
        return max(candidates) if candidates else self.first_cycle


@dataclass
class Iteration:
    iter_num: int
    warp_id: int
    index_access: Optional[DemandAccess]
    data_access: Optional[DemandAccess]
    grasp_events: List[GraspEvent] = field(default_factory=list)

    @property
    def idx_cycle(self) -> Optional[int]:
        return self.index_access.first_cycle if self.index_access else None

    @property
    def data_cycle(self) -> Optional[int]:
        return self.data_access.first_cycle if self.data_access else None

    @property
    def idx_to_data_latency(self) -> Optional[int]:
        if self.index_access is None or self.data_access is None:
            return None
        return self.data_access.last_served_cycle - self.index_access.first_cycle


# ---------------------------------------------------------------------------
# CSV Parsing
# ---------------------------------------------------------------------------


def parse_l1_trace(
    path: Path, warps: Set[int], pc_config: PcConfig
) -> Dict[int, List[L1Event]]:
    relevant_pcs = pc_config.all_pcs
    result: Dict[int, List[L1Event]] = defaultdict(list)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            wid = int(row["warp_id"])
            if wid not in warps:
                continue
            if row["op"] != "LD":
                continue
            pc = int(row["pc"], 16)
            if pc not in relevant_pcs:
                continue
            ev = L1Event(
                cycle=int(row["cycle"]),
                warp_id=wid,
                lane_id=int(row["lane_id"]),
                address=int(row["address"], 16),
                l1_status=row["l1_status"],
                pc=pc,
            )
            result[wid].append(ev)
    return result


def parse_grasp_trace(path: Path, warps: Set[int]) -> Dict[int, List[GraspEvent]]:
    result: Dict[int, List[GraspEvent]] = defaultdict(list)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            wid = int(row["warp_id"])
            if wid not in warps:
                continue
            detail = row.get("detail", "")
            detail_dict = {}
            if detail:
                for kv in detail.split(";"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        detail_dict[k.strip()] = v.strip()
            ev = GraspEvent(
                cycle=int(row["cycle"]),
                warp_id=wid,
                event=row["event"],
                pc=int(row["pc"], 16) if row["pc"] else 0,
                addr=int(row["addr"], 16) if row["addr"] else 0,
                detail=detail,
                detail_dict=detail_dict,
            )
            result[wid].append(ev)
    return result


# ---------------------------------------------------------------------------
# Iteration Detection
# ---------------------------------------------------------------------------


def find_iteration_boundaries(
    l1_events: List[L1Event], pc_config: PcConfig,
    merge_window: int = 0,
) -> List[Tuple[int, int]]:
    """Return (cycle, address) for each IMA iteration start.

    Collects every non-FILL boundary-PC event in chronological order,
    deduplicates per-sector events within the same cycle (multi-lane coalescing),
    then merges events within *merge_window* cycles (multi-sector from the same
    warp instruction).

    Unlike the previous implementation, this does NOT globally deduplicate by
    sector address — the same sector can appear in multiple iterations (e.g.,
    BFS worklist elements in the same cache line across iterations).
    """
    # Collect (cycle, address) for each boundary-PC non-FILL event,
    # dedup by (cycle, sector) to collapse multi-lane events in the same cycle.
    SECTOR_MASK = ~0x1F  # 32B sector
    seen_cycle_sector: set = set()
    raw: List[Tuple[int, int]] = []
    for ev in l1_events:
        if ev.pc not in pc_config.boundary_pcs:
            continue
        if ev.l1_status == FILL_STATUS:
            continue
        sector = ev.address & SECTOR_MASK
        key = (ev.cycle, sector)
        if key in seen_cycle_sector:
            continue
        seen_cycle_sector.add(key)
        raw.append((ev.cycle, sector))

    raw.sort(key=lambda x: x[0])

    if not raw:
        return []
    if merge_window <= 0:
        return raw

    # Merge boundaries within merge_window cycles
    merged: List[Tuple[int, int]] = []
    group_start_cycle = raw[0][0]
    group_sector = raw[0][1]
    for cyc, sector in raw:
        if cyc - group_start_cycle <= merge_window:
            continue  # same warp instruction, skip
        merged.append((group_start_cycle, group_sector))
        group_start_cycle = cyc
        group_sector = sector
    merged.append((group_start_cycle, group_sector))
    return merged


def find_tail_start(
    l1_events: List[L1Event], pc_config: PcConfig
) -> Optional[int]:
    if not pc_config.tail_pcs:
        return None
    for ev in l1_events:
        if ev.pc in pc_config.tail_pcs and ev.lane_id == 0 and ev.l1_status != FILL_STATUS:
            return ev.cycle
    return None


def build_fill_lookup(
    l1_events: List[L1Event],
) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
    lookup: Dict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
    for ev in l1_events:
        if ev.l1_status == FILL_STATUS:
            lookup[(ev.warp_id, ev.address)].append((ev.cycle, ev.lane_id))
    for key in lookup:
        lookup[key].sort()
    return lookup


def group_demand_access(
    events: List[L1Event],
    role: str,
    fill_lookup: Dict[Tuple[int, int], List[Tuple[int, int]]],
    warp_id: int,
) -> Optional[DemandAccess]:
    if not events:
        return None
    non_fill = [e for e in events if e.l1_status != FILL_STATUS]
    if not non_fill:
        return None

    first_cycle = min(e.cycle for e in non_fill)
    da = DemandAccess(pc=non_fill[0].pc, role=role, first_cycle=first_cycle)
    da.all_events = sorted(events, key=lambda e: e.cycle)

    for ev in non_fill:
        da.lane_statuses[ev.lane_id].append(ev.l1_status)

    for ev in [e for e in events if e.l1_status == FILL_STATUS]:
        da.fill_cycles[ev.lane_id] = ev.cycle

    for ev in non_fill:
        if ev.l1_status in MISS_STATUSES and ev.lane_id not in da.fill_cycles:
            key = (warp_id, ev.address)
            for fc, fl in fill_lookup.get(key, []):
                if fc > ev.cycle:
                    da.fill_cycles[ev.lane_id] = fc
                    fill_ev = L1Event(
                        cycle=fc, warp_id=warp_id, lane_id=fl,
                        address=ev.address, l1_status=FILL_STATUS, pc=ev.pc,
                    )
                    da.all_events.append(fill_ev)
                    break
    da.all_events.sort(key=lambda e: e.cycle)
    return da


def detect_iterations(
    l1_events: List[L1Event],
    grasp_events: List[GraspEvent],
    warp_id: int,
    pc_config: PcConfig,
    merge_window: int = 0,
) -> List[Iteration]:
    boundaries = find_iteration_boundaries(l1_events, pc_config, merge_window)
    if not boundaries:
        return []

    tail_start = find_tail_start(l1_events, pc_config)
    fill_lookup = build_fill_lookup(l1_events)

    windows: List[Tuple[int, int]] = []
    for i, (cyc, _addr) in enumerate(boundaries):
        if i + 1 < len(boundaries):
            end = boundaries[i + 1][0]
        elif tail_start is not None:
            end = tail_start
        else:
            end = max(e.cycle for e in l1_events) + 1
        windows.append((cyc, end))

    iterations: List[Iteration] = []
    for i, (start, end) in enumerate(windows):
        idx_events = [
            e for e in l1_events
            if e.pc in pc_config.index_pcs and start <= e.cycle < end
        ]
        data_events = [
            e for e in l1_events
            if e.pc in pc_config.data_pcs and start <= e.cycle < end
        ]

        idx_access = group_demand_access(idx_events, "index", fill_lookup, warp_id)
        data_access = group_demand_access(data_events, "data", fill_lookup, warp_id)

        g_events = [ge for ge in grasp_events if start <= ge.cycle < end]

        iterations.append(
            Iteration(
                iter_num=i, warp_id=warp_id,
                index_access=idx_access, data_access=data_access,
                grasp_events=g_events,
            )
        )
    return iterations


# ---------------------------------------------------------------------------
# Format Helpers
# ---------------------------------------------------------------------------


def summarize_l1(access: Optional[DemandAccess]) -> str:
    if access is None:
        return "N/A"
    counter: Counter = Counter()
    for lane_id, statuses in access.lane_statuses.items():
        final = statuses[-1] if statuses else "?"
        if final in MISS_STATUSES:
            counter["MISS"] += 1
        elif final in HIT_STATUSES:
            counter["HIT"] += 1
        elif final in HITRES_STATUSES:
            counter["HIT_RES"] += 1
        elif final in RFAIL_STATUSES:
            counter["RFAIL"] += 1
        else:
            counter[final] += 1
    n_lanes = len(access.lane_statuses)
    parts = [f"{cnt}x{st}" for st, cnt in counter.most_common()]
    status_str = ",".join(parts) if parts else "?"
    return f"[{n_lanes}L] {status_str}"


def summarize_grasp(events: List[GraspEvent]) -> str:
    if not events:
        return "-"
    counter = Counter(e.event for e in events)
    parts = []
    for etype, cnt in counter.most_common():
        abbr = EVENT_ABBREV.get(etype, etype[:8])
        if cnt == 1:
            parts.append(abbr)
        else:
            parts.append(f"{abbr}x{cnt}")
    return "; ".join(parts)


def format_detail_brief(gev: GraspEvent) -> str:
    d = gev.detail_dict
    etype = gev.event
    if etype == "DEMAND_CT_HIT":
        return f"stride_valid={d.get('stride_valid', '?')} iter_stride={d.get('iter_stride', '?')}"
    elif etype == "STRIDE_UPDATE":
        return f"delta={d.get('delta', '?')} stride_valid={d.get('stride_valid', '?')}"
    elif etype == "STRIDE_CONVERGE":
        return f"stride={d.get('stride', '?')}"
    elif etype == "CHAIN_DETECT":
        return f"idx_pc={d.get('idx_pc', '?')} data_pc={d.get('data_pc', '?')} ct_idx={d.get('ct_idx', '?')}"
    elif etype == "CT_INSERT":
        return f"idx_pc={d.get('idx_pc', '?')} data_pc={d.get('data_pc', '?')} ct_new={d.get('ct_new', '?')}"
    elif etype == "IDX_PF_ENQUEUE":
        return ""
    elif etype == "IDX_PF_INJECT":
        prb = d.get("prb_id", "")
        return f"prb={prb}" if prb else ""
    elif etype == "DATA_PF_ENQUEUE":
        return f"chain={d.get('chain_id', '?')} prb={d.get('prb_id', '?')}"
    elif etype == "DATA_PF_INJECT":
        return ""
    elif etype == "FILL_DISPATCH":
        return f"prb={d.get('prb_id', '?')} targets={d.get('num_targets', '?')}"
    elif etype.startswith("L1_RESULT"):
        return f"kind={d.get('kind', '?')}"
    return ""


# ---------------------------------------------------------------------------
# Format A: Summary Table
# ---------------------------------------------------------------------------


def write_format_a(
    iterations: List[Iteration], out_dir: Path, warp_id: int, pc_config: PcConfig
):
    n = len(iterations)
    txt_path = out_dir / f"format_a_warp{warp_id}.txt"
    csv_path = out_dir / f"format_a_warp{warp_id}.csv"

    lines: List[str] = []
    lines.append(f"=== Warp {warp_id}, IMA region ({n} iterations) ===\n")
    hdr = (
        f"{'iter':>4} | {'idx_cycle':>9} | {'idx_L1':>20} | {'data_cycle':>10} "
        f"| {'data_L1':>25} | {'grasp_summary':>45} | {'latency':>7}"
    )
    lines.append(hdr)
    lines.append("-" * len(hdr))

    csv_rows: List[Dict] = []
    total_latency = 0
    count_latency = 0
    idx_hit_count = 0
    idx_total = 0
    data_hit_count = 0
    data_total = 0

    for it in iterations:
        idx_cyc = it.idx_cycle if it.idx_cycle is not None else 0
        data_cyc = it.data_cycle if it.data_cycle is not None else 0
        idx_summary = summarize_l1(it.index_access)
        data_summary = summarize_l1(it.data_access)
        grasp_summary = summarize_grasp(it.grasp_events)
        latency = it.idx_to_data_latency
        lat_str = str(latency) if latency is not None else "N/A"

        line = (
            f"{it.iter_num:>4} | {idx_cyc:>9} | {idx_summary:>20} | {data_cyc:>10} "
            f"| {data_summary:>25} | {grasp_summary:>45} | {lat_str:>7}"
        )
        lines.append(line)

        if latency is not None:
            total_latency += latency
            count_latency += 1

        if it.index_access:
            for statuses in it.index_access.lane_statuses.values():
                idx_total += 1
                final = statuses[-1] if statuses else ""
                if final in HIT_STATUSES | HITRES_STATUSES:
                    idx_hit_count += 1
        if it.data_access:
            for statuses in it.data_access.lane_statuses.values():
                data_total += 1
                final = statuses[-1] if statuses else ""
                if final in HIT_STATUSES | HITRES_STATUSES:
                    data_hit_count += 1

        csv_rows.append({
            "iter": it.iter_num, "idx_cycle": idx_cyc, "idx_L1": idx_summary,
            "data_cycle": data_cyc, "data_L1": data_summary,
            "grasp_summary": grasp_summary,
            "latency": latency if latency is not None else "",
        })

    lines.append("-" * len(hdr))
    avg_lat = total_latency / count_latency if count_latency else 0
    idx_hr = idx_hit_count / idx_total * 100 if idx_total else 0
    data_hr = data_hit_count / data_total * 100 if data_total else 0
    lines.append(
        f"  avg_latency={avg_lat:.1f}  idx_hit_rate={idx_hr:.1f}%  data_hit_rate={data_hr:.1f}%"
    )

    txt_path.write_text("\n".join(lines) + "\n")
    print(f"  Format A: {txt_path}")

    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "iter", "idx_cycle", "idx_L1", "data_cycle", "data_L1",
            "grasp_summary", "latency",
        ])
        w.writeheader()
        w.writerows(csv_rows)
    print(f"  Format A: {csv_path}")


# ---------------------------------------------------------------------------
# Event Timeline
# ---------------------------------------------------------------------------


def write_event_timeline(
    iterations: List[Iteration], out_dir: Path, warp_id: int, pc_config: PcConfig
) -> Path:
    txt_path = out_dir / f"event_timeline_warp{warp_id}.txt"
    lines: List[str] = []

    for it in iterations:
        lines.append(f"\n=== Warp {warp_id}, Iteration {it.iter_num} ===")

        # Collect all addresses for prefix compression
        all_addrs: List[int] = []
        all_l1: List[L1Event] = []
        if it.index_access:
            all_l1.extend(it.index_access.all_events)
        if it.data_access:
            all_l1.extend(it.data_access.all_events)
        for ev in all_l1:
            all_addrs.append(ev.address)
        for gev in it.grasp_events:
            if gev.addr:
                all_addrs.append(gev.addr)

        # Find common hex prefix (at nibble granularity)
        addr_prefix = ""
        if all_addrs:
            hex_strs = [f"{a:#018x}" for a in all_addrs]
            prefix_len = 0
            for i in range(len(hex_strs[0])):
                if all(h[i] == hex_strs[0][i] for h in hex_strs):
                    prefix_len = i + 1
                else:
                    break
            if prefix_len > 4:  # worth abbreviating
                addr_prefix = hex_strs[0][:prefix_len]

        def fmt_addr(addr: int) -> str:
            full = f"{addr:#018x}"
            if addr_prefix and full.startswith(addr_prefix):
                return f"..{full[len(addr_prefix):]}"
            return full

        if addr_prefix:
            lines.append(f"  [addr prefix: {addr_prefix}...]")

        timeline: List[Tuple[int, int, str, str]] = []

        # L1 events — show hex PC + label
        seen_l1: set = set()
        for ev in sorted(all_l1, key=lambda e: e.cycle):
            key = (ev.cycle, ev.lane_id, ev.address, ev.l1_status)
            if key in seen_l1:
                continue
            seen_l1.add(key)
            pclbl = pc_config.label(ev.pc)
            annotation = ""
            if ev.l1_status in HIT_STATUSES:
                annotation = "  <-- HIT"
            elif ev.l1_status in HITRES_STATUSES:
                annotation = "  <-- HIT_RES"
            text = (
                f"DEMAND {ev.pc:#05x} ({pclbl})  lane={ev.lane_id:<2}  "
                f"addr={fmt_addr(ev.address)}  L1={ev.l1_status}{annotation}"
            )
            timeline.append((ev.cycle, 0, "L1   ", text))

        # GRASP events — show hex PC + label
        for gev in it.grasp_events:
            detail_brief = format_detail_brief(gev)
            gpc_label = pc_config.label(gev.pc) if gev.pc else ""
            text = (
                f"{gev.event:<20} pc={gev.pc:#06x} ({gpc_label})  "
                f"addr={fmt_addr(gev.addr)}  {detail_brief}"
            )
            timeline.append((gev.cycle, 1, "GRASP", text))

        timeline.sort(key=lambda t: (t[0], t[1]))

        # Compress consecutive identical (src, text) runs
        compressed: List[str] = []
        prev_key: Optional[Tuple] = None
        repeat_count = 0
        first_cycle = 0
        last_cycle = 0
        for cyc, _, src, text in timeline:
            line_key = (src, text)
            if line_key == prev_key:
                repeat_count += 1
                last_cycle = cyc
            else:
                if repeat_count > 1:
                    compressed.append(
                        f"  ... repeated {repeat_count}x (cycle {first_cycle}\u2013{last_cycle})"
                    )
                prev_key = line_key
                compressed.append(f"  cycle {cyc:>6}  [{src}]  {text}")
                repeat_count = 1
                first_cycle = cyc
                last_cycle = cyc
        if repeat_count > 1:
            compressed.append(
                f"  ... repeated {repeat_count}x (cycle {first_cycle}\u2013{last_cycle})"
            )
        lines.extend(compressed)

        if it.idx_to_data_latency is not None:
            lines.append(f"  --- latency (idx→data served): {it.idx_to_data_latency} cycles")

    txt_path.write_text("\n".join(lines) + "\n")
    print(f"  Event timeline: {txt_path}")
    return txt_path


# ---------------------------------------------------------------------------
# Baseline Comparison
# ---------------------------------------------------------------------------


def write_baseline_comparison(
    base_iters: List[Iteration],
    grasp_iters: List[Iteration],
    out_dir: Path,
    warp_id: int,
) -> Tuple[Path, dict]:
    txt_path = out_dir / f"baseline_comparison_warp{warp_id}.txt"
    lines: List[str] = []
    n = min(len(base_iters), len(grasp_iters))
    if len(base_iters) != len(grasp_iters):
        lines.append(
            f"WARNING: iteration count mismatch: baseline={len(base_iters)}, "
            f"grasp={len(grasp_iters)}. Showing min({n})."
        )
    lines.append(f"=== Warp {warp_id}, Baseline vs GRASP ({n} iterations) ===\n")

    hdr = (
        f"{'iter':>4} | {'base_idx_cyc':>12} | {'base_idx_L1':>15} "
        f"| {'base_data_cyc':>13} | {'base_data_L1':>20} "
        f"| {'grasp_idx_cyc':>13} | {'grasp_idx_L1':>15} "
        f"| {'grasp_data_cyc':>14} | {'grasp_data_L1':>20} | {'speedup':>7}"
    )
    lines.append(hdr)
    lines.append("-" * len(hdr))

    total_base_lat = 0
    total_grasp_lat = 0
    count_both = 0

    for i in range(n):
        bi = base_iters[i]
        gi = grasp_iters[i]

        b_idx_cyc = bi.idx_cycle or 0
        b_data_cyc = bi.data_cycle or 0
        g_idx_cyc = gi.idx_cycle or 0
        g_data_cyc = gi.data_cycle or 0

        b_idx_l1 = summarize_l1(bi.index_access)
        b_data_l1 = summarize_l1(bi.data_access)
        g_idx_l1 = summarize_l1(gi.index_access)
        g_data_l1 = summarize_l1(gi.data_access)

        b_lat = bi.idx_to_data_latency
        g_lat = gi.idx_to_data_latency
        if b_lat and g_lat and g_lat > 0:
            speedup = f"{b_lat / g_lat:.2f}x"
            total_base_lat += b_lat
            total_grasp_lat += g_lat
            count_both += 1
        else:
            speedup = "N/A"

        line = (
            f"{i:>4} | {b_idx_cyc:>12} | {b_idx_l1:>15} "
            f"| {b_data_cyc:>13} | {b_data_l1:>20} "
            f"| {g_idx_cyc:>13} | {g_idx_l1:>15} "
            f"| {g_data_cyc:>14} | {g_data_l1:>20} | {speedup:>7}"
        )
        lines.append(line)

    lines.append("-" * len(hdr))
    metrics = {"avg_base_lat": 0.0, "avg_grasp_lat": 0.0, "speedup": 0.0, "n_iters": n}
    if count_both:
        avg_b = total_base_lat / count_both
        avg_g = total_grasp_lat / count_both
        overall = avg_b / avg_g if avg_g > 0 else 0
        lines.append(
            f"  avg baseline latency={avg_b:.1f}, avg GRASP latency={avg_g:.1f}, "
            f"overall speedup={overall:.2f}x"
        )
        metrics.update(avg_base_lat=avg_b, avg_grasp_lat=avg_g, speedup=overall)

    txt_path.write_text("\n".join(lines) + "\n")
    print(f"  Baseline comparison: {txt_path}")
    return txt_path, metrics


# ---------------------------------------------------------------------------
# Analysis Log
# ---------------------------------------------------------------------------


def write_analysis_log(
    out_dir: Path,
    grasp_l1_path: Path,
    base_l1_path: Path,
    grasp_trace_path: Path,
    pc_config: PcConfig,
    warp_metrics: Dict[int, dict],
    output_files: List[Path],
):
    log_path = out_dir / "analysis_log.txt"
    lines: List[str] = []
    lines.append("GRASP Per-Iteration Analysis Log (v2 — generalized)")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("Input files:")
    lines.append(f"  L1 trace (GRASP):    {grasp_l1_path}")
    lines.append(f"  L1 trace (baseline): {base_l1_path}")
    lines.append(f"  GRASP event trace:   {grasp_trace_path}")
    lines.append("")
    lines.append("PC configuration:")
    lines.append(f"  Index PCs:    {sorted(f'0x{p:03x}' for p in pc_config.index_pcs)}")
    lines.append(f"  Data PCs:     {sorted(f'0x{p:03x}' for p in pc_config.data_pcs)}")
    lines.append(f"  Boundary PCs: {sorted(f'0x{p:03x}' for p in pc_config.boundary_pcs)}")
    if pc_config.warmup_pc is not None:
        lines.append(f"  Warmup PC:    0x{pc_config.warmup_pc:03x}")
    if pc_config.tail_pcs:
        lines.append(f"  Tail PCs:     {sorted(f'0x{p:03x}' for p in pc_config.tail_pcs)}")
    lines.append("")

    for wid in sorted(warp_metrics):
        m = warp_metrics[wid]
        lines.append(f"Warp {wid}:")
        lines.append(f"  Iterations:          {m.get('n_iters', '?')}")
        avg_b = m.get("avg_base_lat", 0)
        avg_g = m.get("avg_grasp_lat", 0)
        sp = m.get("speedup", 0)
        if avg_b > 0:
            lines.append(f"  Avg baseline latency: {avg_b:.1f} cycles")
            lines.append(f"  Avg GRASP latency:    {avg_g:.1f} cycles")
            lines.append(f"  Overall speedup:      {sp:.2f}x")
        lines.append("")

    lines.append("Output files:")
    for p in output_files:
        lines.append(f"  {p.name}")

    log_path.write_text("\n".join(lines) + "\n")
    print(f"  Analysis log: {log_path}")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def find_csv(directory: Path, suffix: str) -> Path:
    candidates = sorted(directory.glob(f"*{suffix}"))
    if not candidates:
        print(f"ERROR: no *{suffix} found in {directory}", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser(
        description="Per-iteration GRASP prefetcher analysis (generalized v2)"
    )
    p.add_argument("--grasp-dir", type=Path, required=True,
                    help="Directory containing *_l1.csv and *_grasp.csv")
    p.add_argument("--baseline-dir", type=Path, required=True,
                    help="Directory containing baseline *_l1.csv")
    p.add_argument("--chain-csv", type=Path, required=True,
                    help="Chain CSV file to extract index/data PCs")
    p.add_argument("--algorithm", type=str, default=None,
                    help="Filter chains by algorithm name (for combined CSV)")
    p.add_argument("--boundary-pcs", type=str, default=None,
                    help="Comma-separated hex PCs for iteration boundary (default: all index PCs)")
    p.add_argument("--merge-window", type=int, default=0,
                    help="Merge boundary events within N cycles into one iteration (default: 0=off)")
    p.add_argument("--warmup-pc", type=str, default=None,
                    help="Hex PC for warmup region (optional)")
    p.add_argument("--tail-pcs", type=str, default=None,
                    help="Comma-separated hex PCs for tail region (optional)")
    p.add_argument("--warps", type=str, default="1")
    p.add_argument(
        "--format", type=str, default="all",
        choices=["summary", "timeline", "compare", "all", "a", "b", "c", "bc"],
        help="Output format (default: all)",
    )
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()

    # Normalize old aliases
    fmt_aliases = {"a": "summary", "b": "timeline", "c": "compare", "bc": "all"}
    fmt = fmt_aliases.get(args.format, args.format)

    # Build PcConfig from chain CSV
    index_pcs, data_pcs, auto_labels = load_chain_pcs(args.chain_csv, args.algorithm)
    if not index_pcs:
        print(f"ERROR: no chains found in {args.chain_csv}"
              + (f" for algorithm={args.algorithm}" if args.algorithm else ""),
              file=sys.stderr)
        sys.exit(1)

    boundary_pcs = index_pcs
    if args.boundary_pcs:
        boundary_pcs = {int(x, 16) for x in args.boundary_pcs.split(",")}

    warmup_pc = int(args.warmup_pc, 16) if args.warmup_pc else None
    tail_pcs = {int(x, 16) for x in args.tail_pcs.split(",")} if args.tail_pcs else set()

    if warmup_pc:
        auto_labels[warmup_pc] = "warmup"
    for tp in tail_pcs:
        auto_labels.setdefault(tp, f"tail_{tp:#05x}")

    pc_config = PcConfig(
        index_pcs=index_pcs, data_pcs=data_pcs,
        boundary_pcs=boundary_pcs, warmup_pc=warmup_pc,
        tail_pcs=tail_pcs, labels=auto_labels,
    )

    warps = {int(w) for w in args.warps.split(",")}
    out_dir = args.output_dir or args.grasp_dir / "analysis_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    grasp_l1_path = find_csv(args.grasp_dir, "_l1.csv")
    base_l1_path = find_csv(args.baseline_dir, "_l1.csv")
    grasp_trace_path = find_csv(args.grasp_dir, "_grasp.csv")

    print(f"Chain CSV:           {args.chain_csv}")
    if args.algorithm:
        print(f"Algorithm filter:    {args.algorithm}")
    print(f"Index PCs:           {sorted(f'0x{p:03x}' for p in index_pcs)}")
    print(f"Data PCs:            {sorted(f'0x{p:03x}' for p in data_pcs)}")
    print(f"Boundary PCs:        {sorted(f'0x{p:03x}' for p in boundary_pcs)}")
    print(f"L1 trace (GRASP):    {grasp_l1_path}")
    print(f"L1 trace (baseline): {base_l1_path}")
    print(f"GRASP trace:         {grasp_trace_path}")
    print(f"Warps: {sorted(warps)}")
    print(f"Format: {fmt}")
    print(f"Output: {out_dir}\n")

    grasp_l1 = parse_l1_trace(grasp_l1_path, warps, pc_config)
    grasp_trace = parse_grasp_trace(grasp_trace_path, warps)
    need_baseline = fmt in ("compare", "all")
    if need_baseline:
        base_l1 = parse_l1_trace(base_l1_path, warps, pc_config)

    warp_metrics: Dict[int, dict] = {}
    output_files: List[Path] = []

    for warp_id in sorted(warps):
        print(f"--- Warp {warp_id} ---")
        mw = args.merge_window
        grasp_iters = detect_iterations(
            grasp_l1.get(warp_id, []),
            grasp_trace.get(warp_id, []),
            warp_id, pc_config, mw,
        )
        print(f"  Detected {len(grasp_iters)} IMA iterations (GRASP)")

        if fmt in ("summary", "all"):
            write_format_a(grasp_iters, out_dir, warp_id, pc_config)
        if fmt in ("timeline", "all"):
            p_tl = write_event_timeline(grasp_iters, out_dir, warp_id, pc_config)
            output_files.append(p_tl)
        if fmt in ("compare", "all"):
            base_iters = detect_iterations(
                base_l1.get(warp_id, []), [], warp_id, pc_config, mw,
            )
            print(f"  Detected {len(base_iters)} IMA iterations (baseline)")
            p_cmp, metrics = write_baseline_comparison(
                base_iters, grasp_iters, out_dir, warp_id,
            )
            output_files.append(p_cmp)
            warp_metrics[warp_id] = metrics

    write_analysis_log(
        out_dir, grasp_l1_path, base_l1_path, grasp_trace_path,
        pc_config, warp_metrics, output_files,
    )


if __name__ == "__main__":
    main()
