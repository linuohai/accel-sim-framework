---
name: gpu-trace-sim-pipeline
description: End-to-end workflow for repo-integrated GPU workloads in /workspace/prefetch, from designing or registering a CUDA or graph workload in gpu-app-collection to compiling it, generating NVBit hardware traces, and running trace-driven GPGPU-Sim or Accel-Sim experiments. Use when requests mention Gardenia, Rodinia, custom repo workloads, run_hw_trace.py, traceL1, kernelslist.g, run_simulations.py, issue or cache traces, ideal L1D experiments, or failures anywhere between build, trace extraction, and simulation.
---

# GPU Trace Sim Pipeline

## Overview

使用这个 skill 为 `/workspace/prefetch` 内的 workload 走通一条稳定主路径：接入或设计程序、编译、在真实 GPU 上提取 NVBit trace、再进入 GPGPU-Sim/Accel-Sim 的 trace-driven 模拟。优先复用仓库已有入口，不要临时拼接一套平行流程。

## Constraints

- 在 `fa` 容器内工作，并把工作目录视为 `/workspace/prefetch`。
- 对任何仓库文件做改动前，先给出变更方案并等待用户确认。
- 不要使用 `git reset --hard`、`git checkout --` 或其他回退/重置类命令。
- 把“硬件提 trace 需要真实 GPU”当作硬约束；没有 GPU 时，只能转向已有 trace 或下载 trace，不能假装完成 trace 提取。
- 优先使用仓库已有脚本：`gpu-app-collection/src/setup_environment`、`util/tracer_nvbit/run_hw_trace.py`、`traceL1`、`util/job_launching/run_simulations.py`。

## Workflow Decision Tree

- 用户只想复用已有 trace 跑模拟：
  直接走“Step 4: Run Simulation”，并按需读取 `references/repo-entrypoints.md`。
- workload 已存在，但还没有 trace：
  先走“Step 1-3”，确认 build 与 trace 产物，再进入模拟。
- 用户要新增或改造仓库内 workload：
  先给变更方案，确认后再修改 `gpu-app-collection`、benchmark 定义或 `traceL1` 映射。
- 用户在 build、trace、simulation 任一步失败：
  读取 `references/failure-modes.md`，不要直接猜测原因。

## Step 1: Ground the Environment

先确认环境，再决定下一步，不要在不完整环境上盲跑命令。

- 检查当前目录是否为 `/workspace/prefetch`。
- 检查 `CUDA_INSTALL_PATH`、`nvcc --version`、`python3 --version`，必要时再看 `nvidia-smi`。
- 编译 workload 前，优先 `source gpu-app-collection/src/setup_environment`。
- 编译模拟器前，优先 `source gpu-simulator/setup_environment.sh`。
- 如果用户要新增 workload，先定位它属于哪个家族目录，再看是否需要补 benchmark 定义和 trace key。

精确命令、路径和检查点见 `references/workflow.md`。

## Step 2: Design or Register the Workload

优先把新程序接入仓库现有 workload 体系，而不是创建孤立入口。

- 将源码放到 `gpu-app-collection/src/` 下合适的子目录，尽量复用同类 workload 的 Makefile 和目录布局。
- 需要通过 `run_hw_trace.py -B <suite>` 或 `run_simulations.py -B <suite>` 访问时，把 benchmark 注册到 `util/job_launching/apps/define-all-apps.yml` 或同目录自定义 `define-*.yml`。
- 需要通过 `./traceL1 <trace_key>` 快速跑时，再为新 trace 增加 `TRACE_MAP` 键。
- 只在用户明确要求 repo 修改并确认方案后，才执行这些编辑。

仓库入口和编辑点见 `references/repo-entrypoints.md`。

## Step 3: Compile and Extract Trace

先把 workload 和 tracer 分开看待：应用二进制要能运行，tracer 工具要能注入。

1. 编译 workload。
2. 构建 `util/tracer_nvbit/` 下的 tracer。
3. 在真实 GPU 上运行 `run_hw_trace.py` 生成 trace。
4. 验证目标目录里已经出现 `kernelslist.g`，再进入模拟。

关键原则：

- 对 repo-integrated workload，优先使用 `run_hw_trace.py -B <suite> -D <gpu-id>`。
- 把 `kernelslist.g` 当成进入模拟前的最小验收件。
- 如果只看到原始 `kernel-*.trace` 而没有 `kernelslist.g`，说明 trace 后处理未完成或失败。
- 需要源代码行号映射时，再开启 `TRACE_LINEINFO=1` 并重新编译应用。

完整命令和输出目录见 `references/workflow.md`。

## Step 4: Run Simulation

根据用户目标在两条模拟入口之间切换：

- 需要仓库自定义的 L1/L2/issue/HBM trace、ideal L1D、快速对比实验：
  优先使用 `traceL1`，前提是 trace 已经有对应 `TRACE_MAP` 键。
- 需要标准批量作业管理、状态监控、stats 收集：
  使用 `util/job_launching/run_simulations.py`，再配合 `job_status.py`、`monitor_func_test.py`、`get_stats.py`。

运行后至少报告这些事实：

- 使用的 benchmark 或 trace key
- `kernelslist.g` 的真实路径
- 配置名，例如 `SM80_A100` 或 yaml 中定义的 config
- 输出目录，例如 `result/log/`、`result/L1cache_trace/`、`result/issue_trace/`
- 为了提速或控盘启用过哪些限制，例如 `--max-completed-cta`、`--max-cycle`、`--no-issue-trace`

## References

- 读取 `references/workflow.md` 获取端到端 SOP、命令模板和标准产物路径。
- 读取 `references/repo-entrypoints.md` 获取仓库内关键入口、注册点和何时编辑它们。
- 读取 `references/failure-modes.md` 获取常见失败模式、排查顺序和替代路径。
