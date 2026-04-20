#!/usr/bin/env bash
# Usage: run_ncu.sh <cfg_id>
# Emits result/sim_vs_real_mape_v2/ncu_out/cfg_<id>.{ncu-rep,csv}
set -euo pipefail
CFG_ID="${1:?cfg_id required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CFGS="$ROOT/result/sim_vs_real_mape_v2/scripts/configs.csv"
ROW=$(awk -F, -v id="$CFG_ID" 'NR>1 && $1==id' "$CFGS" | tr -d '\r')
[ -z "$ROW" ] && { echo "config $CFG_ID not found"; exit 1; }
IFS=, read -r id workload label seq batch nheads kv_heads head_dim page_size M K N rms_M rms_hidden kernel_regex cfg_tag <<<"$ROW"

OUT_DIR="$ROOT/result/sim_vs_real_mape_v2/ncu_out"
mkdir -p "$OUT_DIR"
OUT_REP="$OUT_DIR/$cfg_tag.ncu-rep"
OUT_CSV="$OUT_DIR/$cfg_tag.csv"

SYS_PY="python3"
VENV_PY="/workspace/agent_exp/.venv/bin/python"

case "$workload" in
    fa)
        CMD=("$SYS_PY" "$ROOT/gpu-app-collection/flash_attention/fa.py"
             --batch_size "$batch" --seqlen "$seq" --nheads "$nheads"
             --kv_heads "$kv_heads" --d "$head_dim")
        ;;
    decode)
        CMD=("$SYS_PY" "$ROOT/gpu-app-collection/src/cuda/flashinfer_decode/flashinfer_decode.py"
             --mode paged --batch "$batch" --seqlen-k "$seq"
             --num-heads "$nheads" --num-kv-heads "$kv_heads" --head-dim "$head_dim"
             --page-size "$page_size" --iters 1 --warmup 0 --dtype bf16)
        ;;
    gemm)
        CMD=("$SYS_PY" "$ROOT/gpu-app-collection/src/cuda/gemm/gemm.py"
             --M "$M" --K "$K" --N "$N" --dtype bf16)
        ;;
    rmsnorm)
        CMD=("$VENV_PY" "$ROOT/gpu-app-collection/src/cuda/rmsnorm/rmsnorm.py"
             --M "$rms_M" --hidden "$rms_hidden" --impl vllm)
        ;;
    *)
        echo "unknown workload: $workload"; exit 4
        ;;
esac

echo "[cfg $CFG_ID] profiling: ${CMD[*]}"

sudo -E -n ncu --set speed-of-light \
    --section ComputeWorkloadAnalysis \
    --section MemoryWorkloadAnalysis \
    --section WarpStateStats \
    --section SchedulerStats \
    --metrics sm__throughput.avg.pct_of_peak_sustained_elapsed,dram__throughput.avg.pct_of_peak_sustained_elapsed,smsp__inst_executed.avg.per_cycle_active,smsp__inst_executed.sum,gpc__cycles_elapsed.avg,l1tex__t_sectors.sum,l1tex__t_sectors_pipe_lsu_mem_global_op_ld.sum,l1tex__t_sectors_pipe_lsu_mem_global_op_st.sum,l1tex__t_sectors_hit.sum,lts__t_sectors.sum,lts__t_sectors_op_read.sum,lts__t_sectors_op_write.sum \
    --target-processes all \
    --replay-mode kernel \
    -f -o "${OUT_REP%.ncu-rep}" \
    "${CMD[@]}"

# Human-readable summary (ad-hoc viewing)
OUT_DETAILS="${OUT_DIR}/${cfg_tag}.details.csv"
sudo -E -n ncu --import "$OUT_REP" --csv --page details > "$OUT_DETAILS"

# Canonical parser input: raw metric names (dram__, l1tex__, sm__, smsp__, ...)
sudo -E -n ncu --import "$OUT_REP" --csv --page raw > "$OUT_CSV"

# Fix ownership so claudeuser can read all output files
sudo chown -R claudeuser:claudeuser "$OUT_DIR"

echo "[cfg $CFG_ID] ncu done: $OUT_CSV ($(wc -l <"$OUT_CSV") lines) | details: $OUT_DETAILS ($(wc -l <"$OUT_DETAILS") lines)"
