#!/bin/bash
# Ideal L1D batch runner — parallel with memory monitoring
set -o pipefail

BASE_DIR="/workspace/prefetch"
REPORT="$BASE_DIR/ima_plan/06_evaluation_plan/ideal_l1d_report.md"
LOG_DIR="$BASE_DIR/result/log"
TRACEL1="$BASE_DIR/traceL1"
COMMON_FLAGS="--ideal-l1d --no-l1-trace --no-l2-trace --no-hbm-trace"

source "$BASE_DIR/gpu-simulator/setup_environment.sh" 2>/dev/null

declare -A PIDS
declare -A START_T

KEYS=(
    bfs_ima_high sssp_ima_high bc_ima_high cc_ima_high spmv_ima_high vc_ima_high symgs_ima_high
    bfs_cit_dir sssp_cit_dir bc_cit_dir symgs_cit_dir
    bfs_ima_med sssp_ima_med bc_ima_med cc_ima_med spmv_ima_med vc_ima_med symgs_ima_med
    bfs_web_dir sssp_web_dir bc_web_dir symgs_web_dir
    bfs_flickr_dir bfs_flickr_sym sssp_flickr_dir sssp_flickr_sym bc_flickr_dir bc_flickr_sym cc_flickr spmv_flickr
    bfs_road_dir bfs_road_sym sssp_road_dir sssp_road_sym bc_road_dir bc_road_sym cc_road spmv_road symgs_road_dir
    bfs_socLJ_dir bfs_socLJ_sym spmv_socLJ
)

# Init report
cat > "$REPORT" << HEADER
# Ideal L1D (Load-Only) Report — $(date '+%Y-%m-%d %H:%M')

## System
- RAM: $(free -h | awk '/Mem:/{print $2}')
- Cores: $(nproc)
- Note: ideal L1D only forces LOAD hits, stores go through normal cache

## Results

| Key | Status | Kernels | Time | Log |
|-----|--------|---------|------|-----|
HEADER

echo "============================================"
echo "Ideal L1D Batch — $(date)"
echo "Launching ${#KEYS[@]} experiments"
echo "============================================"

for key in "${KEYS[@]}"; do
    logname="${key}_ideal"
    # Skip if already done
    if [ -f "$LOG_DIR/${logname}.log" ] && grep -q "^status=COMPLETE" "$LOG_DIR/${logname}.log" 2>/dev/null; then
        echo "[SKIP] $logname (already complete)"
        continue
    fi

    "$TRACEL1" $COMMON_FLAGS "$key" "$logname" > /dev/null 2>&1 &
    pid=$!
    PIDS[$pid]="$key"
    START_T[$pid]=$(date +%s)
    echo "[LAUNCH] $logname (PID=$pid)"
done

total=${#PIDS[@]}
echo ""
echo "Launched: $total"
echo ""

# Monitor loop
echo "--- Monitoring (every 60s) ---"
while [ ${#PIDS[@]} -gt 0 ]; do
    sleep 60
    used=$(free -g | awk '/Mem:/{print $3}')
    total_mem=$(free -g | awk '/Mem:/{print $2}')
    pct=$((used * 100 / total_mem))
    echo "[MEM] ${used}/${total_mem} GB (${pct}%) | ${#PIDS[@]} running"

    if [ $pct -gt 85 ]; then
        echo "[MEM WARNING] >85%!" | tee -a "$REPORT"
    fi

    for pid in "${!PIDS[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            key="${PIDS[$pid]}"
            logname="${key}_ideal"
            logfile="$LOG_DIR/${logname}.log"
            elapsed=$(( $(date +%s) - ${START_T[$pid]} ))
            hours=$(echo "scale=1; $elapsed/3600" | bc)

            wait "$pid" 2>/dev/null
            exit_code=$?

            completed=0
            [ -f "$logfile" ] && completed=$(grep -c "kernel_name" "$logfile" 2>/dev/null)

            status="COMPLETE"
            if [ $exit_code -ne 0 ]; then
                if [ $exit_code -eq 137 ] || [ $exit_code -eq 9 ]; then
                    status="KILLED"
                else
                    status="FAILED(exit=$exit_code)"
                fi
            fi

            echo "[$status] $logname: ${completed} kernels, ${hours}h"
            echo "| $key | $status | $completed | ${hours}h | ${logname}.log |" >> "$REPORT"

            unset PIDS[$pid]
            unset START_T[$pid]
        fi
    done
done

# Summary
completed_count=$(grep -c "COMPLETE" "$REPORT" 2>/dev/null || echo 0)
failed_count=$(grep -cE "FAILED|KILLED" "$REPORT" 2>/dev/null || echo 0)

cat >> "$REPORT" << FOOTER

## Summary
- Total: $total
- Completed: $completed_count
- Failed/Killed: $failed_count
- Finished: $(date '+%Y-%m-%d %H:%M')
FOOTER

echo ""
echo "============================================"
echo "DONE: $completed_count/$total completed, $failed_count failed"
echo "Report: $REPORT"
echo "============================================"
