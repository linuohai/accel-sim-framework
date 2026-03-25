# IMA Prefetch 研究计划总览

> 最后更新：2026-03-20
> 当前阶段：**Phase 2 / Phase 3 — 设计证据回填与预取方案收敛**
>
> 📌 快速了解研究全貌请先读 [`INDEX.md`](INDEX.md)（由 `/update-ima-index` 自动生成的各阶段状态、关键发现和目录摘要）

---

## 研究目标

在 GPU（Accel-Sim / GPGPU-Sim）上设计 **GRASP**（GPU Register-chain Aware Sector Prefetcher），针对 **IMA（Indirect Memory Access）** 的 hardware prefetcher，改善图负载（Gardenia/Rodinia）中因间接访存导致的 cache miss 与 stall 问题。**最终目标：投稿体系结构顶会/顶刊论文。**

> 论文标题：*GRASP: Grasping GPU Indirect Memory Patterns via ISA-Exposed Register-Chain Prefetching*

补充调研线：现代推荐 / embedding-heavy workload。当前仓库里这条线的可直接分析 baseline 是 Gardenia SGD；`mlperf` 和 `huggingface` 目录只作为入口和上游代码追踪线索，不直接等价于推荐系统 kernel。

## 核心方法论

```
IMA 特征化  →  确定性能天花板  →  调研已有方案  →  设计 prefetcher  →  实现 & 评估
   (Phase 1)      (Phase 2)        (Phase 2)        (Phase 3)        (Phase 4)
```

## 绝对规则 (Absolute Rules)

- **严格独立判断**：对于用户提出的方案或观点，必须首先基于客观的先验知识以及整个系统文档的现有资料，去判断其是否合理或正确。
- **拒绝盲从与迎合**：如果有需要修改甚至完全错误的地方，必须直接、明确地指出来，**绝对不允许顺着用户的错误想法去强行自圆其说**。

## 目录与写入规则

- 本研究计划相关的文档、分析脚本、中间结果、SASS、trace 汇总、图表、笔记，统一写入 `ima_plan/` 目录树下。
- 每个阶段的过程文件默认放在对应子目录中，例如 `ima_plan/01_ima_characterization/`、`ima_plan/03_performance_ceiling/`。
- 若任务需要在 `ima_plan/` 之外新增写入，必须先征求确认，再执行。

---

## 里程碑与阶段

| Phase | 名称 | 核心产出 | 状态 |
|-------|------|---------|------|
| 0 | 计划制定 | 本文档及子文档框架 | **进行中** |
| 1 | IMA 特征化 | IMA 分类体系 + 各 workload 微架构行为数据 | **进行中**（ima_high baseline L1 miss breakdown 已完成） |
| 2 | 天花板量化 & 相关工作 | ideal L1D 全 workload 数据 + 文献调研报告 | **部分完成**（ima_high 已有数据） |
| 3 | GRASP Prefetcher 设计 | GRASP 方案文档 + 覆盖分析 + 硬件预算 | **进行中**（`small_1sm_cta5` 时序校准已接入设计文档） |
| 4 | 实现与评估 | GPGPU-Sim 代码 + 完整评估数据 + 论文初稿 | 待开始 |

---

## 文档索引

| 文件 | 对应文件夹（存放中间结果） | 说明 |
|------|--------------------------|------|
| [01_ima_characterization.md](01_ima_characterization.md) | `ima_plan/01_ima_characterization/` | IMA 分类与微架构行为特征化 |
| [02_related_work.md](02_related_work.md) | `ima_plan/02_related_work/` | CPU/GPU prefetch 相关工作调研 |
| [03_performance_ceiling.md](03_performance_ceiling.md) | `ima_plan/03_performance_ceiling/` | Ideal L1D 上界实验 |
| [04_prefetcher_design.md](04_prefetcher_design.md) | `ima_plan/04_prefetcher_design/` | GRASP 方案设计 + small-case 时序证据回填 |
| [05_implementation.md](05_implementation.md) | `ima_plan/05_implementation/` | GPGPU-Sim 实现计划 |
| [06_evaluation_plan.md](06_evaluation_plan.md) | `ima_plan/06_evaluation_plan/` | 评估方案 |
| [07_paper_outline.md](07_paper_outline.md) | `ima_plan/07_paper_outline/` | 论文大纲 |

