#!/bin/bash
# 8-GPU parallel trace generation
# Each trace runs on a separate GPU via CUDA_VISIBLE_DEVICES

export PATH=/usr/local/cuda-12.6/bin:$PATH

TRACER="/workspace/prefetch/util/tracer_nvbit/tracer_tool/tracer_tool.so"
POST="/workspace/prefetch/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing"
TRACE_OUT="/workspace/prefetch/hw_run/traces/device-0/12.6"

PANN_BIN="/workspace/prefetch/gpu-app-collection/bin/pannotia"
LSGPU_BIN="/workspace/prefetch/gpu-app-collection/src/cuda/lonestargpu-2.0/bin"
PANN_DATA="/workspace/prefetch/gpu-app-collection/data_dirs/pannotia"
LSGPU_INPUTS="/workspace/prefetch/gpu-app-collection/data_dirs/cuda/lonestargpu-2.0/inputs"

# Single trace job: runs NVBit + post-processing on a specified GPU
run_trace_job() {
    local gpu_id="$1"
    local name="$2"
    local binary="$3"
    local workdir="$4"
    shift 4
    local args=("$@")

    local dest="$TRACE_OUT/$name"
    if [ -f "$dest/traces/kernelslist.g" ]; then
        echo "[SKIP] $name (GPU $gpu_id)"
        return 0
    fi

    echo "[GEN]  $name (GPU $gpu_id) ..."

    local tmpdir=$(mktemp -d /workspace/prefetch/tmp_trace_${name}_XXXXXX)
    cd "$tmpdir"

    if [ -n "$workdir" ] && [ -d "$workdir" ]; then
        for f in "$workdir"/*; do ln -sf "$f" . 2>/dev/null; done
    fi

    # NVBit trace on specified GPU
    if ! CUDA_VISIBLE_DEVICES="$gpu_id" LD_PRELOAD="$TRACER" "$binary" "${args[@]}" > stdout.log 2>&1; then
        echo "[WARN] $name (GPU $gpu_id): non-zero exit"
    fi

    local kl=$(find . -name "kernelslist*" -path "*/traces/*" 2>/dev/null | head -1)
    if [ -z "$kl" ]; then
        echo "[FAIL] $name (GPU $gpu_id) — no kernelslist"
        tail -3 stdout.log
        rm -rf "$tmpdir"
        return 1
    fi

    # Post-process
    "$POST" "$kl" > /dev/null 2>&1
    local traces_dir=$(dirname "$kl")

    if [ ! -f "$traces_dir/kernelslist.g" ]; then
        echo "[FAIL] $name (GPU $gpu_id) — post-processing failed"
        rm -rf "$tmpdir"
        return 1
    fi

    local kcount=$(grep -c "^kernel-" "$traces_dir/kernelslist.g" || echo 0)
    mkdir -p "$dest"
    mv "$traces_dir" "$dest/traces"
    rm -rf "$tmpdir"

    echo "[OK]   $name (GPU $gpu_id) — $kcount kernels"
    return 0
}

echo "============================================"
echo "8-GPU Parallel Trace Generation — $(date)"
echo "============================================"

# ============================================================
# Batch 1: 8 traces on 8 GPUs simultaneously
# ============================================================
echo ""
echo "=== Batch 1: 8 traces in parallel ==="

run_trace_job 0 "pann_color_web-Google"  "$PANN_BIN/color_max" "" "$PANN_DATA/color_max/data/web-Google.graph" 1 &
run_trace_job 1 "pann_color_flickr"      "$PANN_BIN/color_max" "" "$PANN_DATA/color_max/data/flickr.graph" 1 &
run_trace_job 2 "pann_color_roadNet-CA"  "$PANN_BIN/color_max" "" "$PANN_DATA/color_max/data/roadNet-CA.graph" 1 &
run_trace_job 3 "ls_mst_cit-Patents"     "$LSGPU_BIN/mst" "$LSGPU_INPUTS" "cit-Patents.sym.gr" &
run_trace_job 4 "ls_mst_web-Google"      "$LSGPU_BIN/mst" "$LSGPU_INPUTS" "web-Google.sym.gr" &
run_trace_job 5 "ls_mst_flickr"          "$LSGPU_BIN/mst" "$LSGPU_INPUTS" "flickr.sym.gr" &
run_trace_job 6 "ls_mst_roadNet-CA"      "$LSGPU_BIN/mst" "$LSGPU_INPUTS" "roadNet-CA.sym.gr" &
run_trace_job 7 "ls_bh_30k"             "$LSGPU_BIN/bh" "" 30000 50 0 &

echo "Waiting for batch 1..."
wait
echo "Batch 1 complete."

# ============================================================
# Batch 2: remaining 4 traces
# ============================================================
echo ""
echo "=== Batch 2: 4 traces in parallel ==="

run_trace_job 0 "ls_bh_300k"   "$LSGPU_BIN/bh" "" 300000 10 0 &
run_trace_job 1 "ls_dmr_250k"  "$LSGPU_BIN/dmr" "$LSGPU_INPUTS" 250k.2 20 &
run_trace_job 2 "ls_sp_small"  "$LSGPU_BIN/nsp" "$LSGPU_INPUTS" random-42-10-3.cnf 600 &
run_trace_job 3 "ls_pta_ex"    "$LSGPU_BIN/pta" "$LSGPU_INPUTS" ex &

echo "Waiting for batch 2..."
wait
echo "Batch 2 complete."

# ============================================================
# Final report
# ============================================================
echo ""
echo "============================================"
echo "Final Report — $(date)"
echo "============================================"
ls "$TRACE_OUT"/{pann,ls}_*/traces/kernelslist.g 2>/dev/null | while read f; do
    name=$(echo $f | sed "s|.*/12.6/||;s|/traces.*||")
    kc=$(grep -c "^kernel-" "$f")
    sz=$(du -sh "$(dirname $f)" | cut -f1)
    echo "  $name: $kc kernels ($sz)"
done

total=$(ls "$TRACE_OUT"/{pann,ls}_*/traces/kernelslist.g 2>/dev/null | wc -l)
echo ""
echo "Total completed: $total / 17"
