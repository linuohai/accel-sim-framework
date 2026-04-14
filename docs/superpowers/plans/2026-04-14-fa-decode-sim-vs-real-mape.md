# FA / Decode Sim-vs-Real MAPE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run 14 configs (7 FA + 7 flashinfer decode) on A100 through both GPGPU-Sim and Nsight Compute, compare per-metric MAPE and bottleneck-classification agreement, output one report and four figures.

**Architecture:** Three-stage data pipeline on one A100 machine — (1) real-GPU side collects ncu metrics per config and accel-sim SASS traces for the simulator; (2) GPGPU-Sim consumes traces in parallel on CPU; (3) a merge/analysis step joins both sides into a single CSV and drives report + figure generation. Scripts are thin Python + bash glue calling existing tooling (`traceL1`, `ncu`, `util/tracer_nvbit/`).

**Tech Stack:** bash + python3 (pandas, numpy, matplotlib), GPGPU-Sim (Accel-Sim), Nsight Compute 2024.x, A100 GPU, existing `traceL1` harness and `plot_util.py`.

**Spec reference:** [`docs/superpowers/specs/2026-04-14-fa-decode-sim-vs-real-mape-design.md`](../specs/2026-04-14-fa-decode-sim-vs-real-mape-design.md)

**Key adaptation:** This is a one-day experimental pipeline, not a shipping feature. Traditional red-green-refactor TDD doesn't map cleanly to shell orchestration and profiler wrappers. The adaptation is: **small-scale smoke test first on 1 config → verify → then bulk**. Every task that runs on the GPU has a 1-config smoke step before the 14-config bulk step.

**Directory layout (all scripts + intermediate data are gitignored — final report is copied to tracked `docs/` at the end):**

```
result/sim_vs_real_mape/           # gitignored
├── scripts/
│   ├── configs.csv                # 14 rows, single source of truth
│   ├── gen_configs.py             # writes configs.csv
│   ├── run_tracer.sh              # one config → SASS trace
│   ├── run_ncu.sh                 # one config → ncu-rep + csv
│   ├── run_sim.sh                 # one config → sim log via traceL1
│   ├── parse_ncu.py               # ncu csv → normalized metrics
│   ├── parse_sim.py               # sim log → normalized metrics
│   ├── collect_metrics.py         # merge sim + ncu → merged_metrics.csv
│   ├── classify_bottleneck.py     # add bottleneck category columns
│   ├── make_report.py             # emit mape_report.md with Tables 1/2/3
│   ├── fig1_roofline.py           # production (plot_util style)
│   ├── fig2_mape_breakdown.py
│   ├── fig3_trajectory.py
│   ├── fig4_stall_stacked.py
│   └── _proto_all_figures.py      # ALREADY WRITTEN (prototype from brainstorm)
├── traces/cfg_{01..14}/           # accel-sim trace dirs
├── ncu_out/cfg_{01..14}.{csv,ncu-rep}
├── sim_logs/cfg_{01..14}.log
├── ncu_metrics.csv
├── sim_metrics.csv
├── merged_metrics.csv
└── figures/
    ├── _proto_fig{1..4}.png       # ALREADY GENERATED
    ├── fig{1..4}.pdf               # produced by Task 17
    └── fig{1..4}.svg

docs/superpowers/specs/sim_vs_real_mape_results/   # TRACKED — final deliverables
├── mape_report.md
├── fig1_roofline.pdf
├── fig2_mape_breakdown.pdf
├── fig3_trajectory.pdf
└── fig4_stall_stacked.pdf
```

---

## Pre-flight checklist (user confirms before Task 1)

- [ ] A100 is idle and can be held exclusively for ~3-4 hours
- [ ] `which ncu` returns a ≥ 2022.x Nsight Compute, with permission to profile (CAP_SYS_ADMIN or `/proc/sys/kernel/perf_event_paranoid` ≤ 2)
- [ ] `python3 -c "import flash_attn, flashinfer, torch; print('ok')"` prints ok on the A100 machine
- [ ] `source ./gpu-simulator/setup_environment.sh && make -j -C ./gpu-simulator/` succeeds (simulator binary exists at `./gpu-simulator/bin/release/accel-sim.out`)

If any fails, stop and resolve before starting. Do not skip.

---

## Task 1: Create directory structure and configs.csv

**Files:**
- Create: `result/sim_vs_real_mape/scripts/gen_configs.py`
- Create: `result/sim_vs_real_mape/scripts/configs.csv` (generated)

- [ ] **Step 1: Write `gen_configs.py`**

```python
#!/usr/bin/env python3
"""Emit configs.csv — 14-row single source of truth for the experiment.

Columns: id, workload (fa|decode), label, seq_or_kv, batch, nheads,
kv_heads, head_dim, extra_args, trace_dir, reuse_existing.
"""
from pathlib import Path
import csv

ROWS = [
    # FA: 7 configs (batch=1, causal=on default)
    dict(id=1,  workload="fa",     label="FA-s512",     seq=512,  batch=1, nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=2,  workload="fa",     label="FA-s1k",      seq=1024, batch=1, nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=3,  workload="fa",     label="FA-s2k",      seq=2048, batch=1, nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=4,  workload="fa",     label="FA-s4k",      seq=4096, batch=1, nheads=32, kv_heads=32, head_dim=128, reuse="hw_run/traces/device-0/12.6/fa_4096seq"),
    dict(id=5,  workload="fa",     label="FA-s8k",      seq=8192, batch=1, nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=6,  workload="fa",     label="FA-s2k-d64",  seq=2048, batch=1, nheads=32, kv_heads=32, head_dim=64,  reuse=""),
    dict(id=7,  workload="fa",     label="FA-s2k-H8",   seq=2048, batch=1, nheads=8,  kv_heads=8,  head_dim=128, reuse=""),
    # Decode: 7 configs (mode=paged, page_size=16)
    dict(id=8,  workload="decode", label="DEC-k512",    seq=512,  batch=1,  nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=9,  workload="decode", label="DEC-k1k",     seq=1024, batch=1,  nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=10, workload="decode", label="DEC-k2k",     seq=2048, batch=1,  nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=11, workload="decode", label="DEC-k4k",     seq=4096, batch=1,  nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=12, workload="decode", label="DEC-k2k-B8",  seq=2048, batch=8,  nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=13, workload="decode", label="DEC-k2k-B32", seq=2048, batch=32, nheads=32, kv_heads=32, head_dim=128, reuse=""),
    dict(id=14, workload="decode", label="DEC-k2k-GQA", seq=2048, batch=1,  nheads=32, kv_heads=8,  head_dim=128, reuse=""),
]

OUT = Path(__file__).resolve().parent / "configs.csv"
with OUT.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(ROWS[0].keys()) + ["cfg_tag"])
    w.writeheader()
    for r in ROWS:
        r["cfg_tag"] = f"cfg_{r['id']:02d}"
        w.writerow(r)
print(f"wrote {OUT} with {len(ROWS)} rows")
```

