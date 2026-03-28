#!/usr/bin/env python3
"""Source-agnostic LDG-IMAD.WIDE-LDG chain scanner for pre-compiled CUDA libraries.

Reuses register-tracing utilities from analyze_broader_sass.py.
Scans all functions in a SASS dump, no source-line info needed.

Usage:
    python3 scan_cugraph_sass.py --sass /tmp/cugraph_sass/cubin23_sm80.sass \
        --filter "cugraph|graph_view|edge_partition|transform_reduce" \
        --output cugraph_ima_chains.csv
"""
import argparse
import csv
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Register-tracing utilities (from analyze_broader_sass.py)
# ---------------------------------------------------------------------------

VARIANT_ADDR_OPS = {
    "LEA", "LEA.HI.X", "IADD3", "IADD3.X",
    "IMAD.SHL.U32", "IMAD.IADD", "SHF.L.U64.HI",
}
MOVE_OPS = {"MOV", "MOV32I", "IMAD.MOV.U32", "IMAD.MOV"}


def clean_reg(token: str):
    match = re.search(r"\b([RU]?\d+|RZ|URZ)\b",
                      token.replace(".reuse", "").replace(".64", ""))
    return match.group(1) if match else None


def parse_dest_reg(operands: str):
    if not operands:
        return None
    return clean_reg(operands.split(",", 1)[0].strip())


def parse_addr_reg(operands: str):
    if not operands:
        return None
    match = re.search(r"\[([RU]?\d+)(?:\.64)?", operands)
    return match.group(1) if match else None


def parse_imad_parts(operands: str):
    parts = [p.strip() for p in operands.split(",")]
    if len(parts) < 4:
        return None
    return {
        "dest": clean_reg(parts[0]),
        "index_reg": clean_reg(parts[1]),
        "scale": parts[2],
        "base": parts[3],
    }


def parse_move_source(operands: str):
    parts = [p.strip() for p in operands.split(",")]
    if len(parts) < 2:
        return None
    return clean_reg(parts[1])


def parse_first_source_reg(operands: str):
    parts = [p.strip() for p in operands.split(",")]
    for part in parts[1:]:
        reg = clean_reg(part)
        if reg and reg not in {"RZ", "URZ"}:
            return reg
    return None


def find_prev_writer(instructions, start_idx, reg):
    for idx in range(start_idx - 1, max(-1, start_idx - 18), -1):
        if parse_dest_reg(instructions[idx]["operands"]) == reg:
            return instructions[idx], idx
    return None, None


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


def classify_chain(index_gap, data_gap):
    if index_gap <= 4 and data_gap <= 2:
        return "exact_chain"
    return "chain_with_preamble"


# ---------------------------------------------------------------------------
# SASS parser (adapted for cuobjdump/nvdisasm output without line info)
# ---------------------------------------------------------------------------

def parse_sass(path: Path):
    """Parse SASS text into {func_name: [instruction_dict, ...]}."""
    current_func = None
    functions = defaultdict(list)
    func_pat = re.compile(r"^\.text\.(\S+)")
    inst_pat = re.compile(
        r"^\s*/\*([0-9a-f]+)\*/\s+(?:@[!P0-9]+\s+)?([A-Z0-9_.]+)(?:\s+(.*?))?\s*;\s*$"
    )
    for raw_line in path.read_text().splitlines():
        func_match = func_pat.match(raw_line)
        if func_match:
            current_func = func_match.group(1)
            continue
        inst_match = inst_pat.match(raw_line)
        if inst_match and current_func:
            functions[current_func].append({
                "pc": inst_match.group(1),
                "opcode": inst_match.group(2),
                "operands": (inst_match.group(3) or "").strip(),
            })
    return functions


# ---------------------------------------------------------------------------
# Source-agnostic chain scanner
# ---------------------------------------------------------------------------

SCALE_OPS = {"IMAD.SHL.U32", "SHF.L.U64.HI", "SHF.R.U64", "SHF.R.U32.HI",
             "LEA", "LEA.HI.X"}


def _trace_to_ldg(instructions, start_idx, reg, max_depth=3):
    """Follow register dataflow backward through addr/scale ops to find an LDG.

    Returns (ldg_inst, ldg_idx, path) or (None, None, []).
    path is list of (inst, idx) for intermediate ops.
    """
    path = []
    current_reg = reg
    current_idx = start_idx
    for _ in range(max_depth):
        prod, prod_idx = follow_reg_producer(instructions, current_idx, current_reg)
        if not prod:
            return None, None, []
        if prod["opcode"].startswith("LDG"):
            return prod, prod_idx, path
        if prod["opcode"] in VARIANT_ADDR_OPS | SCALE_OPS | MOVE_OPS:
            path.append((prod, prod_idx))
            # Get the first meaningful source register
            src = parse_first_source_reg(prod["operands"])
            if src and src != current_reg:
                current_reg = src
                current_idx = prod_idx
                continue
        return None, None, []
    return None, None, []


