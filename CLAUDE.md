# CLAUDE.md

## 重要约束

- 当前工作目录若为 `/workspace/prefetch`（`fa` container）可直接操作；否则所有操作须通过 `docker exec fa <command>`
- **任何代码/文件改动，必须先给出变更方案并获得确认后才能执行**
- **严禁使用 git 回退/重置命令**（`git reset --hard`、`git checkout .` 等）
- 操作文件前若不确定写权限，先 `ls -la` 检查 ownership；root 文件提示 `sudo chown`

## 快速导航

- 研究计划与目标 → [`ima_plan/00_overview.md`](ima_plan/00_overview.md)
- 当前进度与状态 → [`ima_plan/INDEX.md`](ima_plan/INDEX.md)（由 `/update-ima-index` 生成，过时则提示用户重新运行）
- Skill 定义 → `ima_plan/skills/`（`/update-ima-index`、`/grasp-health-check`、`/session-review`、`gpu-trace-sim-pipeline`）
- 回归测试 → [`ima_plan/05_implementation/regression/grasp_regression.sh`](ima_plan/05_implementation/regression/grasp_regression.sh)（修改 GRASP 代码后必跑，默认 `--quick` 只跑 BFS ~34min，`--full` 跑 4 workload 并行 ~44min）
- Debug 方法学 → [`ima_plan/05_implementation/debug/README.md`](ima_plan/05_implementation/debug/README.md)（GRASP 小 case 5 阶段 debug 规范）
- DSE 参数探索 → [`ima_plan/05_implementation/dse_ct_reset_policy.md`](ima_plan/05_implementation/dse_ct_reset_policy.md)（speculative stride、CT reset policy 等待验证特性）
- **实验结果（唯一数据源）** → [`ima_plan/06_evaluation_plan/experiment_results.md`](ima_plan/06_evaluation_plan/experiment_results.md)（46 workloads × 3 modes，含 source log 标注）
- 实验耗时参考 → [`ima_plan/06_evaluation_plan/experiment_timing.md`](ima_plan/06_evaluation_plan/experiment_timing.md)（指导时间规划和并行策略）
- 输出指标规范 → [`ima_plan/06_evaluation_plan/output_specification.md`](ima_plan/06_evaluation_plan/output_specification.md)（§2 展示指标 + §3 调试指标 + §7 报告模板）

## 跨 Session 状态管理与文档自维护

### 并发协调

本项目常有多个 Claude Code 窗口同时运行，使用 `.claude/BOARD.md` 协调：
- **启动**：读 BOARD.md → 检查 Editing 列无冲突 → 注册自己（ID、时间、焦点、编辑文件）→ 清理 >8h 的 STALE 条目
- **冲突**：文件已被另一 ACTIVE session 声明 → 通知用户（等待/换文件/手动协调）。大文件可声明 section 级别（`文件#§3.2`）
- **结束**：移到 Completed，修改共享文档则在 Notes 留说明

### Post-Task 路由表

完成任务后，按下表更新对应文档：

| 做了什么 | 更新哪里 | 怎么更新 |
|---------|---------|---------|
| 跑实验 / 分析结果 / 解决问题 | `05_implementation/experiment_progress.md` | 追加条目（日期+配置+结果+发现/解决的问题） |
| 修改 GRASP 源码 | `experiment_progress.md` 版本记录 | 记版本号+改动摘要 |
| 更新阶段文档 (01-07) | 该文档的 `最近更新` 时间戳 | 改为当天日期 |
| 写论文/绘图 | `07_paper_outline/` 对应文件 | — |
| 新增 SOTA baseline | `05_implementation/sota_baseline/README.md` | 追加结果行 |
| 修改 GRASP 源码（`grasp_*.{h,cc}`） | 回归测试 | 跑 `./ima_plan/05_implementation/regression/grasp_regression.sh check`，确认全 PASS |
| 新建全局工具/脚本/约束 | 本文件（CLAUDE.md）对应 section + BOARD.md Notes | 注册到相应位置（见下方说明） |