- [ ] **Step 2: Run it and verify output**

```bash
mkdir -p result/sim_vs_real_mape/scripts result/sim_vs_real_mape/{traces,ncu_out,sim_logs,figures}
python3 result/sim_vs_real_mape/scripts/gen_configs.py
head -3 result/sim_vs_real_mape/scripts/configs.csv
wc -l result/sim_vs_real_mape/scripts/configs.csv   # expect 15 (1 header + 14 data)
```
Expected: exactly 15 lines; column order matches spec §2.

- [ ] **Step 3: No commit** (scripts in `result/` are gitignored — local only). Just verify CSV opens cleanly in a pandas read: `python3 -c "import pandas as pd; print(pd.read_csv('result/sim_vs_real_mape/scripts/configs.csv'))"`

---

## Task 2: Write `run_tracer.sh` and smoke-test on config 1

**Files:**
- Create: `result/sim_vs_real_mape/scripts/run_tracer.sh`

- [ ] **Step 1: Write the wrapper**

The existing `hw_run/traces/device-0/12.6/fa_4096seq` was generated by `util/tracer_nvbit/run_hw_trace.py`. For a Python entry (fa.py / flashinfer_decode.py) the tracer attaches via `LD_PRELOAD=.../tracer_tool/tracer_tool.so` while the python script runs with controlled argv.

```bash
#!/usr/bin/env bash
# Usage: run_tracer.sh <cfg_id> — reads configs.csv, emits trace to result/sim_vs_real_mape/traces/cfg_<id>/
set -euo pipefail
CFG_ID="${1:?cfg_id required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CFGS="$ROOT/result/sim_vs_real_mape/scripts/configs.csv"
ROW=$(awk -F, -v id="$CFG_ID" 'NR>1 && $1==id' "$CFGS")
[ -z "$ROW" ] && { echo "config $CFG_ID not found"; exit 1; }

IFS=, read -r id workload label seq batch nheads kv_heads head_dim reuse cfg_tag <<<"$ROW"

OUT_DIR="$ROOT/result/sim_vs_real_mape/traces/$cfg_tag"
mkdir -p "$OUT_DIR"

if [ -n "$reuse" ] && [ -d "$ROOT/$reuse" ]; then
    echo "[cfg $CFG_ID] reusing existing trace: $reuse"
    ln -sfn "$ROOT/$reuse" "$OUT_DIR/_reuse_src"
    # Verify the reused trace parameters match by reading kernelslist.g or traces subdir
    exit 0
fi

TRACER_SO="$ROOT/util/tracer_nvbit/tracer_tool/tracer_tool.so"
[ -f "$TRACER_SO" ] || { echo "tracer_tool.so not found at $TRACER_SO — build via util/tracer_nvbit/install_nvbit.sh"; exit 2; }

cd "$OUT_DIR"
case "$workload" in
    fa)
        CMD="python3 $ROOT/gpu-app-collection/flash_attention/fa.py \
             --batch_size $batch --seqlen $seq --nheads $nheads --d $head_dim"
        ;;
    decode)
        CMD="python3 $ROOT/gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py \
             --mode paged --batch $batch --seqlen-k $seq \
             --num-heads $nheads --num-kv-heads $kv_heads --head-dim $head_dim \
             --page-size 16 --iters 1 --warmup 0"
        ;;
esac
echo "[cfg $CFG_ID] tracing: $CMD"
USER_FILTER="0" DYNAMIC_KERNEL_LIMIT_START=1 DYNAMIC_KERNEL_LIMIT_END=0 \
    LD_PRELOAD="$TRACER_SO" $CMD 2>&1 | tee trace.log

# post-process: accel-sim tracer drops raw traces in ./traces/; kernelslist.g is the entry
if [ ! -f traces/kernelslist.g ]; then
    echo "[cfg $CFG_ID] FAILED — traces/kernelslist.g not produced"; exit 3
fi
echo "[cfg $CFG_ID] done. trace at $OUT_DIR/traces/kernelslist.g"
```

- [ ] **Step 2: Smoke-test on config 1 (FA seq=512, fastest)**

```bash
chmod +x result/sim_vs_real_mape/scripts/run_tracer.sh
./result/sim_vs_real_mape/scripts/run_tracer.sh 1
ls -la result/sim_vs_real_mape/traces/cfg_01/traces/kernelslist.g
head -3 result/sim_vs_real_mape/traces/cfg_01/traces/kernelslist.g
```

Expected: `kernelslist.g` exists and starts with `MemcpyHtoD` / kernel descriptor lines.

**If tracer fails:** most likely `tracer_tool.so` not built. Run `./util/tracer_nvbit/install_nvbit.sh` then rebuild tracer per its README. This is the only tooling dependency that isn't yet verified — block on it before bulk.

---

## Task 3: Write `run_ncu.sh` and smoke-test on config 1

**Files:**
- Create: `result/sim_vs_real_mape/scripts/run_ncu.sh`

- [ ] **Step 1: Write the wrapper**

```bash
#!/usr/bin/env bash
# Usage: run_ncu.sh <cfg_id>
# Emits result/sim_vs_real_mape/ncu_out/cfg_<id>.{ncu-rep,csv}
set -euo pipefail
CFG_ID="${1:?cfg_id required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CFGS="$ROOT/result/sim_vs_real_mape/scripts/configs.csv"
ROW=$(awk -F, -v id="$CFG_ID" 'NR>1 && $1==id' "$CFGS")
IFS=, read -r id workload label seq batch nheads kv_heads head_dim reuse cfg_tag <<<"$ROW"

OUT_REP="$ROOT/result/sim_vs_real_mape/ncu_out/$cfg_tag.ncu-rep"
OUT_CSV="$ROOT/result/sim_vs_real_mape/ncu_out/$cfg_tag.csv"

case "$workload" in
    fa)
        CMD="python3 $ROOT/gpu-app-collection/flash_attention/fa.py \
             --batch_size $batch --seqlen $seq --nheads $nheads --d $head_dim"
        ;;
    decode)
        CMD="python3 $ROOT/gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py \
             --mode paged --batch $batch --seqlen-k $seq \
             --num-heads $nheads --num-kv-heads $kv_heads --head-dim $head_dim \
             --page-size 16 --iters 1 --warmup 0"
        ;;
esac

# section set chosen per spec §5.2: speed-of-light + memory + warp state
ncu --set speed-of-light \
    --section MemoryWorkloadAnalysis \
    --section WarpStateStats \
    --section SchedulerStats \
    --target-processes all \
    --replay-mode kernel \
    -f -o "${OUT_REP%.ncu-rep}" \
    $CMD

# export to CSV with all collected metrics flattened
ncu --import "$OUT_REP" --csv --page details > "$OUT_CSV"
echo "[cfg $CFG_ID] ncu done: $OUT_CSV ($(wc -l <"$OUT_CSV") lines)"
```