def scan_all_ldg_chains(functions, name_filter=None):
    """Scan every LDG in every function for IMA chains via register dataflow."""
    results = []
    for func_name, instructions in functions.items():
        if name_filter and not name_filter.search(func_name):
            continue
        for idx, inst in enumerate(instructions):
            if not inst["opcode"].startswith("LDG"):
                continue
            addr_reg = parse_addr_reg(inst["operands"])
            addr_prod, addr_idx = follow_reg_producer(instructions, idx, addr_reg)
            if not addr_prod:
                continue

            # Case 1: IMAD.WIDE chain (canonical IMA)
            if addr_prod["opcode"].startswith("IMAD.WIDE"):
                imad_meta = parse_imad_parts(addr_prod["operands"])
                if not imad_meta:
                    continue
                index_prod, index_idx = follow_reg_producer(
                    instructions, addr_idx, imad_meta["index_reg"]
                )
                if index_prod and index_prod["opcode"].startswith("LDG"):
                    classification = classify_chain(
                        addr_idx - index_idx, idx - addr_idx
                    )
                    results.append({
                        "function": func_name[:200],
                        "classification": classification,
                        "data_ldg_pc": inst["pc"],
                        "data_ldg_op": inst["opcode"],
                        "imad_pc": addr_prod["pc"],
                        "imad_op": addr_prod["opcode"],
                        "index_ldg_pc": index_prod["pc"],
                        "index_ldg_op": index_prod["opcode"],
                        "scale": imad_meta.get("scale", ""),
                        "chain_type": "IMAD.WIDE",
                    })

            # Case 2: variant addr ops — trace up to 3 levels back to find LDG
            elif addr_prod["opcode"] in VARIANT_ADDR_OPS | SCALE_OPS:
                # Try all source regs of the addr producer
                parts = [p.strip() for p in addr_prod["operands"].split(",")]
                found = False
                for part in parts[1:]:  # skip dest
                    src_reg = clean_reg(part)
                    if not src_reg or src_reg in {"RZ", "URZ"}:
                        continue
                    ldg, ldg_idx, path = _trace_to_ldg(
                        instructions, addr_idx, src_reg, max_depth=4
                    )
                    if ldg:
                        chain_ops = " → ".join(
                            p[0]["opcode"] for p in path
                        ) if path else ""
                        results.append({
                            "function": func_name[:200],
                            "classification": "variant_multi_step",
                            "data_ldg_pc": inst["pc"],
                            "data_ldg_op": inst["opcode"],
                            "imad_pc": addr_prod["pc"],
                            "imad_op": addr_prod["opcode"],
                            "index_ldg_pc": ldg["pc"],
                            "index_ldg_op": ldg["opcode"],
                            "scale": chain_ops,
                            "chain_type": addr_prod["opcode"],
                        })
                        found = True
                        break
    return results


def demangle(name: str) -> str:
    """Try to demangle a C++ symbol using c++filt."""
    try:
        result = subprocess.run(
            ["c++filt", name], capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() if result.returncode == 0 else name
    except Exception:
        return name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sass", required=True, help="Path to SASS text file")
    parser.add_argument("--filter", default=None,
                        help="Regex to filter function names (applied to mangled name)")
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument("--summary", action="store_true",
                        help="Print summary to stdout")
    args = parser.parse_args()

    sass_path = Path(args.sass)
    name_filter = re.compile(args.filter, re.IGNORECASE) if args.filter else None

    print(f"Parsing SASS from {sass_path} ...", file=sys.stderr)
    functions = parse_sass(sass_path)
    total_funcs = len(functions)
    filtered_funcs = sum(1 for f in functions if not name_filter or name_filter.search(f))
    print(f"  Total functions: {total_funcs}, after filter: {filtered_funcs}", file=sys.stderr)

    print("Scanning for IMA chains ...", file=sys.stderr)
    chains = scan_all_ldg_chains(functions, name_filter)
    print(f"  Found {len(chains)} chains", file=sys.stderr)

    # Write CSV
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "function", "classification", "chain_type", "scale",
            "index_ldg_pc", "index_ldg_op", "imad_pc", "imad_op",
            "data_ldg_pc", "data_ldg_op",
        ]
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chains)
        print(f"  Written to {out_path}", file=sys.stderr)

    # Summary
    if args.summary or not args.output:
        from collections import Counter
        by_class = Counter(c["classification"] for c in chains)
        by_type = Counter(c["chain_type"] for c in chains)
        by_scale = Counter(c["scale"] for c in chains if c["scale"])
        unique_funcs = len(set(c["function"] for c in chains))

        print("\n=== IMA Chain Summary ===")
        print(f"Total functions scanned: {total_funcs}")
        print(f"Functions after filter:  {filtered_funcs}")
        print(f"Functions with chains:   {unique_funcs}")
        print(f"Total IMA chains found:  {len(chains)}")
        print(f"\nBy classification:")
        for cls, cnt in by_class.most_common():
            print(f"  {cls}: {cnt}")
        print(f"\nBy address computation type:")
        for typ, cnt in by_type.most_common():
            print(f"  {typ}: {cnt}")
        if by_scale:
            print(f"\nBy IMAD.WIDE scale factor:")
            for scale, cnt in by_scale.most_common():
                print(f"  {scale}: {cnt}")

        # Show a few representative examples
        if chains:
            print(f"\n=== Representative Examples (first 5) ===")
            for c in chains[:5]:
                short_name = demangle(c["function"][:300])
                if len(short_name) > 120:
                    short_name = short_name[:117] + "..."
                print(f"  [{c['classification']}] {c['chain_type']}"
                      f" scale={c['scale']}")
                print(f"    LDG_idx@{c['index_ldg_pc']} → "
                      f"{c['imad_op']}@{c['imad_pc']} → "
                      f"LDG_data@{c['data_ldg_pc']}")
                print(f"    func: {short_name}")


if __name__ == "__main__":
    main()
