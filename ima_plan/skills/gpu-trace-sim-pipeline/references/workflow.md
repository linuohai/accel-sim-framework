# GPU Trace to Simulation Workflow

按这个顺序走，不要把“接入 workload”“提 trace”“跑模拟”混成一个黑箱。

## 1. 环境检查

在 `/workspace/prefetch` 下执行：

```bash
pwd
echo "$CUDA_INSTALL_PATH"
nvcc --version
python3 --version
```

如果要提硬件 trace，再确认真实 GPU 可见：

```bash
nvidia-smi
```

## 2. 编译 workload

对仓库内 workload，先 source：

```bash
source gpu-app-collection/src/setup_environment
```

常见编译方式：

```bash
make -j -C gpu-app-collection/src <benchmark-suite>
make -C gpu-app-collection/src data
```

快速检查二进制是否落到标准位置：

```bash
ls gpu-app-collection/bin
```

只改了单个 workload 时，优先编译最小目标，不要默认 `make all`。

## 3. 构建 tracer

首次或 tracer 代码变更后执行：

```bash
./util/tracer_nvbit/install_nvbit.sh
make -C ./util/tracer_nvbit
```

## 4. 生成硬件 trace

标准主路径是 benchmark 级别 trace：

```bash
./util/tracer_nvbit/run_hw_trace.py -B <benchmark-suite> -D <gpu-id>
```

预期输出在：

```text
hw_run/traces/device-<gpu-id>/<cuda-version>/<app>/<args>/traces/
```

进入模拟前必须确认：

```text
kernelslist.g
```

如果只看到 `kernel-*.trace` 或 `kernelslist`，说明后处理没有正确完成。

需要源代码行号时：

```bash
export TRACE_LINEINFO=1
source gpu-app-collection/src/setup_environment
make -j -C gpu-app-collection/src <benchmark-suite>
```

## 5. 编译模拟器

```bash
source ./gpu-simulator/setup_environment.sh
make -j -C ./gpu-simulator
```

构建成功后，常见产物在：

```text
gpu-simulator/bin/release/accel-sim.out
```

## 6. 跑模拟

### 6.1 使用 `traceL1`

在这些情况优先使用：

- 需要 ideal L1D
- 需要仓库自定义 L1/L2/issue/HBM CSV trace
- 需要快速跑单个 trace key

示例：

```bash
./traceL1 bfs_roadnet
./traceL1 --ideal-l1d bfs_usa bfs_usa_ideal_l1d
./traceL1 --max-completed-cta 200 --no-issue-trace bfs_web quick_bfs_web
```

常见输出：

```text
result/log/<log_name>.log
result/L1cache_trace/<log_name>_l1.csv
result/L2cache_trace/<log_name>_l2.csv
result/issue_trace/<log_name>_issue.csv[.gz|.zst]
result/bandwidth/<log_name>_hbm_partition.csv
```

### 6.2 使用 `run_simulations.py`

在这些情况优先使用：

- 跑整个 benchmark suite
- 需要批量配置和作业管理
- 需要标准状态监控和 stats 收集

示例：

```bash
./util/job_launching/run_simulations.py -B <benchmark-suite> -C <config> -T ./hw_run/traces/device-<gpu-id>/<cuda-version>/ -N <run-name>
./util/job_launching/job_status.py -N <run-name>
./util/job_launching/monitor_func_test.py -v -N <run-name>
./util/job_launching/get_stats.py -N <run-name>
```

## 7. 交付时必须汇报

- benchmark suite 或 trace key
- 真实 `kernelslist.g` 路径
- 使用的 config
- 输出目录
- 是否做过裁剪，例如 `--max-cycle`、`--max-completed-cta`、`--no-issue-trace`

## 8. 无 GPU 时的处理

不要继续走硬件 trace 主路径。转为：

- 复用 `hw_run/traces/` 下已有 trace
- 或使用 `get-accel-sim-traces.py` 下载预制 trace
- 或明确告诉用户当前只能准备 workload 和模拟步骤，不能完成 trace 提取