## GRASP 内部缩写速查

| 缩写 | 全称 | 作用 |
|------|------|------|
| `GRASP` | GPU Register-chain Aware Sector Prefetcher | 本工作的 GPU IMA 预取器总名，目标是在 L2→L1 路径上提前填充间接访问所需数据 |
| `CD` | Chain Detector | 在 issue/decode 阶段识别 `LDG→IMAD.WIDE→LDG` 依赖链，判断哪些 load 属于 IMA |
| `CT` | Chain Table | 记录每个 `index_load_PC` 对应的 data-side 依赖信息和 target 映射，是 IMA 链的主索引表 |
| `TT` | Target Table | 存储 target array 的 `base_addr` 与 `scale`，供 data 地址计算使用 |
| `IPU` | Index Prefetch Unit | 在 index load 发出时，根据 `iter_stride` 提前发出下一轮 index prefetch |
| `DPU` | Data Prefetch Unit | 在 index prefetch 返回后，根据 index 值生成 `A[B[i]]` 的 data prefetch 请求 |
| `PRB` | Prefetch Request Buffer | 跟踪在途 index prefetch，请求返回前保存目标 target 信息与完成进度 |
| `ACU` | Address Computation Unit | 将返回的 index 值转换为 `base + value × scale` 形式的 data 地址 |

## 最新产出

- [ima_high baseline L1 miss breakdown](01_ima_characterization/l1_miss_breakdown/analysis.md)：基于 SASS + baseline L1 trace 的四类 load 统计，输出汇总表、热点 PC 表和跨 workload 总览图。
- [03_performance_ceiling.md](03_performance_ceiling.md)：作为 motivation/background 页面，承接 ideal L1D 上界、L1/L2 hit-rate 不对称，以及为何继续做按 load 类型的 miss 归因。
- [small_1sm_cta5 design evidence](04_prefetcher_design/extra_pattern/small_1sm_cta5/prefetch_design_summary_lrr.md)：基于 `1SM + CTA5 + lrr` 代表窗口恢复 IMA 链级时延与 index-vs-data 压力，用于修正设计文档中早期固定 `~200 / ~400 cycles` 的时序估计；这些结果仅作为 small-case 参考，不直接外推到 full-scale workload。

## 工作负载速查

### Gardenia（主要）

| 算法 | IMA 模式 | 关键 trace key |
|------|---------|---------------|
| BFS | `dists[column_indices[offset]]` frontier-driven | `bfs_ima_high/med/small` |
| SSSP | `dist[column_indices[offset]]` + weight | `sssp_ima_high/med/small` |
| BC | `sigma/delta[neighbor]` 双向遍历 | `bc_ima_high/med/small` |
| SpMV | `x[Aj[offset]]` gather | `spmv_ima_high/small` |
| CC | `comp[neighbor]` union-find 迭代 | `cc_ima_high/med/small` |

### Rodinia（补充基线）

| 算法 | IMA 模式 | 特点 |
|------|---------|------|
| B+Tree | pointer chasing + `records[idx]` | 串行依赖链 |

### 现代推荐 / Embedding（补充调研线）

| 入口 | IMA 模式 | 说明 |
|------|---------|------|
| Gardenia SGD | `column_indices[offset]` 驱动的 latent vector lookup | 当前仓库内最清晰的推荐系统 CUDA baseline |
| `mlperf` / 上游模型 | sparse ID lookup / embedding gather | 作为现代推荐 / embedding 代码线索，需继续追到具体 kernel |

## 实验基础设施

- **模拟器**：Accel-Sim / GPGPU-Sim（`gpu-simulator/`）
- **默认配置**：SM80_A100
- **实验入口**：`./traceL1 <trace_key> [log_name]`
- **已有自定义功能**：ideal L1D、L1/L2 trace、issue trace（含 stall 归因）、HBM 带宽 trace
- **绘图**：`result/plot/run_plots.sh --log-name <log_name>`
