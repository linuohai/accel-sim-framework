# MIGRATION.md — GRASP 研究环境迁移指南

> 最近更新: 2026-04-23
> 用途：单个 Agent（或接手者）按本指南 + `manifest.json` 执行，即可在新服务器上复刻当前 GRASP 预取器研究环境。
> 阅读顺序：TL;DR → §1 前置条件 → §5 新机器复刻步骤。其余章节按需检索。

---

## TL;DR — 一页速览

迁移产出 3 类交付物：

1. **Docker 镜像** `ghcr.io/linuohai/accel-sim-framework:migration-20260423`
   - 基于 NGC PyTorch 24.08 (CUDA 12.6 + cuDNN 9.3 + TensorRT 10.3)
   - 内置 NVBit、已压缩的 IMA 数据集、mini flickr trace 包
   - 预计大小：~28 GB
2. **GitHub 上 4 个自有 fork**（commit SHA 锁在 `manifest.json`）
3. **本目录 `migration/`**（随父仓库 `dev` 分支走）

新机器一键复刻：

```bash
docker login ghcr.io
export HOST_PREFETCH_PATH=/data/prefetch
git clone https://github.com/linuohai/accel-sim-framework.git "$HOST_PREFETCH_PATH"
cd "$HOST_PREFETCH_PATH"
bash migration/restore.sh
```

预计耗时：
- 仅冒烟验证（无 GPU 也可）：**~30 min**
- 含全量 trace 重生成（需 GPU）：**~3 h** with 8 × A100

---

## 1. 前置条件

### 1.1 目标机器

| 项目 | 要求 | 备注 |
|------|------|------|
| OS | Linux x86_64 | Ubuntu 20.04/22.04 验证过 |
| GPU（可选） | NVIDIA A100 80GB PCIe × 1-8 | **无 GPU 也能复刻**，只是不能重生成 trace |
| GPU 驱动 | ≥ 535（原环境 560.35.03） | 若要跑 NVBit tracer |
| Docker | 20.10+ | 需支持 `--gpus all` |
| nvidia-container-toolkit | latest | 同上 |
| 磁盘 | ≥ 300 GB 可用 | image 30G + 代码 1G + trace 67G + result 按需 |
| 公网 | ghcr.io / github.com / pypi.org 可达 | 字节内网外自然满足 |

### 1.2 账号与认证

| 系统 | 要求 |
|------|------|
| GitHub | 能 clone `linuohai/accel-sim-framework` 等 4 个 fork（public 仓库） |
| ghcr.io | `docker login ghcr.io` 用 PAT with `read:packages` |
| Claude Code / Codex | 容器首启后手动 `claude login` / `codex login` |
| POE_API_KEY（可选） | 手填回 `~/.claude/settings.json` 若要继续用 Poe |

---

## 2. 存储数据清单

### 2.1 随 Docker 镜像走

| 容器内路径 | 源 | 压缩前 | 压缩后 (xz -3) |
|-----------|----|-------|---------------|
| 系统 toolchain（NGC PyTorch + CUDA + NVBit） | base image + 定制 | ~10-15 GB | image 总 20 GB |
| `/home/claudeuser/`（去凭证） | 容器内 home | ~50 MB | included |
| `/opt/prefetch_staging/data_dirs.tar.xz` | `gpu-app-collection/data_dirs` | 7.8 GB | ~2-3 GB |
| `/opt/prefetch_staging/gardenia_datasets.tar.xz` | `gpu-app-collection/gardenia/datasets` | 5.1 GB | ~1.5-2 GB |
| `/opt/prefetch_staging/traces_mini.tar`（**新**） | flickr 数据集上的 5 算法 trace | 8 GB | ~8 GB（已是 xz 压缩） |

**镜像 ENV 修正**（commit 时 `--change` 覆盖）：
- `PIP_INDEX_URL=https://pypi.org/simple/`（原值是字节内部 pypi，外网不可达）
- `ACCEL_SIM_HOME=/workspace/prefetch`（原值 `/workspace/accel-sim-framework` 是陈旧路径）

### 2.2 随 Git 走（GitHub 4 个自有 fork）

