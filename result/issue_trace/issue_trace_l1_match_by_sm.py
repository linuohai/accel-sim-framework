#!/usr/bin/env python3
"""
Annotate issue trace CSVs with L1 cache status information using per-SM matching
and low-memory streaming.

Differences vs issue_trace_l1_match:
  * issue and L1 traces are split per SM and processed one SM at a time to bound
    memory usage (at the cost of extra I/O)
  * unmatched rows are recorded in CSVs without printing warning lines to
    stdout
  * an extra shadow-access check records instructions that share
    (pc, warp, lane, address) within an SM but occur at different cycles

Outputs match the original script, plus a shadow report CSV.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from heapq import heappop, heappush
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_L1_ROOT = SCRIPT_DIR.parent / "L1cache_trace"
DEFAULT_OUTPUT_TAG = "with_l1trace"

AddressKey = Tuple[str, str, str, str, str]
ShadowKey = Tuple[str, str, str, str]

MEMORY_OPS = {"LOAD_OP", "STORE_OP"}
MEMORY_SPACES = {"GLOBAL", "LOCAL"}
ISSUE_TO_L1_OP = {"LOAD_OP": "LD", "STORE_OP": "ST"}
CYCLE_SEARCH_WINDOW = 3000
CYCLE_WARN_THRESHOLD = CYCLE_SEARCH_WINDOW
STATUS_PRIORITY = {
    "RESERVATION_FAIL": 3,
    "MISS": 2,
    "HIT": 1,
}
SHADOW_FILE_NAME = "shadow_accesses.csv"


@dataclass
class L1Record:
    cycle: Optional[int]
    status: str
    lane_id: str
    address: str


@dataclass
class ShadowState:
    cycles: set
    ops: set
    spaces: set


def shadow_state_factory() -> ShadowState:
    return ShadowState(set(), set(), set())


def safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value, 0)
    except (TypeError, ValueError):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def mask_is_zero(mask_value: Optional[str]) -> bool:
    if mask_value is None:
        return True
    mask_str = mask_value.strip()
    if not mask_str:
        return True
    if mask_str.lower().startswith("0x"):
        try:
            return int(mask_str, 16) == 0
        except ValueError:
            return mask_str == "0x0"
    try:
        return int(mask_str) == 0
    except ValueError:
        return False


def parse_tuple_field(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    value = raw.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    if not value:
        return []
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item]


def detect_sm_value(row: Dict[str, str]) -> str:
    return (
        row.get("sm")
        or row.get("sm_id")
        or row.get("SM")
        or row.get("smid")
        or "unknown"
    )


def detect_warp_value(row: Dict[str, str]) -> str:
    return (
        row.get("warp")
        or row.get("warp_id")
        or row.get("warpId")
        or row.get("warp_id_i")
        or ""
    )


def detect_pc_value(row: Dict[str, str]) -> str:
    return row.get("pc") or row.get("PC") or row.get("pc_val") or ""


def detect_lane_value(row: Dict[str, str]) -> str:
    return row.get("lane_id") or row.get("lane") or row.get("laneId") or ""


def detect_address_value(row: Dict[str, str]) -> str:
    return row.get("address") or row.get("addr") or ""


def sm_sort_key(sm: str) -> Tuple[int, object]:
    try:
        return (0, int(sm))
    except (TypeError, ValueError):
        return (1, sm)


def discover_l1_csv(issue_csv: Path, l1_dir: Path) -> Path:
    candidates: List[Path] = []
    issue_stem = issue_csv.stem
    candidates.append(l1_dir / f"{issue_stem}_l1.csv")
    if issue_stem.endswith("_issue"):
        base = issue_stem[:-6]
        candidates.append(l1_dir / f"{base}_l1.csv")
    if "_" in issue_stem:
        prefix = issue_stem.split("_", 1)[0]
        candidates.append(l1_dir / f"{prefix}_l1.csv")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Unable to locate matching L1 trace CSV for {issue_csv.name} "
        f"in {l1_dir}"
    )


def classify_status_values(values: Sequence[str]) -> str:
    best = ""
    best_rank = -1
    for value in values:
        status = (value or "").upper()
        rank = STATUS_PRIORITY.get(status, -1)
        if rank > best_rank:
            best_rank = rank
            best = status or ""
    return best if best else "UNKNOWN"


def consume_address_records(
    queue: Optional[List[L1Record]],
    issue_cycle: Optional[int],
    cycle_window: Optional[int],
) -> Optional[Tuple[str, Optional[int], Optional[int]]]:
    if not queue:
        return None
    # Drop stale entries that happened before the issue cycle.
    while queue:
        head = queue[0]
        if issue_cycle is not None and head.cycle is not None and head.cycle < issue_cycle:
            queue.pop(0)
            continue
        break
    if not queue:
        return None

    limit = (issue_cycle + cycle_window) if (issue_cycle is not None and cycle_window is not None) else None

    def over_limit(cycle_val: Optional[int]) -> bool:
        return limit is not None and cycle_val is not None and cycle_val > limit

    min_cycle = None
    max_cycle = None
    first = queue[0]

    if over_limit(first.cycle):
        return None

    if first.status == "RESERVATION_FAIL":
        status = "RESERVATION_FAIL"
        while queue:
            entry = queue[0]
            cycle_val = entry.cycle
            if over_limit(cycle_val):
                break
            entry = queue.pop(0)
            if cycle_val is not None:
                if min_cycle is None or cycle_val < min_cycle:
                    min_cycle = cycle_val
                if max_cycle is None or cycle_val > max_cycle:
                    max_cycle = cycle_val
            if entry.status != "RESERVATION_FAIL":
                # Consume the first non-reservation entry as part of the same request.
                break
        return status, min_cycle, max_cycle

    entry = queue.pop(0)
    cycle_val = entry.cycle
    if cycle_val is not None:
        min_cycle = max_cycle = cycle_val
    return entry.status or "UNKNOWN", min_cycle, max_cycle


def ensure_output_dir(issue_csv: Path, output_tag: str) -> Path:
    out_dir = issue_csv.parent / f"{issue_csv.stem}_{output_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


class PerSMWriterManager:
    """Manage csv writers for per-SM output files."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._writers: Dict[str, csv.DictWriter] = {}
        self._handles: List = []

    def get_writer(self, sm: str, fieldnames: Sequence[str]) -> csv.DictWriter:
        writer = self._writers.get(sm)
        if writer:
            return writer
        out_path = self._output_dir / f"sm_{sm}.csv"
        handle = out_path.open("w", newline="")
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        self._writers[sm] = writer
        self._handles.append(handle)
        return writer

    def close(self) -> None:
        for handle in self._handles:
            handle.close()