- [ ] **Step 2: Smoke-test on config 1**

```bash
chmod +x result/sim_vs_real_mape/scripts/run_ncu.sh
./result/sim_vs_real_mape/scripts/run_ncu.sh 1
ls -la result/sim_vs_real_mape/ncu_out/cfg_01.csv
# confirm we got per-kernel rows, not just headers
awk -F, 'NR>1{print $1, $2}' result/sim_vs_real_mape/ncu_out/cfg_01.csv | head -5
```

Expected: CSV has ≥ 20 lines (FA launches ~5-10 kernels × 3 sections ≈ rows). First column should show kernel names like `flash_fwd_kernel`.

- [ ] **Step 3: Time-budget check**

If config 1 took > 5 minutes wall clock, **stop and reconsider**:
- drop `SchedulerStats` section (keeps ~3 sections, halves replay count)
- or drop to `--set speed-of-light` only (lose stall-reason detail, Fig 4 becomes impossible — would need to skip Fig 4)

---

## Task 4: Write `run_sim.sh` leveraging traceL1

**Files:**
- Create: `result/sim_vs_real_mape/scripts/run_sim.sh`

- [ ] **Step 1: Write the wrapper**

traceL1's `TRACE_MAP` is keyed by hard-coded names. Easiest: symlink our trace into a `TRACE_MAP`-known path and pass via `--trace-override`, OR invoke `accel-sim.out` directly. For simplicity use direct invocation:

```bash
#!/usr/bin/env bash
# Usage: run_sim.sh <cfg_id>
# Emits result/sim_vs_real_mape/sim_logs/cfg_<id>.log
set -euo pipefail
CFG_ID="${1:?cfg_id required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CFGS="$ROOT/result/sim_vs_real_mape/scripts/configs.csv"
ROW=$(awk -F, -v id="$CFG_ID" 'NR>1 && $1==id' "$CFGS")
IFS=, read -r id workload label seq batch nheads kv_heads head_dim reuse cfg_tag <<<"$ROW"

source "$ROOT/gpu-simulator/setup_environment.sh"
SIM_BIN="$ROOT/gpu-simulator/bin/release/accel-sim.out"
CONFIG_FILE="$ROOT/gpu-simulator/gpgpu-sim/configs/tested-cfgs/SM80_A100/gpgpusim.config"
TRACE_ROOT="$ROOT/result/sim_vs_real_mape/traces/$cfg_tag"
KERNELSLIST="$TRACE_ROOT/traces/kernelslist.g"
[ -f "$KERNELSLIST" ] || KERNELSLIST="$TRACE_ROOT/_reuse_src/traces/kernelslist.g"
[ -f "$KERNELSLIST" ] || { echo "no trace for $cfg_tag"; exit 1; }

LOG="$ROOT/result/sim_vs_real_mape/sim_logs/$cfg_tag.log"
# Turn OFF large traces (spec §2 note): no l1/l2/hbm/issue trace
cd "$(dirname "$KERNELSLIST")/.."
"$SIM_BIN" \
    -trace "$KERNELSLIST" \
    -config "$CONFIG_FILE" \
    -gpgpu_l1_trace_enable 0 -gpgpu_l2_trace_enable 0 \
    -gpgpu_hbm_trace_enable 0 -issue_trace_enable 0 \
    > "$LOG" 2>&1
echo "[cfg $CFG_ID] sim done. exit=$? log=$LOG"
grep -E "^(gpu_tot_sim_cycle|gpu_tot_ipc|gpgpu_simulation_time)" "$LOG" | tail -5
```

- [ ] **Step 2: Smoke-test on config 1**

```bash
chmod +x result/sim_vs_real_mape/scripts/run_sim.sh
time ./result/sim_vs_real_mape/scripts/run_sim.sh 1
tail -30 result/sim_vs_real_mape/sim_logs/cfg_01.log
```

Expected: log ends with normal GPGPU-Sim shutdown lines (`GPGPU-Sim: ** STATS **`). Sim should finish within 15 minutes for FA-s512.

- [ ] **Step 3: Adjust if sim hangs** — add `-gpgpu_max_completed_cta 50` to cap runtime for the 2 largest configs (FA-s8k, DEC-k2k-B32). Note this as a planned downgrade in Task 15 report.

---

## Task 5: Bulk run tracer for configs 2..14 (serial, ~1-2h)

- [ ] **Step 1: Launch**

```bash
cd /workspace/prefetch
for id in 2 3 4 5 6 7 8 9 10 11 12 13 14; do
    echo "=== TRACER cfg $id ==="
    time ./result/sim_vs_real_mape/scripts/run_tracer.sh "$id" 2>&1 | tail -5
done 2>&1 | tee result/sim_vs_real_mape/tracer_bulk.log
```

- [ ] **Step 2: Verify all 14 succeeded**

```bash
for id in $(seq 1 14); do
    tag=$(printf "cfg_%02d" "$id")
    path=$(ls result/sim_vs_real_mape/traces/$tag/traces/kernelslist.g \
           result/sim_vs_real_mape/traces/$tag/_reuse_src/traces/kernelslist.g \
           2>/dev/null | head -1)
    [ -n "$path" ] && echo "$tag OK ($path)" || echo "$tag MISSING"
done
```

All 14 must print `OK`. If any `MISSING`, debug before proceeding — do not silently drop configs.

---

## Task 6: Bulk run ncu for configs 2..14 (serial, ~1-2h)

- [ ] **Step 1: Launch** (GPU exclusive; must run after tracing finishes)

```bash
for id in 2 3 4 5 6 7 8 9 10 11 12 13 14; do
    echo "=== NCU cfg $id ==="
    time ./result/sim_vs_real_mape/scripts/run_ncu.sh "$id" 2>&1 | tail -3
done 2>&1 | tee result/sim_vs_real_mape/ncu_bulk.log
```

- [ ] **Step 2: Verify all CSVs non-empty**

```bash
for id in $(seq 1 14); do
    tag=$(printf "cfg_%02d" "$id")
    lines=$(wc -l <"result/sim_vs_real_mape/ncu_out/$tag.csv" 2>/dev/null || echo 0)
    [ "$lines" -gt 20 ] && echo "$tag OK ($lines lines)" || echo "$tag THIN ($lines lines)"
done
```

All 14 must be `OK`. Any `THIN` means ncu collected nothing meaningful — re-run that config with `--print-summary per-gpu` for debug.

