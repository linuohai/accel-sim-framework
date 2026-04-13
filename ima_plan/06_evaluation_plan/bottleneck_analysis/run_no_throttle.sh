#!/bin/bash
# GRASP Bottleneck Analysis: No-Throttle + Rfail-Retry mode
# 14 workloads (≤4h on full SM), all parallel
# Prerequisites: build with -grasp_no_throttle + GRASP_BOTTLENECK print
# Usage: bash ima_plan/06_evaluation_plan/bottleneck_analysis/run_no_throttle.sh

set -e
source ./gpu-simulator/setup_environment.sh

COMMON="--grasp --no-l1-trace --no-l2-trace --no-hbm-trace"
WORKLOADS="bfs_cit_dir sssp_cit_dir spmv_road_sym spmv_web_sym bfs_road_sym sssp_road_sym cc_road_sym spmv_flickr_sym bfs_web_sym bfs_flickr_sym bc_road_sym sssp_flickr_sym cc_flickr_sym sssp_web_sym"

echo "=== Launching GRASP Bottleneck Experiments (14 runs) ==="
for w in $WORKLOADS; do
    echo "  [NT] $w no_throttle=1"
    ./traceL1 $COMMON --sim-args "-grasp_no_throttle 1" $w ${w}_no_throttle &
done

echo ""
echo "=== All 14 simulations launched ==="
echo "Critical path: sssp_web_sym (~4.1h)"
echo "Monitor: ls -lt result/log/*_no_throttle.log 2>/dev/null | head"

wait
echo "=== All simulations completed ==="
