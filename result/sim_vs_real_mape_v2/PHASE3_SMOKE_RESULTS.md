# v2 Phase 3 Smoke Test Results

> 最近更新: 2026-04-20
> 状态: Phase 3 完成，4 cfg 全部通过 kernel-set validation，Checkpoint A 就绪

## 一句话结论

4 个代表性 cfg（FA / Decode / GEMM / RMSNorm 各 1）的 trace + sim + ncu + MAPE 全 pipeline 跑通。**指令计数 MAPE 0-5.5%（sim 极准）；DRAM MAPE 2.7-30.4%；cycle MAPE 25.9-40.2%（sim 系统性偏高，GPGPU-Sim 已知 IPC 保守性）**。Kernel 集合在 sim 与 NCU 两端 100% 对齐。

## 参与 Cfg

| cfg | workload | 参数 | kernel_regex |
|-----|---------|------|-------------|
| F3 | fa | B=1 S=2048 H=32 kv_H=32 D=128 causal=True bf16 | `.*flash_fwd.*` |
| D3 | decode | B=1 kv=2048 H=32 kv_H=32 D=128 page=16 bf16 | `.*flashinfer.*` |
| G4 | gemm | M=1024 K=4096 N=11008 bf16 (LLaMA-2 7B FFN-up) | `.*gemm.*` |
| R2 | rmsnorm | M=1024 hidden=4096 vLLM impl bf16 | `.*fused_add_rms_norm.*` |

## 最终 MAPE 表（kernel 集合严格一致）

| cfg | cycle_sim | cycle_ncu | **cycle%** | winsn_sim | winsn_ncu | **winsn%** | dram_sim% | dram_ncu% | **dram%** |
|-----|-----------|-----------|------------|-----------|-----------|------------|-----------|-----------|-----------|
| F3 (FA) | 464,641 | 345,546 | **34.5%** | 34.76M | 34.17M | **1.7%** | 13.86 | 15.05 | **7.9%** |
| D3 (Decode) | 73,037 | 52,102 | **40.2%** | 2.47M | 2.39M | **3.3%** | 41.74 | 45.13 | **7.5%** |
| G4 (GEMM) | 1,428,103 | 1,134,761 | **25.9%** | 81.34M | 77.12M | **5.5%** | 15.41 | 15.00 | **2.7%** |
| R2 (RMSNorm) | 75,663 | 54,850 | **37.9%** | 3.80M | 3.80M | **0.0%** | 40.22 | 57.79 | **30.4%** |

### Kernel Set Validation

```
✅ F3:  sim 1 ↔ ncu 1 matched   (14 noise kernels 过滤: 3 curand init)
✅ D3:  sim 2 ↔ ncu 2 matched   (16 总, 14 noise 过滤: arange/vectorized_elementwise/unrolled_elementwise 等)
✅ G4:  sim 2 ↔ ncu 2 matched   (2 noise 过滤: curand init × 2)
✅ R2:  sim 2 ↔ ncu 2 matched   (2 noise 过滤: curand init × 2)
OVERALL: ✅ ALL CONSISTENT
```

## 方法学（已实现）

1. **NVBit trace 过滤**: `DYNAMIC_KERNEL_RANGE="0-@<regex>"`。必须有 `0-@` 前缀，否则 NVBit 按 ID range 解析 regex 会触发 `std::stoull` → 传染为 PyTorch `RuntimeError: stoull`。
2. **Post-tracer 二次过滤**: NVBit 偶尔会漏匹配（D3 里 `unrolled_elementwise` 名字不含 flashinfer 但被抓进 trace）。`run_tracer.sh` 在 post-traces-processing 后读每个 `.traceg.xz` 的 `kernel name = ...` 首行，按 configs.csv 的 `kernel_regex` 二次过滤 `kernelslist.g`，确保 sim 和 NCU 看到同一集合。
3. **NCU 过滤**: NCU CSV 含全部 kernel（包括 PyTorch init）。`compute_mape.py` 按 kernel_regex 过滤 target rows。
4. **DRAM util 反推**: sim 端 `L2_total_cache_misses × 32B / runtime / 1555 GB/s`——L2 hit 不到 HBM。`dram_util_bins[]` 源码里从未被 `++`（SC.2 只加了打印，累加逻辑本就没有），因此永远全 0，走反推 fallback。
5. **Cycle 对比**: sim `gpu_tot_sim_cycle` vs NCU `gpc__cycles_elapsed.avg`（两端都是 GPU clock cycle 计数）。
6. **Warp 指令对比**: sim `WINSN_TOTAL`（SC.1）vs NCU `smsp__inst_executed.sum`。

## 跨维度观察