---

## Task 7: Bulk run sim for all 14 configs in parallel (~2-3h wall)

- [ ] **Step 1: Launch with xargs parallelism (6 workers)**

```bash
seq 1 14 | xargs -n1 -P6 -I{} bash -c \
  './result/sim_vs_real_mape/scripts/run_sim.sh {} 2>&1 | tee result/sim_vs_real_mape/sim_logs/wall_{}.out' \
  2>&1 | tee result/sim_vs_real_mape/sim_bulk.log
```

6 workers on a multi-core box keeps RAM in check (each sim ~3-5 GB). Adjust to `-P4` if machine has < 32 GB or `-P8` if ≥ 64 GB.

- [ ] **Step 2: Verify all sims completed normally**

```bash
for id in $(seq 1 14); do
    tag=$(printf "cfg_%02d" "$id")
    log="result/sim_vs_real_mape/sim_logs/$tag.log"
    if grep -q "GPGPU-Sim: \*\* STATS \*\*" "$log" 2>/dev/null; then
        ipc=$(grep "^gpu_tot_ipc" "$log" | tail -1 | awk '{print $3}')
        echo "$tag OK ipc=$ipc"
    else
        echo "$tag INCOMPLETE"
    fi
done
```

All 14 must be `OK`. Any `INCOMPLETE`: inspect `wall_<id>.out` for OOM / crash; optionally add `-gpgpu_max_completed_cta 50` and re-run just that one.

---

## Task 8: Write `parse_ncu.py`

**Files:**
- Create: `result/sim_vs_real_mape/scripts/parse_ncu.py`

- [ ] **Step 1: Smoke-test data first** — inspect one ncu CSV to learn actual metric column names

```bash
head -5 result/sim_vs_real_mape/ncu_out/cfg_01.csv
# Identify how kernel rows and metric rows are laid out.
# ncu --csv --page details typically emits: ID, Process ID, ..., Section Name, Metric Name, Metric Unit, Metric Value
```

- [ ] **Step 2: Write parser**

```python
#!/usr/bin/env python3
"""Parse one ncu CSV → one row of normalized metrics.

Usage: parse_ncu.py <cfg_id>  (reads ncu_out/cfg_<id>.csv, writes cfg_<id>.metrics.json)
Across all kernels in the trace, we aggregate as follows:
 - runtime_ms     : sum over kernels of "gpu__time_duration.sum" / 1e6
 - ipc            : duration-weighted mean of "sm__inst_executed.avg.per_cycle_active"
 - dram_util_pct  : duration-weighted mean of "dram__throughput.avg.pct_of_peak_sustained_elapsed"
 - l1_hit_pct     : duration-weighted mean of "l1tex__t_sector_hit_rate.pct"
 - l2_hit_pct     : duration-weighted mean of "lts__t_sector_hit_rate.pct"
 - sm_busy_pct    : duration-weighted mean of "sm__throughput.avg.pct_of_peak_sustained_elapsed"
 - stall_<reason> : duration-weighted sum of smsp stall_<reason> percentages (top 5)
"""
from pathlib import Path
import json, sys
import pandas as pd

METRICS = {
    "runtime_ms":    ("gpu__time_duration.sum",                            "sum"),
    "ipc":           ("sm__inst_executed.avg.per_cycle_active",            "wmean"),
    "dram_util_pct": ("dram__throughput.avg.pct_of_peak_sustained_elapsed","wmean"),
    "l1_hit_pct":    ("l1tex__t_sector_hit_rate.pct",                      "wmean"),
    "l2_hit_pct":    ("lts__t_sector_hit_rate.pct",                        "wmean"),
    "sm_busy_pct":   ("sm__throughput.avg.pct_of_peak_sustained_elapsed",  "wmean"),
}
STALL_REASONS = [
    "smsp__average_warp_latency_per_inst_issued",   # replace with actual top-5 stall metric names
    "smsp__warps_issue_stalled_long_scoreboard_per_issue_active",
    "smsp__warps_issue_stalled_short_scoreboard_per_issue_active",
    "smsp__warps_issue_stalled_mio_throttle_per_issue_active",
    "smsp__warps_issue_stalled_barrier_per_issue_active",
    "smsp__warps_issue_stalled_not_selected_per_issue_active",
]

def load_ncu_csv(path: Path) -> pd.DataFrame:
    # ncu CSV has a preamble; find the header row starting with "ID"
    raw = path.read_text().splitlines()
    start = next(i for i, ln in enumerate(raw) if ln.startswith('"ID"') or ln.startswith("ID,"))
    return pd.read_csv(path, skiprows=start)

def wmean(values, weights):
    w = weights.sum()
    return (values * weights).sum() / w if w > 0 else float("nan")

def parse_one(cfg_id: int, ncu_csv: Path, out_json: Path):
    df = load_ncu_csv(ncu_csv)
    # Expected long-format: rows are (kernel × metric). Pivot to wide: kernel rows × metric cols
    wide = df.pivot_table(
        index=["Kernel Name", "Launch Index"] if "Launch Index" in df.columns else "Kernel Name",
        columns="Metric Name",
        values="Metric Value",
        aggfunc="first",
    )
    if "gpu__time_duration.sum" not in wide.columns:
        raise RuntimeError(f"gpu__time_duration.sum absent — CSV schema unexpected")
    weights = pd.to_numeric(wide["gpu__time_duration.sum"], errors="coerce").fillna(0)
    out = {"cfg_id": cfg_id, "n_kernels": len(wide)}
    for name, (col, how) in METRICS.items():
        if col not in wide.columns:
            out[name] = None; continue
        vals = pd.to_numeric(wide[col], errors="coerce").fillna(0)
        out[name] = float(weights.sum() and (vals * weights).sum() / weights.sum()) if how == "wmean" \
                    else float(vals.sum())
    # Convert duration sum to ms (ncu unit is ns)
    if out.get("runtime_ms") is not None:
        out["runtime_ms"] = out["runtime_ms"] / 1e6
    # Stall reason distribution — normalize to 100%
    stall_vals = {}
    for s in STALL_REASONS:
        if s in wide.columns:
            stall_vals[s] = float(wmean(pd.to_numeric(wide[s], errors="coerce").fillna(0), weights))
    total = sum(stall_vals.values()) or 1.0
    out["stalls"] = {k: v / total * 100 for k, v in stall_vals.items()}
    out_json.write_text(json.dumps(out, indent=2))

if __name__ == "__main__":
    cfg_id = int(sys.argv[1])
    root = Path(__file__).resolve().parent.parent
    ncu_csv = root / f"ncu_out/cfg_{cfg_id:02d}.csv"
    out_json = root / f"ncu_out/cfg_{cfg_id:02d}.metrics.json"
    parse_one(cfg_id, ncu_csv, out_json)
    print(f"wrote {out_json}")
```

