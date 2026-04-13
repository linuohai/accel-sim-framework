#!/bin/bash
# Sensitivity/Ablation: Exp-B2 (TC DSE) + Exp-C (Distance)
# 30 simulations, all parallel, no code changes needed
# Usage: bash run_expB2_C.sh

set -e
source ./gpu-simulator/setup_environment.sh

COMMON="--grasp --no-l1-trace --no-l2-trace --no-hbm-trace"
WORKLOADS="bfs_cit_dir sssp_cit_dir bc_cit_dir spmv_web_sym bfs_web_sym cc_flickr_sym spmv_flickr_sym bfs_flickr_sym"

echo "=== Launching Exp-B2: TC DSE (6 runs) ==="
# Only cit_dir workloads need T50C100/T50C300 (others already have logs)
for w in bfs_cit_dir sssp_cit_dir bc_cit_dir; do
    echo "  [B2] $w T50C100"
    ./traceL1 $COMMON --sim-args "-grasp_tc_mode 4 -grasp_tc_mshr_threshold 50 -grasp_tc_cooldown 100" \
        $w ${w}_g_T50C100 &
    echo "  [B2] $w T50C300"
    ./traceL1 $COMMON --sim-args "-grasp_tc_mode 4 -grasp_tc_mshr_threshold 50 -grasp_tc_cooldown 300" \
        $w ${w}_g_T50C300 &
done

echo "=== Launching Exp-C: Distance Sensitivity (24 runs) ==="
for D in 2 4 8; do
    for w in $WORKLOADS; do
        echo "  [C] $w D=$D"
        ./traceL1 $COMMON --sim-args "-grasp_ist_distance $D" \
            $w ${w}_dist${D} &
    done
done

echo ""
echo "=== All 30 simulations launched ==="
echo "Critical path: cc_flickr_sym (~4h)"
echo "Monitor: ls -lt result/log/*dist* result/log/*T50C* | head -20"

wait
echo "=== All simulations completed ==="
