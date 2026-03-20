#!/usr/bin/env python3
"""Issue-trace-driven IMA visualization for the tiny BFS case.

This version is centered on instruction issue timing rather than raw per-lane
L1 events so that:
  * warp-level patterns remain readable at SVG zoom levels
  * scheduler behavior can be compared between lrr and gto
  * IMA chains can be shown as issue->service timelines for a single warp

Outputs:
  * ima_windowed_<scheduler>.<fmt>
  * ima_window_summary_<scheduler>.csv
  * ima_window_role_breakdown_<scheduler>.csv
  * dcache_window_timeseries_<scheduler>.csv
  * ima_pattern_<scheduler>_absolute.<fmt>
  * ima_pattern_<scheduler>_aligned.<fmt>
  * ima_chain_<scheduler>_w<warp>.<fmt>
  * ima_scatter_index_<scheduler>.<fmt>
  * ima_scatter_data_<scheduler>.<fmt>
  * ima_chain_detail_<scheduler>.csv
  * ima_warp_stats_<scheduler>.csv
"""

from __future__ import annotations

import argparse
import csv
import gzip
import re
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np


plt.rcParams["svg.fonttype"] = "none"

CACHELINE_SHIFT = 7
L1_MATCH_WINDOW = 3000
WINDOW_BIN_CYCLES = 5000
WINDOW_THRESHOLD_RATIO = 0.6
MAX_STATUS_BINS = 120
DEFAULT_SOURCE_LINE_TO_ROLE = {
    "linear_base.cu:19": "index_load",
    "linear_base.cu:20": "data_load",
    "linear_base.cu:21": "data_load",
}
WORKLOAD_SOURCE_LINE_TO_ROLE = {
    "bfs_ima_high": DEFAULT_SOURCE_LINE_TO_ROLE,
    "sssp_ima_high": {
        "linear_base.cu:39": "index_load",
        "linear_base.cu:40": "data_load",
    },
    "cc_ima_high": {
        "base.cu:17": "index_load",
        "base.cu:19": "data_load",
    },
    "bc_ima_high": {
        "linear_base.cu:52": "index_load",
        "linear_base.cu:53": "data_load",
        "linear_base.cu:56": "data_load",
        "linear_base.cu:57": "data_load",
        "linear_base.cu:77": "index_load",
        "linear_base.cu:78": "data_load",
        "linear_base.cu:80": "data_load",
    },
}
ROLE_ORDER = ("index_load", "data_load")
HIT_STATUSES = {"HIT"}
HIT_RESERVED_STATUSES = {"HIT_RESERVED"}
MISS_STATUSES = {"MISS", "SECTOR_MISS"}
RESFAIL_STATUSES = {"RESERVATION_FAIL"}
STATUS_PRIORITY = {
    "MISS": 4,
    "HIT_RESERVED": 3,
    "HIT": 2,
    "RESFAIL": 1,
    "UNKNOWN": 0,
}
STATUS_STYLE = {
    "HIT": {"color": "#7fb3ff", "marker": "o", "label": "hit"},
    "HIT_RESERVED": {"color": "#5dade2", "marker": "s", "label": "hit_reserved"},
    "MISS": {"color": "#f2a65a", "marker": "x", "label": "miss-like"},
    "RESFAIL": {"color": "#b56576", "marker": "|", "label": "reservation_fail"},
    "UNKNOWN": {"color": "#9ca3af", "marker": ".", "label": "unknown"},
}
ROLE_COLOR = {
    "index_load": "#4f8ef7",
    "data_load": "#ff9f43",
}
L1_STATUS_ORDER = [
    "HIT",
    "HIT_RESERVED",
    "MSHR_HIT",
    "MISS",
    "SECTOR_MISS",
    "RESERVATION_FAIL",
]
L1_STATUS_COLOR = {
    "HIT": "#93c5fd",
    "HIT_RESERVED": "#38bdf8",
    "MSHR_HIT": "#14b8a6",
    "MISS": "#f59e0b",
    "SECTOR_MISS": "#f97316",
    "RESERVATION_FAIL": "#b91c1c",
}


@dataclass
class L1Record:
    cycle: int
    status: str


@dataclass
class L1TraceEvent:
    cycle: int
    warp_id: int
    op: str
    address: int
    status: str


@dataclass
class IssueEvent:
    cycle: int
    warp_id: int
    scheduler_id: int
    pc: Optional[int]
    op: str
    space: str
    role: Optional[str]


@dataclass
class MemoryIssue:
    scheduler_label: str
    scheduler_id: int
    cycle: int
    warp_id: int
    pc: int
    role: str
    issue_mask_hex: str
    issue_seq: int
    addresses: Tuple[int, ...]
    cachelines: Tuple[int, ...]
    initial_status: str
    initial_cycle: Optional[int]
    refill_cycle: Optional[int]
    completion_cycle: Optional[int]
    issue_to_refill: Optional[int]
    issue_to_complete: Optional[int]
    sector_count: int
    matched_sector_count: int
    sector_accesses: Tuple["SectorAccess", ...]


@dataclass
class SectorAccess:
    address: int
    cacheline: int
    initial_status: str
    initial_cycle: Optional[int]
    fill_cycle: Optional[int]


@dataclass
class ChainRecord:
    scheduler_label: str
    warp_id: int
    chain_id: int
    idx_issue_cycle: int
    idx_complete_cycle: Optional[int]
    idx_status: str
    idx_pc: int
    data_issue_cycle: Optional[int]
    data_complete_cycle: Optional[int]
    data_status: Optional[str]
    data_pc: Optional[int]
    idx_to_data_gap: Optional[int]
    data_service_latency: Optional[int]
    complete_flag: int


@dataclass
class RuntimeSnapshot:
    cycle: int
    accesses_total: int
    misses_total: int
    pending_hits_total: int
    reservation_fails_total: int
    data_port_util: float
    fill_port_util: float


@dataclass
class DcacheTimeseriesSample:
    origin: str
    cycle: int
    accesses_total: int
    misses_total: int
    pending_hits_total: int
    reservation_fails_total: int
    access_delta: int
    miss_delta: int
    pending_hit_delta: int
    reservation_fail_delta: int
    miss_rate_delta: float
    pending_hit_per_access: float
    reservation_fail_per_access: float
    data_port_util: float
    fill_port_util: float
    derived_outstanding_sectors: int


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", newline="")
    return path.open("r", newline="")


def parse_tuple_field(raw: Optional[str]) -> Tuple[int, ...]:
    if not raw:
        return ()
    value = raw.strip()
    if value == "NA":
        return ()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    if not value:
        return ()
    items = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        items.append(int(token, 16) if token.lower().startswith("0x") else int(token))
    return tuple(items)


def mask_is_zero(mask_value: Optional[str]) -> bool:
    if mask_value is None:
        return True
    text = mask_value.strip()
    if not text:
        return True
    try:
        return int(text, 16 if text.lower().startswith("0x") else 10) == 0
    except ValueError:
        return False


def normalize_mask_hex(mask_value: Optional[str]) -> str:
    if mask_value is None:
        return "NA"
    text = mask_value.strip()
    if not text:
        return "NA"
    try:
        value = int(text, 16 if text.lower().startswith("0x") else 10)
    except ValueError:
        return text
    return f"0x{value:x}"


def parse_cycle_range(text: str) -> Tuple[int, int]:
    parts = text.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"invalid cycle range: {text}")
    return int(parts[0]), int(parts[1])


def parse_pc_classification(path: Path, workload: str) -> Dict[int, Dict[str, str]]:
    pc_info: Dict[int, Dict[str, str]] = {}
    source_line_to_role = WORKLOAD_SOURCE_LINE_TO_ROLE.get(workload, DEFAULT_SOURCE_LINE_TO_ROLE)
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("workload") != workload:
                continue
            pc_hex = (row.get("pc") or "").strip()
            if not pc_hex:
                continue
            pc = int(pc_hex, 16)
            source = row.get("source_examples", "")
            role = None
            for pattern, mapped_role in source_line_to_role.items():
                if pattern in source:
                    role = mapped_role
                    break
            pc_info[pc] = {
                "role": role or row.get("load_class", "unknown"),
                "load_class": row.get("load_class", "unknown"),
                "source": source,
            }
    return pc_info


def classify_pc_role(pc: Optional[int], pc_info: Dict[int, Dict[str, str]]) -> Optional[str]:
    if pc is None:
        return None
    info = pc_info.get(pc)
    if info is None:
        return None
    role = info["role"]
    if role in ROLE_ORDER:
        return role
    return None


def load_l1_queues(
    path: Path,
) -> Tuple[Dict[Tuple[int, int], Tuple[L1Record, ...]], Dict[int, Tuple[int, ...]], List[L1TraceEvent]]:
    initial_lookup: Dict[Tuple[int, int], List[L1Record]] = defaultdict(list)
    fill_lookup: Dict[int, List[int]] = defaultdict(list)
    raw_events: List[L1TraceEvent] = []
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                cycle = int(row["cycle"])
                warp_id = int(row["warp_id"])
                addr = int(row["address"], 16)
            except (KeyError, TypeError, ValueError):
                continue
            op = row.get("op", "NA")
            status = row.get("l1_status", "UNKNOWN")
            raw_events.append(
                L1TraceEvent(
                    cycle=cycle,
                    warp_id=warp_id,
                    op=op,
                    address=addr,
                    status=status,
                )
            )
            if op != "LD":
                continue
            if status == "FILL":
                fill_lookup[addr].append(cycle)
            else:
                initial_lookup[(warp_id, addr)].append(L1Record(cycle=cycle, status=status))

    return (
        {key: tuple(sorted(records, key=lambda rec: rec.cycle)) for key, records in initial_lookup.items()},
        {key: tuple(sorted(cycles)) for key, cycles in fill_lookup.items()},
        raw_events,
    )


