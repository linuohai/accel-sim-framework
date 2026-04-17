# LLM Operator Sim-vs-Real MAPE Experiment v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run 41-cfg sim-vs-real MAPE comparison across 4 LLM operators (FA prefill, decode attention, GEMM, fused_add_rmsnorm) all in bf16, anchored to real models (LLaMA-2/3.1, Qwen3, GLM-4), and produce a publication-quality report with figures.

**Architecture:** v2 is a self-contained directory `result/sim_vs_real_mape_v2/` that mirrors v1's pipeline (trace → sim/ncu → parse → collect → classify → report → figures). Scripts are copied from v1 and extended for the 2 new operators. Workload scripts (`fa.py`, `flashinfer_decode.py`) are rewritten / extended for bf16 + GQA + causal + page_size parameterization. New `gemm.py` and `rmsnorm.py` are written from scratch.

**Tech Stack:** Python 3.10, PyTorch (bf16), flash_attn 2.4.2, flashinfer (paged kernel), vLLM RMSNorm, GPGPU-Sim/Accel-Sim, NVBit 1.7.4, Nsight Compute (sudo -E -n ncu --page raw), 8× A100 SM80.

**Spec:** [docs/superpowers/specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md](../specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md)

**Total cfg:** 41 (FA 11 + Decode 13 + GEMM 12 + RMSNorm 5), all bf16, 0 reuse from v1.

---

## Phase 0: Prereqs and Decision Points

### Task 0.0: Decision Gate — Step C Metric Revisions

**Context:** Spec §9 Open Issue 1 says Step C (IPC warp counter, DRAM bins, Cache access count, Issue stage细分) needs to be discussed before v2 实施。

**Files:** None (decision/discussion only)

- [ ] **Step 1: Review Step C scope with user**

Read spec §7 to confirm 5 metric revision items. Ask user:
> "v2 在跑 41 cfg 之前是否要先实施 Step C 指标修订？4 项修订选哪几项？还是 v2 用现有指标跑完，Step C 留给 v3？"

- [ ] **Step 2: Document decision in plan**

Append decision to spec §9 Open Issue 1 as a resolution note (do not edit the issue itself), or update the open issue if different.

- [ ] **Step 3: Commit decision**

```bash
git add docs/superpowers/specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md
git commit -m "docs(spec): resolve v2 Step C metric revision decision"
```

### Task 0.1: cfg_13 Root Cause Investigation (≤30 min)

**Context:** Spec §6 says we have a 30-min window to investigate v1 cfg_13 (DEC-k2k-B32) sim bail at kernel-198.

**Files:**
- Read: `result/sim_vs_real_mape/sim_logs/cfg_13.log`
- Read: `result/sim_vs_real_mape/traces/cfg_13/traces/kernelslist.g`

- [ ] **Step 1: Identify what kernel-198 is**

```bash
grep -A 2 "kernel-198" result/sim_vs_real_mape/sim_logs/cfg_13.log | head -20
ls result/sim_vs_real_mape/traces/cfg_13/traces/ | grep "198\|199\|200"
```

Expected: Kernel name (e.g. CatArrayBatchedCopy) and trace file presence.

- [ ] **Step 2: Check trace integrity for kernels 195-200**

```bash
for k in 195 196 197 198 199 200; do
  f=$(ls result/sim_vs_real_mape/traces/cfg_13/traces/kernel-${k}.* 2>/dev/null | head -1)
  echo "kernel-$k: $f ($(stat -c %s $f 2>/dev/null) bytes)"
done
```

Expected: All trace files present with non-zero size.

- [ ] **Step 3: Decision**

If root cause found in <30 min: classify as **simple failure**, fix in v2. Document fix.
If not: classify as **困难（工具链）**, sediment to spec §6, **永久排除 cfg_13 类型 (B≥32 decode multi-kernel sequence)**.

- [ ] **Step 4: Update spec §6 with finding**

Edit `docs/superpowers/specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md` row for cfg_13 with final classification.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-16-llm-op-sim-vs-real-mape-v2-design.md
git commit -m "docs(spec): finalize cfg_13 classification after 30-min investigation"
```

### Task 0.2: Verify v2 Tooling Environment

**Files:** None (verification only)

- [ ] **Step 1: Verify flash_attn version + GQA support**

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

Expected: `flash_attn: 2.4.2`, `GQA + causal + bf16 OK, output: torch.Size([1, 128, 32, 128]) torch.bfloat16`.

If fails: install `pip install flash_attn==2.4.2` (already installed per session memory).

- [ ] **Step 2: Verify flashinfer + page_size parameterization**

```bash
python3 -c "
import flashinfer
print('flashinfer:', flashinfer.__version__)
import flashinfer.decode
help(flashinfer.decode.BatchDecodeWithPagedKVCacheWrapper)
" 2>&1 | head -30
```

Expected: page_size shows as a settable parameter in `plan(...)` or `forward(...)` signature.

- [ ] **Step 3: Verify vLLM RMSNorm availability**

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

Expected one of:
- `vLLM RMSNorm OK: torch.Size([256, 4096]) torch.bfloat16` → use vLLM
- `vLLM not installed:` → fallback path needed (Task 0.6)

- [ ] **Step 4: Document tooling decisions**

Create `result/sim_vs_real_mape_v2/PREREQ_LOG.md`:

```markdown
# v2 Prereq Verification Log (2026-04-17)