def stream_issue_to_temp(issue_csv: Path, temp_dir: Path) -> Tuple[List[str], Dict[str, Path]]:
    """Split the issue trace into per-SM temp files with row indices."""
    temp_paths: Dict[str, Path] = {}
    writers: Dict[str, csv.DictWriter] = {}
    handles = []
    header: List[str] = []
    try:
        with issue_csv.open(newline="") as src:
            reader = csv.DictReader(src)
            header = reader.fieldnames or []
            for idx, row in enumerate(reader):
                sm = str(detect_sm_value(row))
                row["_row_index"] = str(idx)
                writer = writers.get(sm)
                if writer is None:
                    path = temp_dir / f"issue_sm_{sm}.csv"
                    handle = path.open("w", newline="")
                    writer = csv.DictWriter(handle, fieldnames=header + ["_row_index"])
                    writer.writeheader()
                    writers[sm] = writer
                    temp_paths[sm] = path
                    handles.append(handle)
                writer.writerow(row)
    finally:
        for handle in handles:
            handle.close()
    return header, temp_paths


def stream_l1_to_temp(l1_csv: Path, temp_dir: Path) -> Tuple[List[str], Dict[str, Path]]:
    """Split the L1 trace into per-SM temp files."""
    temp_paths: Dict[str, Path] = {}
    writers: Dict[str, csv.DictWriter] = {}
    handles = []
    header: List[str] = []
    try:
        with l1_csv.open(newline="") as src:
            reader = csv.DictReader(src)
            header = reader.fieldnames or []
            for row in reader:
                sm = detect_sm_value(row)
                sm_str = str(sm)
                writer = writers.get(sm_str)
                if writer is None:
                    path = temp_dir / f"l1_sm_{sm_str}.csv"
                    handle = path.open("w", newline="")
                    writer = csv.DictWriter(handle, fieldnames=header)
                    writer.writeheader()
                    writers[sm_str] = writer
                    temp_paths[sm_str] = path
                    handles.append(handle)
                writer.writerow(row)
    finally:
        for handle in handles:
            handle.close()
    return header, temp_paths


