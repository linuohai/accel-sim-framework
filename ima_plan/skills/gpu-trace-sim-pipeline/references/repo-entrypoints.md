# Repo Entrypoints

只列对这个 skill 真正关键的入口。

## Workload 接入与编译

- `gpu-app-collection/src/setup_environment`
  先 source，再编译应用；它会设置 `GPUAPPS_ROOT`、`CUDA_VERSION`、`BINDIR`、gencode 相关变量。
- `gpu-app-collection/src/Makefile`
  benchmark suite 的主编译入口。新增或修改 workload 时，先看这里如何组织目标。
- `gpu-app-collection/src/cuda/`
  实际 workload 源码所在目录。优先复用相似 workload 的目录结构和 Makefile 模式。

## Benchmark 注册

- `util/job_launching/apps/define-all-apps.yml`
  `run_hw_trace.py -B <suite>` 和 `run_simulations.py -B <suite>` 的标准 benchmark 定义入口。
- `util/job_launching/apps/define-*.yml`
  如果不想污染默认定义，新增自定义 benchmark suite 时优先新建自己的 `define-*.yml`。

定义里最关键的是：

- `exec_dir`
- `data_dirs`
- `execs`
- 每个 exec 的 `args`
- 可选的 `accel-sim-mem`

## Trace 提取

- `util/tracer_nvbit/run_hw_trace.py`
  benchmark 级 trace 主入口；负责运行、后处理和清理。
- `util/tracer_nvbit/README.md`
  tracer 用法、`DYNAMIC_KERNEL_RANGE`、`TRACE_LINEINFO`、手动模式说明。

## Simulation

- `traceL1`
  仓库定制化单 trace 启动脚本。适合输出 L1/L2/issue/HBM trace 或做 ideal L1D 实验。
- `traceL1.md`
  `traceL1` 的中文使用说明。
- `util/job_launching/run_simulations.py`
  标准批量模拟入口。
- `util/job_launching/README.md`
  作业目录、状态检查、stats 收集说明。

## Trace Key 与路径

`traceL1` 不会自动发现任何 trace。它依赖脚本中的 `TRACE_MAP`：

- 新 trace 需要通过 `traceL1 <trace_key>` 使用时，必须为它添加键值。
- `TRACE_MAP` 的值是相对 `TRACE_BASE_DIR` 的 `kernelslist.g` 路径。
- 如果用户只给了真实 trace 路径而没有 trace key，优先使用 `run_simulations.py`，或在得到确认后再补 `TRACE_MAP`。

## 常见输出目录

- `hw_run/traces/`
  硬件 trace 根目录。
- `result/log/`
  `traceL1` 日志。
- `result/L1cache_trace/`
  L1 CSV trace。
- `result/L2cache_trace/`
  L2 CSV trace。
- `result/issue_trace/`
  issue trace。
- `result/bandwidth/`
  HBM 带宽 trace。
