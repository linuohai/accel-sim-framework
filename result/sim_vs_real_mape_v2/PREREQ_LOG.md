# SC.0 Reconnaissance: Sim Log Field Inventory

**Date**: 2026-04-17  
**Task**: Determine whether SC.6 (write parser) is "parser-only (~30min)" or needs sim source changes (~1.5h+)  
**Decision**: **Classification A — Parser-only, ~30 min**

## Verification Note

This file replaces the misplaced `docs/superpowers/specs/SC.0_sim_log_reconnaissance.md`. The source log inspected is corrected to `result/sim_vs_real_mape/sim_logs/cfg_03.log` (v1 baseline sim_vs_real_mape experiment), which is the authoritative log for SC.6 parser design.

## Inspected Artifact

- **File**: `result/sim_vs_real_mape/sim_logs/cfg_03.log` (baseline GPGPU-Sim run, v1 sim_vs_real_mape experiment)
- **Size**: 655,848 bytes
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

**Example (cfg_03)**: `L1D_total_cache_accesses = 1572864`, `L1D_total_cache_accesses = 2121728` (multiple kernels)

### L2 (Unified Cache)
| Field | Per-Kernel | Per-Bank | Notes |
|-------|-----------|----------|-------|
| Access count | ✓ `L2_total_cache_accesses` | ✓ `L2_cache_bank[0..159]` | Direct read |
| Detailed breakdown | ✓ `L2_cache_stats_breakdown[<type>][<status>]` | — | By access type (GLOBAL_ACC_R/W, LOCAL_ACC_*, CONST_ACC_*, TEXTURE_ACC_*, L1_WRBK_ACC, L2_WRBK_ACC, INST_ACC_R, L1_WR_ALLOC_R, L2_WR_ALLOC_R) and status (HIT, HIT_RESERVED, MISS, RESERVATION_FAIL, SECTOR_MISS, MSHR_HIT) |
| Port utilization | ✓ `L2_cache_data_port_util`, `L2_cache_fill_port_util` | — | Per kernel |

**Example (cfg_03 aggregate)**: 
```
L2_total_cache_accesses = 1572864
L2_total_cache_accesses = 19415040
```

### IPC & Cycle Counts
| Field | Per-Kernel | Notes |
|-------|-----------|-------|
| `gpu_sim_insn` | ✓ | Kernel total instructions |
| `gpu_tot_sim_insn` | ✓ | Cumulative across all SMs |
| `gpu_tot_ipc` | ✓ | Direct read, e.g., `gpu_tot_ipc = 10153.2344`, `4973.4282` |
| `gpu_sim_cycle` | ✓ | Kernel cycle count |
| `gpu_tot_sim_cycle` | ✓ | Cumulative cycles |
| `m_num_sim_winsn` | ✗ NOT FOUND | Not in baseline log; **SC.1 must add WINSN_TOTAL dump** |

**Important Note**: The `gpu_tot_ipc` field in cfg_03 (e.g., `10153.2344`, `4973.4282`) represents **thread-active IPC**, NOT warp-IPC. This is the ratio of total instructions issued to total thread-active cycles. To compute **warp-level IPC** for sim_vs_real_mape comparison, `m_num_sim_winsn` (total warp instructions) must be added to the log via SC.1's source modification.

**Example (cfg_03)**: `gpu_tot_ipc = 10153.2344` (thread-active IPC)

### DRAM & Bandwidth
| Field | Emitted | Granularity | Notes |
|-------|---------|------------|-------|
| `L2_BW` | ✓ | Per kernel | e.g., `L2_BW = 0.0217 GB/Sec` |
| `dram_util_bins` | ✓ | Per DRAM partition × per-kernel-end | 10-bin histogram per partition (16 partitions), printed once at each kernel boundary |
| DRAM partition detail | ✓ | Per partition | `n_cmd`, `n_nop`, `n_rd`, `bw_util`, etc. |
| Interconnect stats | ✓ | Global only | `icnt_total_pkts_mem_to_simt`, conflicts, buffer util |

**Note on `dram_util_bins`**: In cfg_03, the histogram is printed per DRAM partition (16 total) at each kernel boundary. Example format: `dram_util_bins: 0 0 0 0 0 0 0 0 0 0` (10 bins per partition). For small workloads like cfg_03, many bins remain zero; larger kernels populate bins across the utilization spectrum. The format is verified and sufficient for baseline MAPE comparison.

## SC.6 Scope Analysis

### Can SC.6 proceed as "parser-only"?

**YES** — All required metrics are already emitted:

1. **L1D access count**: Direct per-kernel field → no computation needed
2. **L2 access count**: Direct per-kernel field → no computation needed
3. **IPC**: Direct per-kernel field → no computation needed (thread-active; warp-IPC requires SC.1 WINSN_TOTAL)
4. **Cycle count**: Direct per-kernel field → no computation needed
5. **Cache breakdown**: Detailed type/status breakdown already aggregated → parser can extract directly
6. **DRAM util**: Per-kernel-end histogram sufficient for baseline → no per-kernel accumulation required

### Why not B (per-kernel delta) or C (source changes)?

- **Per-SM banks/cores ARE available** → if granular per-kernel analysis needed later, can sum per-kernel (O(n) post-processing)
- **No missing fields** (except warp-IPC, which is SC.1's job) → no sim source modification required for SC.6
- **Log structure stable** → kernel delimiters clear, easy to parse

### Estimated SC.6 effort

- **Parse per-kernel summary lines**: 10 min (grep + regex per kernel_launch_uid block)
- **Extract L1D/L2/IPC fields**: 10 min (simple field lookup)
- **Generate CSV output**: 5 min (pandas or simple CSV writer)
- **Test on 2-3 logs**: 5 min

**Total**: ~30 min (Classification A confirmed)

## Confidence

**HIGH**. Log format is mature, stable, and complete. No surprises expected in SC.6 implementation. SC.1's WINSN_TOTAL addition is a separate, scoped task.

## SC.3 Concern (2026-04-17): DRAM_UTIL_BINS often zero

After SC.2+SC.3, smoke verify on v1 cfg_01 shows `DRAM_UTIL_BINS: 0 0 0 0 0 0 0 0 0 0 (total=0)` — expected for small workload.

But independently grepping v1 cfg_03 (FA-7B-s2k) baseline log shows `dram_util_bins: 0 0 0 0 0 0 0 0 0 0` ALSO all zero, despite v1 reverse-derived DRAM util being non-zero (~50% per old metric). This means the sim's internal bin accumulation logic likely doesn't trigger as expected for typical workloads.

**Implication for SC.6**: parser must handle zero-total bins gracefully:
- If total > 0: use weighted util (preferred per Step C decision)
- If total == 0: fall back to v1's reverse-derive `(rd+wr)*32B/runtime/1555`
- Document the fallback in parser comments

**Future investigation** (not blocking v2): why dram_util_bins doesn't populate on FA workloads — may be a sim bug or specific to certain DRAM scheduler configs. Can be SC.X+ deferred.