### 新能力注册（关键）

当你在 session 中**创建了任何应影响后续所有 session 的新事物**时，必须注册到全局文档，否则其他 session 不知道它的存在：

| 新建了什么 | 注册到哪里 |
|-----------|-----------|
| 测试/回归测试脚本 | CLAUDE.md "运行仿真" section 添加用法 |
| 新的分析/绘图脚本 | 对应阶段文档 + experiment_progress.md 记录 |
| 新的代码规范/约束 | CLAUDE.md "GRASP 代码规范" section |
| 新的 skill/command | `ima_plan/skills/` 创建 SKILL.md + `.claude/commands/` 创建 pointer |
| 新的配置参数 | CLAUDE.md "关键自定义功能" 表 + `grasp_config_t` |

同时在 BOARD.md Notes 留一条通知，让并发 session 立即可见。

### Session 结束自检

以下自检项在 session 结束时应执行。**但 context 增长后 agent 可能遗忘**——建议用户在结束 session 前主动运行 `/session-review`，该命令会强制执行以下所有检查：

1. 按路由表确认：本次改动的每个类别都已更新对应跟踪文档
2. **新能力检查**：本次是否创建了新脚本/工具/约束？若是，是否已按上表注册到全局文档？
3. INDEX.md 刷新条件（任一命中即提示用户 `/update-ima-index`）：experiment_progress 有追加 / 阶段文档修改 / `ima_plan/` 新增文件
4. 所有修改过的 `ima_plan/*.md` 的 `> 最近更新:` 时间戳已更新为当天

### 文档新鲜度

- `ima_plan/` 下 .md 文件前 10 行须有 `> 最近更新: YYYY-MM-DD`；编辑时同步更新
- 读取时若时间戳与目录最新 mtime 差 >7 天，提示用户文档可能过时
- INDEX.md 时间戳由 `/update-ima-index` 维护，不手动改

### 冗余检测与垃圾回收

**检测**：读文档时发现与其他跟踪文档的实质性重复 → 指出并建议保留权威源、其他处改为链接。权威优先级：experiment_progress.md（实验数据）> 阶段文档（分析）> INDEX.md（派生摘要）

**回收**（检测不够，必须定期清理）：
- `experiment_progress.md`：超过 30 天的旧实验条目 → 归档到 `05_implementation/experiment_logs/YYYY-MM.md`，主文件只保留最近条目
- 阶段文档中已完成的 TODO / 已解决的问题 → 删除或移到"已完成"section
- INDEX.md 中指向已不存在文件的链接 → 清除
- `ima_plan/` 下不再使用的临时分析脚本 → 标记或归档
- 定期运行 `/grasp-health-check` 执行全面扫描（建议每周一次）

## 技术分析规范

### GPU Prefetcher 分析
- **先读再说**：对 GRASP 行为或性能的任何判断，**必须先读相关源码和实验数据**，禁止在未读代码的情况下推测原因。INDEX.md "GRASP 源代码文件" 和 "源码导航" 段提供了文件→功能的映射
- 分析 GPU prefetcher（GRASP、IMA 等）时，**必须以 SASS 指令级 trace 和硬件实测数据为依据**，禁止仅给出源码层面或抽象层面的摘要
- 讨论 GPU prefetching 的 baseline 时，**严禁引入 CPU-only prefetcher**（如 stream/stride 等 CPU 变体），必须验证所有 baseline 均为 GPU 相关
- 涉及 cache/memory hierarchy 机制（MSHR、FIFO、prefetch buffer）时，**必须精确区分 entry 的"检测/匹配"与"分配/消耗"**