def build_l1_queues_for_sm(l1_path: Path, sm_id: str) -> Tuple[Dict[AddressKey, List[L1Record]], int]:
    queues: Dict[AddressKey, List[L1Record]] = defaultdict(list)
    total_entries = 0
    with l1_path.open(newline="") as src:
        reader = csv.DictReader(src)
        # Assume the L1 trace is already chronological; split by address key without
        # a second full sort to reduce memory and runtime.
        for row in reader:
            op = (row.get("op", "")).strip().upper()
            if not op.startswith(("LD", "ST")):
                continue
            warp_val = detect_warp_value(row)
            pc_val = detect_pc_value(row)
            lane_val = detect_lane_value(row)
            address_val = detect_address_value(row)
            key = (
                sm_id,
                warp_val,
                pc_val,
                op[:2],
                address_val.strip(),
            )
            queues[key].append(
                L1Record(
                    cycle=safe_int(row.get("cycle")),
                    status=(row.get("l1_status", "") or "").upper(),
                    lane_id=str(lane_val).strip(),
                    address=str(address_val).strip(),
                )
            )
            total_entries += 1
    return queues, total_entries


def emit_unmatched_events_for_sm(
    sm: str, queues: Dict[AddressKey, List[L1Record]], writer: csv.writer
) -> int:
    remaining = sum(len(events) for events in queues.values())
    if remaining == 0:
        return 0

    def sort_key(item: Tuple[AddressKey, List[L1Record]]) -> Tuple[int, int, str, str, str]:
        sm_val, warp, pc, op, addr = item[0]
        try:
            sm_int = int(sm_val)
        except ValueError:
            sm_int = 1 << 20
        try:
            warp_int = int(warp)
        except ValueError:
            warp_int = 1 << 20
        return (sm_int, warp_int, pc, op, addr)

    for (sm_val, warp, pc, op, addr), records in sorted(queues.items(), key=sort_key):
        for rec in records:
            writer.writerow(
                [
                    sm_val,
                    warp,
                    pc,
                    op,
                    addr,
                    rec.cycle if rec.cycle is not None else "",
                    rec.status,
                    rec.lane_id,
                ]
            )
    return remaining


def emit_shadow_entries_for_sm(
    shadow_map: Dict[ShadowKey, ShadowState],
    issue_name: str,
    sm: str,
    writer: csv.DictWriter,
) -> int:
    count = 0
    for (warp, pc, lane, addr), state in shadow_map.items():
        if len(state.cycles) <= 1:
            continue
        entry = {
            "issue_file": issue_name,
            "sm": sm,
            "warp": warp,
            "pc": pc,
            "lane": lane,
            "address": addr,
            "ops": ";".join(sorted(state.ops)),
            "spaces": ";".join(sorted(state.spaces)),
            "cycles": ";".join(str(c) for c in sorted(state.cycles)),
            "count": str(len(state.cycles)),
        }
        writer.writerow(entry)
        count += 1
    return count


