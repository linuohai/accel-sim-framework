#!/bin/bash
# Sensitivity/Ablation: Extended workloads (12 new workloads × 9 configs = 108 sims)
# Experiments: Exp-A (Index-Only, Data-Only), Exp-C (D=2,4,8), Exp-D (S1-S4)
# Usage: bash run_exp_extended.sh

set -e
source ./gpu-simulator/setup_environment.sh

COMMON="--grasp --no-l1-trace --no-l2-trace --no-hbm-trace"
NEW_WORKLOADS="bfs_road_sym sssp_road_sym cc_road_sym bc_road_sym sssp_flickr_sym sssp_web_sym vc_web_sym spmv_cit_sym bc_flickr_sym bc_web_sym vc_cit_sym cc_web_sym"

echo "=== Launching Extended Experiments (108 runs) ==="
for w in $NEW_WORKLOADS; do
    # Exp-A: Component Ablation (2 configs)
    echo "  [A] $w Index-Only"
    ./traceL1 $COMMON --sim-args "-grasp_dpu_enable 0" $w ${w}_ablation_ipu &
    echo "  [A] $w Data-Only"
    ./traceL1 $COMMON --sim-args "-grasp_ipu_enable 0" $w ${w}_ablation_dpu &

    # Exp-C: Distance (3 configs)
    for D in 2 4 8; do
        echo "  [C] $w D=$D"
        ./traceL1 $COMMON --sim-args "-grasp_ist_distance $D" $w ${w}_dist${D} &
    done

    # Exp-D: Storage Budget (4 configs)
    echo "  [D] $w S1"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 8 -grasp_tt_size 4 -grasp_prb_capacity 256" $w ${w}_storage_s1 &
    echo "  [D] $w S2"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 16 -grasp_tt_size 8 -grasp_prb_capacity 512" $w ${w}_storage_s2 &
    echo "  [D] $w S3"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 32 -grasp_tt_size 16 -grasp_prb_capacity 1024" $w ${w}_storage_s3 &
    echo "  [D] $w S4"
    ./traceL1 $COMMON --sim-args "-grasp_ct_size 64 -grasp_tt_size 32 -grasp_prb_capacity 2048" $w ${w}_storage_s4 &
done

echo ""
echo "=== All 108 simulations launched ==="
echo "12 workloads × 9 configs"
echo "Critical path: cc_web_sym (~11.6h)"
echo "Monitor: ps aux | grep accel-sim | grep -v grep | wc -l"

wait
echo "=== All simulations completed ==="