def classify_initial_status(statuses: Sequence[str]) -> str:
    if any(status in MISS_STATUSES for status in statuses):
        return "MISS"
    if any(status in HIT_RESERVED_STATUSES for status in statuses):
        return "HIT_RESERVED"
    if any(status in HIT_STATUSES for status in statuses):
        return "HIT"
    if any(status in RESFAIL_STATUSES for status in statuses):
        return "RESFAIL"
    return "UNKNOWN"


def find_initial_status(records: Optional[Sequence[L1Record]], issue_cycle: int) -> Optional[Tuple[str, Optional[int], Optional[int]]]:
    if not records:
        return None

    limit = issue_cycle + L1_MATCH_WINDOW
    cycles = [record.cycle for record in records]
    start_idx = bisect_left(cycles, issue_cycle)
    if start_idx >= len(records):
        return None

    statuses: List[str] = []
    min_cycle: Optional[int] = None
    max_cycle: Optional[int] = None
    idx = start_idx
    while idx < len(records):
        record = records[idx]
        if record.cycle > limit:
            break
        statuses.append(record.status)
        if min_cycle is None or record.cycle < min_cycle:
            min_cycle = record.cycle
        if max_cycle is None or record.cycle > max_cycle:
            max_cycle = record.cycle
        if record.status not in RESFAIL_STATUSES:
            break
        idx += 1

    if not statuses:
        return None
    return classify_initial_status(statuses), min_cycle, max_cycle


def find_fill_cycle(cycles: Optional[Sequence[int]], start_cycle: int) -> Optional[int]:
    if not cycles:
        return None
    idx = bisect_left(cycles, start_cycle)
    if idx >= len(cycles):
        return None
    return cycles[idx]


def aggregate_issue_status(
    addresses: Sequence[int],
    warp_id: int,
    issue_cycle: int,
    initial_lookup: Dict[Tuple[int, int], Tuple[L1Record, ...]],
    fill_lookup: Dict[int, Tuple[int, ...]],
) -> Tuple[str, Optional[int], Optional[int], Optional[int], int, Tuple[SectorAccess, ...]]:
    statuses: List[str] = []
    initial_cycles: List[int] = []
    refill_candidates: List[int] = []
    completion_candidates: List[int] = []
    matched_sector_count = 0
    sector_accesses: List[SectorAccess] = []

    for addr in sorted(set(addresses)):
        initial_match = find_initial_status(initial_lookup.get((warp_id, addr)), issue_cycle)
        if initial_match is None:
            statuses.append("UNKNOWN")
            sector_accesses.append(
                SectorAccess(
                    address=addr,
                    cacheline=addr >> CACHELINE_SHIFT,
                    initial_status="UNKNOWN",
                    initial_cycle=None,
                    fill_cycle=None,
                )
            )
            continue
        matched_sector_count += 1
        status, min_cycle, max_cycle = initial_match
        fill_cycle: Optional[int] = None
        statuses.append(status)
        if min_cycle is not None:
            initial_cycles.append(min_cycle)
        if status in {"MISS", "HIT_RESERVED"}:
            fill_cycle = find_fill_cycle(fill_lookup.get(addr), max_cycle or issue_cycle)
            if fill_cycle is not None:
                refill_candidates.append(fill_cycle)
                completion_candidates.append(fill_cycle)
        elif status == "HIT" and max_cycle is not None:
            completion_candidates.append(max_cycle)
        sector_accesses.append(
            SectorAccess(
                address=addr,
                cacheline=addr >> CACHELINE_SHIFT,
                initial_status=status,
                initial_cycle=min_cycle,
                fill_cycle=fill_cycle,
            )
        )

    if not statuses:
        return "UNKNOWN", None, None, None, matched_sector_count, ()

    overall_status = max(statuses, key=lambda item: STATUS_PRIORITY[item])
    initial_cycle = min(initial_cycles) if initial_cycles else None
    refill_cycle = max(refill_candidates) if refill_candidates else None
    completion_cycle = max(completion_candidates) if completion_candidates else None
    if overall_status == "RESFAIL":
        completion_cycle = None
    return overall_status, initial_cycle, refill_cycle, completion_cycle, matched_sector_count, tuple(sector_accesses)


def iter_issue_rows(path: Path) -> Iterator[Dict[str, str]]:
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("event") == "ISSUE":
                yield row


def parse_issue_row(row: Dict[str, str], pc_info: Dict[int, Dict[str, str]]) -> Optional[IssueEvent]:
    try:
        cycle = int(row.get("cycle", "0"))
        warp_id = int(row.get("warp") or row.get("warp_id") or "0")
        scheduler_id = int(row.get("scheduler", "0"))
    except ValueError:
        return None

    pc_text = row.get("pc")
    pc = None
    if pc_text and pc_text != "NA":
        try:
            pc = int(pc_text, 16)
        except ValueError:
            pc = None

    op = row.get("OP", "NA")
    space = row.get("Space", "NA")
    role = classify_pc_role(pc, pc_info)
    return IssueEvent(
        cycle=cycle,
        warp_id=warp_id,
        scheduler_id=scheduler_id,
        pc=pc,
        op=op,
        space=space,
        role=role,
    )


def build_memory_issue(
    row: Dict[str, str],
    issue_event: IssueEvent,
    scheduler_label: str,
    issue_seq: int,
    initial_lookup: Dict[Tuple[int, int], Tuple[L1Record, ...]],
    fill_lookup: Dict[int, Tuple[int, ...]],
) -> Optional[MemoryIssue]:
    if issue_event.role not in ROLE_ORDER:
        return None
    if issue_event.op != "LOAD_OP":
        return None
    if issue_event.space not in {"GLOBAL", "LOCAL"}:
        return None
    if mask_is_zero(row.get("mask")):
        return None

    addresses = tuple(sorted(set(parse_tuple_field(row.get("Issue_Sector_Addresses")))))
    cachelines = tuple(sorted({addr >> CACHELINE_SHIFT for addr in addresses}))
    status, initial_cycle, refill_cycle, completion_cycle, matched_sector_count, sector_accesses = aggregate_issue_status(
        addresses, issue_event.warp_id, issue_event.cycle, initial_lookup, fill_lookup
    )
    return MemoryIssue(
        scheduler_label=scheduler_label,
        scheduler_id=issue_event.scheduler_id,
        cycle=issue_event.cycle,
        warp_id=issue_event.warp_id,
        pc=issue_event.pc if issue_event.pc is not None else 0,
        role=issue_event.role,
        issue_mask_hex=normalize_mask_hex(row.get("mask")),
        issue_seq=issue_seq,
        addresses=addresses,
        cachelines=cachelines,
        initial_status=status,
        initial_cycle=initial_cycle,
        refill_cycle=refill_cycle,
        completion_cycle=completion_cycle,
        issue_to_refill=refill_cycle - issue_event.cycle if refill_cycle is not None else None,
        issue_to_complete=completion_cycle - issue_event.cycle if completion_cycle is not None else None,
        sector_count=len(addresses),
        matched_sector_count=matched_sector_count,
        sector_accesses=sector_accesses,
    )


def auto_cycle_window(memory_issues: Sequence[MemoryIssue]) -> Tuple[int, int]:
    start = min(event.cycle for event in memory_issues)
    end = max(event.cycle for event in memory_issues)
    margin = max(2000, int((end - start) * 0.04))
    return start - margin, end + margin


