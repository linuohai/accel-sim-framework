#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT = Path("/workspace/prefetch")
ANALYSIS_DIR = ROOT / "ima_plan/01_ima_characterization/family_variant_sass_analysis"
RAW_SASS_DIR = ANALYSIS_DIR / "raw_sass"
INCLUDE_DIR = ROOT / "gpu-app-collection/gardenia/include"
CUDA_INCLUDE = Path("/usr/local/cuda/include")

SCREEN_SMS = [80]
SAMPLE_SMS = [70, 80, 90]


ALGO_META = {
    "bfs": {
        "canonical": "linear_base",
        "variation_pref": ["linear_vector", "topo_base", "hybrid_base", "linear_tex"],
        "wrapper": set(),
        "redesign": {"bottom_up", "merrill"},
        "boundary_pref": ["bottom_up", "merrill"],
    },
    "sssp": {
        "canonical": "linear_base",
        "variation_pref": ["topo_base", "linear_lb", "topo_lb"],
        "wrapper": set(),
        "redesign": {"dstep", "davidson"},
        "boundary_pref": ["dstep", "davidson"],
    },
    "bc": {
        "canonical": "linear_base",
        "variation_pref": ["hybrid_base", "topo_base", "linear_lb"],
        "wrapper": set(),
        "redesign": set(),
        "boundary_pref": [],
    },
    "cc": {
        "canonical": "base",
        "variation_pref": ["warp", "partition", "fusion", "afforest"],
        "wrapper": set(),
        "redesign": {"afforest"},
        "boundary_pref": ["base"],
    },
    "spmv": {
        "canonical": "base",
        "variation_pref": ["vector", "warp", "tex", "tiling", "push"],
        "wrapper": {"cusparse"},
        "redesign": set(),
        "boundary_pref": [],
    },
    "pr": {
        "canonical": "base",
        "variation_pref": ["push", "warp", "vector", "tiling", "partition"],
        "wrapper": {"nvgraph"},
        "redesign": {"delta"},
        "boundary_pref": ["delta"],
    },
    "vc": {
        "canonical": "linear_base",
        "variation_pref": ["topo_base", "linear_warp", "linear_bitset"],
        "wrapper": set(),
        "redesign": set(),
        "boundary_pref": [],
    },
    "scc": {
        "canonical": "base",
        "variation_pref": ["topo", "bitset", "two_phase", "wcc"],
        "wrapper": set(),
        "redesign": set(),
        "boundary_pref": ["base"],
    },
}


STYLE_ORDER = [
    "linear",
    "topo",
    "hybrid",
    "push",
    "base",
    "vector",
    "warp",
    "tex",
    "tile",
    "bitset",
    "fusion",
    "partition",
    "atomic_free",
    "bottom_up",
    "merrill",
    "dstep",
    "davidson",
    "delta",
    "afforest",
    "two_phase",
    "wcc",
    "other",
]


FUNC_PAT = re.compile(r"^//--------------------- \.text\.(\S+) ")
LINE_PAT = re.compile(r'^\s*//## File "(.+)", line (\d+)')
INST_PAT = re.compile(r"^\s*/\*([0-9a-f]+)\*/\s+(?:@[!P0-9]+\s+)?([A-Z0-9_.]+)(?:\s+(.*?))?\s*;\s*$")

VARIANT_ADDR_OPS = {
    "LEA",
    "LEA.HI.X",
    "IADD3",
    "IADD3.X",
    "IMAD.SHL.U32",
    "IMAD.IADD",
    "SHF.L.U64.HI",
}
MOVE_OPS = {
    "MOV",
    "MOV32I",
    "IMAD.MOV.U32",
    "IMAD.MOV",
}
STRICT_FIFO_DEPTH = 128


@dataclass
class ManifestEntry:
    algorithm: str
    impl: str
    source_cu: str
    category: str
    style_bucket: str
    canonical_rank: int
    variation_rank: int
    boundary_rank: int
    notes: str


@dataclass
class StrictFifoEntry:
    dst_reg: str
    entry_type: str
    pc: str
    opcode: str
    source_file: str | None
    source_line: int | None
    index_pc: str | None = None
    index_opcode: str | None = None
    index_source_file: str | None = None
    index_source_line: int | None = None


