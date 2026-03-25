# 仿真加速研究总结

> 日期：2026-03-25
> 目的：探索加速 ima_high workload 仿真的可行方案，为论文评估阶段的实验规划提供依据

---

## 1. 背景

GRASP prefetcher 评估需要在 ima_high workload（cit-Patents 图，~3.5M 边）上运行 baseline + GRASP 对比实验。当前完整运行每个 workload 耗时 5–25 小时，全套 5 个 workload × 2 配置串行需要 ~130 小时。

机器配置：128 核 Intel Xeon 8336C (AVX-512, Ice Lake) + 2TB RAM。每次仿真单线程。

## 2. 已尝试的加速策略及结论

### 2.1 编译优化：`-march=native` + LTO（已落地）

修改 `gpu-simulator/CMakeLists.txt` 和 `gpu-simulator/gpgpu-sim/CMakeLists.txt`，添加 `-march=native`（启用 AVX-512）和 `CMAKE_INTERPROCEDURAL_OPTIMIZATION`（LTO）。

**验证结果**（spmv_ima_high, 1SM, 200 CTA）：

| 指标 | 旧二进制 | 新二进制 | 变化 |
|------|---------|---------|------|
| gpu_tot_sim_cycle | 574,370 | 574,370 | 完全一致 |
| gpu_tot_ipc | 5.0236 | 5.0236 | 完全一致 |
| simulation_rate | 24,972 cycle/sec | 28,718 cycle/sec | **+15%** |

结论：IPC 完全不变，模拟速率提升 15%。零精度损失。

### 2.2 1SM 配置 vs 108SM（不显著加速）

| 配置 | BFS ima_high 总 cycle | 模拟速率 | Wall time |
|------|----------------------|---------|-----------|
| 108SM (SM80_A100) | 5.36M | 335 cycle/sec | ~4.4h |
| 1SM (SM80_A100_1SM) | 364M | 26,000 cycle/sec | ~3.9h |

**关键发现**：1SM 每 cycle 模拟快 77x，但总 cycle 数多 68x。两者相消，wall time 几乎相同。

原因：108SM 上 CTA 并行执行（GPU cycle 少但每 cycle 主机计算量大）；1SM 上 CTA 串行执行（每 cycle 主机计算量小但 GPU cycle 数量极大）。

### 2.3 `--max-completed-cta` 限制（不适用于多 kernel 工作负载）

| 配置 | CC 1SM 500 CTA | CC 1SM 全量 |
|------|---------------|------------|
| IPC | 3.60 | 1.75 |
| Cycles | 2.8M | 375M+ |

| 配置 | SpMV 108SM 100 CTA | SpMV 108SM 全量 |
|------|-------------------|----------------|
| IPC | 557.73 | 374.57 |
| Cycles | 22K | 1.07M |

**关键发现**：IPC 随 CTA 增加**不收敛**，差异可达 33%–100%。原因：
1. 多 kernel 工作负载（BFS/SSSP/BC/CC）：不同 kernel 的 CTA 数和工作量差异大，CTA 限制只跑到前几个 kernel
2. 图算法局部性变化：早期迭代 cache 友好，后期随机性增大
3. Cache contention：CTA 越多，L1/L2 竞争越激烈

结论：**`--max-completed-cta` 不适合作为论文评估的加速手段**，会导致结果不具代表性。

### 2.4 关闭 trace 输出（推荐用于纯 IPC 评估）

在纯 IPC 评估时，可关闭所有 trace 输出节省 10–20% 时间：

```bash
EVAL_FLAGS="--no-l1-trace --no-l2-trace --no-hbm-trace --no-stall-reason-pc-stats --no-issue-trace"
```

注意：需要 L1/cache 详细分析时不能关闭 L1 trace。

### 2.5 PGO（未成功）

因 CMakeLists.txt 中 `set()` 覆盖了命令行 `-D` cache 变量，`-fprofile-generate` 未生效。需要临时修改 CMakeLists.txt 才能使用，暂未实施。预估额外加速 10–20%。

## 3. 实际可行的加速组合

| 策略 | 加速效果 | 已落地 |
|------|---------|--------|
| `-march=native` + LTO | +15% | ✅ |
| 关闭 trace 输出 | +10–20% | 运行时参数 |
| 并行执行 5 workload | wall time 取最慢 | ✅ |
| **复合效果** | 每个 run 快 ~25–35%；全套 wall time = 最慢 workload 时间 | — |

## 4. 论文评估的推荐实验方案

鉴于 CTA 限制和 1SM 配置均不能显著加速且影响精度，推荐：

1. **使用 108SM 配置**（与实际 A100 对应，论文可信度高）
2. **完整运行所有 CTA**（不使用 `--max-completed-cta`）
3. **5 个 workload 并行跑**（每个占 1 个 CPU 核，机器有 128 核）
4. **Baseline + GRASP 同时跑**（总共 10 个进程并行）
5. **纯 IPC 评估时关闭 trace 输出**
6. **预期总 wall time**：最慢 workload ~15–20h（如 bc/cc），隔夜跑完

### 批量运行脚本

已创建 `scripts/run_grasp_eval.sh`，用法：

```bash
# 108SM 全量评估（论文最终数据，隔夜运行）
./scripts/run_grasp_eval.sh --full --config SM80_A100

# 可自定义 GRASP 参数
./scripts/run_grasp_eval.sh --full --config SM80_A100 \
    --grasp-args "--grasp --grasp-distance 4 --grasp-chain-csv /path/to/csv"
```

## 5. 配套工具

| 文件 | 用途 |
|------|------|
| `scripts/run_grasp_eval.sh` | 批量评估入口，并行跑 baseline + GRASP |
| `scripts/cta_convergence_sweep.sh` | CTA 收敛校准（已验证：对多 kernel 不适用） |
| `scripts/analyze_cta_convergence.py` | 收敛分析 + 可视化 |

## 6. 变更记录

| 文件 | 变更 |
|------|------|
| `gpu-simulator/CMakeLists.txt` | 添加 `-march=native`, `CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE` |
| `gpu-simulator/gpgpu-sim/CMakeLists.txt` | 同上（CXX + C flags） |