- [ ] **Step 3: Test on config 1**

```bash
python3 result/sim_vs_real_mape/scripts/parse_ncu.py 1
cat result/sim_vs_real_mape/ncu_out/cfg_01.metrics.json
```

Expected: JSON with numeric values for `runtime_ms`, `ipc`, `dram_util_pct`, `l1_hit_pct`, `l2_hit_pct`, `sm_busy_pct`, plus a `stalls` dict with 5 keys summing to ~100.

- [ ] **Step 4: Iterate on metric names**

ncu's exact metric names vary by version. If any metric comes back `None`, re-run with:
```bash
awk -F, '{print $NF}' result/sim_vs_real_mape/ncu_out/cfg_01.csv | sort -u | grep -iE "hit_rate|throughput|duration|stall" | head -30
```
and update `METRICS` / `STALL_REASONS` dict in `parse_ncu.py` accordingly. **Only proceed once config 1 emits 6 non-None metrics + 5 stall entries.**

- [ ] **Step 5: Run on all 14**

```bash
for id in $(seq 1 14); do python3 result/sim_vs_real_mape/scripts/parse_ncu.py "$id"; done
```

---

## Task 9: Write `parse_sim.py`

**Files:**
- Create: `result/sim_vs_real_mape/scripts/parse_sim.py`

- [ ] **Step 1: Identify sim log fields**

```bash
grep -E "^(gpu_tot_sim_cycle|gpu_tot_ipc|gpu_period|gpu_tot_sim_insn|L1D_total_cache_accesses|L1D_total_cache_hits|L2_total_cache_accesses|L2_total_cache_hits|total_dram_reads|total_dram_writes|gpgpu_simulation_rate|gpgpu_simulation_time|Warp_Inst_Issued_Distro)" result/sim_vs_real_mape/sim_logs/cfg_01.log | head -40
```

Note the exact line formats — `gpu_tot_ipc = 1.234` (with spaces/=) is typical.

- [ ] **Step 2: Write parser**

```python
#!/usr/bin/env python3
"""Parse one GPGPU-Sim log → normalized metrics JSON (matching parse_ncu.py keys).

Aggregation: GPGPU-Sim prints "gpu_tot_*" totals across all kernels; use them directly.
"""
from pathlib import Path
import json, re, sys

# A100 SM80 config peaks (from gpgpusim.config): 108 SMs × 64 lanes × 1.41 GHz × 2 fp16 FMA = 312 TFLOPS
# DRAM peak: 1555 GB/s (80 GB HBM2e)
CORE_CLK_MHZ = 1410    # used to convert cycles → ms
N_SM = 108
PEAK_IPC = 4 * N_SM    # rough upper bound (4 insn/cycle/SM on A100)
PEAK_DRAM_GBPS = 1555

PATTERNS = {
    "cycles":         r"gpu_tot_sim_cycle\s*=\s*(\S+)",
    "ipc":            r"gpu_tot_ipc\s*=\s*(\S+)",
    "insn":           r"gpu_tot_sim_insn\s*=\s*(\S+)",
    "l1d_acc":        r"L1D_total_cache_accesses\s*=\s*(\S+)",
    "l1d_hit":        r"L1D_total_cache_hits\s*=\s*(\S+)",
    "l2_acc":         r"L2_total_cache_accesses\s*=\s*(\S+)",
    "l2_hit":         r"L2_total_cache_hits\s*=\s*(\S+)",
    "dram_reads":     r"total_dram_reads\s*=\s*(\S+)",
    "dram_writes":    r"total_dram_writes\s*=\s*(\S+)",
}
# Stall reasons in GPGPU-Sim: warp_issue_*  (format may differ by fork)
STALL_PATTERN = r"Warp_Issue_Dynamic_Stall_(\w+)\s*=\s*(\S+)"

def grab_last(text, pat):
    m = re.findall(pat, text)
    return float(m[-1]) if m else None

def parse(cfg_id: int, log_path: Path, out_json: Path):
    text = log_path.read_text()
    out = {"cfg_id": cfg_id}
    raw = {k: grab_last(text, p) for k, p in PATTERNS.items()}
    cycles = raw["cycles"] or 0
    runtime_ms = cycles / (CORE_CLK_MHZ * 1e3) if cycles else None
    out["runtime_ms"] = runtime_ms
    out["ipc"] = raw["ipc"]
    out["sm_busy_pct"] = (raw["ipc"] / PEAK_IPC * 100) if raw["ipc"] else None
    # DRAM throughput — bytes transferred / time
    bytes_per_req = 32   # GPGPU-Sim DRAM burst
    dram_bytes = ((raw["dram_reads"] or 0) + (raw["dram_writes"] or 0)) * bytes_per_req
    if runtime_ms and runtime_ms > 0:
        bw_gbps = dram_bytes / (runtime_ms / 1000) / 1e9
        out["dram_util_pct"] = bw_gbps / PEAK_DRAM_GBPS * 100
    else:
        out["dram_util_pct"] = None
    # Cache hit rates
    if raw["l1d_acc"]:
        out["l1_hit_pct"] = raw["l1d_hit"] / raw["l1d_acc"] * 100
    if raw["l2_acc"]:
        out["l2_hit_pct"] = raw["l2_hit"] / raw["l2_acc"] * 100
    # Stall reasons — sum all _total_ stalls, normalize top-5 to 100
    stalls = {}
    for name, val in re.findall(STALL_PATTERN, text):
        stalls[name] = stalls.get(name, 0) + float(val)
    top5 = sorted(stalls.items(), key=lambda kv: -kv[1])[:5]
    total = sum(v for _, v in top5) or 1.0
    out["stalls"] = {k: v / total * 100 for k, v in top5}
    out_json.write_text(json.dumps(out, indent=2))

if __name__ == "__main__":
    cfg_id = int(sys.argv[1])
    root = Path(__file__).resolve().parent.parent
    parse(cfg_id, root / f"sim_logs/cfg_{cfg_id:02d}.log",
                  root / f"sim_logs/cfg_{cfg_id:02d}.metrics.json")
    print("ok")
```

- [ ] **Step 3: Test on config 1**

```bash
python3 result/sim_vs_real_mape/scripts/parse_sim.py 1
cat result/sim_vs_real_mape/sim_logs/cfg_01.metrics.json
```

If any field is `null`: grep for the exact literal in the log and adjust `PATTERNS`. The stall-pattern is the most likely mismatch — if `Warp_Issue_Dynamic_Stall_*` not present, search for alternatives: `grep -E "stall|Stall" result/sim_vs_real_mape/sim_logs/cfg_01.log | awk '{print $1}' | sort -u`. Iterate until all 6 primary metrics + ≥ 3 stall entries populate.

