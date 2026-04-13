#!/usr/bin/env python3
"""Extract IMA chains (LDG → IMAD.WIDE → LDG) from SASS assembly files.

Scans SASS files for the pattern:
  1. LDG.E Rdest, [Rbase.64]          (index load)
  2. IMAD.WIDE Rdest2, Rdest, ...     (address computation using loaded value)
  3. LDG.E Rdest3, [Rdest2.64]        (data load using computed address)

Register dataflow is verified: LDG(1).dest → IMAD.WIDE.src, IMAD.WIDE.dest → LDG(2).addr_base.
"""
from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# SASS Parsing
# ---------------------------------------------------------------------------

# Matches: /*0640*/  LDG.E R0, [R16.64] ;
# Or:      /*0660*/  IMAD.WIDE R2, R0, R11, c[0x0][0x178] ;
RE_INSTR = re.compile(
    r"/\*([0-9a-fA-F]{4})\*/\s+"        # PC hex offset
    r"(?:@!?P\d+\s+)?"                   # optional predicate
    r"(\S+)"                              # opcode (e.g. LDG.E, IMAD.WIDE)
    r"\s+(.*?)\s*;"                       # operands
)

# Source line annotation: //## File "...", line NN
RE_SOURCE = re.compile(r'//##\s+File\s+"([^"]+)",\s+line\s+(\d+)')

# Function section start
RE_FUNC_START = re.compile(r"^\.text\.(_Z\S+):")

# Register in operand: R0, R2, R16 etc.
RE_REG = re.compile(r"\bR(\d+)\b")


@dataclass
class SassInstr:
    pc: int              # hex offset within function
    opcode: str
    operands: str
    source_file: str = ""
    source_line: int = 0
    function: str = ""

    @property
    def pc_hex(self) -> str:
        return f"{self.pc:04x}"

    def dest_reg(self) -> Optional[str]:
        """First register in operands (destination for most instructions)."""
        m = RE_REG.search(self.operands)
        return m.group(0) if m else None

    def all_regs(self) -> List[str]:
        return RE_REG.findall(self.operands)


def parse_sass_file(path: Path) -> Dict[str, List[SassInstr]]:
    """Parse SASS file → {function_name: [SassInstr, ...]}."""
    functions: Dict[str, List[SassInstr]] = {}
    current_func = ""
    current_source_file = ""
    current_source_line = 0

    with open(path) as f:
        for line in f:
            line = line.rstrip()

            # Function start
            m = RE_FUNC_START.match(line)
            if m:
                current_func = m.group(1)
                if current_func not in functions:
                    functions[current_func] = []
                continue

            # Source annotation
            m = RE_SOURCE.search(line)
            if m:
                current_source_file = m.group(1)
                current_source_line = int(m.group(2))
                continue

            # Instruction
            m = RE_INSTR.search(line)
            if m and current_func:
                instr = SassInstr(
                    pc=int(m.group(1), 16),
                    opcode=m.group(2),
                    operands=m.group(3),
                    source_file=current_source_file,
                    source_line=current_source_line,
                    function=current_func,
                )
                functions[current_func].append(instr)

    return functions


# ---------------------------------------------------------------------------
# Chain Detection
# ---------------------------------------------------------------------------

@dataclass
class ImaChain:
    function: str
    index_instr: SassInstr
    addr_instr: SassInstr
    data_instr: SassInstr
    scale_operand: str = ""
    base_operand: str = ""


def _reads_reg(instr: SassInstr, reg: str) -> bool:
    """Check if an instruction reads the given register (appears in source operands)."""
    regs = RE_REG.findall(instr.operands)
    if not regs:
        return False
    # First reg is dest, rest are sources. Also check predicate reads.
    sources = {f"R{r}" for r in regs[1:]}
    # For predicated/comparison instructions, ALL regs after dest may be sources
    # For LDG [Rbase.64], the base reg is a source too
    # Conservative: if reg appears anywhere after first position, it's a read
    return reg in sources


def _writes_reg(instr: SassInstr, reg: str) -> bool:
    """Check if an instruction writes to the given register (dest = first reg)."""
    dest = instr.dest_reg()
    return dest == reg


