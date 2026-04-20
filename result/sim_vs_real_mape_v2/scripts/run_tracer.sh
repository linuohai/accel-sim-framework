#!/usr/bin/env bash
# v2 NVBit tracer wrapper with Discovery/Filter/Verify 3-stage support.
# Usage:
#   run_tracer.sh --discovery <cfg_id>    # unfiltered trace, for first-time kernel name discovery
#   run_tracer.sh --filter <cfg_id>       # use kernel_regex from configs.csv as DYNAMIC_KERNEL_RANGE
set -euo pipefail

MODE="${1:?mode required: --discovery or --filter}"
CFG_ID="${2:?cfg_id required}"

case "$MODE" in
    --discovery|--filter) ;;
    *) echo "unknown mode $MODE; use --discovery or --filter"; exit 10;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CFGS="$ROOT/result/sim_vs_real_mape_v2/scripts/configs.csv"
[ -f "$CFGS" ] || { echo "configs.csv not found at $CFGS"; exit 1; }

ROW=$(awk -F, -v id="$CFG_ID" 'NR>1 && $1==id' "$CFGS" | tr -d '\r')
[ -z "$ROW" ] && { echo "config $CFG_ID not found in $CFGS"; exit 1; }

# 16-col schema: id, workload, label, seq, batch, nheads, kv_heads, head_dim,
#                page_size, M, K, N, rms_M, rms_hidden, kernel_regex, cfg_tag
IFS=, read -r id workload label seq batch nheads kv_heads head_dim \
              page_size M K N rms_M rms_hidden kernel_regex cfg_tag <<<"$ROW"

if [ "$MODE" = "--discovery" ]; then
    OUT_DIR="$ROOT/result/sim_vs_real_mape_v2/discovery/$cfg_tag"
    KERNEL_RANGE=""
else
    OUT_DIR="$ROOT/result/sim_vs_real_mape_v2/traces/$cfg_tag"
    if [ "$kernel_regex" = "TBD" ] || [ -z "$kernel_regex" ]; then
        echo "[cfg $CFG_ID] FATAL: kernel_regex is '$kernel_regex' — run --discovery first, then populate configs.csv"
        exit 2
    fi
    # NVBit syntax: <id_range>@<regex>. Wrap raw regex with "0-@" (open-ended ID
    # range from kernel 0). Without this prefix NVBit tries std::stoull on the
    # whole regex and throws — the exception surfaces as PyTorch RuntimeError
    # because NVBit's callback fires inside cuCtxCreate.
    KERNEL_RANGE="0-@${kernel_regex}"
fi

mkdir -p "$OUT_DIR/traces"

TRACER_SO="$ROOT/util/tracer_nvbit/tracer_tool/tracer_tool.so"
[ -f "$TRACER_SO" ] || { echo "tracer_tool.so not found at $TRACER_SO"; exit 2; }
POST_PROC="$ROOT/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing"
[ -f "$POST_PROC" ] || { echo "post-traces-processing not found at $POST_PROC"; exit 2; }

# Dispatch per-workload python command. rmsnorm uses agent_exp venv (vLLM).
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
        echo "unknown workload: $workload"; exit 4;;
esac

cd "$OUT_DIR"
echo "[cfg $CFG_ID] mode=$MODE workload=$workload kernel_regex='$KERNEL_RANGE'"
echo "[cfg $CFG_ID] cmd: ${CMD[*]}"
rm -f traces/*.trace traces/*.traceg traces/*.trace.xz traces/*.traceg.xz traces/kernelslist traces/kernelslist.g 2>/dev/null || true

DYNAMIC_KERNEL_RANGE="$KERNEL_RANGE" TRACES_FOLDER="$OUT_DIR" \
    CUDA_INJECTION64_PATH="$TRACER_SO" "${CMD[@]}" 2>&1 | tee trace.log

echo "[cfg $CFG_ID] running post-traces-processing..."
"$POST_PROC" "$OUT_DIR/traces" 2>&1 | tee -a trace.log
rm -f "$OUT_DIR/traces"/*.trace 2>/dev/null || true

if [ ! -f traces/kernelslist.g ]; then
    echo "[cfg $CFG_ID] FAILED — traces/kernelslist.g not produced"
    tail -30 trace.log
    exit 3
fi

# Post-filter: NVBit sometimes leaks non-matching kernels into the trace
# (name-resolution timing). Re-filter kernelslist.g with the same regex
# used for NCU parsing, so sim and NCU see the exact same kernel set.
if [ "$MODE" = "--filter" ]; then
    TMP=$(mktemp)
    KEEP=0
    DROP=0
    while IFS= read -r line; do
        if [[ "$line" == *.traceg.xz ]]; then
            kname=$(xzcat "traces/$line" 2>/dev/null | head -1 \
                    | sed -nE 's/.*kernel name = ([^ ,]+).*/\1/p')
            if [[ -n "$kname" && "$kname" =~ $kernel_regex ]]; then
                echo "$line" >> "$TMP"
                KEEP=$((KEEP+1))
            else
                DROP=$((DROP+1))
                echo "[cfg $CFG_ID] post-filter DROP: $line -> $kname"
            fi
        else
            echo "$line" >> "$TMP"
        fi
    done < "traces/kernelslist.g"
    mv "$TMP" "traces/kernelslist.g"
    echo "[cfg $CFG_ID] post-filter: kept $KEEP kernel, dropped $DROP"
fi

KCOUNT=$(wc -l < traces/kernelslist.g)
echo "[cfg $CFG_ID] done. mode=$MODE kernelslist.g has $KCOUNT kernels"
echo "[cfg $CFG_ID] output: $OUT_DIR/traces/kernelslist.g"

if [ "$MODE" = "--filter" ]; then
    echo "[cfg $CFG_ID] Filter mode verification:"
    echo "  - kernel count: $KCOUNT (compare to discovery target count manually)"
    echo "  - kernel names:"
    head -5 traces/kernelslist.g | sed 's/^/      /'
fi

{ ls -la traces/ | head -10; } || true
