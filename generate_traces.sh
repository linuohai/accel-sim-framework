#!/bin/bash
set -e

TRACER="/workspace/prefetch/util/tracer_nvbit/tracer_tool/tracer_tool.so"
POST="/workspace/prefetch/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing"
BIN="/workspace/prefetch/gpu-app-collection/gardenia/bin"
DATA="/workspace/prefetch/gpu-app-collection/gardenia/datasets/real_workload"
TRACE_OUT="/workspace/prefetch/hw_run/traces/device-0/12.6"

generate_trace() {
    local algo_bin="$1"    # e.g. bfs_linear_base
    local algo_dir="$2"    # trace output dir name (same as algo_bin usually)
    local dataset="$3"     # e.g. flickr
    local sym="$4"         # 0 or 1
    local extra_args="$5"  # e.g. "0 1586" for rev=0 source=1586, or just "" for no-source algos
    local trace_subdir="$6" # e.g. mtx___data_flickr_0_0_1586

    local dest="$TRACE_OUT/$algo_dir/$trace_subdir"
    
    # Skip if already exists
    if [ -f "$dest/traces/kernelslist.g" ]; then
        echo "[SKIP] $algo_dir/$trace_subdir (already exists)"
        return 0
    fi

    echo "[GEN]  $algo_dir/$trace_subdir ..."
    
    # Create temp working directory
    local tmpdir=$(mktemp -d /workspace/prefetch/tmp_trace_gen_XXXXXX)
    cd "$tmpdir"
    
    # Run with NVBit tracer
    LD_PRELOAD="$TRACER" "$BIN/$algo_bin" mtx "$DATA/$dataset/$dataset" $sym $extra_args > /dev/null 2>&1
    
    # Post-process — NVBit names the file kernelslist_ctx_<hex>
    local kl=$(ls traces/kernelslist* 2>/dev/null | head -1)
    if [ -n "$kl" ]; then
        "$POST" "$kl" 2>&1 | tail -3
    fi
    
    # Verify kernelslist.g exists
    if [ ! -f traces/kernelslist.g ]; then
        echo "[FAIL] $algo_dir/$trace_subdir — no kernelslist.g generated"
        rm -rf "$tmpdir"
        return 1
    fi
    
    local kcount=$(grep -c "^kernel-" traces/kernelslist.g)
    echo "[OK]   $algo_dir/$trace_subdir — $kcount kernels"
    
    # Move to final location
    mkdir -p "$dest"
    mv traces "$dest/"
    
    # Cleanup
    rm -rf "$tmpdir"
    return 0
}

# Track progress
TOTAL=0
DONE=0
FAIL=0

run_and_count() {
    TOTAL=$((TOTAL + 1))
    if generate_trace "$@"; then
        DONE=$((DONE + 1))
    else
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================"
echo "GRASP Trace Generation — $(date)"
echo "============================================"

# === cit-Patents (3 traces) ===
echo ""
echo "--- cit-Patents ---"
# BC sym=0, source=3569341
run_and_count bc_linear_base bc_linear_base cit-Patents 0 "0 3569341" "mtx___data_cit_Patents_0_0_3569341"
# PR sym=0
run_and_count pr_base pr_base cit-Patents 0 "" "mtx___data_cit_Patents_0"
# SymGS sym=0
run_and_count symgs_base symgs_base cit-Patents 0 "" "mtx___data_cit_Patents_0"

# === web-Google (1 trace) ===
echo ""
echo "--- web-Google ---"
# SymGS sym=0
run_and_count symgs_base symgs_base web-Google 0 "" "mtx___data_web_Google_0"

# === flickr (10 traces — no VC/SymGS due to MAXCOLOR crash) ===
echo ""
echo "--- flickr ---"
# BFS
run_and_count bfs_linear_base bfs_linear_base flickr 0 "0 1586" "mtx___data_flickr_0_0_1586"
run_and_count bfs_linear_base bfs_linear_base flickr 1 "0 1586" "mtx___data_flickr_1_0_1586"
# SSSP (delta=1)
run_and_count sssp_linear_base sssp_linear_base flickr 0 "0 1586 1" "mtx___data_flickr_0_0_1586"
run_and_count sssp_linear_base sssp_linear_base flickr 1 "0 1586 1" "mtx___data_flickr_1_0_1586"
# BC
run_and_count bc_linear_base bc_linear_base flickr 0 "0 1586" "mtx___data_flickr_0_0_1586"
run_and_count bc_linear_base bc_linear_base flickr 1 "0 1586" "mtx___data_flickr_1_0_1586"
# CC sym=1 only
run_and_count cc_base cc_base flickr 1 "" "mtx___data_flickr_1_0"
# SpMV sym=1 only
run_and_count spmv_base spmv_base flickr 1 "" "mtx___data_flickr_1_0"
# PR
run_and_count pr_base pr_base flickr 0 "" "mtx___data_flickr_0"
run_and_count pr_base pr_base flickr 1 "" "mtx___data_flickr_1"

# === roadNet-CA (11 traces — VC sym=1 and SymGS sym=1 already exist) ===
echo ""
echo "--- roadNet-CA ---"
# BFS (directed hub=117563, sym hub=562818)
run_and_count bfs_linear_base bfs_linear_base roadNet-CA 0 "0 117563" "mtx___data_roadNet_CA_0_0_117563"
run_and_count bfs_linear_base bfs_linear_base roadNet-CA 1 "0 562818" "mtx___data_roadNet_CA_1_0_562818"
# SSSP
run_and_count sssp_linear_base sssp_linear_base roadNet-CA 0 "0 117563 1" "mtx___data_roadNet_CA_0_0_117563"
run_and_count sssp_linear_base sssp_linear_base roadNet-CA 1 "0 562818 1" "mtx___data_roadNet_CA_1_0_562818"
# BC
run_and_count bc_linear_base bc_linear_base roadNet-CA 0 "0 117563" "mtx___data_roadNet_CA_0_0_117563"
run_and_count bc_linear_base bc_linear_base roadNet-CA 1 "0 562818" "mtx___data_roadNet_CA_1_0_562818"
# CC sym=1 only
run_and_count cc_base cc_base roadNet-CA 1 "" "mtx___data_roadNet_CA_1_0"
# SpMV sym=1 only
run_and_count spmv_base spmv_base roadNet-CA 1 "" "mtx___data_roadNet_CA_1_0"
# PR
run_and_count pr_base pr_base roadNet-CA 0 "" "mtx___data_roadNet_CA_0"
run_and_count pr_base pr_base roadNet-CA 1 "" "mtx___data_roadNet_CA_1"
# SymGS sym=0 only (sym=1 already exists)
run_and_count symgs_base symgs_base roadNet-CA 0 "" "mtx___data_roadNet_CA_0"

# === soc-LiveJournal1 (3 traces — no VC/SymGS due to MAXCOLOR crash) ===
echo ""
echo "--- soc-LiveJournal1 ---"
# BFS
run_and_count bfs_linear_base bfs_linear_base soc-LiveJournal1 0 "0 10009" "mtx___data_soc_LiveJournal1_0_0_10009"
run_and_count bfs_linear_base bfs_linear_base soc-LiveJournal1 1 "0 10009" "mtx___data_soc_LiveJournal1_1_0_10009"
# SpMV sym=1 only
run_and_count spmv_base spmv_base soc-LiveJournal1 1 "" "mtx___data_soc_LiveJournal1_1_0"

echo ""
echo "============================================"
echo "COMPLETE: $DONE/$TOTAL succeeded, $FAIL failed"
echo "============================================"
