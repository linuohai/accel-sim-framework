#!/bin/bash
# Bug-Fix & Speculative Stride 两组实验
# Group 1: --grasp (bug-fix only, spec_stride=0)
# Group 2: --grasp -grasp_speculative_stride 4 (bug-fix + spec stride)
# + vc_road_sym baseline & ideal
#
# 内存监控: 每30s检查, available < 150GB 暂停启动, < 80GB kill 最新

set -euo pipefail
cd /workspace/prefetch

MEM_PAUSE_THRESHOLD_GB=150   # 暂停启动新实验
MEM_KILL_THRESHOLD_GB=80     # 紧急 kill
CHECK_INTERVAL=30            # 秒
LOG_DIR="result/log"
REPORT="ima_plan/06_evaluation_plan/bugfix_specstride_batch_report.md"

# 38 workloads (excluding PR)
WORKLOADS=(
    bfs_cit_sym sssp_cit_sym bc_cit_sym cc_cit_sym spmv_cit_sym vc_cit_sym
    bfs_cit_dir sssp_cit_dir bc_cit_dir
    bfs_web_sym sssp_web_sym bc_web_sym cc_web_sym spmv_web_sym vc_web_sym
    bfs_web_dir sssp_web_dir bc_web_dir
    bfs_flickr_sym sssp_flickr_sym bc_flickr_sym cc_flickr_sym spmv_flickr_sym
    bfs_flickr_dir sssp_flickr_dir bc_flickr_dir
    bfs_road_sym sssp_road_sym bc_road_sym cc_road_sym spmv_road_sym vc_road_sym
    bfs_road_dir sssp_road_dir bc_road_dir
    bfs_socLJ_sym bfs_socLJ_dir spmv_socLJ_sym
)

get_avail_gb() {
    awk '/MemAvailable/ {printf "%d", $2/1024/1024}' /proc/meminfo
}

wait_for_memory() {
    while true; do
        local avail=$(get_avail_gb)
        if [ "$avail" -ge "$MEM_PAUSE_THRESHOLD_GB" ]; then
            return
        fi
        echo "[MEM-WAIT] $(date '+%H:%M:%S') available=${avail}GB < ${MEM_PAUSE_THRESHOLD_GB}GB, waiting..."
        sleep $CHECK_INTERVAL
    done
}

emergency_check() {
    local avail=$(get_avail_gb)
    if [ "$avail" -lt "$MEM_KILL_THRESHOLD_GB" ]; then
        echo "[MEM-EMERGENCY] $(date '+%H:%M:%S') available=${avail}GB < ${MEM_KILL_THRESHOLD_GB}GB!"
        # Kill the most recently started accel-sim process
        local newest_pid=$(ps aux | grep '[a]ccel-sim.out' | sort -k9 -r | head -1 | awk '{print $2}')
        if [ -n "$newest_pid" ]; then
            echo "[MEM-EMERGENCY] Killing newest sim PID=$newest_pid"
            kill "$newest_pid" 2>/dev/null || true
        fi
    fi
}

launch_experiment() {
    local trace_key="$1"
    local log_suffix="$2"
    local extra_flags="$3"

    local log_name="${trace_key}_${log_suffix}"

    # Skip if already completed
    if [ -f "$LOG_DIR/${log_name}.log" ] && grep -q "status=COMPLETE" "$LOG_DIR/${log_name}.log" 2>/dev/null; then
        echo "[SKIP] $log_name already COMPLETE"
        return
    fi

    wait_for_memory

    echo "[LAUNCH] $(date '+%H:%M:%S') $log_name (avail=$(get_avail_gb)GB)"
    ./traceL1 --grasp $extra_flags \
        --no-l1-trace --no-l2-trace --no-hbm-trace \
        "$trace_key" "$log_name" &

    # Brief pause between launches to avoid thundering herd
    sleep 1
}

# --- Background memory monitor ---
monitor_memory() {
    while true; do
        sleep $CHECK_INTERVAL
        emergency_check
        local avail=$(get_avail_gb)
        local n_sims=$(ps aux | grep '[a]ccel-sim.out' | wc -l)
        echo "[MONITOR] $(date '+%H:%M:%S') sims=$n_sims avail=${avail}GB" >> "$REPORT"
    done
}

# Initialize report
cat > "$REPORT" <<'EOF'
# Bug-Fix & Speculative Stride Batch Report

> Started: $(date)

## Launch Log
EOF
echo "> Started: $(date)" >> "$REPORT"

# Start memory monitor in background
monitor_memory &
MONITOR_PID=$!
trap "kill $MONITOR_PID 2>/dev/null; wait $MONITOR_PID 2>/dev/null" EXIT

echo "=========================================="
echo "Phase 0: vc_road_sym baseline + ideal"
echo "=========================================="

# vc_road_sym baseline (no GRASP)
vc_base_log="vc_road_sym_baseline_v2"
if [ ! -f "$LOG_DIR/${vc_base_log}.log" ] || ! grep -q "status=COMPLETE" "$LOG_DIR/${vc_base_log}.log" 2>/dev/null; then
    wait_for_memory
    echo "[LAUNCH] $(date '+%H:%M:%S') $vc_base_log (baseline)"
    ./traceL1 --no-l1-trace --no-l2-trace --no-hbm-trace \
        vc_road_sym "$vc_base_log" &
    sleep 1
fi

# vc_road_sym ideal L1D
vc_ideal_log="vc_road_sym_ideal_v2"
if [ ! -f "$LOG_DIR/${vc_ideal_log}_ideal_l1d.log" ] || ! grep -q "status=COMPLETE" "$LOG_DIR/${vc_ideal_log}_ideal_l1d.log" 2>/dev/null; then
    wait_for_memory
    echo "[LAUNCH] $(date '+%H:%M:%S') $vc_ideal_log (ideal L1D)"
    ./traceL1 --ideal-l1d --no-l1-trace --no-l2-trace --no-hbm-trace \
        vc_road_sym "$vc_ideal_log" &
    sleep 1
fi

echo "=========================================="
echo "Phase 1: Group 1 — Bug-Fix Only (38 experiments)"
echo "=========================================="

for wl in "${WORKLOADS[@]}"; do
    launch_experiment "$wl" "g1_bugfix" ""
done

echo "=========================================="
echo "Phase 2: Group 2 — Bug-Fix + Speculative Stride (38 experiments)"
echo "=========================================="

for wl in "${WORKLOADS[@]}"; do
    launch_experiment "$wl" "g2_specstride" "--grasp-speculative-stride 4"
done

echo "=========================================="
echo "All 78 experiments launched."
echo "Waiting for completion..."
echo "=========================================="

# Wait for all background jobs (except monitor)
JOBS=$(jobs -p | grep -v $MONITOR_PID)
for job in $JOBS; do
    wait "$job" 2>/dev/null || true
done

echo "[DONE] $(date '+%H:%M:%S') All experiments finished."
echo "## Completion: $(date)" >> "$REPORT"

# Count results
echo ""
echo "=== Results Summary ==="
g1_done=$(ls "$LOG_DIR"/*_g1_bugfix.log 2>/dev/null | xargs grep -l "status=COMPLETE" 2>/dev/null | wc -l)
g2_done=$(ls "$LOG_DIR"/*_g2_specstride.log 2>/dev/null | xargs grep -l "status=COMPLETE" 2>/dev/null | wc -l)
echo "Group 1 (bug-fix): $g1_done / 38 COMPLETE"
echo "Group 2 (spec stride): $g2_done / 38 COMPLETE"