### 实验数据验证（先 sanity check 再分析）
- 生成诊断数据（event timeline、GRASP trace、指标输出）后，**必须先做值域分布 sanity check**（如 `grep iter_stride | sort | uniq -c`），确认无异常值后再进入高层分析
- 看到 accuracy < 60% 等不理想指标时，**必须追问 root cause**（stride 异常？pair table miss？RFAIL？），禁止只记录数字不分析原因
- 原则：**先验证数据质量，再做数据分析**。简单的统计检查永远优先于复杂的性能分析

### 文档写作
- 写周报、related work 等文档前，**必须先确认范围**，默认取**最小范围**
- 技术声明若涉及硬件行为或性能数据，需能指向具体的文件/trace/spec

### GRASP 代码规范（Golden Rules）
- 新增配置参数必须通过 `grasp_config_t` 暴露，禁止硬编码 magic number
- debug 日志统一用 `GRASP_DPRINTF`，禁止裸 `printf`/`cout`
- 实验性代码用 `#ifdef GRASP_EXPERIMENTAL` 隔离，合入主线前删除
- 分析脚本必须 `from plot_util import apply_style`，禁止内联 `rcParams`
- 保持与 GPGPU-Sim 编码惯例一致（`m_` 前缀成员变量、`_t` 后缀类型名）

## 构建模拟器

```bash
source ./gpu-simulator/setup_environment.sh  # 每次新 shell 必须先运行
make -j -C ./gpu-simulator/                  # 编译（或用 cmake）
# 产物: ./gpu-simulator/bin/release/accel-sim.out
```

## 运行仿真（核心入口：traceL1 脚本）

```bash
./traceL1 <trace_key> [log_name]                                    # 基本用法（默认 SM80_A100）
./traceL1 -c SM7_QV100 bfs_roadnet                                  # 切换 GPU 配置
./traceL1 --ideal-l1d bfs_usa bfs_usa_ideal                         # Ideal L1D 上界实验
./traceL1 --grasp bfs_roadnet bfs_grasp                              # 启用 GRASP prefetcher
./traceL1 --max-completed-cta 200 bfs_web                            # 限制 CTA（快速验证）
./traceL1 --issue-trace-compress gzip bfs_roadnet bfs_roadnet_gz     # 边跑边压缩
./traceL1 --plot bfs_roadnet bfs_roadnet_plot                        # 仿真后自动绘图
./traceL1 --grasp --sim-args "-grasp_tc_mode 4 -grasp_tc_mshr_threshold 40 -grasp_tc_cooldown 200" bfs_ima_small bfs_tc  # 传递额外仿真参数
```

`trace_key` 须为 `traceL1` 脚本 `TRACE_MAP` 中的键。统一命名规范：`{algo}_{dataset}_{dir|sym}`（如 `bfs_cit_sym`、`cc_flickr_sym`）。旧名 `*_ima_high` = `*_cit_sym`，`*_ima_med` = `*_web_sym`（保留兼容）。

> **Trace 输出注意**：默认开启 L1/L2/HBM trace，单实验可产出 10-20 GB。批量实验**必须**关闭（`--no-l1-trace --no-l2-trace --no-hbm-trace`）或开启压缩。

### 批量实验

```bash
./run_batch_experiments.sh all       # 并行跑全部 baseline + GRASP（带内存监控 + kill 检测）
./run_batch_experiments.sh baseline  # 只跑 baseline
./run_batch_experiments.sh grasp     # 只跑 GRASP
./run_ideal_l1d.sh                   # 并行跑全部 Ideal L1D（load-only）
```

结果报告自动写入 `ima_plan/06_evaluation_plan/batch_run_report.md` 和 `ideal_l1d_report.md`。

### 实验完成性验证

`traceL1` 在仿真结束后自动写入 `=== EXPERIMENT SUMMARY ===` 到 log 末尾，包含 `status=COMPLETE|PARTIAL|CRASHED`、`expected_kernels`、`completed_kernels`、`final_ipc`。**Agent 每次读取实验结果前必须先检查 `status=COMPLETE`**。