| Tool | Version | Status |
|---|---|---|
| flash_attn | <ver> | <OK/issue> |
| flashinfer | <ver>; page_size param: <yes/no> | <OK/issue> |
| vLLM | <ver or not installed> | <OK/fallback to flash_attn rms_norm> |
```

### Task 0.3: Rewrite fa.py for GQA + causal + bf16

**Files:**
- Modify: `gpu-app-collection/flash_attention/fa.py`

- [ ] **Step 1: Read current fa.py to confirm baseline**

```bash
cat gpu-app-collection/flash_attention/fa.py
```

Expected: uses `flash_attn_qkvpacked_func`, dtype=fp16, no causal arg, no kv_heads support.

- [ ] **Step 2: Rewrite fa.py**

Replace entire file with:

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

    # Q has H heads, K/V have kv_heads (supports MHA when kv_H==H, else GQA)
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

- [ ] **Step 3: Smoke test new fa.py — MHA mode**

```bash
cd gpu-app-collection/flash_attention
python3 fa.py --batch_size 1 --seqlen 512 --nheads 32 --kv_heads 32 --d 128
```

Expected: `OK. output=(1, 512, 32, 128) dtype=torch.bfloat16`

- [ ] **Step 4: Smoke test — GQA 4:1 mode**

```bash
python3 fa.py --batch_size 1 --seqlen 512 --nheads 32 --kv_heads 8 --d 128
```

Expected: `OK. output=(1, 512, 32, 128) dtype=torch.bfloat16`

- [ ] **Step 5: Commit**

```bash
git add gpu-app-collection/flash_attention/fa.py
git commit -m "refactor(fa.py): support GQA + causal=True + bf16 via flash_attn_func"
```

### Task 0.4: Extend flashinfer_decode.py with page_size param

**Files:**
- Modify: `gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py`

- [ ] **Step 1: Read current script to find page_size location**

```bash
grep -n "page_size\|page-size\|paged" gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py
```

Expected: existing argparse arg `--page-size` (per v1 trace command).

- [ ] **Step 2: Verify page_size already accepts {16, 32, 64} or extend if needed**

```bash
grep -A 3 "page-size\|page_size" gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py | head -20
```

If page_size is already exposed as `--page-size`: no change needed, mark this task done.
If not: add `parser.add_argument("--page-size", type=int, default=16)` and pass to flashinfer wrapper.

- [ ] **Step 3: Switch dtype default to bf16**

Find dtype assignment (likely `torch.float16`) and change to `torch.bfloat16`. Add `--dtype` CLI arg with default `bf16`.

- [ ] **Step 4: Smoke test**

```bash
cd gpu-app-collection/src/cuda/flashinfer_decode
python3 flashinfer_decode.py --mode paged --batch 1 --seqlen-k 512 \
    --num-heads 32 --num-kv-heads 32 --head-dim 128 \
    --page-size 32 --iters 1 --warmup 0