- [ ] **Step 4: Run on all 14**

```bash
for id in $(seq 1 14); do python3 result/sim_vs_real_mape/scripts/parse_sim.py "$id"; done
```

---

## Task 10: Write `collect_metrics.py` — merge ncu + sim + compute MAPE

**Files:**
- Create: `result/sim_vs_real_mape/scripts/collect_metrics.py`

- [ ] **Step 1: Write merger**

```python
#!/usr/bin/env python3
"""Read 14 × (ncu.metrics.json, sim.metrics.json), emit merged_metrics.csv.

Output columns:
 cfg_id, label, workload, <param>, <for each metric>: sim_X / real_X / rel_err_X,
 stall_<r>_sim, stall_<r>_real (normalized %)
"""
from pathlib import Path
import json, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CFGS = pd.read_csv(ROOT / "scripts/configs.csv")

METRIC_KEYS = ["runtime_ms", "ipc", "dram_util_pct",
               "l1_hit_pct", "l2_hit_pct", "sm_busy_pct"]

rows = []
for _, r in CFGS.iterrows():
    cid = int(r["id"]); tag = r["cfg_tag"]
    sim_path = ROOT / f"sim_logs/{tag}.metrics.json"
    ncu_path = ROOT / f"ncu_out/{tag}.metrics.json"
    sim = json.loads(sim_path.read_text())
    ncu = json.loads(ncu_path.read_text())
    row = {"cfg_id": cid, "label": r["label"], "workload": r["workload"],
           "seq": r["seq"], "batch": r["batch"], "nheads": r["nheads"],
           "kv_heads": r["kv_heads"], "head_dim": r["head_dim"]}
    for m in METRIC_KEYS:
        s, t = sim.get(m), ncu.get(m)
        row[f"sim_{m}"]  = s
        row[f"real_{m}"] = t
        row[f"rel_err_{m}"] = None if (s is None or t is None or t == 0) \
                              else (s - t) / t * 100
        row[f"abs_err_{m}"] = None if (s is None or t is None) else abs(s - t) / abs(t or 1) * 100
    # Stall reasons — align keys (best-effort; different taxonomies between sim / ncu)
    ncu_stalls = ncu.get("stalls", {})
    sim_stalls = sim.get("stalls", {})
    all_keys = set(ncu_stalls) | set(sim_stalls)
    for k in sorted(all_keys):
        row[f"stall_{k}_sim"]  = sim_stalls.get(k, 0.0)
        row[f"stall_{k}_real"] = ncu_stalls.get(k, 0.0)
    rows.append(row)

df = pd.DataFrame(rows)
df.to_csv(ROOT / "merged_metrics.csv", index=False)
print(f"wrote {ROOT/'merged_metrics.csv'}: {df.shape}")
print("MAPE per metric:")
for m in METRIC_KEYS:
    col = f"abs_err_{m}"
    if col in df.columns:
        print(f"  {m}: MAPE={df[col].mean():.1f}%  median={df[col].median():.1f}%  max={df[col].max():.1f}%")
```

- [ ] **Step 2: Run and sanity-check**

```bash
python3 result/sim_vs_real_mape/scripts/collect_metrics.py
python3 -c "import pandas as pd; df=pd.read_csv('result/sim_vs_real_mape/merged_metrics.csv'); print(df[['label','sim_ipc','real_ipc','rel_err_ipc','sim_dram_util_pct','real_dram_util_pct']].to_string())"
```

Expected: 14 rows, most `rel_err_*` values in a plausible range ([-50%, 50%]). Any `null` in key columns means parsing dropped — go fix parse_ncu.py or parse_sim.py first.

---

## Task 11: Write `classify_bottleneck.py`

**Files:**
- Create: `result/sim_vs_real_mape/scripts/classify_bottleneck.py`

- [ ] **Step 1: Write classifier**

```python
#!/usr/bin/env python3
"""Add bottleneck-class columns using spec §4 thresholds.

Threshold (tentative, may be tuned post-hoc):
  sm_busy >= 70 & dram_util < 50  → COMPUTE
  dram_util >= 70                 → MEM-BW
  sm_busy < 50 & dram_util < 50   → LATENCY
  else                            → MIXED
"""
from pathlib import Path
import pandas as pd

def classify(sm, dram):
    if pd.isna(sm) or pd.isna(dram): return "UNKNOWN"
    if dram >= 70: return "MEM-BW"
    if sm >= 70 and dram < 50: return "COMPUTE"
    if sm < 50 and dram < 50: return "LATENCY"
    return "MIXED"

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "merged_metrics.csv")
df["sim_class"]  = [classify(s, d) for s, d in zip(df["sim_sm_busy_pct"],  df["sim_dram_util_pct"])]
df["real_class"] = [classify(s, d) for s, d in zip(df["real_sm_busy_pct"], df["real_dram_util_pct"])]
df["agree"] = df["sim_class"] == df["real_class"]
df.to_csv(ROOT / "merged_metrics.csv", index=False)
agree_pct = df["agree"].mean() * 100
print(f"classification agreement: {df['agree'].sum()}/14 = {agree_pct:.0f}%")
print(df[["label","sim_class","real_class","agree"]].to_string(index=False))
```

- [ ] **Step 2: Run and check distribution**

```bash
python3 result/sim_vs_real_mape/scripts/classify_bottleneck.py
```

Expected: 14 rows printed with class + agreement boolean. Look at the overall agreement %. If > 10/14 classes are `MIXED`, thresholds may be too conservative — note for the report to tune them. Do NOT re-tune now; capture the raw distribution first.

---

## Task 12: Write `make_report.py` → `mape_report.md`

**Files:**
- Create: `result/sim_vs_real_mape/scripts/make_report.py`

- [ ] **Step 1: Write report generator**

