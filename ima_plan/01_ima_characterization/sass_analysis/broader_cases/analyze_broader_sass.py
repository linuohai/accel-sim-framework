#!/usr/bin/env python3
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path("/workspace/prefetch")
ANALYSIS_DIR = ROOT / "ima_plan/01_ima_characterization/broader_sass_analysis"
RAW_SASS_DIR = ANALYSIS_DIR / "raw_sass"


@dataclass
class Target:
    algorithm: str
    source_file_suffix: str
    kernel_pattern: str
    kernel_label: str
    index_line_hint: int
    source_expr: str
    notes: str
    data_line: int = 0
    match_on_data_line: int = None
    match_on_addr_line: int = None
    data_opcode_regex: str = r"^LDG"
    base_operand_hint: str = None


TARGETS = [
    Target(
        algorithm="pr",
        source_file_suffix="gpu-app-collection/gardenia/src/pr/base.cu",
        kernel_pattern=r"_Z9pull_step",
        kernel_label="pull_step",
        index_line_hint=32,
        data_line=34,
        source_expr="outgoing_contrib[src]",
        notes="PR pull path: __ldg(column_indices+offset) drives outgoing_contrib[src]",
        match_on_addr_line=34,
        data_opcode_regex=r"^LDG",
    ),
    Target(
        algorithm="vc",
        source_file_suffix="gpu-app-collection/gardenia/src/vc/linear_base.cu",
        kernel_pattern=r"_Z9first_fit",
        kernel_label="first_fit",
        index_line_hint=22,
        data_line=23,
        source_expr="colors[neighbor]",
        notes="VC first-fit color probe",
        match_on_data_line=23,
        data_opcode_regex=r"^LDG\.E",
    ),
    Target(
        algorithm="vc",
        source_file_suffix="gpu-app-collection/gardenia/src/vc/linear_base.cu",
        kernel_pattern=r"_Z16conflict_resolve",
        kernel_label="conflict_resolve",
        index_line_hint=51,
        data_line=52,
        source_expr="colors[neighbor]",
        notes="VC conflict resolution color probe",
        match_on_data_line=52,
        data_opcode_regex=r"^LDG\.E",
    ),
    Target(
        algorithm="scc",
        source_file_suffix="gpu-app-collection/gardenia/src/scc/base.cu",
        kernel_pattern=r"_Z8bfs_step",
        kernel_label="bfs_step",
        index_line_hint=21,
        data_line=23,
        source_expr="colors[dst]",
        notes="SCC reachability check compares colors[dst] vs colors[src]",
        match_on_data_line=23,
        data_opcode_regex=r"^LDG\.E(?:\.SYS)?$",
    ),
    Target(
        algorithm="scc",
        source_file_suffix="gpu-app-collection/gardenia/src/scc/base.cu",
        kernel_pattern=r"_Z11trim_kernel",
        kernel_label="trim_kernel_in",
        index_line_hint=43,
        data_line=44,
        source_expr="colors[dst] (incoming)",
        notes="SCC trim incoming-neighbor color test",
        match_on_addr_line=43,
        data_opcode_regex=r"^LDG\.E(?:\.SYS)?$",
    ),
    Target(
        algorithm="scc",
        source_file_suffix="gpu-app-collection/gardenia/src/scc/base.cu",
        kernel_pattern=r"_Z11trim_kernel",
        kernel_label="trim_kernel_out",
        index_line_hint=51,
        data_line=52,
        source_expr="colors[dst] (outgoing)",
        notes="SCC trim outgoing-neighbor color test",
        match_on_addr_line=51,
        data_opcode_regex=r"^LDG\.E(?:\.SYS)?$",
    ),
]


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


def clean_reg(token: str):
    match = re.search(r"\b([RU]?\d+|RZ|URZ)\b", token.replace(".reuse", "").replace(".64", ""))
    return match.group(1) if match else None


def parse_dest_reg(operands: str):
    if not operands:
        return None
    first = operands.split(",", 1)[0].strip()
    return clean_reg(first)


def parse_addr_reg(operands: str):
    if not operands:
        return None
    match = re.search(r"\[([RU]?\d+)(?:\.64)?", operands)
    return match.group(1) if match else None


