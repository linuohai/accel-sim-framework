#!/bin/bash
# Do NOT set -e: we want to continue past individual trace failures

# Trace generation for new benchmarks (LonestarGPU + Pannotia)
# Requires: A100 GPU, NVBit tracer built, datasets converted

export PATH=/usr/local/cuda-12.6/bin:$PATH

TRACER="/workspace/prefetch/util/tracer_nvbit/tracer_tool/tracer_tool.so"
POST="/workspace/prefetch/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing"
TRACE_OUT="/workspace/prefetch/hw_run/traces/device-0/12.6"

# Binaries
PANN_BIN="/workspace/prefetch/gpu-app-collection/bin/pannotia"
LSGPU_BIN="/workspace/prefetch/gpu-app-collection/src/cuda/lonestargpu-2.0/bin"

# Data
PANN_DATA="/workspace/prefetch/gpu-app-collection/data_dirs/pannotia"
LSGPU_INPUTS="/workspace/prefetch/gpu-app-collection/data_dirs/cuda/lonestargpu-2.0/inputs"

# Counters
TOTAL=0; DONE=0; FAIL=0; SKIP=0

generate_trace() {
    local name="$1"      # trace key
    local binary="$2"    # full path to binary
    local workdir="$3"   # working directory (cd here before running)
    shift 3
    local args=("$@")    # runtime arguments

    TOTAL=$((TOTAL + 1))
    local dest="$TRACE_OUT/$name"

    if [ -f "$dest/traces/kernelslist.g" ]; then
        echo "[SKIP] $name (already exists)"
        SKIP=$((SKIP + 1))
        return 0
    fi

    echo "[GEN]  $name ..."

    local tmpdir=$(mktemp -d /workspace/prefetch/tmp_trace_XXXXXX)
    cd "$tmpdir"

    # Symlink all files from working directory into tmpdir
    if [ -n "$workdir" ] && [ -d "$workdir" ]; then
        for f in "$workdir"/*; do
            ln -sf "$f" . 2>/dev/null
        done
    fi

    # Run with NVBit tracer
    if ! LD_PRELOAD="$TRACER" "$binary" "${args[@]}" > stdout.log 2>&1; then
        echo "[WARN] $name: binary returned non-zero, checking traces anyway..."
    fi

    # Find kernelslist file
    local kl=$(find . -name "kernelslist*" -path "*/traces/*" 2>/dev/null | head -1)
    if [ -z "$kl" ]; then
        echo "[FAIL] $name — no kernelslist generated"
        cat stdout.log | tail -5
        FAIL=$((FAIL + 1))
        rm -rf "$tmpdir"
        return 1
    fi

    # Post-process
    local traces_dir=$(dirname "$kl")
    "$POST" "$kl" 2>&1 | tail -3

    # Verify
    if [ ! -f "$traces_dir/kernelslist.g" ]; then
        echo "[FAIL] $name — post-processing failed"
        FAIL=$((FAIL + 1))
        rm -rf "$tmpdir"
        return 1
    fi

    local kcount=$(grep -c "^kernel-" "$traces_dir/kernelslist.g" || echo 0)
    echo "[OK]   $name — $kcount kernels"

    # Move to final location
    mkdir -p "$dest"
    mv "$traces_dir" "$dest/traces"

    # Cleanup
    rm -rf "$tmpdir"
    DONE=$((DONE + 1))
    return 0
}

echo "============================================"
echo "New Benchmark Trace Generation — $(date)"
echo "============================================"

# ===========================================================
# Pannotia MIS × 4 SNAP datasets
# ===========================================================
echo ""
echo "--- Pannotia MIS ---"

for ds in cit-Patents web-Google flickr roadNet-CA; do
    generate_trace "pann_mis_${ds}" \
        "$PANN_BIN/mis" "" \
        "$PANN_DATA/mis/data/${ds}.graph" 1
done

# ===========================================================
# Pannotia Color × 4 SNAP datasets
# ===========================================================
echo ""
echo "--- Pannotia Color ---"

for ds in cit-Patents web-Google flickr roadNet-CA; do
    generate_trace "pann_color_${ds}" \
        "$PANN_BIN/color_max" "" \
        "$PANN_DATA/color_max/data/${ds}.graph" 1
done

# ===========================================================
# LonestarGPU MST × 4 SNAP datasets
# ===========================================================
echo ""
echo "--- LonestarGPU MST ---"

for ds in cit-Patents web-Google flickr roadNet-CA; do
    generate_trace "ls_mst_${ds}" \
        "$LSGPU_BIN/mst" "$LSGPU_INPUTS" \
        "${ds}.sym.gr"
done

# ===========================================================
# LonestarGPU BH (N-Body)
# ===========================================================
echo ""
echo "--- LonestarGPU BH ---"

generate_trace "ls_bh_30k" \
    "$LSGPU_BIN/bh" "" \
    30000 50 0

generate_trace "ls_bh_300k" \
    "$LSGPU_BIN/bh" "" \
    300000 10 0

# ===========================================================
# LonestarGPU DMR (Mesh Refinement)
# ===========================================================
echo ""
echo "--- LonestarGPU DMR ---"

generate_trace "ls_dmr_250k" \
    "$LSGPU_BIN/dmr" "$LSGPU_INPUTS" \
    250k.2 20

# ===========================================================
# LonestarGPU SP (Survey Propagation)
# ===========================================================
echo ""
echo "--- LonestarGPU SP ---"

generate_trace "ls_sp_small" \
    "$LSGPU_BIN/nsp" "$LSGPU_INPUTS" \
    random-42-10-3.cnf 600

# ===========================================================
# LonestarGPU PTA (Points-to Analysis)
# ===========================================================
echo ""
echo "--- LonestarGPU PTA ---"

# PTA reads files relative to CWD with specific naming convention
generate_trace "ls_pta_ex" \
    "$LSGPU_BIN/pta" "$LSGPU_INPUTS" \
    ex

# ===========================================================
echo ""
echo "============================================"
echo "Summary: total=$TOTAL done=$DONE skip=$SKIP fail=$FAIL"
echo "============================================"