```

Expected: runs without error, output mentions page_size=32.

- [ ] **Step 5: Commit**

```bash
git add gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py
git commit -m "feat(flashinfer_decode): expose page_size param, default dtype bf16"
```

### Task 0.5: Write gemm.py

**Files:**
- Create: `gpu-app-collection/src/cuda/gemm/gemm.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p gpu-app-collection/src/cuda/gemm
```

- [ ] **Step 2: Write gemm.py**

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

    # benchmark call (NVBit will trace this)
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

- [ ] **Step 3: Smoke test**

```bash
cd gpu-app-collection/src/cuda/gemm
python3 gemm.py --M 1024 --K 4096 --N 11008
```

Expected: `OK. output=(1024, 11008) dtype=torch.bfloat16`

- [ ] **Step 4: Commit**

```bash
git add gpu-app-collection/src/cuda/gemm/gemm.py
git commit -m "feat(gemm): add bf16 GEMM benchmark via torch.matmul (cuBLAS)"
```

### Task 0.6: Write rmsnorm.py

**Files:**
- Create: `gpu-app-collection/src/cuda/rmsnorm/rmsnorm.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p gpu-app-collection/src/cuda/rmsnorm
```

- [ ] **Step 2: Write rmsnorm.py (with vLLM primary + flash_attn fallback)**

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

- [ ] **Step 3: Smoke test (use impl decided in Task 0.2 Step 3)**

```bash
cd gpu-app-collection/src/cuda/rmsnorm
python3 rmsnorm.py --M 1024 --hidden 4096 --impl vllm
```

Expected: `OK. output=(1024, 4096) dtype=torch.bfloat16`

If vLLM impl errors: re-run with `--impl flash_attn`.

- [ ] **Step 4: Commit**

```bash
git add gpu-app-collection/src/cuda/rmsnorm/rmsnorm.py
git commit -m "feat(rmsnorm): add bf16 fused_add_rmsnorm via vLLM (with flash_attn fallback)"
```

---

---

## Phase 0.5: Step C Metric Revisions (BEFORE Phase 1 bulk)

> Decided 2026-04-17 (spec §7 update + Open Issue 1 resolved). Implements 3 of 4 Step C items + drops stall alignment as architectural artifact.

### Task SC.0: Reconnaissance — what does v1 sim log already emit?

**Files:** None (read-only)

- [ ] **Step 1: Grep v1 sim log for cache/IPC related fields**

```bash
cd /workspace/prefetch
LOG="result/sim_vs_real_mape/sim_logs/cfg_03.log"
[ -f "$LOG" ] || LOG=$(ls result/sim_vs_real_mape/sim_logs/*.log | head -1)
echo "=== sim log: $LOG ==="
grep -E "gpgpu_n_l1_cache|gpgpu_n_l2_cache|l1d.*access|l1d.*miss|l2.*access|l2.*miss|num_sim_winsn|warp_inst|dram_util_bins|gpu_tot_issued" "$LOG" | head -40
```

Expected output documented in `result/sim_vs_real_mape_v2/PREREQ_LOG.md` under §SC.0:
- Which cache fields exist per-SM / per-kernel / aggregate?
- Whether `m_num_sim_winsn` is dumped anywhere
- Whether `dram_util_bins` is dumped anywhere

- [ ] **Step 2: Decide SC.6 scope**

Based on Step 1 findings:
- If sim already prints L1/L2 access count per-kernel: SC.6 is **parser-only** (~30min)
- If sim only prints aggregate: SC.6 needs **per-kernel delta computation** (~1h)
- If sim doesn't print at all: SC.6 needs **sim source change too** (+1h, escalate to user)

- [ ] **Step 3: Document findings in PREREQ_LOG.md**

Append to `result/sim_vs_real_mape_v2/PREREQ_LOG.md`:

```markdown
## SC.0 Reconnaissance (2026-04-17)

### Cache fields in sim log
- L1: <field names found, granularity (per-SM/per-kernel/aggregate)>
- L2: <same>

### IPC warp counter
- m_num_sim_winsn dumped: <yes/no/where>

### DRAM util
- dram_util_bins dumped: <yes/no/where>

### SC.6 scope decision
- <parser-only / +per-kernel delta / +sim source change>
```

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/PREREQ_LOG.md
git commit -m "chore(v2): SC.0 reconnaissance — sim log field inventory for Step C"
```

### Task SC.1: Add WINSN_TOTAL per-kernel dump to GPGPU-Sim

**Files:**
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc` (find per-kernel summary print location)

- [ ] **Step 1: Locate per-kernel summary print site**

```bash
grep -n "kernel.*done\|gpu_print_stat\|print_simulation_time\|kernel_finished" gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc | head -20
```

Expected: identifies the function that runs at each kernel boundary (likely `gpu_sim_thread()` end or `print_simulation_time()`).

- [ ] **Step 2: Add WINSN_TOTAL: aggregator print**

In the per-kernel summary location (after each kernel's `gpu_sim_cycle` print), add:

```cpp
// SC.1: warp-level instruction counter aggregation across SMs
{
    unsigned long long winsn_total = 0;
    for (unsigned i = 0; i < m_shader_config->num_shader(); i++) {
        winsn_total += m_shader_stats->m_num_sim_winsn[i];
    }
    printf("WINSN_TOTAL: %llu\n", winsn_total);
}
```

(Replace `m_shader_stats` / `m_shader_config` with the correct accessor in the function context — implementer to verify.)

- [ ] **Step 3: Skip rebuild here (batched in SC.3)**

Note edits but don't rebuild yet — SC.3 will rebuild after SC.1+SC.2 both done.

- [ ] **Step 4: Commit**

```bash
git add gpu-simulator/gpgpu-sim/src/gpgpu-sim/gpu-sim.cc
git commit -m "feat(sim): SC.1 add WINSN_TOTAL per-kernel dump (aggregate m_num_sim_winsn)"
```

### Task SC.2: Add DRAM_UTIL_BINS per-kernel dump to GPGPU-Sim

**Files:**
- Modify: `gpu-simulator/gpgpu-sim/src/gpgpu-sim/dram.cc` (or wherever per-kernel DRAM stat print is invoked)

- [ ] **Step 1: Locate dram_util_bins print site**

```bash
grep -n "dram_util_bins" gpu-simulator/gpgpu-sim/src/gpgpu-sim/dram.cc
```

Expected: locations at lines 783 and 817 (per session memory).

- [ ] **Step 2: Add machine-parseable DRAM_UTIL_BINS print near per-kernel dram stats**

Modify the existing `dram_util_bins:` print (line 783-784 or 817) to ALSO emit a normalized line:

```cpp
// SC.2: machine-parseable bins for parser
unsigned total_cycles = 0;
for (unsigned i = 0; i < 10; i++) total_cycles += dram_util_bins[i];
fprintf(simFile, "DRAM_UTIL_BINS: ");
for (unsigned i = 0; i < 10; i++) fprintf(simFile, "%u ", dram_util_bins[i]);
fprintf(simFile, "(total=%u)\n", total_cycles);
```

This new line lives alongside the existing histogram print. Parser will use the new `DRAM_UTIL_BINS:` line.

- [ ] **Step 3: Commit**

```bash
git add gpu-simulator/gpgpu-sim/src/gpgpu-sim/dram.cc
git commit -m "feat(sim): SC.2 add DRAM_UTIL_BINS machine-parseable dump"
```

### Task SC.3: Rebuild GPGPU-Sim

**Files:** None (build only)

- [ ] **Step 1: Setup environment + build**

```bash
cd /workspace/prefetch
source ./gpu-simulator/setup_environment.sh release
make -j -C ./gpu-simulator/ 2>&1 | tail -30
```

Expected: build succeeds, `accel-sim.out` regenerated.

- [ ] **Step 2: Verify binary updated**

```bash
ls -la gpu-simulator/bin/release/accel-sim.out
```

Expected: mtime ~ now.

- [ ] **Step 3: Quick smoke — re-run v1 cfg_01 and verify new lines appear**

```bash
./result/sim_vs_real_mape/scripts/run_sim.sh 1 2>&1 | tail -30
grep -E "WINSN_TOTAL|DRAM_UTIL_BINS" result/sim_vs_real_mape/sim_logs/cfg_01.log | head
```

Expected: both `WINSN_TOTAL:` and `DRAM_UTIL_BINS:` lines present.

- [ ] **Step 4: Commit (if any build artifacts tracked)**

If accel-sim.out is gitignored, no commit needed. Otherwise:

```bash
git status gpu-simulator/bin/release/accel-sim.out
# only commit if status indicates change is tracked
```

### Task SC.4: Update run_ncu.sh metrics list

**Files:**
- Modify: `result/sim_vs_real_mape_v2/scripts/run_ncu.sh` (already created in Phase 2)

- [ ] **Step 1: Find current --metrics line**

```bash
grep -n "metrics" result/sim_vs_real_mape_v2/scripts/run_ncu.sh
```

- [ ] **Step 2: Replace metrics list to include 5 cache + 1 execution rate (SC.4 final list)**

Edit the `--metrics` arg in run_ncu.sh. Final metrics:

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

(plus existing v1 metrics for runtime, IPC stall reasons — keep as-is for stall display-only).

- [ ] **Step 3: Smoke ncu on F3**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh F3
head -3 result/sim_vs_real_mape_v2/ncu/F3_FA_7B_s2k.csv
```

Expected: CSV columns include the new sectors / inst_executed metrics.

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/run_ncu.sh
git commit -m "feat(v2): SC.4 add 5 cache sector metrics + inst_executed rate to ncu"
```

### Task SC.5: Update parse_ncu.py for new metrics

**Files:**
- Modify: `result/sim_vs_real_mape_v2/scripts/parse_ncu.py`

- [ ] **Step 1: Add new field extraction**

In the parser's per-kernel field dict, add:

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

Iterate the row dict using these mappings, write to per-kernel JSON.

- [ ] **Step 2: Smoke**

```bash
python3 result/sim_vs_real_mape_v2/scripts/parse_ncu.py F3
python3 -c "import json; d=json.load(open('result/sim_vs_real_mape_v2/parsed/F3_FA_7B_s2k_ncu.json')); print({k:v for k,v in d.items() if 'sector' in k or 'exec' in k})"
```

Expected: JSON contains all 8 new fields with non-null values.

- [ ] **Step 3: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/parse_ncu.py
git commit -m "feat(v2): SC.5 parse 5 cache sector metrics + execution rate from ncu"
```

### Task SC.6: Update parse_sim.py for WINSN/DRAM_BINS/cache count

**Files:**
- Modify: `result/sim_vs_real_mape_v2/scripts/parse_sim.py`

- [ ] **Step 1: Parse WINSN_TOTAL → warp-IPC**

In per-kernel block, add:

```python
m = re.search(r"WINSN_TOTAL:\s+(\d+)", block)
winsn_total = int(m.group(1)) if m else None
warp_ipc_per_scheduler = (winsn_total / cycle_total / 432.0) if winsn_total else None  # 108 SMs × 4 schedulers
```

Replace the old thread-active IPC computation with this `warp_ipc_per_scheduler` as the primary IPC metric.

- [ ] **Step 2: Parse DRAM_UTIL_BINS → weighted util %**

```python
m = re.search(r"DRAM_UTIL_BINS:\s+([\d\s]+?)\s*\(total=(\d+)\)", block)
if m:
    bins = list(map(int, m.group(1).split()))   # 10 ints
    total = int(m.group(2))
    # Weighted average: bin i represents 10*i % to 10*(i+1) % util range; midpoint = 10i+5
    weighted_pct = sum((10 * i + 5) * bins[i] for i in range(10)) / total if total else 0.0
    dram_util_pct = weighted_pct
```

Replace the old `(rd+wr)*32B/runtime/1555` reverse-derivation with this `dram_util_pct` as primary.

- [ ] **Step 3: Parse cache access counts (depends on SC.0 outcome)**

If SC.0 found per-kernel cache fields: extract directly. Otherwise compute deltas between kernel boundaries. Implementer fills based on SC.0's PREREQ_LOG.md decision.

- [ ] **Step 4: Smoke on cfg_03**

```bash
python3 result/sim_vs_real_mape_v2/scripts/parse_sim.py 3   # using v1 cfg id since we use v1 log for now
# OR
python3 result/sim_vs_real_mape_v2/scripts/parse_sim.py F3  # if F3 trace+sim already done in Phase 3
cat <output JSON> | python3 -m json.tool | grep -E "ipc|dram_util|sector|cache"
```

Expected: warp-IPC value reasonable (NCU NCU: 0.4-1.5 typical), dram_util_pct in 0-100 range.

- [ ] **Step 5: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/parse_sim.py
git commit -m "feat(v2): SC.6 parse WINSN_TOTAL, DRAM_UTIL_BINS, cache access count from sim log"
```

### Task SC.7: Update collect_metrics.py + classify_bottleneck.py

**Files:**
- Modify: `result/sim_vs_real_mape_v2/scripts/collect_metrics.py`
- Modify: `result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py`

- [ ] **Step 1: Add new columns to merged_metrics.csv schema**

In collect_metrics.py, add new column pairs (sim_X, real_X) for:
- `l1_sectors_total`, `l1_sectors_hit`, `l1_hit_rate_weighted` (= hit/total)
- `l2_sectors_total`, `l2_sectors_hit`, `l2_hit_rate_weighted`
- `exec_rate_per_cycle` (NCU only — sim can use winsn-based equivalent)

Also for primary metrics (now upgraded):
- `ipc_warp` (replaces `ipc` thread-based)
- `dram_util_weighted` (replaces `dram_util` reverse-derived)

- [ ] **Step 2: Update classify_bottleneck.py thresholds (optional, may stay same)**

Verify thresholds still make sense for new IPC scale (warp-IPC has range 0-1 per scheduler, vs old thread-IPC 0-32 per scheduler). May need 1/32 scaling.

- [ ] **Step 3: Smoke**

```bash
python3 result/sim_vs_real_mape_v2/scripts/collect_metrics.py
head -3 result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
```

Expected: header has new columns; values populated.

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/collect_metrics.py result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py
git commit -m "feat(v2): SC.7 collect_metrics + classify_bottleneck use new IPC/DRAM/cache metrics"
```

### Task SC.8: Smoke validation on v1 cfg_03

**Files:** None (validation only)

**Goal:** Verify Step C revisions actually improved metrics on a known v1 datapoint.

- [ ] **Step 1: Re-run v1 cfg_03 with new sim binary**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape/scripts/run_sim.sh 3
```

This regenerates `result/sim_vs_real_mape/sim_logs/cfg_03.log` with new WINSN_TOTAL + DRAM_UTIL_BINS lines.

- [ ] **Step 2: Re-parse with v2 parser (point at v1 log temporarily)**

```bash
# Quick validation script
python3 -c "
import sys
sys.path.insert(0, 'result/sim_vs_real_mape_v2/scripts')
from parse_sim import parse_sim_log
import json
result = parse_sim_log('result/sim_vs_real_mape/sim_logs/cfg_03.log', kernel_filter='flash_fwd')
print(json.dumps(result, indent=2))
"
```

- [ ] **Step 3: Compare to v1 ground truth (cfg_03 NCU data)**

```bash
# v1 NCU data for cfg_03
cat result/sim_vs_real_mape/parsed/cfg_03_ncu.json | python3 -m json.tool | grep -E "ipc|dram_util"
```

- [ ] **Step 4: Verify IPC MAPE improvement**

Compute: `|sim_ipc_warp - ncu_ipc| / ncu_ipc * 100`

Expected: <34% (v1 baseline). Target: ~5-15%.

- [ ] **Step 5: Verify DRAM util MAPE improvement**

Compute: `|sim_dram_weighted - ncu_dram_pct|` (absolute pp).

Expected: <52pp (v1 baseline). Target: ~5-20pp.

- [ ] **Step 6: Document findings in PREREQ_LOG.md**

Append to `result/sim_vs_real_mape_v2/PREREQ_LOG.md`:

```markdown
## SC.8 Smoke Validation (2026-04-17, v1 cfg_03 with new sim + parsers)

| Metric | v1 sim | v1 NCU | v1 MAPE | v2 sim | v2 MAPE | Δ |
|---|---|---|---|---|---|---|
| IPC | <v1> | <ncu> | 34% | <v2> | <new> | <improvement> |
| DRAM util | <v1> | <ncu> | 52pp | <v2> | <new> | <improvement> |

**Decision**: <improvement is acceptable / regression / needs more work>
```

- [ ] **Step 7: Commit + Phase 0.5 done marker**

```bash
git add result/sim_vs_real_mape_v2/PREREQ_LOG.md
git commit -m "chore(v2): SC.8 smoke validation passes — Step C metrics improved on cfg_03"
```

---

## Phase 1: Configuration Generation

### Task 1.1: Create v2 directory scaffolding + gen_configs.py

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/gen_configs.py`

- [ ] **Step 1: Create directories**

```bash
mkdir -p result/sim_vs_real_mape_v2/{scripts,traces,sim_logs,ncu,parsed,reports,figures}
```

- [ ] **Step 2: Write gen_configs.py with all 41 cfgs explicitly**

```python
"""Generate configs.csv for v2 (41 cfgs, all bf16, anchored to real models)."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "configs.csv"

# Schema: id, workload, label, seq_or_kvlen, batch, nheads, kv_heads, head_dim, page_size, M, K, N, hidden, impl, cfg_tag
# (Some fields N/A per workload; use empty string)

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
    # G9-G11: QKV proj across GQA ratios
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
    w = csv.writer(f, lineterminator="\n")  # avoid CRLF (v1 lesson)
    w.writerow(HEADER)
    for row in ROWS:
        w.writerow(row)

print(f"Wrote {len(ROWS)} rows to {OUT}")
```

- [ ] **Step 3: Run gen_configs.py**

```bash
cd /workspace/prefetch
python3 result/sim_vs_real_mape_v2/scripts/gen_configs.py
```

Expected: `Wrote 41 rows to .../configs.csv`

- [ ] **Step 4: Verify CSV (no CRLF, 42 lines = 1 header + 41 rows)**

```bash
wc -l result/sim_vs_real_mape_v2/scripts/configs.csv
file result/sim_vs_real_mape_v2/scripts/configs.csv
```

Expected: `42 ...`, file type `ASCII text` (NOT `with CRLF line terminators`).

- [ ] **Step 5: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/gen_configs.py result/sim_vs_real_mape_v2/scripts/configs.csv
git commit -m "feat(v2): add 41-cfg matrix generator + CSV (FA 11 + Decode 13 + GEMM 12 + RMSNorm 5)"
```

---

## Phase 2: Pipeline Scripts (Trace / Sim / NCU)

### Task 2.1: Copy + extend run_tracer.sh for 4 workloads

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/run_tracer.sh`

- [ ] **Step 1: Read v1 run_tracer.sh as baseline**

```bash
cat result/sim_vs_real_mape/scripts/run_tracer.sh
```

- [ ] **Step 2: Write extended v2 run_tracer.sh**

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
git add result/sim_vs_real_mape_v2/scripts/run_tracer.sh
git commit -m "feat(v2): add run_tracer.sh for 4 workloads (fa/decode/gemm/rmsnorm), bf16"
```

### Task 2.2: Copy + extend run_sim.sh

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/run_sim.sh`

- [ ] **Step 1: Copy v1 sim script and adjust paths to v2**

Copy `result/sim_vs_real_mape/scripts/run_sim.sh` to `result/sim_vs_real_mape_v2/scripts/run_sim.sh`, then in the new file replace all occurrences of `result/sim_vs_real_mape/` with `result/sim_vs_real_mape_v2/`.

```bash
cp result/sim_vs_real_mape/scripts/run_sim.sh result/sim_vs_real_mape_v2/scripts/run_sim.sh
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/run_sim.sh
```

- [ ] **Step 2: Update CSV column parsing for new schema**

Edit `result/sim_vs_real_mape_v2/scripts/run_sim.sh`, find the line:

```bash
IFS=, read -r id workload label seq batch nheads kv_heads head_dim reuse cfg_tag <<<"$ROW"
```

Replace with:

```bash
IFS=, read -r id workload label seq batch nheads kv_heads head_dim page_size M K N rms_M rms_hidden cfg_tag <<<"$ROW"
```

(The fields after cfg_tag aren't used by sim; only cfg_tag and workload matter.)

- [ ] **Step 3: Verify file is OK**

```bash
bash -n result/sim_vs_real_mape_v2/scripts/run_sim.sh && echo "syntax OK"
```

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/run_sim.sh
git commit -m "feat(v2): add run_sim.sh — copy of v1 with v2 paths and 15-col CSV schema"
```

### Task 2.3: Copy + extend run_ncu.sh

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/run_ncu.sh`

- [ ] **Step 1: Copy + sed paths**

```bash
cp result/sim_vs_real_mape/scripts/run_ncu.sh result/sim_vs_real_mape_v2/scripts/run_ncu.sh
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/run_ncu.sh
```

- [ ] **Step 2: Update CSV parsing + add gemm/rmsnorm command branches**

Edit `result/sim_vs_real_mape_v2/scripts/run_ncu.sh`. Update IFS read line same as Task 2.2 Step 2. Then in the case statement that builds CMD, add `gemm` and `rmsnorm` branches mirroring run_tracer.sh Task 2.1 Step 2.

- [ ] **Step 3: chmod + verify**

```bash
chmod +x result/sim_vs_real_mape_v2/scripts/run_ncu.sh
bash -n result/sim_vs_real_mape_v2/scripts/run_ncu.sh && echo "syntax OK"
```

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/run_ncu.sh
git commit -m "feat(v2): add run_ncu.sh for 4 workloads"
```

---

## Phase 3: Smoke Tests (4 representative cfgs, 1 per operator)

### Task 3.1: Smoke FA (cfg F3 = FA-7B-s2k)

**Files:** None (run scripts only)

- [ ] **Step 1: Trace**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh F3
```

Expected: trace.log shows MHA + causal + bf16 + `OK. output=(1, 2048, 32, 128) dtype=torch.bfloat16`. kernelslist.g exists.

- [ ] **Step 2: NCU profile**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh F3
```

Expected: ncu CSV produced at `result/sim_vs_real_mape_v2/ncu/F3_FA_7B_s2k.csv`, contains row with kernel name matching `flash_fwd*` AND grpc/L1/L2/DRAM metrics.

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh F3
```

Expected: sim log ends with `EXPERIMENT SUMMARY` containing `status=COMPLETE`, `gpu_tot_ipc`, `gpu_tot_sim_cycle`.

- [ ] **Step 4: Verify outputs**

```bash
ls -la result/sim_vs_real_mape_v2/{traces/F3_FA_7B_s2k/traces/kernelslist.g,sim_logs/F3_FA_7B_s2k.log,ncu/F3_FA_7B_s2k.csv}
```

All 3 files non-zero size.

### Task 3.2: Smoke Decode (cfg D3 = DEC-7B-k2k)

**Files:** None (run scripts only)

- [ ] **Step 1: Trace**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh D3
```

Expected: trace.log shows decode kernel launches with B=1, kv_len=2048, H=32, kv_H=32, page_size=16, dtype=bf16. kernelslist.g exists.

- [ ] **Step 2: NCU profile**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh D3
```

Expected: NCU CSV at `result/sim_vs_real_mape_v2/ncu/D3_DEC_7B_k2k.csv`, contains row with kernel name matching `flashinfer*` or `BatchDecodeWithPagedKVCache*`.

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh D3
```

Expected: sim log ends with `EXPERIMENT SUMMARY status=COMPLETE`.

- [ ] **Step 4: Verify outputs**

```bash
ls -la result/sim_vs_real_mape_v2/{traces/D3_DEC_7B_k2k/traces/kernelslist.g,sim_logs/D3_DEC_7B_k2k.log,ncu/D3_DEC_7B_k2k.csv}
```

All 3 files non-zero size.

### Task 3.3: Smoke GEMM (cfg G4 = GEMM-7B-FFN-up-M1024)

**Files:** None (run scripts only)

- [ ] **Step 1: Trace**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh G4
```

Expected: trace.log shows `GEMM [M=1024, K=4096] @ [K=4096, N=11008] dtype=torch.bfloat16` and `OK. output=(1024, 11008)`.

- [ ] **Step 2: NCU profile**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh G4
```

Expected: NCU CSV at `result/sim_vs_real_mape_v2/ncu/G4_GEMM_7B_FFN_up_M1024.csv`. Kernel name matches one of: `ampere_bf16_s16816gemm*`, `sm80_xmma_gemm_*`, `cutlass_80_tensorop_bf16*`. **Note for engineer**: if no match, run `head -3 result/sim_vs_real_mape_v2/ncu/G4_*.csv` to see actual kernel names and update KERNEL_PATTERNS regex in Task 5.1.

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh G4
```

Expected: sim log ends with `EXPERIMENT SUMMARY status=COMPLETE`. GEMM is compute-bound — expect high IPC (>0.5 warp-IPC) and low DRAM util (<30%).

- [ ] **Step 4: Verify outputs**

```bash
ls -la result/sim_vs_real_mape_v2/{traces/G4_GEMM_7B_FFN_up_M1024/traces/kernelslist.g,sim_logs/G4_GEMM_7B_FFN_up_M1024.log,ncu/G4_GEMM_7B_FFN_up_M1024.csv}
```

All 3 files non-zero size.

### Task 3.4: Smoke RMSNorm (cfg R2 = RMS-7B-M1024)

**Files:** None (run scripts only)

- [ ] **Step 1: Trace**

```bash
cd /workspace/prefetch
./result/sim_vs_real_mape_v2/scripts/run_tracer.sh R2
```

Expected: trace.log shows `RMSNorm M=1024 hidden=4096 impl=vllm dtype=bf16` and `OK. output=(1024, 4096)`.

- [ ] **Step 2: NCU profile**

```bash
./result/sim_vs_real_mape_v2/scripts/run_ncu.sh R2
```

Expected: NCU CSV at `result/sim_vs_real_mape_v2/ncu/R2_RMS_7B_M1024.csv`. Kernel name matches one of: `rms_norm*`, `vllm::ops::rms_norm*`, `fused_add_rms_norm*`. Same regex iteration note as Task 3.3 Step 2.

- [ ] **Step 3: Sim**

```bash
./result/sim_vs_real_mape_v2/scripts/run_sim.sh R2
```

Expected: sim log ends with `EXPERIMENT SUMMARY status=COMPLETE`. RMSNorm is bandwidth-bound — expect high DRAM util (>60%) and low IPC.

- [ ] **Step 4: Verify outputs**

```bash
ls -la result/sim_vs_real_mape_v2/{traces/R2_RMS_7B_M1024/traces/kernelslist.g,sim_logs/R2_RMS_7B_M1024.log,ncu/R2_RMS_7B_M1024.csv}
```

All 3 files non-zero size.

### Checkpoint A: User Reviews 4 Smoke Tests

- [ ] **Pause for user**

Print summary of 4 smoke results:
- F3 / D3 / G4 / R2: trace OK / sim OK / ncu OK / kernel name detected

Ask user:
> "4 个 smoke test 全部通过，可以进入 bulk run 了吗？"

Wait for explicit user "yes" before proceeding to Task 4.x.

---

## Phase 4: Bulk Execution (37 remaining cfgs)

### Task 4.1: Bulk Trace (37 cfgs, sequential on 1 GPU)

**Files:** None (run scripts only)

- [ ] **Step 1: Identify remaining cfg ids (excl smoke)**

Smoke = {F3, D3, G4, R2}. Remaining 37 = all others.

- [ ] **Step 2: Loop with retry-once**

```bash
cd /workspace/prefetch
SMOKE="F3 D3 G4 R2"
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

Expected wall time: ~1.5-2h (NVBit on 1 GPU, sequential).

- [ ] **Step 3: Verify all 41 traces present**

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

Expected: 41 OK lines.

### Task 4.2: Bulk NCU (37 cfgs, sequential on 1 GPU)

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

Expected wall time: ~1-1.5h.

- [ ] **Step 2: Verify 41 ncu CSVs present**

```bash
ls result/sim_vs_real_mape_v2/ncu/*.csv | wc -l
```

Expected: 41.

### Task 4.3: Bulk Sim (37 cfgs, parallel 8-way on CPU)

- [ ] **Step 1: Run via xargs -P 8**

```bash
cd /workspace/prefetch
echo "F1 F2 F4 F5 F6 F7 F8 F9 F10 F11 \
      D1 D2 D4 D5 D6 D7 D8 D9 D10 D11 D12 D13 \
      G1 G2 G3 G5 G6 G7 G8 G9 G10 G11 G12 \
      R1 R3 R4 R5" | tr ' ' '\n' \
    | xargs -P 8 -I{} bash -c './result/sim_vs_real_mape_v2/scripts/run_sim.sh {} 2>&1 | tail -5'
```

Expected wall time: ~3-5h (parallelism limited by sim per-job memory).

- [ ] **Step 2: Verify all 41 sim logs have status=COMPLETE**

```bash
for f in result/sim_vs_real_mape_v2/sim_logs/*.log; do
    status=$(grep "^status=" "$f" | tail -1)
    echo "$(basename $f): $status"
done | grep -c COMPLETE
```

Expected: 41.

If <41: investigate failed cfgs, classify per spec §6 (simple/困难/未明). Document in `result/sim_vs_real_mape_v2/FAILED_CFGS.md` and decide whether to retry, fix, or sediment.

---

## Phase 5: Parsing + Analysis Pipeline

### Task 5.1: Copy + extend parse_ncu.py for 4 workloads

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/parse_ncu.py`

- [ ] **Step 1: Copy v1 parser**

```bash
cp result/sim_vs_real_mape/scripts/parse_ncu.py result/sim_vs_real_mape_v2/scripts/parse_ncu.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/parse_ncu.py
```

- [ ] **Step 2: Extend kernel name filter to include GEMM + RMSNorm patterns**

Edit `result/sim_vs_real_mape_v2/scripts/parse_ncu.py`. Find the kernel name filter (likely a regex like `re.match("flash_fwd|flashinfer", ...)`). Replace with:

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

Use this filter when iterating ncu CSV rows.

- [ ] **Step 3: Test on F3 (FA smoke)**

```bash
python3 result/sim_vs_real_mape_v2/scripts/parse_ncu.py F3
ls result/sim_vs_real_mape_v2/parsed/F3_*.json
```

Expected: JSON file with non-empty kernel list, runtime/IPC/DRAM/L1/L2 fields.

- [ ] **Step 4: Test on G4 (GEMM smoke)**

```bash
python3 result/sim_vs_real_mape_v2/scripts/parse_ncu.py G4
cat result/sim_vs_real_mape_v2/parsed/G4_*.json | python3 -m json.tool | head -40
```

Expected: JSON has runtime, IPC, DRAM util filled (compute-bound expected: high IPC, low DRAM util).

- [ ] **Step 5: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/parse_ncu.py
git commit -m "feat(v2): extend parse_ncu.py to filter GEMM (cublas/ampere/sm80) and RMSNorm kernels"
```

### Task 5.2: Copy + extend parse_sim.py

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/parse_sim.py`

- [ ] **Step 1: Copy v1 parser**

```bash
cp result/sim_vs_real_mape/scripts/parse_sim.py result/sim_vs_real_mape_v2/scripts/parse_sim.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/parse_sim.py
```

- [ ] **Step 2: Extend KERNEL_PATTERNS dict**

Same as Task 5.1 Step 2 — add the 4 patterns to parse_sim.py for sim log filtering.

- [ ] **Step 3: Test on F3 + G4**

```bash
python3 result/sim_vs_real_mape_v2/scripts/parse_sim.py F3
python3 result/sim_vs_real_mape_v2/scripts/parse_sim.py G4
ls result/sim_vs_real_mape_v2/parsed/F3_*sim.json result/sim_vs_real_mape_v2/parsed/G4_*sim.json
```

Both should produce non-empty JSON.

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/parse_sim.py
git commit -m "feat(v2): extend parse_sim.py for GEMM and RMSNorm kernel filters"
```

### Task 5.3: Run parse on all 41 cfgs

- [ ] **Step 1: Loop both parsers**

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

Expected: 82 JSON files produced (41 ncu + 41 sim) under `result/sim_vs_real_mape_v2/parsed/`.

- [ ] **Step 2: Verify count**

```bash
ls result/sim_vs_real_mape_v2/parsed/*.json | wc -l
```

Expected: 82.

### Task 5.4: collect_metrics.py → merged_metrics.csv

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/collect_metrics.py`

- [ ] **Step 1: Copy v1 + sed paths**

```bash
cp result/sim_vs_real_mape/scripts/collect_metrics.py result/sim_vs_real_mape_v2/scripts/collect_metrics.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/collect_metrics.py
```

- [ ] **Step 2: Verify CSV schema column count for v2 (15 columns)**

Open `result/sim_vs_real_mape_v2/scripts/collect_metrics.py` and find any code that reads configs.csv. Confirm it accesses fields by name (`row["label"]`, `row["workload"]`) rather than by positional index. If positional, refactor to dict-based access.

- [ ] **Step 3: Run**

```bash
cd /workspace/prefetch
python3 result/sim_vs_real_mape_v2/scripts/collect_metrics.py
```

Expected: produces `result/sim_vs_real_mape_v2/parsed/merged_metrics.csv` with 41 rows × (id, label, runtime_real, runtime_sim, ipc_real, ipc_sim, dram_real, dram_sim, l1_real, l1_sim, l2_real, l2_sim, ...).

- [ ] **Step 4: Sanity check**

```bash
head -5 result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
wc -l result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
```

Expected: 42 lines (1 header + 41 cfg).

- [ ] **Step 5: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/collect_metrics.py result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
git commit -m "feat(v2): collect_metrics.py → merged_metrics.csv (41 cfg)"
```

### Task 5.5: classify_bottleneck.py

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py`

- [ ] **Step 1: Copy v1**

```bash
cp result/sim_vs_real_mape/scripts/classify_bottleneck.py result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py
```

- [ ] **Step 2: Run + verify**

```bash
cd /workspace/prefetch
python3 result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py
head -5 result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
```

Expected: merged_metrics.csv now has additional columns `sim_class`, `real_class`, `agree`. ~30-50% agreement expected (similar to v1 18% but improved by bf16 + correct fa.py impl).

- [ ] **Step 3: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/classify_bottleneck.py result/sim_vs_real_mape_v2/parsed/merged_metrics.csv
git commit -m "feat(v2): classify_bottleneck.py — sim/real/agree columns added"
```

### Checkpoint B: User Reviews Tables

- [ ] **Pause for user**

Print summary table:
- 41 cfg total, X sim valid, Y/X classification agreement
- runtime / IPC / DRAM / L1 / L2 mean MAPE per algo

Ask user:
> "数据看起来合理吗？想调整 bottleneck 分类阈值或增加额外指标吗？OK 后进入图表生成阶段。"

Wait for user "yes".

---

## Phase 6: Report and Figures

### Task 6.1: make_report.py — generate mape_report.md

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/make_report.py`

- [ ] **Step 1: Copy v1**

```bash
cp result/sim_vs_real_mape/scripts/make_report.py result/sim_vs_real_mape_v2/scripts/make_report.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/make_report.py
```

- [ ] **Step 2: Extend report with per-algo MAPE breakdown (4 algos)**

Edit `make_report.py`. Add a section that groups merged_metrics.csv by `workload` field and reports per-workload MAPE for runtime / IPC / DRAM / L1 / L2.

```python
import pandas as pd
df = pd.read_csv("result/sim_vs_real_mape_v2/parsed/merged_metrics.csv")
for workload in ["fa", "decode", "gemm", "rmsnorm"]:
    sub = df[df["label"].str.startswith(workload[:2].upper()) | df["id"].str.startswith(workload[0].upper())]
    print(f"\n## {workload}: {len(sub)} cfgs")
    print(f"  runtime MAPE = {((sub['runtime_real']-sub['runtime_sim']).abs()/sub['runtime_real']).mean()*100:.1f}%")
    # ...similar for IPC, DRAM, L1, L2
```

- [ ] **Step 3: Run + verify**

```bash
cd /workspace/prefetch
python3 result/sim_vs_real_mape_v2/scripts/make_report.py
ls result/sim_vs_real_mape_v2/reports/mape_report.md
```

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/make_report.py result/sim_vs_real_mape_v2/reports/mape_report.md
git commit -m "feat(v2): make_report.py — per-algo MAPE breakdown for 4 workloads"
```

### Task 6.2: Update Fig 1 (Roofline) for new operator points

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig1_roofline.py`

- [ ] **Step 1: Copy v1 fig + sed paths**

```bash
cp result/sim_vs_real_mape/scripts/fig1_roofline.py result/sim_vs_real_mape_v2/scripts/fig1_roofline.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig1_roofline.py
```

- [ ] **Step 2: Add 4 panels (was 2: FA|Decode → 4: FA|Decode|GEMM|RMSNorm)**

Edit `fig1_roofline.py`. Change `fig, axes = plt.subplots(1, 2, ...)` to `fig, axes = plt.subplots(2, 2, ...)`. For each panel, filter merged_metrics.csv to that workload's cfgs and plot AI vs achieved TFLOPS with the 3 ceilings (L1 15 TB/s, L2 3.35 TB/s, HBM 1.56 TB/s) + compute ceiling 312 TFLOPS.

- [ ] **Step 3: Run + visually inspect**

```bash
cd /workspace/prefetch
python3 result/sim_vs_real_mape_v2/scripts/fig1_roofline.py
ls result/sim_vs_real_mape_v2/figures/fig1_roofline.{pdf,svg}
```

- [ ] **Step 4: Commit**

```bash
git add result/sim_vs_real_mape_v2/scripts/fig1_roofline.py result/sim_vs_real_mape_v2/figures/fig1_roofline.{pdf,svg}
git commit -m "feat(v2): fig1 roofline — 4 panels (FA/Decode/GEMM/RMSNorm) with 3 mem ceilings"
```

### Task 6.3: Fig 2 (MAPE breakdown for 4 algos)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py`

- [ ] **Step 1: Copy + extend**

```bash
cp result/sim_vs_real_mape/scripts/fig2_mape_breakdown.py result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py
```

Edit fig2: change x-axis from "FA / Decode" to "FA / Decode / GEMM / RMSNorm". Keep 5 metric subpanels (runtime/IPC use rel MAPE; DRAM/L1/L2 use abs pp).

- [ ] **Step 2: Run + commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py
git add result/sim_vs_real_mape_v2/scripts/fig2_mape_breakdown.py result/sim_vs_real_mape_v2/figures/fig2_mape_breakdown.{pdf,svg}
git commit -m "feat(v2): fig2 MAPE breakdown — 4 algos × 5 metrics"
```

### Task 6.4: Fig 3 (Trajectory — multi-axis sweep curves)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py`

- [ ] **Step 1: Copy + extend with 4 subplots (one per algo's primary depth axis)**

```bash
cp result/sim_vs_real_mape/scripts/fig3_trajectory.py result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py
```

Edit: 4 subplots:
- (a) FA seq sweep: x=seq, y=runtime/IPC/DRAM (real vs sim), one line per metric
- (b) Decode kv_len sweep: x=kv_len, y=...
- (c) GEMM M sweep: x=log(M), y=achieved TFLOPS (real vs sim)
- (d) RMSNorm M sweep: x=log(M), y=achieved bandwidth GB/s

- [ ] **Step 2: Run + commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py
git add result/sim_vs_real_mape_v2/scripts/fig3_trajectory.py result/sim_vs_real_mape_v2/figures/fig3_trajectory.{pdf,svg}
git commit -m "feat(v2): fig3 trajectory — 4 algos primary-axis sweeps"
```

### Task 6.5: Fig 4 (Stall stacked, 41 cfgs)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py`

- [ ] **Step 1: Copy + adjust x-axis labels**

```bash
cp result/sim_vs_real_mape/scripts/fig4_stall_stacked.py result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py
sed -i 's|result/sim_vs_real_mape/|result/sim_vs_real_mape_v2/|g' \
    result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py
```

Edit: layout 41 cfg × 2 bars (sim | real) on x-axis. May need landscape wider figsize; group by algo (vertical separators).

- [ ] **Step 2: Run + commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py
git add result/sim_vs_real_mape_v2/scripts/fig4_stall_stacked.py result/sim_vs_real_mape_v2/figures/fig4_stall_stacked.{pdf,svg}
git commit -m "feat(v2): fig4 stall stacked — 41 cfgs grouped by algo"
```

### Task 6.6: Fig 5 (NEW: GEMM shape pattern comparison)

**Files:**
- Create: `result/sim_vs_real_mape_v2/scripts/fig5_gemm_shape_pattern.py`

This is a v2-specific figure showing how QKV vs O vs FFN-up vs FFN-down patterns differ in observed runtime/IPC/DRAM, comparing real vs sim.

- [ ] **Step 1: Write fig5 from scratch**

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

# Group GEMM cfgs by shape pattern
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

- [ ] **Step 2: Run + commit**

```bash
python3 result/sim_vs_real_mape_v2/scripts/fig5_gemm_shape_pattern.py
git add result/sim_vs_real_mape_v2/scripts/fig5_gemm_shape_pattern.py result/sim_vs_real_mape_v2/figures/fig5_gemm_shape_pattern.{pdf,svg}
git commit -m "feat(v2): fig5 GEMM shape pattern comparison (QKV / O / FFN-up / FFN-down)"
```

---

## Phase 7: Deliverables and Session Review

### Task 7.1: Copy v2 deliverables to tracked docs/

**Files:**
- Create: `docs/superpowers/specs/sim_vs_real_mape_v2_results/mape_report.md`
- Create: `docs/superpowers/specs/sim_vs_real_mape_v2_results/figures/*.pdf`

- [ ] **Step 1: Copy report + figures + merged_metrics**

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

### Task 7.2: Update Feishu doc

- [ ] **Step 1: Append v2 section to Feishu doc**

Use `mcp__feishu__update-doc` to append v2 results section to existing doc `AoMsdhMk4oruflxMswicxNx1neb`. Include: 4 algo summary table, per-algo MAPE, classification agreement, links to local figures (user must manually upload).

### Task 7.3: Run /session-review

- [ ] **Step 1: Invoke session-review skill**

This will check INDEX.md freshness, experiment_progress.md updates, and any new globally-relevant scripts that should be registered to CLAUDE.md.

```
/session-review
```

---

## Self-Review Checklist (run before handing off plan to executor)

- [ ] **Spec coverage**: Each section of spec is implemented:
  - §0 v2 升级目标 8 项 → all addressed (dtype/FA impl/multi-axis/Step C all in plan)
  - §1 P1-P5 设计原则 → enforced via cfg constraints
  - §3 model anchors → anchored in configs.csv
  - §3.5 实现选型 → Task 0.3-0.6
  - §4.1-§4.4 矩阵 → Task 1.1
  - §6 失败档案 → Task 0.1 (cfg_13 investigation)
  - §7 Step C → Task 0.0 (decision gate)
  - §9 open issues → Task 0.0 + 0.1 + 0.2

- [ ] **Placeholder scan**: No "TBD", "implement later", or "see Task N" without code.

- [ ] **Type/path consistency**: All file paths use `result/sim_vs_real_mape_v2/` consistently. CSV schema (15 columns) matches across gen_configs.py, run_*.sh, parse_*.py.

- [ ] **Workflow gates**: Checkpoint A (smoke review) and Checkpoint B (table review) require user "yes" before proceeding.

---

## Estimated Wall Time

| Phase | Time |
|---|---|
| Phase 0: prereqs | 1-2h |
| Phase 1: configs.csv | 30min |
| Phase 2: scripts | 1h |
| Phase 3: smoke (4 cfg) | 30min-1h |
| Phase 4: bulk (37 cfg, 8-way parallel sim) | 5-7h |
| Phase 5: parse + collect + classify | 1h |
| Phase 6: figures (5 figs) | 2-3h |
| Phase 7: deliverables | 30min |
| **Total** | **~12-16h** (1.5-2 working days) |

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| vLLM not installed | Medium | Task 0.2 Step 3 verifies; fallback to flash_attn rms_norm |
| flashinfer page_size not param | Low | Task 0.4 verifies; if not, modify flashinfer_decode.py |
| FA F7 (B=4 s2k) sim CTA budget exceeded | Low-Medium | Watch sim log for hang; if hangs, drop F7 and document |
| GEMM kernel name regex misses cublas variants | Medium | Task 5.1 Step 4 verifies G4 parses; iterate regex if not |
| Decode page_size=64 sim runtime explodes | Low | Watch D9 sim time; if >2× D8, document as sim limitation |
| Multi-cfg sim fails with similar pattern as cfg_13 | Medium | Apply Task 0.1 30-min rule per failure; sediment to spec §6 |