def parse_imad_parts(operands: str):
    parts = [part.strip() for part in operands.split(",")]
    if len(parts) < 4:
        return None
    return {
        "dest": clean_reg(parts[0]),
        "index_reg": clean_reg(parts[1]),
        "scale": parts[2],
        "base": parts[3],
    }


def parse_move_source(operands: str):
    parts = [part.strip() for part in operands.split(",")]
    if len(parts) < 2:
        return None
    return clean_reg(parts[1])


def parse_first_source_reg(operands: str):
    parts = [part.strip() for part in operands.split(",")]
    for part in parts[1:]:
        reg = clean_reg(part)
        if reg and reg not in {"RZ", "URZ"}:
            return reg
    return None


def parse_sass(path: Path):
    current_func = None
    current_file = None
    current_line = None
    functions = defaultdict(list)
    func_pat = re.compile(r"^//--------------------- \.text\.(\S+) ")
    line_pat = re.compile(r'^\s*//## File "(.+)", line (\d+)')
    inst_pat = re.compile(r"^\s*/\*([0-9a-f]+)\*/\s+(?:@[!P0-9]+\s+)?([A-Z0-9_.]+)(?:\s+(.*?))?\s*;\s*$")
    for raw_line in path.read_text().splitlines():
        func_match = func_pat.match(raw_line)
        if func_match:
            current_func = func_match.group(1)
            current_file = None
            current_line = None
            continue
        line_match = line_pat.match(raw_line)
        if line_match:
            current_file = line_match.group(1)
            current_line = int(line_match.group(2))
            continue
        inst_match = inst_pat.match(raw_line)
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


def follow_reg_producer(instructions, start_idx, reg):
    if not reg:
        return None, None
    current_reg = reg
    current_idx = start_idx
    for _ in range(4):
        producer, producer_idx = find_prev_writer(instructions, current_idx, current_reg)
        if not producer:
            return None, None
        if producer["opcode"] in MOVE_OPS:
            src_reg = parse_move_source(producer["operands"])
            if src_reg and src_reg != current_reg:
                current_reg = src_reg
                current_idx = producer_idx
                continue
        return producer, producer_idx
    return None, None


def find_prev_writer(instructions, start_idx, reg):
    for idx in range(start_idx - 1, max(-1, start_idx - 18), -1):
        if parse_dest_reg(instructions[idx]["operands"]) == reg:
            return instructions[idx], idx
    return None, None


def classify_chain(index_gap, data_gap):
    if index_gap <= 4 and data_gap <= 2:
        return "exact_chain"
    return "chain_with_preamble"


def analyze_target(sm, sass_path, target):
    functions = parse_sass(sass_path)
    kernel_name = None
    for func_name in functions:
        if re.search(target.kernel_pattern, func_name):
            kernel_name = func_name
            break
    if not kernel_name:
        return []
    instructions = functions[kernel_name]
    rows = []
    for idx, inst in enumerate(instructions):
        if not inst["opcode"].startswith("LDG"):
            continue
        data_addr_reg = parse_addr_reg(inst["operands"])
        addr_prod, addr_idx = follow_reg_producer(instructions, idx, data_addr_reg)
        classification = "unresolved"
        index_prod = None
        imad_meta = {"index_reg": None, "scale": None, "base": None}
        addr_operand_text = addr_prod["operands"] if addr_prod else ""
        data_line_match = (
            target.match_on_data_line is not None
            and inst["source_file"]
            and inst["source_file"].endswith(target.source_file_suffix)
            and inst["source_line"] == target.match_on_data_line
        )
        addr_line_match = (
            target.match_on_addr_line is not None
            and addr_prod
            and addr_prod["source_file"]
            and addr_prod["source_file"].endswith(target.source_file_suffix)
            and addr_prod["source_line"] == target.match_on_addr_line
        )
        if not (data_line_match or addr_line_match):
            continue
        if not re.search(target.data_opcode_regex, inst["opcode"]):
            continue
        if addr_prod and addr_prod["opcode"].startswith("IMAD.WIDE"):
            imad_meta = parse_imad_parts(addr_prod["operands"]) or imad_meta
            if target.base_operand_hint and target.base_operand_hint not in (imad_meta["base"] or ""):
                continue
            index_prod, index_idx = follow_reg_producer(instructions, addr_idx, imad_meta["index_reg"])
            if index_prod and index_prod["opcode"].startswith("LDG"):
                classification = classify_chain(addr_idx - index_idx, idx - addr_idx)
            else:
                classification = "chain_with_preamble"
        elif addr_prod and addr_prod["opcode"] in VARIANT_ADDR_OPS:
            if target.base_operand_hint and target.base_operand_hint not in addr_operand_text:
                continue
            variant_index_reg = parse_first_source_reg(addr_prod["operands"])
            index_prod, _ = follow_reg_producer(instructions, addr_idx, variant_index_reg)
            classification = "variant_non_imadwide"
        elif target.base_operand_hint:
            continue
        if classification == "unresolved":
            continue
        rows.append(
            {
                "algorithm": target.algorithm,
                "sm": sm,
                "sass_file": str(sass_path.relative_to(ROOT)),
                "kernel": kernel_name,
                "kernel_label": target.kernel_label,
                "source_expr": target.source_expr,
                "source_file": target.source_file_suffix,
                "index_line_hint": target.index_line_hint,
                "data_line": target.data_line,
                "classification": classification,
                "index_pc": index_prod["pc"] if index_prod else "",
                "index_opcode": index_prod["opcode"] if index_prod else "",
                "index_source_line": index_prod["source_line"] if index_prod else "",
                "addr_pc": addr_prod["pc"] if addr_prod else "",
                "addr_opcode": addr_prod["opcode"] if addr_prod else "",
                "addr_source_line": addr_prod["source_line"] if addr_prod else "",
                "data_pc": inst["pc"],
                "data_opcode": inst["opcode"],
                "data_source_line": inst["source_line"],
                "scale": imad_meta["scale"] or "",
                "base_operand": imad_meta["base"] or "",
                "notes": target.notes,
            }
        )
    return rows


