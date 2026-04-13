# Benchmark Suite — IMA Prefetcher 评估测例

> 最近更新: 2026-04-07

---

## **>>> 论文最终评估范围（Paper Evaluation Scope）<<<**

> **本节是论文写作和图表绘制的唯一权威依据。**
> 下方「初始设计」部分为实验早期的完整设计，随着实验推进已有调整。
> 当两者冲突时，以本节为准。
> 最近更新: 2026-04-07

### 总体范围

| 类别 | 算法 | Workloads | 说明 |
|------|------|:---------:|------|
| **核心实验（Gardenia）** | BFS, SSSP, BC, CC, SpMV, VC | 38 | 6 算法 × 5 数据集，含 dir+sym 双变体 |
| **扩展实验** | MIS, Color, MST | 3 | Pannotia (MIS, Color) + LonestarGPU (MST) |
| **合计** | 9 | **41** | |

> 扩展实验的目的是证明 GRASP 跨 benchmark suite 的泛化性（引用覆盖 Gardenia + Pannotia + LonestarGPU）。

### 选优后论文主表（28 workloads）

双变体选优规则：cit-Patents 选 dir（Speedup 更高），其余选 sym。选优后 25 Gardenia + 3 Extended = 28。

| # | Key | 算法 | 来源 | 数据集 | GRASP TC 配置 | GRASP 数据源 |
|--:|-----|------|------|--------|:------------:|-------------|
| 1 | `bfs_cit_dir` | BFS | Gardenia | cit-Patents | D5b | `throttle_control_results.md` |
| 2 | `sssp_cit_dir` | SSSP | Gardenia | cit-Patents | D5b | `throttle_control_results.md` |
| 3 | `bc_cit_dir` | BC | Gardenia | cit-Patents | D5b | `throttle_control_results.md` |
| 4 | `cc_cit_sym` | CC | Gardenia | cit-Patents | D5b | `throttle_control_results.md` |
| 5 | `spmv_cit_sym` | SpMV | Gardenia | cit-Patents | D5b | `throttle_control_results.md` |
| 6 | `vc_cit_sym` | VC | Gardenia | cit-Patents | D5b | `throttle_control_results.md` |
| 7 | `bfs_web_sym` | BFS | Gardenia | web-Google | D5b | `throttle_control_results.md` |
| 8 | `sssp_web_sym` | SSSP | Gardenia | web-Google | D5b | `throttle_control_results.md` |
| 9 | `bc_web_sym` | BC | Gardenia | web-Google | D5b | `throttle_control_results.md` |
| 10 | `cc_web_sym` | CC | Gardenia | web-Google | D5b | `throttle_control_results.md` |
| 11 | `spmv_web_sym` | SpMV | Gardenia | web-Google | D5b | `throttle_control_results.md` |
| 12 | `vc_web_sym` | VC | Gardenia | web-Google | D5b | `throttle_control_results.md` |
| 13 | `bfs_flickr_sym` | BFS | Gardenia | flickr | D5b | `throttle_control_results.md` |
| 14 | `sssp_flickr_sym` | SSSP | Gardenia | flickr | D5b | `throttle_control_results.md` |
| 15 | `bc_flickr_sym` | BC | Gardenia | flickr | D5b | `throttle_control_results.md` |
| 16 | `cc_flickr_sym` | CC | Gardenia | flickr | D5b | `throttle_control_results.md` |
| 17 | `spmv_flickr_sym` | SpMV | Gardenia | flickr | D5b | `throttle_control_results.md` |
| 18 | `bfs_road_sym` | BFS | Gardenia | roadNet-CA | D5b | `throttle_control_results.md` |
| 19 | `sssp_road_sym` | SSSP | Gardenia | roadNet-CA | D5b | `throttle_control_results.md` |
| 20 | `bc_road_sym` | BC | Gardenia | roadNet-CA | D5b | `throttle_control_results.md` |
| 21 | `cc_road_sym` | CC | Gardenia | roadNet-CA | D5b | `throttle_control_results.md` |
| 22 | `spmv_road_sym` | SpMV | Gardenia | roadNet-CA | D5b | `throttle_control_results.md` |
| 23 | `vc_road_sym` | VC | Gardenia | roadNet-CA | D5b | `throttle_control_results.md` |
| 24 | `bfs_socLJ_sym` | BFS | Gardenia | soc-LJ1 | ⏳ Default→D5b | `experiment_results.md`（D5b 仿真中，完成后替换） |
| 25 | `spmv_socLJ_sym` | SpMV | Gardenia | soc-LJ1 | ⏳ Default→D5b | `experiment_results.md`（D5b 仿真中，完成后替换） |
| 26 | `pann_mis_flickr` | MIS | Pannotia | flickr | Default | `extra_case/extra_case_results.csv` |
| 27 | `pann_color_eco` | Color | Pannotia | ecology1 | Default | `extra_case/extra_case_results.csv` |
| 28 | `ls_mst_rmat12` | MST | LonestarGPU | rmat12 | Default | `extra_case/extra_case_results.csv` |

