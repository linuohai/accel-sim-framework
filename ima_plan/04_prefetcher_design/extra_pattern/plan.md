# IMA Prefetcher Tiny Test Case & Execution Visualization

## Goal

Build a controlled small-scale test environment for IMA prefetcher development:
1. Baseline for prefetcher validation
2. Detailed execution timeline visualization (warp switching, L1 return timing, loop iterations)
3. 1-SM configuration for maximum observability

## Steps

### Step 1: SM80_A100_1SM Configuration
- Copy `SM80_A100/gpgpusim.config` → `SM80_A100_1SM/gpgpusim.config`
- Modify: `gpgpu_n_clusters=1`, `gpgpu_n_mem=1`, `gpgpu_n_sub_partition_per_mchannel=2`
- Use via: `./traceL1 -c SM80_A100_1SM ...`

### Step 2: Run Test Workloads
```bash
./traceL1 -c SM80_A100_1SM --max-completed-cta 20 bfs_ima_small bfs_1sm_cta20
./traceL1 -c SM80_A100_1SM --max-completed-cta 5  bfs_ima_small bfs_1sm_cta5
./traceL1 -c SM80_A100_1SM spmv spmv_1sm
```

### Step 3: L1D Fill-Time Tracking
- Add `l1_tracer::emit_fill()` to record FILL events in L1 trace CSV
- Hook into `ldst_unit::cycle()` at `m_L1D->fill()` call site in shader.cc
- Enables MISS→FILL latency pairing by `(sm_id, warp_id, pc, address)`

### Step 4: Visualization Script (`plot_ima_timeline.py`)
Three plots:
1. **Warp-Level IMA Heatmap** — X: cycle, Y: warp ID, color: load type × status
2. **Single-Warp Gantt** — IMA chain dependency timeline for one warp
3. **Address Scatter** — X: cycle, Y: cache line address, color: load type

Plus `ima_chain_stats.csv` with per-warp miss rates, latencies, MLP estimates.

## BFS IMA Sub-classification (from pc_classification.csv)

| Source Line | IMA Role | PCs |
|-------------|----------|-----|
| linear_base.cu:16-17 | row_offset | 0xf0, 0x100 |
| linear_base.cu:19 | index_load | 0x1d0 (+ 0x640 stride variant) |
| linear_base.cu:20 | data_load | 0x200, 0x670, 0x9d0, 0xd30, 0x1090 |
| linear_base.cu:21 | data_load | 0x270 |

## File Layout
```
ima_plan/04_prefetcher_design/tiny_case/
├── plan.md                     # This file
├── plot_ima_timeline.py        # Visualization script
├── run_tiny_case.sh            # One-click simulation wrapper
├── ima_chain_stats.csv         # Generated statistics
└── figures/                    # Generated plots
```