| 仓库 | 分支 | 内容摘要 |
|------|------|---------|
| `linuohai/accel-sim-framework` | `dev` | 主线；GRASP 脚本、`ima_plan/`、`migration/` |
|  | `mape` | `dev` + MAPE v2 commits |
|  | `exp/sota_stride` | 对应 `worktrees/sota_stride` 工作区 |
| `linuohai/gpgpu-sim_distribution` | `dev` | 主仿真器；含 GRASP 源码 |
|  | `mape` | `dev` + WINSN_TOTAL / DRAM_UTIL_BINS commits |
|  | `exp/sota_stride` | Snake / CAPS / SpareReg baseline 源码 |
| `linuohai/gpu-app-collection` | `dev` | 48 个改动全 commit 到此（通用 build fix + 新 workload 支持） |
| `linuohai/gardenia` | `master` | 图算法实现（BFS/SSSP/CC/BC/SpMV/VC） |

精确 commit SHA 见 `manifest.json`。

### 2.3 新机器重生成（不传）

| 数据 | 命令 | 耗时 | 前提 |
|------|------|------|------|
| `hw_run/traces/` 67.5 GB（paper 70 个子目录） | `bash migration/regenerate_traces.sh` | ~2 h | 8 × A100 + 容器内 NVBit |

**如果目标机器没有 GPU**：
- `regenerate_traces.sh` 会 exit 并提示
- 可使用镜像自带的 mini trace（§2.1 最后一行）跑冒烟 / 5 算法 × flickr 的基础对比
- mini trace 包含 `bfs_cit_sym` 等**不可用**（因为只打包了 flickr 变体）；可用的是 `bfs_flickr_sym`、`sssp_flickr_sym`、`bc_flickr_sym`、`cc_flickr_sym`、`spmv_flickr_sym` 等

`result/` 目录**不重生成**——它是实验产出，每次运行 `./traceL1 ...` 或 `./run_batch_experiments.sh` 时按需生成。迁移后为空是正常。

### 2.4 刻意丢弃（永不出现在任何交付物里）

| 数据 | 原因 |
|------|------|
| `~/.claude/{file-history,history.jsonl,.credentials.json,backups}`、`~/.claude.json` | 含 Claude Code 凭证和历史对话明文 |
| `~/.codex/{auth.json,history.jsonl}` | 含 Codex 凭证 |
| `~/.bash_history`、`~/.viminfo`、`~/.ssh/known_hosts` | 个人痕迹 |
| `result/`、`tmp/`、`worktrees/*/result/` | 实验产出，可重生成 |
| `RohuWmuRbET2.yaml` + 3 个 `.bak` | 字节内部代理配置（含 shadowsocks 密码），**绝不能上传** |
| `/mnt/share` 挂载 | 字节内部共享盘，外网不存在 |

### 2.5 需要人工步骤

| 动作 | 时机 | 操作 |
|------|------|------|
| `claude login` / `codex login` | 容器首启后 | 交互登录，无法自动化 |
| 手填 POE_API_KEY（可选） | 如需继续用 Poe API | `jq` 写回 `~/.claude/settings.json` |
| 升级 nvidia 驱动（可选） | 若新机器驱动 < 535 | 宿主升级 |

---

## 3. 目录布局与 Git 对应

```
<HOST_PREFETCH_PATH>/                            linuohai/accel-sim-framework:dev
├── gpu-simulator/
│   ├── gpgpu-sim/                               linuohai/gpgpu-sim_distribution:dev
│   └── extern/pybind11/                         pybind/pybind11 (上游，只读)
├── gpu-app-collection/                          linuohai/gpu-app-collection:dev
│   ├── gardenia/                                linuohai/gardenia:master
│   └── gardenia/cub/                            upstream cub (上游)
├── ima_plan/01_ima_characterization/
│   ├── pannotia/                                pannotia/pannotia (上游)
│   └── lonestargpu/                             IntelligentSoftwareSystems/GaloisGPU (上游)
└── worktrees/sota_stride/                       accel-sim-framework:exp/sota_stride (worktree)
    └── gpu-simulator/gpgpu-sim/                 gpgpu-sim_distribution:exp/sota_stride (独立 clone)
```

---

## 4. 源机器打包步骤（原始机器上执行一次）

**顺序**：§4.1 Git 整理**先做**，§4.2 Docker 打包**后做**。

理由：bind mount 让两者在数据层面独立，但把代码状态先 push 到 GitHub + SHA 锁到 `manifest.json` 是迁移的可恢复锚点；任何 Docker 阶段的失败（push 超时、磁盘不足等）都不会牵连代码状态。

### 4.1 Git 整理

**顺序**（由叶到根）：
`gpu-app-collection/gardenia` → `gpu-app-collection` → `gpgpu-sim` → 父仓库 → `worktrees/sota_stride/gpu-simulator/gpgpu-sim`

每个 fork 3 步：**(A) 更新 .gitignore → (B) commit 剩余改动 → (C) push**。

