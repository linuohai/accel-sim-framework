# IMA Prefetch 研究上下文（本仓库的主要用途）

## 注意事项

- 任何对仓库代码/文件的改动，都必须先给出变更方案，并在获得确认同意后才能执行。
- 所有的操作都应该在 `fa` docker container 内进行（重点：容器内 `/workspace/prefetch`），不要在宿主机直接操作。
- 严禁使用任何 git 回退/重置类命令（例如 `git reset --hard` 等），避免破坏历史与工作区状态。
- 每次对话结束后追加“帅哥”（直接追加即可）。
- 对 `attention/decode` 的 IPC 衰退问题，优先使用“锚点 + episode”方法：先定位同步锚点（如 `WAIT_LDGSTS` / `WAIT_CTA_BARRIER` 的热点 PC），再按同一锚点内的 cycle gap 切分 episode，禁止把全程跨轮次事件直接混合统计。
- `attention/decode` 衰退分析的结果文件统一放在 `analyze/attention_degradation/`，至少包含：episode 明细 CSV、anchor 汇总 CSV、base-vs-ideal 对比 CSV、结论 Markdown。

## 研究目标，
本仓库用于在 Accel-Sim / GPGPU-Sim 上研究图负载中的 **IMA（Indirect Memory Access）** 行为，并评估/改进 **L1/L2 cache prefetch** 对 IMA 的缓解效果。重点关注：

- 典型 IMA 访问：`x[col_idx]`、`dist[neighbor]`、`visited[neighbor]`、`comp[neighbor]` 等“用数据当索引”的间接访存。
- 通过 trace（L1/L2/issue/HBM）对齐分析：cache 命中/缺失、stall 归因、带宽/占用等与 IMA 相关的瓶颈。

## 实验平台（当前运行环境）
当前实验在名为 `fa` 的 docker container 内进行。

- 容器内工作目录：`/workspace/prefetch`
- 宿主机对应路径：`accel-sim-framework/`

说明：容器内的 `/workspace/prefetch` 通过 bind mount 映射到宿主机的 `accel-sim-framework/`，因此在容器内对 `/workspace/prefetch` 的修改会直接反映到宿主机仓库目录中。

## 主要工作负载（Gardenia）
以 Gardenia 的图算法为主（均用于体现 IMA 访存模式）：

- BFS / SSSP / BC：frontier 扩散类，`dist/parent/sigma` 等数组对邻居 id 的间接访问明显。
- SpMV：`x[col_idx]` gather 典型 IMA。
- CC：`comp[neighbor]` 读写 + 多轮迭代。
- TC：邻接表交集（更偏图挖掘型 IMA），但规模可能更难控。
详见：`gpu-app-collection/gardenia/datasets/real_workload/IMA_workload_selection.md`

## 主要工作负载（Rodinia 3.1）
Rodinia 的图类 workload 很少，主要用来补充“更干净/更可控”的 IMA 基线：

- BFS：典型 `visited/cost[neighbor]` 间接访存；自带 `graph*` 输入更偏合成随机图（IMA 很强）。
- B+Tree：典型 pointer chasing + `records[idx]` 间接访存；适合观察串行依赖链下的 miss latency/MLP/预取权衡。
详见：`gpu-app-collection/src/cuda/rodinia/3.1/IMA_workload_selection.md`

## Attention / Decode Degradation 研究说明

### 背景

- 在 `gpgpu_perfect_l1d`（ideal L1D）实验中，部分 attention/decode workload 会出现 IPC 不升反降。
- 该问题与“读被加速后的 warp 时序变化、同步点拥堵、读写不对称”相关，需要通过 issue trace 的时序分析验证。

### 推荐分析流程（锚点 + episode）

1. 从 `stall_reason_pc_topk_other.csv` 中提取同步热点 PC（`WAIT_LDGSTS` / `WAIT_CTA_BARRIER`）。
2. 在 base 与 ideal 的 issue trace 中提取锚点事件。
3. 对每个锚点按 cycle gap 切分 episode（同一轮次同步会合）。
4. 逐 episode 统计并对比：
   - 到达离散度：`arrival_span` / `arrival_std`
   - 同周期拥堵：`peak_rows_same_cycle` / `peak_sms_same_cycle`
   - 停留时长：`dwell_p50/p90/max`
5. 结合 IPC 与 stall breakdown 给出因果判断，避免只看单一比例指标。

### 输出规范

- 目录：`analyze/attention_degradation/`
- 文件命名建议：
  - `*_episode_stats_base.csv`
  - `*_episode_stats_ideal*.csv`
  - `*_episode_anchor_summary_base.csv`
  - `*_episode_anchor_summary_ideal*.csv`
  - `*_episode_anchor_summary_compare.csv`
  - `*_episode_analysis.md`