def process_sm(
    sm: str,
    issue_path: Optional[Path],
    l1_path: Optional[Path],
    writer_manager: Optional[PerSMWriterManager],
    annotated_temp_dir: Optional[Path],
    fieldnames: Sequence[str],
    warnings_writer: csv.DictWriter,
    shadow_writer: csv.DictWriter,
    leftover_writer: csv.writer,
    issue_name: str,
    output_mode: str,
) -> Tuple[Dict[str, int], Tuple[int, int], Tuple[int, int], int, int, int, Optional[Path]]:
    stats_counter: Counter = Counter()
    matched_loads = 0
    missing_loads = 0
    delta_ok = 0
    delta_violation = 0
    warnings_count = 0
    shadow_count = 0
    annotated_path: Optional[Path] = None

    queues: Dict[AddressKey, List[L1Record]] = {}
    total_l1_entries = 0
    if l1_path and l1_path.exists():
        queues, total_l1_entries = build_l1_queues_for_sm(l1_path, sm)

    shadow_map: Dict[ShadowKey, ShadowState] = defaultdict(shadow_state_factory)

    writer = None
    annotated_fieldnames = list(fieldnames)
    if output_mode == "single":
        annotated_fieldnames.append("_row_index")
        if issue_path and issue_path.exists():
            annotated_path = annotated_temp_dir / f"annotated_sm_{sm}.csv"
            annotated_handle = annotated_path.open("w", newline="")
            writer = csv.DictWriter(annotated_handle, fieldnames=annotated_fieldnames)
            writer.writeheader()
            writer_handle = annotated_handle
        else:
            writer_handle = None
    else:
        writer = writer_manager.get_writer(sm, fieldnames)
        writer_handle = None

    try:
        if issue_path and issue_path.exists():
            with issue_path.open(newline="") as src:
                reader = csv.DictReader(src)
                for local_idx, row in enumerate(reader):
                    if "_row_index" not in row or row["_row_index"] is None:
                        row["_row_index"] = str(local_idx)
                    stats_counter["total_rows"] += 1
                    l1_status = ""
                    cycle_delta_str = ""
                    op_type = row.get("OP", "")
                    issue_cycle = safe_int(row.get("cycle"))
                    if row.get("event") == "ISSUE" and op_type in MEMORY_OPS:
                        l1_op = ISSUE_TO_L1_OP.get(op_type)
                        space = row.get("Space", "").upper()
                        if l1_op and space in MEMORY_SPACES and not mask_is_zero(row.get("mask")):
                            stats_counter["mem_rows"] += 1
                            expected_addresses = parse_tuple_field(row.get("Issue_Sector_Addresses"))
                            expected_lanes = parse_tuple_field(row.get("Issue_Sector_Lanes"))
                            if expected_lanes and len(expected_lanes) < len(expected_addresses):
                                expected_lanes.extend([""] * (len(expected_addresses) - len(expected_lanes)))
                            elif not expected_lanes:
                                expected_lanes = [""] * len(expected_addresses)

                            matched_statuses: List[str] = []
                            missing_addresses: List[str] = []
                            min_cycle = None
                            max_cycle = None

                            for addr, lane in zip(expected_addresses, expected_lanes):
                                shadow_state = shadow_map[(row.get("warp", ""), row.get("pc", ""), lane, addr)]
                                if issue_cycle is not None:
                                    shadow_state.cycles.add(issue_cycle)
                                shadow_state.ops.add(op_type)
                                shadow_state.spaces.add(row.get("Space", ""))

                                addr_key = (
                                    sm,
                                    row.get("warp", ""),
                                    row.get("pc", ""),
                                    l1_op,
                                    addr,
                                )
                                result = consume_address_records(
                                    queues.get(addr_key),
                                    issue_cycle,
                                    None,
                                )
                                if result is None:
                                    missing_addresses.append(addr)
                                    continue
                                status, addr_min_cycle, addr_max_cycle = result
                                matched_statuses.append(status)
                                if addr_min_cycle is not None:
                                    if min_cycle is None or addr_min_cycle < min_cycle:
                                        min_cycle = addr_min_cycle
                                if addr_max_cycle is not None:
                                    if max_cycle is None or addr_max_cycle > max_cycle:
                                        max_cycle = addr_max_cycle

                            if missing_addresses:
                                warnings_writer.writerow(
                                    {
                                        "issue_file": issue_name,
                                        "sm": row.get("sm", ""),
                                        "warp": row.get("warp", ""),
                                        "pc": row.get("pc", ""),
                                        "issue_cycle": row.get("cycle", ""),
                                        "missing_addresses": ";".join(missing_addresses),
                                    }
                                )
                                warnings_count += 1
                            if matched_statuses:
                                l1_status = classify_status_values(matched_statuses)
                                if (
                                    issue_cycle is not None
                                    and min_cycle is not None
                                    and max_cycle is not None
                                ):
                                    min_delta = min_cycle - issue_cycle
                                    max_delta = max_cycle - issue_cycle
                                    cycle_delta_str = f"({min_delta},{max_delta})"
                                    if (
                                        abs(min_delta) > CYCLE_WARN_THRESHOLD
                                        or abs(max_delta) > CYCLE_WARN_THRESHOLD
                                    ):
                                        delta_violation += 1
                                    else:
                                        delta_ok += 1
                            if matched_statuses and not missing_addresses:
                                matched_loads += 1
                                stats_counter["mem_with_l1"] += 1
                            else:
                                if not l1_status:
                                    l1_status = "NOT_FOUND"
                                missing_loads += 1
                    row["l1_status_at_issue"] = l1_status
                    row["l1_cycle_delta"] = cycle_delta_str
                    if writer:
                        if output_mode == "per-sm":
                            writer.writerow({k: v for k, v in row.items() if k != "_row_index"})
                        else:
                            writer.writerow(row)
    finally:
        if writer_handle:
            writer_handle.close()

    shadow_count = emit_shadow_entries_for_sm(shadow_map, issue_name, sm, shadow_writer)
    unmatched_count = emit_unmatched_events_for_sm(sm, queues, leftover_writer)

    stats_dict = {
        "total_rows": stats_counter["total_rows"],
        "mem_rows": stats_counter["mem_rows"],
        "mem_with_l1": stats_counter["mem_with_l1"],
        "l1_entries": total_l1_entries,
    }
    return (
        stats_dict,
        (matched_loads, missing_loads),
        (delta_ok, delta_violation),
        warnings_count,
        shadow_count,
        unmatched_count,
        annotated_path,
    )


