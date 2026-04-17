# LLM 算子 Sim-vs-Real MAPE 实验 v2 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 跑 41 cfg 的 sim-vs-real MAPE 对比，覆盖 4 个 LLM 算子（FA prefill / decode attention / GEMM / fused_add_rmsnorm），全部 bf16，参数锚定真实模型（LLaMA-2/3.1, Qwen3-32B, GLM-4-9B），产出可发表级报告 + 图表。

**架构：** v2 用独立目录 `result/sim_vs_real_mape_v2/` 镜像 v1 pipeline。脚本从 v1 拷贝扩展支持 2 个新算子（GEMM, RMSNorm）。Workload 脚本改写支持 bf16 + GQA + causal + page_size 参数化。Step C 指标修订（IPC warp 级 / DRAM 加权 util / cache access count）已嵌入 sim 源码 + parser。

**技术栈：** Python 3.10, PyTorch bf16, flash_attn 2.4.2, flashinfer paged kernel, vLLM RMSNorm, GPGPU-Sim/Accel-Sim (含 SC.1/SC.2 修改), NVBit 1.7.4, NCU `sudo -E -n ncu --page raw`, 8× A100 SM80.

**Spec:** [`docs/superpowers/specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md`](../specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md)

**总 cfg：** 41 (FA 11 + Decode 13 + GEMM 12 + RMSNorm 5)，全部 bf16，0 复用 v1。

**Step C 集成策略：** Phase 0.5a（sim 源码 + rebuild）独立完成；其余原 SC.4-SC.8 已**分布到 Phase 2 / Phase 5** 中（脚本/parser 创建时直接含新指标，不分两步）。

---

## 已完成进度（截至 2026-04-17）

| 阶段 | 状态 | 关键 commits |
|---|---|---|
| Spec 冻结 | ✅ | `56d6177`（v2 design）+ `1091426`（Phase 0.5 插入）|
| Plan v1（英文）| ✅ | `63c24dd` |
| **Phase 0.5a** sim 源码 + rebuild（SC.0-SC.3）| ✅ | SC.0 `0358f43`, SC.1 `571e3dc`, SC.2 `c47f09f`, SC.3 concern `0927e71` |
| Plan v2（中文 + 重排序）| 🆕 当前文档 | - |
| Phase 0 通用 prereqs（0.1-0.6）| ⏸️ pending | - |
| Phase 1+ | ⏸️ pending | - |

---

## Phase 0: 通用 Prereqs

### Task 0.0: ~~Step C 指标修订决策~~ ✅ RESOLVED 2026-04-17

用户决定：4 项中 IPC + DRAM + Cache 全做；Issue stage 仅加 `smsp__inst_executed.avg.per_cycle_active`；Stall reasons 不对齐（保持 v1 display-only，因 sim 内部判断路径与 NCU 硬件事件本质不同，强映射会引入 artifact）。已写入 spec §7。

### Task 0.1: cfg_13 Root Cause 排查（≤30 min 人工时间）

**Files:**
- 读：`result/sim_vs_real_mape/sim_logs/cfg_13.log`
- 读：`result/sim_vs_real_mape/traces/cfg_13/traces/kernelslist.g`

- [ ] **Step 1: 识别 kernel-198 是什么**

```bash
grep -A 2 "kernel-198" result/sim_vs_real_mape/sim_logs/cfg_13.log | head -20
ls result/sim_vs_real_mape/traces/cfg_13/traces/ | grep "198\|199\|200"
```

预期：kernel 名（如 CatArrayBatchedCopy）+ trace 文件存在性。

- [ ] **Step 2: 检查 kernel 195-200 的 trace 完整性**

```bash
for k in 195 196 197 198 199 200; do
  f=$(ls result/sim_vs_real_mape/traces/cfg_13/traces/kernel-${k}.* 2>/dev/null | head -1)
  echo "kernel-$k: $f ($(stat -c %s $f 2>/dev/null) bytes)"
done
```

预期：所有 trace 文件存在且非零。

- [ ] **Step 3: 决策**

若 30 min 内定位 root cause：归"简单失败"，v2 中修复。
若超时：归"困难（工具链）"，沉淀到 spec §6，**永久排除 cfg_13 类型（B≥32 decode multi-kernel sequence）**。

- [ ] **Step 4: 更新 spec §6**

编辑 `docs/superpowers/specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md` 中 cfg_13 行的最终归类。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md
git commit -m "docs(spec): finalize cfg_13 classification after 30-min investigation"
```

### Task 0.2: 验证 v2 工具链环境

**Files:** 无（验证 only）

- [ ] **Step 1: 验证 flash_attn 版本 + GQA 支持**

```bash
python3 -c "
import flash_attn
print('flash_attn:', flash_attn.__version__)
from flash_attn import flash_attn_func
import torch
q = torch.randn(1, 128, 32, 128, dtype=torch.bfloat16, device='cuda')
k = torch.randn(1, 128,  8, 128, dtype=torch.bfloat16, device='cuda')
v = torch.randn(1, 128,  8, 128, dtype=torch.bfloat16, device='cuda')
out = flash_attn_func(q, k, v, causal=True)
print('GQA + causal + bf16 OK, output:', out.shape, out.dtype)
"
```

预期：`flash_attn: 2.4.2`，`GQA + causal + bf16 OK, output: torch.Size([1, 128, 32, 128]) torch.bfloat16`。

- [ ] **Step 2: 验证 flashinfer + page_size 参数化**

```bash
python3 -c "
import flashinfer
print('flashinfer:', flashinfer.__version__)
import flashinfer.decode
help(flashinfer.decode.BatchDecodeWithPagedKVCacheWrapper)
" 2>&1 | head -30
```

预期：`page_size` 在 `plan(...)` 或 `forward(...)` 签名中出现。

- [ ] **Step 3: 验证 vLLM RMSNorm 可用性**

```bash
python3 -c "
try:
    from vllm.model_executor.layers.layernorm import RMSNorm
    import torch
    layer = RMSNorm(hidden_size=4096, eps=1e-6).to('cuda', torch.bfloat16)
    x = torch.randn(256, 4096, dtype=torch.bfloat16, device='cuda')
    res = torch.randn(256, 4096, dtype=torch.bfloat16, device='cuda')
    out, new_res = layer(x, residual=res)
    print('vLLM RMSNorm OK:', out.shape, out.dtype)
except ImportError as e:
    print('vLLM not installed:', e)
"
```

预期之一：
- `vLLM RMSNorm OK: torch.Size([256, 4096]) torch.bfloat16` → 用 vLLM
- `vLLM not installed:` → fallback 到 flash_attn `rms_norm`（Task 0.6 中处理）

- [ ] **Step 4: 记录工具链决策**

追加到 `result/sim_vs_real_mape_v2/PREREQ_LOG.md`（已存在，由 SC.0 创建）：

```markdown
## Task 0.2 工具链验证（2026-04-17）

| 工具 | 版本 | 状态 |
|---|---|---|
| flash_attn | <ver> | <OK/issue> |
| flashinfer | <ver>; page_size 参数: <yes/no> | <OK/issue> |
| vLLM | <ver 或未装> | <OK/fallback to flash_attn rms_norm> |
```

### Task 0.3: 改写 fa.py 支持 GQA + causal + bf16

**Files:**
- Modify: `gpu-app-collection/flash_attention/fa.py`

- [ ] **Step 1: Read 当前 fa.py 确认 baseline**

```bash
cat gpu-app-collection/flash_attention/fa.py
```

预期：用 `flash_attn_qkvpacked_func`，dtype=fp16，无 causal arg，无 kv_heads 支持。

- [ ] **Step 2: 全文替换 fa.py**

```python
import argparse
import torch
import flash_attn
from flash_attn import flash_attn_func


def test_flash_attention(batch_size, seqlen, nheads, kv_heads, head_dim):
    print(f"PyTorch: {torch.__version__}, flash_attn: {flash_attn.__version__}")
    print(f"Config: B={batch_size} S={seqlen} H={nheads} kv_H={kv_heads} D={head_dim} causal=True dtype=bf16")

    device = "cuda"
    dtype = torch.bfloat16

    # Q has H heads, K/V have kv_heads (MHA when kv_H==H, else GQA)
    q = torch.randn(batch_size, seqlen, nheads,    head_dim, device=device, dtype=dtype, requires_grad=False)
    k = torch.randn(batch_size, seqlen, kv_heads,  head_dim, device=device, dtype=dtype, requires_grad=False)
    v = torch.randn(batch_size, seqlen, kv_heads,  head_dim, device=device, dtype=dtype, requires_grad=False)

    out = flash_attn_func(q, k, v, causal=True)
    torch.cuda.synchronize()
    print(f"OK. output={tuple(out.shape)} dtype={out.dtype}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--batch_size", type=int, default=1)
    p.add_argument("--seqlen", type=int, default=2048)
    p.add_argument("--nheads", type=int, default=32)
    p.add_argument("--kv_heads", type=int, default=32, help="GQA: kv_heads<nheads; MHA: kv_heads==nheads")
    p.add_argument("--d", type=int, default=128)
    args = p.parse_args()
    test_flash_attention(args.batch_size, args.seqlen, args.nheads, args.kv_heads, args.d)
