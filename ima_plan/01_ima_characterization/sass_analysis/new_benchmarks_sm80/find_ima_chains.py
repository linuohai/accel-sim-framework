#!/usr/bin/env python3
"""
Scan SM80 SASS files for IMA chains: LDG → IMAD.WIDE → LDG
Checks register dependency: LDG_idx writes Rd, IMAD.WIDE reads Rd and writes Re, LDG_data reads Re.
"""
import re, sys, os, glob

SASS_DIR = os.path.dirname(os.path.abspath(__file__))

# Parse a SASS instruction line
# Example: /*0080*/  LDG.E.SYS R5, [R2.64] ;
INST_RE = re.compile(
    r'/\*([0-9a-f]+)\*/\s+'   # offset
    r'(@!?P\d\s+)?'            # optional predicate
    r'(\S+)'                    # opcode (e.g. LDG.E, IMAD.WIDE)
    r'\s+(.*?)\s*;'             # operands
)
REG_RE = re.compile(r'R(\d+)')

def parse_sass(filepath):
    """Parse SASS file into list of (offset, func_name, opcode, dst_regs, src_regs, raw_line)."""
    instructions = []
    current_func = "(unknown)"
    with open(filepath) as f:
        for line in f:
            line = line.rstrip()
            # Track function names
            if line.startswith('.text.'):
                current_func = line.strip().rstrip(':')
                continue
            m = INST_RE.search(line)
            if not m:
                continue
            offset = m.group(1)
            opcode = m.group(3)
            operands = m.group(4)

            # Parse destination and source registers
            parts = operands.split(',')
            dst_regs = set()
            src_regs = set()

            if parts:
                # First operand is usually destination for most instructions
                dst_part = parts[0].strip()
                # For LDG, dst is the first operand before comma
                # For IMAD.WIDE, dst is the first operand
                for rm in REG_RE.finditer(dst_part):
                    r = int(rm.group(1))
                    dst_regs.add(r)
                    # IMAD.WIDE writes a 64-bit result (Rd, Rd+1)
                    if 'IMAD.WIDE' in opcode:
                        dst_regs.add(r + 1)
                    # LDG.64 writes 2 regs
                    if 'LDG' in opcode and '.64' in opcode:
                        dst_regs.add(r + 1)

                # Rest are sources
                for sp in parts[1:]:
                    # For LDG, the address part [R2.64] contains source regs
                    # For IMAD.WIDE, operands after first are sources
                    for rm in REG_RE.finditer(sp):
                        src_regs.add(int(rm.group(1)))

                # For LDG, also parse address regs from brackets in dst_part if it has [...]
                # Actually LDG format: LDG.E R5, [R2.64] — R5 is dst, R2 is src (address)
                # Let me re-parse: everything in [...] is address (source)
                bracket_match = re.search(r'\[(.+?)\]', operands)
                if bracket_match and 'LDG' in opcode:
                    addr_part = bracket_match.group(1)
                    for rm in REG_RE.finditer(addr_part):
                        src_regs.add(int(rm.group(1)))
                    # Remove address regs from dst
                    # dst is only the first operand before the comma
                    dst_regs = set()
                    dst_first = parts[0].strip()
                    for rm in REG_RE.finditer(dst_first):
                        r = int(rm.group(1))
                        dst_regs.add(r)
                        if '.64' in opcode:
                            dst_regs.add(r + 1)

                # For IMAD.WIDE: IMAD.WIDE R4, R7.reuse, R9, c[0x0][0x168]
                # dst=R4,R5, src=R7,R9,constant
                if 'IMAD.WIDE' in opcode:
                    src_regs = set()
                    for sp in parts[1:]:
                        for rm in REG_RE.finditer(sp):
                            src_regs.add(int(rm.group(1)))

            instructions.append((offset, current_func, opcode, dst_regs, src_regs, line))
    return instructions