### Golden Chain CSV（GRASP 硬依赖）

`ima_plan/05_implementation/ima_pair_table/golden/strict_selected_chain_instances.csv` 是所有 GRASP/IMA 仿真的必需输入。`traceL1 --grasp` 默认使用此文件。**修改此 CSV 后必须重跑回归测试**。per-workload 子 CSV 也在同一 `golden/` 目录下。

### Baseline Registry

完成的 baseline 实验自动写入 `ima_plan/06_evaluation_plan/baseline_registry.csv`。**不需要每次重跑 baseline**——直接从 registry 读取。仅在改了 GPU config 或重新生成 trace 时才需要重跑。

### GRASP Prefetch 指标输出

启用 GRASP 的仿真 log 中会输出以下行：
- `GRASP_CONFIG:` — 一次性参数 dump（仅 SM0）
- `GRASP_DEMAND SM*:` — global reads/misses, throttle_suppressed
- `GRASP_IMA_DEMAND SM*:` — IMA index/data 分项：reads/hits/hit_reserved/misses（chain CSV PC 过滤，reads=hits+hit_res+misses）
- `GRASP_TIMELINESS SM*:` — index/data timeliness%（= hits/(hits+hit_reserved)）
- `GRASP_EFFECT SM*:` — legacy pf_useful/pf_useless/pf_late/accuracy%（L1 cache 级，不区分 IMA PC，仅供 debug）
- `GRASP_STORAGE SM*:` — PRB/CT/CD FIFO 峰值占用 vs 配置容量（利用率%）+ prefetch queue 峰值
- `GRASP_RFAIL SM*:` — index+data 合并 reservation fail 各原因占比%

全局输出（baseline 和 GRASP 都有，所有 SM 汇总）：
- `IMA_DEMAND:` — index/data reads/hits/hit_reserved/misses 汇总
- `IMA_TIMELINESS:` — index/data timeliness%

EXPERIMENT SUMMARY（GRASP 模式）会自动**聚合全部 SM** 的 EFFECT/STORAGE/RFAIL/FUNNEL 并显示在终端和 log 末尾。TIMELINESS 取自全局 `IMA_TIMELINESS:` 行。

> 完整的指标分级规范（展示/调试分层 + 三版本规则 + 报告模板）见 [`06_evaluation_plan/output_specification.md`](ima_plan/06_evaluation_plan/output_specification.md)

### 输出文件位置

| 类型 | 路径 |
|------|------|
| 日志 | `result/log/<log_name>.log` |
| L1 trace | `result/L1cache_trace/<log_name>_l1.csv` |
| L2 trace | `result/L2cache_trace/<log_name>_l2.csv` |
| Issue trace | `result/issue_trace/<log_name>_issue.csv[.gz|.zst]` |
| HBM 带宽 | `result/bandwidth/<log_name>_hbm_partition.csv` |
| Stall 统计 | `result/issue_trace/stall_reason_pc_stats/<log_name>/` |

### 绘图与后处理

```bash
result/plot/run_plots.sh --log-name <log_name>                    # 一键绘图
result/plot/run_plots.sh --log-name <log_name> --format png       # 或 both
```

GRASP 逐 Iteration 分析：见 `ima_plan/04_prefetcher_design/tiny_case/grasp_verify/README.md`。

## 绘图规范（Paper-Quality Figures）

### Style 与尺寸

```python
import sys; from pathlib import Path
_REPO = Path(__file__).resolve().parents[N]  # 调整 N 到仓库根目录
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_col, figsize_full, save_fig, CB10
apply_style()
```

| 类型 | 宽度 | 默认高度 | 用途 |
|------|------|----------|------|
| 单栏 | 3.5 in | 2.5 in | 单个 bar chart、line plot |
| 双栏 | 7.0 in | 2.7 in | 并排子图、timeline |

### 必须遵守