```

- [ ] **Step 3: Smoke MHA**

```bash
cd gpu-app-collection/flash_attention
python3 fa.py --batch_size 1 --seqlen 512 --nheads 32 --kv_heads 32 --d 128
```

预期：`OK. output=(1, 512, 32, 128) dtype=torch.bfloat16`

- [ ] **Step 4: Smoke GQA 4:1**

```bash
python3 fa.py --batch_size 1 --seqlen 512 --nheads 32 --kv_heads 8 --d 128
```

预期：`OK. output=(1, 512, 32, 128) dtype=torch.bfloat16`

- [ ] **Step 5: Commit**

```bash
git add gpu-app-collection/flash_attention/fa.py
git commit -m "refactor(fa.py): support GQA + causal=True + bf16 via flash_attn_func"
```

### Task 0.4: 扩展 flashinfer_decode.py 加 page_size 参数

**Files:**
- Modify: `gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py`

- [ ] **Step 1: 找 page_size 位置**

```bash
grep -n "page_size\|page-size\|paged" gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py
```

预期：v1 已有 `--page-size` argparse arg。

- [ ] **Step 2: 验证 page_size 接受 {16, 32, 64} 或扩展**

```bash
grep -A 3 "page-size\|page_size" gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py | head -20
```

若 `--page-size` 已 expose：无需改动。
否则：加 `parser.add_argument("--page-size", type=int, default=16)` 并传给 flashinfer wrapper。

- [ ] **Step 3: 切默认 dtype 为 bf16**

找到 dtype 赋值（可能 `torch.float16`），改为 `torch.bfloat16`。加 `--dtype` CLI arg 默认 `bf16`。

- [ ] **Step 4: Smoke**

```bash
cd gpu-app-collection/src/cuda/flashinfer_decode
python3 flashinfer_decode.py --mode paged --batch 1 --seqlen-k 512 \
    --num-heads 32 --num-kv-heads 32 --head-dim 128 \
    --page-size 32 --iters 1 --warmup 0
```

预期：无错误运行，输出含 page_size=32。

- [ ] **Step 5: Commit**

```bash
git add gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py
git commit -m "feat(flashinfer_decode): expose page_size param, default dtype bf16"
```

### Task 0.5: 写 gemm.py

**Files:**
- Create: `gpu-app-collection/src/cuda/gemm/gemm.py`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p gpu-app-collection/src/cuda/gemm
```

- [ ] **Step 2: 写 gemm.py**

```python
import argparse
import torch


def test_gemm(M, K, N, dtype_str="bf16"):
    dtype = torch.bfloat16 if dtype_str == "bf16" else torch.float16
    device = "cuda"

    print(f"GEMM [M={M}, K={K}] @ [K={K}, N={N}] dtype={dtype}")

    a = torch.randn(M, K, dtype=dtype, device=device)
    b = torch.randn(K, N, dtype=dtype, device=device)

    # warmup
    _ = torch.matmul(a, b)
    torch.cuda.synchronize()

    # benchmark call (NVBit 会 trace 这里)
    out = torch.matmul(a, b)
    torch.cuda.synchronize()

    print(f"OK. output={tuple(out.shape)} dtype={out.dtype}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--M", type=int, required=True)
    p.add_argument("--K", type=int, required=True)
    p.add_argument("--N", type=int, required=True)
    p.add_argument("--dtype", type=str, default="bf16", choices=["bf16", "fp16"])
    args = p.parse_args()
    test_gemm(args.M, args.K, args.N, args.dtype)
```

- [ ] **Step 3: Smoke**

```bash
cd gpu-app-collection/src/cuda/gemm
python3 gemm.py --M 1024 --K 4096 --N 11008
```

预期：`OK. output=(1024, 11008) dtype=torch.bfloat16`

- [ ] **Step 4: Commit**

```bash
git add gpu-app-collection/src/cuda/gemm/gemm.py
git commit -m "feat(gemm): add bf16 GEMM benchmark via torch.matmul (cuBLAS)"
```

### Task 0.6: 写 rmsnorm.py

**Files:**
- Create: `gpu-app-collection/src/cuda/rmsnorm/rmsnorm.py`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p gpu-app-collection/src/cuda/rmsnorm
```

- [ ] **Step 2: 写 rmsnorm.py（vLLM 优先 + flash_attn fallback）**

```python
import argparse
import torch


def test_rmsnorm(M, hidden, impl="vllm"):
    device = "cuda"
    dtype = torch.bfloat16

    print(f"RMSNorm M={M} hidden={hidden} impl={impl} dtype=bf16")

    x = torch.randn(M, hidden, dtype=dtype, device=device)
    residual = torch.randn(M, hidden, dtype=dtype, device=device)

    if impl == "vllm":
        from vllm.model_executor.layers.layernorm import RMSNorm
        layer = RMSNorm(hidden_size=hidden, eps=1e-6).to(device, dtype)
        # warmup
        _ = layer(x.clone(), residual=residual.clone())
        torch.cuda.synchronize()
        # benchmark
        out, new_res = layer(x, residual=residual)
    elif impl == "flash_attn":
        from flash_attn.ops.rms_norm import rms_norm
        weight = torch.ones(hidden, dtype=dtype, device=device)
        # warmup
        _ = rms_norm(x + residual, weight, 1e-6)
        torch.cuda.synchronize()
        # benchmark: residual add + rmsnorm fused manually
        added = x + residual
        out = rms_norm(added, weight, 1e-6)
    else:
        raise ValueError(f"unknown impl {impl}")

    torch.cuda.synchronize()
    print(f"OK. output={tuple(out.shape)} dtype={out.dtype}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--M", type=int, required=True)
    p.add_argument("--hidden", type=int, required=True)
    p.add_argument("--impl", type=str, default="vllm", choices=["vllm", "flash_attn"])
    args = p.parse_args()
    test_rmsnorm(args.M, args.hidden, args.impl)
```

- [ ] **Step 3: Smoke（用 Task 0.2 决定的 impl）**

```bash
cd gpu-app-collection/src/cuda/rmsnorm
python3 rmsnorm.py --M 1024 --hidden 4096 --impl vllm
```

预期：`OK. output=(1024, 4096) dtype=torch.bfloat16`

若 vLLM impl 报错：用 `--impl flash_attn` 重试。

- [ ] **Step 4: Commit**

```bash
git add gpu-app-collection/src/cuda/rmsnorm/rmsnorm.py
git commit -m "feat(rmsnorm): add bf16 fused_add_rmsnorm via vLLM (with flash_attn fallback)"
```

---

## Phase 0.5a: Step C 模拟器源码修订（已完成 ✅）

> SC.0-SC.3 已完成。SC.4-SC.8 已**重新分布到 Phase 2 / Phase 5**（脚本/parser 创建时直接含新指标）。

### Task SC.0: 侦察 v1 sim log 字段 ✅
**Commit:** `0358f43`
**结论:** SC.6 范围分类 = A (parser-only)。L1D/L2 cache access count 已 per-kernel emit；`m_num_sim_winsn` 未 emit（确认 SC.1 必须做）；`dram_util_bins` per-DRAM-partition × per-kernel-end 已 emit 但常零。
**输出:** `result/sim_vs_real_mape_v2/PREREQ_LOG.md`

### Task SC.1: 加 WINSN_TOTAL per-kernel dump ✅
**Commits:** submodule `00a11c5`, 父 repo `571e3dc`
**位置:** `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc:1869`（在 `gpu_tot_ipc` printf 之后）
**变更:** 加 10 行 scoped block，遍历所有 SM 累加 `m_shader_stats->m_num_sim_winsn[i]`，emit `WINSN_TOTAL: <value>`。Parser 在 Phase 5 用 `winsn / cycle / 432` 算 warp-IPC。

### Task SC.2: 加 DRAM_UTIL_BINS per-kernel dump ✅
**Commits:** submodule `b341de5`, 父 repo `c47f09f`
**位置:** `gpu-simulator/gpgpu-sim/src/gpgpu-sim/dram.cc:787`（在 `dram_t::print()`）+ `:837`（在 `dram_t::print_stat()`）
**变更:** 加 22 行，emit `DRAM_UTIL_BINS: <b0> ... <b9> (total=<sum>)`。Parser 在 Phase 5 用加权平均算 effective util。

### Task SC.3: rebuild GPGPU-Sim + smoke verify ✅
**Commit:** `0927e71`（concern note）
**结论:** 编译成功；cfg_01 smoke 显示 `WINSN_TOTAL` 2 occurrences（12.9M, 16.9M）+ `DRAM_UTIL_BINS` 80 occurrences（**全零，预期** for small workload）。
**SC.3 Concern:** v1 cfg_03 (s=2k) 的 `dram_util_bins` 也全零，但 reverse-derived util ≠ 0。**Phase 5 Task 5.2 (parse_sim.py) 必须实现 fallback**：bins total=0 时退回 `(rd+wr)*32B/runtime/1555` 反推。

---

## Phase 1: 生成 v2 配置

### Task 1.1: 创建 v2 目录骨架 + gen_configs.py

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/gen_configs.py`

- [ ] **Step 1: 创建目录**

```bash
mkdir -p result/sim_vs_real_mape_v2/{scripts,traces,sim_logs,ncu,parsed,reports,figures}
```

- [ ] **Step 2: 写 gen_configs.py（41 cfg 显式列出）**