#### 4.1.A — 各仓库 .gitignore 追加清单

**父仓库** `/workspace/prefetch/.gitignore` 追加：
```
RohuWmuRbET2.yaml.bak.*
```

**`gpu-app-collection/.gitignore` 追加**：
```
# 编译产物
src/cuda/GPU_Microbenchmark/ubench/**/atomic_add_*
src/cuda/GPU_Microbenchmark/ubench/**/MaxFlops_*
src/cuda/GPU_Microbenchmark/ubench/**/MaxIops_*
src/cuda/GPU_Microbenchmark/ubench/**/config_*
src/cuda/GPU_Microbenchmark/ubench/**/core_config
src/cuda/GPU_Microbenchmark/ubench/**/lat_*
src/cuda/GPU_Microbenchmark/ubench/**/sfu_*
src/cuda/GPU_Microbenchmark/ubench/**/mem_bw
src/cuda/GPU_Microbenchmark/ubench/**/spinlock_*
src/cuda/lonestargpu-2.0/apps/pta/pta
src/cuda/pannotia/color/color_max
src/cuda/pannotia/mis/mis
src/cuda/pannotia/mis/result.out
src/cuda/flashinfer_decode/flashinfer_decode_*

# LaTeX 构建产物
src/cuda/shoc-master/doc/*.aux
src/cuda/shoc-master/doc/*.log
src/cuda/shoc-master/doc/*.out
src/cuda/shoc-master/doc/*.fdb_latexmk
src/cuda/shoc-master/doc/*.fls
src/cuda/shoc-master/doc/*.synctex.gz
```

**`gpu-simulator/gpgpu-sim/.gitignore` 追加**：
```
gpgpu_inst_stats.txt
```

#### 4.1.B — commit 各仓库剩余真正入库的改动

```bash
cd <repo>
git add .gitignore
git commit -m "chore: gitignore build artifacts pre-migration"

# review 剩余 untracked + modified
git status --short

# 手动指定要入库的文件（不用 -A，避免误加）
git add <具体路径>
git commit -m "chore: accumulated pre-migration fixes"
git push origin <branch>
```

**父仓库要特别留意入库的**：
- `docs/superpowers/specs/sim_vs_real_mape_results/`（进 mape 分支）
- `CLAUDE.md` 里 `fa container` → `prefetch-env container` 改名

**gpu-app-collection 要特别留意的**（选项 C：全进 dev）：
- `src/Makefile`（加 flashinfer_decode target）
- `src/cuda/pannotia/graph_parser/parse.cpp`（line buffer 8KB→1MB 修 high-degree 崩溃）
- `src/cuda/lonestargpu-2.0/apps/pta/andersen.cu`（thrust:: 命名空间修复）
- `src/cuda/custom-apps/ima_tiny_case/`（新 IMA test case 源码）
- `src/cuda/flashinfer_decode/{Makefile,README.md}`（新 workload 入口）
- `src/cuda/rodinia/3.1/IMA_workload_selection.md`

**gpgpu-sim 要特别留意的**：
- `configs/tested-cfgs/SM80_A100_1SM_infmq/`（完整）
- `configs/tested-cfgs/SM80_A100_1SM_infmq2/`（缺 trace.config，原样 commit 或补齐后 commit）
- `configs/tested-cfgs/SM80_A100_infmq/`（完整）

#### 4.1.C — 建 mape 分支（仅父仓库 + gpgpu-sim）

```bash
git branch mape dev
git push -u origin mape
```

sota_stride 嵌套的 gpgpu-sim clone 单独 push 到 `exp/sota_stride` 分支：
```bash
cd /workspace/prefetch/worktrees/sota_stride/gpu-simulator/gpgpu-sim
git push origin HEAD:exp/sota_stride
```

#### 4.1.D — 收集所有 commit SHA 写入 manifest.json

见 `migration/manifest.json`，把每个仓库每个分支的 commit SHA 填进去。

### 4.2 Docker 打包（双阶段 commit，不影响源容器）

**原理（关键安全机制）**：
1. `docker commit shn → intermediate` — 仅对源容器做只读快照，pause 几秒，**不改任何文件**
2. `docker run intermediate → migrate-worker` 临时容器（挂相同 bind mount）
3. 在 **migrate-worker（非 shn！）** 里做破坏性操作：清凭证、打包数据集、打包 mini trace
4. `docker commit migrate-worker → 最终镜像` + `--change ENV`
5. `docker push` 最终镜像到 ghcr.io
6. `docker rm -f migrate-worker && docker rmi intermediate` 清理