def detect_dense_window(
    memory_issues: Sequence[MemoryIssue],
    bin_cycles: int = WINDOW_BIN_CYCLES,
    threshold_ratio: float = WINDOW_THRESHOLD_RATIO,
) -> Tuple[int, int]:
    if not memory_issues:
        raise ValueError("cannot detect a dense window without memory issues")

    cycles = [event.cycle for event in memory_issues if event.role in ROLE_ORDER]
    if not cycles:
        return auto_cycle_window(memory_issues)

    counts = Counter(cycle // bin_cycles for cycle in cycles)
    peak_bin, peak_count = max(counts.items(), key=lambda item: (item[1], -item[0]))
    threshold = max(1, int(np.ceil(peak_count * threshold_ratio)))
    selected_bins = {peak_bin}

    probe = peak_bin - 1
    while counts.get(probe, 0) >= threshold:
        selected_bins.add(probe)
        probe -= 1

    probe = peak_bin + 1
    while counts.get(probe, 0) >= threshold:
        selected_bins.add(probe)
        probe += 1

    selected_cycles = [cycle for cycle in cycles if (cycle // bin_cycles) in selected_bins]
    if not selected_cycles:
        return auto_cycle_window(memory_issues)

    margin = max(1000, bin_cycles // 2)
    return min(selected_cycles) - margin, max(selected_cycles) + margin


def choose_status_bin_cycles(cycle_window: Tuple[int, int]) -> int:
    span = max(1, cycle_window[1] - cycle_window[0] + 1)
    raw_bin = max(1, int(np.ceil(span / MAX_STATUS_BINS)))
    granularity = 500 if span <= 100_000 else 1000
    return max(granularity, int(np.ceil(raw_bin / granularity)) * granularity)


def parse_dl1_config(log_path: Path) -> Tuple[Optional[int], Optional[int]]:
    config_re = re.compile(r"-gpgpu_cache:dl1\s+(\S+)")
    with log_path.open() as handle:
        for line in handle:
            match = config_re.search(line)
            if not match:
                continue
            config = match.group(1)
            parts = config.split(",")
            if len(parts) < 3:
                return None, None
            geometry = parts[0].split(":")
            mshr = parts[2].split(":")
            try:
                nsets = int(geometry[1])
                assoc = int(geometry[3])
                total_lines = nsets * assoc
            except (IndexError, ValueError):
                total_lines = None
            try:
                mshr_entries = int(mshr[1])
            except (IndexError, ValueError):
                mshr_entries = None
            return total_lines, mshr_entries
    return None, None


def parse_runtime_snapshots(log_path: Path) -> List[RuntimeSnapshot]:
    cycle_re = re.compile(r"gpu_tot_sim_cycle\s*=\s*(\d+)")
    int_fields = {
        "accesses_total": re.compile(r"L1D_total_cache_accesses\s*=\s*(\d+)"),
        "misses_total": re.compile(r"L1D_total_cache_misses\s*=\s*(\d+)"),
        "pending_hits_total": re.compile(r"L1D_total_cache_pending_hits\s*=\s*(\d+)"),
        "reservation_fails_total": re.compile(r"L1D_total_cache_reservation_fails\s*=\s*(\d+)"),
    }
    float_fields = {
        "data_port_util": re.compile(r"L1D_cache_data_port_util\s*=\s*([0-9.]+)"),
        "fill_port_util": re.compile(r"L1D_cache_fill_port_util\s*=\s*([0-9.]+)"),
    }

    snapshots: List[RuntimeSnapshot] = []
    current: Dict[str, object] = {}

    def finalize_snapshot() -> None:
        if not current:
            return
        required = [
            "cycle",
            "accesses_total",
            "misses_total",
            "pending_hits_total",
            "reservation_fails_total",
            "data_port_util",
            "fill_port_util",
        ]
        if all(key in current for key in required):
            snapshots.append(
                RuntimeSnapshot(
                    cycle=int(current["cycle"]),
                    accesses_total=int(current["accesses_total"]),
                    misses_total=int(current["misses_total"]),
                    pending_hits_total=int(current["pending_hits_total"]),
                    reservation_fails_total=int(current["reservation_fails_total"]),
                    data_port_util=float(current["data_port_util"]),
                    fill_port_util=float(current["fill_port_util"]),
                )
            )

    with log_path.open() as handle:
        for line in handle:
            cycle_match = cycle_re.search(line)
            if cycle_match:
                finalize_snapshot()
                current = {"cycle": int(cycle_match.group(1))}
                continue
            if not current:
                continue
            for name, pattern in int_fields.items():
                match = pattern.search(line)
                if match:
                    current[name] = int(match.group(1))
            for name, pattern in float_fields.items():
                match = pattern.search(line)
                if match:
                    current[name] = float(match.group(1))
    finalize_snapshot()
    snapshots.sort(key=lambda item: item.cycle)
    return snapshots


def build_outstanding_markers(l1_events: Sequence[L1TraceEvent]) -> Tuple[List[int], List[int]]:
    active_addrs: set[int] = set()
    markers: List[Tuple[int, int]] = []
    for event in sorted(l1_events, key=lambda item: item.cycle):
        if event.op != "LD":
            continue
        if event.status in MISS_STATUSES:
            if event.address not in active_addrs:
                active_addrs.add(event.address)
                markers.append((event.cycle, 1))
        elif event.status == "FILL":
            if event.address in active_addrs:
                active_addrs.remove(event.address)
                markers.append((event.cycle, -1))

    cycles: List[int] = []
    counts: List[int] = []
    cur = 0
    for cycle, delta in sorted(markers):
        cur += delta
        cycles.append(cycle)
        counts.append(cur)
    return cycles, counts


def outstanding_at(cycles: Sequence[int], counts: Sequence[int], query_cycle: int) -> int:
    if not cycles:
        return 0
    idx = bisect_left(cycles, query_cycle)
    if idx < len(cycles) and cycles[idx] == query_cycle:
        return counts[idx]
    idx -= 1
    if idx < 0:
        return 0
    return counts[idx]


def build_dcache_timeseries(
    runtime_snapshots: Sequence[RuntimeSnapshot],
    l1_events: Sequence[L1TraceEvent],
    cycle_window: Tuple[int, int],
) -> List[DcacheTimeseriesSample]:
    outstanding_cycles, outstanding_counts = build_outstanding_markers(l1_events)
    samples: List[DcacheTimeseriesSample] = []
    previous: Optional[RuntimeSnapshot] = None
    for snapshot in runtime_snapshots:
        access_delta = snapshot.accesses_total - (previous.accesses_total if previous else 0)
        miss_delta = snapshot.misses_total - (previous.misses_total if previous else 0)
        pending_hit_delta = snapshot.pending_hits_total - (previous.pending_hits_total if previous else 0)
        reservation_fail_delta = snapshot.reservation_fails_total - (
            previous.reservation_fails_total if previous else 0
        )
        access_delta = max(access_delta, 0)
        miss_delta = max(miss_delta, 0)
        pending_hit_delta = max(pending_hit_delta, 0)
        reservation_fail_delta = max(reservation_fail_delta, 0)
        sample = DcacheTimeseriesSample(
            origin="in_window",
            cycle=snapshot.cycle,
            accesses_total=snapshot.accesses_total,
            misses_total=snapshot.misses_total,
            pending_hits_total=snapshot.pending_hits_total,
            reservation_fails_total=snapshot.reservation_fails_total,
            access_delta=access_delta,
            miss_delta=miss_delta,
            pending_hit_delta=pending_hit_delta,
            reservation_fail_delta=reservation_fail_delta,
            miss_rate_delta=(miss_delta / access_delta) if access_delta else 0.0,
            pending_hit_per_access=(pending_hit_delta / access_delta) if access_delta else 0.0,
            reservation_fail_per_access=(reservation_fail_delta / access_delta) if access_delta else 0.0,
            data_port_util=snapshot.data_port_util,
            fill_port_util=snapshot.fill_port_util,
            derived_outstanding_sectors=outstanding_at(outstanding_cycles, outstanding_counts, snapshot.cycle),
        )
        if cycle_window[0] <= snapshot.cycle <= cycle_window[1]:
            samples.append(sample)
        previous = snapshot

    if not samples and runtime_snapshots:
        midpoint = (cycle_window[0] + cycle_window[1]) // 2
        nearest = min(
            [
                DcacheTimeseriesSample(
                    origin="nearest_snapshot",
                    cycle=snapshot.cycle,
                    accesses_total=snapshot.accesses_total,
                    misses_total=snapshot.misses_total,
                    pending_hits_total=snapshot.pending_hits_total,
                    reservation_fails_total=snapshot.reservation_fails_total,
                    access_delta=max(
                        snapshot.accesses_total - (runtime_snapshots[idx - 1].accesses_total if idx else 0),
                        0,
                    ),
                    miss_delta=max(
                        snapshot.misses_total - (runtime_snapshots[idx - 1].misses_total if idx else 0),
                        0,
                    ),
                    pending_hit_delta=max(
                        snapshot.pending_hits_total - (runtime_snapshots[idx - 1].pending_hits_total if idx else 0),
                        0,
                    ),
                    reservation_fail_delta=max(
                        snapshot.reservation_fails_total
                        - (runtime_snapshots[idx - 1].reservation_fails_total if idx else 0),
                        0,
                    ),
                    miss_rate_delta=0.0,
                    pending_hit_per_access=0.0,
                    reservation_fail_per_access=0.0,
                    data_port_util=snapshot.data_port_util,
                    fill_port_util=snapshot.fill_port_util,
                    derived_outstanding_sectors=outstanding_at(outstanding_cycles, outstanding_counts, snapshot.cycle),
                )
                for idx, snapshot in enumerate(runtime_snapshots)
            ],
            key=lambda item: abs(item.cycle - midpoint),
        )
        if nearest.access_delta:
            nearest.miss_rate_delta = nearest.miss_delta / nearest.access_delta
            nearest.pending_hit_per_access = nearest.pending_hit_delta / nearest.access_delta
            nearest.reservation_fail_per_access = nearest.reservation_fail_delta / nearest.access_delta
        samples = [nearest]
    return samples


def filter_l1_window(l1_events: Sequence[L1TraceEvent], cycle_window: Tuple[int, int]) -> List[L1TraceEvent]:
    return [event for event in l1_events if cycle_window[0] <= event.cycle <= cycle_window[1]]


def status_counts_in_window(l1_events: Sequence[L1TraceEvent]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in l1_events:
        if event.op != "LD" or event.status == "FILL":
            continue
        counts[event.status] += 1
    return counts


def build_status_timeseries(
    l1_events: Sequence[L1TraceEvent],
    cycle_window: Tuple[int, int],
    bin_cycles: int,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], np.ndarray]:
    span = max(1, cycle_window[1] - cycle_window[0] + 1)
    num_bins = max(1, int(np.ceil(span / bin_cycles)))
    total = np.zeros(num_bins, dtype=np.int64)
    status_counts = {status: np.zeros(num_bins, dtype=np.int64) for status in L1_STATUS_ORDER}
    for event in l1_events:
        if event.op != "LD" or event.status == "FILL":
            continue
        bin_idx = min(num_bins - 1, max(0, (event.cycle - cycle_window[0]) // bin_cycles))
        total[bin_idx] += 1
        if event.status in status_counts:
            status_counts[event.status][bin_idx] += 1
    x = cycle_window[0] + np.arange(num_bins) * bin_cycles + (bin_cycles / 2.0)
    return x, status_counts, total


def unique_cachelines_touched(l1_events: Sequence[L1TraceEvent], cycle_window: Tuple[int, int]) -> int:
    lines = {
        event.address >> CACHELINE_SHIFT
        for event in l1_events
        if event.op == "LD" and event.status != "FILL" and cycle_window[0] <= event.cycle <= cycle_window[1]
    }
    return len(lines)


def warp_order_by_first_issue(memory_issues: Sequence[MemoryIssue]) -> List[int]:
    first_cycle: Dict[int, int] = {}
    for event in memory_issues:
        first_cycle.setdefault(event.warp_id, event.cycle)
    return [warp_id for warp_id, _ in sorted(first_cycle.items(), key=lambda item: (item[1], item[0]))]


def load_memory_issues(
    path: Path,
    scheduler_label: str,
    pc_info: Dict[int, Dict[str, str]],
    initial_lookup: Dict[Tuple[int, int], Tuple[L1Record, ...]],
    fill_lookup: Dict[int, Tuple[int, ...]],
    cycle_range: Optional[Tuple[int, int]],
) -> List[MemoryIssue]:
    memory_issues: List[MemoryIssue] = []
    issue_seq_by_warp_role: Dict[Tuple[int, str], int] = defaultdict(int)
    for row in iter_issue_rows(path):
        issue_event = parse_issue_row(row, pc_info)
        if issue_event is None:
            continue
        if cycle_range and not (cycle_range[0] <= issue_event.cycle <= cycle_range[1]):
            continue
        if issue_event.role in ROLE_ORDER:
            issue_key = (issue_event.warp_id, issue_event.role)
            issue_seq = issue_seq_by_warp_role[issue_key]
            issue_seq_by_warp_role[issue_key] += 1
        else:
            issue_seq = 0
        memory_issue = build_memory_issue(
            row,
            issue_event,
            scheduler_label,
            issue_seq,
            initial_lookup,
            fill_lookup,
        )
        if memory_issue is not None:
            memory_issues.append(memory_issue)
    return memory_issues


def load_issue_events_in_window(
    path: Path,
    pc_info: Dict[int, Dict[str, str]],
    cycle_window: Tuple[int, int],
) -> List[IssueEvent]:
    start, end = cycle_window
    events: List[IssueEvent] = []
    for row in iter_issue_rows(path):
        issue_event = parse_issue_row(row, pc_info)
        if issue_event is None:
            continue
        if start <= issue_event.cycle <= end:
            events.append(issue_event)
    return events


def tracked_ima_loads(memory_issues: Sequence[MemoryIssue]) -> List[MemoryIssue]:
    role_order = {"index_load": 0, "data_load": 1}
    return sorted(
        [event for event in memory_issues if event.role in role_order],
        key=lambda event: (event.warp_id, role_order[event.role], event.issue_seq),
    )


def format_hex_list(values: Sequence[int]) -> str:
    return ";".join(f"0x{value:x}" for value in values)


def format_int_list(values: Sequence[int]) -> str:
    return ";".join(str(value) for value in values)


def write_warp_load_events(out_dir: Path, scheduler_label: str, memory_issues: Sequence[MemoryIssue]) -> Path:
    out_file = out_dir / f"warp_load_events_{scheduler_label}.csv"
    tracked = tracked_ima_loads(memory_issues)
    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "role",
                "warp_id",
                "issue_seq",
                "issue_cycle",
                "scheduler",
                "pc",
                "issue_mask_hex",
                "sector_addr_count",
                "sector_addrs",
                "cacheline_ids",
                "first_status",
                "refill_cycle",
                "issue_to_refill",
            ]
        )
        for event in tracked:
            writer.writerow(
                [
                    event.role,
                    event.warp_id,
                    event.issue_seq,
                    event.cycle,
                    event.scheduler_id,
                    f"0x{event.pc:x}",
                    event.issue_mask_hex,
                    len(event.addresses),
                    format_hex_list(event.addresses),
                    format_int_list(event.cachelines),
                    event.initial_status,
                    event.refill_cycle,
                    event.issue_to_refill,
                ]
            )
    print(f"  Saved: {out_file}")
    return out_file


def write_warp_load_sectors(out_dir: Path, scheduler_label: str, memory_issues: Sequence[MemoryIssue]) -> Path:
    out_file = out_dir / f"warp_load_sectors_{scheduler_label}.csv"
    tracked = tracked_ima_loads(memory_issues)
    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "role",
                "warp_id",
                "issue_seq",
                "issue_cycle",
                "scheduler",
                "pc",
                "issue_mask_hex",
                "sector_idx",
                "sector_addr",
                "cacheline_id",
                "initial_l1_status",
                "initial_cycle",
                "fill_cycle",
            ]
        )
        for event in tracked:
            for sector_idx, sector in enumerate(event.sector_accesses):
                writer.writerow(
                    [
                        event.role,
                        event.warp_id,
                        event.issue_seq,
                        event.cycle,
                        event.scheduler_id,
                        f"0x{event.pc:x}",
                        event.issue_mask_hex,
                        sector_idx,
                        f"0x{sector.address:x}",
                        sector.cacheline,
                        sector.initial_status,
                        sector.initial_cycle,
                        sector.fill_cycle,
                    ]
                )
    print(f"  Saved: {out_file}")
    return out_file


def write_window_summary(
    out_dir: Path,
    scheduler_label: str,
    cycle_window: Tuple[int, int],
    memory_issues: Sequence[MemoryIssue],
    l1_window_events: Sequence[L1TraceEvent],
    dcache_samples: Sequence[DcacheTimeseriesSample],
    l1d_total_lines: Optional[int],
    l1d_mshr_entries: Optional[int],
) -> Path:
    out_file = out_dir / f"ima_window_summary_{scheduler_label}.csv"
    status_counts = status_counts_in_window(l1_window_events)
    total_accesses = sum(status_counts.values())
    unique_lines = unique_cachelines_touched(l1_window_events, cycle_window)
    working_set_pressure = (unique_lines / l1d_total_lines) if l1d_total_lines else 0.0
    avg_outstanding = (
        float(np.mean([sample.derived_outstanding_sectors for sample in dcache_samples]))
        if dcache_samples
        else 0.0
    )
    peak_outstanding = max((sample.derived_outstanding_sectors for sample in dcache_samples), default=0)
    avg_pending_rate = (
        float(np.mean([sample.pending_hit_per_access for sample in dcache_samples])) if dcache_samples else 0.0
    )
    peak_pending_rate = max((sample.pending_hit_per_access for sample in dcache_samples), default=0.0)
    avg_resfail_rate = (
        float(np.mean([sample.reservation_fail_per_access for sample in dcache_samples]))
        if dcache_samples
        else 0.0
    )
    peak_resfail_rate = max((sample.reservation_fail_per_access for sample in dcache_samples), default=0.0)
    avg_data_util = float(np.mean([sample.data_port_util for sample in dcache_samples])) if dcache_samples else 0.0
    peak_data_util = max((sample.data_port_util for sample in dcache_samples), default=0.0)
    avg_fill_util = float(np.mean([sample.fill_port_util for sample in dcache_samples])) if dcache_samples else 0.0
    peak_fill_util = max((sample.fill_port_util for sample in dcache_samples), default=0.0)

    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheduler",
                "summary_scope",
                "window_start",
                "window_end",
                "active_warp_count",
                "ima_issue_count",
                "index_issue_count",
                "data_issue_count",
                "all_ld_accesses_in_window",
                "runtime_sample_count",
                "used_nearest_runtime_snapshot",
                "hit_rate",
                "hit_reserved_rate",
                "mshr_hit_rate",
                "miss_like_rate",
                "resfail_rate",
                "unique_cachelines_touched",
                "l1d_total_lines",
                "l1d_mshr_entries",
                "working_set_pressure",
                "avg_outstanding_sectors",
                "peak_outstanding_sectors",
                "avg_pending_hit_per_access",
                "peak_pending_hit_per_access",
                "avg_reservation_fail_per_access",
                "peak_reservation_fail_per_access",
                "avg_data_port_util",
                "peak_data_port_util",
                "avg_fill_port_util",
                "peak_fill_port_util",
            ]
        )
        writer.writerow(
            [
                scheduler_label,
                "all_ld_window",
                cycle_window[0],
                cycle_window[1],
                len({event.warp_id for event in memory_issues}),
                len(memory_issues),
                sum(event.role == "index_load" for event in memory_issues),
                sum(event.role == "data_load" for event in memory_issues),
                total_accesses,
                sum(sample.origin == "in_window" for sample in dcache_samples),
                1 if any(sample.origin == "nearest_snapshot" for sample in dcache_samples) else 0,
                f"{(status_counts['HIT'] / total_accesses):.4f}" if total_accesses else "0.0000",
                f"{(status_counts['HIT_RESERVED'] / total_accesses):.4f}" if total_accesses else "0.0000",
                f"{(status_counts['MSHR_HIT'] / total_accesses):.4f}" if total_accesses else "0.0000",
                f"{((status_counts['MISS'] + status_counts['SECTOR_MISS']) / total_accesses):.4f}"
                if total_accesses
                else "0.0000",
                f"{(status_counts['RESERVATION_FAIL'] / total_accesses):.4f}" if total_accesses else "0.0000",
                unique_lines,
                l1d_total_lines if l1d_total_lines is not None else "",
                l1d_mshr_entries if l1d_mshr_entries is not None else "",
                f"{working_set_pressure:.4f}",
                f"{avg_outstanding:.2f}",
                peak_outstanding,
                f"{avg_pending_rate:.4f}",
                f"{peak_pending_rate:.4f}",
                f"{avg_resfail_rate:.4f}",
                f"{peak_resfail_rate:.4f}",
                f"{avg_data_util:.4f}",
                f"{peak_data_util:.4f}",
                f"{avg_fill_util:.4f}",
                f"{peak_fill_util:.4f}",
            ]
        )
    print(f"  Saved: {out_file}")
    return out_file