```python
"""生成 v2 configs.csv（41 cfg，全 bf16，参数锚定真实模型）。"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "configs.csv"

# Schema: id, workload, label, seq_or_kvlen, batch, nheads, kv_heads, head_dim, page_size, M, K, N, rms_M, rms_hidden, cfg_tag

ROWS = [
    # ─── FA (11 cfg) ────────────────────────────────────────────────────────
    # F1-F4: seq sweep
    ("F1",  "fa", "FA-7B-s512",       512,  1, 32, 32, 128, "", "", "", "", "", "", "F1_FA_7B_s512"),
    ("F2",  "fa", "FA-7B-s1k",       1024,  1, 32, 32, 128, "", "", "", "", "", "", "F2_FA_7B_s1k"),
    ("F3",  "fa", "FA-7B-s2k",       2048,  1, 32, 32, 128, "", "", "", "", "", "", "F3_FA_7B_s2k"),
    ("F4",  "fa", "FA-7B-s4k",       4096,  1, 32, 32, 128, "", "", "", "", "", "", "F4_FA_7B_s4k"),
    # F5: head_dim ablation
    ("F5",  "fa", "FA-7B-s2k-d64",   2048,  1, 32, 32,  64, "", "", "", "", "", "", "F5_FA_7B_s2k_d64"),
    # F6, F7: batch sweep
    ("F6",  "fa", "FA-7B-s2k-B2",    2048,  2, 32, 32, 128, "", "", "", "", "", "", "F6_FA_7B_s2k_B2"),
    ("F7",  "fa", "FA-7B-s2k-B4",    2048,  4, 32, 32, 128, "", "", "", "", "", "", "F7_FA_7B_s2k_B4"),
    # F8-F10: GQA ratio sweep
    ("F8",  "fa", "FA-LLaMA3-8B-s2k",  2048, 1, 32,  8, 128, "", "", "", "", "", "", "F8_FA_LLaMA3_8B_s2k"),
    ("F9",  "fa", "FA-LLaMA3-70B-s2k", 2048, 1, 64,  8, 128, "", "", "", "", "", "", "F9_FA_LLaMA3_70B_s2k"),
    ("F10", "fa", "FA-GLM4-s2k",       2048, 1, 32,  2, 128, "", "", "", "", "", "", "F10_FA_GLM4_s2k"),
    # F11: GQA × long seq crossover
    ("F11", "fa", "FA-LLaMA3-8B-s4k",  4096, 1, 32,  8, 128, "", "", "", "", "", "", "F11_FA_LLaMA3_8B_s4k"),

    # ─── Decode (13 cfg) ────────────────────────────────────────────────────
    # D1-D4: kv_len sweep
    ("D1",  "decode", "DEC-7B-k512",    512, 1, 32, 32, 128, 16, "", "", "", "", "", "D1_DEC_7B_k512"),
    ("D2",  "decode", "DEC-7B-k1k",    1024, 1, 32, 32, 128, 16, "", "", "", "", "", "D2_DEC_7B_k1k"),
    ("D3",  "decode", "DEC-7B-k2k",    2048, 1, 32, 32, 128, 16, "", "", "", "", "", "D3_DEC_7B_k2k"),
    ("D4",  "decode", "DEC-7B-k4k",    4096, 1, 32, 32, 128, 16, "", "", "", "", "", "D4_DEC_7B_k4k"),
    # D5: head_dim ablation
    ("D5",  "decode", "DEC-7B-k2k-d64", 2048, 1, 32, 32, 64, 16, "", "", "", "", "", "D5_DEC_7B_k2k_d64"),
    # D6, D7: batch sweep
    ("D6",  "decode", "DEC-7B-k2k-B2",  2048, 2, 32, 32, 128, 16, "", "", "", "", "", "D6_DEC_7B_k2k_B2"),
    ("D7",  "decode", "DEC-7B-k2k-B4",  2048, 4, 32, 32, 128, 16, "", "", "", "", "", "D7_DEC_7B_k2k_B4"),
    # D8, D9: page_size sweep
    ("D8",  "decode", "DEC-7B-k2k-page32", 2048, 1, 32, 32, 128, 32, "", "", "", "", "", "D8_DEC_7B_k2k_page32"),
    ("D9",  "decode", "DEC-7B-k2k-page64", 2048, 1, 32, 32, 128, 64, "", "", "", "", "", "D9_DEC_7B_k2k_page64"),
    # D10-D12: GQA ratio sweep
    ("D10", "decode", "DEC-LLaMA3-8B-k2k",  2048, 1, 32,  8, 128, 16, "", "", "", "", "", "D10_DEC_LLaMA3_8B_k2k"),
    ("D11", "decode", "DEC-LLaMA3-70B-k2k", 2048, 1, 64,  8, 128, 16, "", "", "", "", "", "D11_DEC_LLaMA3_70B_k2k"),
    ("D12", "decode", "DEC-GLM4-k2k",       2048, 1, 32,  2, 128, 16, "", "", "", "", "", "D12_DEC_GLM4_k2k"),
    # D13: GQA × long KV crossover
    ("D13", "decode", "DEC-LLaMA3-8B-k4k",  4096, 1, 32,  8, 128, 16, "", "", "", "", "", "D13_DEC_LLaMA3_8B_k4k"),

    # ─── GEMM (12 cfg) ──────────────────────────────────────────────────────
    # G1-G5: FFN-up M sweep (LLaMA-2 7B: K=4096, N=11008)
    ("G1",  "gemm", "GEMM-7B-FFN-up-M1",    "", "", "", "", "", "",    1,  4096, 11008, "", "", "G1_GEMM_7B_FFN_up_M1"),
    ("G2",  "gemm", "GEMM-7B-FFN-up-M64",   "", "", "", "", "", "",   64,  4096, 11008, "", "", "G2_GEMM_7B_FFN_up_M64"),
    ("G3",  "gemm", "GEMM-7B-FFN-up-M256",  "", "", "", "", "", "",  256,  4096, 11008, "", "", "G3_GEMM_7B_FFN_up_M256"),
    ("G4",  "gemm", "GEMM-7B-FFN-up-M1024", "", "", "", "", "", "", 1024,  4096, 11008, "", "", "G4_GEMM_7B_FFN_up_M1024"),
    ("G5",  "gemm", "GEMM-7B-FFN-up-M4096", "", "", "", "", "", "", 4096,  4096, 11008, "", "", "G5_GEMM_7B_FFN_up_M4096"),
    # G6: FFN-down (LLaMA-2 7B)
    ("G6",  "gemm", "GEMM-7B-FFN-down-M1024",     "", "", "", "", "", "", 1024, 11008,  4096, "", "", "G6_GEMM_7B_FFN_down_M1024"),
    # G7-G8: FFN-up other models
    ("G7",  "gemm", "GEMM-70B-FFN-up-M1024",      "", "", "", "", "", "", 1024,  8192, 28672, "", "", "G7_GEMM_70B_FFN_up_M1024"),
    ("G8",  "gemm", "GEMM-Qwen3-32B-FFN-up-M1024","", "", "", "", "", "", 1024,  5120, 25600, "", "", "G8_GEMM_Qwen3_32B_FFN_up_M1024"),
    # G9-G11: QKV proj across GQA ratios (注意 N 维由 GQA ratio 决定)
    ("G9",  "gemm", "GEMM-7B-QKV-MHA-M1024",        "", "", "", "", "", "", 1024, 4096, 12288, "", "", "G9_GEMM_7B_QKV_MHA_M1024"),
    ("G10", "gemm", "GEMM-LLaMA3-8B-QKV-GQA4-M1024","", "", "", "", "", "", 1024, 4096,  6144, "", "", "G10_GEMM_LLaMA3_8B_QKV_GQA4_M1024"),
    ("G11", "gemm", "GEMM-GLM4-QKV-GQA16-M1024",    "", "", "", "", "", "", 1024, 4096,  4608, "", "", "G11_GEMM_GLM4_QKV_GQA16_M1024"),
    # G12: O proj (LLaMA-2 7B)
    ("G12", "gemm", "GEMM-7B-O-M1024", "", "", "", "", "", "", 1024, 4096, 4096, "", "", "G12_GEMM_7B_O_M1024"),

    # ─── RMSNorm (5 cfg) ────────────────────────────────────────────────────
    # R1-R3: M sweep at hidden=4096
    ("R1", "rmsnorm", "RMS-7B-M256",          "", "", "", "", "", "", "", "", "",  256, 4096, "R1_RMS_7B_M256"),
    ("R2", "rmsnorm", "RMS-7B-M1024",         "", "", "", "", "", "", "", "", "", 1024, 4096, "R2_RMS_7B_M1024"),
    ("R3", "rmsnorm", "RMS-7B-M4096",         "", "", "", "", "", "", "", "", "", 4096, 4096, "R3_RMS_7B_M4096"),
    # R4-R5: hidden sweep at M=1024
    ("R4", "rmsnorm", "RMS-Qwen3-32B-M1024",  "", "", "", "", "", "", "", "", "", 1024, 5120, "R4_RMS_Qwen3_32B_M1024"),
    ("R5", "rmsnorm", "RMS-70B-M1024",        "", "", "", "", "", "", "", "", "", 1024, 8192, "R5_RMS_70B_M1024"),
]

HEADER = ["id", "workload", "label", "seq", "batch", "nheads", "kv_heads", "head_dim",
          "page_size", "M", "K", "N", "rms_M", "rms_hidden", "cfg_tag"]

with open(OUT, "w", newline="\n") as f:
    w = csv.writer(f, lineterminator="\n")  # 避免 CRLF (v1 教训)
    w.writerow(HEADER)
    for row in ROWS:
        w.writerow(row)

print(f"Wrote {len(ROWS)} rows to {OUT}")
```

