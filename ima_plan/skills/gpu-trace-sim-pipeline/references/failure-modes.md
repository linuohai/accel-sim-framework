# Failure Modes

按“先环境，后产物，最后配置”的顺序排查。

## `CUDA_INSTALL_PATH` 为空或 `nvcc` 不存在

现象：

- `gpu-app-collection/src/setup_environment` 报错
- `nvcc --version` 失败
- 编译 Makefile 直接退出

处理：

```bash
export CUDA_INSTALL_PATH=<cuda-root>
export PATH=$CUDA_INSTALL_PATH/bin:$PATH
source gpu-app-collection/src/setup_environment
```

## 没有真实 GPU，无法提硬件 trace

现象：

- `nvidia-smi` 不可用
- `run_hw_trace.py` 无法启动或找不到设备

处理：

- 不要继续 trace 主路径
- 转为使用已有 trace 或下载 trace
- 向用户明确说明“当前无法完成硬件 trace 提取”

## 编译成功，但 `run_hw_trace.py -B <suite>` 找不到 benchmark

现象：

- suite 名不在定义文件里
- 可执行文件名和 yaml 定义不一致

处理：

- 检查 `util/job_launching/apps/define-all-apps.yml`
- 如需新增 suite，优先新建 `define-*.yml`
- 检查 `exec_dir`、`execs` 和真实二进制名称是否匹配

## trace 目录里没有 `kernelslist.g`

现象：

- 只有 `kernel-*.trace`
- 只有 `kernelslist`
- trace 目录为空

处理：

- 先确认 workload 实际运行到了 kernel launch
- 再确认 tracer 后处理是否完成
- 不要在没有 `kernelslist.g` 时直接进入模拟

## `traceL1` 报 trace key 不存在

现象：

- `traceL1` 无法识别 `<trace_key>`

处理：

- 先搜索 `traceL1` 中的 `TRACE_MAP`
- 如果用户只是想跑现有 trace 路径，改用 `run_simulations.py`
- 如果确实要纳入 `traceL1`，先给出补 `TRACE_MAP` 的修改方案并等待确认

## `run_simulations.py` 找不到 trace 或 config

现象：

- `-T` 指向的目录层级错误
- `-C` 名称不在配置 yaml 中

处理：

- 核对 `./hw_run/traces/device-<gpu-id>/<cuda-version>/`
- 核对 `util/job_launching/configs/define-standard-cfgs.yml`
- 优先用实际存在的 `kernelslist.g` 反推上层 trace 根目录

## issue trace 太大或跑太慢

现象：

- `result/issue_trace/` 激增
- 仿真受 IO 或压缩拖慢

处理：

- 快速验证时加 `--no-issue-trace`
- 或用 `--issue-trace-compress gzip`
- 或限制 `--max-cycle` / `--max-completed-cta`

## source 顺序混乱导致环境不一致

现象：

- 能编 workload 但不能编 simulator
- `CUDA_VERSION`、`GPUAPPS_ROOT`、`GPGPUSIM_ROOT` 混乱

处理：

- workload 相关命令前先 `source gpu-app-collection/src/setup_environment`
- simulator 相关命令前先 `source gpu-simulator/setup_environment.sh`
- 在每段流程开始前重新打印关键环境变量，不要依赖旧 shell 记忆
