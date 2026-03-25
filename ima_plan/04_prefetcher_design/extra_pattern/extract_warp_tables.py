#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import re
from bisect import bisect_left
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple


CACHELINE_SHIFT = 7
L1_MATCH_WINDOW = 3000
WINDOW_BIN_CYCLES = 5000
WINDOW_THRESHOLD_RATIO = 0.6
ROLE_ORDER = ("index_load", "data_load")
MISS_STATUSES = {"MISS", "SECTOR_MISS"}
HIT_RESERVED_STATUSES = {"HIT_RESERVED"}
HIT_STATUSES = {"HIT"}
RESFAIL_STATUSES = {"RESERVATION_FAIL"}
STATUS_PRIORITY = {"MISS": 4, "HIT_RESERVED": 3, "HIT": 2, "RESFAIL": 1, "UNKNOWN": 0}
L2_STATUS_PRIORITY = {
    "MISS": 6,
    "SECTOR_MISS": 5,
    "MSHR_HIT": 4,
    "HIT_RESERVED": 3,
    "HIT": 2,
    "RESERVATION_FAIL": 1,
    "UNKNOWN": 0,
}
LOAD_OPCODE_PREFIXES = ("LDG",)
SASS_ANALYSIS_DIR = Path("ima_plan/01_ima_characterization/sass_analysis/core_cases")
SASS_ROLE_CONFIGS = {
    "bfs": {
        "sass_path": SASS_ANALYSIS_DIR / "bfs_linear_base.sm80.sass",
        "source_matches": (
            {
                "function_symbols": {"_Z10bfs_kerneliPKmPKiPi9Worklist2S4_"},
                "file_suffix": "/bfs/linear_base.cu",
                "line": 19,
                "role": "index_load",
            },
            {
                "function_symbols": {"_Z10bfs_kerneliPKmPKiPi9Worklist2S4_"},
                "file_suffix": "/bfs/linear_base.cu",
                "line": 20,
                "role": "data_load",
            },
            {
                "function_symbols": {"_Z10bfs_kerneliPKmPKiPi9Worklist2S4_"},
                "file_suffix": "/bfs/linear_base.cu",
                "line": 21,
                "role": "data_load",
            },
        ),
    },
    "sssp": {
        "sass_path": SASS_ANALYSIS_DIR / "sssp_linear_base.sm80.sass",
        "source_matches": (
            {
                "function_symbols": {"_Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_"},
                "file_suffix": "/sssp/linear_base.cu",
                "line": 39,
                "role": "index_load",
            },
            {
                "function_symbols": {"_Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_"},
                "file_suffix": "/sssp/linear_base.cu",
                "line": 40,
                "role": "data_load",
            },
            {
                "function_symbols": {"_Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_"},
                "file_suffix": "/sssp/linear_base.cu",
                "line": 41,
                "role": "data_load",
            },
        ),
    },
    "cc": {
        "sass_path": SASS_ANALYSIS_DIR / "cc_base.sm80.sass",
        "source_matches": (
            {
                "function_symbols": {"_Z4hookiPKmPKiPiPb"},
                "file_suffix": "/cc/base.cu",
                "line": 17,
                "role": "index_load",
            },
            {
                "function_symbols": {"_Z4hookiPKmPKiPiPb"},
                "file_suffix": "sm_32_intrinsics.hpp",
                "line": 112,
                "role": "data_load",
            },
        ),
    },
    "bc": {
        "sass_path": SASS_ANALYSIS_DIR / "bc_linear_base.sm80.sass",
        "source_matches": (
            {
                "function_symbols": {"_Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_"},
                "file_suffix": "/bc/linear_base.cu",
                "line": 52,
                "role": "index_load",
            },
            {
                "function_symbols": {"_Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_"},
                "file_suffix": "/bc/linear_base.cu",
                "line": 53,
                "role": "data_load",
            },
            {
                "function_symbols": {"_Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_"},
                "file_suffix": "/bc/linear_base.cu",
                "line": 56,
                "role": "data_load",
            },
            {
                "function_symbols": {"_Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_"},
                "file_suffix": "/bc/linear_base.cu",
                "line": 57,
                "role": "data_load",
            },
            {
                "function_symbols": {"_Z10bc_reverseiPKmPKiS2_S2_S2_iPfS3_"},
                "file_suffix": "/bc/linear_base.cu",
                "line": 77,
                "role": "index_load",
            },
            {
                "function_symbols": {"_Z10bc_reverseiPKmPKiS2_S2_S2_iPfS3_"},
                "file_suffix": "/bc/linear_base.cu",
                "line": 78,
                "role": "data_load",
            },
            {
                "function_symbols": {"_Z10bc_reverseiPKmPKiS2_S2_S2_iPfS3_"},
                "file_suffix": "/bc/linear_base.cu",
                "line": 80,
                "role": "data_load",
            },
        ),
    },
    "spmv": {
        "sass_path": SASS_ANALYSIS_DIR / "spmv_base.sm80.sass",
        "source_matches": (
            {
                "function_symbols": {"_Z15spmv_csr_scalariPKmPKiPKfS4_Pf"},
                "file_suffix": "/spmv/base.cu",
                "line": 22,
                "role": "data_load",
            },
        ),
    },
}
WORKLOAD_TO_SASS_KEY = {
    "bfs_ima_high": "bfs",
    "bfs_ima_med": "bfs",
    "bfs_ima_small": "bfs",
    "bfs_cit_ima": "bfs",
    "bfs_web": "bfs",
    "bfs_flickr": "bfs",
    "bfs_roadnet": "bfs",
    "bfs_usa": "bfs",
    "sssp_ima_high": "sssp",
    "sssp_ima_med": "sssp",
    "sssp_ima_small": "sssp",
    "sssp_cit_ima": "sssp",
    "sssp_cit_ima_nosym": "sssp",
    "cc_ima_high": "cc",
    "cc_ima_med": "cc",
    "cc_ima_small": "cc",
    "cc_cit_ima": "cc",
    "bc_ima_high": "bc",
    "bc_ima_med": "bc",
    "bc_ima_small": "bc",
    "bc_cit_ima": "bc",
    "bc_ima_high_forward": "bc_forward",
    "bc_ima_high_reverse": "bc_reverse",
    "bc_ima_small_forward": "bc_forward",
    "bc_ima_small_reverse": "bc_reverse",
    "bc_cit_ima_forward": "bc_forward",
    "bc_cit_ima_reverse": "bc_reverse",
    "spmv_ima_high": "spmv",
    "spmv_ima_small": "spmv",
    "spmv_cit_ima": "spmv",
}
STATIC_PAIR_CONFIGS = {
    "bfs": (
        ("p00", 0x01D0, 0x0200),
        ("p01", 0x0640, 0x0670),
        ("p02", 0x09A0, 0x09D0),
        ("p03", 0x0D00, 0x0D30),
        ("p04", 0x1060, 0x1090),
    ),
    "cc": (
        ("p00", 0x01B0, 0x01E0),
        ("p01", 0x0390, 0x03C0),
        ("p02", 0x04B0, 0x04D0),
        ("p03", 0x05C0, 0x05E0),
        ("p04", 0x06D0, 0x06F0),
    ),
    "bc_forward": (
        ("f00", 0x01D0, 0x0200),
        ("f01", 0x06E0, 0x0710),
        ("f02", 0x0AE0, 0x0B10),
        ("f03", 0x0ED0, 0x0F00),
        ("f04", 0x12C0, 0x12F0),
    ),
    "bc_reverse": (
        ("r00", 0x0200, 0x0230),
        ("r01", 0x0520, 0x0550),
        ("r02", 0x0740, 0x0770),
        ("r03", 0x0960, 0x0990),
        ("r04", 0x0B80, 0x0BB0),
    ),
    "sssp": (
        ("p00", 0x0250, 0x02A0),
        ("p01", 0x05D0, 0x0610),
        ("p02", 0x07E0, 0x0820),
        ("p03", 0x09E0, 0x0A20),
        ("p04", 0x0BE0, 0x0C20),
    ),
    "spmv": (
        ("p00", 0x0200, 0x0250),
        ("p01", 0x03D0, 0x04A0),
        ("p02", 0x03E0, 0x04C0),
        ("p03", 0x03F0, 0x04D0),
        ("p04", 0x0400, 0x0510),
        ("p05", 0x0410, 0x0530),
        ("p06", 0x0440, 0x05D0),
        ("p07", 0x0460, 0x0600),
        ("p08", 0x0470, 0x0620),
        ("p09", 0x0520, 0x0680),
        ("p10", 0x0550, 0x0730),
        ("p11", 0x0570, 0x0770),
        ("p12", 0x0650, 0x07A0),
        ("p13", 0x0670, 0x07D0),
        ("p14", 0x06A0, 0x0840),
        ("p15", 0x06B0, 0x0820),
        ("p16", 0x06C0, 0x0850),
        ("p17", 0x09A0, 0x0A60),
        ("p18", 0x09B0, 0x0A80),
        ("p19", 0x09C0, 0x0AA0),
        ("p20", 0x09D0, 0x0AD0),
        ("p21", 0x09E0, 0x0B10),
        ("p22", 0x09F0, 0x0B40),
        ("p23", 0x0A00, 0x0B60),
        ("p24", 0x0A10, 0x0B80),
        ("p25", 0x0CC0, 0x0D60),
        ("p26", 0x0CD0, 0x0D80),
        ("p27", 0x0CE0, 0x0DA0),
        ("p28", 0x0CF0, 0x0DB0),
    ),
}
WINDOW_MARKER_PCS = {
    "bc_forward": {0x01D0, 0x06E0, 0x0710, 0x0AE0, 0x0B10, 0x0ED0, 0x0F00, 0x12C0, 0x12F0},
    "bc_reverse": {0x0230, 0x0520, 0x0550, 0x0740, 0x0770, 0x0960, 0x0990, 0x0B80, 0x0BB0},
}


