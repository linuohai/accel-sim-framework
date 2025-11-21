#!/usr/bin/env python3
"""
Annotate issue trace CSVs with L1 cache status information.

The script consumes issue-trace CSVs that follow the pathfinder_issue.csv format
and looks for the matching L1 trace CSV (same stem or stem without the
``_issue`` suffix) under the L1 trace directory. Each issue row receives the
extra columns ``l1_status_at_issue``, ``l1_cycle``, ``l1_sector_addresses``,
``l1_lane_ids`` and ``l1_cycle_delta`` (formatted as ``(min,max)`` deltas). Only
ISSUE-stage GLOBAL/LOCAL LOAD/STORE ops whose mask is not zero are matched, all
lanes must report HIT before the warp is classified as a hit, and the script
emits warnings whenever not all sectors are matched within the 200-cycle window
or when the L1 cycles deviate from the issue cycle by more than 100 cycles.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_L1_ROOT = SCRIPT_DIR.parent / "L1cache_trace"
DEFAULT_OUTPUT_TAG = "per_sm"

MatchKey = Tuple[str, str, str, str]
AddressKey = Tuple[str, str, str, str, str]
MEMORY_OPS = {"LOAD_OP", "STORE_OP"}
MEMORY_SPACES = {"GLOBAL", "LOCAL"}
ISSUE_TO_L1_OP = {"LOAD_OP": "LD", "STORE_OP": "ST"}
CYCLE_WARN_THRESHOLD = 200
CYCLE_SEARCH_WINDOW = 200
STATUS_PRIORITY = {
    "RESERVATION_FAIL": 3,
    "MISS": 2,
    "HIT": 1,
}


@dataclass
class L1Record:
    cycle: Optional[int]
    status: str
    lane_id: str
    address: str


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


def format_tuple_string(items: Sequence[str]) -> str:
    return "(" + ",".join(str(item) for item in items) + ")" if items else "()"


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


def consume_address_records(
    queue: Optional[List[L1Record]],
    issue_cycle: Optional[int],
    cycle_window: int,
) -> Optional[Tuple[str, Optional[int], Optional[int]]]:
    if not queue:
        return None
    min_cycle = None
    max_cycle = None
    statuses: List[str] = []
    limit = (issue_cycle + cycle_window) if issue_cycle is not None else None
    final_found = False

    idx = 0
    while idx < len(queue):
        entry = queue[idx]
        cycle_val = entry.cycle
        if issue_cycle is not None and cycle_val is not None:
            if cycle_val < issue_cycle:
                queue.pop(idx)
                continue
            if limit is not None and cycle_val > limit:
                break
        entry = queue.pop(idx)
        if not final_found:
            statuses.append(entry.status)
            if cycle_val is not None:
                if min_cycle is None or cycle_val < min_cycle:
                    min_cycle = cycle_val
                if max_cycle is None or cycle_val > max_cycle:
                    max_cycle = cycle_val
            if entry.status and entry.status != "RESERVATION_FAIL":
                final_found = True
        # discard any remaining derivative entries within the window
    if statuses:
        return classify_status_values(statuses), min_cycle, max_cycle
    return None


def load_l1_rows(l1_csv: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with l1_csv.open(newline="") as src:
        reader = csv.DictReader(src)
        rows = list(reader)
        header = reader.fieldnames or []
    return rows, header


def split_l1_trace(rows: List[Dict[str, str]], header: List[str], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not header and rows:
        header = list(rows[0].keys())
    writers: Dict[str, csv.DictWriter] = {}
    handles: List = []
    try:
        for row in rows:
            sm = row.get("sm_id", "unknown")
            writer = writers.get(sm)
            if writer is None:
                path = out_dir / f"sm_{sm}.csv"
                handle = path.open("w", newline="")
                writer = csv.DictWriter(handle, fieldnames=header)
                writer.writeheader()
                writers[sm] = writer
                handles.append(handle)
            writer.writerow(row)
    finally:
        for handle in handles:
            handle.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Annotate issue-trace CSVs with L1 cache hit/miss information and "
            "optionally split the annotated rows per SM."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python issue_trace_l1_match.py result/issue_trace/pathfinder_issue.csv \\\n"
            "      --l1-dir result/L1cache_trace --output-tag analysis\n\n"
            "Key features:\n"
            "  * Matches only ISSUE-stage GLOBAL/LOCAL load/store ops with non-zero mask\n"
            "  * Requires all lanes of a warp to hit before marking the instruction as HIT\n"
            "  * Logs cycle deltas greater than 100 cycles and dumps unmatched L1 events\n"
            "  * Can optionally split the L1 trace by SM for additional analysis\n"
            "  * Supports per-SM CSV splitting (default) or combined single-file output"
        ),
    )
    parser.add_argument(
        "issue_csvs",
        nargs="+",
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
        default="per-sm",
        help=(
            "Choose 'per-sm' to split rows into one CSV per SM (default) or "
            "'single' to emit one annotated CSV that keeps all SMs together."
        ),
    )
    parser.add_argument(
        "--split-l1-trace",
        action="store_true",
        help="Split the raw L1 trace into per-SM CSVs alongside the annotated output.",
    )
    return parser.parse_args()


def discover_l1_csv(issue_csv: Path, l1_dir: Path) -> Path:
    """Return the L1 trace CSV path that matches *issue_csv*."""
    candidates: List[Path] = []
    issue_stem = issue_csv.stem
    candidates.append(l1_dir / f"{issue_stem}.csv")
    candidates.append(l1_dir / f"{issue_stem}_l1.csv")
    if issue_stem.endswith("_issue"):
        base = issue_stem[:-6]
        candidates.append(l1_dir / f"{base}.csv")
        candidates.append(l1_dir / f"{base}_l1.csv")
    # Allow using the stem without the last suffix (e.g. foo_issue_extra)
    if "_" in issue_stem:
        prefix = issue_stem.split("_", 1)[0]
        candidates.append(l1_dir / f"{prefix}.csv")
        candidates.append(l1_dir / f"{prefix}_l1.csv")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Unable to locate matching L1 trace CSV for {issue_csv.name} "
        f"in {l1_dir}"
    )


def classify_status_values(values: Sequence[str]) -> str:
    """Reduce multiple status strings into a single label using priority order."""
    best = ""
    best_rank = -1
    for value in values:
        status = (value or "").upper()
        rank = STATUS_PRIORITY.get(status, -1)
        if rank > best_rank:
            best_rank = rank
            best = status or ""
    return best if best else "UNKNOWN"


def build_l1_queues(
    l1_rows: List[Dict[str, str]],
) -> Tuple[Dict[AddressKey, List[L1Record]], int]:
    """
    Build per-address queues sorted by cycle for nearest-cycle matching.
    """
    rows_sorted = sorted(
        l1_rows,
        key=lambda row: (
            safe_int(row.get("cycle")) if safe_int(row.get("cycle")) is not None else float("inf"),
            safe_int(row.get("warp_id")) if safe_int(row.get("warp_id")) is not None else float("inf"),
            row.get("pc", ""),
            safe_int(row.get("lane_id")) if safe_int(row.get("lane_id")) is not None else float("inf"),
        ),
    )
    queues: Dict[AddressKey, List[L1Record]] = defaultdict(list)
    total_entries = 0
    for row in rows_sorted:
        op = (row.get("op", "")).strip().upper()
        if not op.startswith(("LD", "ST")):
            continue
        key = (
            row.get("sm_id", ""),
            row.get("warp_id", ""),
            row.get("pc", ""),
            op[:2],
            row.get("address", "").strip(),
        )
        queues[key].append(
            L1Record(
                cycle=safe_int(row.get("cycle")),
                status=(row.get("l1_status", "") or "").upper(),
                lane_id=row.get("lane_id", "").strip(),
                address=row.get("address", "").strip(),
            )
        )
        total_entries += 1
    return queues, total_entries


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


class SingleFileWriterManager:
    """Manage a single csv writer used for combined output."""

    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path
        self._writer: Optional[csv.DictWriter] = None
        self._handle = None

    def get_writer(self, _sm: str, fieldnames: Sequence[str]) -> csv.DictWriter:
        if self._writer is None:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self._output_path.open("w", newline="")
            self._writer = csv.DictWriter(self._handle, fieldnames=fieldnames)
            self._writer.writeheader()
        return self._writer

    def close(self) -> None:
        if self._handle:
            self._handle.close()


def annotate_issue_trace(
    issue_csv: Path,
    l1_queues: Dict[AddressKey, List[L1Record]],
    writer_manager,
) -> Tuple[
    Dict[str, Dict[str, int]],
    Tuple[int, int],
    Tuple[int, int],
    List[Dict[str, str]],
]:
    """Stream the issue CSV, attach L1 status column, and emit rows via writer manager."""
    stats: Dict[str, Counter] = defaultdict(Counter)
    matched_loads = 0
    missing_loads = 0
    warnings: List[Dict[str, str]] = []

    try:
        with issue_csv.open(newline="") as src:
            reader = csv.DictReader(src)
            base_fields = reader.fieldnames or []
            fieldnames = list(base_fields) + [
                "l1_status_at_issue",
                "l1_cycle_delta",
            ]
            delta_ok = 0
            delta_violation = 0
            for row in reader:
                sm = row["sm"]
                stats[sm]["total_rows"] += 1
                l1_status = ""
                cycle_delta_str = ""
                op_type = row.get("OP", "")
                issue_cycle = safe_int(row.get("cycle"))
                if row.get("event") == "ISSUE" and op_type in MEMORY_OPS:
                    l1_op = ISSUE_TO_L1_OP.get(op_type)
                    if not l1_op:
                        continue
                    space = row.get("Space", "").upper()
                    if space not in MEMORY_SPACES:
                        continue
                    if mask_is_zero(row.get("mask")):
                        continue
                    stats[sm]["mem_rows"] += 1
                    expected_addresses = parse_tuple_field(
                        row.get("Issue_Sector_Addresses")
                    )
                    matched_statuses: List[str] = []
                    min_cycle = None
                    max_cycle = None
                    missing_addresses: List[str] = []
                    for addr in expected_addresses:
                        addr_key = (
                            row["sm"],
                            row["warp"],
                            row["pc"],
                            l1_op,
                            addr,
                        )
                        result = consume_address_records(
                            l1_queues.get(addr_key),
                            issue_cycle,
                            CYCLE_SEARCH_WINDOW,
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
                        warnings.append(
                            {
                                "issue_file": issue_csv.name,
                                "sm": row["sm"],
                                "warp": row["warp"],
                                "pc": row["pc"],
                                "issue_cycle": row["cycle"],
                                "missing_addresses": ";".join(missing_addresses),
                            }
                        )
                        print(
                            f"[WARN] Unable to match all sectors for SM {row['sm']} "
                            f"warp {row['warp']} at cycle {row['cycle']} "
                            f"(missing {len(missing_addresses)} sectors)"
                        )
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
                                print(
                                    "[WARN] Cycle delta > "
                                    f"{CYCLE_WARN_THRESHOLD} for SM {sm} warp {row['warp']}: "
                                    f"issue {issue_cycle}, min {min_cycle}, max {max_cycle}"
                                )
                            else:
                                delta_ok += 1
                    if matched_statuses and not missing_addresses:
                        matched_loads += 1
                        stats[sm]["mem_with_l1"] += 1
                    else:
                        if not l1_status:
                            l1_status = "NOT_FOUND"
                        missing_loads += 1
                row["l1_status_at_issue"] = l1_status
                row["l1_cycle_delta"] = cycle_delta_str
                writer = writer_manager.get_writer(sm, fieldnames)
                writer.writerow(row)
    finally:
        writer_manager.close()

    stats_dict = {
        sm: {
            "total_rows": stats[sm]["total_rows"],
            "mem_rows": stats[sm]["mem_rows"],
            "mem_with_l1": stats[sm]["mem_with_l1"],
        }
        for sm in stats
    }
    return stats_dict, (matched_loads, missing_loads), (delta_ok, delta_violation), warnings


def write_unmatched_events(
    l1_queues: Dict[AddressKey, List[L1Record]], output_path: Path
) -> int:
    remaining = sum(len(events) for events in l1_queues.values())
    if remaining == 0:
        return 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(
            [
                "sm",
                "warp",
                "pc",
                "op",
                "address",
                "cycle",
                "status",
                "lane_id",
            ]
        )
        def sort_key(item: Tuple[AddressKey, List[L1Record]]) -> Tuple[int, int, str, str, str]:
            sm, warp, pc, op, addr = item[0]
            try:
                sm_int = int(sm)
            except ValueError:
                sm_int = 1 << 20
            try:
                warp_int = int(warp)
            except ValueError:
                warp_int = 1 << 20
            return (sm_int, warp_int, pc, op, addr)

        for (sm, warp, pc, op, addr), records in sorted(
            l1_queues.items(), key=sort_key
        ):
            for rec in records:
                writer.writerow(
                    [
                        sm,
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


def write_summary(
    stats: Dict[str, Dict[str, int]], summary_path: Path, issue_name: str
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(
            ["issue_file", "sm", "total_rows", "memory_rows", "mem_with_l1"]
        )
        totals = Counter()
        def sort_key(item: Tuple[str, Dict[str, int]]) -> Tuple[int, object]:
            sm = item[0]
            try:
                return (0, int(sm))
            except ValueError:
                return (1, sm)

        for sm, metrics in sorted(stats.items(), key=sort_key):
            total_rows = metrics["total_rows"]
            mem_rows = metrics["mem_rows"]
            mem_with_l1 = metrics["mem_with_l1"]
            writer.writerow([issue_name, sm, total_rows, mem_rows, mem_with_l1])
            totals["total_rows"] += total_rows
            totals["memory_rows"] += mem_rows
            totals["mem_with_l1"] += mem_with_l1
        writer.writerow(
            [
                issue_name,
                "__TOTAL__",
                totals["total_rows"],
                totals["memory_rows"],
                totals["mem_with_l1"],
            ]
        )


def write_match_warnings(warnings: List[Dict[str, str]], output_path: Path) -> None:
    if not warnings:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as dst:
        writer = csv.DictWriter(
            dst,
            fieldnames=[
                "issue_file",
                "sm",
                "warp",
                "pc",
                "issue_cycle",
                "missing_addresses",
            ],
        )
        writer.writeheader()
        for entry in warnings:
            writer.writerow(entry)


def process_issue_file(
    issue_csv: Path,
    l1_dir: Path,
    output_tag: str,
    output_mode: str,
    split_l1: bool,
) -> None:
    issue_csv = issue_csv.resolve()
    if not issue_csv.exists():
        raise FileNotFoundError(f"{issue_csv} not found")
    l1_csv = discover_l1_csv(issue_csv, l1_dir.resolve())
    print(f"[INFO] Processing {issue_csv.name}")
    print(f"[INFO] Using L1 trace {l1_csv}")

    l1_rows, l1_header = load_l1_rows(l1_csv)
    l1_queues, total_l1_loads = build_l1_queues(l1_rows)
    print(f"[INFO] L1 trace contains {total_l1_loads} memory load/store events")

    if output_mode == "per-sm":
        output_destination = ensure_output_dir(issue_csv, output_tag)
        writer_manager = PerSMWriterManager(output_destination)
        summary_path = output_destination / "summary.csv"
        leftover_path = output_destination / "unmatched_l1_events.csv"
        l1_split_dir = output_destination / "l1_trace_per_sm"
    else:
        output_destination = issue_csv.parent / f"{issue_csv.stem}_{output_tag}.csv"
        writer_manager = SingleFileWriterManager(output_destination)
        summary_path = (
            output_destination.parent / f"{output_destination.stem}_summary.csv"
        )
        leftover_path = (
            output_destination.parent
            / f"{output_destination.stem}_unmatched_l1_events.csv"
        )
        l1_split_dir = (
            output_destination.parent
            / f"{output_destination.stem}_l1_trace_per_sm"
        )

    if split_l1:
        split_l1_trace(l1_rows, l1_header, l1_split_dir)
        print(f"[INFO] L1 trace split per SM under {l1_split_dir}")

    stats, (matched_loads, missing_loads), (delta_ok, delta_violation), warnings = annotate_issue_trace(
        issue_csv, l1_queues, writer_manager
    )
    total_issue_mem = sum(m["mem_rows"] for m in stats.values())
    print(f"[INFO] Issue trace contains {total_issue_mem} memory ISSUE rows")
    print(
        f"[INFO] Issue trace loads matched: {matched_loads}, "
        f"missing: {missing_loads}"
    )
    if matched_loads:
        print(
            f"[INFO] Cycle delta check: {delta_ok} within +/-{CYCLE_WARN_THRESHOLD}, "
            f"{delta_violation} violations"
        )
    leftover = write_unmatched_events(l1_queues, leftover_path)
    if leftover:
        print(
            f"[WARN] {leftover} load events in L1 trace were not consumed "
            f"(details in {leftover_path})"
        )
    print(
        f"[INFO] L1 trace entries consumed: {total_l1_loads - leftover} / "
        f"{total_l1_loads} (unmatched {leftover})"
    )
    warnings_path = (
        output_destination / "matching_warnings.csv"
        if output_mode == "per-sm"
        else output_destination.parent
        / f"{output_destination.stem}_matching_warnings.csv"
    )
    write_match_warnings(warnings, warnings_path)
    if warnings:
        print(
            f"[WARN] {len(warnings)} issue rows exceeded the "
            f"{CYCLE_SEARCH_WINDOW}-cycle window (details in {warnings_path})"
        )
    write_summary(stats, summary_path, issue_csv.name)
    print(f"[INFO] Output written to {output_destination}")


def main() -> None:
    args = parse_args()
    for issue_csv in args.issue_csvs:
        process_issue_file(
            issue_csv,
            args.l1_dir,
            args.output_tag,
            args.output_mode,
            args.split_l1_trace,
        )


if __name__ == "__main__":
    main()