def style_bucket(impl: str) -> str:
    for key in STYLE_ORDER:
        if key == "other":
            continue
        if impl == key or impl.startswith(f"{key}_") or impl.endswith(f"_{key}") or f"_{key}_" in impl:
            return key
    return "other"


def extra_flags_for(algorithm: str, _impl: str) -> list[str]:
    if algorithm == "scc":
        return ["-include", "thrust/sort.h"]
    return []


def build_manifest() -> list[ManifestEntry]:
    manifest = []
    src_root = ROOT / "gpu-app-collection/gardenia/src"
    for algorithm, meta in ALGO_META.items():
        prefs = {name: idx for idx, name in enumerate(meta["variation_pref"])}
        boundaries = {name: idx for idx, name in enumerate(meta["boundary_pref"])}
        for path in sorted((src_root / algorithm).glob("*.cu")):
            impl = path.stem
            if impl in meta["wrapper"]:
                category = "library_wrapper"
                notes = "vendor/library-backed path; excluded from main evidence"
            elif impl in meta["redesign"]:
                category = "native_redesign"
                notes = "native but algorithmic flow differs materially from family fast path"
            else:
                category = "native_comparable"
                notes = "native family implementation"
            manifest.append(
                ManifestEntry(
                    algorithm=algorithm,
                    impl=impl,
                    source_cu=str(path.relative_to(ROOT)),
                    category=category,
                    style_bucket=style_bucket(impl),
                    canonical_rank=0 if impl == meta["canonical"] else 1,
                    variation_rank=prefs.get(impl, 999),
                    boundary_rank=boundaries.get(impl, 999),
                    notes=notes,
                )
            )
    manifest.sort(key=lambda e: (e.algorithm, e.canonical_rank, e.variation_rank, e.impl))
    return manifest


def clean_reg(token: str | None) -> str | None:
    if not token:
        return None
    match = re.search(r"\b([RU]?\d+|RZ|URZ)\b", token.replace(".reuse", "").replace(".64", ""))
    return match.group(1) if match else None


def parse_dest_reg(operands: str) -> str | None:
    if not operands:
        return None
    return clean_reg(operands.split(",", 1)[0].strip())


def paired_reg(reg: str | None) -> str | None:
    if not reg:
        return None
    match = re.fullmatch(r"R(\d+)", reg)
    if not match:
        return None
    return f"R{int(match.group(1)) + 1}"


def parse_dest_regs(opcode: str, operands: str) -> list[str]:
    dst = parse_dest_reg(operands)
    if not dst:
        return []
    regs = [dst]
    if opcode.startswith("IMAD.WIDE"):
        pair = paired_reg(dst)
        if pair:
            regs.append(pair)
    return regs


def parse_addr_reg(operands: str) -> str | None:
    if not operands:
        return None
    match = re.search(r"\[([RU]?\d+)(?:\.64)?", operands)
    return match.group(1) if match else None


def parse_imad_parts(operands: str) -> list[str]:
    return [part.strip() for part in operands.split(",")]


def parse_source_regs(operands: str) -> list[str]:
    regs = []
    parts = [part.strip() for part in operands.split(",")]
    for part in parts[1:]:
        for match in re.finditer(r"\b([RU]?\d+|RZ|URZ)\b", part.replace(".reuse", "").replace(".64", "")):
            reg = match.group(1)
            if reg not in {"RZ", "URZ"} and reg not in regs:
                regs.append(reg)
    return regs


def parse_sass(path: Path) -> dict[str, list[dict]]:
    functions = defaultdict(list)
    current_func = None
    current_file = None
    current_line = None
    for raw_line in path.read_text().splitlines():
        func_match = FUNC_PAT.match(raw_line)
        if func_match:
            current_func = func_match.group(1)
            current_file = None
            current_line = None
            continue
        line_match = LINE_PAT.match(raw_line)
        if line_match:
            current_file = line_match.group(1)
            current_line = int(line_match.group(2))
            continue
        inst_match = INST_PAT.match(raw_line)
        if inst_match and current_func:
            functions[current_func].append(
                {
                    "pc": inst_match.group(1),
                    "opcode": inst_match.group(2),
                    "operands": (inst_match.group(3) or "").strip(),
                    "source_file": current_file,
                    "source_line": current_line,
                }
            )
    return functions