@dataclass
class IssueRecord:
    sm_id: int
    role: str
    warp_id: int
    issue_seq: int
    issue_cycle: int
    scheduler_id: int
    pc: int
    pair_id: Optional[str]
    mask_hex: str
    addresses: Tuple[int, ...]
    cachelines: Tuple[int, ...]


@dataclass
class L1Record:
    cycle: int
    status: str


@dataclass
class L2Record:
    cycle: int
    status: str
    hbm_bw_gbps: Optional[float]
    hbm_occupancy: Optional[float]
    sm_alu_utilization: Optional[float]


@dataclass
class IssueSummary:
    issue: IssueRecord
    first_status: str
    refill_cycle: Optional[int]
    issue_to_refill: Optional[int]
    l2_first_status: str
    l2_first_cycle: Optional[int]
    l2_hbm_bw_gbps: Optional[float]
    l2_hbm_occupancy: Optional[float]
    l2_sm_alu_utilization: Optional[float]


@dataclass
class ChainRecord:
    workload: str
    scheduler_label: str
    sm_id: int
    warp_id: int
    static_pair_id: str
    dynamic_seq: int
    index_pc: str
    index_issue_cycle: Optional[int]
    index_status: str
    index_refill_cycle: Optional[int]
    index_issue_to_refill: Optional[int]
    data_pc: str
    data_issue_cycle: Optional[int]
    index_issue_to_data_issue: Optional[int]
    refill_to_data_issue: Optional[int]
    data_status: str
    data_refill_cycle: Optional[int]
    data_issue_to_refill: Optional[int]
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


def get_static_pair_maps(workload: str) -> Tuple[Dict[int, str], Dict[int, str], Dict[str, Tuple[int, int]]]:
    sass_key = WORKLOAD_TO_SASS_KEY.get(workload, workload)
    pair_defs = STATIC_PAIR_CONFIGS.get(sass_key, ())
    pc_to_role: Dict[int, str] = {}
    pc_to_pair: Dict[int, str] = {}
    pair_to_pcs: Dict[str, Tuple[int, int]] = {}
    for pair_id, index_pc, data_pc in pair_defs:
        pc_to_role[index_pc] = "index_load"
        pc_to_role[data_pc] = "data_load"
        pc_to_pair[index_pc] = pair_id
        pc_to_pair[data_pc] = pair_id
        pair_to_pcs[pair_id] = (index_pc, data_pc)
    return pc_to_role, pc_to_pair, pair_to_pcs


def get_window_marker_pcs(workload: str) -> Optional[set[int]]:
    sass_key = WORKLOAD_TO_SASS_KEY.get(workload, workload)
    marker_pcs = WINDOW_MARKER_PCS.get(sass_key)
    if not marker_pcs:
        return None
    return set(marker_pcs)


def parse_sass_role_map(workload: str) -> Dict[int, str]:
    static_pc_to_role, _, _ = get_static_pair_maps(workload)
    if static_pc_to_role:
        return static_pc_to_role

    sass_key = WORKLOAD_TO_SASS_KEY.get(workload, workload)
    config = SASS_ROLE_CONFIGS.get(sass_key)
    if config is None:
        return {}

    sass_path = config["sass_path"]
    source_matches = config["source_matches"]
    pc_to_role: Dict[int, str] = {}
    current_symbol: Optional[str] = None
    current_line: Optional[int] = None
    current_source: Optional[str] = None

    for raw_line in sass_path.read_text(errors="ignore").splitlines():
        line = raw_line.strip()
        if line.startswith(".text.") and line.endswith(":"):
            current_symbol = line[len(".text.") : -1]
            current_line = None
            continue
        if line.startswith("_Z") and line.endswith(":"):
            current_symbol = line[:-1]
            current_line = None
            continue

        match = re.search(r'//## File "([^"]+)", line (\d+)', raw_line)
        if match:
            current_source = match.group(1)
            current_line = int(match.group(2))
            continue

        match = re.search(r"/\*([0-9a-fA-F]+)\*/\s+([A-Z0-9_.]+)", raw_line)
        if not match or current_symbol is None or current_source is None or current_line is None:
            continue

        opcode = match.group(2)
        if not opcode.startswith(LOAD_OPCODE_PREFIXES):
            continue

        for source_match in source_matches:
            if current_symbol not in source_match["function_symbols"]:
                continue
            if not current_source.endswith(source_match["file_suffix"]):
                continue
            if current_line != source_match["line"]:
                continue
            pc_to_role[int(match.group(1), 16)] = source_match["role"]
            break

    return pc_to_role