- `apply_style()` 加载 `academic.mplstyle`；颜色用 `CB10` 或语义调色板
- 输出 PDF + SVG，使用 `save_fig(fig, stem, out_dir)`；每个 figure 必须 `plt.close(fig)`
- 创建 figure 优先使用 `constrained_layout=True`
- 图例放置优先级：(a) 图外 `bbox_to_anchor` (b) `loc='best'` (c) 图下方 `fig.legend`。**禁止**固定 `loc=` 不检查重叠
- `annotate_bars()` 后 ylim 上界留空间（`data_max × 1.12`）
- stacked bar 类别 >4 个时图例必须在图外或图下方
- 多 baseline 对比（≥3 个方案）的 grouped bar chart **必须同时使用颜色 + hatching**（`plot_util.HATCHES`），确保黑白打印可分辨。"Our work" (GRASP) 使用实色无 hatch（`HATCHES[0]`），视觉突出
- y 方向水平虚线网格已在 `.mplstyle` 中默认开启（`axes.grid: true`, `axes.grid.axis: y`），不需要手动设置

### 禁止

- `figsize` 超 `(7.0, 5.0)` / 文字小于 6pt / red+green 对比 / `plt.show()` / 内联 `rcParams`

### 配置文件

- Style: `ima_plan/07_paper_outline/plot_style/academic.mplstyle`
- 工具: `ima_plan/07_paper_outline/plot_style/plot_util.py`

## 架构概览

```
accel-sim-framework/
├── traceL1                     # 主实验入口（自定义）
├── gpu-simulator/
│   ├── gpgpu-sim/src/gpgpu-sim/ # 核心仿真：gpu-sim.cc, gpu-cache.cc, shader.cc
│   │   └── grasp_*.{h,cc}      # GRASP prefetcher（CD/CT/TT/IPU/DPU/PRB）
│   └── configs/tested-cfgs/     # GPU 配置（默认 SM80_A100）
├── gpu-app-collection/gardenia/ # 主要工作负载（BFS/SSSP/BC/SpMV/CC/TC）
└── result/                      # 所有实验输出（CSV、图、日志）
```

### 关键自定义功能

| 功能 | 开关 | 文档 |
|------|------|------|
| Ideal L1D Cache | `--ideal-l1d` 或 `-gpgpu_perfect_l1d 1` | `gpu-simulator/gpgpu-sim/doc/ideal_l1d_cache_plan.md` |
| L1 Trace | `-l1_trace_enable 1 -l1_trace_path <path>` | `gpu-simulator/gpgpu-sim/doc/l1_trace.md` |
| Issue Trace | `-issue_trace_enable 1`（建议 `--issue-trace-compress gzip`） | `gpu-simulator/gpgpu-sim/doc/issue_trace.md` |
| N-Level 调度器 | `./traceL1 -nl` | `gpu-simulator/gpgpu-sim/doc/n_level_warp_scheduler.md` |
| Speculative Stride | `--grasp-speculative-stride N` 或 `-grasp_speculative_stride N`（默认 0=关闭）+ chain CSV `stride_hint` 列。CC/VC stride_hint 已于 2026-04-03 从 SASS 分析补齐 | `ima_plan/05_implementation/dse_ct_reset_policy.md` |
| Throttle Cooldown | `-grasp_tc_mode 4 -grasp_tc_mshr_threshold 40 -grasp_tc_cooldown 200`（默认 mode=0 thr=80） | `ima_plan/05_implementation/dse_throttle_control/README.md` |
| Sim Args Passthrough | `--sim-args "<raw gpgpusim options>"`（traceL1 额外参数透传） | traceL1 脚本内 `EXTRA_SIM_ARGS` |

### GPU 配置

默认 `SM80_A100`，可选：`SM7_QV100`、`SM7_GV100`、`SM75_RTX2060`、`SM86_RTX3070`。配置路径：`gpu-simulator/gpgpu-sim/configs/tested-cfgs/<CONFIG>/gpgpusim.config`