def write_window_role_breakdown(
    out_dir: Path,
    scheduler_label: str,
    cycle_window: Tuple[int, int],
    memory_issues: Sequence[MemoryIssue],
    l1_window_events: Sequence[L1TraceEvent],
) -> Path:
    out_file = out_dir / f"ima_window_role_breakdown_{scheduler_label}.csv"
    tracked = tracked_ima_loads(memory_issues)

    def role_issue_counts(role: str) -> Counter[str]:
        counts: Counter[str] = Counter()
        for event in tracked:
            if event.role == role:
                counts[event.initial_status] += 1
        return counts

    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheduler",
                "window_start",
                "window_end",
                "scope",
                "count_basis",
                "access_count",
                "hit_count",
                "hit_reserved_count",
                "mshr_hit_count",
                "miss_count",
                "sector_miss_count",
                "reservation_fail_count",
                "unknown_count",
                "hit_rate",
                "miss_like_rate",
                "resfail_rate",
            ]
        )

        all_ld_counts = status_counts_in_window(l1_window_events)
        all_ld_total = sum(all_ld_counts.values())
        writer.writerow(
            [
                scheduler_label,
                cycle_window[0],
                cycle_window[1],
                "all_ld_window",
                "all_l1_ld_events",
                all_ld_total,
                all_ld_counts["HIT"],
                all_ld_counts["HIT_RESERVED"],
                all_ld_counts["MSHR_HIT"],
                all_ld_counts["MISS"],
                all_ld_counts["SECTOR_MISS"],
                all_ld_counts["RESERVATION_FAIL"],
                0,
                f"{(all_ld_counts['HIT'] / all_ld_total):.4f}" if all_ld_total else "0.0000",
                f"{((all_ld_counts['MISS'] + all_ld_counts['SECTOR_MISS']) / all_ld_total):.4f}"
                if all_ld_total
                else "0.0000",
                f"{(all_ld_counts['RESERVATION_FAIL'] / all_ld_total):.4f}" if all_ld_total else "0.0000",
            ]
        )

        for role in ROLE_ORDER:
            counts = role_issue_counts(role)
            total = sum(counts.values())
            writer.writerow(
                [
                    scheduler_label,
                    cycle_window[0],
                    cycle_window[1],
                    role,
                    "ima_issue_events",
                    total,
                    counts["HIT"],
                    counts["HIT_RESERVED"],
                    0,
                    counts["MISS"],
                    0,
                    counts["RESFAIL"],
                    counts["UNKNOWN"],
                    f"{(counts['HIT'] / total):.4f}" if total else "0.0000",
                    f"{(counts['MISS'] / total):.4f}" if total else "0.0000",
                    f"{(counts['RESFAIL'] / total):.4f}" if total else "0.0000",
                ]
            )

    print(f"  Saved: {out_file}")
    return out_file