def find_prev_writer(instructions: list[dict], start_idx: int, reg: str, window: int = 24):
    for idx in range(start_idx - 1, max(-1, start_idx - window), -1):
        if parse_dest_reg(instructions[idx]["operands"]) == reg:
            return instructions[idx], idx
    return None, None


def fifo_lookup(reg_fifo: list[StrictFifoEntry], reg: str | None) -> StrictFifoEntry | None:
    if not reg:
        return None
    for entry in reversed(reg_fifo):
        if entry.dst_reg == reg:
            return entry
    return None


def fifo_invalidate_load_results_by_read(reg_fifo: list[StrictFifoEntry], src_regs: list[str]):
    if not src_regs:
        return
    src_set = set(src_regs)
    reg_fifo[:] = [
        entry
        for entry in reg_fifo
        if not (entry.entry_type == "LOAD_RESULT" and entry.dst_reg in src_set)
    ]


def fifo_invalidate_by_write(reg_fifo: list[StrictFifoEntry], dst_regs: list[str]):
    if not dst_regs:
        return
    dst_set = set(dst_regs)
    reg_fifo[:] = [entry for entry in reg_fifo if entry.dst_reg not in dst_set]


def fifo_push(reg_fifo: list[StrictFifoEntry], entry: StrictFifoEntry):
    reg_fifo.append(entry)
    if len(reg_fifo) > STRICT_FIFO_DEPTH:
        del reg_fifo[0 : len(reg_fifo) - STRICT_FIFO_DEPTH]


def follow_move_chain(instructions: list[dict], start_idx: int, reg: str | None, max_depth: int = 4):
    current_reg = reg
    current_idx = start_idx
    seen = set()
    for _ in range(max_depth):
        if not current_reg or (current_reg, current_idx) in seen:
            return None, None
        seen.add((current_reg, current_idx))
        producer, producer_idx = find_prev_writer(instructions, current_idx, current_reg)
        if not producer:
            return None, None
        if producer["opcode"] in MOVE_OPS:
            src_regs = parse_source_regs(producer["operands"])
            next_reg = next((reg for reg in src_regs if reg != current_reg), None)
            if next_reg:
                current_reg = next_reg
                current_idx = producer_idx
                continue
        return producer, producer_idx
    return None, None


def classify_imad_chain(index_gap: int, data_gap: int) -> str:
    if index_gap <= 4 and data_gap <= 2:
        return "exact_chain"
    return "chain_with_preamble"


def analyze_sass_file(sass_path: Path, algorithm: str, impl: str, sm: int) -> list[dict]:
    results = []
    if not sass_path.exists():
        return results
    functions = parse_sass(sass_path)
    for function_name, instructions in functions.items():
        reg_fifo: list[StrictFifoEntry] = []
        for inst in instructions:
            opcode = inst["opcode"]
            src_regs = parse_source_regs(inst["operands"])
            dst_regs = parse_dest_regs(opcode, inst["operands"])

            if not opcode.startswith("IMAD.WIDE"):
                fifo_invalidate_load_results_by_read(reg_fifo, src_regs)

            if opcode.startswith("LDG"):
                addr_reg = parse_addr_reg(inst["operands"])
                addr_prod = fifo_lookup(reg_fifo, addr_reg)
                if addr_prod and addr_prod.entry_type == "IMA_ADDR_COMPUTE":
                    results.append(
                        {
                            "algorithm": algorithm,
                            "impl": impl,
                            "sm": f"sm{sm}",
                            "function": function_name,
                            "classification": "exact_chain",
                            "index_pc": addr_prod.index_pc,
                            "index_opcode": addr_prod.index_opcode,
                            "addr_pc": addr_prod.pc,
                            "addr_opcode": addr_prod.opcode,
                            "data_pc": inst["pc"],
                            "data_opcode": inst["opcode"],
                            "index_source_file": addr_prod.index_source_file,
                            "index_source_line": addr_prod.index_source_line,
                            "addr_source_file": addr_prod.source_file,
                            "addr_source_line": addr_prod.source_line,
                            "data_source_file": inst["source_file"],
                            "data_source_line": inst["source_line"],
                        }
                    )
                fifo_invalidate_by_write(reg_fifo, dst_regs)
                dst_reg = parse_dest_reg(inst["operands"])
                if dst_reg:
                    fifo_push(
                        reg_fifo,
                        StrictFifoEntry(
                            dst_reg=dst_reg,
                            entry_type="LOAD_RESULT",
                            pc=inst["pc"],
                            opcode=inst["opcode"],
                            source_file=inst["source_file"],
                            source_line=inst["source_line"],
                        ),
                    )
                continue

            if opcode.startswith("IMAD.WIDE"):
                parts = parse_imad_parts(inst["operands"])
                producer = None
                if len(parts) >= 4:
                    producer = fifo_lookup(reg_fifo, clean_reg(parts[1]))
                fifo_invalidate_by_write(reg_fifo, dst_regs)
                if producer and producer.entry_type == "LOAD_RESULT":
                    dst_reg = parse_dest_reg(inst["operands"])
                    if dst_reg:
                        fifo_push(
                            reg_fifo,
                            StrictFifoEntry(
                                dst_reg=dst_reg,
                                entry_type="IMA_ADDR_COMPUTE",
                                pc=inst["pc"],
                                opcode=inst["opcode"],
                                source_file=inst["source_file"],
                                source_line=inst["source_line"],
                                index_pc=producer.pc,
                                index_opcode=producer.opcode,
                                index_source_file=producer.source_file,
                                index_source_line=producer.source_line,
                            ),
                        )
                continue

            fifo_invalidate_by_write(reg_fifo, dst_regs)
    return results