def find_ima_chains(instructions):
    """Find LDG → IMAD.WIDE → LDG chains with register dependency."""
    chains = []

    for i, (off_imad, func_imad, op_imad, dst_imad, src_imad, line_imad) in enumerate(instructions):
        if 'IMAD.WIDE' not in op_imad:
            continue

        # Look backward for LDG_idx: a LDG whose dst overlaps IMAD.WIDE src
        ldg_idx = None
        for j in range(i - 1, max(i - 30, -1), -1):
            off_j, func_j, op_j, dst_j, src_j, line_j = instructions[j]
            if func_j != func_imad:
                break
            if 'LDG' in op_j and dst_j & src_imad:
                ldg_idx = (j, off_j, func_j, op_j, dst_j, src_j, line_j)
                break

        if not ldg_idx:
            continue

        # Look forward for LDG_data: a LDG whose src overlaps IMAD.WIDE dst
        ldg_data = None
        for k in range(i + 1, min(i + 30, len(instructions))):
            off_k, func_k, op_k, dst_k, src_k, line_k = instructions[k]
            if func_k != func_imad:
                break
            if 'LDG' in op_k and src_k & dst_imad:
                ldg_data = (k, off_k, func_k, op_k, dst_k, src_k, line_k)
                break

        if not ldg_data:
            continue

        chains.append({
            'func': func_imad,
            'ldg_idx': ldg_idx[6].strip(),
            'imad_wide': line_imad.strip(),
            'ldg_data': ldg_data[6].strip(),
            'ldg_idx_dst': ldg_idx[4],
            'imad_src': src_imad,
            'imad_dst': dst_imad,
            'ldg_data_src': ldg_data[5],
        })

    return chains


def main():
    sass_files = sorted(glob.glob(os.path.join(SASS_DIR, '*.sm80.sass')))
    if not sass_files:
        print("No .sm80.sass files found!")
        return

    total_chains = 0
    results = {}

    for filepath in sass_files:
        name = os.path.basename(filepath).replace('.sm80.sass', '')
        instructions = parse_sass(filepath)
        chains = find_ima_chains(instructions)
        results[name] = chains
        total_chains += len(chains)

    # Print summary
    print("=" * 80)
    print(f"IMA Chain Analysis (LDG → IMAD.WIDE → LDG)")
    print(f"Total files: {len(sass_files)}, Total chains found: {total_chains}")
    print("=" * 80)

    for name in sorted(results.keys()):
        chains = results[name]
        # Deduplicate by function
        funcs_with_chains = set(c['func'] for c in chains)
        print(f"\n{'─' * 70}")
        print(f"  {name}: {len(chains)} chains in {len(funcs_with_chains)} functions")
        print(f"{'─' * 70}")

        if not chains:
            print("  (no IMA chains found)")
            continue

        # Group by function
        by_func = {}
        for c in chains:
            by_func.setdefault(c['func'], []).append(c)

        for func, fchains in sorted(by_func.items()):
            # Shorten function name
            short_func = func.split('.')[-1] if '.' in func else func
            if len(short_func) > 60:
                short_func = short_func[:57] + '...'
            print(f"\n  Function: {short_func}")
            for idx, c in enumerate(fchains[:5]):  # Show max 5 per function
                print(f"    Chain {idx+1}:")
                print(f"      LDG_idx:   {c['ldg_idx']}")
                print(f"      IMAD.WIDE: {c['imad_wide']}")
                print(f"      LDG_data:  {c['ldg_data']}")
            if len(fchains) > 5:
                print(f"    ... and {len(fchains) - 5} more chains")

    # Final verdict table
    print(f"\n{'=' * 80}")
    print("SUMMARY: IMA Chain Verdict")
    print(f"{'=' * 80}")
    print(f"{'Benchmark':<22} {'Chains':>7} {'Functions':>10} {'Verdict':<20}")
    print(f"{'─' * 60}")
    for name in sorted(results.keys()):
        chains = results[name]
        funcs = len(set(c['func'] for c in chains))
        if len(chains) == 0:
            verdict = "❌ No IMA chain"
        elif len(chains) < 3:
            verdict = "⚠️  Few chains"
        else:
            verdict = "✅ IMA chains found"
        print(f"{name:<22} {len(chains):>7} {funcs:>10} {verdict}")


if __name__ == '__main__':
    main()