def write_dcache_timeseries(
    out_dir: Path,
    scheduler_label: str,
    cycle_window: Tuple[int, int],
    dcache_samples: Sequence[DcacheTimeseriesSample],
) -> Path:
    out_file = out_dir / f"dcache_window_timeseries_{scheduler_label}.csv"
    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheduler",
                "window_start",
                "window_end",
                "sample_origin",
                "sample_cycle",
                "accesses_total",
                "misses_total",
                "pending_hits_total",
                "reservation_fails_total",
                "access_delta",
                "miss_delta",
                "pending_hit_delta",
                "reservation_fail_delta",
                "miss_rate_delta",
                "pending_hit_per_access",
                "reservation_fail_per_access",
                "data_port_util",
                "fill_port_util",
                "derived_outstanding_sectors",
            ]
        )
        for sample in dcache_samples:
            writer.writerow(
                [
                    scheduler_label,
                    cycle_window[0],
                    cycle_window[1],
                    sample.origin,
                    sample.cycle,
                    sample.accesses_total,
                    sample.misses_total,
                    sample.pending_hits_total,
                    sample.reservation_fails_total,
                    sample.access_delta,
                    sample.miss_delta,
                    sample.pending_hit_delta,
                    sample.reservation_fail_delta,
                    f"{sample.miss_rate_delta:.4f}",
                    f"{sample.pending_hit_per_access:.4f}",
                    f"{sample.reservation_fail_per_access:.4f}",
                    f"{sample.data_port_util:.4f}",
                    f"{sample.fill_port_util:.4f}",
                    sample.derived_outstanding_sectors,
                ]
            )
    print(f"  Saved: {out_file}")
    return out_file


def plot_windowed_view(
    out_dir: Path,
    scheduler_label: str,
    cycle_window: Tuple[int, int],
    all_issue_events: Sequence[IssueEvent],
    memory_issues: Sequence[MemoryIssue],
    all_l1_events: Sequence[L1TraceEvent],
    l1_window_events: Sequence[L1TraceEvent],
    dcache_samples: Sequence[DcacheTimeseriesSample],
    fmt: str,
) -> Path:
    warp_ids = warp_order_by_first_issue(memory_issues)
    if not warp_ids:
        raise ValueError("no warp activity found in the selected IMA window")

    selected = set(warp_ids)
    plot_issue_events = [event for event in all_issue_events if event.warp_id in selected]
    y_lookup = {warp_id: idx for idx, warp_id in enumerate(warp_ids)}

    bin_cycles = choose_status_bin_cycles(cycle_window)
    status_x, status_counts, total_counts = build_status_timeseries(l1_window_events, cycle_window, bin_cycles)

    outstanding_cycles, outstanding_counts = build_outstanding_markers(all_l1_events)
    outstanding_x = status_x
    outstanding_y = np.array(
        [outstanding_at(outstanding_cycles, outstanding_counts, int(cycle)) for cycle in outstanding_x],
        dtype=float,
    )
    outstanding_peak = max(float(outstanding_y.max()) if outstanding_y.size else 0.0, 1.0)
    outstanding_norm = outstanding_y / outstanding_peak

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(18, max(11, 7 + 0.22 * len(warp_ids))),
        sharex=True,
        gridspec_kw={"height_ratios": [3.4, 2.3, 2.6]},
    )
    warp_axis, status_axis, dcache_axis = axes

    warp_axis.scatter(
        [event.cycle for event in plot_issue_events],
        [y_lookup[event.warp_id] for event in plot_issue_events],
        s=110,
        marker="|",
        color="#9ca3af",
        alpha=0.35,
        linewidths=0.8,
        label="all issue",
    )
    for role, color in (("index_load", ROLE_COLOR["index_load"]), ("data_load", ROLE_COLOR["data_load"])):
        role_events = [event for event in memory_issues if event.role == role]
        if not role_events:
            continue
        warp_axis.scatter(
            [event.cycle for event in role_events],
            [y_lookup[event.warp_id] for event in role_events],
            s=180,
            marker="|",
            color=color,
            alpha=0.95,
            linewidths=1.5,
            label=role,
        )
    warp_axis.set_ylabel("Warp\n(first-issue order)")
    warp_axis.set_yticks(np.arange(len(warp_ids)))
    warp_axis.set_yticklabels([str(warp_id) for warp_id in warp_ids])
    warp_axis.set_title(f"{scheduler_label.upper()} dense IMA window warp order")
    warp_axis.grid(True, alpha=0.18, axis="x")
    warp_axis.legend(loc="upper right", fontsize=8, framealpha=0.92)

    cumulative = np.zeros_like(status_x, dtype=float)
    for status in L1_STATUS_ORDER:
        counts = status_counts[status].astype(float)
        ratio = np.divide(counts, np.maximum(total_counts, 1), dtype=float)
        status_axis.fill_between(
            status_x,
            cumulative,
            cumulative + ratio,
            step="mid",
            color=L1_STATUS_COLOR[status],
            alpha=0.85,
            linewidth=0.0,
            label=status.lower(),
        )
        cumulative += ratio
    status_axis.set_ylim(0.0, 1.0)
    status_axis.set_ylabel("L1 status share")
    status_axis.set_title(f"L1D status mix inside selected window (bin={bin_cycles} cycles)")
    status_axis.grid(True, alpha=0.18, axis="x")
    status_axis.legend(loc="upper right", ncol=3, fontsize=8, framealpha=0.92)

    dcache_axis.plot(
        outstanding_x,
        outstanding_norm,
        color="#111827",
        linewidth=1.8,
        label=f"normalized outstanding miss sectors (peak={int(outstanding_peak)})",
    )
    in_window_samples = [sample for sample in dcache_samples if sample.origin == "in_window"]
    proxy_samples = [sample for sample in dcache_samples if sample.origin == "nearest_snapshot"]
    if in_window_samples:
        sample_cycles = [sample.cycle for sample in in_window_samples]
        dcache_axis.step(
            sample_cycles,
            [sample.pending_hit_per_access for sample in in_window_samples],
            where="mid",
            color="#0ea5e9",
            linewidth=1.5,
            linestyle="--",
            label="pending_hit per access",
        )
        dcache_axis.step(
            sample_cycles,
            [sample.reservation_fail_per_access for sample in in_window_samples],
            where="mid",
            color="#b91c1c",
            linewidth=1.5,
            linestyle=":",
            label="reservation_fail per access",
        )
    elif proxy_samples:
        proxy = proxy_samples[0]
        dcache_axis.axhline(
            proxy.pending_hit_per_access,
            color="#0ea5e9",
            linewidth=1.5,
            linestyle="--",
            label=f"pending_hit per access (nearest snapshot @ {proxy.cycle})",
        )
        dcache_axis.axhline(
            proxy.reservation_fail_per_access,
            color="#b91c1c",
            linewidth=1.5,
            linestyle=":",
            label=f"reservation_fail per access (nearest snapshot @ {proxy.cycle})",
        )
    dcache_axis.set_ylabel("Pressure indicator")
    dcache_axis.grid(True, alpha=0.18, axis="x")

    util_axis = dcache_axis.twinx()
    if in_window_samples:
        sample_cycles = [sample.cycle for sample in in_window_samples]
        util_axis.step(
            sample_cycles,
            [sample.data_port_util for sample in in_window_samples],
            where="mid",
            color="#2563eb",
            linewidth=1.8,
            label="data_port_util",
        )
        util_axis.step(
            sample_cycles,
            [sample.fill_port_util for sample in in_window_samples],
            where="mid",
            color="#7c3aed",
            linewidth=1.8,
            label="fill_port_util",
        )
    elif proxy_samples:
        proxy = proxy_samples[0]
        util_axis.axhline(
            proxy.data_port_util,
            color="#2563eb",
            linewidth=1.8,
            label=f"data_port_util (nearest snapshot @ {proxy.cycle})",
        )
        util_axis.axhline(
            proxy.fill_port_util,
            color="#7c3aed",
            linewidth=1.8,
            label=f"fill_port_util (nearest snapshot @ {proxy.cycle})",
        )
    util_axis.set_ylim(0.0, 1.0)
    util_axis.set_ylabel("Port util")

    handles_left, labels_left = dcache_axis.get_legend_handles_labels()
    handles_right, labels_right = util_axis.get_legend_handles_labels()
    dcache_axis.legend(
        handles_left + handles_right,
        labels_left + labels_right,
        loc="upper right",
        ncol=2,
        fontsize=8,
        framealpha=0.92,
    )
    dcache_axis.set_title("Dcache pressure and port utilization")
    dcache_axis.set_xlabel("Cycle")

    for axis in axes:
        axis.set_xlim(cycle_window[0], cycle_window[1])

    window_summary = (
        f"window={cycle_window[0]}-{cycle_window[1]} | active_warps={len(warp_ids)} | "
        f"ima_issues={len(memory_issues)} | ld_events={int(total_counts.sum())}"
    )
    warp_axis.text(
        0.01,
        1.02,
        window_summary,
        transform=warp_axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
    )

    fig.tight_layout()
    out_file = out_dir / f"ima_windowed_{scheduler_label}.{fmt}"
    fig.savefig(out_file, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_file}")
    return out_file


