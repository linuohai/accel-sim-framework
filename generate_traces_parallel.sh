#!/bin/bash
# Parallel trace generation for remaining benchmarks
# Strategy: NVBit must serialize (single GPU), but post-processing runs in parallel on CPU

export PATH=/usr/local/cuda-12.6/bin:$PATH

TRACER="/workspace/prefetch/util/tracer_nvbit/tracer_tool/tracer_tool.so"
POST="/workspace/prefetch/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing"
TRACE_OUT="/workspace/prefetch/hw_run/traces/device-0/12.6"

PANN_BIN="/workspace/prefetch/gpu-app-collection/bin/pannotia"
LSGPU_BIN="/workspace/prefetch/gpu-app-collection/src/cuda/lonestargpu-2.0/bin"
PANN_DATA="/workspace/prefetch/gpu-app-collection/data_dirs/pannotia"
LSGPU_INPUTS="/workspace/prefetch/gpu-app-collection/data_dirs/cuda/lonestargpu-2.0/inputs"

TOTAL=0; DONE=0; FAIL=0; SKIP=0
POST_PIDS=()

# Reap completed post-processing jobs
reap_posts() {
    local new_pids=()
    for pid in "${POST_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            new_pids+=("$pid")
        else
            wait "$pid" 2>/dev/null
        fi
    done
    POST_PIDS=("${new_pids[@]}")
}

# Post-process a trace directory in background
post_process_bg() {
    local name="$1"
    local tmpdir="$2"
    (
        local kl=$(find "$tmpdir" -name "kernelslist*" -path "*/traces/*" 2>/dev/null | head -1)
        if [ -z "$kl" ]; then
            echo "[FAIL] $name — no kernelslist generated"
            exit 1
        fi

        local traces_dir=$(dirname "$kl")
        "$POST" "$kl" > /dev/null 2>&1

        if [ ! -f "$traces_dir/kernelslist.g" ]; then
            echo "[FAIL] $name — post-processing failed"
            exit 1
        fi

        local kcount=$(grep -c "^kernel-" "$traces_dir/kernelslist.g" || echo 0)

        local dest="$TRACE_OUT/$name"
        mkdir -p "$dest"
        mv "$traces_dir" "$dest/traces"
        rm -rf "$tmpdir"

        echo "[OK]   $name — $kcount kernels (post-processed)"
    ) &
    POST_PIDS+=($!)
}

# NVBit trace (serial on GPU) + background post-processing
generate_trace() {
    local name="$1"
    local binary="$2"
    local workdir="$3"
    shift 3
    local args=("$@")

    TOTAL=$((TOTAL + 1))
    local dest="$TRACE_OUT/$name"

    if [ -f "$dest/traces/kernelslist.g" ]; then
        echo "[SKIP] $name"
        SKIP=$((SKIP + 1))
        return 0
    fi

    echo "[GEN]  $name ..."

    local tmpdir=$(mktemp -d /workspace/prefetch/tmp_trace_XXXXXX)
    cd "$tmpdir"

    # Symlink input files
    if [ -n "$workdir" ] && [ -d "$workdir" ]; then
        for f in "$workdir"/*; do
            ln -sf "$f" . 2>/dev/null
        done
    fi

    # NVBit trace (GPU-bound, serial)
    if ! LD_PRELOAD="$TRACER" "$binary" "${args[@]}" > stdout.log 2>&1; then
        echo "[WARN] $name: non-zero exit, checking traces..."
    fi

    # Check if trace was generated
    local kl=$(find . -name "kernelslist*" -path "*/traces/*" 2>/dev/null | head -1)
    if [ -z "$kl" ]; then
        echo "[FAIL] $name — no kernelslist"
        cat stdout.log | tail -3
        FAIL=$((FAIL + 1))
        rm -rf "$tmpdir"
        return 1
    fi

    local raw_kernels=$(grep -c "^kernel-" "$(dirname "$kl")/$(basename "$kl")" || echo 0)
    echo "[DONE] $name — $raw_kernels kernels traced, post-processing in background..."

    # Launch post-processing in background (CPU-bound)
    post_process_bg "$name" "$tmpdir"
    DONE=$((DONE + 1))

    # Reap any finished background jobs
    reap_posts

    cd /workspace/prefetch
    return 0
}

echo "============================================"
echo "Parallel Trace Generation — $(date)"
echo "============================================"

# ======================== Pannotia MIS ========================
echo ""
echo "--- Pannotia MIS ---"
for ds in cit-Patents web-Google flickr roadNet-CA; do
    generate_trace "pann_mis_${ds}" "$PANN_BIN/mis" "" "$PANN_DATA/mis/data/${ds}.graph" 1
done

# ======================== Pannotia Color ========================
echo ""
echo "--- Pannotia Color ---"
for ds in cit-Patents web-Google flickr roadNet-CA; do
    generate_trace "pann_color_${ds}" "$PANN_BIN/color_max" "" "$PANN_DATA/color_max/data/${ds}.graph" 1
done

# ======================== LonestarGPU MST ========================
echo ""
echo "--- LonestarGPU MST ---"
for ds in cit-Patents web-Google flickr roadNet-CA; do
    generate_trace "ls_mst_${ds}" "$LSGPU_BIN/mst" "$LSGPU_INPUTS" "${ds}.sym.gr"
done

# ======================== LonestarGPU BH ========================
echo ""
echo "--- LonestarGPU BH ---"
generate_trace "ls_bh_30k" "$LSGPU_BIN/bh" "" 30000 50 0
generate_trace "ls_bh_300k" "$LSGPU_BIN/bh" "" 300000 10 0

# ======================== LonestarGPU DMR ========================
echo ""
echo "--- LonestarGPU DMR ---"
generate_trace "ls_dmr_250k" "$LSGPU_BIN/dmr" "$LSGPU_INPUTS" 250k.2 20

# ======================== LonestarGPU SP ========================
echo ""
echo "--- LonestarGPU SP ---"
generate_trace "ls_sp_small" "$LSGPU_BIN/nsp" "$LSGPU_INPUTS" random-42-10-3.cnf 600

# ======================== LonestarGPU PTA ========================
echo ""
echo "--- LonestarGPU PTA ---"
generate_trace "ls_pta_ex" "$LSGPU_BIN/pta" "$LSGPU_INPUTS" ex

# ======================== Wait for all post-processing ========================
echo ""
echo "Waiting for background post-processing to finish..."
for pid in "${POST_PIDS[@]}"; do
    wait "$pid" 2>/dev/null
done

echo ""
echo "============================================"
echo "Summary: total=$TOTAL done=$DONE skip=$SKIP fail=$FAIL"
echo "============================================"

# Final report
echo ""
echo "=== All traces ==="
ls "$TRACE_OUT"/{pann,ls}_*/traces/kernelslist.g 2>/dev/null | while read f; do
    name=$(echo $f | sed "s|.*/12.6/||;s|/traces.*||")
    kc=$(grep -c "^kernel-" "$f")
    sz=$(du -sh "$(dirname $f)" | cut -f1)
    echo "  $name: $kc kernels, $sz"
done