**整个流程中源容器 `shn` 的文件系统不被修改**，正在使用 `shn` 的 Claude Code / Codex 会话不会掉线。代价：临时占用约 20-30 GB 磁盘、流程多几分钟。

**一键命令**：
```bash
bash migration/docker-bootstrap.sh prepare-and-push shn \
    ghcr.io/linuohai/accel-sim-framework:migration-20260423
```

关键细节：
- 凭证清理发生在 **migrate-worker**，源容器 `shn` 的 `~/.claude/`、`~/.codex/` 不被删
- 打数据集到 migrate-worker 的 `/opt/prefetch_staging/*.tar.xz`
- 打 mini flickr trace 到 migrate-worker 的 `/opt/prefetch_staging/traces_mini.tar`
- commit 时 `--change ENV PIP_INDEX_URL=...`、`--change ENV ACCEL_SIM_HOME=...`
- 脚本会自动从 `shn` 反推 bind mount 源路径（`/data00/shn/workbench/accel-sim-framework`），migrate-worker 会挂同一路径以访问真实数据

---

## 5. 新机器复刻步骤（按顺序，每步独立可重跑）

### 5.1 宿主准备（一次性）

- 装 Docker 20.10+ 和 nvidia-container-toolkit
- `docker login ghcr.io`（PAT with `read:packages`）
- 验证 GPU：`docker run --rm --gpus all nvidia/cuda:12.2.2-base-ubuntu22.04 nvidia-smi`

无 GPU 机器：跳过 GPU 验证，后续 `--gpus all` 改成不传该参数。

### 5.2 宿主：clone 主仓库（迁移第一个动作）

```bash
export HOST_PREFETCH_PATH=/data/prefetch    # 新机器选定的代码根目录
git clone https://github.com/linuohai/accel-sim-framework.git "$HOST_PREFETCH_PATH"
cd "$HOST_PREFETCH_PATH"
```

至此拿到 `migration/` 子目录，后续一切操作的说明书都在这里。

### 5.3 宿主：拉 Docker 镜像

```bash
docker pull ghcr.io/linuohai/accel-sim-framework:migration-20260423
```

下载时间取决于网络；~28 GB 在 100 Mbps 下约 40 min。

### 5.4 宿主：启动容器

```bash
bash migration/docker-bootstrap.sh
```

脚本用 `HOST_PREFETCH_PATH` 做 bind mount，起一个叫 `prefetch-env` 的容器。

验证：`docker ps --filter name=prefetch-env` 应看到 `Up` 状态。

### 5.5 容器内：解压 IMA 数据集 + mini trace

```bash
docker exec prefetch-env bash -c '
  tar -I "xz -T0" -xf /opt/prefetch_staging/data_dirs.tar.xz \
      -C /workspace/prefetch/gpu-app-collection/
  tar -I "xz -T0" -xf /opt/prefetch_staging/gardenia_datasets.tar.xz \
      -C /workspace/prefetch/gpu-app-collection/gardenia/
  tar -xf /opt/prefetch_staging/traces_mini.tar \
      -C /workspace/prefetch/hw_run/traces/device-0/12.6/
'
```

验证：
- `du -sh gpu-app-collection/data_dirs` 应 ≈ 7.8 GB
- `du -sh gpu-app-collection/gardenia/datasets` 应 ≈ 5.1 GB
- `du -sh hw_run/traces/device-0/12.6/` 应 ≈ 8 GB（仅 flickr mini）

### 5.6 容器内：clone 子仓库 + worktree

```bash
docker exec prefetch-env bash -c 'cd /workspace/prefetch && bash migration/clone_subrepos.sh'
```

脚本按 `manifest.json` 里的 SHA clone 3 个自有 fork + 3 个上游只读 clone + worktree。

### 5.7 容器内：编译 accel-sim

```bash
docker exec prefetch-env bash -lc '
  cd /workspace/prefetch
  source gpu-simulator/setup_environment.sh
  make -j -C gpu-simulator/
'
```

产物 `gpu-simulator/bin/release/accel-sim.out`。

### 5.8 容器内：首次登录 agent（交互）

```bash
docker exec -it prefetch-env bash
# 在容器 shell 里：
claude login
codex login
# 可选：手填 POE_API_KEY
jq '.env.POE_API_KEY = "<your-key>"' ~/.claude/settings.json > /tmp/s.json && mv /tmp/s.json ~/.claude/settings.json
```

### 5.9 Smoke test（必过）