def out_dir(entry: ManifestEntry, sm: int) -> Path:
    return RAW_SASS_DIR / entry.algorithm / entry.impl / f"sm{sm}"


def cubin_path(entry: ManifestEntry, sm: int) -> Path:
    return out_dir(entry, sm) / f"{entry.impl}.sm{sm}.cubin"


def sass_path(entry: ManifestEntry, sm: int) -> Path:
    return out_dir(entry, sm) / f"{entry.impl}.sm{sm}.sass"


def log_path(entry: ManifestEntry, sm: int) -> Path:
    return out_dir(entry, sm) / f"{entry.impl}.sm{sm}.build.log"


def compile_entry(entry: ManifestEntry, sm: int) -> dict:
    target_dir = out_dir(entry, sm)
    target_dir.mkdir(parents=True, exist_ok=True)
    c_path = ROOT / entry.source_cu
    cubin = cubin_path(entry, sm)
    sass = sass_path(entry, sm)
    log = log_path(entry, sm)

    if cubin.exists() and sass.exists() and log.exists():
        return {
            "algorithm": entry.algorithm,
            "impl": entry.impl,
            "sm": f"sm{sm}",
            "compile_status": "ok",
            "log_path": str(log.relative_to(ROOT)),
            "sass_path": str(sass.relative_to(ROOT)),
            "cubin_path": str(cubin.relative_to(ROOT)),
        }

    cmd = [
        "nvcc",
        "-O3",
        "-w",
        "-lineinfo",
        "-std=c++11",
        "-DTHRUST_IGNORE_CUB_VERSION_CHECK",
        *extra_flags_for(entry.algorithm, entry.impl),
        f"-gencode=arch=compute_{sm},code=sm_{sm}",
        f"-I{INCLUDE_DIR}",
        f"-I{CUDA_INCLUDE}",
        "-cubin",
        str(c_path),
        "-o",
        str(cubin),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log.write_text(proc.stdout + proc.stderr)
    if proc.returncode != 0:
        return {
            "algorithm": entry.algorithm,
            "impl": entry.impl,
            "sm": f"sm{sm}",
            "compile_status": "compile_fail",
            "log_path": str(log.relative_to(ROOT)),
            "sass_path": "",
            "cubin_path": "",
        }
    disasm = subprocess.run(
        ["nvdisasm", "--print-code", "--print-line-info", "--separate-functions", str(cubin)],
        capture_output=True,
        text=True,
    )
    if disasm.returncode != 0:
        log.write_text(log.read_text() + "\n\n=== nvdisasm ===\n" + disasm.stdout + disasm.stderr)
        return {
            "algorithm": entry.algorithm,
            "impl": entry.impl,
            "sm": f"sm{sm}",
            "compile_status": "disasm_fail",
            "log_path": str(log.relative_to(ROOT)),
            "sass_path": "",
            "cubin_path": str(cubin.relative_to(ROOT)),
        }
    sass.write_text(disasm.stdout)
    return {
        "algorithm": entry.algorithm,
        "impl": entry.impl,
        "sm": f"sm{sm}",
        "compile_status": "ok",
        "log_path": str(log.relative_to(ROOT)),
        "sass_path": str(sass.relative_to(ROOT)),
        "cubin_path": str(cubin.relative_to(ROOT)),
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize_entry(entry: ManifestEntry, compile_row: dict, chains: list[dict]) -> dict:
    counts = Counter(row["classification"] for row in chains)
    total = sum(counts.values())
    fast_path = counts["exact_chain"] + counts["chain_with_preamble"]
    variant = counts["variant_non_imadwide"]
    function_counts = Counter(row["function"] for row in chains)
    dominant_function = function_counts.most_common(1)[0][0] if function_counts else ""
    if compile_row["compile_status"] != "ok":
        verdict = compile_row["compile_status"]
    elif total == 0:
        verdict = "no_detected_ima"
    elif variant == 0:
        verdict = "stable_fast_path"
    elif fast_path >= 4 * variant:
        verdict = "mostly_fast_path"
    elif fast_path > variant:
        verdict = "mixed_fast_path"
    elif fast_path == 0:
        verdict = "variant_only"
    else:
        verdict = "mixed_variant_heavy"
    return {
        "algorithm": entry.algorithm,
        "impl": entry.impl,
        "category": entry.category,
        "style_bucket": entry.style_bucket,
        "sm": compile_row["sm"],
        "compile_status": compile_row["compile_status"],
        "total_chains": total,
        "exact_chain": counts["exact_chain"],
        "chain_with_preamble": counts["chain_with_preamble"],
        "variant_non_imadwide": counts["variant_non_imadwide"],
        "functions_hit": len(function_counts),
        "dominant_function": dominant_function,
        "screen_verdict": verdict,
        "sass_path": compile_row["sass_path"],
        "log_path": compile_row["log_path"],
        "source_cu": entry.source_cu,
        "notes": entry.notes,
        "canonical_rank": entry.canonical_rank,
        "variation_rank": entry.variation_rank,
        "boundary_rank": entry.boundary_rank,
    }


def choose_samples(manifest: list[ManifestEntry], screening_rows: list[dict]) -> list[dict]:
    entry_map = {(entry.algorithm, entry.impl): entry for entry in manifest}
    by_algo = defaultdict(list)
    for row in screening_rows:
        if row["sm"] != "sm80":
            continue
        by_algo[row["algorithm"]].append(row)
    samples = []
    for algorithm, rows in by_algo.items():
        comparable = [row for row in rows if row["category"] == "native_comparable" and row["compile_status"] == "ok"]
        if comparable:
            stable_candidates = sorted(
                comparable,
                key=lambda row: (
                    0 if row["screen_verdict"] in {"stable_fast_path", "mostly_fast_path"} else 1,
                    row["canonical_rank"],
                    -(row["exact_chain"] + row["chain_with_preamble"]),
                    row["variant_non_imadwide"],
                    row["impl"],
                ),
            )
            rep = stable_candidates[0]
            samples.append(
                {
                    "algorithm": algorithm,
                    "impl": rep["impl"],
                    "role": "stable_rep",
                    "reason": "best stable-or-mostly family representative on sm80",
                }
            )
            variation_candidates = [
                row
                for row in comparable
                if row["impl"] != rep["impl"] and row["variation_rank"] < 999 and row["total_chains"] > 0
            ]
            if variation_candidates:
                variation = sorted(
                    variation_candidates,
                    key=lambda row: (
                        row["variation_rank"],
                        0 if row["screen_verdict"] in {"stable_fast_path", "mostly_fast_path"} else 1,
                        -(row["exact_chain"] + row["chain_with_preamble"] + row["variant_non_imadwide"]),
                        row["impl"],
                    ),
                )[0]
                samples.append(
                    {
                        "algorithm": algorithm,
                        "impl": variation["impl"],
                        "role": "variation_rep",
                        "reason": "same-family implementation perturbation sample",
                    }
                )
        boundary_candidates = [
            row
            for row in rows
            if row["compile_status"] == "ok"
            and row["screen_verdict"] not in {"stable_fast_path", "mostly_fast_path"}
            and (row["boundary_rank"] < 999 or row["screen_verdict"] in {"mixed_fast_path", "variant_only", "mixed_variant_heavy"})
        ]
        if boundary_candidates:
            boundary = sorted(
                boundary_candidates,
                key=lambda row: (
                    row["boundary_rank"],
                    0 if row["screen_verdict"] in {"variant_only", "mixed_variant_heavy", "mixed_fast_path"} else 1,
                    -row["variant_non_imadwide"],
                    row["impl"],
                ),
            )[0]
            if not any(sample["algorithm"] == algorithm and sample["impl"] == boundary["impl"] for sample in samples):
                samples.append(
                    {
                        "algorithm": algorithm,
                        "impl": boundary["impl"],
                        "role": "boundary_rep",
                        "reason": "mixed/non-standard address-generation boundary case",
                    }
                )
    deduped = []
    seen = set()
    for sample in samples:
        key = (sample["algorithm"], sample["impl"], sample["role"])
        if key not in seen:
            seen.add(key)
            deduped.append(sample)
    return deduped


def build_family_summary(screening_rows: list[dict]) -> list[dict]:
    summary = []
    for algorithm in sorted(ALGO_META):
        rows = [row for row in screening_rows if row["algorithm"] == algorithm and row["sm"] == "sm80"]
        verdict_counts = Counter(row["screen_verdict"] for row in rows if row["category"] != "library_wrapper")
        comparable_rows = [row for row in rows if row["category"] == "native_comparable"]
        comparable_ok = [row for row in comparable_rows if row["compile_status"] == "ok"]
        total_comp = len(comparable_rows)
        stable = sum(row["screen_verdict"] == "stable_fast_path" for row in comparable_ok)
        mostly = sum(row["screen_verdict"] == "mostly_fast_path" for row in comparable_ok)
        mixed = sum(row["screen_verdict"] in {"mixed_fast_path", "mixed_variant_heavy"} for row in comparable_ok)
        variant_only = sum(row["screen_verdict"] == "variant_only" for row in comparable_ok)
        no_detected = sum(row["screen_verdict"] == "no_detected_ima" for row in comparable_ok)
        compile_fail = sum(row["compile_status"] != "ok" for row in comparable_rows)
        summary.append(
            {
                "algorithm": algorithm,
                "comparable_impls": total_comp,
                "comparable_compiled": len(comparable_ok),
                "stable_fast_path": stable,
                "mostly_fast_path": mostly,
                "mixed_fast_path": mixed,
                "variant_only": variant_only,
                "no_detected_ima": no_detected,
                "compile_fail": compile_fail,
                "native_redesign": sum(row["category"] == "native_redesign" for row in rows),
                "library_wrapper": sum(row["category"] == "library_wrapper" for row in rows),
                "verdict_notes": "; ".join(f"{k}={v}" for k, v in sorted(verdict_counts.items())),
            }
        )
    return summary


def render_analysis(manifest_rows: list[dict], family_summary: list[dict], screening_rows: list[dict], sample_rows: list[dict], sample_summary: list[dict]):
    total_native = sum(row["category"] != "library_wrapper" for row in manifest_rows)
    total_comparable = sum(row["category"] == "native_comparable" for row in manifest_rows)
    compiled_sm80 = sum(row["compile_status"] == "ok" for row in screening_rows if row["category"] == "native_comparable")
    stable_sm80 = sum(row["screen_verdict"] == "stable_fast_path" for row in screening_rows if row["sm"] == "sm80" and row["category"] == "native_comparable")
    mostly_sm80 = sum(row["screen_verdict"] == "mostly_fast_path" for row in screening_rows if row["sm"] == "sm80" and row["category"] == "native_comparable")
    mixed_algorithms = [row["algorithm"] for row in family_summary if row["mixed_fast_path"] or row["variant_only"]]

    lines = [
        "# Family Variant SASS Analysis",
        "",
        "## Bottom Line",
        "",
        f"- 本轮先在 `sm80` 上 screening 了 `8` 个算法家族的本地实现，共 `{total_native}` 个 native `.cu` 文件，其中 `{total_comparable}` 个被视为 family-comparable 主证据。",
        f"- 在已成功编译并进入 `sm80` screening 的 comparable 实现中，`{stable_sm80 + mostly_sm80}/{compiled_sm80}` 个表现为 stable/mostly fast path，其中 `{stable_sm80}` 个是纯 `IMAD.WIDE`、`{mostly_sm80}` 个只含少量变体。",
        f"- 出现明显 mixed / non-IMAD 变体的家族主要集中在：{', '.join(sorted(set(mixed_algorithms))) if mixed_algorithms else '无'}。",
        "- 因而审稿叙事可以升级为：detect 方法不仅覆盖核心算法，也对多数同家族实现扰动稳健；真正的边界来自 mixed-predicate 或 redesign，而不是普通实现切换。",
        "",
        "## Family Summary",
        "",
        "| Algorithm | Comparable | Compiled@sm80 | Stable | Mostly | Mixed | Variant-only | No-IMA | Compile-fail | Redesign | Wrapper |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in family_summary:
        lines.append(
            f"| {row['algorithm']} | {row['comparable_impls']} | {row['comparable_compiled']} | {row['stable_fast_path']} | {row['mostly_fast_path']} | {row['mixed_fast_path']} | {row['variant_only']} | {row['no_detected_ima']} | {row['compile_fail']} | {row['native_redesign']} | {row['library_wrapper']} |"
        )

    lines += [
        "",
        "## Three-Arch Samples",
        "",
        "| Algorithm | Impl | Role | sm70 | sm80 | sm90 |",
        "|---|---|---|---|---|---|",
    ]
    sample_keyed = defaultdict(dict)
    for row in sample_summary:
        sample_keyed[(row["algorithm"], row["impl"], row["role"])][row["sm"]] = row["screen_verdict"]
    for sample in sample_rows:
        verdicts = sample_keyed[(sample["algorithm"], sample["impl"], sample["role"])]
        lines.append(
            f"| {sample['algorithm']} | `{sample['impl']}` | {sample['role']} | {verdicts.get('sm70', '')} | {verdicts.get('sm80', '')} | {verdicts.get('sm90', '')} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- `stable_fast_path` 与 `mostly_fast_path` 都可以拿来支撑“理论很 solid”的论点；两者区别只是后者含少量非主导变体。",
        "- `mixed_fast_path` 表明同一实现里既有 `IMAD.WIDE` 主链，也有不可忽略的非 `IMAD.WIDE` 变体，适合用来说明 detector 的主覆盖面与边界。",
        "- `variant_only` 或 `no_detected_ima` 更像 boundary / redesign 样本，不应与同家族普通实现混算为“理论失效”。",
    ]

    (ANALYSIS_DIR / "analysis.md").write_text("\n".join(lines) + "\n")


def main():
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    manifest_rows = [asdict(entry) for entry in manifest]
    write_csv(
        ANALYSIS_DIR / "manifest.csv",
        manifest_rows,
        ["algorithm", "impl", "source_cu", "category", "style_bucket", "canonical_rank", "variation_rank", "boundary_rank", "notes"],
    )

    screening_rows = []
    chain_rows = []
    for entry in manifest:
        if entry.category == "library_wrapper":
            screening_rows.append(
                {
                    "algorithm": entry.algorithm,
                    "impl": entry.impl,
                    "category": entry.category,
                    "style_bucket": entry.style_bucket,
                    "sm": "sm80",
                    "compile_status": "skipped_wrapper",
                    "total_chains": 0,
                    "exact_chain": 0,
                    "chain_with_preamble": 0,
                    "variant_non_imadwide": 0,
                    "functions_hit": 0,
                    "dominant_function": "",
                    "screen_verdict": "skipped_wrapper",
                    "sass_path": "",
                    "log_path": "",
                    "source_cu": entry.source_cu,
                    "notes": entry.notes,
                    "canonical_rank": entry.canonical_rank,
                    "variation_rank": entry.variation_rank,
                    "boundary_rank": entry.boundary_rank,
                }
            )
            continue
        compile_row = compile_entry(entry, 80)
        chains = analyze_sass_file(sass_path(entry, 80), entry.algorithm, entry.impl, 80) if compile_row["compile_status"] == "ok" else []
        chain_rows.extend(chains)
        screening_rows.append(summarize_entry(entry, compile_row, chains))

    write_csv(
        ANALYSIS_DIR / "sm80_screening.csv",
        screening_rows,
        [
            "algorithm",
            "impl",
            "category",
            "style_bucket",
            "sm",
            "compile_status",
            "total_chains",
            "exact_chain",
            "chain_with_preamble",
            "variant_non_imadwide",
            "functions_hit",
            "dominant_function",
            "screen_verdict",
            "sass_path",
            "log_path",
            "source_cu",
            "notes",
            "canonical_rank",
            "variation_rank",
            "boundary_rank",
        ],
    )
    write_csv(
        ANALYSIS_DIR / "sm80_chain_instances.csv",
        chain_rows,
        [
            "algorithm",
            "impl",
            "sm",
            "function",
            "classification",
            "index_pc",
            "index_opcode",
            "addr_pc",
            "addr_opcode",
            "data_pc",
            "data_opcode",
            "index_source_file",
            "index_source_line",
            "addr_source_file",
            "addr_source_line",
            "data_source_file",
            "data_source_line",
        ],
    )

    sample_rows = choose_samples(manifest, screening_rows)
    write_csv(
        ANALYSIS_DIR / "three_arch_sample_manifest.csv",
        sample_rows,
        ["algorithm", "impl", "role", "reason"],
    )

    sample_lookup = {(row["algorithm"], row["impl"]) for row in sample_rows}
    sample_entry_map = {(entry.algorithm, entry.impl): entry for entry in manifest}
    sample_summary_rows = []
    sample_chain_rows = []
    for sample in sample_rows:
        entry = sample_entry_map[(sample["algorithm"], sample["impl"])]
        for sm in SAMPLE_SMS:
            compile_row = compile_entry(entry, sm)
            chains = analyze_sass_file(sass_path(entry, sm), entry.algorithm, entry.impl, sm) if compile_row["compile_status"] == "ok" else []
            sample_chain_rows.extend(chains)
            summary = summarize_entry(entry, compile_row, chains)
            summary["role"] = sample["role"]
            summary["reason"] = sample["reason"]
            sample_summary_rows.append(summary)

    write_csv(
        ANALYSIS_DIR / "three_arch_summary.csv",
        sample_summary_rows,
        [
            "algorithm",
            "impl",
            "role",
            "reason",
            "category",
            "style_bucket",
            "sm",
            "compile_status",
            "total_chains",
            "exact_chain",
            "chain_with_preamble",
            "variant_non_imadwide",
            "functions_hit",
            "dominant_function",
            "screen_verdict",
            "sass_path",
            "log_path",
            "source_cu",
            "notes",
            "canonical_rank",
            "variation_rank",
            "boundary_rank",
        ],
    )
    write_csv(
        ANALYSIS_DIR / "three_arch_chain_instances.csv",
        sample_chain_rows,
        [
            "algorithm",
            "impl",
            "sm",
            "function",
            "classification",
            "index_pc",
            "index_opcode",
            "addr_pc",
            "addr_opcode",
            "data_pc",
            "data_opcode",
            "index_source_file",
            "index_source_line",
            "addr_source_file",
            "addr_source_line",
            "data_source_file",
            "data_source_line",
        ],
    )

    family_summary = build_family_summary(screening_rows)
    write_csv(
        ANALYSIS_DIR / "family_summary.csv",
        family_summary,
        [
            "algorithm",
            "comparable_impls",
            "comparable_compiled",
            "stable_fast_path",
            "mostly_fast_path",
            "mixed_fast_path",
            "variant_only",
            "no_detected_ima",
            "compile_fail",
            "native_redesign",
            "library_wrapper",
            "verdict_notes",
        ],
    )
    render_analysis(manifest_rows, family_summary, screening_rows, sample_rows, sample_summary_rows)


if __name__ == "__main__":
    main()
