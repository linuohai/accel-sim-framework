#!/bin/bash
# Sensitivity/Ablation: Exp-A (Component Ablation) + Exp-D (Storage Budget)
# 48 simulations, all parallel
# Prerequisites: build with ipu_enable/dpu_enable + PRB hard cap
# Usage: bash run_expA_D.sh

set -e
source ./gpu-simulator/setup_environment.sh

COMMON="--grasp --no-l1-trace --no-l2-trace --no-hbm-trace"
WORKLOADS="bfs_cit_dir sssp_cit_dir bc_cit_dir spmv_web_sym bfs_web_sym cc_flickr_sym spmv_flickr_sym bfs_flickr_sym"

echo "=== Launching Exp-A: Component Ablation (16 runs) ==="
for w in $WORKLOADS; do
    echo "  [A] $w Index-Only (dpu=0)"
    ./traceL1 $COMMON --sim-args "-grasp_dpu_enable 0" \
        $w ${w}_ablation_ipu &
    echo "  [A] $w Data-Only (ipu=0)"
    ./traceL1 $COMMON --sim-args "-grasp_ipu_enable 0" \
        $w ${w}_ablation_dpu &
done

echo "=== Launching Exp-D: Storage Budget (32 runs) ==="
# S1: CT=8 TT=4 PRB=256
for w in $WORKLOADS; do
    echo "  [D] $w S1"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 8 -grasp_tt_size 4 -grasp_prb_capacity 256" \
        $w ${w}_storage_s1 &
done
# S2: CT=16 TT=8 PRB=512
for w in $WORKLOADS; do
    echo "  [D] $w S2"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 16 -grasp_tt_size 8 -grasp_prb_capacity 512" \
        $w ${w}_storage_s2 &
done
# S3: CT=32 TT=16 PRB=1024
for w in $WORKLOADS; do
    echo "  [D] $w S3"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 32 -grasp_tt_size 16 -grasp_prb_capacity 1024" \
        $w ${w}_storage_s3 &
done
# S4: CT=64 TT=32 PRB=2048
for w in $WORKLOADS; do
    echo "  [D] $w S4"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 64 -grasp_tt_size 32 -grasp_prb_capacity 2048" \
        $w ${w}_storage_s4 &
done

echo ""
echo "=== All 48 simulations launched ==="
echo "Critical path: cc_flickr_sym (~4h)"
echo "Monitor: ls -lt result/log/*ablation* result/log/*storage* | head -20"

wait
echo "=== All simulations completed ==="