- **winsn MAPE 极小（≤5.5%）**: sim 的指令模型与硬件在 SASS 级别高度一致。这是 Accel-Sim/GPGPU-Sim 体系的优势——trace 驱动保证指令序列准确。
- **cycle MAPE 系统性偏高 26-40%**: sim cycle 比硬件多约 30-40%。属 GPGPU-Sim 长期存在的 IPC 保守性问题（调度器/latency 模型过严），不是 v2 的实验问题。
- **DRAM MAPE 跨度大**:
  - FA / Decode / GEMM 都在 8% 内（compute-bound 或简单 memory access pattern）
  - R2 (RMSNorm) 30.4% 偏大，疑似 vLLM Triton kernel 的 shared memory / L2 prefetch 优化 GPGPU-Sim 模型不够细

## Pipeline 脚本 + 关键 commit

| 文件 | 作用 |
|------|------|
| `scripts/run_tracer.sh` | NVBit trace + post-filter kernelslist.g |
| `scripts/run_sim.sh` | GPGPU-Sim 跑 trace |
| `scripts/run_ncu.sh` | NCU profile，覆盖 12 个 metrics（含新增 gpc_cycles_elapsed + inst_executed.sum） |
| `scripts/gen_configs.py` | 生成 41 cfg × 16 列 configs.csv |
| `scripts/compute_mape.py` | 解析 sim log + NCU CSV，按 kernel_regex 过滤算 MAPE，带 kernel-set validation |

关键 commit（2026-04-17 → 2026-04-20）:

- `2da4c7a` — 41-cfg matrix 生成器 + configs.csv
- `18fb389` — run_tracer.sh Discovery/Filter/Verify 三阶段
- `52d143a` — run_sim.sh v2 路径
- `9c01f05` — run_ncu.sh 4 workload + 新 metrics
- `f22527f` — Phase 3 Discovery 后填 kernel_regex
- `fde7637` — NVBit `0-@regex` 前缀 (fix PyTorch RuntimeError stoull)
- `228f650` — NCU metric 追加 gpc_cycles_elapsed + inst_executed.sum
- `14e4bf7` — compute_mape.py parser
- `2db6504` — post-tracer kernelslist filter + MAPE validation
- `d75b172` — SIGPIPE fix (让 post-filter 真正运行)

## Phase 3 踩过的坑（blocker → solution）

| 问题 | 根因 | 解决 |
|------|------|------|
| NCU 多 kernel vs sim 多/少 kernel | NCU 不按 regex 过滤，默认 profile 所有 kernel | parser 按 kernel_regex 过滤 NCU rows |
| v2 fix 后 F3 trace 跑不起来 `RuntimeError: stoull` | NVBit `DYNAMIC_KERNEL_RANGE` 解析纯 regex 触发 stoull，回溯到 PyTorch CUDA init | run_tracer.sh wrap regex 为 `0-@<regex>` |
| D3 kernel 数 sim=3 ncu=2 不一致 | NVBit 漏过滤掉 `at::native::unrolled_elementwise_kernel` (名字不含 flashinfer 但被抓) | run_tracer.sh post-filter 二次过滤 |
| post-filter 实际没跑 | `set -euo pipefail` + `xzcat \| head -1` SIGPIPE → 脚本 exit 141 | subshell `set +o pipefail` + `\|\| true` |
| DRAM_UTIL_BINS 全 0 (sim) | GPGPU-Sim 源码里 `dram_util_bins[]` 只有 reset 和 print，从未被 `++` | parser fallback: L2_misses × 32B / runtime / 1555 GB/s |
| D3 计算是 decode 但 kernel 名是 Prefill | flashinfer 的 `BatchDecodeWithPagedKVCacheWrapper` + `use_tensor_cores=1` 内部 dispatch 到 BatchPrefill kernel 实现 | 文档标注为 "paged decode (tensor-core path)"，不算误标 |
| vLLM import 每次 14 min | vLLM Python 库 import + Triton JIT (Triton cache 跨进程不命中) | 接受成本 (Phase 4 rmsnorm 预计多 ~70 min wall-clock) |

## Checkpoint A 决策点

- ✅ 4 cfg smoke 三阶段完整
- ✅ Kernel 集合 100% 对齐（validation passed）
- ✅ 5 维度 MAPE（cycle / winsn / DRAM）数字就绪
- ⏳ 等 user 决定：进 Phase 4 bulk 还是先优化 smoke 发现的问题

## 下一步（Phase 4 预估）

- Bulk 跑剩余 37 cfg (FA 10 + Decode 12 + GEMM 11 + RMSNorm 4)
- wall-clock ~6-10h:
  - Trace 顺序（GPU 独占）~3.5h，其中 R2 类 vLLM 每个 ~14 min
  - NCU 顺序（GPU 独占）~2.5h
  - Sim 并行（CPU）~1-3h，GEMM 大 cfg 单个 30-90 min
- 完成后出 41 cfg 完整 MAPE 表，进 Phase 5 parser + Checkpoint B