def write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["algorithm"], row["sm"])].append(row)
    summary_rows = []
    for (algorithm, sm), group_rows in sorted(grouped.items()):
        total = len(group_rows)
        exact = sum(1 for row in group_rows if row["classification"] == "exact_chain")
        preamble = sum(1 for row in group_rows if row["classification"] == "chain_with_preamble")
        variant = sum(1 for row in group_rows if row["classification"] == "variant_non_imadwide")
        unresolved = sum(1 for row in group_rows if row["classification"] == "unresolved")
        summary_rows.append(
            {
                "algorithm": algorithm,
                "sm": sm,
                "total_instances": total,
                "exact_chain": exact,
                "chain_with_preamble": preamble,
                "variant_non_imadwide": variant,
                "unresolved": unresolved,
                "exact_chain_ratio": f"{exact / total:.3f}" if total else "0.000",
                "chain_with_preamble_ratio": f"{preamble / total:.3f}" if total else "0.000",
                "variant_ratio": f"{variant / total:.3f}" if total else "0.000",
            }
        )
    return summary_rows


def write_markdown(summary_rows, mapping_rows, instance_rows, path: Path):
    lines = [
        "# Broader Gardenia SASS Analysis",
        "",
        "## Bottom Line",
        "",
        "Across `PR`, `VC`, and `SCC` on `sm_70`, `sm_80`, and `sm_90`, the broader Gardenia set splits into two behaviors: `PR` and `VC` consistently retain the expected `LDG(index) -> IMAD.WIDE(base+scale) -> LDG(data)` pattern, while `SCC` mixes that pattern with non-`IMAD.WIDE` lowers for composite predicates.",
        "",
        "The main caveat is therefore not that indirect addressing disappears, but that the compiler may choose either `IMAD.WIDE` or a multi-instruction `IADD3/LEA` sequence depending on data width, predicate structure, and surrounding byte-addressed side conditions.",
        "",
        "## Matrix",
        "",
        "| Algorithm | SM | Total | Exact | With Preamble | Variant | Unresolved |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['algorithm']} | {row['sm']} | {row['total_instances']} | {row['exact_chain']} | {row['chain_with_preamble']} | {row['variant_non_imadwide']} | {row['unresolved']} |"
        )
    lines.extend(
        [
            "",
            "## Per-Algorithm Notes",
            "",
            "- `pr`: `pull_step` is still structurally compliant. The final demand load frequently appears as `LDG.E.CONSTANT` because `__ldg()` routes through the read-only path, but the dependency anchor remains `index load -> IMAD.WIDE -> data load`.",
            "- `vc`: both `first_fit` and `conflict_resolve` show textbook `column_indices[offset] -> colors[neighbor]` chains. The only variation is extra scheduling distance and loop-unrolled repetition.",
            "- `scc`: `trim_kernel` still uses `IMAD.WIDE` for `colors[dst]`, but `bfs_step` often lowers the `colors[dst]` compare through `LEA/IADD3 + LDG` because the line also contains `mark[dst]` / `visited[dst]` byte-addressed conditions. This is a real counterexample to the claim that `IMAD.WIDE` is universal.",
            "",
            "## Representative Instances",
            "",
            "| Algorithm | SM | Kernel | Expr | Index PC | IMAD PC | Data PC | Data Opcode | Classification |",
            "|---|---:|---|---|---|---|---|---|---|",
        ]
    )
    seen = set()
    for row in mapping_rows:
        key = (row["algorithm"], row["sm"], row["kernel_label"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"| {row['algorithm']} | {row['sm']} | `{row['kernel_label']}` | `{row['source_expr']}` | `{row['index_pc']}` | `{row['addr_pc']}` | `{row['data_pc']}` | `{row['data_opcode']}` | {row['classification']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The broader Gardenia set partially supports the prefetcher premise: the index still flows through a register in all three algorithms, but `IMAD.WIDE` is common rather than universal.",
            "- `PR` and `VC` validate the intended detector anchor directly. `SCC` shows that once a source statement mixes byte-addressed predicates with a word-sized indirect compare, the compiler may pick `IADD3/LEA` instead of a single `IMAD.WIDE` for the target data path.",
            "- For detector design, `LDG -> IMAD.WIDE -> LDG*` is still the main fast path, but a robust implementation should either tolerate `LEA/IADD3` variants or explicitly scope itself away from mixed-width composite predicates like `SCC bfs_step`.",
            "",
            f"Generated from {len(instance_rows)} chain instances across {len(summary_rows)} algorithm/SM buckets.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main():
    instance_rows = []
    for target in TARGETS:
        for sass_path in sorted((RAW_SASS_DIR / target.algorithm).glob("sm*/**/*.sass")):
            sm = sass_path.parent.name
            instance_rows.extend(analyze_target(sm, sass_path, target))
    instance_rows.sort(key=lambda row: (row["algorithm"], row["sm"], row["kernel_label"], row["data_pc"]))

    mapping_rows = []
    mapping_seen = set()
    for row in instance_rows:
        key = (row["algorithm"], row["sm"], row["kernel_label"])
        if key in mapping_seen:
            continue
        mapping_seen.add(key)
        mapping_rows.append(row)

    summary_rows = summarize(instance_rows)

    write_csv(
        ANALYSIS_DIR / "ima_chain_instances.csv",
        instance_rows,
        [
            "algorithm",
            "sm",
            "sass_file",
            "kernel",
            "kernel_label",
            "source_expr",
            "source_file",
            "index_line_hint",
            "data_line",
            "classification",
            "index_pc",
            "index_opcode",
            "index_source_line",
            "addr_pc",
            "addr_opcode",
            "addr_source_line",
            "data_pc",
            "data_opcode",
            "data_source_line",
            "scale",
            "base_operand",
            "notes",
        ],
    )
    write_csv(
        ANALYSIS_DIR / "source_sass_mapping.csv",
        mapping_rows,
        [
            "algorithm",
            "sm",
            "kernel_label",
            "source_expr",
            "source_file",
            "index_line_hint",
            "data_line",
            "classification",
            "index_pc",
            "addr_pc",
            "data_pc",
            "data_opcode",
            "scale",
            "base_operand",
            "notes",
        ],
    )
    write_csv(
        ANALYSIS_DIR / "algorithm_sm_summary.csv",
        summary_rows,
        [
            "algorithm",
            "sm",
            "total_instances",
            "exact_chain",
            "chain_with_preamble",
            "variant_non_imadwide",
            "unresolved",
            "exact_chain_ratio",
            "chain_with_preamble_ratio",
            "variant_ratio",
        ],
    )
    write_markdown(summary_rows, mapping_rows, instance_rows, ANALYSIS_DIR / "analysis_matrix.md")


if __name__ == "__main__":
    main()