```python
#!/usr/bin/env python3
"""Emit mape_report.md with:
  Table 1 — Raw metrics side-by-side
  Table 2 — MAPE summary
  Table 3 — Bottleneck classification matrix
  Short commentary on which configs disagree
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "merged_metrics.csv")
METRICS = ["runtime_ms", "ipc", "dram_util_pct", "l1_hit_pct", "l2_hit_pct", "sm_busy_pct"]

def fmt(v, p=2):
    if pd.isna(v): return "—"
    return f"{v:.{p}f}"

lines = ["# Sim vs Real-GPU MAPE Report (FA / Decode)", "", 
         f"> Generated: {pd.Timestamp.now().date()}", "",
         f"> 14 configs (7 FA + 7 Decode) on A100. Spec: "
         f"[2026-04-14-fa-decode-sim-vs-real-mape-design.md](../../specs/2026-04-14-fa-decode-sim-vs-real-mape-design.md)", ""]

# Table 1 — Raw metrics (one row per config, simple columns)
lines += ["## Table 1 — Raw metrics", "",
          "| Config | Workload | Param | sim IPC | real IPC | sim rt(ms) | real rt(ms) | sim DRAM% | real DRAM% | sim L1% | real L1% | sim L2% | real L2% | sim SM% | real SM% |",
          "|--------|----------|-------|---------|----------|-----------|-------------|-----------|------------|---------|---------|---------|---------|---------|---------|"]
for _, r in df.iterrows():
    param = f"seq/kv={r['seq']}, B={r['batch']}, H={r['nheads']}/{r['kv_heads']}, d={r['head_dim']}"
    lines.append("| " + " | ".join([
        r["label"], r["workload"], param,
        fmt(r["sim_ipc"]), fmt(r["real_ipc"]),
        fmt(r["sim_runtime_ms"], 3), fmt(r["real_runtime_ms"], 3),
        fmt(r["sim_dram_util_pct"], 1), fmt(r["real_dram_util_pct"], 1),
        fmt(r["sim_l1_hit_pct"], 1), fmt(r["real_l1_hit_pct"], 1),
        fmt(r["sim_l2_hit_pct"], 1), fmt(r["real_l2_hit_pct"], 1),
        fmt(r["sim_sm_busy_pct"], 1), fmt(r["real_sm_busy_pct"], 1),
    ]) + " |")

# Table 2 — MAPE summary
lines += ["", "## Table 2 — MAPE summary", "",
          "| Metric | MAPE (%) | Median abs err (%) | Max abs err (%) | # configs within ±20% |",
          "|--------|----------|--------------------|-----------------|-----------------------|"]
for m in METRICS:
    col_abs = f"abs_err_{m}"
    col_rel = f"rel_err_{m}"
    valid = df[col_abs].dropna()
    within20 = (df[col_rel].abs() <= 20).sum()
    lines.append(f"| {m} | {valid.mean():.1f} | {valid.median():.1f} | {valid.max():.1f} | {within20}/14 |")

# Table 3 — Classification matrix
lines += ["", "## Table 3 — Bottleneck classification", "",
          "| Config | sim class | real class | agree? |",
          "|--------|-----------|------------|--------|"]
for _, r in df.iterrows():
    mark = "✓" if r["agree"] else "✗"
    lines.append(f"| {r['label']} | {r['sim_class']} | {r['real_class']} | {mark} |")

agree_pct = df["agree"].mean() * 100
disagree = df[~df["agree"]]["label"].tolist()
lines += ["", "## Summary", "",
          f"- Overall bottleneck-classification agreement: **{df['agree'].sum()}/14 ({agree_pct:.0f}%)**",
          f"- Disagreeing configs: {', '.join(disagree) if disagree else '(none)'}",
          f"- Best-aligned metric (lowest MAPE): `{min(METRICS, key=lambda m: df[f'abs_err_{m}'].mean())}`",
          f"- Worst-aligned metric (highest MAPE): `{max(METRICS, key=lambda m: df[f'abs_err_{m}'].mean())}`"]

(ROOT / "mape_report.md").write_text("\n".join(lines))
print(f"wrote {ROOT/'mape_report.md'} ({len(lines)} lines)")
```

- [ ] **Step 2: Run and preview**

```bash
python3 result/sim_vs_real_mape/scripts/make_report.py
head -40 result/sim_vs_real_mape/mape_report.md
```

Expected: three well-formed markdown tables + a summary section.

---

## Task 13: Sanity check — read the tables before producing figures

- [ ] **Step 1: User review gate**

```bash
cat result/sim_vs_real_mape/mape_report.md
```

**Stop and check the actual numbers** before proceeding to figures:

1. Are any MAPE values > 100%? → parser bug, go fix before figures.
2. Is classification `UNKNOWN` anywhere? → a metric is NaN, fix the underlying parser.
3. Does the bottleneck distribution match expectations (FA small seq = COMPUTE, Decode = MEM-BW)? If FA s512 shows MEM-BW (wrong), double-check `parse_sim.py` DRAM-util computation. If Decode k4k shows LATENCY, check sm_busy_pct denominator.

**Do not continue** until these sanity checks pass.

---

## Task 14: Fig 1 production — Roofline (port from prototype)

**Files:**
- Create: `result/sim_vs_real_mape/scripts/fig1_roofline.py`

- [ ] **Step 1: Start from prototype + switch to plot_util.py style**

```python
#!/usr/bin/env python3
"""Fig 1 — Roofline overlay: sim vs real per config (2 subplots: FA | Decode)."""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]  # /workspace/prefetch
sys.path.insert(0, str(_REPO / "ima_plan/07_paper_outline/plot_style"))
from plot_util import apply_style, save_fig

apply_style()
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PAL = {"blue": "#1F4E79", "red": "#8B2E2F"}
ROOT = _REPO / "result/sim_vs_real_mape"
df = pd.read_csv(ROOT / "merged_metrics.csv")

# Arithmetic intensity (flop/byte): sim side uses sim metrics; real side uses ncu
# For simplicity, use a pre-computed column — or derive from sm_busy × peak / dram_util × bw
PEAK_FLOPS = 312e12   # A100 fp16
PEAK_BW    = 1.555e12  # A100 HBM2e

def achieved_tflops(sm_busy_pct):
    return (sm_busy_pct / 100) * PEAK_FLOPS / 1e12

def achieved_ai(sm_busy_pct, dram_util_pct):
    # AI ≈ (SM_busy × peak_flops) / (dram_util × peak_bw)  (flop / byte)
    compute = sm_busy_pct / 100 * PEAK_FLOPS
    bytes_s = max(dram_util_pct / 100 * PEAK_BW, 1e9)
    return compute / bytes_s

fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7), constrained_layout=True)
ai_grid = np.logspace(-1, 2, 200)
roof = np.minimum(PEAK_FLOPS / 1e12, ai_grid * PEAK_BW / 1e12)

for ax, wl, title in [(axes[0], "fa", "(a) Flash Attention"),
                       (axes[1], "decode", "(b) Flashinfer Decode")]:
    sub = df[df["workload"] == wl]
    ax.plot(ai_grid, roof, "k-", lw=1.2)
    ax.axhline(PEAK_FLOPS/1e12, color="gray", ls=":", lw=0.6)
    for _, r in sub.iterrows():
        ai_s = achieved_ai(r["sim_sm_busy_pct"], r["sim_dram_util_pct"])
        ai_r = achieved_ai(r["real_sm_busy_pct"], r["real_dram_util_pct"])
        tp_s = achieved_tflops(r["sim_sm_busy_pct"])
        tp_r = achieved_tflops(r["real_sm_busy_pct"])
        ax.plot([ai_s, ai_r], [tp_s, tp_r], color="0.5", lw=0.7, zorder=1)
        ax.scatter(ai_r, tp_r, marker="o", s=30, color=PAL["blue"],
                   edgecolor="k", lw=0.4, zorder=3)
        ax.scatter(ai_s, tp_s, marker="^", s=30, color=PAL["red"],
                   edgecolor="k", lw=0.4, zorder=3)
        ax.annotate(r["label"].split("-", 1)[1], (ai_r, tp_r),
                    xytext=(3, 3), textcoords="offset points", fontsize=6)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Arithmetic Intensity (FLOP/byte)")
    ax.set_ylabel("Achieved TFLOPS")
    ax.set_title(title, fontsize=9)

from matplotlib.lines import Line2D
handles = [Line2D([0],[0], marker="o", color="w", markerfacecolor=PAL["blue"],
                  markeredgecolor="k", label="Real (ncu)", markersize=6),
           Line2D([0],[0], marker="^", color="w", markerfacecolor=PAL["red"],
                  markeredgecolor="k", label="Sim", markersize=6),
           Line2D([0],[0], color="k", lw=1.2, label="A100 roofline")]
fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
           bbox_to_anchor=(0.5, 1.04), fontsize=8)

save_fig(fig, "fig1_roofline", ROOT / "figures")
plt.close(fig)
print("fig1 done")
```

