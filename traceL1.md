# traceL1 使用说明（中文）

`traceL1` 是一个 Accel-Sim 启动脚本：用于在指定配置（如 `SM80_A100`）下运行某个 trace（`kernelslist.g`），并自动把 L1/L2/issue/HBM 等 CSV trace 输出到 `accel-sim-framework/result/` 目录，同时可选在仿真结束后自动绘图。

本文档侧重“常见使用场景”，便于你日常批量跑实验时快速套用。

---

## 1. 快速开始（最常用）

在 `accel-sim-framework/` 目录下运行：

- 运行一个测例（默认配置 `SM80_A100`，日志名默认等于 trace_key）
  - `./traceL1 bfs_roadnet`
- 指定日志名（强烈建议：便于并行跑、避免覆盖）
  - `./traceL1 bfs_roadnet my_bfs_roadnet_run1`
- 切换配置模型
  - `./traceL1 -c SM7_QV100 bfs_roadnet`
- Ideal L1D（上界实验：强制 eligible global read 为 L1D HIT）
  - `./traceL1 --ideal-l1d bfs_usa bfs_usa_ideal_l1d`

`trace_key` 必须是脚本内 `TRACE_MAP` 定义过的键。

---

## 2. 输出文件在哪里

脚本会把输出放到以下目录（若不存在会自动创建）：

- 日志：`result/log/<log_name>.log`
- L1 trace：`result/L1cache_trace/<log_name>_l1.csv`
- L2 trace：`result/L2cache_trace/<log_name>_l2.csv`
- issue trace：
  - 未压缩：`result/issue_trace/<log_name>_issue.csv`
  - 边运行边压缩：`result/issue_trace/<log_name>_issue.csv.gz` 或 `result/issue_trace/<log_name>_issue.csv.zst`
- HBM 分区带宽：`result/bandwidth/<log_name>_hbm_partition.csv`

---

## 3. 常见场景

### 场景 A：只想快速验证（减少时间/输出体量）

常见做法：限制 cycle/CTA 或直接关掉最重的 trace。

- 只跑前 N 个 CTA：
  - `./traceL1 --max-completed-cta 200 bfs_web quick_bfs_web`
- 只跑前 N 个 cycle：
  - `./traceL1 --max-cycle 200000 bfs_roadnet quick_bfs_roadnet`
- 只关 issue trace（最省空间/最提速）：
  - `./traceL1 --no-issue-trace bfs_roadnet no_issue`

### 场景 B：大规模 issue trace 会爆盘（推荐：边运行边压缩）

issue trace 非常大（按 cycle×SM×scheduler 记账），建议对大规模 workload 默认开启压缩。

- 使用 gzip（依赖最少，系统通常自带）：
  - `./traceL1 --issue-trace-compress gzip bfs_roadnet bfs_roadnet_gz`
- gzip 调整压缩级别（1~9，越大越慢，通常在线建议 1~3）：
  - `./traceL1 --issue-trace-compress gzip --issue-trace-compress-level 1 bfs_roadnet bfs_roadnet_gz1`
- 使用 zstd（需系统有 `zstd` 命令；通常压缩比更好）：
  - `./traceL1 --issue-trace-compress zstd bfs_roadnet bfs_roadnet_zst`
- zstd 调整级别与线程数（在线并行跑时建议 threads=1，避免压缩抢 CPU）：
  - `./traceL1 --issue-trace-compress zstd --issue-trace-compress-level 3 --issue-trace-compress-threads 1 bfs_roadnet bfs_roadnet_zst3`

压缩过程会写一份日志：
- `result/log/<log_name>_issue_trace_compress.log`

### 场景 C：切换调度器（n_level / gto）

- 启用 n_level：
  - `./traceL1 -nl bfs_roadnet bfs_roadnet_nl`
- n_level 指定默认 scheduler：
  - `./traceL1 -nl -nls gto bfs_roadnet bfs_roadnet_nl_gto`
- 直接启用 gto（与 -nl 互斥）：
  - `./traceL1 -gto bfs_roadnet bfs_roadnet_gto`

### 场景 D：仿真结束自动绘图（快速看趋势）

- 本地并行绘图（默认 local）：
  - `./traceL1 --plot bfs_roadnet bfs_roadnet_plot`
- session/tmux 后端（适合后台跑）：
  - `./traceL1 --plot-backend session --plot-monitor bfs_roadnet bfs_roadnet_plot_session`

注意：`run_plots.sh` 已支持压缩后的 issue trace 输入（`.csv.gz/.csv.zst` 会自动优先使用）。
如果同一个 `log_name` 同时存在 `.csv` 与压缩版本，你也可以直接在绘图脚本里用完整路径指定要画哪个文件（例如传入 `..._issue.csv.gz`）。

---

## 4. 并行跑多个测例的建议（强烈建议阅读）

你经常会并行启动多个 `traceL1`，建议遵循：

- **确保 `log_name` 唯一**：避免覆盖 `result/*` 下同名输出文件
  - 推荐显式传第二个参数：`./traceL1 bfs_roadnet run_$(date +%m%d_%H%M%S)_bfs_roadnet`
- 开启压缩时更要唯一：FIFO/压缩文件名也基于 `log_name`
- 如果并行很多任务：
  - gzip：建议 `--issue-trace-compress-level 1`
  - zstd：建议 `--issue-trace-compress-threads 1`（避免压缩抢 CPU 影响仿真）
- 批量跑时不建议每个任务都 `--plot`（会额外起一堆绘图进程抢资源）；可以跑完后再统一画。

---

## 5. 后处理与分析入口（常用）

- issue trace stall breakdown（支持 `.csv/.csv.gz/.csv.zst`）：
  - `python3 result/issue_trace/plot/script/plot_single_issue_breakdown.py result/issue_trace/<log>_issue.csv.gz`
- issue trace 带宽/占用随时间（支持 `.csv/.csv.gz/.csv.zst`）：
  - `python3 result/issue_trace/plot/script/plot_bandwidth_over_time.py --stem <log>_issue`
- 一键画四张图：
  - `result/plot/run_plots.sh --log-name <log>`

---

## 6. 常见问题（FAQ）

- Q：开启 `--issue-trace-compress zstd` 报 “找不到 zstd”
  - A：安装 `zstd` 命令，或改用 `--issue-trace-compress gzip`。
- Q：压缩后找不到 `*_issue.csv`
  - A：这是预期行为（压缩输出是 `*_issue.csv.gz` 或 `*_issue.csv.zst`）。绘图脚本与 `run_plots.sh` 已支持直接读取压缩文件。
- Q：并行跑时输出被覆盖/乱掉
  - A：检查是否多个进程使用了相同 `log_name`（第二个参数）。