- [ ] **Step 3: 跑 gen_configs.py**

```bash
cd /workspace/prefetch
python3 result/sim_vs_real_mape_v2/scripts/gen_configs.py
```

预期：`Wrote 41 rows to .../configs.csv`

- [ ] **Step 4: 验证 CSV（无 CRLF, 42 行 = 1 header + 41 rows）**

```bash
wc -l result/sim_vs_real_mape_v2/scripts/configs.csv
file result/sim_vs_real_mape_v2/scripts/configs.csv
```

预期：`42 ...`，类型 `ASCII text`（**不能**是 `with CRLF line terminators`）。

- [ ] **Step 5: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/gen_configs.py result/sim_vs_real_mape_v2/scripts/configs.csv
git commit -m "feat(v2): add 41-cfg matrix generator + CSV (FA 11 + Decode 13 + GEMM 12 + RMSNorm 5)"
```

> 注意：`result/*` 在 .gitignore 中，需用 `git add -f` 强加。

---

## Phase 2: Pipeline 脚本（trace / sim / ncu，**含 Step C 新 NCU metrics**）

### Task 2.1: 拷贝 + 扩展 run_tracer.sh 支持 4 workload

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/run_tracer.sh`

#### Task 2.1 强制约束: NVBit Kernel 过滤（v2 新增, 防 cfg_13 类失败）

**背景**: cfg_13 失败根因是 PyTorch `DistributionNormal` 等 init kernel 进入了 sim。v2 强制启用 NVBit `DYNAMIC_KERNEL_RANGE` 在 trace 阶段过滤 kernel。

**机制**: `util/tracer_nvbit/tracer_tool/tracer_tool.cu:109` 读取 `DYNAMIC_KERNEL_RANGE` env，语法 `<id_range>@<regex1>,<regex2> ...`，例如 `DYNAMIC_KERNEL_RANGE=".*BatchDecode.*"` 只 trace 名字含 BatchDecode 的 kernel。

**两阶段流程（每算子首次必跑 Discovery）**:

- [ ] **Stage 1: Discovery（每算子一次性，记录到 PREREQ_LOG.md）**
  ```bash
  # 不设 DYNAMIC_KERNEL_RANGE → 全量 trace 一次
  bash run_tracer.sh --discovery <cfg_id>
  # 输出 result/sim_vs_real_mape_v2/discovery/<cfg_id>/kernelslist.g
  cat result/sim_vs_real_mape_v2/discovery/<cfg_id>/kernelslist.g | sort -u
  # 人工/脚本识别哪些是目标 kernel、哪些是 PyTorch init 噪声
  # 把目标 kernel 名 + 派生 regex 写入 PREREQ_LOG.md "Kernel Discovery 表"
  ```

- [ ] **Stage 2: Filter（每 cfg 跑）**
  ```bash
  # configs.csv 新增列 kernel_regex
  DYNAMIC_KERNEL_RANGE="<csv 中读到的 regex>" bash run_tracer.sh --filter <cfg_id>
  ```

- [ ] **Stage 3: Verify（强制至少 2/3 通过）**
  - kernel 数量校验: `wc -l filtered/kernelslist.g` 必须等于 discovery 中目标 kernel 数
  - kernel 名 sanity: `grep -v -E "<expected_substring>" kernelslist.g` 必须为空
  - 总指令数 sanity: sim 后 `gpu_tot_sim_insn` 与 discovery 累加目标 kernel 指令数在 ±5% 内（事后做）

**Fallback (regex 漏抓时)**: 若 Stage 3 失败，改用精确 kernel ID range（例如 `DYNAMIC_KERNEL_RANGE="50-50@.*"`）兜底。ID 来自 discovery 阶段记录。

**`run_tracer.sh` 实现要点**:
- 必须支持 `--discovery` 和 `--filter` 两种模式
- `--filter` 模式从 `configs.csv` 读 `kernel_regex` 列
- 每次 trace 后自动跑 verification 脚本，fail 则非零退出

**`gen_configs.py` (Task 1.1) 调整**:
- `configs.csv` 新增列 `kernel_regex`，初始填 placeholder `TBD`，由 Discovery 阶段填充

- [ ] **Step 1: 读 v1 run_tracer.sh 作 baseline**

```bash
cat result/sim_vs_real_mape/scripts/run_tracer.sh
```

- [ ] **Step 2: 写扩展版 v2 run_tracer.sh**

```bash
#!/usr/bin/env bash
# Usage: run_tracer.sh <cfg_id>
# Emits accel-sim trace to result/sim_vs_real_mape_v2/traces/<cfg_tag>/traces/kernelslist.g
set -euo pipefail

CFG_ID="${1:?cfg_id required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CFGS="$ROOT/result/sim_vs_real_mape_v2/scripts/configs.csv"

ROW=$(awk -F, -v id="$CFG_ID" 'NR>1 && $1==id' "$CFGS" | tr -d '\r')
[ -z "$ROW" ] && { echo "config $CFG_ID not found"; exit 1; }

IFS=, read -r id workload label seq batch nheads kv_heads head_dim page_size M K N rms_M rms_hidden cfg_tag <<<"$ROW"

OUT_DIR="$ROOT/result/sim_vs_real_mape_v2/traces/$cfg_tag"
mkdir -p "$OUT_DIR"

TRACER_SO="$ROOT/util/tracer_nvbit/tracer_tool/tracer_tool.so"
[ -f "$TRACER_SO" ] || { echo "tracer_tool.so not found at $TRACER_SO"; exit 2; }
POST_PROC="$ROOT/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing"
[ -f "$POST_PROC" ] || { echo "post-traces-processing not found at $POST_PROC"; exit 2; }

cd "$OUT_DIR"

case "$workload" in
    fa)
        CMD=(python3 "$ROOT/gpu-app-collection/flash_attention/fa.py"
             --batch_size "$batch" --seqlen "$seq" --nheads "$nheads"
             --kv_heads "$kv_heads" --d "$head_dim")
        ;;
    decode)
        CMD=(python3 "$ROOT/gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py"
             --mode paged --batch "$batch" --seqlen-k "$seq"
             --num-heads "$nheads" --num-kv-heads "$kv_heads" --head-dim "$head_dim"
             --page-size "$page_size" --iters 1 --warmup 0 --dtype bf16)
        ;;
    gemm)
        CMD=(python3 "$ROOT/gpu-app-collection/src/cuda/gemm/gemm.py"
             --M "$M" --K "$K" --N "$N" --dtype bf16)
        ;;
    rmsnorm)
        CMD=(python3 "$ROOT/gpu-app-collection/src/cuda/rmsnorm/rmsnorm.py"
             --M "$rms_M" --hidden "$rms_hidden" --impl vllm)
        ;;
    *)
        echo "unknown workload: $workload"; exit 4
        ;;
esac

echo "[cfg $CFG_ID] tracing: ${CMD[*]}"
rm -f traces/*.trace traces/*.traceg traces/*.trace.xz traces/*.traceg.xz traces/kernelslist traces/kernelslist.g 2>/dev/null || true

DYNAMIC_KERNEL_RANGE="" TRACES_FOLDER="$OUT_DIR" \
    CUDA_INJECTION64_PATH="$TRACER_SO" "${CMD[@]}" 2>&1 | tee trace.log

echo "[cfg $CFG_ID] running post-traces-processing..."
"$POST_PROC" "$OUT_DIR/traces" 2>&1 | tee -a trace.log
rm -f "$OUT_DIR/traces"/*.trace 2>/dev/null || true

if [ ! -f traces/kernelslist.g ]; then
    echo "[cfg $CFG_ID] FAILED — traces/kernelslist.g not produced"
    tail -30 trace.log
    exit 3
fi
echo "[cfg $CFG_ID] done. trace at $OUT_DIR/traces/kernelslist.g"
{ ls -la traces/ | head -10; } || true
```

- [ ] **Step 3: chmod +x**

```bash
chmod +x result/sim_vs_real_mape_v2/scripts/run_tracer.sh
```

- [ ] **Step 4: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/run_tracer.sh
git commit -m "feat(v2): add run_tracer.sh for 4 workloads (fa/decode/gemm/rmsnorm), bf16"
```

### Task 2.2: 拷贝 + 扩展 run_sim.sh

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/run_sim.sh`

- [ ] **Step 1: 拷贝 v1 sim 脚本 + 调整路径**

```bash
cp result/sim_vs_real_mape/scripts/run_sim.sh result/sim_vs_real_mape_v2/scripts/run_sim.sh
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/run_sim.sh
```

- [ ] **Step 2: 更新 CSV 列解析适配新 schema（15 列）**

编辑 `result/sim_vs_real_mape_v2/scripts/run_sim.sh`，找：

```bash
IFS=, read -r id workload label seq batch nheads kv_heads head_dim reuse cfg_tag <<<"$ROW"
```

替换为：

```bash
IFS=, read -r id workload label seq batch nheads kv_heads head_dim page_size M K N rms_M rms_hidden cfg_tag <<<"$ROW"
```

（cfg_tag 之后的字段 sim 不用，只要 cfg_tag 和 workload 即可。）

- [ ] **Step 3: 验证语法**

```bash
bash -n result/sim_vs_real_mape_v2/scripts/run_sim.sh && echo "syntax OK"
```

- [ ] **Step 4: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/run_sim.sh
git commit -m "feat(v2): add run_sim.sh — copy of v1 with v2 paths and 15-col CSV schema"
```

### Task 2.3: 创建 run_ncu.sh（**含 Step C 新 metrics — 集成原 SC.4**）

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/run_ncu.sh`

> **Step C 集成说明**：直接在创建时含 5 项 cache + 1 项 execution rate metrics，避免分两步。

- [ ] **Step 1: 拷贝 v1 + 调整路径**

```bash
cp result/sim_vs_real_mape/scripts/run_ncu.sh result/sim_vs_real_mape_v2/scripts/run_ncu.sh
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/run_ncu.sh
```

- [ ] **Step 2: 更新 CSV 解析（同 Task 2.2 Step 2）**

- [ ] **Step 3: 添加 4 workload case 分支（fa / decode / gemm / rmsnorm）**

镜像 run_tracer.sh Task 2.1 Step 2 中的 case 分支。

- [ ] **Step 4: 扩展 --metrics 列表（Step C 集成）**

找到 ncu 命令的 `--metrics` 参数（v1 已有 sm__throughput, dram__throughput, l1tex hit, lts hit），扩展为：

```bash
--metrics \
  sm__throughput.avg.pct_of_peak_sustained_elapsed,\
  dram__throughput.avg.pct_of_peak_sustained_elapsed,\
  l1tex__t_sector_hit_rate.pct,\
  lts__t_sector_hit_rate.pct,\
  smsp__inst_executed.avg.per_cycle_active,\
  l1tex__t_sectors.sum,\
  l1tex__t_sectors_pipe_lsu_mem_global_op_ld.sum,\
  l1tex__t_sectors_pipe_lsu_mem_global_op_st.sum,\
  l1tex__t_sectors_hit.sum,\
  lts__t_sectors.sum,\
  lts__t_sectors_op_read.sum,\
  lts__t_sectors_op_write.sum
```

（保留 v1 已有的 stall reasons metrics，因 stall display-only 仍需要。）

- [ ] **Step 5: chmod + 验证语法**

```bash
chmod +x result/sim_vs_real_mape_v2/scripts/run_ncu.sh
bash -n result/sim_vs_real_mape_v2/scripts/run_ncu.sh && echo "syntax OK"
```

- [ ] **Step 6: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/run_ncu.sh
git commit -m "feat(v2): add run_ncu.sh for 4 workloads + Step C cache/exec_rate metrics"
```

---

## Phase 3: Smoke Tests（4 个代表 cfg，1 per 算子）

### Task 3.1: Smoke FA (cfg F3 = FA-7B-s2k)

**Files:** 无（跑脚本 only）

- [ ] **Step 1: Trace**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh F3
```

预期：trace.log 显示 MHA + causal + bf16 + `OK. output=(1, 2048, 32, 128) dtype=torch.bfloat16`。kernelslist.g 存在。

- [ ] **Step 2: NCU profile**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh F3
```

预期：ncu CSV 写入 `result/sim_vs_real_mape_v2/ncu/F3_FA_7B_s2k.csv`，含 row 与 kernel 名匹配 `flash_fwd*`，并含 cache sectors / inst_executed 列。

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh F3
```

预期：sim log 末尾 `EXPERIMENT SUMMARY` 含 `status=COMPLETE`、`gpu_tot_ipc`、`gpu_tot_sim_cycle`、`WINSN_TOTAL:`、`DRAM_UTIL_BINS:`。

- [ ] **Step 4: 验证输出**

```bash
ls -la result/sim_vs_real_mape_v2/{traces/F3_FA_7B_s2k/traces/kernelslist.g,sim_logs/F3_FA_7B_s2k.log,ncu/F3_FA_7B_s2k.csv}
```

3 个文件均非零字节。

### Task 3.2: Smoke Decode (cfg D3 = DEC-7B-k2k)

- [ ] **Step 1: Trace**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh D3
```

预期：trace.log 显示 decode kernel 启动，B=1, kv_len=2048, H=32, kv_H=32, page_size=16, dtype=bf16。

- [ ] **Step 2: NCU profile**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh D3
```

预期：CSV 含 kernel 名匹配 `flashinfer*` 或 `BatchDecodeWithPagedKVCache*`。

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh D3
```

预期：`EXPERIMENT SUMMARY status=COMPLETE`。

- [ ] **Step 4: 验证 3 个文件**

```bash
ls -la result/sim_vs_real_mape_v2/{traces/D3_DEC_7B_k2k/traces/kernelslist.g,sim_logs/D3_DEC_7B_k2k.log,ncu/D3_DEC_7B_k2k.csv}
```

### Task 3.3: Smoke GEMM (cfg G4 = GEMM-7B-FFN-up-M1024)

- [ ] **Step 1: Trace**

```bash
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh G4
```

预期：`GEMM [M=1024, K=4096] @ [K=4096, N=11008] dtype=torch.bfloat16` 和 `OK. output=(1024, 11008)`。

- [ ] **Step 2: NCU**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh G4
```

预期：kernel 名匹配 `ampere_bf16_s16816gemm*` / `sm80_xmma_gemm_*` / `cutlass_80_tensorop_bf16*`。**注意：若不匹配，head -3 看实际 kernel 名，更新 KERNEL_PATTERNS regex（见 Phase 5 Task 5.1）。**

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh G4
```

预期：`EXPERIMENT SUMMARY status=COMPLETE`。GEMM compute-bound：高 IPC (>0.5 warp-IPC) + 低 DRAM util (<30%)。

- [ ] **Step 4: 验证 3 个文件**

### Task 3.4: Smoke RMSNorm (cfg R2 = RMS-7B-M1024)

- [ ] **Step 1: Trace**

```bash
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh R2
```

预期：`RMSNorm M=1024 hidden=4096 impl=vllm dtype=bf16` 和 `OK. output=(1024, 4096)`。

- [ ] **Step 2: NCU**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh R2
```

预期：kernel 名匹配 `rms_norm*` / `vllm::ops::rms_norm*` / `fused_add_rms_norm*`。

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh R2
```

预期：`EXPERIMENT SUMMARY status=COMPLETE`。RMSNorm bandwidth-bound：高 DRAM util (>60%) + 低 IPC。

- [ ] **Step 4: 验证 3 个文件**

### Checkpoint A: 用户审 4 smoke tests

- [ ] **暂停等用户**

打印 4 smoke 总结：F3 / D3 / G4 / R2 各 3 stage（trace / ncu / sim）状态 + kernel 名匹配情况。

询问用户：
> "4 个 smoke test 全部通过，可以进入 bulk run 了吗？"

得到用户明确"yes" 后才进入 Phase 4。

---

## Phase 4: Bulk Execution（37 剩余 cfg）

### Task 4.1: Bulk Trace（37 cfg，1 GPU 顺序）

- [ ] **Step 1: 识别剩余 cfg id**（除 smoke）

Smoke = {F3, D3, G4, R2}。剩余 37 = 其他全部。

- [ ] **Step 2: Loop with retry-once**

```bash
cd /workspace/prefetch
for id in F1 F2 F4 F5 F6 F7 F8 F9 F10 F11 \
          D1 D2 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 \
          G1 G2 G3 G5 G6 G7 G8 G9 G10 G11 G12 \
          R1 R3 R4 R5; do
    echo "=== TRACE cfg $id ==="
    ./result/sim_vs_real_mape_v2/scripts/run_tracer.sh "$id" 2>&1 | tee -a result/sim_vs_real_mape_v2/bulk_trace.log
    if [ $? -ne 0 ]; then
        echo "FAILED $id; retrying once after 5s..."
        sleep 5
        ./result/sim_vs_real_mape_v2/scripts/run_tracer.sh "$id" 2>&1 | tee -a result/sim_vs_real_mape_v2/bulk_trace.log
    fi
done
```

预期 wall time：~1.5-2h（NVBit 在 1 GPU 上顺序）。

- [ ] **Step 3: 验证 41 个 trace 全部存在**

```bash
for id in F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 \
          D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 \
          G1 G2 G3 G4 G5 G6 G7 G8 G9 G10 G11 G12 \
          R1 R2 R3 R4 R5; do
    tag=$(awk -F, -v i="$id" 'NR>1 && $1==i {print $NF}' result/sim_vs_real_mape_v2/scripts/configs.csv | tr -d '\r')
    f="result/sim_vs_real_mape_v2/traces/$tag/traces/kernelslist.g"
    [ -f "$f" ] && echo "OK $id" || echo "MISSING $id ($tag)"
done | sort | uniq -c | head
```

预期：41 行 OK。

### Task 4.2: Bulk NCU（37 cfg，1 GPU 顺序）

- [ ] **Step 1: Loop**

```bash
cd /workspace/prefetch
for id in F1 F2 F4 F5 F6 F7 F8 F9 F10 F11 \
          D1 D2 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 \
          G1 G2 G3 G5 G6 G7 G8 G9 G10 G11 G12 \
          R1 R3 R4 R5; do
    echo "=== NCU cfg $id ==="
    ./result/sim_vs_real_mape_v2/scripts/run_ncu.sh "$id" 2>&1 | tee -a result/sim_vs_real_mape_v2/bulk_ncu.log
done
```

预期 wall time：~1-1.5h。

- [ ] **Step 2: 验证 41 个 ncu CSV 存在**

```bash
ls result/sim_vs_real_mape_v2/ncu/*.csv | wc -l
```

预期：41。

### Task 4.3: Bulk Sim（37 cfg，CPU 8-way 并行）

- [ ] **Step 1: 用 xargs -P 8 跑**

```bash
cd /workspace/prefetch
echo "F1 F2 F4 F5 F6 F7 F8 F9 F10 F11 \
      D1 D2 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 \
      G1 G2 G3 G5 G6 G7 G8 G9 G10 G11 G12 \
      R1 R3 R4 R5" | tr ' ' '\n' \
    | xargs -P 8 -I{} bash -c './result/sim_vs_real_mape_v2/scripts/run_sim.sh {} 2>&1 | tail -5'
```

预期 wall time：~3-5h（受 sim 单 job 内存制约）。

- [ ] **Step 2: 验证 41 个 sim log 全部 status=COMPLETE**

```bash
for f in result/sim_vs_real_mape_v2/sim_logs/*.log; do
    status=$(grep "^status=" "$f" | tail -1)
    echo "$(basename $f): $status"
done | grep -c COMPLETE
```

预期：41。

若 <41：排查失败 cfg，按 spec §6 分类（简单/困难/未明），记入 `result/sim_vs_real_mape_v2/FAILED_CFGS.md`，决定重试 / 修 / 沉淀。

---

## Phase 5: Parsers + 分析（**含 Step C 集成 — 原 SC.5/6/7/8**）

### Task 5.1: 创建 parse_ncu.py（**直接含 Step C 新指标 — 集成原 SC.5**）

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/parse_ncu.py`

> **Step C 集成**：parser 一次性写好支持 5 项 cache + 1 项 execution rate，不用先写再扩展。

- [ ] **Step 1: 拷贝 v1 parser**

```bash
cp result/sim_vs_real_mape/scripts/parse_ncu.py result/sim_vs_real_mape_v2/scripts/parse_ncu.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/parse_ncu.py
```

- [ ] **Step 2: 扩展 KERNEL_PATTERNS 字典支持 4 workload**

编辑 `result/sim_vs_real_mape_v2/scripts/parse_ncu.py`。找 kernel 名 filter（可能是 `re.match("flash_fwd|flashinfer", ...)`）。替换为：

```python
KERNEL_PATTERNS = {
    "fa":      re.compile(r"flash_fwd|flash_attn"),
    "decode":  re.compile(r"flashinfer|BatchDecode|BatchPrefillWithPagedKV"),
    "gemm":    re.compile(r"cublas.*gemm|ampere_.*16x|sm80.*gemm|cutlass.*gemm"),
    "rmsnorm": re.compile(r"rms_norm|RMSNorm|vllm.*norm"),
}

def filter_kernel(workload, kernel_name):
    pat = KERNEL_PATTERNS.get(workload)
    return pat is not None and bool(pat.search(kernel_name))
```

迭代 ncu CSV 行时用此 filter。

- [ ] **Step 3: 加 Step C 新字段提取**

在 per-kernel 字段 dict，加：

```python
new_fields = {
    "l1_sectors_total":    "l1tex__t_sectors.sum",
    "l1_sectors_load":     "l1tex__t_sectors_pipe_lsu_mem_global_op_ld.sum",
    "l1_sectors_store":    "l1tex__t_sectors_pipe_lsu_mem_global_op_st.sum",
    "l1_sectors_hit":      "l1tex__t_sectors_hit.sum",
    "l2_sectors_total":    "lts__t_sectors.sum",
    "l2_sectors_read":     "lts__t_sectors_op_read.sum",
    "l2_sectors_write":    "lts__t_sectors_op_write.sum",
    "exec_rate_per_cycle": "smsp__inst_executed.avg.per_cycle_active",
}
```

按这些 mapping 迭代 row dict，写入 per-kernel JSON。

- [ ] **Step 4: Smoke**

```bash
python3 result/sim_vs_real_mape_v2/scripts/parse_ncu.py F3
python3 -c "import json; d=json.load(open('result/sim_vs_real_mape_v2/parsed/F3_FA_7B_s2k_ncu.json')); print({k:v for k,v in d.items() if 'sector' in k or 'exec' in k})"
```

预期：JSON 含全部 8 个新字段且非空。

- [ ] **Step 5: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/parse_ncu.py
git commit -m "feat(v2): parse_ncu.py — 4 workloads + Step C cache sectors + exec_rate"
```

### Task 5.2: 创建 parse_sim.py（**直接含 WINSN/DRAM bins/cache 解析 — 集成原 SC.6**）

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/parse_sim.py`

> **Step C 集成 + SC.3 fallback**：直接含 WINSN / DRAM bins 解析；DRAM bins 全零时 fallback 到 v1 reverse-derive。

- [ ] **Step 1: 拷贝 v1 parser**

```bash
cp result/sim_vs_real_mape/scripts/parse_sim.py result/sim_vs_real_mape_v2/scripts/parse_sim.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/parse_sim.py
```

- [ ] **Step 2: 扩展 KERNEL_PATTERNS 支持 4 workload**（同 Task 5.1 Step 2）

- [ ] **Step 3: 加 WINSN_TOTAL → warp-IPC 解析**

per-kernel block 中加：

```python
m = re.search(r"WINSN_TOTAL:\s+(\d+)", block)
winsn_total = int(m.group(1)) if m else None
warp_ipc_per_scheduler = (winsn_total / cycle_total / 432.0) if winsn_total else None  # 108 SMs × 4 schedulers
```

替换原 thread-active IPC 计算，将 `warp_ipc_per_scheduler` 作为主 IPC 指标。

- [ ] **Step 4: 加 DRAM_UTIL_BINS → 加权 util 解析（含 fallback）**

```python
m = re.search(r"DRAM_UTIL_BINS:\s+([\d\s]+?)\s*\(total=(\d+)\)", block)
if m:
    bins = list(map(int, m.group(1).split()))   # 10 ints
    total = int(m.group(2))
    if total > 0:
        # 加权平均：bin i 代表 [10i%, 10(i+1)%) 范围；中点 = 10i+5
        dram_util_pct = sum((10 * i + 5) * bins[i] for i in range(10)) / total
    else:
        # SC.3 concern fallback: bins 全零时退回 v1 reverse-derive
        dram_bytes = (total_mem_r + total_mem_w) * 32
        runtime_s = total_cycles / (1410 * 1e6)
        dram_util_pct = (dram_bytes / runtime_s / 1555e9 * 100) if runtime_s > 0 else None
        # 标记为 fallback 来源
        dram_util_source = "reverse_derive_fallback"
else:
    dram_util_pct = None
```

- [ ] **Step 5: 加 cache access count 解析**

直接从 sim log 提取（per SC.0 confirmed available）：

```python
m = re.search(r"L1D_total_cache_accesses\s*=\s*(\d+)", block)
l1_access = int(m.group(1)) if m else None
m = re.search(r"L1D_total_cache_misses\s*=\s*(\d+)", block)
l1_miss = int(m.group(1)) if m else None
m = re.search(r"L2_total_cache_accesses\s*=\s*(\d+)", block)
l2_access = int(m.group(1)) if m else None
m = re.search(r"L2_total_cache_misses\s*=\s*(\d+)", block)
l2_miss = int(m.group(1)) if m else None
l1_hit_rate = (1 - l1_miss / l1_access) if l1_access else None
l2_hit_rate = (1 - l2_miss / l2_access) if l2_access else None
```

- [ ] **Step 6: Smoke 在 v1 cfg_03（用 v1 cfg id 测）**

```bash
# 临时跑：parser 接受 v1 sim log 也可以
python3 -c "
import sys
sys.path.insert(0, 'result/sim_vs_real_mape_v2/scripts')
from parse_sim import parse_sim_log
import json
result = parse_sim_log('result/sim_vs_real_mape/sim_logs/cfg_03.log', kernel_filter='flash_fwd')
print(json.dumps(result, indent=2))
"
```

- [ ] **Step 7: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/parse_sim.py
git commit -m "feat(v2): parse_sim.py — WINSN warp-IPC, DRAM bins (with fallback), cache access count"
```

### Task 5.3: 跑全 41 cfg parse

- [ ] **Step 1: Loop 两个 parser**

```bash
cd /workspace/prefetch
for id in F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 \
          D1 D2 D3 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 \
          G1 G2 G3 G4 G5 G6 G7 G8 G9 G10 G11 G12 \
          R1 R2 R3 R4 R5; do
    python3 result/sim_vs_real_mape_v2/scripts/parse_ncu.py "$id"
    python3 result/sim_vs_real_mape_v2/scripts/parse_sim.py "$id"
done 2>&1 | tee result/sim_vs_real_mape_v2/parse.log
```

预期：82 个 JSON 文件（41 ncu + 41 sim）写入 `result/sim_vs_real_mape_v2/parsed/`。

- [ ] **Step 2: 验证数量**

```bash
ls result/sim_vs_real_mape_v2/parsed/*.json | wc -l
```

预期：82。

### Task 5.4: collect_metrics.py → merged_metrics.csv（**含 Step C 新 column — 集成原 SC.7**）

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/collect_metrics.py`

- [ ] **Step 1: 拷贝 + 调整路径**

```bash
cp result/sim_vs_real_mape/scripts/collect_metrics.py result/sim_vs_real_mape_v2/scripts/collect_metrics.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/collect_metrics.py
```

- [ ] **Step 2: 更新 CSV 列名按 v2 schema**

打开 `collect_metrics.py`，找读 configs.csv 的代码。确认按字段名访问（`row["label"]`）而非位置 index。若按位置，refactor 为 dict。

- [ ] **Step 3: 加 Step C 新列**

加列对（sim_X, real_X）：
- `l1_sectors_total`, `l1_sectors_hit`, `l1_hit_rate_weighted` (= hit/total)
- `l2_sectors_total`, `l2_sectors_hit`, `l2_hit_rate_weighted`
- `exec_rate_per_cycle` (NCU only — sim 用 winsn 等价)

主指标升级：
- `ipc_warp` (替代 `ipc` thread-based)
- `dram_util_weighted` (替代 `dram_util` reverse-derived)

- [ ] **Step 4: 跑 + 验证**

```bash
cd /workspace/prefetch
python3 result/sim_vs_real_mape_v2/scripts/collect_metrics.py
head -3 result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
wc -l result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
```

预期：42 行（1 header + 41 cfg），header 含新列。

- [ ] **Step 5: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/collect_metrics.py result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
git commit -m "feat(v2): collect_metrics — 41 cfg + Step C cache/IPC_warp/DRAM_weighted columns"
```

### Task 5.5: classify_bottleneck.py（用新 IPC/DRAM 指标）

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py`

- [ ] **Step 1: 拷贝 v1**

```bash
cp result/sim_vs_real_mape/scripts/classify_bottleneck.py result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py
```

- [ ] **Step 2: 校准阈值（IPC 量纲变了）**

v1 IPC 是 thread-active scaled (0-32 per scheduler)；v2 IPC 是 warp-IPC (0-1 per scheduler)。校准 1/32 scaling 或重新设阈值。

- [ ] **Step 3: 跑 + 验证**

```bash
python3 result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py
head -5 result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
```

预期：merged_metrics.csv 多了 `sim_class`, `real_class`, `agree` 列。期待一致率 ≥30-50%（v1 18% 因 IPC + DRAM 单位错；v2 修正后应改善）。

- [ ] **Step 4: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
git commit -m "feat(v2): classify_bottleneck.py — sim/real/agree using new warp-IPC + weighted DRAM"
```

### Task 5.6: SC.8 Smoke 验证 — v1 cfg_03 IPC/DRAM 改善

**Files:** 无（验证 only）

> **集成原 SC.8**：在 41 cfg parse 完后，单独验证 v2 修订对 v1 cfg_03 的 IPC + DRAM MAPE 改善。

- [ ] **Step 1: 用新 sim binary 重跑 v1 cfg_03**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape/scripts/run_sim.sh 3
```

注意：用 v1 的 `run_sim.sh`（指向 v1 路径），重写 v1 cfg_03 sim log 含新 WINSN_TOTAL + DRAM_UTIL_BINS 行。

- [ ] **Step 2: 用 v2 parser 解析 v1 cfg_03 log**

```bash
python3 -c "
import sys
sys.path.insert(0, 'result/sim_vs_real_mape_v2/scripts')
from parse_sim import parse_sim_log
import json
result = parse_sim_log('result/sim_vs_real_mape/sim_logs/cfg_03.log', kernel_filter='flash_fwd')
print(json.dumps(result, indent=2))
"
```

- [ ] **Step 3: 与 v1 NCU ground truth 对比**

```bash
cat result/sim_vs_real_mape/parsed/cfg_03_ncu.json | python3 -m json.tool | grep -E "ipc|dram_util"
```

- [ ] **Step 4: 计算 IPC MAPE 改善**

`|sim_ipc_warp - ncu_ipc| / ncu_ipc * 100`

预期：< 34%（v1 baseline）。目标：~5-15%。

- [ ] **Step 5: 计算 DRAM util MAPE 改善**

`|sim_dram_weighted - ncu_dram_pct|`（绝对 pp）

预期：< 52pp（v1 baseline）。目标：~5-20pp。

- [ ] **Step 6: 文档化结果**

追加到 `result/sim_vs_real_mape_v2/PREREQ_LOG.md`：

```markdown
## SC.8 Smoke 验证（2026-04-17，v1 cfg_03 用新 sim + parsers）

| 指标 | v1 sim | v1 NCU | v1 MAPE | v2 sim | v2 MAPE | Δ |
|---|---|---|---|---|---|---|
| IPC | <v1> | <ncu> | 34% | <v2> | <new> | <improvement> |
| DRAM util | <v1> | <ncu> | 52pp | <v2> | <new> | <improvement> |

**判断**: <改善可接受 / 退化 / 需进一步调查>
```

- [ ] **Step 7: Commit + Phase 5 完成**

```bash
git add -f result/sim_vs_real_mape_v2/PREREQ_LOG.md
git commit -m "chore(v2): SC.8 smoke validation — Step C metrics improvement on cfg_03"
```

### Checkpoint B: 用户审 tables

- [ ] **暂停等用户**

打印总结表：
- 41 cfg total，X sim 有效，Y/X 分类一致率
- runtime / IPC / DRAM / L1 / L2 平均 MAPE per algo

询问用户：
> "数据合理吗？想调阈值或加额外指标吗？OK 后进入图表生成。"

得到用户 "yes" 后才进入 Phase 6。

---

## Phase 6: 报告 + 图表

### Task 6.1: make_report.py → mape_report.md

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/make_report.py`

- [ ] **Step 1: 拷贝 v1**

```bash
cp result/sim_vs_real_mape/scripts/make_report.py result/sim_vs_real_mape_v2/scripts/make_report.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/make_report.py
```

- [ ] **Step 2: 加 per-algo MAPE breakdown（4 算子）**

编辑 `make_report.py`，加按 `workload` 字段 group merged_metrics.csv 并报 per-workload MAPE for runtime / IPC / DRAM / L1 / L2 的 section。

```python
import pandas as pd
df = pd.read_csv("result/sim_vs_real_mape_v2/parsed/merged_metrics.csv")
for workload in ["fa", "decode", "gemm", "rmsnorm"]:
    sub = df[df["label"].str.startswith(workload[:2].upper()) | df["id"].str.startswith(workload[0].upper())]
    print(f"\n## {workload}: {len(sub)} cfgs")
    print(f"  runtime MAPE = {((sub['runtime_real']-sub['runtime_sim']).abs()/sub['runtime_real']).mean()*100:.1f}%")
    # ... similar for IPC, DRAM, L1, L2
```

- [ ] **Step 3: 跑 + 验证**

```bash
python3 result/sim_vs_real_mape_v2/scripts/make_report.py
ls result/sim_vs_real_mape_v2/reports/mape_report.md
```

- [ ] **Step 4: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/make_report.py result/sim_vs_real_mape_v2/reports/mape_report.md
git commit -m "feat(v2): make_report.py — per-algo MAPE for 4 workloads"
```

### Task 6.2: Fig 1 (Roofline) — 4 panels

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig1_roofline.py`

- [ ] **Step 1: 拷贝 v1 + 调整路径**

```bash
cp result/sim_vs_real_mape/scripts/fig1_roofline.py result/sim_vs_real_mape_v2/scripts/fig1_roofline.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig1_roofline.py
```

- [ ] **Step 2: 改 4 panels（v1 是 2 panel）**

把 `fig, axes = plt.subplots(1, 2, ...)` → `plt.subplots(2, 2, ...)`。每个 panel filter merged_metrics.csv 对应 workload 的 cfg，画 AI vs achieved TFLOPS + 3 ceilings (L1 15 TB/s, L2 3.35 TB/s, HBM 1.56 TB/s) + compute ceiling 312 TFLOPS。

- [ ] **Step 3: 跑 + 视觉检查**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig1_roofline.py
ls result/sim_vs_real_mape_v2/figures/fig1_roofline.{pdf,svg}
```

- [ ] **Step 4: Commit**

```bash
git add -f result/sim_vs_real_mape_v2/scripts/fig1_roofline.py result/sim_vs_real_mape_v2/figures/fig1_roofline.{pdf,svg}
git commit -m "feat(v2): fig1 roofline — 4 panels (FA/Decode/GEMM/RMSNorm) with 3 mem ceilings"
```

### Task 6.3: Fig 2 (MAPE breakdown for 4 algos)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py`

- [ ] **Step 1: 拷贝 + 扩展 x 轴**

```bash
cp result/sim_vs_real_mape/scripts/fig2_mape_breakdown.py result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py
```

把 x 轴从 "FA / Decode" 扩展为 "FA / Decode / GEMM / RMSNorm"。保留 5 metric subpanel（runtime/IPC 用 rel MAPE；DRAM/L1/L2 用 abs pp）。

- [ ] **Step 2: 跑 + Commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py
git add -f result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py result/sim_vs_real_mape_v2/figures/fig2_mape_breakdown.{pdf,svg}
git commit -m "feat(v2): fig2 MAPE breakdown — 4 algos × 5 metrics"
```

### Task 6.4: Fig 3 (Trajectory — 多轴 sweep 曲线)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py`

- [ ] **Step 1: 拷贝 + 4 subplot**

```bash
cp result/sim_vs_real_mape/scripts/fig3_trajectory.py result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py
```

4 subplot：
- (a) FA seq sweep: x=seq, y=runtime/IPC/DRAM (real vs sim)
- (b) Decode kv_len sweep: x=kv_len, y=...
- (c) GEMM M sweep: x=log(M), y=achieved TFLOPS (real vs sim)
- (d) RMSNorm M sweep: x=log(M), y=achieved bandwidth GB/s

- [ ] **Step 2: 跑 + Commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py
git add -f result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py result/sim_vs_real_mape_v2/figures/fig3_trajectory.{pdf,svg}
git commit -m "feat(v2): fig3 trajectory — 4 algos primary-axis sweeps"
```

### Task 6.5: Fig 4 (Stall stacked, 41 cfg)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py`

- [ ] **Step 1: 拷贝 + 调 x 轴 label**

```bash
cp result/sim_vs_real_mape/scripts/fig4_stall_stacked.py result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py
```

布局：41 cfg × 2 bar (sim | real) on x-axis。可能需要 landscape 宽 figsize；按 algo 加分隔线。

> **注意**：stall display-only（spec §7 决定不算 MAPE）。两边各画一套，让读者看 shape distribution，但不强行映射。

- [ ] **Step 2: 跑 + Commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py
git add -f result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py result/sim_vs_real_mape_v2/figures/fig4_stall_stacked.{pdf,svg}
git commit -m "feat(v2): fig4 stall stacked — 41 cfgs grouped by algo (display-only)"
```

### Task 6.6: Fig 5 (NEW: GEMM shape pattern comparison)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig5_gemm_shape_pattern.py`

v2 特有图表，展示 QKV vs O vs FFN-up vs FFN-down 4 种 pattern 在 runtime/IPC/DRAM 的差异，real vs sim 对比。

- [ ] **Step 1: 写 fig5 from scratch**

```python
"""Fig 5: GEMM shape pattern comparison — QKV (3 GQA ratios) | O | FFN-up | FFN-down"""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, figsize_full, save_fig, CB10, HATCHES, annotate_bars

apply_style()

df = pd.read_csv(REPO / "result/sim_vs_real_mape_v2/parsed/merged_metrics.csv")
gemm = df[df["id"].str.startswith("G")]

pattern_map = {
    "G1": "FFN-up M=1", "G2": "FFN-up M=64", "G3": "FFN-up M=256",
    "G4": "FFN-up M=1024", "G5": "FFN-up M=4096",
    "G6": "FFN-down", "G7": "FFN-up 70B", "G8": "FFN-up Qwen3-32B",
    "G9": "QKV MHA", "G10": "QKV GQA 4:1", "G11": "QKV GQA 16:1",
    "G12": "O proj",
}
gemm = gemm.assign(pattern=gemm["id"].map(pattern_map))

fig, ax = plt.subplots(figsize=figsize_full(height=3.0))
x = range(len(gemm))
w = 0.4
ax.bar([i - w/2 for i in x], gemm["runtime_real"], width=w, label="Real (NCU)", color=CB10[0])
ax.bar([i + w/2 for i in x], gemm["runtime_sim"], width=w, label="Sim (Accel-Sim)", color=CB10[2], hatch=HATCHES[1])
ax.set_xticks(list(x))
ax.set_xticklabels(gemm["pattern"], rotation=45, ha="right")
ax.set_ylabel("Runtime (ms)")
ax.legend(loc="upper left")
ax.set_title("GEMM shape pattern: real vs sim runtime")

save_fig(fig, "fig5_gemm_shape_pattern", REPO / "result/sim_vs_real_mape_v2/figures")
plt.close(fig)
```

- [ ] **Step 2: 跑 + Commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig5_gemm_shape_pattern.py
git add -f result/sim_vs_real_mape_v2/scripts/fig5_gemm_shape_pattern.py result/sim_vs_real_mape_v2/figures/fig5_gemm_shape_pattern.{pdf,svg}
git commit -m "feat(v2): fig5 GEMM shape pattern (QKV / O / FFN-up / FFN-down)"
```

---

## Phase 7: 交付物 + Session Review

### Task 7.1: 拷贝 v2 交付物到 docs/

**Files:**
- Create: `docs/superpowers/specs/sim_vs_real_mape_v2_results/mape_report.md`
- Create: `docs/superpowers/specs/sim_vs_real_mape_v2_results/figures/*.pdf`

- [ ] **Step 1: 拷贝 report + figures + merged_metrics**

```bash
mkdir -p docs/superpowers/specs/sim_vs_real_mape_v2_results/figures
cp result/sim_vs_real_mape_v2/reports/mape_report.md docs/superpowers/specs/sim_vs_real_mape_v2_results/
cp result/sim_vs_real_mape_v2/figures/*.pdf docs/superpowers/specs/sim_vs_real_mape_v2_results/figures/
cp result/sim_vs_real_mape_v2/parsed/merged_metrics.csv docs/superpowers/specs/sim_vs_real_mape_v2_results/
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/sim_vs_real_mape_v2_results/
git commit -m "docs(results): v2 sim-vs-real MAPE deliverables (41 cfg, 4 ops, bf16, 5 figs)"
```

### Task 7.2: 更新 Feishu doc

- [ ] **Step 1: 追加 v2 section 到 Feishu doc**

用 `mcp__feishu__update-doc` 追加 v2 results section 到现有 doc `AoMsdhMk4oruflxMswicxNx1neb`。含：4 算子总结表、per-algo MAPE、分类一致率、本地 figure 链接（用户需手动上传）。

### Task 7.3: 跑 /session-review

- [ ] **Step 1: 调 session-review skill**

会检查 INDEX.md 新鲜度、experiment_progress.md 更新、新 globally-relevant 脚本是否注册到 CLAUDE.md。

```
/session-review
```

---

## Self-Review 清单（执行前最后一查）

- [ ] **Spec 覆盖**: spec 每个 section 都有 task 实现：
  - §0 v2 升级目标 8 项 → all addressed (dtype/FA impl/multi-axis/Step C 都在 plan)
  - §1 P1-P5 设计原则 → enforced via cfg constraints
  - §3 model anchors → 在 configs.csv
  - §3.5 实现选型 → Task 0.3-0.6
  - §4.1-§4.4 矩阵 → Task 1.1
  - §6 失败档案 → Task 0.1 (cfg_13 排查)
  - §7 Step C → Phase 0.5a (已完成) + Task 2.3 (NCU metrics) + Task 5.1/5.2 (parser) + Task 5.6 (验证)
  - §9 open issues → Task 0.0 已 RESOLVED + 0.1 + 0.2 待办

- [ ] **占位符扫描**: 无 "TBD" / "implement later" / "see Task N" 无代码。

- [ ] **类型/路径一致**: 所有路径用 `result/sim_vs_real_mape_v2/`；CSV schema (15 列) 在 gen_configs.py / run_*.sh / parse_*.py 一致。

- [ ] **Workflow gates**: Checkpoint A (smoke 审) 和 Checkpoint B (table 审) 都需用户 "yes" 才进下一阶段。

---

## 估时

| Phase | 时间 |
|---|---|
| Phase 0.5a (sim 源码 + rebuild) | ✅ 已完成 |
| Phase 0 (通用 prereqs) | 1-2h |
| Phase 1 (configs.csv) | 30min |
| Phase 2 (scripts 含 SC.4) | 1-1.5h |
| Phase 3 (smoke 4 cfg) | 30min-1h |
| Phase 4 (bulk 37 cfg, 8-way 并行 sim) | 5-7h |
| Phase 5 (parsers 含 SC.5/6/7 + SC.8 验证) | 1.5-2h |
| Phase 6 (figures 5 张) | 2-3h |
| Phase 7 (deliverables) | 30min |
| **Total（剩余）** | **~12-17h**（1.5-2 工作日）|

---

## Risk Register

| 风险 | 概率 | 缓解 |
|---|---|---|
| vLLM 未装 | 中 | Task 0.2 Step 3 验证；fallback flash_attn rms_norm |
| flashinfer page_size 不可参数化 | 低 | Task 0.4 验证；不行则改 flashinfer_decode.py |
| FA F7 (B=4 s2k) sim CTA 预算超 | 低-中 | 看 sim log；hang 则 drop F7 + 文档化 |
| GEMM kernel name regex 没匹配 cublas variant | 中 | Task 3.3 Step 2 验证；不匹配看 head -3 实际 kernel 名，改 regex |
| Decode page_size=64 sim runtime 爆炸 | 低 | 看 D9 sim 时间；>2× D8 则文档化为 sim 限制 |
| 多 cfg sim 失败模式与 cfg_13 类似 | 中 | 应用 Task 0.1 的 30-min 规则；沉淀到 spec §6 |
| **DRAM_UTIL_BINS 全零（SC.3 concern）** | **高** | parse_sim.py 已实现 fallback（bins total=0 退回 reverse-derive），见 Task 5.2 Step 4 |
