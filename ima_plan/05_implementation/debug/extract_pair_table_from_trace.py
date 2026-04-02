#!/usr/bin/env python3
"""Extract idx_addr -> data_addr mapping table from GPU trace files (.traceg).

Parses .traceg.xz trace files directly (no simulation needed) to build the
full index-to-data address mapping for IMA chains defined in the golden
chain CSV.

Usage:
    python3 extract_pair_table_from_trace.py \
        --trace-dir /path/to/traces/ \
        --chain-csv  ima_plan/.../strict_selected_chain_instances.csv \
        --algorithm bfs --impl linear_base \
        --kernels 2 \
        --output pair_table.csv
"""
from __future__ import annotations

import argparse
import csv
import lzma
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Address decoding helpers
# ---------------------------------------------------------------------------

def _active_lanes(mask_hex: str) -> List[int]:
    """Return sorted list of lane indices (0-31) that are active in *mask_hex*."""
    m = int(mask_hex, 16)
    return [i for i in range(32) if m & (1 << i)]


def decode_addresses(addr_mode: int, tokens: List[str], active: List[int]) -> Dict[int, int]:
    """Decode per-lane addresses from the trace tokens after addr_mode.

    Returns {lane_index: address} for every active lane.
    *tokens* starts right after the addr_mode field and includes the
    trailing ``0`` terminator.

    Address modes:
        0 – list_all : 32 hex addresses, one per lane (always 32 values)
        1 – base_stride : base(hex) stride(int) 0
        2 – base_delta  : base(hex) delta1(int) delta2(int) … 0
    """
    result: Dict[int, int] = {}
    if not tokens or not active:
        return result

    if addr_mode == 0:
        # 32 hex addresses, one per lane (lanes 0-31)
        for lane in active:
            if lane < len(tokens):
                result[lane] = int(tokens[lane], 16)
    elif addr_mode == 1:
        # base stride 0
        base = int(tokens[0], 16)
        stride = int(tokens[1])
        for lane in active:
            result[lane] = base + lane * stride
    elif addr_mode == 2:
        # base delta1 delta2 … 0  (deltas are cumulative, one per active lane)
        base = int(tokens[0], 16)
        # Remaining tokens (before trailing 0) are deltas for active lanes 1..N-1
        # Number of deltas = len(active) - 1, then a trailing 0
        addr = base
        result[active[0]] = addr
        for i, lane in enumerate(active[1:], start=1):
            if i < len(tokens):
                delta = int(tokens[i])
                addr += delta
                result[lane] = addr
    else:
        # Unknown mode – skip
        pass

    return result


# ---------------------------------------------------------------------------
# Instruction parser
# ---------------------------------------------------------------------------

def parse_instruction(line: str):
    """Parse one instruction line.

    Returns (pc_int, mask_hex, opcode, mem_width, addr_mode, addr_tokens)
    or None for non-parseable lines.

    *addr_tokens* is the list of string tokens after addr_mode (addresses +
    trailing 0).  For non-memory instructions addr_mode is -1 and
    addr_tokens is empty.
    """
    parts = line.split()
    if len(parts) < 5:
        return None

    try:
        pc_hex = parts[0]
        pc_int = int(pc_hex, 16)
    except ValueError:
        return None

    mask_hex = parts[1]

    try:
        ndst = int(parts[2])
    except ValueError:
        return None

    idx = 3 + ndst          # opcode position
    if idx >= len(parts):
        return None
    opcode = parts[idx]

    idx += 1                 # nsrc position
    if idx >= len(parts):
        return None
    try:
        nsrc = int(parts[idx])
    except ValueError:
        return None

    idx += 1 + nsrc          # past src regs -> mem_width
    if idx >= len(parts):
        return None

    try:
        mem_width = int(parts[idx])
    except ValueError:
        return None

    if mem_width == 0:
        return (pc_int, mask_hex, opcode, 0, -1, [])

    idx += 1                 # addr_mode
    if idx >= len(parts):
        return (pc_int, mask_hex, opcode, mem_width, -1, [])

    try:
        addr_mode = int(parts[idx])
    except ValueError:
        return (pc_int, mask_hex, opcode, mem_width, -1, [])

    addr_tokens = parts[idx + 1:]
    return (pc_int, mask_hex, opcode, mem_width, addr_mode, addr_tokens)