> soc-LJ1 两个 workload 目前使用 Default 配置结果（与 D5b 差异预计 <1pp），D5b 仿真完成后替换。

### 各实验类型 Workloads 与数据源

#### L1: 主性能评估（Speedup 表）

**范围**: 28 workloads（上表全部）
**展示指标**: Baseline IPC, GRASP IPC, Speedup%, Ideal IPC, Headroom%

| 子集 | Workloads | Baseline 数据源 | GRASP 数据源 | Ideal L1D 数据源 |
|------|:---------:|----------------|-------------|-----------------|
| Gardenia 23 (D5b) | 23 | `throttle_control_results.md` | `throttle_control_results.md` (D5b) | `experiment_results.md` |
| Gardenia soc-LJ1 | 2 | `experiment_results.md` | `experiment_results.md` (Default ⏳) | `experiment_results.md` |
| Extended MIS + Color | 2 | `extra_case/extra_case_results.csv` | `extra_case/extra_case_results.csv` | 无（未跑 ideal L1D） |
| Extended MST | 1 | `extra_case/extra_case_results.csv` | `extra_case/extra_case_results.csv` | 无 |

**Extended Log 文件**:

| Key | Baseline Log | GRASP Log |
|-----|-------------|-----------|
| `pann_mis_flickr` | `pann_mis_flickr_baseline.log` | `pann_mis_flickr_grasp2.log` |
| `pann_color_eco` | `pann_color_eco_baseline.log` | `pann_color_eco_grasp.log` |
| `ls_mst_rmat12` | `ls_mst_rmat12_baseline.log` | `ls_mst_rmat12_grasp.log` |

#### L2: Prefetch 有效性（Coverage / Timeliness / Accuracy）

**范围**: 27 workloads（28 − MST）
**排除 MST 原因**: rmat12 数据集上目标 kernel 未执行，0 prefetch 活动，无有效指标
**展示指标**: Idx/Data Coverage%, Idx/Data Timeliness%, Accuracy%
**数据源**: 同 L1，从对应 GRASP log 中 `IMA_DEMAND:` / `IMA_TIMELINESS:` / `GRASP_EFFECT` 提取

#### L3: SOTA Baseline 对比