def first_ima_entry_cycle(events: Sequence[MemoryIssue]) -> Dict[int, int]:
    entry: Dict[int, int] = {}
    by_warp: Dict[int, List[MemoryIssue]] = defaultdict(list)
    for event in events:
        by_warp[event.warp_id].append(event)
    for warp_id, warp_events in by_warp.items():
        index_cycles = [event.cycle for event in warp_events if event.role == "index_load"]
        if index_cycles:
            entry[warp_id] = min(index_cycles)
        else:
            entry[warp_id] = min(event.cycle for event in warp_events)
    return entry


def build_issue_density(
    issue_events: Sequence[IssueEvent],
    transform,
    max_bins: int = 1400,
) -> Tuple[List[float], List[int], List[float]]:
    if not issue_events:
        return [], [], []

    transformed = [(transform(event.cycle, event.warp_id), event.warp_id) for event in issue_events]
    x_values = [x for x, _ in transformed]
    x_min = min(x_values)
    x_max = max(x_values)
    span = max(1, x_max - x_min)
    bin_width = max(1, int(np.ceil((span + 1) / max_bins)))

    counts: Counter[Tuple[int, int]] = Counter()
    for x_value, warp_id in transformed:
        bin_idx = (x_value - x_min) // bin_width
        counts[(warp_id, bin_idx)] += 1

    xs: List[float] = []
    ys: List[int] = []
    sizes: List[float] = []
    for (warp_id, bin_idx), count in sorted(counts.items()):
        xs.append(x_min + bin_idx * bin_width + bin_width / 2.0)
        ys.append(warp_id)
        sizes.append(10.0 + 10.0 * np.log1p(count))
    return xs, ys, sizes


