# ima_high baseline L1 miss breakdown

> Generated: 2026-03-15 07:29

## Method

- SASS baseline: runtime `sm_80` SASS extracted from NVBit runtime cubins and mirrored under `ima_plan/01_ima_characterization/sass_analysis/`.
- Scope: only real `LDG*` instructions from the main kernel(s) of each workload.
- Three classes only: `regular`, `stride`, `ima`.
- Rule priority: if a load address depends on a prior load value, classify it as `ima`; otherwise, if the address is computed by regular arithmetic without load dependency, classify it as `stride`; all remaining covered loads are `regular`.
- Trace PCs that do not map to those real main-kernel load PCs are excluded from the main summary and reported through coverage.

## Key Findings

- `bfs_ima_high` 的 covered main-kernel miss 主导类是 `ima`，miss_share = 79.3%。
- `sssp_ima_high` 的 covered main-kernel miss 主导类是 `ima`，miss_share = 51.1%。
- `bc_ima_high` 的 covered main-kernel miss 主导类是 `ima`，miss_share = 70.5%。
- `cc_ima_high` 的 covered main-kernel miss 主导类是 `ima`，miss_share = 83.6%。
- `spmv_ima_high` 的 covered main-kernel miss 主导类是 `ima`，miss_share = 66.9%。
- Static load mix shows that IMA loads span 26.7%–61.9% of real static `LDG*` instructions, but they account for 51.1%–83.6% of covered L1 misses across `ima_high`.

## Coverage Summary

| Workload | covered access | covered miss | dropped access | dropped miss |
| --- | --- | --- | --- | --- |
| bfs_ima_high | 100.0% | 100.0% | 1 | 1 |
| sssp_ima_high | 100.0% | 100.0% | 1 | 1 |
| bc_ima_high | 92.9% | 92.2% | 46100560 | 45600102 |
| cc_ima_high | 100.0% | 100.0% | 0 | 0 |
| spmv_ima_high | 100.0% | 100.0% | 0 | 0 |

## Miss Share Summary

| Workload | regular miss_share | stride miss_share | ima miss_share |
| --- | --- | --- | --- |
| bfs_ima_high | 15.7% | 5.0% | 79.3% |
| sssp_ima_high | 40.0% | 9.0% | 51.1% |
| bc_ima_high | 21.8% | 7.7% | 70.5% |
| cc_ima_high | 5.1% | 11.3% | 83.6% |
| spmv_ima_high | 7.9% | 25.2% | 66.9% |

## Static Load Mix

- The table below uses runtime `sm_80` SASS from the traced main kernels, so it reflects static SASS composition rather than dynamic issue counts.
- The figure and the first ratio column use `IMA loads / all static LDG* instructions`, which is the requested load-only view.

| Workload | IMA loads / loads | IMA loads / instructions | IMA static loads | All static loads | All main-kernel inst |
| --- | --- | --- | --- | --- | --- |
| bfs_ima_high | 37.5% | 2.7% | 9 | 24 | 336 |
| sssp_ima_high | 34.5% | 4.2% | 10 | 29 | 240 |
| bc_ima_high | 43.1% | 3.4% | 25 | 58 | 736 |
| cc_ima_high | 61.9% | 7.4% | 13 | 21 | 176 |
| spmv_ima_high | 26.7% | 10.0% | 24 | 90 | 240 |

## Top Miss PCs

| Workload | Rank | Kernel | PC | Class | Miss count | Miss rate |
| --- | --- | --- | --- | --- | --- | --- |
| bfs_ima_high | 1 | _Z10bfs_kerneliPKmPKiPi9Worklist2S4_ | 0x1d0 | ima | 35477394 | 98.3% |
| bfs_ima_high | 2 | _Z10bfs_kerneliPKmPKiPi9Worklist2S4_ | 0xf0 | ima | 27994935 | 99.4% |
| bfs_ima_high | 3 | _Z10bfs_kerneliPKmPKiPi9Worklist2S4_ | 0x200 | ima | 27143055 | 99.9% |
| bfs_ima_high | 4 | _Z10bfs_kerneliPKmPKiPi9Worklist2S4_ | 0xd30 | ima | 12079424 | 99.1% |
| sssp_ima_high | 1 | _Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_ | 0x240 | ima | 65626484 | 99.6% |
| sssp_ima_high | 2 | _Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_ | 0x250 | ima | 64930084 | 99.7% |
| sssp_ima_high | 3 | _Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_ | 0x280 | ima | 60685046 | 99.7% |
| sssp_ima_high | 4 | _Z12bellman_fordiPKmPKiPiS3_9Worklist2S4_ | 0x2a0 | ima | 55771251 | 100.0% |
| bc_ima_high | 1 | _Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_|_Z10bc_reverseiPKmPKiS2_S2_S2_iPfS3_ | 0x200 | ima | 73487161 | 99.5% |
| bc_ima_high | 2 | _Z10bc_reverseiPKmPKiS2_S2_S2_iPfS3_ | 0x230 | ima | 39122640 | 99.9% |
| bc_ima_high | 3 | _Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_ | 0x1d0 | ima | 37718575 | 98.6% |
| bc_ima_high | 4 | _Z10bc_forwardPKmPKiPiS3_i9Worklist2S4_ | 0xf0 | ima | 29095429 | 99.6% |
| cc_ima_high | 1 | _Z4hookiPKmPKiPiPb | 0x1e0 | ima | 92784538 | 99.3% |
| cc_ima_high | 2 | _Z4hookiPKmPKiPiPb | 0x3c0 | ima | 92551486 | 98.6% |
| cc_ima_high | 3 | _Z4hookiPKmPKiPiPb | 0x4d0 | ima | 92003502 | 98.5% |
| cc_ima_high | 4 | _Z4hookiPKmPKiPiPb | 0x5e0 | ima | 91959606 | 98.5% |
| spmv_ima_high | 1 | _Z15spmv_csr_scalariPKmPKiPKfS4_Pf | 0x250 | ima | 20792569 | 99.8% |
| spmv_ima_high | 2 | _Z15spmv_csr_scalariPKmPKiPKfS4_Pf | 0x200 | ima | 15578916 | 95.2% |
| spmv_ima_high | 3 | _Z15spmv_csr_scalariPKmPKiPKfS4_Pf | 0x230 | ima | 15224159 | 95.0% |
| spmv_ima_high | 4 | _Z15spmv_csr_scalariPKmPKiPKfS4_Pf | 0xd80 | ima | 5898746 | 99.6% |

## Outputs

- `data/pc_classification.csv`
- `data/pc_classification_candidates.csv`
- `data/per_pc_stats.csv`
- `data/per_workload_class_summary.csv`
- `data/coverage_summary.csv`
- `data/per_workload_top_miss_pcs.csv`
- `data/instruction_mix_summary.csv`
- `figures/ima_high_baseline_l1_miss_share.svg`
- `figures/ima_high_baseline_l1_miss_share_no_labels.svg`
- `figures/ima_high_baseline_ima_instruction_share.svg`

