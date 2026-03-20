#!/usr/bin/env python3
"""
Build baseline L1 miss breakdowns for ima_high workloads.

Public semantics:
  - Only classify real LDG* instructions from the main kernel(s)
  - Three classes only: regular / stride / ima
  - Trace PCs that do not map to those real load PCs are excluded from the
    main summary and reported via coverage metrics
"""

from __future__ import annotations

import csv
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


CLASS_ORDER: Tuple[str, ...] = ("regular", "stride", "ima")

CLASS_COLORS: Dict[str, str] = {
    "regular": "#d9d9d9",
    "stride": "#ffffff",
    "ima": "#5a5a5a",
}

MISS_LIKE_STATUSES: Set[str] = {"MISS", "SECTOR_MISS", "RESERVATION_FAIL"}

WORKLOADS: Tuple[Dict[str, object], ...] = (
    {
        "name": "bfs_ima_high",
        "sass": "ima_plan/01_ima_characterization/sass_analysis/bfs_linear_base.sm80.sass",
        "main_kernels": ("_Z10bfs_kerneliPKmPKiPi9Worklist2S4_",),
    },
    {
        "name": "sssp_ima_high",
        "sass": "ima_plan/01_ima_characterization/sass_analysis/sssp_linear_base.sm80.sass",
        "main_kernels": ("_Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_",),
    },
    {
        "name": "bc_ima_high",
        "sass": "ima_plan/01_ima_characterization/sass_analysis/bc_linear_base.sm80.sass",
        "main_kernels": ("_Z10bc_reverseiPKmPKiS2_S2_S2_iPfS3_", "_Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_"),
    },
    {
        "name": "cc_ima_high",
        "sass": "ima_plan/01_ima_characterization/sass_analysis/cc_base.sm80.sass",
        "main_kernels": ("_Z4hookiPKmPKiPiPb", "_Z8shortcutiPi"),
    },
    {
        "name": "spmv_ima_high",
        "sass": "ima_plan/01_ima_characterization/sass_analysis/spmv_base.sm80.sass",
        "main_kernels": ("_Z15spmv_csr_scalariPKmPKiPKfS4_Pf",),
    },
)

INSTRUCTION_RE = re.compile(r"^\s*/\*([0-9a-fA-F]+)\*/\s+(.*?)\s*;\s*$")
REGISTER_RE = re.compile(r"\bU?R\d+\b")
MEMORY_RE = re.compile(r"\[([^\]]+)\]")
LINEINFO_RE = re.compile(r'^\s*//## File "([^"]+)", line (\d+)')
SECTION_RE = re.compile(r"^\s*\.section\s+\.text\.([^,]+),")
TEXT_LABEL_RE = re.compile(r"^\s*\.text\.([^:]+):\s*$")

DEPENDENCE_OP_PREFIXES: Tuple[str, ...] = (
    "MOV",
    "IMAD",
    "IMAD.WIDE",
    "IMAD.MOV",
    "IADD",
    "IADD3",
    "LEA",
    "SHF",
    "LOP3",
    "IMNMX",
    "SEL",
    "UIADD",
    "UIMAD",
)

STRIDE_OP_PREFIXES: Tuple[str, ...] = (
    "MOV",
    "IMAD",
    "IMAD.WIDE",
    "IMAD.MOV",
    "IADD",
    "IADD3",
    "LEA",
    "SHF",
    "LOP3",
    "SEL",
    "S2R",
)


@dataclass(frozen=True)
class Instruction:
    index: int
    function: str
    pc: str
    opcode: str
    operands: str
    raw: str
    dest_reg: Optional[str]
    src_regs: Tuple[str, ...]
    mem_base_reg: Optional[str]
    source_file: str
    source_line: str


def repo_root_from_script(script_path: Path) -> Path:
    return script_path.resolve().parents[4]


@lru_cache(maxsize=None)
def normalize_pc(raw_pc: str) -> str:
    return hex(int(raw_pc, 16))


def split_opcode_and_operands(body: str) -> Tuple[str, str]:
    text = body.strip()
    if not text:
        return "", ""
    if text.startswith("@"):
        parts = text.split(None, 1)
        if len(parts) == 1:
            return parts[0], ""
        text = parts[1]
    parts = text.split(None, 1)
    if len(parts) == 1:
        return parts[0].strip(), ""
    return parts[0].strip(), parts[1].strip()


def extract_dest_reg(operands: str) -> Optional[str]:
    if not operands:
        return None
    first = operands.split(",", 1)[0].strip()
    if REGISTER_RE.fullmatch(first):
        return first
    return None


def extract_src_regs(operands: str, dest_reg: Optional[str]) -> Tuple[str, ...]:
    regs = REGISTER_RE.findall(operands)
    if dest_reg and regs and regs[0] == dest_reg:
        regs = regs[1:]
    return tuple(regs)


def extract_mem_base_reg(operands: str) -> Optional[str]:
    match = MEMORY_RE.search(operands)
    if not match:
        return None
    regs = REGISTER_RE.findall(match.group(1))
    for reg in regs:
        if reg.startswith("R"):
            return reg
    return regs[0] if regs else None