有 GPU 或无 GPU 都能跑（仿真器本体是 trace-driven，CPU-only 也运行）：

```bash
docker exec prefetch-env bash -lc '
  cd /workspace/prefetch
  ./traceL1 --max-completed-cta 50 bfs_flickr_sym migration_smoke
  grep "status=COMPLETE" result/log/migration_smoke.log && echo OK || echo FAIL
'
```

预期：终端打印 `status=COMPLETE`，`expected_kernels` 与 `completed_kernels` 一致。

### 5.10 GRASP vs baseline 验证（无 GPU 也可）

```bash
docker exec prefetch-env bash -lc '
  cd /workspace/prefetch
  ./traceL1 --max-completed-cta 200 bfs_flickr_sym bfs_flickr_base
  ./traceL1 --grasp --max-completed-cta 200 bfs_flickr_sym bfs_flickr_grasp
  # 对比 result/log/bfs_flickr_{base,grasp}.log 里的 IPC
'
```

### 一键自动化

上述 5.2–5.9 可由 `migration/restore.sh` 串联执行。出错时脚本打印失败步骤号，定位到 5.X 重跑即可。

---

## 6. Trace 重生成（仅有 GPU 的机器）

```bash
docker exec -it prefetch-env bash
cd /workspace/prefetch
bash migration/regenerate_traces.sh
```

脚本会依次调用原始机器留下的 `generate_traces*.sh`，覆盖 paper 用到的 70 个 `(workload, dataset)` 对。

**无 GPU 的情况**：`regenerate_traces.sh` 会 exit 并提示用 mini bundle。

验证：
```bash
du -sh hw_run/traces/device-0/12.6/    # 应 ≈ 67.5 GB
```

---

## 7. 故障排查

| 症状 | 可能原因 | 处理 |
|------|---------|------|
| `docker pull` 401 Unauthorized | 未登录 ghcr.io 或 PAT 权限不足 | `docker login ghcr.io`，PAT 需 `read:packages` |
| 容器起不来 "permission denied" | 缺 `--privileged` / `--cap-add sys_ptrace` | 核 `docker-bootstrap.sh` 参数 |
| `pip install` 超时 | `PIP_INDEX_URL` 残留 bytedpypi | `env \| grep PIP_`；若残留：`docker run ... -e PIP_INDEX_URL=https://pypi.org/simple/` 覆盖 |
| NVBit tracer 段错误 | 驱动版本不匹配 | 升级宿主 nvidia 驱动 ≥ 535 |
| `regenerate_traces.sh` 找不到数据集 | staging 未解压 | 检查 §5.5 是否完成 |
| Smoke test `status=PARTIAL` / `CRASHED` | 编译失败或 trace 残缺 | 重跑 §5.7 + §5.5；再跑 smoke |
| `clone_subrepos.sh` 报 SHA 不存在 | manifest.json 里的 SHA 还未 push | 检查源机器是否 §4.1.C 完成并 push |
| `git worktree add` 失败 | 目标路径已有文件 | `rm -rf worktrees/sota_stride` 后重跑 |

---

## 8. manifest.json 字段说明

简要字段列表，完整 schema 见 `migration/manifest.json`：

| 字段 | 含义 |
|------|------|
| `version` | 本 manifest 的 schema 版本 |
| `created` | 构建日期 |
| `docker.image` | 镜像完整 tag |
| `docker.registry` | 镜像仓库 host |
| `docker.size_gb` | 镜像大小估计 |
| `repos.<name>.url` | Git clone URL |
| `repos.<name>.path` | 相对 `HOST_PREFETCH_PATH` 的目录 |
| `repos.<name>.branches.<name>.sha` | 锁定的 commit SHA |
| `upstream_readonly.<name>` | 上游只读 clone 信息 |
| `mini_trace_bundle` | docker 内 mini trace 包含哪些 workload |

---

## 9. 本次迁移对 CLAUDE.md 的影响

CLAUDE.md 里若干处提到 "fa container"（例如 "当前工作目录若为 /workspace/prefetch（fa container）可直接操作"），这是过时信息——实际运行的容器叫 `shn`，迁移后新容器命名为 `prefetch-env`。

**迁移完成后需同步修改** CLAUDE.md：
- "fa container" → "prefetch-env container"
- "docker exec fa" → "docker exec prefetch-env"

修改跟 4.1.B 的 commit 一起进 dev 分支。

---

*本指南与 `manifest.json` 是"一份信息两种呈现"：前者给人读，后者给机器解析。两者有冲突时以 `manifest.json` 为准。*