def find_ima_chains(
    instrs: List[SassInstr],
    function: str,
    max_window: int = 30,
) -> List[ImaChain]:
    """Find all LDG → IMAD.WIDE → LDG chains with read-invalidation.

    Rules matching GRASP CD FIFO behavior:
      1. Between index LDG and IMAD.WIDE: idx_dest must NOT be read by any
         non-IMAD.WIDE instruction (read-invalidation — FIFO entry consumed)
      2. Between IMAD.WIDE and data LDG: addr_dest must NOT be written by
         any other instruction (write-invalidation — value corrupted)
    """
    re_addr_base = re.compile(r"\[(R\d+)")
    chains: List[ImaChain] = []
    seen: set = set()

    for i, idx_instr in enumerate(instrs):
        if not idx_instr.opcode.startswith("LDG"):
            continue
        idx_dest = idx_instr.dest_reg()
        if idx_dest is None:
            continue

        for j in range(i + 1, min(i + 1 + max_window, len(instrs))):
            mid_instr = instrs[j]

            # Read-invalidation: if a non-IMAD.WIDE instruction reads idx_dest, stop
            if not mid_instr.opcode.startswith("IMAD.WIDE") and _reads_reg(mid_instr, idx_dest):
                break
            # Also stop if idx_dest is overwritten
            if _writes_reg(mid_instr, idx_dest) and not mid_instr.opcode.startswith("IMAD.WIDE"):
                break

            if not mid_instr.opcode.startswith("IMAD.WIDE"):
                continue

            addr_regs = RE_REG.findall(mid_instr.operands)
            if len(addr_regs) < 2:
                continue
            addr_dest = f"R{addr_regs[0]}"
            addr_sources = {f"R{r}" for r in addr_regs[1:]}
            if idx_dest not in addr_sources:
                # IMAD.WIDE doesn't use idx_dest — check if it writes or reads idx_dest
                if addr_dest == idx_dest or _reads_reg(mid_instr, idx_dest):
                    break
                continue

            parts = [p.strip() for p in mid_instr.operands.split(",")]
            scale_op = parts[2] if len(parts) > 2 else ""
            base_op = parts[3] if len(parts) > 3 else ""

            # Second segment: IMAD.WIDE → data LDG (write-invalidation on addr_dest)
            for k in range(j + 1, min(j + 1 + max_window, len(instrs))):
                data_cand = instrs[k]
                # Write-invalidation: if addr_dest is overwritten, stop
                if _writes_reg(data_cand, addr_dest) and not data_cand.opcode.startswith("LDG"):
                    break

                if not data_cand.opcode.startswith("LDG"):
                    continue
                m = re_addr_base.search(data_cand.operands)
                if m is None:
                    continue
                if m.group(1) != addr_dest:
                    if _writes_reg(data_cand, addr_dest):
                        break
                    continue

                key = (idx_instr.pc, mid_instr.pc, data_cand.pc)
                if key in seen:
                    continue
                seen.add(key)

                chains.append(ImaChain(
                    function=function,
                    index_instr=idx_instr,
                    addr_instr=mid_instr,
                    data_instr=data_cand,
                    scale_operand=scale_op,
                    base_operand=base_op,
                ))

    return chains


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "algorithm", "impl", "sm", "function", "classification",
    "index_pc", "index_opcode", "addr_pc", "addr_opcode",
    "data_pc", "data_opcode",
    "index_source_file", "index_source_line",
    "addr_source_file", "addr_source_line",
    "data_source_file", "data_source_line",
]


def chain_to_csv_row(chain: ImaChain, algorithm: str, impl: str, sm: str) -> dict:
    return {
        "algorithm": algorithm,
        "impl": impl,
        "sm": sm,
        "function": chain.function,
        "classification": "exact_chain",
        "index_pc": chain.index_instr.pc_hex,
        "index_opcode": chain.index_instr.opcode,
        "addr_pc": chain.addr_instr.pc_hex,
        "addr_opcode": chain.addr_instr.opcode,
        "data_pc": chain.data_instr.pc_hex,
        "data_opcode": chain.data_instr.opcode,
        "index_source_file": chain.index_instr.source_file,
        "index_source_line": str(chain.index_instr.source_line),
        "addr_source_file": chain.addr_instr.source_file,
        "addr_source_line": str(chain.addr_instr.source_line),
        "data_source_file": chain.data_instr.source_file,
        "data_source_line": str(chain.data_instr.source_line),
    }


def write_csv(chains: List[dict], output_path: Path):
    with open(output_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(chains)
    print(f"Wrote {len(chains)} chains to {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def infer_algorithm_impl(sass_filename: str) -> Tuple[str, str]:
    """Infer algorithm and impl from filename like 'bfs_linear_base.sm80.sass'."""
    stem = sass_filename.replace(".sass", "")
    parts = stem.split(".")
    sm = parts[1] if len(parts) > 1 else "sm80"
    name = parts[0]  # e.g. "bfs_linear_base"
    # Split: last segment(s) after algorithm name = impl
    # Known algorithms
    for algo in ["bfs", "sssp", "bc", "cc", "spmv", "pr", "vc", "scc", "tc", "sgd", "mst", "symgs"]:
        if name.startswith(algo + "_"):
            impl = name[len(algo) + 1:]
            return algo, impl
        elif name == algo:
            return algo, "base"
    return name, "unknown"


def main():
    p = argparse.ArgumentParser(description="Extract IMA chains from SASS files")
    p.add_argument("sass_files", nargs="+", type=Path,
                    help="SASS file(s) to analyze")
    p.add_argument("--output", "-o", type=Path, default=None,
                    help="Output CSV path (default: stdout summary)")
    p.add_argument("--max-window", type=int, default=30,
                    help="Max instruction window for chain search (default: 30)")
    args = p.parse_args()

    all_rows: List[dict] = []

    for sass_path in args.sass_files:
        if not sass_path.exists():
            print(f"WARNING: {sass_path} not found, skipping")
            continue

        algo, impl = infer_algorithm_impl(sass_path.name)
        sm_match = re.search(r"sm(\d+)", sass_path.name)
        sm = f"sm{sm_match.group(1)}" if sm_match else "sm80"

        print(f"\n=== {sass_path.name} (algo={algo}, impl={impl}, sm={sm}) ===")
        functions = parse_sass_file(sass_path)
        print(f"  Functions: {list(functions.keys())}")

        for func_name, instrs in functions.items():
            chains = find_ima_chains(instrs, func_name, args.max_window)
            print(f"  {func_name}: {len(chains)} chains found")
            for chain in chains:
                all_rows.append(chain_to_csv_row(chain, algo, impl, sm))

    if args.output:
        write_csv(all_rows, args.output)
    else:
        print(f"\nTotal: {len(all_rows)} chains across {len(args.sass_files)} files")
        for row in all_rows:
            print(f"  {row['algorithm']}/{row['function']}: "
                  f"idx=0x{row['index_pc']} → addr=0x{row['addr_pc']} → data=0x{row['data_pc']}")


if __name__ == "__main__":
    main()
