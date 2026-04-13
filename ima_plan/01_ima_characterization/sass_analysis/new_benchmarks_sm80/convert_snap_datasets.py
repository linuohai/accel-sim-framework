#!/usr/bin/env python3
"""
Convert SNAP datasets from MTX (Matrix Market) to:
1. METIS .graph format (for Pannotia MIS/Color)
2. Galois .gr binary format (for LonestarGPU MST)

All outputs are symmetric (undirected), self-loops removed.
"""
import struct
import sys
import os
import numpy as np
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]  # up to /workspace/prefetch
GARDENIA_DATA = REPO_ROOT / "gpu-app-collection/gardenia/datasets/real_workload"
PANNOTIA_DATA = REPO_ROOT / "gpu-app-collection/data_dirs/pannotia"
LSGPU_DATA = REPO_ROOT / "gpu-app-collection/data_dirs/cuda/lonestargpu-2.0/inputs"

DATASETS = ["cit-Patents", "web-Google", "flickr", "roadNet-CA"]


def read_mtx(filepath):
    """Read MTX file, return (num_nodes, edges_list) with 0-indexed edges."""
    symmetric = False
    num_nodes = 0
    edges = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line.startswith("%%"):
                if "symmetric" in line.lower():
                    symmetric = True
                continue
            if line.startswith("%"):
                continue
            parts = line.split()
            if num_nodes == 0:
                # First data line: rows cols nnz
                num_nodes = int(parts[0])
                continue
            # Edge line: row col [value]
            r, c = int(parts[0]) - 1, int(parts[1]) - 1  # 0-indexed
            if r == c:
                continue  # skip self-loops
            edges.append((r, c))
            if symmetric:
                edges.append((c, r))

    # For general (directed) graphs, symmetrize
    if not symmetric:
        edge_set = set(edges)
        sym_edges = set()
        for r, c in edge_set:
            sym_edges.add((r, c))
            sym_edges.add((c, r))
        edges = list(sym_edges)

    return num_nodes, edges


def build_adjacency(num_nodes, edges):
    """Build sorted adjacency list from edges."""
    adj = defaultdict(set)
    for r, c in edges:
        adj[r].add(c)
    # Sort neighbors for each node
    sorted_adj = {}
    for v in range(num_nodes):
        sorted_adj[v] = sorted(adj.get(v, set()))
    return sorted_adj


def write_metis(filepath, num_nodes, adj):
    """Write METIS .graph format (1-indexed neighbor lists)."""
    # Count undirected edges (each edge counted once per endpoint)
    total_entries = sum(len(adj[v]) for v in range(num_nodes))
    num_undirected_edges = total_entries // 2

    with open(filepath, "w") as f:
        f.write(f"{num_nodes} {num_undirected_edges}\n")
        for v in range(num_nodes):
            neighbors = adj[v]
            if neighbors:
                # METIS uses 1-indexed
                f.write(" ".join(str(n + 1) for n in neighbors) + " \n")
            else:
                f.write("\n")

    print(f"  METIS: {filepath}")
    print(f"    nodes={num_nodes}, undirected_edges={num_undirected_edges}, "
          f"total_adj_entries={total_entries}")


def write_galois_gr(filepath, num_nodes, adj):
    """Write Galois .gr binary format (little-endian)."""
    # Build CSR arrays
    num_edges = sum(len(adj[v]) for v in range(num_nodes))

    # outIdx: cumulative edge count (exclusive prefix sum)
    # outIdx[i] = total edges of nodes 0..i
    outIdx = np.zeros(num_nodes, dtype=np.uint64)
    running = 0
    for v in range(num_nodes):
        running += len(adj[v])
        outIdx[v] = running

    # outs: destination node IDs
    outs = np.zeros(num_edges, dtype=np.uint32)
    idx = 0
    for v in range(num_nodes):
        for n in adj[v]:
            outs[idx] = n
            idx += 1

    # edgeData: weights (all 1 for unweighted)
    edgeData = np.ones(num_edges, dtype=np.uint32)

    # Write binary
    with open(filepath, "wb") as f:
        # Header: version, sizeEdgeTy, numNodes, numEdges
        f.write(struct.pack("<QQQQ", 1, 4, num_nodes, num_edges))
        # outIdx array
        f.write(outIdx.tobytes())
        # outs array
        f.write(outs.tobytes())
        # Padding if numEdges is odd (align to 8 bytes)
        if num_edges % 2:
            f.write(struct.pack("<I", 0))
        # edgeData array
        f.write(edgeData.tobytes())

    size_mb = os.path.getsize(filepath) / 1048576
    print(f"  Galois .gr: {filepath}")
    print(f"    nodes={num_nodes}, edges={num_edges}, size={size_mb:.1f} MB")


def main():
    for ds in DATASETS:
        mtx_path = GARDENIA_DATA / ds / f"{ds}.mtx"
        if not mtx_path.exists():
            print(f"[SKIP] {ds}: {mtx_path} not found")
            continue

        print(f"\n{'='*60}")
        print(f"Converting {ds} ...")
        print(f"  Source: {mtx_path}")

        num_nodes, edges = read_mtx(mtx_path)
        print(f"  Read: {num_nodes} nodes, {len(edges)} directed edge entries")

        adj = build_adjacency(num_nodes, edges)

        # Write METIS for Pannotia MIS and Color
        for app in ["mis", "color_max"]:
            metis_dir = PANNOTIA_DATA / app / "data"
            metis_dir.mkdir(parents=True, exist_ok=True)
            metis_path = metis_dir / f"{ds}.graph"
            write_metis(metis_path, num_nodes, adj)

        # Write Galois .gr for LonestarGPU MST
        gr_path = LSGPU_DATA / f"{ds}.sym.gr"
        write_galois_gr(gr_path, num_nodes, adj)

    print(f"\n{'='*60}")
    print("All conversions complete.")


if __name__ == "__main__":
    main()