def parse_sass(path: Path) -> List[Instruction]:
    instructions: List[Instruction] = []
    current_function = ""
    current_file = ""
    current_line = ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = SECTION_RE.match(line)
        if match:
            current_function = match.group(1)
            continue
        match = TEXT_LABEL_RE.match(line)
        if match:
            current_function = match.group(1)
            continue
        info = LINEINFO_RE.match(line)
        if info:
            current_file = info.group(1)
            current_line = info.group(2)
            continue
        match = INSTRUCTION_RE.match(line)
        if not match:
            continue
        pc = normalize_pc(match.group(1))
        body = match.group(2).strip()
        opcode, operands = split_opcode_and_operands(body)
        dest_reg = extract_dest_reg(operands)
        instructions.append(
            Instruction(
                index=len(instructions),
                function=current_function,
                pc=pc,
                opcode=opcode,
                operands=operands,
                raw=body,
                dest_reg=dest_reg,
                src_regs=extract_src_regs(operands, dest_reg),
                mem_base_reg=extract_mem_base_reg(operands),
                source_file=current_file,
                source_line=current_line,
            )
        )
    return instructions


def is_load(inst: Instruction) -> bool:
    return inst.opcode.startswith("LDG")


def in_main_kernel(inst: Instruction, markers: Sequence[str]) -> bool:
    return any(marker in inst.function for marker in markers)


def nearest_producer(instructions: Sequence[Instruction], idx: int, reg: str, window: int = 20) -> Optional[Instruction]:
    lo = max(0, idx - window)
    for probe in range(idx - 1, lo - 1, -1):
        inst = instructions[probe]
        if inst.dest_reg == reg:
            return inst
    return None


def depends_on_prior_load(
    instructions: Sequence[Instruction],
    idx: int,
    reg: Optional[str],
    visited: Optional[Set[Tuple[int, str]]] = None,
) -> bool:
    if reg is None:
        return False
    if visited is None:
        visited = set()
    key = (idx, reg)
    if key in visited:
        return False
    visited.add(key)
    producer = nearest_producer(instructions, idx, reg)
    if producer is None:
        return False
    if is_load(producer):
        return True
    if producer.opcode.startswith(DEPENDENCE_OP_PREFIXES):
        for src_reg in producer.src_regs:
            if depends_on_prior_load(instructions, producer.index, src_reg, visited):
                return True
    return False


def is_stride_like(instructions: Sequence[Instruction], idx: int, inst: Instruction) -> bool:
    if inst.mem_base_reg is None:
        return False
    producer = nearest_producer(instructions, idx, inst.mem_base_reg)
    if producer is None:
        return False
    if is_load(producer):
        return False
    return producer.opcode.startswith(STRIDE_OP_PREFIXES)


def classify_real_load(instructions: Sequence[Instruction], idx: int, inst: Instruction) -> Tuple[str, str]:
    if depends_on_prior_load(instructions, idx, inst.mem_base_reg):
        return "ima", "address-depends-on-prior-load"
    if is_stride_like(instructions, idx, inst):
        return "stride", "address-computed-without-load-dependency"
    return "regular", "non-ima-load-not-recognized-as-stride"