# ---------------------------------------------------------------------------
# Chain CSV reader
# ---------------------------------------------------------------------------

def load_chains(csv_path: str, algorithm: str, impl: str) -> List[Tuple[int, int, int]]:
    """Load (chain_id, idx_pc, data_pc) tuples from the golden chain CSV.

    *chain_id* is assigned sequentially (0-based) for each matching row.
    PCs are returned as integers.
    """
    chains = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["algorithm"] == algorithm and row["impl"] == impl:
                idx_pc = int(row["index_pc"], 16)
                data_pc = int(row["data_pc"], 16)
                chains.append((len(chains), idx_pc, data_pc))
    return chains


# ---------------------------------------------------------------------------
# Kernel-list reader
# ---------------------------------------------------------------------------

def read_kernel_list(trace_dir: str) -> List[Tuple[int, str]]:
    """Read kernelslist.g and return [(kernel_index, traceg_filename), …].

    Only kernel entries are returned (MemcpyHtoD lines are skipped).
    The kernel_index is extracted from the filename (kernel-N-…).
    """
    kl_path = os.path.join(trace_dir, "kernelslist.g")
    kernels = []
    with open(kl_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Memcpy"):
                continue
            # Lines may be like: -trace ./kernel-N-ctx_ADDR.traceg
            # or just: kernel-N-ctx_ADDR.traceg.xz
            fname = line.split()[-1]
            # strip leading ./
            if fname.startswith("./"):
                fname = fname[2:]
            # Extract kernel index from filename
            base = os.path.basename(fname)
            # kernel-N-ctx_...
            try:
                kid = int(base.split("-")[1])
            except (IndexError, ValueError):
                continue
            kernels.append((kid, fname))
    return kernels


# ---------------------------------------------------------------------------
# Core: process one kernel trace file
# ---------------------------------------------------------------------------

def process_kernel(trace_dir: str, traceg_file: str, kernel_id: int,
                   chains: List[Tuple[int, int, int]],
                   ) -> List[Tuple[int, int, int, int, int]]:
    """Parse a single .traceg(.xz) file and extract (chain_id, idx_pc, data_pc, idx_addr, data_addr).

    Matching logic per warp:
      - For each (idx_pc, data_pc) chain, maintain a queue of index-address snapshots.
      - Every time idx_pc fires: push {lane: addr} onto the queue.
      - Every time data_pc fires: pop one index snapshot from the queue
        and match lane-by-lane.

    Returns a list of 5-tuples.
    """

    # Build lookup structures
    # idx_pc -> list of chain_ids that use this idx_pc
    idx_pc_to_chains: Dict[int, List[int]] = defaultdict(list)
    # (chain_id) -> data_pc
    chain_data_pc: Dict[int, int] = {}
    # All PCs we care about (for fast filtering)
    pcs_of_interest: Set[int] = set()

    for cid, ipc, dpc in chains:
        idx_pc_to_chains[ipc].append(cid)
        chain_data_pc[cid] = dpc
        pcs_of_interest.add(ipc)
        pcs_of_interest.add(dpc)

    # Per-warp state: chain_id -> queue of {lane: addr}
    # Each element of the queue is a dict mapping lane -> index address
    WarpState = Dict[int, List[Dict[int, int]]]

    results: List[Tuple[int, int, int, int, int]] = []
    stats = {"tb_count": 0, "warp_count": 0, "insts_parsed": 0,
             "idx_hits": 0, "data_hits": 0, "pairs_matched": 0}

    # Resolve file path (may be .traceg or .traceg.xz)
    fpath = os.path.join(trace_dir, traceg_file)
    if not os.path.exists(fpath):
        # Try .xz variant
        fpath_xz = fpath + ".xz" if not fpath.endswith(".xz") else fpath
        fpath_noxz = fpath[:-3] if fpath.endswith(".xz") else fpath
        if os.path.exists(fpath_xz):
            fpath = fpath_xz
        elif os.path.exists(fpath_noxz):
            fpath = fpath_noxz
        else:
            print(f"  WARNING: trace file not found: {traceg_file}")
            return results

    # Open (possibly compressed)
    if fpath.endswith(".xz"):
        fh = lzma.open(fpath, "rt", encoding="utf-8")
    else:
        fh = open(fpath, "r", encoding="utf-8")

    warp_state: WarpState = {}
    current_warp_id: Optional[int] = None
    in_tb = False
    t0 = time.time()

    try:
        for line in fh:
            line = line.strip()
            if not line:
                continue

            # Metadata / header
            if line.startswith("-") or line.startswith("#"):
                if line == "#BEGIN_TB":
                    in_tb = True
                    stats["tb_count"] += 1
                    # Reset warp state for new TB
                    warp_state = {}
                    current_warp_id = None
                elif line == "#END_TB":
                    in_tb = False
                continue

            if not in_tb:
                continue

            # Thread block header
            if line.startswith("thread block"):
                continue

            # Warp header
            if line.startswith("warp = "):
                current_warp_id = int(line.split("=")[1].strip())
                stats["warp_count"] += 1
                # Initialize state for this warp
                warp_state[current_warp_id] = defaultdict(list)
                continue

            # Instruction count
            if line.startswith("insts = "):
                continue

            # Parse instruction
            stats["insts_parsed"] += 1
            parsed = parse_instruction(line)
            if parsed is None:
                continue

            pc_int, mask_hex, opcode, mem_width, addr_mode, addr_tokens = parsed

            # Fast path: skip if this PC is not relevant
            if pc_int not in pcs_of_interest:
                continue

            # Only care about memory instructions
            if mem_width == 0 or addr_mode < 0:
                continue

            active = _active_lanes(mask_hex)
            if not active:
                continue

            lane_addrs = decode_addresses(addr_mode, addr_tokens, active)

            if current_warp_id is None:
                continue
            ws = warp_state.get(current_warp_id)
            if ws is None:
                ws = defaultdict(list)
                warp_state[current_warp_id] = ws

            # Check if this is an index PC
            if pc_int in idx_pc_to_chains:
                stats["idx_hits"] += 1
                for cid in idx_pc_to_chains[pc_int]:
                    ws[cid].append(lane_addrs)

            # Check if this is a data PC for any chain
            for cid, ipc, dpc in chains:
                if pc_int == dpc:
                    # Pop the oldest index snapshot for this chain
                    queue = ws.get(cid)
                    if queue:
                        stats["data_hits"] += 1
                        idx_snapshot = queue.pop(0)
                        # Match lane-by-lane
                        for lane in active:
                            if lane in idx_snapshot and lane in lane_addrs:
                                results.append((
                                    cid, ipc, dpc,
                                    idx_snapshot[lane],
                                    lane_addrs[lane],
                                ))
                                stats["pairs_matched"] += 1
                        break  # Each data_pc execution matches at most one chain pop

    finally:
        fh.close()

    elapsed = time.time() - t0
    print(f"  kernel-{kernel_id}: {stats['tb_count']} TBs, "
          f"{stats['warp_count']} warps, "
          f"{stats['insts_parsed']} instructions parsed in {elapsed:.1f}s")
    print(f"    idx_hits={stats['idx_hits']}  data_hits={stats['data_hits']}  "
          f"pairs_matched={stats['pairs_matched']}")
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract idx_addr → data_addr mapping table from GPU trace files.")
    parser.add_argument("--trace-dir", required=True,
                        help="Path to traces directory (containing kernelslist.g)")
    parser.add_argument("--chain-csv",
                        default="ima_plan/05_implementation/ima_pair_table/golden/"
                                "strict_selected_chain_instances.csv",
                        help="Path to golden chain CSV")
    parser.add_argument("--algorithm", default="bfs",
                        help="Algorithm filter (default: bfs)")
    parser.add_argument("--impl", default="linear_base",
                        help="Implementation filter (default: linear_base)")
    parser.add_argument("--output", default=None,
                        help="Output CSV path (default: <trace-dir>/pair_table.csv)")
    parser.add_argument("--kernels", default=None,
                        help="Comma-separated kernel indices to process (default: all)")

    args = parser.parse_args()

    # Resolve chain CSV path (may be relative to repo root)
    chain_csv = args.chain_csv
    if not os.path.isabs(chain_csv):
        # Try relative to script location's repo root
        repo_root = Path(__file__).resolve().parents[3]
        candidate = repo_root / chain_csv
        if candidate.exists():
            chain_csv = str(candidate)

    print(f"=== Extract Pair Table from Trace ===")
    print(f"Trace dir : {args.trace_dir}")
    print(f"Chain CSV : {chain_csv}")
    print(f"Algorithm : {args.algorithm}")
    print(f"Impl      : {args.impl}")

    # Load chains
    chains = load_chains(chain_csv, args.algorithm, args.impl)
    if not chains:
        print(f"ERROR: No chains found for algorithm={args.algorithm}, impl={args.impl}")
        sys.exit(1)
    print(f"\nLoaded {len(chains)} chains:")
    for cid, ipc, dpc in chains:
        print(f"  chain {cid}: idx_pc=0x{ipc:04x} -> data_pc=0x{dpc:04x}")

    # Read kernel list
    kernel_list = read_kernel_list(args.trace_dir)
    if not kernel_list:
        print(f"ERROR: No kernels found in {args.trace_dir}/kernelslist.g")
        sys.exit(1)
    print(f"\nFound {len(kernel_list)} kernels in kernelslist.g")

    # Filter kernels if requested
    if args.kernels:
        wanted = set(int(k) for k in args.kernels.split(","))
        kernel_list = [(kid, kf) for kid, kf in kernel_list if kid in wanted]
        print(f"Filtered to {len(kernel_list)} kernel(s): {sorted(k[0] for k in kernel_list)}")

    # Process each kernel
    all_results: List[Tuple[int, int, int, int, int]] = []
    t_total = time.time()
    for kid, kfile in sorted(kernel_list):
        print(f"\nProcessing kernel-{kid} ({kfile})...")
        pairs = process_kernel(args.trace_dir, kfile, kid, chains)
        all_results.extend(pairs)

    elapsed_total = time.time() - t_total
    print(f"\n=== Summary ===")
    print(f"Total pairs extracted: {len(all_results)}")
    print(f"Total time: {elapsed_total:.1f}s")

    if not all_results:
        print("WARNING: No pairs found. Check chain PCs and trace content.")
        return

    # Per-chain stats
    chain_counts = defaultdict(int)
    for cid, ipc, dpc, ia, da in all_results:
        chain_counts[cid] += 1
    print("\nPer-chain pair counts:")
    for cid, ipc, dpc in chains:
        cnt = chain_counts.get(cid, 0)
        print(f"  chain {cid} (0x{ipc:04x}->0x{dpc:04x}): {cnt} pairs")

    # Unique idx_addr and data_addr counts
    unique_idx = len(set(r[3] for r in all_results))
    unique_data = len(set(r[4] for r in all_results))
    print(f"\nUnique index addresses: {unique_idx}")
    print(f"Unique data addresses : {unique_data}")

    # Sort by idx_addr ascending
    all_results.sort(key=lambda r: r[3])

    # Write output
    out_path = args.output
    if out_path is None:
        out_path = os.path.join(args.trace_dir, "pair_table.csv")

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["chain_id", "idx_pc", "data_pc", "idx_addr", "data_addr"])
        for cid, ipc, dpc, ia, da in all_results:
            writer.writerow([cid, f"0x{ipc:04x}", f"0x{dpc:04x}",
                             f"0x{ia:016x}", f"0x{da:016x}"])

    print(f"\nOutput written to: {out_path}")

    # Show a few sample rows
    print("\nSample rows (first 10):")
    print(f"  {'chain':>5}  {'idx_pc':>8}  {'data_pc':>8}  {'idx_addr':>18}  {'data_addr':>18}")
    for cid, ipc, dpc, ia, da in all_results[:10]:
        print(f"  {cid:>5}  0x{ipc:04x}    0x{dpc:04x}    0x{ia:016x}  0x{da:016x}")


if __name__ == "__main__":
    main()