def merge_single_output(
    annotated_paths: Dict[str, Path],
    output_path: Path,
    fieldnames: Sequence[str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handles = {}
    heap: List[Tuple[int, int, str, Dict[str, str]]] = []
    seq = 0
    try:
        for sm, path in annotated_paths.items():
            handle = path.open(newline="")
            reader = csv.DictReader(handle)
            handles[sm] = (handle, reader)
            try:
                first = next(reader)
            except StopIteration:
                continue
            first_idx = safe_int(first.get("_row_index")) or 0
            heappush(heap, (first_idx, seq, sm, first))
            seq += 1

        with output_path.open("w", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=fieldnames)
            writer.writeheader()
            while heap:
                _, _, sm, row = heappop(heap)
                writer.writerow({k: v for k, v in row.items() if k != "_row_index"})
                handle, reader = handles[sm]
                try:
                    nxt = next(reader)
                except StopIteration:
                    continue
                nxt_idx = safe_int(nxt.get("_row_index")) or 0
                heappush(heap, (nxt_idx, seq, sm, nxt))
                seq += 1
    finally:
        for handle, _ in handles.values():
            handle.close()
        for path in annotated_paths.values():
            path.unlink(missing_ok=True)


def split_csv_by_sm(csv_path: Path, out_dir: Optional[Path] = None) -> Path:
    csv_path = csv_path.resolve()
    if out_dir is None:
        out_dir = csv_path.parent / csv_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    writers: Dict[str, csv.DictWriter] = {}
    handles: List = []
    try:
        with csv_path.open(newline="") as src:
            reader = csv.DictReader(src)
            header = reader.fieldnames or []
            for row in reader:
                sm = str(detect_sm_value(row))
                writer = writers.get(sm)
                if writer is None:
                    handle = (out_dir / f"sm_{sm}.csv").open("w", newline="")
                    writer = csv.DictWriter(handle, fieldnames=header)
                    writer.writeheader()
                    writers[sm] = writer
                    handles.append(handle)
                writer.writerow(row)
    finally:
        for handle in handles:
            handle.close()
    return out_dir


def load_sm_split_dir(directory: Path) -> Dict[str, Path]:
    if not directory.exists():
        raise FileNotFoundError(f"{directory} not found")
    paths: Dict[str, Path] = {}
    for path in directory.iterdir():
        if path.is_file() and path.name.startswith("sm_") and path.suffix == ".csv":
            sm = path.stem[3:]
            paths[sm] = path
    if not paths:
        raise ValueError(f"No sm_*.csv files found under {directory}")
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Annotate issue-trace CSVs with L1 cache hit/miss information using "
            "per-SM matching and emit shadow-access diagnostics."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python issue_trace_l1_match_by_sm.py result/issue_trace/pathfinder_issue.csv \\\n"
            "      --l1-dir result/L1cache_trace --output-tag analysis\n\n"
            "Key features:\n"
            "  * Splits issue and L1 traces per SM before matching\n"
            "  * Matches only ISSUE-stage GLOBAL/LOCAL load/store ops with non-zero mask\n"
            "  * Records unmatched sectors and L1 leftovers to CSV without printing warnings\n"
            "  * Emits shadow accesses (same pc/warp/lane/address, different cycles) per SM\n"
            "  * Supports combined single-file output (default) or per-SM CSV splitting\n"
            "  * Can split any CSV by SM as a standalone utility (--split-only)\n"
        ),
    )
    parser.add_argument(
        "issue_csvs",
        nargs="*",
        type=Path,
        help="One or more issue trace CSV files (e.g. pathfinder_issue.csv)",
    )
    parser.add_argument(
        "--l1-dir",
        type=Path,
        default=DEFAULT_L1_ROOT,
        help=(
            "Directory that stores the L1 trace CSVs "
            f"(default: {DEFAULT_L1_ROOT})"
        ),
    )
    parser.add_argument(
        "--output-tag",
        default=DEFAULT_OUTPUT_TAG,
        help=(
            "Suffix appended to the issue CSV stem to form the output "
            "directory name (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--output-mode",
        choices=("per-sm", "single"),
        default="single",
        help=(
            "Choose 'per-sm' to split rows into one CSV per SM or "
            "'single' (default) to emit one annotated CSV that keeps all SMs together."
        ),
    )
    parser.add_argument(
        "--split-l1-trace",
        action="store_true",
        help="Split the raw L1 trace into per-SM CSVs alongside the annotated output.",
    )
    parser.add_argument(
        "--issue-per-sm-dir",
        type=Path,
        help="Use an existing per-SM issue directory (sm_*.csv) instead of splitting the issue CSV.",
    )
    parser.add_argument(
        "--l1-per-sm-dir",
        type=Path,
        help="Use an existing per-SM L1 directory (sm_*.csv) instead of splitting the L1 CSV.",
    )
    parser.add_argument(
        "--split-only",
        nargs="*",
        type=Path,
        help=(
            "Split the provided CSV files by SM into <stem>/sm_<id>.csv and exit. "
            "Works for any CSV that has an SM column."
        ),
    )
    return parser.parse_args()


def process_issue_file(
    issue_csv: Path,
    l1_dir: Path,
    output_tag: str,
    output_mode: str,
    split_l1: bool,
    issue_per_sm_dir: Optional[Path] = None,
    l1_per_sm_dir: Optional[Path] = None,
) -> None:
    issue_csv = issue_csv.resolve()
    if not issue_csv.exists():
        raise FileNotFoundError(f"{issue_csv} not found")
    l1_csv = discover_l1_csv(issue_csv, l1_dir.resolve())
    print(f"[INFO] Processing {issue_csv.name}")
    print(f"[INFO] Using L1 trace {l1_csv}")

    temp_dir = Path(
        tempfile.mkdtemp(prefix=f"{issue_csv.stem}_{output_tag}_", dir=issue_csv.parent)
    )

    try:
        if issue_per_sm_dir:
            issue_temp_paths = load_sm_split_dir(issue_per_sm_dir)
            sample_file = next(iter(issue_temp_paths.values()))
            with sample_file.open(newline="") as src:
                reader = csv.DictReader(src)
                issue_header = reader.fieldnames or []
        else:
            issue_header, issue_temp_paths = stream_issue_to_temp(issue_csv, temp_dir)

        if l1_per_sm_dir:
            l1_temp_paths = load_sm_split_dir(l1_per_sm_dir)
            sample_file = next(iter(l1_temp_paths.values()))
            with sample_file.open(newline="") as src:
                reader = csv.DictReader(src)
                l1_header = reader.fieldnames or []
        else:
            l1_header, l1_temp_paths = stream_l1_to_temp(l1_csv, temp_dir)

        if output_mode == "per-sm":
            output_destination = ensure_output_dir(issue_csv, output_tag)
            writer_manager = PerSMWriterManager(output_destination)
            leftover_path = output_destination / "unmatched_l1_events.csv"
            l1_split_dir = output_destination / "l1_trace_per_sm"
            warnings_path = output_destination / "matching_warnings.csv"
            shadow_path = output_destination / SHADOW_FILE_NAME
            annotated_temp_dir = None
        else:
            output_destination = issue_csv.parent / f"{issue_csv.stem}_{output_tag}.csv"
            writer_manager = None
            leftover_path = (
                output_destination.parent
                / f"{output_destination.stem}_unmatched_l1_events.csv"
            )
            l1_split_dir = (
                output_destination.parent
                / f"{output_destination.stem}_l1_trace_per_sm"
            )
            warnings_path = (
                output_destination.parent
                / f"{output_destination.stem}_matching_warnings.csv"
            )
            shadow_path = (
                output_destination.parent
                / f"{output_destination.stem}_{SHADOW_FILE_NAME}"
            )
            annotated_temp_dir = temp_dir

        if split_l1:
            if l1_per_sm_dir:
                print(f"[INFO] Using existing per-SM L1 under {l1_per_sm_dir}")
            else:
                l1_split_dir.mkdir(parents=True, exist_ok=True)
                for sm, path in l1_temp_paths.items():
                    target = l1_split_dir / f"sm_{sm}.csv"
                    shutil.copy(path, target)
                print(f"[INFO] L1 trace split per SM under {l1_split_dir}")

        base_fields = [
            field
            for field in issue_header
            if field not in ("l1_status_at_issue", "l1_cycle_delta")
        ]
        fieldnames = base_fields + ["l1_status_at_issue", "l1_cycle_delta"]

        warnings_handle = warnings_path.open("w", newline="")
        warnings_writer = csv.DictWriter(
            warnings_handle,
            fieldnames=[
                "issue_file",
                "sm",
                "warp",
                "pc",
                "issue_cycle",
                "missing_addresses",
            ],
        )
        warnings_writer.writeheader()

        leftover_handle = leftover_path.open("w", newline="")
        leftover_writer = csv.writer(leftover_handle)
        leftover_writer.writerow(
            ["sm", "warp", "pc", "op", "address", "cycle", "status", "lane_id"]
        )

        shadow_handle = shadow_path.open("w", newline="")
        shadow_writer = csv.DictWriter(
            shadow_handle,
            fieldnames=[
                "issue_file",
                "sm",
                "warp",
                "pc",
                "lane",
                "address",
                "ops",
                "spaces",
                "cycles",
                "count",
            ],
        )
        shadow_writer.writeheader()

        annotated_temp_paths: Dict[str, Path] = {}
        total_issue_mem = 0
        total_matched = 0
        total_missing = 0
        total_delta_ok = 0
        total_delta_violation = 0
        total_warnings = 0
        total_shadow = 0
        total_unmatched = 0
        total_l1_events = 0

        try:
            all_sms = sorted(set(issue_temp_paths.keys()) | set(l1_temp_paths.keys()), key=sm_sort_key)
            for sm in all_sms:
                (
                    stats,
                    (matched_loads, missing_loads),
                    (delta_ok, delta_violation),
                    warnings_count,
                    shadow_count,
                    unmatched_count,
                    annotated_path,
                ) = process_sm(
                    sm,
                    issue_temp_paths.get(sm),
                    l1_temp_paths.get(sm),
                    writer_manager,
                    annotated_temp_dir,
                    fieldnames,
                    warnings_writer,
                    shadow_writer,
                    leftover_writer,
                    issue_csv.name,
                    output_mode,
                )
                total_issue_mem += stats.get("mem_rows", 0)
                total_l1_events += stats.get("l1_entries", 0)
                total_matched += matched_loads
                total_missing += missing_loads
                total_delta_ok += delta_ok
                total_delta_violation += delta_violation
                total_warnings += warnings_count
                total_shadow += shadow_count
                total_unmatched += unmatched_count
                if annotated_path:
                    annotated_temp_paths[sm] = annotated_path
        finally:
            warnings_handle.close()
            leftover_handle.close()
            shadow_handle.close()
            if writer_manager:
                writer_manager.close()

        if output_mode == "single":
            merge_single_output(annotated_temp_paths, output_destination, fieldnames)
        print(f"[INFO] L1 trace contains {total_l1_events} memory load/store events")
        print(f"[INFO] Issue trace contains {total_issue_mem} memory ISSUE rows")
        print(
            f"[INFO] Issue trace loads matched: {total_matched}, "
            f"missing: {total_missing}"
        )
        if total_matched:
            print(
                f"[INFO] Cycle delta check: {total_delta_ok} within +/-{CYCLE_WARN_THRESHOLD}, "
                f"{total_delta_violation} violations"
            )
        if total_unmatched:
            print(
                f"[INFO] Unmatched L1 events written to {leftover_path} ({total_unmatched} rows)"
            )
        if total_warnings:
            print(
                f"[INFO] {total_warnings} issue rows missing one or more sectors "
                f"(details in {warnings_path})"
            )
        if total_shadow:
            print(
                f"[INFO] Detected {total_shadow} shadow access groups "
                f"(details in {shadow_path})"
            )
        else:
            print(f"[INFO] No shadow accesses detected (shadow report saved to {shadow_path})")

        print(f"[INFO] Output written to {output_destination}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    args = parse_args()
    if args.split_only:
        for csv_path in args.split_only:
            out_dir = split_csv_by_sm(csv_path)
            print(f"[INFO] Split {csv_path} by SM under {out_dir}")
        return
    if not args.issue_csvs:
        raise SystemExit("No issue CSVs provided (and --split-only not used)")
    for issue_csv in args.issue_csvs:
        process_issue_file(
            issue_csv,
            args.l1_dir,
            args.output_tag,
            args.output_mode,
            args.split_l1_trace,
            args.issue_per_sm_dir,
            args.l1_per_sm_dir,
        )


if __name__ == "__main__":
    main()