def collect_load_candidates(workload_cfg: Dict[str, object], instructions: Sequence[Instruction]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    markers = workload_cfg["main_kernels"]
    for idx, inst in enumerate(instructions):
        if not is_load(inst) or not in_main_kernel(inst, markers):
            continue
        load_class, reason = classify_real_load(instructions, idx, inst)
        rows.append(
            {
                "workload": str(workload_cfg["name"]),
                "kernel": inst.function,
                "pc": inst.pc,
                "opcode": inst.opcode,
                "load_class": load_class,
                "reason": reason,
                "source_file": inst.source_file,
                "source_line": inst.source_line,
                "sass": inst.raw,
            }
        )
    return rows


def collect_instruction_mix_row(
    workload_cfg: Dict[str, object],
    instructions: Sequence[Instruction],
    candidate_rows: Sequence[Dict[str, str]],
) -> Dict[str, object]:
    markers = workload_cfg["main_kernels"]
    main_kernel_instructions = [inst for inst in instructions if in_main_kernel(inst, markers)]
    class_counts = {klass: 0 for klass in CLASS_ORDER}
    for row in candidate_rows:
        class_counts[row["load_class"]] += 1

    total_inst_count = len(main_kernel_instructions)
    total_load_count = sum(class_counts.values())
    ima_load_count = class_counts["ima"]
    return {
        "workload": str(workload_cfg["name"]),
        "main_kernel_instruction_count": total_inst_count,
        "main_kernel_load_count": total_load_count,
        "regular_load_count": class_counts["regular"],
        "stride_load_count": class_counts["stride"],
        "ima_load_count": ima_load_count,
        "ima_load_share_of_instructions": f"{(ima_load_count / total_inst_count) if total_inst_count else 0.0:.6f}",
        "ima_load_share_of_loads": f"{(ima_load_count / total_load_count) if total_load_count else 0.0:.6f}",
    }


def consolidate_candidates(candidate_rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        grouped[row["pc"]].append(row)

    classification_rows: List[Dict[str, str]] = []
    classification_map: Dict[str, Dict[str, str]] = {}

    for pc in sorted(grouped, key=lambda value: int(value, 16)):
        rows = grouped[pc]
        classes = sorted({row["load_class"] for row in rows})
        kernels = sorted({row["kernel"] for row in rows})
        sources = sorted({f"{Path(row['source_file']).name}:{row['source_line']}" for row in rows if row["source_file"] or row["source_line"]})
        opcodes = sorted({row["opcode"] for row in rows})
        classification = {
            "workload": rows[0]["workload"],
            "pc": pc,
            "kernel": "|".join(kernels),
            "opcode": "|".join(opcodes),
            "covered": "yes",
            "load_class": classes[0],
            "needs_review": "yes" if len(kernels) > 1 else "no",
            "drop_reason": "",
            "candidate_classes": "|".join(classes),
            "candidate_count": str(len(rows)),
            "source_examples": " | ".join(sources),
            "sass_examples": " || ".join(row["sass"] for row in rows[:3]),
            "reason_examples": " | ".join(sorted({row["reason"] for row in rows})),
        }
        if len(classes) > 1:
            classification["covered"] = "no"
            classification["load_class"] = ""
            classification["needs_review"] = "yes"
            classification["drop_reason"] = "conflicting-main-kernel-classes"
        elif len(kernels) > 1:
            classification["drop_reason"] = "same-class-multi-kernel-pc"
        classification_rows.append(classification)
        classification_map[pc] = classification

    return classification_rows, classification_map


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def aggregate_trace_by_pc(trace_path: Path) -> List[Dict[str, str]]:
    awk_script = r"""
BEGIN { OFS="," }
NR == 1 {
    for (i = 1; i <= NF; ++i) idx[$i] = i
    next
}
$(idx["op"]) == "LD" && $(idx["space"]) == "GLOBAL" {
    pc = tolower($(idx["pc"]))
    status = toupper($(idx["l1_status"]))
    access[pc]++
    if (status == "HIT") hit[pc]++
    if (status == "MISS" || status == "SECTOR_MISS" || status == "RESERVATION_FAIL") {
        miss[pc]++
        if (status == "MISS") miss_only[pc]++
        else if (status == "SECTOR_MISS") sector[pc]++
        else if (status == "RESERVATION_FAIL") reserve[pc]++
    }
}
END {
    print "pc,access_count,hit_count,miss_count,miss_status_count,sector_miss_count,reservation_fail_count"
    for (pc in access) {
        print pc, access[pc] + 0, hit[pc] + 0, miss[pc] + 0, miss_only[pc] + 0, sector[pc] + 0, reserve[pc] + 0
    }
}
"""
    unzip = subprocess.Popen(
        ["gzip", "-dc", str(trace_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    assert unzip.stdout is not None
    awk = subprocess.run(
        ["awk", "-F,", awk_script],
        stdin=unzip.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=False,
    )
    unzip.stdout.close()
    unzip_stderr = unzip.stderr.read() if unzip.stderr is not None else ""
    unzip_code = unzip.wait()
    if unzip_code != 0:
        raise SystemExit(f"failed to decompress {trace_path}: {unzip_stderr.strip()}")
    if awk.returncode != 0:
        raise SystemExit(f"failed to aggregate {trace_path}: {awk.stderr.strip()}")
    rows: List[Dict[str, str]] = []
    for row in csv.DictReader(awk.stdout.splitlines()):
        if not row.get("pc"):
            continue
        row["pc"] = normalize_pc(row["pc"])
        rows.append(row)
    return rows


def analyze_workload(
    workload_name: str,
    raw_pc_rows: Sequence[Dict[str, str]],
    classification_map: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Dict[str, object], List[Dict[str, object]]]:
    total_access = sum(int(row["access_count"]) for row in raw_pc_rows)
    total_miss = sum(int(row["miss_count"]) for row in raw_pc_rows)

    per_pc_rows: List[Dict[str, object]] = []
    covered_rows: List[Dict[str, object]] = []
    class_stats: Dict[str, Dict[str, int]] = {klass: defaultdict(int) for klass in CLASS_ORDER}
    covered_access = 0
    covered_miss = 0

    for raw in sorted(raw_pc_rows, key=lambda row: int(row["pc"], 16)):
        info = classification_map.get(raw["pc"])
        access_count = int(raw["access_count"])
        miss_count = int(raw["miss_count"])
        hit_count = int(raw["hit_count"])
        row = {
            "workload": workload_name,
            "pc": raw["pc"],
            "kernel": info["kernel"] if info else "",
            "covered": "no",
            "load_class": "",
            "needs_review": info["needs_review"] if info else "yes",
            "drop_reason": "",
            "access_count": access_count,
            "hit_count": hit_count,
            "miss_count": miss_count,
            "miss_status_count": int(raw["miss_status_count"]),
            "sector_miss_count": int(raw["sector_miss_count"]),
            "reservation_fail_count": int(raw["reservation_fail_count"]),
            "miss_rate": f"{(miss_count / access_count) if access_count else 0.0:.6f}",
            "access_share_total": f"{(access_count / total_access) if total_access else 0.0:.6f}",
            "miss_share_total": f"{(miss_count / total_miss) if total_miss else 0.0:.6f}",
            "covered_access_share": "",
            "covered_miss_share": "",
        }
        if info is None:
            row["drop_reason"] = "pc-not-in-main-kernel-real-load-set"
        elif info["covered"] != "yes":
            row["drop_reason"] = info["drop_reason"]
        else:
            row["covered"] = "yes"
            row["load_class"] = info["load_class"]
            covered_access += access_count
            covered_miss += miss_count
            covered_rows.append(row)
            stats = class_stats[info["load_class"]]
            stats["access_count"] += access_count
            stats["hit_count"] += hit_count
            stats["miss_count"] += miss_count
            stats["miss_status_count"] += int(raw["miss_status_count"])
            stats["sector_miss_count"] += int(raw["sector_miss_count"])
            stats["reservation_fail_count"] += int(raw["reservation_fail_count"])
        per_pc_rows.append(row)

    for row in covered_rows:
        access_count = int(row["access_count"])
        miss_count = int(row["miss_count"])
        row["covered_access_share"] = f"{(access_count / covered_access) if covered_access else 0.0:.6f}"
        row["covered_miss_share"] = f"{(miss_count / covered_miss) if covered_miss else 0.0:.6f}"

    summary_rows: List[Dict[str, object]] = []
    for load_class in CLASS_ORDER:
        stats = class_stats[load_class]
        access_count = int(stats["access_count"])
        miss_count = int(stats["miss_count"])
        summary_rows.append(
            {
                "workload": workload_name,
                "load_class": load_class,
                "access_count": access_count,
                "hit_count": int(stats["hit_count"]),
                "miss_count": miss_count,
                "miss_status_count": int(stats["miss_status_count"]),
                "sector_miss_count": int(stats["sector_miss_count"]),
                "reservation_fail_count": int(stats["reservation_fail_count"]),
                "access_share": f"{(access_count / covered_access) if covered_access else 0.0:.6f}",
                "miss_share": f"{(miss_count / covered_miss) if covered_miss else 0.0:.6f}",
                "miss_rate": f"{(miss_count / access_count) if access_count else 0.0:.6f}",
                "covered_total_access_count": covered_access,
                "covered_total_miss_count": covered_miss,
            }
        )

    coverage_row = {
        "workload": workload_name,
        "total_global_ld_access_count": total_access,
        "covered_main_kernel_ld_access_count": covered_access,
        "covered_access_ratio": f"{(covered_access / total_access) if total_access else 0.0:.6f}",
        "dropped_access_count": total_access - covered_access,
        "total_global_ld_miss_count": total_miss,
        "covered_main_kernel_ld_miss_count": covered_miss,
        "covered_miss_ratio": f"{(covered_miss / total_miss) if total_miss else 0.0:.6f}",
        "dropped_miss_count": total_miss - covered_miss,
    }

    top_rows: List[Dict[str, object]] = []
    top_slice = sorted(covered_rows, key=lambda row: (-int(row["miss_count"]), -int(row["access_count"]), int(row["pc"], 16)))[:12]
    for rank, row in enumerate(top_slice, start=1):
        ranked = dict(row)
        ranked["rank"] = rank
        top_rows.append(ranked)

    return per_pc_rows, summary_rows, coverage_row, top_rows


def svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def plot_miss_share_svg(path: Path, summary_rows: Sequence[Dict[str, object]], annotate: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows_by_workload: Dict[str, Dict[str, Dict[str, object]]] = defaultdict(dict)
    for row in summary_rows:
        rows_by_workload[str(row["workload"])][str(row["load_class"])] = row

    workload_names = [cfg["name"] for cfg in WORKLOADS]
    display_names = {
        "bfs_ima_high": "BFS",
        "sssp_ima_high": "SSSP",
        "bc_ima_high": "BC",
        "cc_ima_high": "CC",
        "spmv_ima_high": "SpMV",
    }
    display_classes = {
        "regular": "Regular",
        "stride": "Stride",
        "ima": "IMA",
    }

    left_margin = 110
    right_margin = 28
    top_margin = 58
    bottom_margin = 74
    width = 900
    height = 430
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_y0 = top_margin
    chart_y1 = height - bottom_margin
    chart_w = chart_x1 - chart_x0
    chart_h = chart_y1 - chart_y0

    def y_of(value: float) -> float:
        return chart_y1 - (value / 100.0) * chart_h

    group_w = chart_w / max(1, len(workload_names))
    bar_w = min(64.0, group_w * 0.42)
    if bar_w < 34.0:
        bar_w = 34.0

    axis_color = "#1f2937"
    tick_color = "#374151"
    grid_color = "#d7dde5"
    border_color = "#6b7280"
    label_font = "Helvetica, Arial, sans-serif"

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<pattern id="strideHatch" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)">',
        '<rect width="8" height="8" fill="#ffffff"/>',
        '<line x1="0" y1="0" x2="0" y2="8" stroke="#5f5f5f" stroke-width="1.2"/>',
        "</pattern>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{chart_x0}" y1="{chart_y1}" x2="{chart_x1}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.2"/>',
        f'<line x1="{chart_x0}" y1="{chart_y0}" x2="{chart_x0}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.2"/>',
        f'<text x="28" y="{(chart_y0 + chart_y1) / 2:.1f}" text-anchor="middle" font-size="14" font-family="{label_font}" fill="{axis_color}" transform="rotate(-90 28 {(chart_y0 + chart_y1) / 2:.1f})">Share of covered L1 misses (%)</text>',
    ]

    for tick in range(0, 101, 25):
        y = y_of(float(tick))
        lines.append(f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid_color}" stroke-width="0.9" stroke-dasharray="3 3"/>')
        lines.append(f'<text x="{chart_x0 - 14}" y="{y + 4:.2f}" text-anchor="end" font-size="12" font-family="{label_font}" fill="{tick_color}">{tick}</text>')

    legend_gap = 104
    legend_total_w = legend_gap * len(CLASS_ORDER)
    legend_x = chart_x0 + (chart_w - legend_total_w) / 2.0
    legend_y = 18
    for idx, load_class in enumerate(CLASS_ORDER):
        lx = legend_x + idx * legend_gap
        fill = 'url(#strideHatch)' if load_class == "stride" else CLASS_COLORS[load_class]
        lines.append(f'<rect x="{lx:.2f}" y="{legend_y}" width="18" height="18" fill="{fill}" stroke="{border_color}" stroke-width="0.8"/>')
        lines.append(f'<text x="{lx + 26:.2f}" y="{legend_y + 14}" font-size="13" font-family="{label_font}" fill="{axis_color}">{svg_escape(display_classes[load_class])}</text>')

    for group_idx, workload in enumerate(workload_names):
        group_x = chart_x0 + group_idx * group_w
        x = group_x + (group_w - bar_w) / 2.0
        label_x = group_x + group_w / 2.0
        lines.append(f'<text x="{label_x:.2f}" y="{chart_y1 + 34}" text-anchor="middle" font-size="13" font-family="{label_font}" fill="{axis_color}">{svg_escape(display_names.get(workload, workload))}</text>')
        current_pct = 0.0
        last_outside_y = chart_y0 - 999.0
        for load_class in CLASS_ORDER:
            row = rows_by_workload[workload].get(load_class)
            pct = 100.0 * float(row["miss_share"]) if row else 0.0
            if pct <= 0.0:
                continue
            y_top = y_of(current_pct + pct)
            y_bottom = y_of(current_pct)
            h = y_bottom - y_top
            fill = 'url(#strideHatch)' if load_class == "stride" else CLASS_COLORS[load_class]
            lines.append(f'<rect x="{x:.2f}" y="{y_top:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{fill}" stroke="{border_color}" stroke-width="0.6"/>')
            if annotate:
                label = f"{pct:.1f}%"
                label_x = x + bar_w / 2.0
                label_y = y_top + h / 2.0 + 4.0
                if h >= 18.0:
                    text_color = "#ffffff" if load_class == "ima" else axis_color
                    lines.append(f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="middle" font-size="11" font-family="{label_font}" font-weight="600" fill="{text_color}">{label}</text>')
                else:
                    outside_y = y_top + h / 2.0 + 4.0
                    if outside_y <= last_outside_y + 12.0:
                        outside_y = last_outside_y + 12.0
                    outside_y = min(outside_y, chart_y1 - 6.0)
                    line_x0 = x + bar_w + 2.0
                    line_x1 = x + bar_w + 10.0
                    text_x = x + bar_w + 14.0
                    lines.append(f'<line x1="{line_x0:.2f}" y1="{y_top + h / 2.0:.2f}" x2="{line_x1:.2f}" y2="{outside_y - 4.0:.2f}" stroke="{axis_color}" stroke-width="0.8"/>')
                    lines.append(f'<text x="{text_x:.2f}" y="{outside_y:.2f}" text-anchor="start" font-size="11" font-family="{label_font}" font-weight="600" fill="{axis_color}">{label}</text>')
                    last_outside_y = outside_y
            current_pct += pct
        lines.append(f'<rect x="{x:.2f}" y="{chart_y0:.2f}" width="{bar_w:.2f}" height="{chart_h:.2f}" fill="none" stroke="{border_color}" stroke-width="0.8"/>')

    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_instruction_mix_svg(path: Path, instruction_mix_rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    display_names = {
        "bfs_ima_high": "BFS",
        "sssp_ima_high": "SSSP",
        "bc_ima_high": "BC",
        "cc_ima_high": "CC",
        "spmv_ima_high": "SpMV",
    }
    rows_by_workload = {str(row["workload"]): row for row in instruction_mix_rows}
    workload_names = [cfg["name"] for cfg in WORKLOADS]

    left_margin = 110
    right_margin = 28
    top_margin = 42
    bottom_margin = 74
    width = 900
    height = 360
    chart_x0 = left_margin
    chart_x1 = width - right_margin
    chart_y0 = top_margin
    chart_y1 = height - bottom_margin
    chart_w = chart_x1 - chart_x0
    chart_h = chart_y1 - chart_y0

    max_pct = 0.0
    for workload in workload_names:
        row = rows_by_workload[workload]
        max_pct = max(max_pct, 100.0 * float(row["ima_load_share_of_loads"]))
    tick_max = max(10.0, ((max_pct + 4.9) // 5) * 5)
    if tick_max - max_pct < 1.5:
        tick_max += 5.0

    def y_of(value: float) -> float:
        return chart_y1 - (value / tick_max) * chart_h

    group_w = chart_w / max(1, len(workload_names))
    bar_w = min(70.0, group_w * 0.46)
    if bar_w < 36.0:
        bar_w = 36.0

    axis_color = "#1f2937"
    tick_color = "#374151"
    grid_color = "#d7dde5"
    border_color = "#4b5563"
    label_font = "Helvetica, Arial, sans-serif"

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<line x1="{chart_x0}" y1="{chart_y1}" x2="{chart_x1}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.2"/>',
        f'<line x1="{chart_x0}" y1="{chart_y0}" x2="{chart_x0}" y2="{chart_y1}" stroke="{axis_color}" stroke-width="1.2"/>',
        f'<text x="28" y="{(chart_y0 + chart_y1) / 2:.1f}" text-anchor="middle" font-size="14" font-family="{label_font}" fill="{axis_color}" transform="rotate(-90 28 {(chart_y0 + chart_y1) / 2:.1f})">IMA loads / all static LDG* instructions (%)</text>',
    ]

    tick = 0.0
    while tick <= tick_max + 1e-6:
        y = y_of(tick)
        lines.append(f'<line x1="{chart_x0}" y1="{y:.2f}" x2="{chart_x1}" y2="{y:.2f}" stroke="{grid_color}" stroke-width="0.9" stroke-dasharray="3 3"/>')
        lines.append(f'<text x="{chart_x0 - 14}" y="{y + 4:.2f}" text-anchor="end" font-size="12" font-family="{label_font}" fill="{tick_color}">{tick:.0f}</text>')
        tick += 5.0

    for group_idx, workload in enumerate(workload_names):
        row = rows_by_workload[workload]
        pct = 100.0 * float(row["ima_load_share_of_loads"])
        group_x = chart_x0 + group_idx * group_w
        x = group_x + (group_w - bar_w) / 2.0
        label_x = group_x + group_w / 2.0
        y_top = y_of(pct)
        bar_h = chart_y1 - y_top
        lines.append(f'<rect x="{x:.2f}" y="{y_top:.2f}" width="{bar_w:.2f}" height="{bar_h:.2f}" fill="#6b6b6b" stroke="{border_color}" stroke-width="0.8"/>')
        lines.append(f'<text x="{label_x:.2f}" y="{chart_y1 + 34}" text-anchor="middle" font-size="13" font-family="{label_font}" fill="{axis_color}">{svg_escape(display_names.get(workload, workload))}</text>')
        lines.append(f'<text x="{label_x:.2f}" y="{max(y_top - 8.0, chart_y0 + 12.0):.2f}" text-anchor="middle" font-size="11" font-family="{label_font}" font-weight="600" fill="{axis_color}">{pct:.1f}%</text>')

    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_pct(raw_value: str) -> str:
    return f"{100.0 * float(raw_value):.1f}%"


def build_markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_analysis_md(
    path: Path,
    summary_rows: Sequence[Dict[str, object]],
    coverage_rows: Sequence[Dict[str, object]],
    top_rows: Sequence[Dict[str, object]],
    instruction_mix_rows: Sequence[Dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows_by_workload: Dict[str, Dict[str, Dict[str, object]]] = defaultdict(dict)
    coverage_by_workload: Dict[str, Dict[str, object]] = {}
    top_by_workload: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    instruction_mix_by_workload: Dict[str, Dict[str, object]] = {}
    for row in summary_rows:
        rows_by_workload[str(row["workload"])][str(row["load_class"])] = row
    for row in coverage_rows:
        coverage_by_workload[str(row["workload"])] = row
    for row in top_rows:
        top_by_workload[str(row["workload"])].append(row)
    for row in instruction_mix_rows:
        instruction_mix_by_workload[str(row["workload"])] = row

    miss_headers = ["Workload", "regular miss_share", "stride miss_share", "ima miss_share"]
    miss_rows: List[List[str]] = []
    coverage_headers = ["Workload", "covered access", "covered miss", "dropped access", "dropped miss"]
    coverage_md_rows: List[List[str]] = []
    instruction_headers = ["Workload", "IMA loads / loads", "IMA loads / instructions", "IMA static loads", "All static loads", "All main-kernel inst"]
    instruction_md_rows: List[List[str]] = []
    findings: List[str] = []
    top_md_rows: List[List[str]] = []

    for cfg in WORKLOADS:
        workload = str(cfg["name"])
        class_rows = rows_by_workload[workload]
        dominant_class = max(CLASS_ORDER, key=lambda klass: float(class_rows[klass]["miss_share"]))
        findings.append(f"- `{workload}` 的 covered main-kernel miss 主导类是 `{dominant_class}`，miss_share = {format_pct(str(class_rows[dominant_class]['miss_share']))}。")
        miss_rows.append(
            [
                workload,
                format_pct(str(class_rows["regular"]["miss_share"])),
                format_pct(str(class_rows["stride"]["miss_share"])),
                format_pct(str(class_rows["ima"]["miss_share"])),
            ]
        )
        coverage = coverage_by_workload[workload]
        coverage_md_rows.append(
            [
                workload,
                format_pct(str(coverage["covered_access_ratio"])),
                format_pct(str(coverage["covered_miss_ratio"])),
                str(coverage["dropped_access_count"]),
                str(coverage["dropped_miss_count"]),
            ]
        )
        instruction_mix = instruction_mix_by_workload[workload]
        instruction_md_rows.append(
            [
                workload,
                format_pct(str(instruction_mix["ima_load_share_of_loads"])),
                format_pct(str(instruction_mix["ima_load_share_of_instructions"])),
                str(instruction_mix["ima_load_count"]),
                str(instruction_mix["main_kernel_load_count"]),
                str(instruction_mix["main_kernel_instruction_count"]),
            ]
        )
        for row in top_by_workload[workload][:4]:
            top_md_rows.append(
                [
                    workload,
                    str(row["rank"]),
                    str(row["kernel"]),
                    str(row["pc"]),
                    str(row["load_class"]),
                    str(row["miss_count"]),
                    format_pct(str(row["miss_rate"])),
                ]
            )

    instruction_load_shares = [float(row["ima_load_share_of_loads"]) for row in instruction_mix_rows]
    miss_shares = [float(row["miss_share"]) for row in summary_rows if str(row["load_class"]) == "ima"]
    findings.append(
        "- Static load mix shows that IMA loads span "
        f"{format_pct(f'{min(instruction_load_shares):.6f}')}–{format_pct(f'{max(instruction_load_shares):.6f}')}"
        " of real static `LDG*` instructions, but they account for "
        f"{format_pct(f'{min(miss_shares):.6f}')}–{format_pct(f'{max(miss_shares):.6f}')}"
        " of covered L1 misses across `ima_high`."
    )

    body = [
        "# ima_high baseline L1 miss breakdown",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Method",
        "",
        "- SASS baseline: runtime `sm_80` SASS extracted from NVBit runtime cubins and mirrored under `ima_plan/01_ima_characterization/sass_analysis/`.",
        "- Scope: only real `LDG*` instructions from the main kernel(s) of each workload.",
        "- Three classes only: `regular`, `stride`, `ima`.",
        "- Rule priority: if a load address depends on a prior load value, classify it as `ima`; otherwise, if the address is computed by regular arithmetic without load dependency, classify it as `stride`; all remaining covered loads are `regular`.",
        "- Trace PCs that do not map to those real main-kernel load PCs are excluded from the main summary and reported through coverage.",
        "",
        "## Key Findings",
        "",
        *findings,
        "",
        "## Coverage Summary",
        "",
        build_markdown_table(coverage_headers, coverage_md_rows),
        "",
        "## Miss Share Summary",
        "",
        build_markdown_table(miss_headers, miss_rows),
        "",
        "## Static Load Mix",
        "",
        "- The table below uses runtime `sm_80` SASS from the traced main kernels, so it reflects static SASS composition rather than dynamic issue counts.",
        "- The figure and the first ratio column use `IMA loads / all static LDG* instructions`, which is the requested load-only view.",
        "",
        build_markdown_table(instruction_headers, instruction_md_rows),
        "",
        "## Top Miss PCs",
        "",
        build_markdown_table(["Workload", "Rank", "Kernel", "PC", "Class", "Miss count", "Miss rate"], top_md_rows),
        "",
        "## Outputs",
        "",
        "- `data/pc_classification.csv`",
        "- `data/pc_classification_candidates.csv`",
        "- `data/per_pc_stats.csv`",
        "- `data/per_workload_class_summary.csv`",
        "- `data/coverage_summary.csv`",
        "- `data/per_workload_top_miss_pcs.csv`",
        "- `data/instruction_mix_summary.csv`",
        "- `figures/ima_high_baseline_l1_miss_share.svg`",
        "- `figures/ima_high_baseline_l1_miss_share_no_labels.svg`",
        "- `figures/ima_high_baseline_ima_instruction_share.svg`",
        "",
    ]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def process_workload(task: Tuple[str, Dict[str, object]]) -> Dict[str, object]:
    repo_root_str, workload_cfg = task
    repo_root = Path(repo_root_str)
    instructions = parse_sass(repo_root / str(workload_cfg["sass"]))
    candidate_rows = collect_load_candidates(workload_cfg, instructions)
    instruction_mix_row = collect_instruction_mix_row(workload_cfg, instructions, candidate_rows)
    classification_rows, classification_map = consolidate_candidates(candidate_rows)
    raw_pc_rows = aggregate_trace_by_pc(repo_root / "result" / "L1cache_trace" / f"{workload_cfg['name']}_l1.csv.gz")
    per_pc_rows, summary_rows, coverage_row, top_rows = analyze_workload(str(workload_cfg["name"]), raw_pc_rows, classification_map)
    return {
        "candidate_rows": candidate_rows,
        "instruction_mix_row": instruction_mix_row,
        "classification_rows": classification_rows,
        "per_pc_rows": per_pc_rows,
        "summary_rows": summary_rows,
        "coverage_row": coverage_row,
        "top_rows": top_rows,
    }


def main() -> None:
    script_path = Path(__file__)
    repo_root = repo_root_from_script(script_path)
    output_root = script_path.resolve().parents[1]
    data_dir = output_root / "data"
    figure_dir = output_root / "figures"

    all_candidate_rows: List[Dict[str, object]] = []
    all_classification_rows: List[Dict[str, object]] = []
    all_per_pc_rows: List[Dict[str, object]] = []
    all_summary_rows: List[Dict[str, object]] = []
    all_coverage_rows: List[Dict[str, object]] = []
    all_top_rows: List[Dict[str, object]] = []
    all_instruction_mix_rows: List[Dict[str, object]] = []

    tasks = [(str(repo_root), cfg) for cfg in WORKLOADS]
    results_by_workload: Dict[str, Dict[str, object]] = {}
    with ProcessPoolExecutor(max_workers=len(WORKLOADS)) as executor:
        future_to_name = {executor.submit(process_workload, task): str(task[1]["name"]) for task in tasks}
        done = 0
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            results_by_workload[name] = future.result()
            done += 1
            print(f"[{done}/{len(WORKLOADS)}] finished {name}", flush=True)

    for cfg in WORKLOADS:
        name = str(cfg["name"])
        result = results_by_workload[name]
        all_candidate_rows.extend(result["candidate_rows"])
        all_instruction_mix_rows.append(result["instruction_mix_row"])
        all_classification_rows.extend(result["classification_rows"])
        all_per_pc_rows.extend(result["per_pc_rows"])
        all_summary_rows.extend(result["summary_rows"])
        all_coverage_rows.append(result["coverage_row"])
        all_top_rows.extend(result["top_rows"])

    write_csv(
        data_dir / "pc_classification_candidates.csv",
        ("workload", "kernel", "pc", "opcode", "load_class", "reason", "source_file", "source_line", "sass"),
        all_candidate_rows,
    )
    write_csv(
        data_dir / "pc_classification.csv",
        ("workload", "kernel", "pc", "opcode", "covered", "load_class", "needs_review", "drop_reason", "candidate_classes", "candidate_count", "reason_examples", "source_examples", "sass_examples"),
        all_classification_rows,
    )
    write_csv(
        data_dir / "per_pc_stats.csv",
        ("workload", "pc", "kernel", "covered", "load_class", "needs_review", "drop_reason", "access_count", "hit_count", "miss_count", "miss_status_count", "sector_miss_count", "reservation_fail_count", "miss_rate", "access_share_total", "miss_share_total", "covered_access_share", "covered_miss_share"),
        all_per_pc_rows,
    )
    write_csv(
        data_dir / "per_workload_class_summary.csv",
        ("workload", "load_class", "access_count", "hit_count", "miss_count", "miss_status_count", "sector_miss_count", "reservation_fail_count", "access_share", "miss_share", "miss_rate", "covered_total_access_count", "covered_total_miss_count"),
        all_summary_rows,
    )
    write_csv(
        data_dir / "coverage_summary.csv",
        ("workload", "total_global_ld_access_count", "covered_main_kernel_ld_access_count", "covered_access_ratio", "dropped_access_count", "total_global_ld_miss_count", "covered_main_kernel_ld_miss_count", "covered_miss_ratio", "dropped_miss_count"),
        all_coverage_rows,
    )
    write_csv(
        data_dir / "instruction_mix_summary.csv",
        ("workload", "main_kernel_instruction_count", "main_kernel_load_count", "regular_load_count", "stride_load_count", "ima_load_count", "ima_load_share_of_instructions", "ima_load_share_of_loads"),
        all_instruction_mix_rows,
    )
    write_csv(
        data_dir / "per_workload_top_miss_pcs.csv",
        ("workload", "rank", "kernel", "pc", "covered", "load_class", "needs_review", "drop_reason", "access_count", "hit_count", "miss_count", "miss_status_count", "sector_miss_count", "reservation_fail_count", "miss_rate", "access_share_total", "miss_share_total", "covered_access_share", "covered_miss_share"),
        all_top_rows,
    )
    plot_miss_share_svg(figure_dir / "ima_high_baseline_l1_miss_share.svg", all_summary_rows, annotate=True)
    plot_miss_share_svg(figure_dir / "ima_high_baseline_l1_miss_share_no_labels.svg", all_summary_rows, annotate=False)
    plot_instruction_mix_svg(figure_dir / "ima_high_baseline_ima_instruction_share.svg", all_instruction_mix_rows)
    write_analysis_md(output_root / "analysis.md", all_summary_rows, all_coverage_rows, all_top_rows, all_instruction_mix_rows)


if __name__ == "__main__":
    main()
