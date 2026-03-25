# SOTA Baseline Resume Design

> 目的：把 `sota_impl_spec.md` 的后续落地方案与旧会话中已确认的关键信息固化到仓库文件，避免后续实现再次依赖聊天上下文。
>
> 状态：2026-03-24 恢复版设计，尚未开始在主仓库正式实现 SOTA baseline 代码。

---

## 1. 背景与当前结论

`ima_plan/05_implementation/sota_impl_spec.md` 已经给出了 SOTA baseline 的实现规格，但当前主仓库里：

- 还没有 `baseline_stride.{h,cc}`
- 还没有 `baseline_snake.{h,cc}`
- 还没有 `baseline_spare_reg.{h,cc}`
- 还没有 `exp/sota_*` 分支和 `/workspace/prefetch/worktrees/sota_*` worktree

也就是说，`sota_impl_spec.md` 目前仍处于“规格完成、正式实现未开始”的状态。

同时，仓库里已经存在一条可直接复用的前置能力链路：

- strict IMA chain 提取
- runtime loader 按 `function / impl / sm / classification` 过滤
- `ima_pair_table` correctness 验证

对应交接材料见：

- `ima_plan/05_implementation/ima_pair_table/agent_handoff_status.md`
- `ima_plan/05_implementation/ima_pair_table/validation_status.md`
- `ima_plan/05_implementation/experiment_progress.md`

这意味着：SOTA baseline 的后续实现不需要重新证明 strict chain / pair table 输入本身是否可信，而是应该在该输入之上推进 baseline 逻辑与实验入口。

## 2. 从旧会话恢复出的关键事实

### 2.1 已确认的可复用前置能力

旧会话已经确认：

- `gpu-simulator/trace-driven/trace_driven.cc` 侧已经实现 seed API，baseline 可以复用 strict chain 作为 IMA seed/filter 输入。
- `strict_selected_chain_instances.csv` 已经覆盖 `spmv / bfs / sssp / bc` 的 strict `exact_chain` 样例。
- `ima_pair_table` 在 strict `exact_chain` 输入下，对 `spmv / bfs / sssp / bc forward / bc reverse` 没发现 correctness 反例。

这些结论说明：

- `Spare Register` 所需的 chain-based filtering 不是“不可做”，而是“已有前置输入可接”。
- baseline 不需要回退到旧的宽松 chain 提取口径。

### 2.2 已确认的实验入口缺口

旧会话还确认了一个直接影响 baseline 验证的入口问题：

- `traceL1` 当前只在 GRASP 分支写入 `-gpgpu_ima_prefetch_chain_csv`
- baseline 路径即使传入 `--grasp-chain-csv ...`，也不会把该 CSV 写进生成后的 config

该缺口的直接表现是：

- 用 `--baseline-spare-reg --grasp-chain-csv strict_selected_chain_instances.csv` 跑 probe 时，`prefetch_issued` 保持 0
- 这与“baseline run 没拿到 chain CSV”一致

因此，`traceL1` 的 chain CSV 传参修复应当作为正式续做中的一部分保留，而不是依赖聊天记忆。

### 2.3 旧 scratch worktree 中已做过一次原型修补

旧会话在 scratch 副本 `tmp/sota_exec/` 中已经做过一次原型修补，关键信息如下：

- `traceL1` 原型版曾改成 baseline 也注入 `-gpgpu_ima_prefetch_chain_csv`
- `baseline_stride` 原型版曾尝试使用 `warp->get_ima_seed_chain_ids(pc)` 过滤非 IMA PC
- `baseline_stride` 原型版曾在 warp 退出时清理 intra 状态
- 原型 smoke test 已能跑通，但短窗口内 `prefetch_issued` 仍为 0

这些改动目前只存在于 `tmp/sota_exec/` 的 scratch 副本，不在主仓库正式代码中。它们的价值是：

- 证明“入口修复 + IMA seed 过滤”方向是可编译、可 smoke 的
- 但不能视为主仓库已完成实现

## 3. 设计目标

本轮恢复后的正式目标不是“一口气做完所有 baseline”，而是先建立一个可持续推进、不依赖会话上下文的实施路径：

1. 先把续做依据写入仓库文档
2. 正式实现顺序遵守 `sota_impl_spec.md`
3. 第一批只做 `INTRA/INTER`
4. 将 `traceL1` 的 chain CSV 缺口一并纳入正式实现计划
5. 每一阶段都生成新的 handoff 痕迹，避免再次被 `/compact` 打断

## 4. 推荐的正式实现顺序

### Phase 0: 文档与交接固化

输出：

- 本文件
- 对应的 implementation plan 文件

目标：

- 把旧会话恢复出的事实写入仓库
- 让后续 agent 不需要读取会话历史即可继续