def plot_pattern_view(
    out_dir: Path,
    scheduler_label: str,
    all_issue_events: Sequence[IssueEvent],
    memory_issues: Sequence[MemoryIssue],
    fmt: str,
    aligned: bool,
) -> None:
    entry_cycle = first_ima_entry_cycle(memory_issues)
    role_events: Dict[str, List[MemoryIssue]] = defaultdict(list)
    for event in memory_issues:
        if aligned and event.warp_id not in entry_cycle:
            continue
        role_events[event.role].append(event)

    def transform(cycle: int, warp_id: int) -> int:
        if not aligned:
            return cycle
        return cycle - entry_cycle[warp_id]

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(18, 11),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 3, 2]},
    )

    for axis, role in zip(axes[:2], ROLE_ORDER):
        for status in ("HIT", "HIT_RESERVED", "MISS", "RESFAIL", "UNKNOWN"):
            style = STATUS_STYLE[status]
            role_status_events = [event for event in role_events[role] if event.initial_status == status]
            xs = [transform(event.cycle, event.warp_id) for event in role_status_events]
            ys = [event.warp_id for event in role_status_events]
            if not xs:
                continue
            axis.scatter(
                xs,
                ys,
                s=14 if status != "RESFAIL" else 20,
                marker=style["marker"],
                color=style["color"],
                alpha=0.65 if status != "UNKNOWN" else 0.35,
                linewidths=0.7,
                rasterized=False,
                label=style["label"],
            )
        axis.set_ylabel("Warp ID")
        axis.set_title(f"{scheduler_label.upper()} {role} issue pattern")
        axis.grid(True, alpha=0.18)
        axis.legend(loc="upper right", fontsize=8, framealpha=0.9)

    issue_axis = axes[2]
    issue_events_filtered = [event for event in all_issue_events if (not aligned or event.warp_id in entry_cycle)]
    issue_x, issue_y, issue_sizes = build_issue_density(issue_events_filtered, transform)
    if issue_x:
        issue_axis.scatter(
            issue_x,
            issue_y,
            s=issue_sizes,
            marker="s",
            color="#4b5563",
            alpha=0.20,
            linewidths=0,
            label="all ISSUE (binned)",
        )
    for role in ROLE_ORDER:
        xs = [transform(event.cycle, event.warp_id) for event in role_events[role]]
        ys = [event.warp_id for event in role_events[role]]
        if not xs:
            continue
        issue_axis.scatter(
            xs,
            ys,
            s=10,
            marker="o",
            color=ROLE_COLOR[role],
            alpha=0.55,
            linewidths=0,
            label=f"{role} ISSUE",
        )
    if aligned:
        for axis in axes:
            axis.axvline(0, color="#111827", linestyle="--", linewidth=1.0, alpha=0.7)
    issue_axis.set_ylabel("Warp ID")
    issue_axis.set_xlabel("Cycle" if not aligned else "Cycle since first IMA issue")
    issue_axis.set_title(f"{scheduler_label.upper()} warp issue behavior")
    issue_axis.grid(True, alpha=0.18)
    issue_axis.legend(loc="upper right", fontsize=8, framealpha=0.9)

    suffix = "aligned" if aligned else "absolute"
    fig.suptitle(f"IMA pattern view ({scheduler_label}, {suffix})", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    out_file = out_dir / f"ima_pattern_{scheduler_label}_{suffix}.{fmt}"
    fig.savefig(out_file, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_file}")


def build_chains(memory_issues: Sequence[MemoryIssue]) -> List[ChainRecord]:
    by_warp_role: Dict[Tuple[int, str], List[MemoryIssue]] = defaultdict(list)
    for event in memory_issues:
        by_warp_role[(event.warp_id, event.role)].append(event)

    chains: List[ChainRecord] = []
    scheduler_label = memory_issues[0].scheduler_label if memory_issues else "unknown"
    for warp_id in sorted({event.warp_id for event in memory_issues}):
        index_events = sorted(by_warp_role[(warp_id, "index_load")], key=lambda event: event.cycle)
        data_events = sorted(by_warp_role[(warp_id, "data_load")], key=lambda event: event.cycle)
        data_pos = 0
        chain_id = 0

        for index_event in index_events:
            data_event: Optional[MemoryIssue] = None
            search_start = index_event.completion_cycle if index_event.completion_cycle is not None else index_event.cycle
            while data_pos < len(data_events):
                candidate = data_events[data_pos]
                if candidate.cycle >= search_start:
                    data_event = candidate
                    data_pos += 1
                    break
                data_pos += 1

            complete = (
                data_event is not None
                and index_event.completion_cycle is not None
                and data_event.completion_cycle is not None
            )
            chains.append(
                ChainRecord(
                    scheduler_label=scheduler_label,
                    warp_id=warp_id,
                    chain_id=chain_id,
                    idx_issue_cycle=index_event.cycle,
                    idx_complete_cycle=index_event.completion_cycle,
                    idx_status=index_event.initial_status,
                    idx_pc=index_event.pc,
                    data_issue_cycle=data_event.cycle if data_event is not None else None,
                    data_complete_cycle=data_event.completion_cycle if data_event is not None else None,
                    data_status=data_event.initial_status if data_event is not None else None,
                    data_pc=data_event.pc if data_event is not None else None,
                    idx_to_data_gap=(
                        data_event.cycle - index_event.completion_cycle
                        if data_event is not None and index_event.completion_cycle is not None
                        else None
                    ),
                    data_service_latency=(
                        data_event.completion_cycle - data_event.cycle
                        if data_event is not None and data_event.completion_cycle is not None
                        else None
                    ),
                    complete_flag=1 if complete else 0,
                )
            )
            chain_id += 1
    return chains


def select_warps(chains: Sequence[ChainRecord], explicit_warps: Optional[Sequence[int]], top_warps: int) -> List[int]:
    if explicit_warps:
        return list(explicit_warps)
    counts: Dict[int, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    for chain in chains:
        complete, total = counts[chain.warp_id]
        counts[chain.warp_id] = (complete + chain.complete_flag, total + 1)
    ranked = sorted(counts.items(), key=lambda item: (item[1][0], item[1][1], -item[0]), reverse=True)
    return [warp_id for warp_id, _ in ranked[:top_warps]]


def cleanup_chain_outputs(out_dir: Path, scheduler_label: str, warp_id: int) -> None:
    prefix = f"ima_chain_{scheduler_label}_w{warp_id}"
    for path in sorted(out_dir.glob(f"{prefix}*")):
        if path.is_file():
            path.unlink()


def plot_chain_detail(
    out_dir: Path,
    scheduler_label: str,
    warp_id: int,
    chains: Sequence[ChainRecord],
    all_issue_events: Sequence[IssueEvent],
    fmt: str,
    max_chains_per_figure: int,
) -> None:
    cleanup_chain_outputs(out_dir, scheduler_label, warp_id)
    warp_chains = [chain for chain in chains if chain.warp_id == warp_id]
    if not warp_chains:
        print(f"  Skipping chain plot for warp {warp_id}: no chains recovered")
        return
    warp_issues = [event.cycle for event in all_issue_events if event.warp_id == warp_id]
    part_count = max(1, int(np.ceil(len(warp_chains) / max_chains_per_figure)))

    for part_idx in range(part_count):
        chunk = warp_chains[part_idx * max_chains_per_figure : (part_idx + 1) * max_chains_per_figure]
        if not chunk:
            continue
        xmin = min(chain.idx_issue_cycle for chain in chunk)
        xmax_candidates = [chain.idx_issue_cycle for chain in chunk]
        xmax_candidates.extend(chain.idx_complete_cycle for chain in chunk if chain.idx_complete_cycle is not None)
        xmax_candidates.extend(chain.data_issue_cycle for chain in chunk if chain.data_issue_cycle is not None)
        xmax_candidates.extend(chain.data_complete_cycle for chain in chunk if chain.data_complete_cycle is not None)
        xmax = max(xmax_candidates)
        margin = max(200, int((xmax - xmin) * 0.03))

        chunk_issue_cycles = [cycle for cycle in warp_issues if xmin - margin <= cycle <= xmax + margin]
        fig, (ax_issue, ax_chain) = plt.subplots(
            2,
            1,
            figsize=(18, max(8, min(18, 6 + 0.04 * len(chunk)))),
            sharex=True,
            gridspec_kw={"height_ratios": [1, 4]},
        )

        if chunk_issue_cycles:
            ax_issue.scatter(
                chunk_issue_cycles,
                np.zeros(len(chunk_issue_cycles)),
                s=24,
                marker="|",
                color="#111827",
                alpha=0.65,
                linewidths=0.9,
            )
        ax_issue.set_yticks([])
        ax_issue.set_ylabel("ISSUE")
        ax_issue.set_title(f"{scheduler_label.upper()} warp {warp_id} issue ticks")
        ax_issue.grid(True, alpha=0.18, axis="x")

        y_positions = np.arange(len(chunk))
        idx_handle = None
        data_handle = None
        for ypos, chain in zip(y_positions, chunk):
            idx_end = chain.idx_complete_cycle if chain.idx_complete_cycle is not None else chain.idx_issue_cycle
            idx_alpha = 0.8 if chain.idx_complete_cycle is not None else 0.35
            idx_container = ax_chain.barh(
                ypos,
                max(idx_end - chain.idx_issue_cycle, 1),
                left=chain.idx_issue_cycle,
                height=0.38,
                color="#93c5fd",
                edgecolor="#2563eb",
                linewidth=0.8,
                alpha=idx_alpha,
            )
            if idx_handle is None:
                idx_handle = idx_container[0]
            if chain.data_issue_cycle is not None and chain.idx_complete_cycle is not None:
                ax_chain.plot(
                    [chain.idx_complete_cycle, chain.data_issue_cycle],
                    [ypos, ypos],
                    color="#6b7280",
                    linestyle="--",
                    linewidth=1.0,
                    alpha=0.8,
                )
            if chain.data_issue_cycle is not None:
                data_end = chain.data_complete_cycle if chain.data_complete_cycle is not None else chain.data_issue_cycle
                data_alpha = 0.8 if chain.data_complete_cycle is not None else 0.35
                data_container = ax_chain.barh(
                    ypos,
                    max(data_end - chain.data_issue_cycle, 1),
                    left=chain.data_issue_cycle,
                    height=0.38,
                    color="#fdba74",
                    edgecolor="#ea580c",
                    linewidth=0.8,
                    alpha=data_alpha,
                )
                if data_handle is None:
                    data_handle = data_container[0]

        ax_chain.set_ylabel("Recovered Chain ID")
        ax_chain.set_xlabel("Cycle")
        ax_chain.set_title(
            f"{scheduler_label.upper()} warp {warp_id} IMA chain timeline\n"
            "row = index_issue -> index_complete -> data_issue -> data_complete"
        )
        ax_chain.set_yticks(y_positions)
        ax_chain.set_yticklabels([str(chain.chain_id) for chain in chunk], fontsize=8)
        ax_chain.grid(True, alpha=0.18, axis="x")
        handles = [handle for handle in (idx_handle, data_handle) if handle is not None]
        labels = ["index stage", "data stage"][: len(handles)]
        if handles:
            ax_chain.legend(handles, labels, loc="upper right")
        ax_chain.set_xlim(xmin - margin, xmax + margin)

        fig.tight_layout()
        suffix = f"_part{part_idx + 1:02d}" if part_count > 1 else ""
        out_file = out_dir / f"ima_chain_{scheduler_label}_w{warp_id}{suffix}.{fmt}"
        fig.savefig(out_file, dpi=160, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {out_file}")


def plot_scatter(out_dir: Path, scheduler_label: str, role: str, events: Sequence[MemoryIssue], fmt: str) -> None:
    role_events = [event for event in events if event.role == role and event.cachelines]
    if not role_events:
        print(f"  Skipping scatter for {scheduler_label}/{role}: no cachelines")
        return

    unique_lines = sorted({line for event in role_events for line in event.cachelines})
    line_to_rank = {line: idx for idx, line in enumerate(unique_lines)}
    access_counts = np.zeros(len(unique_lines), dtype=np.int64)
    unique_warps: List[set[int]] = [set() for _ in unique_lines]
    for event in role_events:
        for line in event.cachelines:
            rank = line_to_rank[line]
            access_counts[rank] += 1
            unique_warps[rank].add(event.warp_id)

    warp_coverage = np.array([len(warp_ids) for warp_ids in unique_warps], dtype=np.int64)
    hotness = np.sort(access_counts)[::-1]
    cumulative_share = np.cumsum(hotness) / hotness.sum()
    hotness_rank = np.arange(1, len(hotness) + 1, dtype=np.int64) / len(hotness)

    fig, (ax_dist, ax_hotness) = plt.subplots(
        2,
        1,
        figsize=(18, 10),
        gridspec_kw={"height_ratios": [3, 2]},
    )

    scatter = ax_dist.scatter(
        np.arange(len(unique_lines)),
        access_counts,
        s=18,
        c=warp_coverage,
        cmap="cividis",
        alpha=0.8,
        linewidths=0,
        rasterized=False,
    )
    ax_dist.set_yscale("log")
    ax_dist.set_xlabel("Normalized cacheline index")
    ax_dist.set_ylabel("Total touches over full trace")
    ax_dist.set_title(
        f"{scheduler_label.upper()} {role} overall cacheline footprint\n"
        "point color = number of warps touching the cacheline"
    )
    ax_dist.grid(True, alpha=0.18)
    colorbar = fig.colorbar(scatter, ax=ax_dist, pad=0.01)
    colorbar.set_label("Warp coverage")
    summary_text = (
        f"cachelines={len(unique_lines)} | total_touches={int(access_counts.sum())} | "
        f"avg_touches/line={access_counts.mean():.2f} | "
        f"avg_warps/line={warp_coverage.mean():.2f}"
    )
    ax_dist.text(
        0.01,
        0.98,
        summary_text,
        transform=ax_dist.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.88, "edgecolor": "#d1d5db"},
    )

    ax_hotness.plot(hotness_rank, cumulative_share, color=ROLE_COLOR[role], linewidth=2.2)
    ax_hotness.set_xlabel("Fraction of cachelines included, sorted by touch count")
    ax_hotness.set_ylabel("Cumulative touch share")
    ax_hotness.set_title("Hotness concentration over the full trace")
    ax_hotness.set_xlim(0.0, 1.0)
    ax_hotness.set_ylim(0.0, 1.0)
    ax_hotness.grid(True, alpha=0.18)

    fig.tight_layout()
    suffix = "index" if role == "index_load" else "data"
    out_file = out_dir / f"ima_scatter_{suffix}_{scheduler_label}.{fmt}"
    fig.savefig(out_file, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_file}")


def write_chain_csv(out_dir: Path, scheduler_label: str, chains: Sequence[ChainRecord]) -> Path:
    out_file = out_dir / f"ima_chain_detail_{scheduler_label}.csv"
    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheduler",
                "warp_id",
                "chain_id",
                "idx_issue_cycle",
                "idx_complete_cycle",
                "idx_status",
                "idx_pc",
                "data_issue_cycle",
                "data_complete_cycle",
                "data_status",
                "data_pc",
                "idx_to_data_gap",
                "data_service_latency",
                "complete_flag",
            ]
        )
        for chain in chains:
            writer.writerow(
                [
                    chain.scheduler_label,
                    chain.warp_id,
                    chain.chain_id,
                    chain.idx_issue_cycle,
                    chain.idx_complete_cycle,
                    chain.idx_status,
                    f"0x{chain.idx_pc:x}",
                    chain.data_issue_cycle,
                    chain.data_complete_cycle,
                    chain.data_status,
                    f"0x{chain.data_pc:x}" if chain.data_pc is not None else "",
                    chain.idx_to_data_gap,
                    chain.data_service_latency,
                    chain.complete_flag,
                ]
            )
    print(f"  Saved: {out_file}")
    return out_file