**范围**: 25 Gardenia + 3 Extended = 28 workloads × 3 baselines = 84 实验
**Baselines**: Snake (MICRO'23), CAPS (IPDPS'18), Spare Register (HPCA'14)
**展示指标**: Speedup%, Accuracy%, Coverage%
**数据源**: `05_implementation/sota_baseline/sota_experiment_results.md`

> 3 个 Extended 测例的 SOTA 数据已包含在该文件 "Extended Benchmarks" 章节中。

#### L4: 组件消融（Exp-A: Index-Only / Data-Only / Full）

**范围**: 20 Gardenia workloads（仅核心实验）

```
bfs_cit_dir  sssp_cit_dir  bc_cit_dir  spmv_web_sym  bfs_web_sym
cc_flickr_sym  spmv_flickr_sym  bfs_flickr_sym
bfs_road_sym  sssp_road_sym  cc_road_sym  bc_road_sym
sssp_flickr_sym  sssp_web_sym  vc_web_sym  spmv_cit_sym
bc_flickr_sym  bc_web_sym  vc_cit_sym  cc_web_sym
```

**配置**: Baseline / Index-Only / Data-Only / Full GRASP (D5b)
**展示指标**: Speedup%（grouped bar chart）
**数据源**: `06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md` §Exp-A

#### L5: 节流消融（Exp-B: Throttle Control）

**范围**: 22 Gardenia workloads（同 L4 + vc_road_sym + spmv_road_sym）
**配置**: Default (tc_mode=0) / D5b (论文版, tc_mode=5) / T40C200 (tc_mode=4)
**展示指标**: Speedup% + Accuracy% + Data Coverage%
**数据源**: `06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md` §Exp-B
  + `throttle_control_results.md`（D5b / T40C200 原始数据）

#### L6: 预取距离敏感性（Exp-C: Distance = 1, 2, 4, 8）

**范围**: 20 Gardenia workloads（同 L4）
**展示指标**: Speedup%（折线图, x=distance）
**数据源**: `06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md` §Exp-C

#### L7: 存储预算敏感性（Exp-D: S1~S4）

**范围**: 20 Gardenia workloads（同 L4）
**配置**: S1(712B/0.54%L1D) / S2(1.1KB) / S3(1.9KB) / S4(3.6KB)
**展示指标**: Speedup%（grouped bar chart + 面积标注）
**数据源**: `06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md` §Exp-D

#### L8: 有效性分解（Exp-E: Miss Reduction + Pipeline Funnel）

**范围**: 8 Gardenia workloads（代表子集）

```
bfs_cit_dir  sssp_cit_dir  bc_cit_dir  spmv_web_sym
bfs_web_sym  cc_flickr_sym  spmv_flickr_sym  bfs_flickr_sym
```

**展示指标**: IMA Miss Reduction%, CT Entry 复用率, Pipeline 转化率
**数据源**: `06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md` §Exp-E
  （从已有 baseline + D5b log 提取，无需额外仿真）

### 非选优变体（补充数据，13 workloads）

不进入论文主表，但可用于附录或补充分析。全部使用 Default 配置。

| # | Key | 算法 | 数据集 | 数据源 |
|--:|-----|------|--------|--------|
| 1 | `bfs_cit_sym` | BFS | cit-Patents | `experiment_results.md` |
| 2 | `sssp_cit_sym` | SSSP | cit-Patents | `experiment_results.md` |
| 3 | `bc_cit_sym` | BC | cit-Patents | `experiment_results.md` |
| 4 | `bfs_web_dir` | BFS | web-Google | `experiment_results.md` |
| 5 | `sssp_web_dir` | SSSP | web-Google | `experiment_results.md` |
| 6 | `bc_web_dir` | BC | web-Google | `experiment_results.md` |
| 7 | `bfs_flickr_dir` | BFS | flickr | `experiment_results.md` |
| 8 | `sssp_flickr_dir` | SSSP | flickr | `experiment_results.md` |
| 9 | `bc_flickr_dir` | BC | flickr | `experiment_results.md` |
| 10 | `bfs_road_dir` | BFS | roadNet-CA | `experiment_results.md` |
| 11 | `sssp_road_dir` | SSSP | roadNet-CA | `experiment_results.md` |
| 12 | `bc_road_dir` | BC | roadNet-CA | `experiment_results.md` |
| 13 | `bfs_socLJ_dir` | BFS | soc-LJ1 | `experiment_results.md` |

### 数据文件索引

| 文件 | 相对路径 | 内容 | Workloads |
|------|---------|------|:---------:|
| **Throttle Control 结果** | `06_evaluation_plan/throttle_control_results.md` | D5b + T40C200 全指标 | 23 Gardenia |
| **全量实验结果** | `06_evaluation_plan/experiment_results.md` | Default 全指标 + Ideal L1D | 38 Gardenia |
| **扩展测例结果** | `06_evaluation_plan/extra_case/extra_case_results.csv` | Extended 全指标 | 3 Extended |
| **扩展测例说明** | `06_evaluation_plan/extra_case/README.md` | Bug fix + 0pf 分析 | — |
| **SOTA Baseline** | `05_implementation/sota_baseline/sota_experiment_results.md` | 3 baselines × 28 workloads | 28 |
| **敏感性 + 消融** | `06_evaluation_plan/sensitivity_ablation/sensitivity_ablation_experiments.md` | Exp-A~E, 186 次仿真 | 8~22 Gardenia |
| **Golden Chain CSV** | `05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv` | 205 chains（全算法） | — |
| **Baseline Registry** | `06_evaluation_plan/baseline_registry.csv` | 避免重跑 baseline | — |
| **Log 文件目录** | `result/log/` | 全部仿真 log | — |

### 待办

- [ ] `bfs_socLJ_sym` / `spmv_socLJ_sym` D5b 仿真完成后，将数据从 `experiment_results.md` 替换为 D5b 结果，并更新 `throttle_control_results.md`

---
---

## 以下为初始设计（历史参考）

> **注意**: 以下内容是实验初期的完整设计方案。随着实验推进，部分内容已被上方「论文最终评估范围」调整和覆盖。
> 保留此部分用于追溯设计决策和参考算法/数据集的详细说明。
> **当两者冲突时，以上方 Paper Evaluation Scope 为准。**

> 各 trace key 定义于 `traceL1` 脚本的 `TRACE_MAP`。

## 测例总览（38 个 Workload）

| # | Workload Key | 算法 | 数据集 | Sym |
|--:|-------------|------|--------|:---:|
| 1 | `bfs_cit_dir` | BFS | cit-Patents | 0 |
| 2 | `bfs_cit_sym` | BFS | cit-Patents | 1 |
| 3 | `sssp_cit_dir` | SSSP | cit-Patents | 0 |
| 4 | `sssp_cit_sym` | SSSP | cit-Patents | 1 |
| 5 | `bc_cit_dir` | BC | cit-Patents | 0 |
| 6 | `bc_cit_sym` | BC | cit-Patents | 1 |
| 7 | `cc_cit_sym` | CC | cit-Patents | 1 |
| 8 | `spmv_cit_sym` | SpMV | cit-Patents | 1 |
| 9 | `vc_cit_sym` | VC | cit-Patents | 1 |
| 10 | `bfs_web_dir` | BFS | web-Google | 0 |
| 11 | `bfs_web_sym` | BFS | web-Google | 1 |
| 12 | `sssp_web_dir` | SSSP | web-Google | 0 |
| 13 | `sssp_web_sym` | SSSP | web-Google | 1 |
| 14 | `bc_web_dir` | BC | web-Google | 0 |
| 15 | `bc_web_sym` | BC | web-Google | 1 |
| 16 | `cc_web_sym` | CC | web-Google | 1 |
| 17 | `spmv_web_sym` | SpMV | web-Google | 1 |
| 18 | `vc_web_sym` | VC | web-Google | 1 |
| 19 | `bfs_flickr_dir` | BFS | flickr | 0 |
| 20 | `bfs_flickr_sym` | BFS | flickr | 1 |
| 21 | `sssp_flickr_dir` | SSSP | flickr | 0 |
| 22 | `sssp_flickr_sym` | SSSP | flickr | 1 |
| 23 | `bc_flickr_dir` | BC | flickr | 0 |
| 24 | `bc_flickr_sym` | BC | flickr | 1 |
| 25 | `cc_flickr_sym` | CC | flickr | 1 |
| 26 | `spmv_flickr_sym` | SpMV | flickr | 1 |
| 27 | `bfs_road_dir` | BFS | roadNet-CA | 0 |
| 28 | `bfs_road_sym` | BFS | roadNet-CA | 1 |
| 29 | `sssp_road_dir` | SSSP | roadNet-CA | 0 |
| 30 | `sssp_road_sym` | SSSP | roadNet-CA | 1 |
| 31 | `bc_road_dir` | BC | roadNet-CA | 0 |
| 32 | `bc_road_sym` | BC | roadNet-CA | 1 |
| 33 | `cc_road_sym` | CC | roadNet-CA | 1 |
| 34 | `spmv_road_sym` | SpMV | roadNet-CA | 1 |
| 35 | `vc_road_sym` | VC | roadNet-CA | 1 |
| 36 | `bfs_socLJ_dir` | BFS | soc-LJ1 | 0 |
| 37 | `bfs_socLJ_sym` | BFS | soc-LJ1 | 1 |
| 38 | `spmv_socLJ_sym` | SpMV | soc-LJ1 | 1 |

> **分布**: cit-Patents 9 | web-Google 9 | flickr 8（无 VC） | roadNet-CA 9 | soc-LJ1 3
> **缺失**: VC-flickr/soc-LJ1 因 MAXCOLOR=128 crash 排除

---

## 图输入数据集（4 类 + 1 扩展）

| 类别 | 数据集 | |V| | |E| (directed) | |E| (sym) | 来源 |
|------|--------|-----|-----------|---------|------|
| 引文网络 | **cit-Patents** | 3.77M | 16.5M | ~33M | SNAP |
| 网页链接 | **web-Google** | 916K | 5.1M | ~8.6M | SNAP |
| 社交网络 | **flickr** | 821K | 9.8M | ~19.6M | NetworkRepository |
| 道路网络 | **roadNet-CA** | 1.97M | 2.8M | 2.8M | SNAP/DIMACS |
| 大社交（扩展） | **soc-LiveJournal1** | 4.85M | 69M | ~138M | SNAP |

### Source 顶点（BFS / SSSP / BC 使用）

| 数据集 | Hub (directed, sym=0) | Hub (symmetric, sym=1) |
|--------|----------------------|----------------------|
| cit-Patents | v=3569341 (out-deg=770) | v=3569341 |
| web-Google | v=506742 (out-deg=456) | v=506742 |
| flickr | v=1586 (out-deg=10272) | v=1586 (sym-deg=14902) |
| roadNet-CA | v=117563 (out-deg=6) | v=562818 (sym-deg=12) |
| soc-LiveJournal1 | v=10009 (out-deg=20292) | v=10009 (sym-deg=22887) |

> Source 选择依据见 `datasets/real_workload/IMA_source_selection.md`。

---

## 算法（6 个）

### Directed / Undirected 兼容性（A100 真机验证）

| 算法 | sym=0 (directed) | sym=1 (undirected) | IMA Chains | 变体策略 |
|------|:-:|:-:|:-:|------|
| **BFS** | ✅ Correct | ✅ Correct | 7 | 双变体选优 |
| **SSSP** | ✅ Correct | ✅ Correct | 7 | 双变体选优 |
| **BC** | ✅ Correct | ✅ Correct | 19 | 双变体选优 |
| **CC** | ❌ Wrong | ✅ Correct | 6 | 仅 sym=1 |
| **SpMV** | ❌ Crash | ✅ Correct | 29 | 仅 sym=1 |
| **VC** | ❌ Wrong | ✅ Correct | 34 | 仅 sym=1 |

**双变体选优**：BFS / SSSP / BC 在每个数据集上同时跑 sym=0 和 sym=1 baseline，选 ideal L1D 加速更高的变体进入论文。

**仅 sym=1**：CC / SpMV / VC 在 directed 图上产生错误结果或崩溃，只能使用 sym=1。
- SpMV crash 原因：`spmv_base` 使用 `in_rowptr`（CSC），directed 图不构建 reverse → invalid argument
- CC/VC Wrong 原因：算法逻辑依赖双向邻居关系

### MAXCOLOR=128 限制（VC）

`common.h:65` 硬编码 `#define MAXCOLOR 128`。高度数数据集上 VC 的顶点着色预处理触发 assert：

| 数据集 | Max Coloring | VC 状态 |
|--------|:-:|------|
| cit-Patents | 17 色 | ✅ 正常 |
| web-Google | 45 色 | ✅ 正常 |
| roadNet-CA | 5 色 | ✅ 正常 |
| flickr | >128 色 | ❌ CRASH（hub deg=14902） |
| soc-LiveJournal1 | >128 色 | ❌ CRASH（hub deg=22887） |

**结论**：VC 仅能在 cit-Patents、web-Google、roadNet-CA 上评估（3 个数据集）。

---

## 完整测例矩阵

### 双变体算法 × 4 基础数据集（选优阶段跑 sym=0 + sym=1）

| 算法 | cit-Patents | web-Google | flickr | roadNet-CA |
|------|:-:|:-:|:-:|:-:|
| **BFS** | `bfs_cit_dir` / `bfs_cit_sym` | `bfs_web_dir` / `bfs_web_sym` | `bfs_flickr_dir` / `bfs_flickr_sym` | `bfs_road_dir` / `bfs_road_sym` |
| **SSSP** | `sssp_cit_dir` / `sssp_cit_sym` | `sssp_web_dir` / `sssp_web_sym` | `sssp_flickr_dir` / `sssp_flickr_sym` | `sssp_road_dir` / `sssp_road_sym` |
| **BC** | `bc_cit_dir` / `bc_cit_sym` | `bc_web_dir` / `bc_web_sym` | `bc_flickr_dir` / `bc_flickr_sym` | `bc_road_dir` / `bc_road_sym` |

### 仅 sym=1 算法

| 算法 | cit-Patents | web-Google | flickr | roadNet-CA |
|------|:-:|:-:|:-:|:-:|
| **CC** | `cc_cit_sym` | `cc_web_sym` | `cc_flickr_sym` | `cc_road_sym` |
| **SpMV** | `spmv_cit_sym` | `spmv_web_sym` | `spmv_flickr_sym` | `spmv_road_sym` |
| **VC** | `vc_cit_sym` | `vc_web_sym` | ❌ MAXCOLOR | `vc_road_sym` |

### soc-LiveJournal1 扩展（仅快速算法）

| 算法 | sym=0 | sym=1 | 变体 |
|------|:-:|:-:|------|
| **BFS** | `bfs_socLJ_dir` | `bfs_socLJ_sym` | 双变体选优 |
| **SpMV** | — | `spmv_socLJ_sym` | 仅 sym=1 |

### 快速引用（用于批量脚本）

```bash
# 双变体算法 — directed 变体
DUAL_DIR="bfs_cit_dir sssp_cit_dir bc_cit_dir \
          bfs_web_dir sssp_web_dir bc_web_dir \
          bfs_flickr_dir sssp_flickr_dir bc_flickr_dir \
          bfs_road_dir sssp_road_dir bc_road_dir"

# 双变体算法 — symmetric 变体
DUAL_SYM="bfs_cit_sym sssp_cit_sym bc_cit_sym \
          bfs_web_sym sssp_web_sym bc_web_sym \
          bfs_flickr_sym sssp_flickr_sym bc_flickr_sym \
          bfs_road_sym sssp_road_sym bc_road_sym"

# 仅 sym=1 算法
SYM_ONLY="cc_cit_sym cc_web_sym cc_flickr_sym cc_road_sym \
          spmv_cit_sym spmv_web_sym spmv_flickr_sym spmv_road_sym \
          vc_cit_sym vc_web_sym vc_road_sym"

# soc-LiveJournal1 扩展
SOCLJ="bfs_socLJ_dir bfs_socLJ_sym spmv_socLJ_sym"

# 全部
ALL_WORKLOADS="$DUAL_DIR $DUAL_SYM $SYM_ONLY $SOCLJ"
```

### Workload 数量

| 类别 | Workload 数 |
|------|:-:|
| 双变体选优（3 algo × 4 ds × 2 sym） | 24 |
| 仅 sym=1（3 algo × 4 ds，减 VC-flickr） | 11 |
| soc-LJ1 扩展 | 3 |
| **合计** | **38** |

### 迭代分层策略

| 层级 | Workload 数 | 用途 | 并行关键路径 |
|------|:-:|------|:-:|
| **快速迭代（常规）** | 22 | 参数调优、代码改动验证 | ~12h (cc_web_sym) |
| **完整评估** | 25 | 里程碑版本、论文数据 | ~31h (cc_cit_sym) |

**快速迭代排除项（3 个）：**
- `cc_cit_sym`：GRASP -7.0% 退化 + 30.9h（关键路径瓶颈）
- `bfs_socLJ_sym` / `spmv_socLJ_sym`：各 ~17h，仅在重大改动时跑

**双变体选优结果（基于 GRASP speedup）：**
- cit-Patents → dir（BFS +13.6%, SSSP +11.0%, BC +9.8%）
- web-Google / flickr / roadNet-CA / soc-LJ1 → sym

---

## 各实验类型须覆盖的测例

| 实验类型 | 覆盖范围 | 说明 |
|----------|---------|------|
| Baseline (no prefetch) | 全部 44 workloads | 基准 IPC / miss rate / stall |
| Ideal L1D 上界（仅 load） | 全部 44 workloads | 性能天花板（`--ideal-l1d`，仅对 load 生效） |
| 选优决定 | 双变体的 30 workloads | 选 ideal L1D 加速更高的 sym 变体 |
| GRASP Prefetcher | 选定的 ~24 workloads | 主实验 |
| SOTA 对比 | 选定的 cit-Patents workloads | 高 IMA 下与已有方案对比 |
| Ablation Study | 选定的 cit-Patents workloads | 消融实验 |
| Sensitivity Study | 选 3-4 个代表 | 参数扫描 |

---

## Trace 输出策略

> **原则：** 基础实验不输出 trace CSV；需要 trace 分析时必须开启压缩。

| 场景 | trace 开关 | 理由 |
|------|-----------|------|
| Baseline / Ideal L1D / SOTA 对比 | `--no-l1-trace --no-l2-trace --no-hbm-trace` | 只需 log 中的 IPC / miss rate，不需要 CSV |
| Prefetcher 调试（需看 cache 行为） | 开启 L1/L2 trace + `--issue-trace-compress gzip` | 需要逐访问分析 |
| 大规模实验（≥ 5 个测例并行） | 必须关闭 trace 或开启压缩 | 单个 L1 trace 可达 19 GB，并行写入易触发 OOM |

**典型命令：**
```bash
# 基础实验（推荐）
./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace bfs_flickr_sym bfs_flickr_sym_baseline

# 需要 trace 分析时
./traceL1 --issue-trace-compress gzip bfs_flickr_sym bfs_flickr_sym_trace
```

---

## Ideal L1D 说明

Ideal L1D（`--ideal-l1d` / `-gpgpu_perfect_l1d 1`）仅对 **load（GLOBAL_ACC_R / LOCAL_ACC_R）** 强制 L1D HIT，store 走正常 cache 路径。

> 修改于 2026-03-31（`gpu-cache.cc:2075-2077`）。原实现同时对 read + write 强制 HIT，现已限定为仅 load，因 GRASP 仅 prefetch load，load-only ideal 给出更准确的 prefetch-addressable 上界。

---

## 算法概述与应用场景

> Chain 数据来源：golden chain CSV (`ima_pair_table/golden/strict_selected_chain_instances.csv`)
> 2026-03-31 已合并 CC/VC/SymGS chains，共 105 chains

| 算法 | IMA Chains | 数据结构 | 访问模式 |
|------|:---------:|---------|---------|
| BFS | 7 | CSR 图 | `col_idx[rowptr[v]]` — frontier-driven 邻居遍历 |
| SSSP | 7 | CSR 加权图 | `col_idx[rowptr[v]]` + `weight[e]` — Bellman-Ford relax |
| BC | 19 | CSR 图 | forward BFS + reverse 依赖传播，2 个 kernel 各有独立 chain |
| CC | 6 | CSR 图 | `hook` + `shortcut` — Shiloach-Vishkin 并查集操作 |
| SpMV | 29 | CSR 稀疏矩阵 | `val[j] * x[col_idx[j]]` — 循环展开产生 29 条 chain |
| VC | 34 | CSR 图 | `first_fit` 贪心着色 + `conflict_resolve` 冲突修复 |

### 各算法的典型应用

| 算法 | 全称 | 典型应用场景 |
|------|------|-------------|
| **BFS** | Breadth-First Search | 社交网络好友距离（LinkedIn）、网页爬虫调度、网络拓扑层级发现 |
| **SSSP** | Single-Source Shortest Path | 导航路径规划（Google Maps）、网络路由协议（OSPF/IS-IS）、物流配送优化 |
| **BC** | Betweenness Centrality | 社交网络关键节点识别（意见领袖检测）、通信网络脆弱性分析、交通枢纽重要度评估 |
| **CC** | Connected Components | 图聚类与社区发现、图像分割（像素连通域）、网络故障域隔离 |
| **SpMV** | Sparse Matrix-Vector Multiply | 科学计算迭代求解器（CFD/FEM）、PageRank 底层内核、推荐系统矩阵分解 |
| **VC** | Vertex Coloring | 并行计算任务调度（避免冲突着色）、编译器寄存器分配、无线网络频谱分配 |
### 算法分类

从 IMA 模式的角度，6 个算法可归为三类：

1. **图遍历类**（BFS, SSSP, BC, CC）：基于 CSR `rowptr → col_idx` 的邻居访问，IMA chain 直接对应图的邻接表遍历。BFS/SSSP/BC 为 frontier-driven（活跃集驱动），CC 为全图迭代
2. **稀疏线性代数类**（SpMV）：基于 CSR `rowptr → col_idx → value` 的矩阵-向量操作
3. **图着色类**（VC）：基于 CSR 邻居检查的贪心/冲突修复迭代，chain 模式与图遍历类似但有更高的条件分支

---

## 入选依据

| 算法 | IMA Chains | Chain 来源 | L1 miss rate (cit-Patents sym=1) | Ideal L1D 加速 | IMA miss share |
|------|:---------:|-----------|--------------------|-----------------------|:-----------:|
| BFS | 7 | golden | 77.2% | 1.75× | 99.1% |
| SSSP | 7 | golden | 76.7% | 2.46× | 51.1% |
| BC | 19 | golden | 70.3% | 3.04× | 70.5% |
| CC | 6 | golden (合并) | — | 2.22× | 83.6% |
| SpMV | 29 | golden | — | 2.31× | 66.9% |
| VC | 34 | golden (合并) | 待测 | 待测 | 待测 |

> **筛选标准**：SASS 中存在 exact_chain（`LDG → IMAD.WIDE → LDG`）且 ideal L1D 加速 > 10%。
> CC/VC 的 chain 数据于 2026-03-31 从 `chain_extraction/extended_chains.csv` 合并到 golden CSV。

---

## VC 仿真可行性

VC 在较大数据集上仿真时间极长，需特别注意：

| 算法 | 数据集 | 预期 Kernels | 已知耗时 | 备注 |
|------|--------|:-:|---------|------|
| VC | cit-Patents sym=1 | 14 | 第 1 kernel 未完成 | 单 kernel 极慢 |
| VC | web-Google sym=1 | 62 | 1.5h 被 Kill（2%） | 单 kernel 极慢 |

**策略**：先在 roadNet-CA sym=1（最小数据集）上验证 VC baseline 是否可行，再逐步扩展到更大数据集。

---

## 未入选的 Gardenia 算法

| 算法 | IMA Chains | 状态 | 原因 |
|------|:---------:|------|------|
| SymGS | 2 | ✅ 已确认排除 | 有 2 条 chain（gs_kernel），但全场 0% speedup、timeliness <2%。Chain 匹配无效，GRASP 不产生有用 prefetch。另外 flickr/soc-LJ1 因 MAXCOLOR=128 crash 无法运行。详见 `experiment_results.md` |
| SCC | 0 | ✅ 已确认排除 | bfs_step/update/trim kernel 均无 `LDG → IMAD.WIDE → LDG` 链；71% 实例用 LEA/IADD3 |
| TC | 0 | ✅ 已确认排除 | warp-level set intersection，瓶颈是计算而非 IMA |
| MST | 0 | ✅ 已确认排除 | component-based 迭代操作，7 个 kernel 均无 IMAD.WIDE 链 |

> SCC/TC/MST 的 SASS 提取和 chain 分析均于 2026-03-31 完成，确认无 IMA pattern。