def parse_pc_classification(path: Path, workload: str) -> Dict[int, str]:
    pc_to_role = parse_sass_role_map(workload)
    if pc_to_role:
        return pc_to_role

    default_source_line_to_role = {
        "linear_base.cu:19": "index_load",
        "linear_base.cu:20": "data_load",
        "linear_base.cu:21": "data_load",
    }
    workload_source_line_to_role = {
        "bfs_ima_high": default_source_line_to_role,
        "bfs_ima_med": default_source_line_to_role,
        "bfs_ima_small": default_source_line_to_role,
        "sssp_ima_high": {
            "linear_base.cu:39": "index_load",
            "linear_base.cu:40": "data_load",
        },
        "sssp_ima_med": {
            "linear_base.cu:39": "index_load",
            "linear_base.cu:40": "data_load",
        },
        "sssp_ima_small": {
            "linear_base.cu:39": "index_load",
            "linear_base.cu:40": "data_load",
        },
        "cc_ima_high": {
            "base.cu:17": "index_load",
            "base.cu:19": "data_load",
        },
        "cc_ima_med": {
            "base.cu:17": "index_load",
            "base.cu:19": "data_load",
        },
        "cc_ima_small": {
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
        "bc_ima_med": {
            "linear_base.cu:52": "index_load",
            "linear_base.cu:53": "data_load",
            "linear_base.cu:56": "data_load",
            "linear_base.cu:57": "data_load",
            "linear_base.cu:77": "index_load",
            "linear_base.cu:78": "data_load",
            "linear_base.cu:80": "data_load",
        },
        "bc_ima_small": {
            "linear_base.cu:52": "index_load",
            "linear_base.cu:53": "data_load",
            "linear_base.cu:56": "data_load",
            "linear_base.cu:57": "data_load",
            "linear_base.cu:77": "index_load",
            "linear_base.cu:78": "data_load",
            "linear_base.cu:80": "data_load",
        },
    }
    source_line_to_role = workload_source_line_to_role.get(workload, default_source_line_to_role)
    pc_to_role: Dict[int, str] = {}
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("workload") != workload:
                continue
            pc_hex = (row.get("pc") or "").strip()
            if not pc_hex:
                continue
            source = row.get("source_examples", "")
            role = None
            for pattern, mapped_role in source_line_to_role.items():
                if pattern in source:
                    role = mapped_role
                    break
            if role in ROLE_ORDER:
                pc_to_role[int(pc_hex, 16)] = role
    return pc_to_role


def iter_issue_rows(path: Path) -> Iterator[Dict[str, str]]:
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("event") == "ISSUE":
                yield row


def parse_issue_row(
    row: Dict[str, str], pc_to_role: Dict[int, str]
) -> Optional[Tuple[int, int, int, int, int, str, str, Tuple[int, ...]]]:
    try:
        cycle = int(row.get("cycle", "0"))
        sm_id = int(row.get("sm") or row.get("sm_id") or "0")
        warp_id = int(row.get("warp") or row.get("warp_id") or "0")
        scheduler_id = int(row.get("scheduler", "0"))
    except ValueError:
        return None

    pc_text = row.get("pc")
    if not pc_text or pc_text == "NA":
        return None
    try:
        pc = int(pc_text, 16)
    except ValueError:
        return None

    role = pc_to_role.get(pc)
    if role not in ROLE_ORDER:
        return None
    if row.get("OP") != "LOAD_OP":
        return None
    if row.get("Space") not in {"GLOBAL", "LOCAL"}:
        return None
    if mask_is_zero(row.get("mask")):
        return None
    addresses = tuple(sorted(set(parse_tuple_field(row.get("Issue_Sector_Addresses")))))
    return cycle, sm_id, warp_id, scheduler_id, pc, role, normalize_mask_hex(row.get("mask")), addresses


def detect_dense_window(issue_trace: Path, pc_to_role: Dict[int, str]) -> Tuple[int, int]:
    counts: Counter[int] = Counter()
    raise RuntimeError("detect_dense_window should not be called directly")


def detect_dense_window_from_issues(issues: Sequence[IssueRecord]) -> Tuple[int, int]:
    counts: Counter[int] = Counter()
    for issue in issues:
        cycle = issue.issue_cycle
        counts[cycle // WINDOW_BIN_CYCLES] += 1

    if not counts:
        raise SystemExit("No IMA issue rows matched in issue trace.")

    peak_bin, peak_count = max(counts.items(), key=lambda item: (item[1], -item[0]))
    threshold = max(1, int(round(peak_count * WINDOW_THRESHOLD_RATIO)))
    selected_bins = {peak_bin}

    probe = peak_bin - 1
    while counts.get(probe, 0) >= threshold:
        selected_bins.add(probe)
        probe -= 1

    probe = peak_bin + 1
    while counts.get(probe, 0) >= threshold:
        selected_bins.add(probe)
        probe += 1

    selected_cycles = [
        issue.issue_cycle for issue in issues if (issue.issue_cycle // WINDOW_BIN_CYCLES) in selected_bins
    ]

    margin = max(1000, WINDOW_BIN_CYCLES // 2)
    return min(selected_cycles) - margin, max(selected_cycles) + margin


def collect_matching_issues(
    issue_trace: Path,
    pc_to_role: Dict[int, str],
    pc_to_pair: Dict[int, str],
) -> List[IssueRecord]:
    issue_seq_by_warp_role: Dict[Tuple[int, int, str], int] = defaultdict(int)
    issues: List[IssueRecord] = []
    pc_hex_text = {f"0x{pc:x}" for pc in pc_to_role}
    try:
        import pandas as pd  # type: ignore

        compression = "gzip" if issue_trace.suffix == ".gz" else None
        for chunk in pd.read_csv(
            issue_trace,
            usecols=[
                "cycle",
                "sm",
                "scheduler",
                "warp",
                "event",
                "pc",
                "mask",
                "OP",
                "Space",
                "Issue_Sector_Addresses",
            ],
            dtype=str,
            keep_default_na=False,
            chunksize=1_000_000,
            compression=compression,
        ):
            filtered = chunk[
                (chunk["event"] == "ISSUE")
                & (chunk["OP"] == "LOAD_OP")
                & (chunk["Space"].isin(["GLOBAL", "LOCAL"]))
                & (chunk["pc"].isin(pc_hex_text))
            ]
            if filtered.empty:
                continue
            for row in filtered.to_dict("records"):
                parsed = parse_issue_row(row, pc_to_role)
                if parsed is None:
                    continue
                cycle, sm_id, warp_id, scheduler_id, pc, role, mask_hex, addresses = parsed
                key = (sm_id, warp_id, role)
                issue_seq = issue_seq_by_warp_role[key]
                issue_seq_by_warp_role[key] += 1
                cachelines = tuple(sorted({addr >> CACHELINE_SHIFT for addr in addresses}))
                issues.append(
                    IssueRecord(
                        sm_id=sm_id,
                        role=role,
                        warp_id=warp_id,
                        issue_seq=issue_seq,
                        issue_cycle=cycle,
                        scheduler_id=scheduler_id,
                        pc=pc,
                        pair_id=pc_to_pair.get(pc),
                        mask_hex=mask_hex,
                        addresses=addresses,
                        cachelines=cachelines,
                    )
                )
    except ImportError:
        for row in iter_issue_rows(issue_trace):
            parsed = parse_issue_row(row, pc_to_role)
            if parsed is None:
                continue
            cycle, sm_id, warp_id, scheduler_id, pc, role, mask_hex, addresses = parsed
            key = (sm_id, warp_id, role)
            issue_seq = issue_seq_by_warp_role[key]
            issue_seq_by_warp_role[key] += 1
            cachelines = tuple(sorted({addr >> CACHELINE_SHIFT for addr in addresses}))
            issues.append(
                IssueRecord(
                    sm_id=sm_id,
                    role=role,
                    warp_id=warp_id,
                    issue_seq=issue_seq,
                    issue_cycle=cycle,
                    scheduler_id=scheduler_id,
                    pc=pc,
                    pair_id=pc_to_pair.get(pc),
                    mask_hex=mask_hex,
                    addresses=addresses,
                    cachelines=cachelines,
                )
            )
    return issues


def filter_window_issues(issues: Sequence[IssueRecord], cycle_window: Tuple[int, int]) -> List[IssueRecord]:
    start, end = cycle_window
    return [issue for issue in issues if start <= issue.issue_cycle <= end]


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


def find_initial_status(
    records: Optional[Sequence[L1Record]],
    record_cycles: Optional[Sequence[int]],
    issue_cycle: int,
) -> Tuple[str, Optional[int], Optional[int]]:
    if not records or not record_cycles:
        return "UNKNOWN", None, None
    idx = bisect_left(record_cycles, issue_cycle)
    limit = issue_cycle + L1_MATCH_WINDOW
    statuses: List[str] = []
    min_cycle: Optional[int] = None
    max_cycle: Optional[int] = None
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
        return "UNKNOWN", None, None
    return classify_initial_status(statuses), min_cycle, max_cycle


def find_fill_cycle(cycles: Optional[Sequence[int]], start_cycle: int) -> Optional[int]:
    if not cycles:
        return None
    idx = bisect_left(cycles, start_cycle)
    if idx >= len(cycles):
        return None
    return cycles[idx]


def peek_csv_header(path: Path) -> List[str]:
    with open_text(path) as handle:
        reader = csv.reader(handle)
        return next(reader)


def parse_optional_float(value: Optional[str]) -> Optional[float]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def classify_l2_status(statuses: Sequence[str]) -> str:
    if not statuses:
        return "UNKNOWN"
    return max(statuses, key=lambda item: L2_STATUS_PRIORITY.get(item, 0))


def choose_l2_record(records: Sequence[L2Record]) -> Optional[L2Record]:
    if not records:
        return None
    best_status = classify_l2_status([record.status for record in records])
    best_candidates = [record for record in records if record.status == best_status]
    return min(best_candidates, key=lambda record: record.cycle)


def find_l2_status(
    records: Optional[Sequence[L2Record]],
    record_cycles: Optional[Sequence[int]],
    issue_cycle: int,
) -> Tuple[str, Optional[int], Optional[float], Optional[float], Optional[float]]:
    if not records or not record_cycles:
        return "UNKNOWN", None, None, None, None
    idx = bisect_left(record_cycles, issue_cycle)
    limit = issue_cycle + L1_MATCH_WINDOW
    matched: List[L2Record] = []
    while idx < len(records):
        record = records[idx]
        if record.cycle > limit:
            break
        matched.append(record)
        if record.status not in RESFAIL_STATUSES:
            break
        idx += 1
    if not matched:
        return "UNKNOWN", None, None, None, None
    chosen = choose_l2_record(matched)
    if chosen is None:
        return "UNKNOWN", None, None, None, None
    return (
        classify_l2_status([record.status for record in matched]),
        chosen.cycle,
        chosen.hbm_bw_gbps,
        chosen.hbm_occupancy,
        chosen.sm_alu_utilization,
    )


def collect_l1_records(
    l1_trace: Path,
    issues: Sequence[IssueRecord],
    cycle_window: Tuple[int, int],
) -> Tuple[
    Dict[Tuple[int, int, int], List[L1Record]],
    Dict[Tuple[int, int, int], List[int]],
    Dict[Tuple[int, int], List[int]],
    Counter[str],
]:
    tracked_pairs = {(issue.sm_id, issue.warp_id, addr) for issue in issues for addr in issue.addresses}
    tracked_addrs = {addr for issue in issues for addr in issue.addresses}
    initial_lookup: Dict[Tuple[int, int, int], List[L1Record]] = defaultdict(list)
    initial_cycle_lookup: Dict[Tuple[int, int, int], List[int]] = {}
    fill_lookup: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    window_counts: Counter[str] = Counter()
    tracked_addr_hex = {f"0x{addr:x}" for addr in tracked_addrs}

    try:
        import pandas as pd  # type: ignore

        compression = "gzip" if l1_trace.suffix == ".gz" else None
        for chunk in pd.read_csv(
            l1_trace,
            usecols=["cycle", "sm_id", "warp_id", "address", "op", "l1_status"],
            dtype=str,
            keep_default_na=False,
            chunksize=1_000_000,
            compression=compression,
        ):
            ld_chunk = chunk[chunk["op"] == "LD"]
            if ld_chunk.empty:
                continue

            non_fill = ld_chunk[ld_chunk["l1_status"] != "FILL"]
            if not non_fill.empty:
                cycle_series = non_fill["cycle"].astype(int)
                in_window = non_fill[cycle_series.between(cycle_window[0], cycle_window[1])]
                if not in_window.empty:
                    window_counts.update(in_window["l1_status"].tolist())

            tracked_chunk = ld_chunk[ld_chunk["address"].isin(tracked_addr_hex)]
            if tracked_chunk.empty:
                continue
            for row in tracked_chunk.itertuples(index=False):
                try:
                    cycle = int(row.cycle)
                    sm_id = int(row.sm_id)
                    warp_id = int(row.warp_id)
                    addr = int(row.address, 16)
                except (TypeError, ValueError):
                    continue
                status = row.l1_status or "UNKNOWN"
                if status == "FILL":
                    fill_lookup[(sm_id, addr)].append(cycle)
                    continue
                key = (sm_id, warp_id, addr)
                if key in tracked_pairs:
                    initial_lookup[key].append(L1Record(cycle=cycle, status=status))
    except ImportError:
        with open_text(l1_trace) as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    cycle = int(row["cycle"])
                    sm_id = int(row["sm_id"])
                    warp_id = int(row["warp_id"])
                    addr = int(row["address"], 16)
                except (KeyError, TypeError, ValueError):
                    continue
                op = row.get("op", "NA")
                status = row.get("l1_status", "UNKNOWN")
                if op == "LD" and status != "FILL" and cycle_window[0] <= cycle <= cycle_window[1]:
                    window_counts[status] += 1
                if op != "LD":
                    continue
                if status == "FILL":
                    if addr in tracked_addrs:
                        fill_lookup[(sm_id, addr)].append(cycle)
                else:
                    key = (sm_id, warp_id, addr)
                    if key in tracked_pairs:
                        initial_lookup[key].append(L1Record(cycle=cycle, status=status))

    for key in initial_lookup:
        initial_lookup[key].sort(key=lambda record: record.cycle)
        initial_cycle_lookup[key] = [record.cycle for record in initial_lookup[key]]
    for key in fill_lookup:
        fill_lookup[key].sort()
    return initial_lookup, initial_cycle_lookup, fill_lookup, window_counts


def collect_l2_records(
    l2_trace: Path,
    issues: Sequence[IssueRecord],
    cycle_window: Tuple[int, int],
) -> Tuple[
    Dict[Tuple[int, int, int], List[L2Record]],
    Dict[Tuple[int, int, int], List[int]],
    Counter[str],
]:
    tracked_pairs = {(issue.sm_id, issue.warp_id, cacheline) for issue in issues for cacheline in issue.cachelines}
    tracked_cachelines = {cacheline for issue in issues for cacheline in issue.cachelines}
    l2_lookup: Dict[Tuple[int, int, int], List[L2Record]] = defaultdict(list)
    l2_cycle_lookup: Dict[Tuple[int, int, int], List[int]] = {}
    window_counts: Counter[str] = Counter()

    header = peek_csv_header(l2_trace)
    optional_cols = [
        column
        for column in ["hbm_bw_GBps", "hbm_occupancy", "sm_alu_utilization"]
        if column in header
    ]
    usecols = ["cycle", "sm_id", "warp_id", "address", "op", "l2_status"] + optional_cols

    try:
        import pandas as pd  # type: ignore

        compression = "gzip" if l2_trace.suffix == ".gz" else None
        for chunk in pd.read_csv(
            l2_trace,
            usecols=usecols,
            dtype=str,
            keep_default_na=False,
            chunksize=1_000_000,
            compression=compression,
        ):
            ld_chunk = chunk[chunk["op"] == "LD"]
            if ld_chunk.empty:
                continue

            cycle_series = ld_chunk["cycle"].astype(int)
            in_window = ld_chunk[cycle_series.between(cycle_window[0], cycle_window[1])]
            if not in_window.empty:
                window_counts.update(in_window["l2_status"].tolist())

            for row in ld_chunk.itertuples(index=False):
                try:
                    cycle = int(row.cycle)
                    sm_id = int(row.sm_id)
                    warp_id = int(row.warp_id)
                    cacheline = int(row.address, 16) >> CACHELINE_SHIFT
                except (TypeError, ValueError):
                    continue
                key = (sm_id, warp_id, cacheline)
                if cacheline not in tracked_cachelines or key not in tracked_pairs:
                    continue
                l2_lookup[key].append(
                    L2Record(
                        cycle=cycle,
                        status=row.l2_status or "UNKNOWN",
                        hbm_bw_gbps=parse_optional_float(getattr(row, "hbm_bw_GBps", None)),
                        hbm_occupancy=parse_optional_float(getattr(row, "hbm_occupancy", None)),
                        sm_alu_utilization=parse_optional_float(getattr(row, "sm_alu_utilization", None)),
                    )
                )
    except ImportError:
        with open_text(l2_trace) as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    cycle = int(row["cycle"])
                    sm_id = int(row["sm_id"])
                    warp_id = int(row["warp_id"])
                    cacheline = int(row["address"], 16) >> CACHELINE_SHIFT
                except (KeyError, TypeError, ValueError):
                    continue
                if row.get("op", "NA") != "LD":
                    continue
                status = row.get("l2_status", "UNKNOWN")
                if cycle_window[0] <= cycle <= cycle_window[1]:
                    window_counts[status] += 1
                key = (sm_id, warp_id, cacheline)
                if cacheline not in tracked_cachelines or key not in tracked_pairs:
                    continue
                l2_lookup[key].append(
                    L2Record(
                        cycle=cycle,
                        status=status,
                        hbm_bw_gbps=parse_optional_float(row.get("hbm_bw_GBps")),
                        hbm_occupancy=parse_optional_float(row.get("hbm_occupancy")),
                        sm_alu_utilization=parse_optional_float(row.get("sm_alu_utilization")),
                    )
                )

    for key in l2_lookup:
        l2_lookup[key].sort(key=lambda record: record.cycle)
        l2_cycle_lookup[key] = [record.cycle for record in l2_lookup[key]]
    return l2_lookup, l2_cycle_lookup, window_counts


def format_hex_list(values: Sequence[int]) -> str:
    return ";".join(f"0x{value:x}" for value in values)


def format_int_list(values: Sequence[int]) -> str:
    return ";".join(str(value) for value in values)


def summarize_issues(
    issues: Sequence[IssueRecord],
    initial_lookup: Dict[Tuple[int, int, int], List[L1Record]],
    initial_cycle_lookup: Dict[Tuple[int, int, int], List[int]],
    fill_lookup: Dict[Tuple[int, int], List[int]],
    l2_lookup: Optional[Dict[Tuple[int, int, int], List[L2Record]]] = None,
    l2_cycle_lookup: Optional[Dict[Tuple[int, int, int], List[int]]] = None,
) -> Tuple[List[IssueSummary], Dict[str, Counter[str]], List[List[object]], List[List[object]]]:
    role_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    issue_summaries: List[IssueSummary] = []
    rows_for_events: List[List[object]] = []
    rows_for_sectors: List[List[object]] = []

    for issue in sorted(
        issues,
        key=lambda item: (item.sm_id, item.warp_id, 0 if item.role == "index_load" else 1, item.issue_seq),
    ):
        statuses: List[str] = []
        refill_candidates: List[int] = []
        l2_statuses: List[str] = []
        l2_cycles: List[int] = []
        l2_hbm_bw_values: List[float] = []
        l2_hbm_occupancy_values: List[float] = []
        l2_sm_alu_util_values: List[float] = []
        sector_rows: List[List[object]] = []
        for sector_idx, addr in enumerate(issue.addresses):
            initial_status, initial_cycle, max_initial_cycle = find_initial_status(
                initial_lookup.get((issue.sm_id, issue.warp_id, addr)),
                initial_cycle_lookup.get((issue.sm_id, issue.warp_id, addr)),
                issue.issue_cycle,
            )
            fill_cycle = None
            if initial_status in {"MISS", "HIT_RESERVED"}:
                fill_cycle = find_fill_cycle(fill_lookup.get((issue.sm_id, addr)), max_initial_cycle or issue.issue_cycle)
                if fill_cycle is not None:
                    refill_candidates.append(fill_cycle)
            statuses.append(initial_status)
            l2_status = "UNKNOWN"
            l2_cycle = None
            l2_hbm_bw = None
            l2_hbm_occupancy = None
            l2_sm_alu_util = None
            cacheline = addr >> CACHELINE_SHIFT
            if l2_lookup is not None and l2_cycle_lookup is not None:
                l2_status, l2_cycle, l2_hbm_bw, l2_hbm_occupancy, l2_sm_alu_util = find_l2_status(
                    l2_lookup.get((issue.sm_id, issue.warp_id, cacheline)),
                    l2_cycle_lookup.get((issue.sm_id, issue.warp_id, cacheline)),
                    issue.issue_cycle,
                )
                l2_statuses.append(l2_status)
                if l2_cycle is not None:
                    l2_cycles.append(l2_cycle)
                if l2_hbm_bw is not None:
                    l2_hbm_bw_values.append(l2_hbm_bw)
                if l2_hbm_occupancy is not None:
                    l2_hbm_occupancy_values.append(l2_hbm_occupancy)
                if l2_sm_alu_util is not None:
                    l2_sm_alu_util_values.append(l2_sm_alu_util)
            sector_rows.append(
                [
                    issue.sm_id,
                    issue.role,
                    issue.warp_id,
                    issue.issue_seq,
                    issue.issue_cycle,
                    issue.scheduler_id,
                    f"0x{issue.pc:x}",
                    issue.pair_id or "",
                    issue.mask_hex,
                    sector_idx,
                    f"0x{addr:x}",
                    addr >> CACHELINE_SHIFT,
                    initial_status,
                    initial_cycle,
                    fill_cycle,
                    l2_status,
                    l2_cycle,
                    l2_hbm_bw,
                    l2_hbm_occupancy,
                    l2_sm_alu_util,
                ]
            )

        overall_status = max(statuses, key=lambda item: STATUS_PRIORITY[item]) if statuses else "UNKNOWN"
        refill_cycle = max(refill_candidates) if refill_candidates else None
        issue_to_refill = (refill_cycle - issue.issue_cycle) if refill_cycle is not None else None
        overall_l2_status = classify_l2_status(l2_statuses)
        l2_first_cycle = min(l2_cycles) if l2_cycles else None
        l2_hbm_bw_gbps = (
            sum(l2_hbm_bw_values) / len(l2_hbm_bw_values) if l2_hbm_bw_values else None
        )
        l2_hbm_occupancy = (
            sum(l2_hbm_occupancy_values) / len(l2_hbm_occupancy_values) if l2_hbm_occupancy_values else None
        )
        l2_sm_alu_utilization = (
            sum(l2_sm_alu_util_values) / len(l2_sm_alu_util_values) if l2_sm_alu_util_values else None
        )
        role_counts[issue.role][overall_status] += 1
        issue_summaries.append(
            IssueSummary(
                issue=issue,
                first_status=overall_status,
                refill_cycle=refill_cycle,
                issue_to_refill=issue_to_refill,
                l2_first_status=overall_l2_status,
                l2_first_cycle=l2_first_cycle,
                l2_hbm_bw_gbps=l2_hbm_bw_gbps,
                l2_hbm_occupancy=l2_hbm_occupancy,
                l2_sm_alu_utilization=l2_sm_alu_utilization,
            )
        )
        rows_for_events.append(
            [
                issue.sm_id,
                issue.role,
                issue.warp_id,
                issue.issue_seq,
                issue.issue_cycle,
                issue.scheduler_id,
                f"0x{issue.pc:x}",
                issue.pair_id or "",
                issue.mask_hex,
                len(issue.addresses),
                format_hex_list(issue.addresses),
                format_int_list(issue.cachelines),
                overall_status,
                refill_cycle,
                issue_to_refill,
                overall_l2_status,
                l2_first_cycle,
                l2_hbm_bw_gbps,
                l2_hbm_occupancy,
                l2_sm_alu_utilization,
            ]
        )
        rows_for_sectors.extend(sector_rows)
    return issue_summaries, role_counts, rows_for_events, rows_for_sectors


def percentile(values: Sequence[int], pct: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = int(round((len(ordered) - 1) * pct))
    return ordered[min(max(rank, 0), len(ordered) - 1)]


def build_chain_records(
    workload: str,
    scheduler_label: str,
    issue_summaries: Sequence[IssueSummary],
    pair_to_pcs: Dict[str, Tuple[int, int]],
) -> List[ChainRecord]:
    grouped: Dict[Tuple[int, int, str], List[IssueSummary]] = defaultdict(list)
    for summary in issue_summaries:
        pair_id = summary.issue.pair_id
        if not pair_id:
            continue
        grouped[(summary.issue.sm_id, summary.issue.warp_id, pair_id)].append(summary)

    chains: List[ChainRecord] = []
    for sm_id, warp_id, pair_id in sorted(grouped):
        stream = sorted(
            grouped[(sm_id, warp_id, pair_id)],
            key=lambda item: (item.issue.issue_cycle, 0 if item.issue.role == "index_load" else 1),
        )
        index_pc, data_pc = pair_to_pcs[pair_id]
        pending_indexes: deque[IssueSummary] = deque()
        dynamic_seq = 0
        for summary in stream:
            if summary.issue.role == "index_load":
                pending_indexes.append(summary)
                continue
            if pending_indexes:
                index_issue = pending_indexes.popleft()
                data_issue = summary
            else:
                index_issue = None
                data_issue = summary
            index_issue_cycle = index_issue.issue.issue_cycle if index_issue else None
            data_issue_cycle = data_issue.issue.issue_cycle if data_issue else None
            index_refill_cycle = index_issue.refill_cycle if index_issue else None
            data_refill_cycle = data_issue.refill_cycle if data_issue else None
            chains.append(
                ChainRecord(
                    workload=workload,
                    scheduler_label=scheduler_label,
                    sm_id=sm_id,
                    warp_id=warp_id,
                    static_pair_id=pair_id,
                    dynamic_seq=dynamic_seq,
                    index_pc=f"0x{index_pc:x}",
                    index_issue_cycle=index_issue_cycle,
                    index_status=index_issue.first_status if index_issue else "MISSING",
                    index_refill_cycle=index_refill_cycle,
                    index_issue_to_refill=index_issue.issue_to_refill if index_issue else None,
                    data_pc=f"0x{data_pc:x}",
                    data_issue_cycle=data_issue_cycle,
                    index_issue_to_data_issue=(
                        data_issue_cycle - index_issue_cycle
                        if index_issue_cycle is not None and data_issue_cycle is not None
                        else None
                    ),
                    refill_to_data_issue=(
                        data_issue_cycle - index_refill_cycle
                        if index_refill_cycle is not None and data_issue_cycle is not None
                        else None
                    ),
                    data_status=data_issue.first_status if data_issue else "MISSING",
                    data_refill_cycle=data_refill_cycle,
                    data_issue_to_refill=data_issue.issue_to_refill if data_issue else None,
                    complete_flag=int(index_issue is not None and data_issue is not None),
                )
            )
            dynamic_seq += 1
        while pending_indexes:
            index_issue = pending_indexes.popleft()
            index_issue_cycle = index_issue.issue.issue_cycle if index_issue else None
            index_refill_cycle = index_issue.refill_cycle if index_issue else None
            chains.append(
                ChainRecord(
                    workload=workload,
                    scheduler_label=scheduler_label,
                    sm_id=sm_id,
                    warp_id=warp_id,
                    static_pair_id=pair_id,
                    dynamic_seq=dynamic_seq,
                    index_pc=f"0x{index_pc:x}",
                    index_issue_cycle=index_issue_cycle,
                    index_status=index_issue.first_status if index_issue else "MISSING",
                    index_refill_cycle=index_refill_cycle,
                    index_issue_to_refill=index_issue.issue_to_refill if index_issue else None,
                    data_pc=f"0x{data_pc:x}",
                    data_issue_cycle=None,
                    index_issue_to_data_issue=None,
                    refill_to_data_issue=None,
                    data_status="MISSING",
                    data_refill_cycle=None,
                    data_issue_to_refill=None,
                    complete_flag=0,
                )
            )
            dynamic_seq += 1
    return chains


def write_chain_outputs(
    out_dir: Path,
    workload: str,
    scheduler_label: str,
    cycle_window: Tuple[int, int],
    issue_summaries: Sequence[IssueSummary],
    pair_to_pcs: Dict[str, Tuple[int, int]],
) -> None:
    if not pair_to_pcs:
        return

    chains = build_chain_records(workload, scheduler_label, issue_summaries, pair_to_pcs)
    chain_path = out_dir / f"ima_chain_latency_{scheduler_label}.csv"
    summary_path = out_dir / f"ima_chain_summary_{scheduler_label}.csv"

    with chain_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "workload",
                "scheduler",
                "window_start",
                "window_end",
                "sm_id",
                "warp_id",
                "static_pair_id",
                "dynamic_seq",
                "index_pc",
                "index_issue_cycle",
                "index_status",
                "index_refill_cycle",
                "index_issue_to_refill",
                "data_pc",
                "data_issue_cycle",
                "index_issue_to_data_issue",
                "refill_to_data_issue",
                "data_status",
                "data_refill_cycle",
                "data_issue_to_refill",
                "complete_flag",
            ]
        )
        for chain in sorted(chains, key=lambda item: (item.sm_id, item.warp_id, item.static_pair_id, item.dynamic_seq)):
            writer.writerow(
                [
                    chain.workload,
                    chain.scheduler_label,
                    cycle_window[0],
                    cycle_window[1],
                    chain.sm_id,
                    chain.warp_id,
                    chain.static_pair_id,
                    chain.dynamic_seq,
                    chain.index_pc,
                    chain.index_issue_cycle,
                    chain.index_status,
                    chain.index_refill_cycle,
                    chain.index_issue_to_refill,
                    chain.data_pc,
                    chain.data_issue_cycle,
                    chain.index_issue_to_data_issue,
                    chain.refill_to_data_issue,
                    chain.data_status,
                    chain.data_refill_cycle,
                    chain.data_issue_to_refill,
                    chain.complete_flag,
                ]
            )

    index_refill_lat = [chain.index_issue_to_refill for chain in chains if chain.index_issue_to_refill is not None]
    refill_to_data = [chain.refill_to_data_issue for chain in chains if chain.refill_to_data_issue is not None]
    data_refill_lat = [chain.data_issue_to_refill for chain in chains if chain.data_issue_to_refill is not None]
    index_to_data = [chain.index_issue_to_data_issue for chain in chains if chain.index_issue_to_data_issue is not None]
    orphan_index_count = sum(chain.index_status != "MISSING" and chain.data_status == "MISSING" for chain in chains)
    orphan_data_count = sum(chain.index_status == "MISSING" and chain.data_status != "MISSING" for chain in chains)
    bad_order_count = sum(
        1
        for chain in chains
        if chain.index_refill_cycle is not None
        and chain.data_issue_cycle is not None
        and chain.data_issue_cycle < chain.index_refill_cycle
    )

    with summary_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "workload",
                "scheduler",
                "window_start",
                "window_end",
                "chain_count",
                "complete_chain_count",
                "orphan_index_count",
                "orphan_data_count",
                "index_miss_count",
                "index_hit_reserved_count",
                "data_miss_count",
                "data_hit_reserved_count",
                "fill_observed",
                "bad_order_count",
                "index_issue_to_refill_p50",
                "index_issue_to_refill_p90",
                "index_issue_to_refill_p99",
                "refill_to_data_issue_p50",
                "refill_to_data_issue_p90",
                "refill_to_data_issue_p99",
                "index_issue_to_data_issue_p50",
                "index_issue_to_data_issue_p90",
                "index_issue_to_data_issue_p99",
                "data_issue_to_refill_p50",
                "data_issue_to_refill_p90",
                "data_issue_to_refill_p99",
            ]
        )
        writer.writerow(
            [
                workload,
                scheduler_label,
                cycle_window[0],
                cycle_window[1],
                len(chains),
                sum(chain.complete_flag for chain in chains),
                orphan_index_count,
                orphan_data_count,
                sum(chain.index_status == "MISS" for chain in chains),
                sum(chain.index_status == "HIT_RESERVED" for chain in chains),
                sum(chain.data_status == "MISS" for chain in chains),
                sum(chain.data_status == "HIT_RESERVED" for chain in chains),
                int(bool(index_refill_lat or data_refill_lat)),
                bad_order_count,
                percentile(index_refill_lat, 0.50),
                percentile(index_refill_lat, 0.90),
                percentile(index_refill_lat, 0.99),
                percentile(refill_to_data, 0.50),
                percentile(refill_to_data, 0.90),
                percentile(refill_to_data, 0.99),
                percentile(index_to_data, 0.50),
                percentile(index_to_data, 0.90),
                percentile(index_to_data, 0.99),
                percentile(data_refill_lat, 0.50),
                percentile(data_refill_lat, 0.90),
                percentile(data_refill_lat, 0.99),
            ]
        )


def write_outputs(
    out_dir: Path,
    workload: str,
    scheduler_label: str,
    cycle_window: Tuple[int, int],
    issues: Sequence[IssueRecord],
    initial_lookup: Dict[Tuple[int, int, int], List[L1Record]],
    initial_cycle_lookup: Dict[Tuple[int, int, int], List[int]],
    fill_lookup: Dict[Tuple[int, int], List[int]],
    window_counts: Counter[str],
    pair_to_pcs: Dict[str, Tuple[int, int]],
    l2_lookup: Optional[Dict[Tuple[int, int, int], List[L2Record]]] = None,
    l2_cycle_lookup: Optional[Dict[Tuple[int, int, int], List[int]]] = None,
    l2_window_counts: Optional[Counter[str]] = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / f"warp_load_events_{scheduler_label}.csv"
    sectors_path = out_dir / f"warp_load_sectors_{scheduler_label}.csv"
    summary_path = out_dir / f"ima_window_summary_{scheduler_label}.csv"
    breakdown_path = out_dir / f"ima_window_role_breakdown_{scheduler_label}.csv"
    l2_summary_path = out_dir / f"ima_l2_window_summary_{scheduler_label}.csv"

    issue_summaries, role_counts, rows_for_events, rows_for_sectors = summarize_issues(
        issues, initial_lookup, initial_cycle_lookup, fill_lookup, l2_lookup, l2_cycle_lookup
    )

    with events_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sm_id",
                "role",
                "warp_id",
                "issue_seq",
                "issue_cycle",
                "scheduler",
                "pc",
                "static_pair_id",
                "issue_mask_hex",
                "sector_addr_count",
                "sector_addrs",
                "cacheline_ids",
                "first_status",
                "refill_cycle",
                "issue_to_refill",
                "l2_first_status",
                "l2_first_cycle",
                "l2_hbm_bw_GBps",
                "l2_hbm_occupancy",
                "l2_sm_alu_utilization",
            ]
        )
        writer.writerows(rows_for_events)

    with sectors_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sm_id",
                "role",
                "warp_id",
                "issue_seq",
                "issue_cycle",
                "scheduler",
                "pc",
                "static_pair_id",
                "issue_mask_hex",
                "sector_idx",
                "sector_addr",
                "cacheline_id",
                "initial_l1_status",
                "initial_cycle",
                "fill_cycle",
                "l2_first_status",
                "l2_first_cycle",
                "l2_hbm_bw_GBps",
                "l2_hbm_occupancy",
                "l2_sm_alu_utilization",
            ]
        )
        writer.writerows(rows_for_sectors)

    total_accesses = sum(window_counts.values())
    with summary_path.open("w", newline="") as handle:
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
                "hit_rate",
                "hit_reserved_rate",
                "mshr_hit_rate",
                "miss_like_rate",
                "resfail_rate",
            ]
        )
        writer.writerow(
            [
                scheduler_label,
                "all_ld_window",
                cycle_window[0],
                cycle_window[1],
                len({issue.warp_id for issue in issues}),
                len(issues),
                sum(issue.role == "index_load" for issue in issues),
                sum(issue.role == "data_load" for issue in issues),
                total_accesses,
                f"{(window_counts['HIT'] / total_accesses):.4f}" if total_accesses else "0.0000",
                f"{(window_counts['HIT_RESERVED'] / total_accesses):.4f}" if total_accesses else "0.0000",
                f"{(window_counts['MSHR_HIT'] / total_accesses):.4f}" if total_accesses else "0.0000",
                f"{((window_counts['MISS'] + window_counts['SECTOR_MISS']) / total_accesses):.4f}"
                if total_accesses
                else "0.0000",
                f"{(window_counts['RESERVATION_FAIL'] / total_accesses):.4f}" if total_accesses else "0.0000",
            ]
        )

    with breakdown_path.open("w", newline="") as handle:
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
        writer.writerow(
            [
                scheduler_label,
                cycle_window[0],
                cycle_window[1],
                "all_ld_window",
                "all_l1_ld_events",
                total_accesses,
                window_counts["HIT"],
                window_counts["HIT_RESERVED"],
                window_counts["MSHR_HIT"],
                window_counts["MISS"],
                window_counts["SECTOR_MISS"],
                window_counts["RESERVATION_FAIL"],
                0,
                f"{(window_counts['HIT'] / total_accesses):.4f}" if total_accesses else "0.0000",
                f"{((window_counts['MISS'] + window_counts['SECTOR_MISS']) / total_accesses):.4f}"
                if total_accesses
                else "0.0000",
                f"{(window_counts['RESERVATION_FAIL'] / total_accesses):.4f}" if total_accesses else "0.0000",
            ]
        )
        for role in ROLE_ORDER:
            counts = role_counts[role]
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

    l2_window_counts = l2_window_counts or Counter()
    l2_role_rows: List[List[object]] = []
    for role in ROLE_ORDER:
        role_summaries = [summary for summary in issue_summaries if summary.issue.role == role and summary.first_status == "MISS"]
        total = len(role_summaries)
        l2_counts = Counter(summary.l2_first_status for summary in role_summaries)
        bw_values = [summary.l2_hbm_bw_gbps for summary in role_summaries if summary.l2_hbm_bw_gbps is not None]
        occupancy_values = [summary.l2_hbm_occupancy for summary in role_summaries if summary.l2_hbm_occupancy is not None]
        alu_values = [
            summary.l2_sm_alu_utilization
            for summary in role_summaries
            if summary.l2_sm_alu_utilization is not None
        ]
        l2_role_rows.append(
            [
                scheduler_label,
                cycle_window[0],
                cycle_window[1],
                role,
                "l1_miss_issue_events",
                total,
                l2_counts["HIT"],
                l2_counts["HIT_RESERVED"],
                l2_counts["MSHR_HIT"],
                l2_counts["MISS"],
                l2_counts["SECTOR_MISS"],
                l2_counts["RESERVATION_FAIL"],
                l2_counts["UNKNOWN"],
                f"{((l2_counts['HIT'] + l2_counts['HIT_RESERVED'] + l2_counts['MSHR_HIT']) / total):.4f}" if total else "0.0000",
                f"{((l2_counts['MISS'] + l2_counts['SECTOR_MISS']) / total):.4f}" if total else "0.0000",
                f"{(sum(bw_values) / len(bw_values)):.4f}" if bw_values else "",
                f"{(sum(occupancy_values) / len(occupancy_values)):.4f}" if occupancy_values else "",
                f"{(sum(alu_values) / len(alu_values)):.4f}" if alu_values else "",
            ]
        )

    total_l2 = sum(l2_window_counts.values())
    with l2_summary_path.open("w", newline="") as handle:
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
                "l2_hit_path_rate",
                "l2_miss_path_rate",
                "avg_hbm_bw_GBps",
                "avg_hbm_occupancy",
                "avg_sm_alu_utilization",
            ]
        )
        writer.writerow(
            [
                scheduler_label,
                cycle_window[0],
                cycle_window[1],
                "all_l2_window",
                "all_l2_ld_events",
                total_l2,
                l2_window_counts["HIT"],
                l2_window_counts["HIT_RESERVED"],
                l2_window_counts["MSHR_HIT"],
                l2_window_counts["MISS"],
                l2_window_counts["SECTOR_MISS"],
                l2_window_counts["RESERVATION_FAIL"],
                l2_window_counts["UNKNOWN"],
                f"{((l2_window_counts['HIT'] + l2_window_counts['HIT_RESERVED'] + l2_window_counts['MSHR_HIT']) / total_l2):.4f}" if total_l2 else "0.0000",
                f"{((l2_window_counts['MISS'] + l2_window_counts['SECTOR_MISS']) / total_l2):.4f}" if total_l2 else "0.0000",
                "",
                "",
                "",
            ]
        )
        writer.writerows(l2_role_rows)

    write_chain_outputs(out_dir, workload, scheduler_label, cycle_window, issue_summaries, pair_to_pcs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight extractor for workload-specific IMA warp tables")
    parser.add_argument("--l1-trace", required=True, type=Path)
    parser.add_argument("--issue-trace", required=True, type=Path)
    parser.add_argument("--l2-trace", type=Path)
    parser.add_argument("--pc-class", type=Path)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--scheduler-label", default="lrr")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    if args.workload in {"bc_ima_high", "bc_cit_ima", "bc_ima_small", "bc_ima_med"}:
        raise SystemExit(
            "Use bc_*_forward / bc_*_reverse to avoid cross-kernel PC aliasing."
        )

    static_pc_to_role, pc_to_pair, pair_to_pcs = get_static_pair_maps(args.workload)
    if args.pc_class is not None:
        pc_to_role = parse_pc_classification(args.pc_class, args.workload)
        if not pc_to_role:
            pc_to_role = parse_sass_role_map(args.workload)
    else:
        pc_to_role = parse_sass_role_map(args.workload)
    if static_pc_to_role:
        pc_to_role = static_pc_to_role
    if not pc_to_role:
        raise SystemExit(f"No workload-specific SASS/PC role mapping found for {args.workload}")

    all_matching_issues = collect_matching_issues(args.issue_trace, pc_to_role, pc_to_pair)
    if not all_matching_issues:
        raise SystemExit(f"No IMA issues found for {args.workload}")

    marker_pcs = get_window_marker_pcs(args.workload)
    window_source_issues = all_matching_issues
    if marker_pcs:
        marker_issues = [issue for issue in all_matching_issues if issue.pc in marker_pcs]
        if marker_issues:
            window_source_issues = marker_issues

    cycle_window = detect_dense_window_from_issues(window_source_issues)
    issues = filter_window_issues(all_matching_issues, cycle_window)
    if not issues:
        raise SystemExit(f"No IMA issues found in dense window for {args.workload}")

    initial_lookup, initial_cycle_lookup, fill_lookup, window_counts = collect_l1_records(
        args.l1_trace, issues, cycle_window
    )
    l2_lookup = None
    l2_cycle_lookup = None
    l2_window_counts = None
    if args.l2_trace is not None and args.l2_trace.exists():
        l2_lookup, l2_cycle_lookup, l2_window_counts = collect_l2_records(args.l2_trace, issues, cycle_window)
    write_outputs(
        args.out_dir,
        args.workload,
        args.scheduler_label,
        cycle_window,
        issues,
        initial_lookup,
        initial_cycle_lookup,
        fill_lookup,
        window_counts,
        pair_to_pcs,
        l2_lookup,
        l2_cycle_lookup,
        l2_window_counts,
    )

    print(f"Saved workload tables for {args.workload} to {args.out_dir}")


if __name__ == "__main__":
    main()