def compute_max_outstanding(events: Sequence[MemoryIssue]) -> int:
    markers: List[Tuple[int, int]] = []
    for event in events:
        if event.completion_cycle is None:
            continue
        markers.append((event.cycle, 1))
        markers.append((event.completion_cycle, -1))
    markers.sort()
    cur = 0
    max_cur = 0
    for _, delta in markers:
        cur += delta
        max_cur = max(max_cur, cur)
    return max_cur


def write_warp_stats(out_dir: Path, scheduler_label: str, memory_issues: Sequence[MemoryIssue], chains: Sequence[ChainRecord]) -> Path:
    chain_by_warp: Dict[int, List[ChainRecord]] = defaultdict(list)
    for chain in chains:
        chain_by_warp[chain.warp_id].append(chain)

    by_warp_role: Dict[Tuple[int, str], List[MemoryIssue]] = defaultdict(list)
    for event in memory_issues:
        by_warp_role[(event.warp_id, event.role)].append(event)

    out_file = out_dir / f"ima_warp_stats_{scheduler_label}.csv"
    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheduler",
                "warp_id",
                "idx_issue_count",
                "idx_hit_count",
                "idx_hit_reserved_count",
                "idx_miss_like_count",
                "idx_resfail_count",
                "idx_miss_like_rate",
                "avg_idx_service_cycles",
                "data_issue_count",
                "data_hit_count",
                "data_hit_reserved_count",
                "data_miss_like_count",
                "data_resfail_count",
                "data_miss_like_rate",
                "avg_data_service_cycles",
                "complete_chain_count",
                "partial_chain_count",
                "avg_idx_to_data_gap",
                "max_outstanding_mem_ops",
            ]
        )
        warp_ids = sorted({event.warp_id for event in memory_issues})
        for warp_id in warp_ids:
            row: List[object] = [scheduler_label, warp_id]
            all_events_for_warp: List[MemoryIssue] = []
            for role in ROLE_ORDER:
                events = by_warp_role[(warp_id, role)]
                all_events_for_warp.extend(events)
                counts = Counter(event.initial_status for event in events)
                total = len(events)
                miss_like = counts["MISS"]
                service_cycles = [event.issue_to_complete for event in events if event.issue_to_complete is not None]
                row.extend(
                    [
                        total,
                        counts["HIT"],
                        counts["HIT_RESERVED"],
                        miss_like,
                        counts["RESFAIL"],
                        f"{(miss_like / total):.4f}" if total else "0.0000",
                        f"{np.mean(service_cycles):.1f}" if service_cycles else "0.0",
                    ]
                )
            warp_chains = chain_by_warp.get(warp_id, [])
            complete_count = sum(chain.complete_flag for chain in warp_chains)
            partial_count = len(warp_chains) - complete_count
            gaps = [chain.idx_to_data_gap for chain in warp_chains if chain.idx_to_data_gap is not None]
            row.extend(
                [
                    complete_count,
                    partial_count,
                    f"{np.mean(gaps):.1f}" if gaps else "0.0",
                    compute_max_outstanding(all_events_for_warp),
                ]
            )
            writer.writerow(row)
    print(f"  Saved: {out_file}")
    return out_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Issue-trace-driven IMA visualization for workload-specific IMA patterns")
    parser.add_argument("--l1-trace", required=True, type=Path, help="L1 trace CSV(.gz)")
    parser.add_argument("--issue-trace", required=True, type=Path, help="Issue trace CSV(.gz)")
    parser.add_argument("--log", required=True, type=Path, help="Simulator log for runtime-stat Dcache metrics")
    parser.add_argument("--pc-class", required=True, type=Path, help="pc_classification.csv")
    parser.add_argument("--workload", default="bfs_ima_high", help="Workload key in pc_classification.csv")
    parser.add_argument("--scheduler-label", required=True, help="Scheduler label used in output filenames")
    parser.add_argument("--warp", default=None, help="Comma-separated warp IDs for chain plots")
    parser.add_argument("--cycle-range", default=None, type=parse_cycle_range, help="Optional issue cycle range start-end")
    parser.add_argument(
        "--window-bin-cycles",
        default=WINDOW_BIN_CYCLES,
        type=int,
        help="Bin size used to detect the dense IMA window (default: %(default)s)",
    )
    parser.add_argument(
        "--window-threshold",
        default=WINDOW_THRESHOLD_RATIO,
        type=float,
        help="Adjacent-bin threshold ratio for dense window detection (default: %(default)s)",
    )
    parser.add_argument(
        "--legacy-pattern",
        action="store_true",
        help="Also generate the old absolute/aligned/chain/scatter outputs",
    )
    parser.add_argument("--out-dir", required=True, type=Path, help="Figure output directory")
    parser.add_argument("--format", default="svg", choices=["svg", "png", "pdf"], help="Output format")
    parser.add_argument("--top-warps", default=4, type=int, help="Auto-select top warps by complete chain count")
    parser.add_argument("--max-chains", default=250, type=int, help="Maximum chains shown per warp detail figure before splitting into parts")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.issue_trace.is_file():
        raise SystemExit(f"missing --issue-trace file: {args.issue_trace}")
    if not args.l1_trace.is_file():
        raise SystemExit(f"missing --l1-trace file: {args.l1_trace}")
    if not args.log.is_file():
        raise SystemExit(f"missing --log file: {args.log}")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    scheduler_label = args.scheduler_label.strip().lower()
    stats_dir = out_dir.parent

    print("Loading PC classification...")
    pc_info = parse_pc_classification(args.pc_class, args.workload)
    print(f"  Found {len(pc_info)} PC entries for {args.workload}")

    print("Loading L1 trace queues...")
    initial_lookup, fill_lookup, raw_l1_events = load_l1_queues(args.l1_trace)
    print(f"  Indexed {len(initial_lookup)} initial-status queues and {len(fill_lookup)} fill queues")

    print("Loading runtime-stat Dcache snapshots...")
    l1d_total_lines, l1d_mshr_entries = parse_dl1_config(args.log)
    runtime_snapshots = parse_runtime_snapshots(args.log)
    print(
        "  Parsed "
        f"{len(runtime_snapshots)} runtime snapshots"
        + (
            f" | L1D lines={l1d_total_lines} | configured MSHRs={l1d_mshr_entries}"
            if l1d_total_lines is not None or l1d_mshr_entries is not None
            else ""
        )
    )

    print("Loading IMA memory issues from issue trace...")
    all_memory_issues = load_memory_issues(
        args.issue_trace,
        scheduler_label,
        pc_info,
        initial_lookup,
        fill_lookup,
        None,
    )
    print(f"  Matched {len(all_memory_issues)} IMA memory issues")
    if not all_memory_issues:
        raise SystemExit("No IMA memory issues matched. Check issue trace, workload, or cycle range.")

    cycle_window = (
        args.cycle_range
        if args.cycle_range is not None
        else detect_dense_window(
            all_memory_issues,
            bin_cycles=args.window_bin_cycles,
            threshold_ratio=args.window_threshold,
        )
    )
    print(f"  Dense IMA window: {cycle_window[0]}-{cycle_window[1]}")

    memory_issues = [event for event in all_memory_issues if cycle_window[0] <= event.cycle <= cycle_window[1]]
    if not memory_issues:
        raise SystemExit("Selected cycle window contains no IMA memory issues.")
    l1_window_events = filter_l1_window(raw_l1_events, cycle_window)
    write_warp_load_events(stats_dir, scheduler_label, memory_issues)
    write_warp_load_sectors(stats_dir, scheduler_label, memory_issues)

    print("Loading issue events inside the selected window...")
    all_issue_events = load_issue_events_in_window(args.issue_trace, pc_info, cycle_window)
    print(f"  Loaded {len(all_issue_events)} ISSUE events in-window")

    print("Building Dcache window summaries...")
    dcache_samples = build_dcache_timeseries(runtime_snapshots, raw_l1_events, cycle_window)
    write_window_summary(
        stats_dir,
        scheduler_label,
        cycle_window,
        memory_issues,
        l1_window_events,
        dcache_samples,
        l1d_total_lines,
        l1d_mshr_entries,
    )
    write_window_role_breakdown(
        stats_dir,
        scheduler_label,
        cycle_window,
        memory_issues,
        l1_window_events,
    )
    write_dcache_timeseries(stats_dir, scheduler_label, cycle_window, dcache_samples)

    print("Plotting dense-window view...")
    plot_windowed_view(
        out_dir,
        scheduler_label,
        cycle_window,
        all_issue_events,
        memory_issues,
        raw_l1_events,
        l1_window_events,
        dcache_samples,
        args.format,
    )

    if args.legacy_pattern:
        print("Plotting legacy pattern views...")
        plot_pattern_view(out_dir, scheduler_label, all_issue_events, memory_issues, args.format, aligned=False)
        plot_pattern_view(out_dir, scheduler_label, all_issue_events, memory_issues, args.format, aligned=True)

        print("Recovering legacy chains...")
        chains = build_chains(memory_issues)
        write_chain_csv(stats_dir, scheduler_label, chains)
        write_warp_stats(stats_dir, scheduler_label, memory_issues, chains)

        explicit_warps = [int(token) for token in args.warp.split(",")] if args.warp else None
        selected_warps = select_warps(chains, explicit_warps, args.top_warps)
        print(f"  Chain detail warps: {selected_warps}")
        for warp_id in selected_warps:
            plot_chain_detail(out_dir, scheduler_label, warp_id, chains, all_issue_events, args.format, args.max_chains)

        print("Plotting legacy cacheline statistics...")
        plot_scatter(out_dir, scheduler_label, "index_load", all_memory_issues, args.format)
        plot_scatter(out_dir, scheduler_label, "data_load", all_memory_issues, args.format)

    print("Done!")


if __name__ == "__main__":
    main()
