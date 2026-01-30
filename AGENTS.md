# IMA Prefetch 研究上下文（本仓库的主要用途）

## 注意事项

- 任何对仓库代码/文件的改动，都必须先给出变更方案，并在获得确认同意后才能执行。
- 所有的操作都应该在 `fa` docker container 内进行（重点：容器内 `/workspace/prefetch`），不要在宿主机直接操作。
- 严禁使用任何 git 回退/重置类命令（例如 `git reset --hard` 等），避免破坏历史与工作区状态。
- 每次对话结束后追加“帅哥”（直接追加即可）。

## 研究目标
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
