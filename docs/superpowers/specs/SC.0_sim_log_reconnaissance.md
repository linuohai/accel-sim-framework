# SC.0 Reconnaissance: Sim Log Field Inventory

**Date**: 2026-04-17  
**Task**: Determine whether SC.6 (write parser) is "parser-only (~30min)" or needs sim source changes (~1.5h+)  
**Decision**: **Classification A — Parser-only, ~30 min**

## Inspected Artifact

- **File**: `result/log/bfs_ima_high.log` (baseline GPGPU-Sim run, 18 kernels)
- **Size**: 3.6 MB, 87,021 lines
- **GPU Config**: SM80_A100 (108 SMs, 160 L2 banks, 16 DRAM partitions)
- **Log Structure**: Per-kernel output delimited by `kernel_launch_uid = <N>`

## Findings

### L1D (Data Cache)
| Field | Per-Kernel | Per-SM | Notes |
|-------|-----------|--------|-------|
| Access count | ✓ `L1D_total_cache_accesses` | ✓ `L1D_cache_core[0..107]` | Direct read, no delta needed |
| Miss count | ✓ `L1D_total_cache_misses` | ✓ per SM | Integrated per kernel |
| Miss rate | ✓ | ✓ | Computed field |
| Pending hits | ✓ | ✓ | Available |
| Reservation fails | ✓ | ✓ | Available |

**Example (kernel 6)**: `L1D_total_cache_accesses = 20733068`, `L1D_total_cache_misses = 5009120`

### L2 (Unified Cache)
| Field | Per-Kernel | Per-Bank | Notes |
|-------|-----------|----------|-------|
| Access count | ✓ `L2_total_cache_accesses` | ✓ `L2_cache_bank[0..159]` | Direct read |
| Detailed breakdown | ✓ `L2_cache_stats_breakdown[<type>][<status>]` | — | By access type (GLOBAL_ACC_R/W, LOCAL_ACC_*, CONST_ACC_*, TEXTURE_ACC_*, L1_WRBK_ACC, L2_WRBK_ACC, INST_ACC_R, L1_WR_ALLOC_R, L2_WR_ALLOC_R) and status (HIT, HIT_RESERVED, MISS, RESERVATION_FAIL, SECTOR_MISS, MSHR_HIT) |
| Port utilization | ✓ `L2_cache_data_port_util`, `L2_cache_fill_port_util` | — | Per kernel |

**Example (kernel 6 aggregate)**: 
```
L2_total_cache_accesses = 18009942
L2_total_cache_misses = 3827154
L2_total_cache_miss_rate = 0.2124
```

### IPC & Cycle Counts
| Field | Per-Kernel | Notes |
|-------|-----------|-------|
| `gpu_sim_insn` | ✓ | Kernel total instructions |
| `gpu_tot_sim_insn` | ✓ | Cumulative across all SMs |
| `gpu_tot_ipc` | ✓ | Direct read, e.g., `gpu_tot_ipc = 14.4808` |
| `gpu_sim_cycle` | ✓ | Kernel cycle count |
| `gpu_tot_sim_cycle` | ✓ | Cumulative cycles |
| `m_num_sim_winsn` | ✗ NOT FOUND | Not in baseline log |

**Example (kernel 1)**: `gpu_sim_insn = 2070`, `gpu_tot_ipc = 0.3313`, `gpu_sim_cycle = 6248`

### DRAM & Bandwidth
| Field | Emitted | Granularity | Notes |
|-------|---------|------------|-------|
| `L2_BW` | ✓ | Per kernel | e.g., `L2_BW = 0.0217 GB/Sec` |
| `dram_util_bins` | ✓ | Per DRAM partition (16) | 10-bin histogram, printed once at end-of-sim, not per-kernel |
| DRAM partition detail | ✓ | Per partition | `n_cmd`, `n_nop`, `n_rd`, `bw_util`, etc. |
| Interconnect stats | ✓ | Global only | `icnt_total_pkts_mem_to_simt`, conflicts, buffer util |

**Note**: DRAM histogram is global (not per-kernel), but sufficient for baseline MAPE comparison (only aggregate metrics needed).

## SC.6 Scope Analysis

### Can SC.6 proceed as "parser-only"?

**YES** — All required metrics are already emitted:

1. **L1D access count**: Direct per-kernel field → no computation needed
2. **L2 access count**: Direct per-kernel field → no computation needed
3. **IPC**: Direct per-kernel field → no computation needed
4. **Cycle count**: Direct per-kernel field → no computation needed
5. **Cache breakdown**: Detailed type/status breakdown already aggregated → parser can extract directly
6. **DRAM util**: Global histogram sufficient for baseline → no per-kernel accumulation required

### Why not B (per-kernel delta) or C (source changes)?

- **Per-SM banks/cores ARE available** → if granular per-kernel analysis needed later, can sum per-kernel (O(n) post-processing)
- **No missing fields** → no sim source modification required
- **Log structure stable** → kernel delimiters clear, easy to parse

### Estimated SC.6 effort

- **Parse per-kernel summary lines**: 10 min (grep + regex per kernel_launch_uid block)
- **Extract L1D/L2/IPC fields**: 10 min (simple field lookup)
- **Generate CSV output**: 5 min (pandas or simple CSV writer)
- **Test on 2-3 logs**: 5 min

**Total**: ~30 min (Classification A confirmed)

## Confidence

**HIGH**. Log format is mature, stable, and complete. No surprises expected in SC.6 implementation.