### Phase 1: `INTRA/INTER` 正式落地

理由：

- `sota_impl_spec.md` 明确把 `INTRA/INTER` 设为 P0
- 它们对现有 hook 的复用最直接
- 可以最早打通 config、hook、stats、smoke test
- 即使最终性能差，也能最快形成 baseline 对照组

本阶段建议同时纳入两项“入口配套”工作：

- `traceL1` baseline chain CSV 传参修复
- `baseline_stride` 的 IMA seed 过滤与 warp-exit 清理

### Phase 2: `Snake`

前提：

- Phase 1 已证明 baseline 框架、stats、注入路径可用

理由：

- `Snake` 仍属于 stride-family，可复用前一阶段对 hook 和配置框架的验证

### Phase 3: `Spare Register`

前提：

- `traceL1` chain CSV 修复已合入正式主线
- strict chain 输入路径可稳定复用

理由：

- 它最依赖 trace-driven + chain 输入
- 排错成本最高
- 不应在 baseline 基础框架尚未稳定时过早进入

## 5. 关键设计决策

### 5.1 先不在当前脏工作区直接实现

主仓库当前存在大量未提交修改，因此正式 baseline 实现仍应遵守 `sota_impl_spec.md`：

- 一个 baseline 一个 worktree
- 当前 `/workspace/prefetch` 继续作为参考区

这不是形式要求，而是为了避免：

- baseline 改动和研究文档改动混在一起
- 编译产物污染
- 后续难以判断哪些变更属于 SOTA baseline

### 5.2 `traceL1` 入口修复视为 baseline 正式实现的一部分

虽然 `traceL1` 不属于某个 baseline 类本身，但对 `Spare Register` 和未来所有依赖 strict chain 的 baseline 来说，这个入口缺口是 blocker。

因此本轮正式续做中，应把它视为 baseline enablement，而不是单独的杂项修补。

### 5.3 IMA seed/filter 只作为“约束输入”，不作为额外增强

`baseline_stride` 使用 `warp->get_ima_seed_chain_ids(pc)` 过滤非 IMA PC 的目的不是“给 baseline 加论文外优化”，而是：

- 在本项目的 IMA 研究口径下，把 baseline 限定在与 GRASP 可比的 IMA 访问集合上
- 减少非 IMA load 对统计与训练的污染

这项过滤是否最终保留，必须在正式实现时明确记录为：

- 项目级实验口径约束
- 不是 SOTA baseline 论文声称的新机制

## 6. 非目标

本轮恢复和计划编写不做以下事情：

- 不直接开始修改模拟器核心代码
- 不开始 `Snake` 或 `Spare Register` 正式实现
- 不做 baseline-specific 调参
- 不重新跑大规模实验
- 不在当前文档里声称 baseline 已实现完成

## 7. 风险与检查点

### 风险 1：`traceL1` 修复只在 scratch 副本存在

应对：

- 正式实现时在主仓库重做一次
- 重新 smoke 验证，不信任 scratch 结果本身

### 风险 2：IMA seed 过滤可能改变 baseline 定义口径

应对：

- 在正式实现与评估文档中明确写明这是项目级过滤口径
- 保持开关和代码路径清晰，避免与 baseline 核心逻辑耦死

### 风险 3：当前仓库脏状态导致混改

应对：

- 正式编码前先建立隔离 worktree
- 本轮只写文档，不碰模拟器代码

## 8. 本设计对应的下一个产物

本设计之后的直接产物应是一份 implementation plan，内容至少包括：

- Phase 1 `INTRA/INTER` 的具体文件边界
- `traceL1` chain CSV 修复
- smoke test 命令
- worktree 准备要求
- 每一步的完成判定

这样后续即使会话再次中断，新的 agent 也只需要读取：

- `sota_impl_spec.md`
- 本文件
- implementation plan

即可继续推进。 

## 9. 后续阶段性进展入口

在恢复设计与实现计划之外，2026-03-24 已经补充了一份专门记录 stride baseline 实验进展的背景文档：

- `ima_plan/05_implementation/sota_stride_progress_2026-03-24.md`

该文档用于固化以下信息：

- `baseline-intra / baseline-inter` 当前的实际实现状态
- `80k / 200k / 500k` 代表性实验结果
- 为什么当前判断“不是实现坏了，而是 workload 适配性分化明显”
- 为什么 `baseline-intra` 已经可以作为后续 SOTA baseline 实验的有效对照项

后续新的 agent 若需要继续 SOTA baseline 工作，建议优先阅读顺序为：

1. `ima_plan/05_implementation/sota_impl_spec.md`
2. `ima_plan/05_implementation/sota_resume_design.md`
3. `ima_plan/05_implementation/sota_resume_plan.md`
4. `ima_plan/05_implementation/sota_stride_progress_2026-03-24.md`
