#!/usr/bin/env python3
"""Metadata-aware analysis for the standalone IMA tiny-case benchmark."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["svg.fonttype"] = "none"

CACHELINE_SHIFT = 7
L1_MATCH_WINDOW = 3000
ROLE_COLOR = {
    "warmup_load": "#22c55e",
    "index_load": "#2563eb",
    "data_load": "#f97316",
    "tail_load": "#a855f7",
}
PHASE_SPAN_COLOR = {
    "warmup": "#dcfce7",
    "ima": "#dbeafe",
    "tail": "#f3e8ff",
}
STATUS_PRIORITY = {
    "MISS": 4,
    "HIT_RESERVED": 3,
    "HIT": 2,
    "RESFAIL": 1,
    "UNKNOWN": 0,
}
HIT_STATUSES = {"HIT"}
HIT_RESERVED_STATUSES = {"HIT_RESERVED"}
MISS_STATUSES = {"MISS", "SECTOR_MISS"}
RESFAIL_STATUSES = {"RESERVATION_FAIL"}


@dataclass
class ArrayInfo:
    name: str
    base: int
    size_bytes: int
    element_bytes: int

    @property
    def end(self) -> int:
        return self.base + self.size_bytes

    def contains(self, addr: int) -> bool:
        return self.base <= addr < self.end


@dataclass
class L1Record:
    cycle: int
    status: str


@dataclass
class IssueEvent:
    cycle: int
    warp_id: int
    role: Optional[str]
    phase: Optional[str]


@dataclass
class MemoryIssue:
    scheduler_label: str
    scheduler_id: int
    cycle: int
    warp_id: int
    role: str
    phase: str
    pc: str
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
    data_issue_cycle: Optional[int]
    data_complete_cycle: Optional[int]
    data_status: Optional[str]
    idx_to_data_gap: Optional[int]
    data_service_latency: Optional[int]
    complete_flag: int


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
    items: List[int] = []
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze standalone IMA tiny-case traces")
    parser.add_argument("--metadata", required=True, type=Path, help="Benchmark metadata JSON")
    parser.add_argument("--l1-trace", required=True, type=Path, help="L1 trace CSV(.gz)")
    parser.add_argument("--issue-trace", required=True, type=Path, help="Issue trace CSV(.gz)")
    parser.add_argument("--scheduler-label", required=True, help="Scheduler label used in output filenames")
    parser.add_argument("--out-dir", required=True, type=Path, help="Figure output directory")
    parser.add_argument("--format", default="svg", choices=["svg", "png", "pdf"], help="Figure format")
    parser.add_argument("--plots", default="gantt", choices=["gantt", "all"], help="Plot set to generate")
    parser.add_argument("--top-warps", default=2, type=int, help="Number of chain detail warps to plot")
    return parser.parse_args()


def parse_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    raise TypeError(f"unsupported integer payload: {value!r}")


def metadata_int(info: Dict[str, object], *keys: str) -> Optional[int]:
    for key in keys:
        if key in info and info[key] is not None:
            return parse_int(info[key])
    return None


def load_metadata(path: Path) -> Dict[str, ArrayInfo]:
    with path.open() as handle:
        payload = json.load(handle)
    mapping_info = payload.get("mapping", {})
    global_element_bytes = parse_int(
        payload.get("element_size_bytes", mapping_info.get("element_bytes", 4))
    )
    arrays: Dict[str, ArrayInfo] = {}
    for key in ("warmup", "index", "data", "tail", "output"):
        info = payload["arrays"][key]
        base = metadata_int(info, "device_base", "device_base_hex", "base_uint", "base_hex")
        end = metadata_int(info, "device_end", "device_end_hex", "end_uint", "end_hex")
        size_bytes = metadata_int(info, "bytes")
        element_bytes = metadata_int(
            info,
            "element_bytes",
        ) or global_element_bytes
        if size_bytes is None and base is not None and end is not None:
            size_bytes = end - base
        if size_bytes is None:
            count = metadata_int(info, "count")
            if count is None:
                raise KeyError(f"metadata array {key} missing bytes/count")
            size_bytes = count * element_bytes
        if base is None:
            raise KeyError(f"metadata array {key} missing device base")
        arrays[key] = ArrayInfo(
            name=key,
            base=base,
            size_bytes=size_bytes,
            element_bytes=element_bytes,
        )
    return arrays


def classify_address(addr: int, arrays: Dict[str, ArrayInfo]) -> str:
    for key in ("warmup", "index", "data", "tail", "output"):
        if arrays[key].contains(addr):
            return key
    return "other"


def classify_addresses(addresses: Sequence[int], arrays: Dict[str, ArrayInfo]) -> str:
    if not addresses:
        return "other"
    counts = Counter(classify_address(addr, arrays) for addr in addresses)
    for key in ("index", "data", "warmup", "tail", "output"):
        if counts[key]:
            return key
    return "other"


def region_to_role(region: str, op: str) -> Optional[str]:
    if op != "LOAD_OP":
        return None
    mapping = {
        "warmup": "warmup_load",
        "index": "index_load",
        "data": "data_load",
        "tail": "tail_load",
    }
    return mapping.get(region)


def region_to_phase(region: str) -> Optional[str]:
    if region == "warmup":
        return "warmup"
    if region in {"index", "data"}:
        return "ima"
    if region == "tail":
        return "tail"
    return None


def load_l1_queues(path: Path) -> Tuple[Dict[Tuple[int, int], Tuple[L1Record, ...]], Dict[int, Tuple[int, ...]], List[Dict[str, object]]]:
    initial_lookup: Dict[Tuple[int, int], List[L1Record]] = defaultdict(list)
    fill_lookup: Dict[int, List[int]] = defaultdict(list)
    raw_events: List[Dict[str, object]] = []
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                cycle = int(row["cycle"])
                warp_id = int(row["warp_id"])
                addr = int(row["address"], 16)
            except (KeyError, TypeError, ValueError):
                continue
            status = row.get("l1_status", "UNKNOWN")
            raw_events.append(
                {
                    "cycle": cycle,
                    "warp_id": warp_id,
                    "op": row.get("op", "NA"),
                    "address": addr,
                    "status": status,
                }
            )
            if row.get("op") != "LD":
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
) -> Tuple[str, Optional[int], Optional[int], Optional[int], Tuple[SectorAccess, ...]]:
    statuses: List[str] = []
    initial_cycles: List[int] = []
    refill_candidates: List[int] = []
    completion_candidates: List[int] = []
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
        return "UNKNOWN", None, None, None, ()

    overall_status = max(statuses, key=lambda item: STATUS_PRIORITY[item])
    initial_cycle = min(initial_cycles) if initial_cycles else None
    refill_cycle = max(refill_candidates) if refill_candidates else None
    completion_cycle = max(completion_candidates) if completion_candidates else None
    if overall_status == "RESFAIL":
        completion_cycle = None
    return overall_status, initial_cycle, refill_cycle, completion_cycle, tuple(sector_accesses)


def load_issue_and_memory_events(
    issue_path: Path,
    arrays: Dict[str, ArrayInfo],
    scheduler_label: str,
    initial_lookup: Dict[Tuple[int, int], Tuple[L1Record, ...]],
    fill_lookup: Dict[int, Tuple[int, ...]],
) -> Tuple[List[IssueEvent], List[MemoryIssue]]:
    all_issue_events: List[IssueEvent] = []
    memory_issues: List[MemoryIssue] = []
    issue_seq_by_warp_role: Dict[Tuple[int, str], int] = defaultdict(int)
    with open_text(issue_path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("event") != "ISSUE":
                continue
            try:
                cycle = int(row.get("cycle", "0"))
                warp_id = int(row.get("warp") or row.get("warp_id") or "0")
                scheduler_id = int(row.get("scheduler", "0"))
            except ValueError:
                continue
            op = row.get("OP", "NA")
            addresses = tuple(sorted(set(parse_tuple_field(row.get("Issue_Sector_Addresses")))))
            region = classify_addresses(addresses, arrays)
            role = region_to_role(region, op)
            phase = region_to_phase(region)
            all_issue_events.append(IssueEvent(cycle=cycle, warp_id=warp_id, role=role, phase=phase))

            if role is None or not addresses or mask_is_zero(row.get("mask")):
                continue

            status, initial_cycle, refill_cycle, completion_cycle, sector_accesses = aggregate_issue_status(
                addresses, warp_id, cycle, initial_lookup, fill_lookup
            )
            issue_key = (warp_id, role)
            issue_seq = issue_seq_by_warp_role[issue_key]
            issue_seq_by_warp_role[issue_key] += 1
            memory_issues.append(
                MemoryIssue(
                    scheduler_label=scheduler_label,
                    scheduler_id=scheduler_id,
                    cycle=cycle,
                    warp_id=warp_id,
                    role=role,
                    phase=phase or "other",
                    pc=row.get("pc", "NA"),
                    issue_mask_hex=normalize_mask_hex(row.get("mask")),
                    issue_seq=issue_seq,
                    addresses=addresses,
                    cachelines=tuple(sorted({addr >> CACHELINE_SHIFT for addr in addresses})),
                    initial_status=status,
                    initial_cycle=initial_cycle,
                    refill_cycle=refill_cycle,
                    completion_cycle=completion_cycle,
                    issue_to_refill=refill_cycle - cycle if refill_cycle is not None else None,
                    issue_to_complete=completion_cycle - cycle if completion_cycle is not None else None,
                    sector_accesses=sector_accesses,
                )
            )
    return all_issue_events, memory_issues


def tracked_ima_loads(memory_issues: Sequence[MemoryIssue]) -> List[MemoryIssue]:
    role_order = {"index_load": 0, "data_load": 1}
    return sorted(
        [
            event
            for event in memory_issues
            if event.role in role_order and event.phase == "ima"
        ],
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
                    event.pc,
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
                        event.pc,
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


def compute_phase_bounds(memory_issues: Sequence[MemoryIssue]) -> Dict[str, Tuple[int, int]]:
    bounds: Dict[str, List[int]] = defaultdict(list)
    for event in memory_issues:
        bounds[event.phase].append(event.cycle)
    return {phase: (min(cycles), max(cycles)) for phase, cycles in bounds.items() if cycles}


def write_phase_summary(out_dir: Path, scheduler_label: str, memory_issues: Sequence[MemoryIssue]) -> Path:
    out_file = out_dir / f"phase_summary_{scheduler_label}.csv"
    grouped: Dict[Tuple[str, str], List[MemoryIssue]] = defaultdict(list)
    for event in memory_issues:
        grouped[(event.phase, event.role)].append(event)
    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheduler",
                "phase",
                "role",
                "issue_count",
                "hit_count",
                "hit_reserved_count",
                "miss_like_count",
                "resfail_count",
                "unknown_count",
                "avg_service_cycles",
                "avg_sectors_per_issue",
                "first_cycle",
                "last_cycle",
            ]
        )
        for (phase, role), events in sorted(grouped.items()):
            counts = Counter(event.initial_status for event in events)
            latencies = [event.issue_to_complete for event in events if event.issue_to_complete is not None]
            writer.writerow(
                [
                    scheduler_label,
                    phase,
                    role,
                    len(events),
                    counts["HIT"],
                    counts["HIT_RESERVED"],
                    counts["MISS"],
                    counts["RESFAIL"],
                    counts["UNKNOWN"],
                    f"{np.mean(latencies):.1f}" if latencies else "0.0",
                    f"{np.mean([len(event.addresses) for event in events]):.2f}",
                    min(event.cycle for event in events),
                    max(event.cycle for event in events),
                ]
            )
    print(f"  Saved: {out_file}")
    return out_file


def write_ima_summary(out_dir: Path, scheduler_label: str, memory_issues: Sequence[MemoryIssue]) -> Path:
    out_file = out_dir / f"ima_region_summary_{scheduler_label}.csv"
    grouped: Dict[str, List[MemoryIssue]] = defaultdict(list)
    for event in memory_issues:
        if event.phase == "ima":
            grouped[event.role].append(event)
    with out_file.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scheduler",
                "role",
                "issue_count",
                "hit_count",
                "hit_reserved_count",
                "miss_like_count",
                "resfail_count",
                "unknown_count",
                "miss_like_rate",
                "avg_service_cycles",
                "avg_sectors_per_issue",
            ]
        )
        for role in ("index_load", "data_load"):
            events = grouped.get(role, [])
            counts = Counter(event.initial_status for event in events)
            latencies = [event.issue_to_complete for event in events if event.issue_to_complete is not None]
            total = len(events)
            writer.writerow(
                [
                    scheduler_label,
                    role,
                    total,
                    counts["HIT"],
                    counts["HIT_RESERVED"],
                    counts["MISS"],
                    counts["RESFAIL"],
                    counts["UNKNOWN"],
                    f"{(counts['MISS'] / total):.4f}" if total else "0.0000",
                    f"{np.mean(latencies):.1f}" if latencies else "0.0",
                    f"{np.mean([len(event.addresses) for event in events]):.2f}" if events else "0.00",
                ]
            )
    print(f"  Saved: {out_file}")
    return out_file


def build_chains(memory_issues: Sequence[MemoryIssue]) -> List[ChainRecord]:
    by_warp_role: Dict[Tuple[int, str], List[MemoryIssue]] = defaultdict(list)
    for event in memory_issues:
        if event.phase != "ima":
            continue
        by_warp_role[(event.warp_id, event.role)].append(event)

    chains: List[ChainRecord] = []
    scheduler_label = memory_issues[0].scheduler_label if memory_issues else "unknown"
    for warp_id in sorted({event.warp_id for event in memory_issues if event.phase == "ima"}):
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
                    data_issue_cycle=data_event.cycle if data_event is not None else None,
                    data_complete_cycle=data_event.completion_cycle if data_event is not None else None,
                    data_status=data_event.initial_status if data_event is not None else None,
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


def write_chain_summary(out_dir: Path, scheduler_label: str, chains: Sequence[ChainRecord]) -> Path:
    out_file = out_dir / f"chain_summary_{scheduler_label}.csv"
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
                "data_issue_cycle",
                "data_complete_cycle",
                "data_status",
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
                    chain.data_issue_cycle,
                    chain.data_complete_cycle,
                    chain.data_status,
                    chain.idx_to_data_gap,
                    chain.data_service_latency,
                    chain.complete_flag,
                ]
            )
    print(f"  Saved: {out_file}")
    return out_file


def select_top_warps(chains: Sequence[ChainRecord], top_warps: int) -> List[int]:
    ranked = Counter(chain.warp_id for chain in chains if chain.complete_flag)
    return [warp_id for warp_id, _ in ranked.most_common(top_warps)]


def select_gantt_warps(all_issue_events: Sequence[IssueEvent], memory_issues: Sequence[MemoryIssue], limit: int = 8) -> List[int]:
    warp_ids = sorted({event.warp_id for event in all_issue_events})
    if not warp_ids:
        warp_ids = sorted({event.warp_id for event in memory_issues})
    return warp_ids[:limit]


def plot_warp_gantt(
    out_dir: Path,
    scheduler_label: str,
    all_issue_events: Sequence[IssueEvent],
    memory_issues: Sequence[MemoryIssue],
    fmt: str,
) -> None:
    warp_ids = select_gantt_warps(all_issue_events, memory_issues, limit=8)
    if not warp_ids:
        return

    phase_bounds = compute_phase_bounds(memory_issues)
    selected = set(warp_ids)
    full_events = [event for event in all_issue_events if event.warp_id in selected]
    if not full_events:
        return

    y_lookup = {warp_id: idx for idx, warp_id in enumerate(warp_ids)}
    full_cycles = [event.cycle for event in full_events]
    full_start = min(full_cycles)
    full_end = max(full_cycles)
    full_margin = max(100, int((full_end - full_start) * 0.02))

    ima_start, ima_end = phase_bounds.get("ima", (full_start, full_end))
    zoom_margin = max(100, int((ima_end - ima_start) * 0.05)) if ima_end > ima_start else 100

    fig, (ax_full, ax_zoom) = plt.subplots(
        2,
        1,
        figsize=(18, max(7.5, 5 + 0.6 * len(warp_ids))),
        sharey=True,
        gridspec_kw={"height_ratios": [3, 2]},
    )

    def paint_phase_spans(axis: plt.Axes) -> None:
        for phase in ("warmup", "ima", "tail"):
            if phase not in phase_bounds:
                continue
            start, end = phase_bounds[phase]
            alpha = 0.34 if phase == "ima" else 0.12
            label = f"{phase} region"
            axis.axvspan(start, end, color=PHASE_SPAN_COLOR[phase], alpha=alpha, label=label)

    def paint_issue_ticks(axis: plt.Axes) -> None:
        axis.scatter(
            [event.cycle for event in full_events],
            [y_lookup[event.warp_id] for event in full_events],
            s=100,
            marker="|",
            color="#9ca3af",
            alpha=0.45,
            linewidths=0.9,
            label="all issue",
        )
        for role, color in (("index_load", "#2563eb"), ("data_load", "#ea580c")):
            role_events = [event for event in memory_issues if event.warp_id in selected and event.role == role]
            if not role_events:
                continue
            axis.scatter(
                [event.cycle for event in role_events],
                [y_lookup[event.warp_id] for event in role_events],
                s=160,
                marker="|",
                color=color,
                alpha=0.95,
                linewidths=1.4,
                label=role,
            )

    for axis in (ax_full, ax_zoom):
        paint_phase_spans(axis)
        paint_issue_ticks(axis)
        axis.set_yticks(np.arange(len(warp_ids)))
        axis.set_yticklabels([str(warp_id) for warp_id in warp_ids])
        axis.set_ylabel("Warp ID")
        axis.grid(True, alpha=0.18, axis="x")

    ax_full.set_title(f"{scheduler_label.upper()} 8-warp issue gantt")
    ax_full.set_xlim(full_start - full_margin, full_end + full_margin)

    ax_zoom.set_title("IMA region zoom")
    ax_zoom.set_xlim(ima_start - zoom_margin, ima_end + zoom_margin)
    ax_zoom.set_xlabel("Cycle")

    handles, labels = ax_full.get_legend_handles_labels()
    seen = set()
    filtered_handles = []
    filtered_labels = []
    for handle, label in zip(handles, labels):
        if label in seen:
            continue
        seen.add(label)
        filtered_handles.append(handle)
        filtered_labels.append(label)
    ax_full.legend(filtered_handles, filtered_labels, loc="upper right", fontsize=8, framealpha=0.92)

    fig.tight_layout()
    out_file = out_dir / f"warp_gantt_{scheduler_label}.{fmt}"
    fig.savefig(out_file, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_file}")


def plot_phase_timeline(
    out_dir: Path,
    scheduler_label: str,
    all_issue_events: Sequence[IssueEvent],
    memory_issues: Sequence[MemoryIssue],
    fmt: str,
) -> None:
    fig, ax = plt.subplots(figsize=(18, 8))
    ax.scatter(
        [event.cycle for event in all_issue_events],
        [event.warp_id for event in all_issue_events],
        s=8,
        color="#d1d5db",
        alpha=0.35,
        linewidths=0,
        label="all issue",
    )
    for role in ("warmup_load", "index_load", "data_load", "tail_load"):
        events = [event for event in memory_issues if event.role == role]
        if not events:
            continue
        ax.scatter(
            [event.cycle for event in events],
            [event.warp_id for event in events],
            s=20 if role in {"index_load", "data_load"} else 14,
            color=ROLE_COLOR[role],
            alpha=0.9,
            linewidths=0,
            label=role,
        )
    for phase, (start, end) in compute_phase_bounds(memory_issues).items():
        ax.axvspan(start, end, color=PHASE_SPAN_COLOR[phase], alpha=0.25, label=f"{phase} region")
    ax.set_xlabel("Cycle")
    ax.set_ylabel("Warp ID")
    ax.set_title(f"{scheduler_label.upper()} tiny-case phase timeline")
    ax.grid(True, alpha=0.18)
    handles, labels = ax.get_legend_handles_labels()
    seen = set()
    filtered_handles = []
    filtered_labels = []
    for handle, label in zip(handles, labels):
        if label in seen:
            continue
        seen.add(label)
        filtered_handles.append(handle)
        filtered_labels.append(label)
    ax.legend(filtered_handles, filtered_labels, loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    out_file = out_dir / f"phase_timeline_{scheduler_label}.{fmt}"
    fig.savefig(out_file, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_file}")


def plot_chain_detail(
    out_dir: Path,
    scheduler_label: str,
    warp_id: int,
    chains: Sequence[ChainRecord],
    all_issue_events: Sequence[IssueEvent],
    fmt: str,
) -> None:
    warp_chains = [chain for chain in chains if chain.warp_id == warp_id]
    if not warp_chains:
        return
    warp_issues = [event.cycle for event in all_issue_events if event.warp_id == warp_id]
    xmin = min(chain.idx_issue_cycle for chain in warp_chains)
    xmax_candidates = [chain.idx_issue_cycle for chain in warp_chains]
    xmax_candidates.extend(chain.idx_complete_cycle for chain in warp_chains if chain.idx_complete_cycle is not None)
    xmax_candidates.extend(chain.data_issue_cycle for chain in warp_chains if chain.data_issue_cycle is not None)
    xmax_candidates.extend(chain.data_complete_cycle for chain in warp_chains if chain.data_complete_cycle is not None)
    xmax = max(xmax_candidates)
    margin = max(200, int((xmax - xmin) * 0.03))

    fig, (ax_issue, ax_chain) = plt.subplots(
        2,
        1,
        figsize=(18, max(8, min(18, 6 + 0.04 * len(warp_chains)))),
        sharex=True,
        gridspec_kw={"height_ratios": [1, 4]},
    )
    ax_issue.scatter(
        warp_issues,
        np.zeros(len(warp_issues)),
        s=22,
        marker="|",
        color="#111827",
        alpha=0.65,
        linewidths=0.9,
    )
    ax_issue.set_yticks([])
    ax_issue.set_ylabel("ISSUE")
    ax_issue.set_title(f"{scheduler_label.upper()} warp {warp_id} issue ticks")
    ax_issue.grid(True, alpha=0.18, axis="x")

    y_positions = np.arange(len(warp_chains))
    for ypos, chain in zip(y_positions, warp_chains):
        idx_end = chain.idx_complete_cycle if chain.idx_complete_cycle is not None else chain.idx_issue_cycle
        ax_chain.barh(
            ypos,
            max(idx_end - chain.idx_issue_cycle, 1),
            left=chain.idx_issue_cycle,
            height=0.38,
            color="#93c5fd",
            edgecolor="#2563eb",
            linewidth=0.8,
            alpha=0.8 if chain.idx_complete_cycle is not None else 0.35,
        )
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
            ax_chain.barh(
                ypos,
                max(data_end - chain.data_issue_cycle, 1),
                left=chain.data_issue_cycle,
                height=0.38,
                color="#fdba74",
                edgecolor="#ea580c",
                linewidth=0.8,
                alpha=0.8 if chain.data_complete_cycle is not None else 0.35,
            )
    ax_chain.set_ylabel("Recovered Chain ID")
    ax_chain.set_xlabel("Cycle")
    ax_chain.set_title(
        f"{scheduler_label.upper()} warp {warp_id} IMA chain timeline\n"
        "row = index_issue -> index_complete -> data_issue -> data_complete"
    )
    ax_chain.set_yticks(y_positions)
    ax_chain.set_yticklabels([str(chain.chain_id) for chain in warp_chains], fontsize=8)
    ax_chain.grid(True, alpha=0.18, axis="x")
    ax_chain.set_xlim(xmin - margin, xmax + margin)
    fig.tight_layout()
    out_file = out_dir / f"ima_chain_{scheduler_label}_w{warp_id}.{fmt}"
    fig.savefig(out_file, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_file}")


def plot_cacheline_stats(
    out_dir: Path,
    scheduler_label: str,
    role: str,
    memory_issues: Sequence[MemoryIssue],
    fmt: str,
) -> None:
    role_events = [event for event in memory_issues if event.role == role and event.cachelines]
    if not role_events:
        return
    unique_lines = sorted({line for event in role_events for line in event.cachelines})
    line_to_rank = {line: idx for idx, line in enumerate(unique_lines)}
    access_counts = np.zeros(len(unique_lines), dtype=np.int64)
    warp_coverage: List[set[int]] = [set() for _ in unique_lines]
    for event in role_events:
        for line in event.cachelines:
            rank = line_to_rank[line]
            access_counts[rank] += 1
            warp_coverage[rank].add(event.warp_id)

    warp_coverage_arr = np.array([len(item) for item in warp_coverage], dtype=np.int64)
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
        c=warp_coverage_arr,
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

    ax_hotness.plot(hotness_rank, cumulative_share, color=ROLE_COLOR[role], linewidth=2.2)
    ax_hotness.set_xlabel("Fraction of cachelines included, sorted by touch count")
    ax_hotness.set_ylabel("Cumulative touch share")
    ax_hotness.set_title("Hotness concentration over the full trace")
    ax_hotness.set_xlim(0.0, 1.0)
    ax_hotness.set_ylim(0.0, 1.0)
    ax_hotness.grid(True, alpha=0.18)
    fig.tight_layout()
    suffix = "index" if role == "index_load" else "data"
    out_file = out_dir / f"overall_cacheline_{suffix}_{scheduler_label}.{fmt}"
    fig.savefig(out_file, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_file}")


def cleanup_optional_outputs(out_dir: Path, stats_dir: Path, scheduler_label: str) -> None:
    stale_files = [
        stats_dir / f"chain_summary_{scheduler_label}.csv",
    ]
    stale_globs = [
        f"phase_timeline_{scheduler_label}.*",
        f"ima_chain_{scheduler_label}_w*.*",
        f"overall_cacheline_index_{scheduler_label}.*",
        f"overall_cacheline_data_{scheduler_label}.*",
    ]
    for path in stale_files:
        if path.exists():
            path.unlink()
    for pattern in stale_globs:
        for path in out_dir.glob(pattern):
            path.unlink()


def main() -> None:
    args = parse_args()
    arrays = load_metadata(args.metadata)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    scheduler_label = args.scheduler_label.strip().lower()
    stats_dir = out_dir.parent

    print("Loading L1 trace queues...")
    initial_lookup, fill_lookup, _ = load_l1_queues(args.l1_trace)
    print(f"  Indexed {len(initial_lookup)} initial-status queues and {len(fill_lookup)} fill queues")

    print("Loading issue + memory events...")
    all_issue_events, memory_issues = load_issue_and_memory_events(
        args.issue_trace,
        arrays,
        scheduler_label,
        initial_lookup,
        fill_lookup,
    )
    print(f"  Loaded {len(all_issue_events)} issue events and {len(memory_issues)} classified memory issues")
    if not memory_issues:
        raise SystemExit("No classified memory issues matched benchmark arrays.")

    print("Writing summaries...")
    write_phase_summary(stats_dir, scheduler_label, memory_issues)
    write_ima_summary(stats_dir, scheduler_label, memory_issues)
    write_warp_load_events(stats_dir, scheduler_label, memory_issues)
    write_warp_load_sectors(stats_dir, scheduler_label, memory_issues)

    if args.plots != "all":
        cleanup_optional_outputs(out_dir, stats_dir, scheduler_label)

    print("Plotting warp gantt...")
    plot_warp_gantt(out_dir, scheduler_label, all_issue_events, memory_issues, args.format)

    if args.plots == "all":
        chains = build_chains(memory_issues)
        write_chain_summary(stats_dir, scheduler_label, chains)

        print("Plotting legacy phase timeline...")
        plot_phase_timeline(out_dir, scheduler_label, all_issue_events, memory_issues, args.format)

        selected_warps = select_top_warps(chains, args.top_warps)
        print(f"  Chain detail warps: {selected_warps}")
        for warp_id in selected_warps:
            plot_chain_detail(out_dir, scheduler_label, warp_id, chains, all_issue_events, args.format)

        print("Plotting overall cacheline statistics...")
        plot_cacheline_stats(out_dir, scheduler_label, "index_load", memory_issues, args.format)
        plot_cacheline_stats(out_dir, scheduler_label, "data_load", memory_issues, args.format)
    print("Done!")


if __name__ == "__main__":
    main()