- [ ] **Step 2: Run and inspect**

```bash
python3 result/sim_vs_real_mape/scripts/fig1_roofline.py
ls -la result/sim_vs_real_mape/figures/fig1_roofline.{pdf,svg}
```

- [ ] **Step 3: If AI axis compresses all points into a tight cluster**, switch to `ax.set_xscale("linear")` or widen `ai_grid`. Do not tune endlessly — one adjustment then move on.

---

## Task 15: Fig 2, 3, 4 production — port from prototypes

**Files:**
- Create: `result/sim_vs_real_mape/scripts/fig2_mape_breakdown.py`
- Create: `result/sim_vs_real_mape/scripts/fig3_trajectory.py`
- Create: `result/sim_vs_real_mape/scripts/fig4_stall_stacked.py`

Each script follows the same pattern as `fig1_roofline.py`:
1. Imports `apply_style, save_fig` from `plot_util`
2. Reads `merged_metrics.csv`
3. Draws the figure exactly as the corresponding `_proto_fig*.png` but with real data
4. Uses the shared `PAL` dict (blue #1F4E79, orange #B96D29, green #3F6B35, red #8B2E2F, purple #5E3E7F)
5. Calls `save_fig(fig, "figN_name", ROOT / "figures")`
6. `plt.close(fig)`

The prototype implementations in `_proto_all_figures.py` are the reference — copy their bodies and swap synthetic data sources for `df` columns.

- [ ] **Step 1: Port fig2 (6 subplots, relative error bars)** — same logic as `fig2_mape_breakdown()` in prototype; X-axis uses `df["label"]`, Y is `df[f"rel_err_{m}"]`.

- [ ] **Step 2: Port fig3 (trajectory line)** — X = `df[df.workload=='fa'].seq` on log scale; Y = `real_dram_util_pct`, `sim_dram_util_pct`, `real_sm_busy_pct`, `sim_sm_busy_pct`; dashed for sim, solid for real.

- [ ] **Step 3: Port fig4 (stall stacked)** — reconstruct `sim_stall` and `real_stall` matrices from `stall_<reason>_sim` / `stall_<reason>_real` columns; keep the 14×2 stacked bar layout, shared PAL colors, alpha 0.55 for real.

- [ ] **Step 4: Run all three and inspect**

```bash
for s in fig2_mape_breakdown fig3_trajectory fig4_stall_stacked; do
    python3 result/sim_vs_real_mape/scripts/$s.py
done
ls result/sim_vs_real_mape/figures/*.pdf
```

Expected: 4 PDFs + 4 SVGs in `figures/`.

---

## Task 16: Copy deliverables to tracked `docs/`

- [ ] **Step 1: Create tracked results dir and copy**

```bash
mkdir -p docs/superpowers/specs/sim_vs_real_mape_results
cp result/sim_vs_real_mape/mape_report.md docs/superpowers/specs/sim_vs_real_mape_results/
cp result/sim_vs_real_mape/figures/fig*.pdf docs/superpowers/specs/sim_vs_real_mape_results/
cp result/sim_vs_real_mape/merged_metrics.csv docs/superpowers/specs/sim_vs_real_mape_results/
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/sim_vs_real_mape_results/
git commit -m "$(cat <<'EOF'
docs(results): FA/decode sim-vs-real MAPE experiment deliverables

14 configs on A100, comparing GPGPU-Sim vs Nsight Compute for FA (prefill)
and flashinfer decode. Includes raw metrics CSV, MAPE report with three
tables, and four figures (roofline overlay, per-metric MAPE, bottleneck
trajectory, stall composition). Non-IMA internal experiment.
EOF
)"
```

---

## Task 17: Session review

- [ ] **Step 1: Run session-review skill**

```bash
# Per CLAUDE.md routing, update experiment_progress.md with a one-line entry
# and run /update-ima-index if ima_plan/ changed.
```

- [ ] **Step 2: Cross-check spec requirements**

Walk through spec §5.3 once more and confirm all 4 figures exist, all 3 tables are in the report, and the user-preference constraints in §9 are met:
- [ ] Figures are not all bar charts ✓ (scatter + bar + line + stacked bar)
- [ ] ≥ 2 multi-subplot figures ✓ (Fig 1, Fig 2)
- [ ] Roofline figure included ✓ (Fig 1)
- [ ] Raw data tables in report ✓ (Table 1/2/3)
- [ ] Prototype-first workflow followed ✓

- [ ] **Step 3: Capture follow-up notes**

If any config had `UNKNOWN` / `MIXED` classification due to threshold boundaries, note the ranges in the report's summary section and recommend a threshold tune in a follow-up session. Do not re-run the experiment today.

---

## Post-execution notes

**If running out of time in any phase:**

1. **Trace stage blocked** (tracer_tool.so missing): generate traces for just the 3 reusable ones (4, 8, 11) + 3 smaller ones (1, 2, 9); downgrade to 6-config report, keep same figure layout.
2. **ncu stage blocked** (permission): drop Fig 4 (no stall data), keep Fig 1/2/3 with just SoL-level metrics.
3. **Sim stage too slow**: add `-gpgpu_max_completed_cta 50` for the 2 largest configs only; note the CTA cap in Table 1 as a footnote.

**Do not**:
- Mix data from different ncu section sets without labeling
- Silently drop a config — every missing config must be documented in mape_report.md
- Tune the bottleneck-classification threshold mid-run (only after the first Table 3 is produced)
