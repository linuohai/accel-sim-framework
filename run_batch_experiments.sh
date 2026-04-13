#!/bin/bash
# Batch experiment runner — baseline + GRASP parallel execution
# Usage: ./run_batch_experiments.sh [baseline|grasp|all]
# Monitors memory, detects OOM kills, logs results to evaluation report

set -o pipefail

BASE_DIR="/workspace/prefetch"
REPORT="$BASE_DIR/ima_plan/06_evaluation_plan/batch_run_report.md"
LOG_DIR="$BASE_DIR/result/log"
TRACEL1="$BASE_DIR/traceL1"
COMMON_FLAGS="--no-l1-trace --no-l2-trace --no-hbm-trace"

# ── setup ──────────────────────────────────────────────
source "$BASE_DIR/gpu-simulator/setup_environment.sh" 2>/dev/null

MODE="${1:-all}"   # baseline | grasp | all

declare -A PIDS      # pid -> "key mode"
declare -A START_T   # pid -> start epoch

# ── workload definitions ───────────────────────────────

BASELINE_KEYS=(
  # cit-Patents sym=1 补充
  vc_ima_high symgs_ima_high
  # cit-Patents dir
  bfs_cit_dir sssp_cit_dir bc_cit_dir symgs_cit_dir
  # web-Google sym=1 补充
  vc_ima_med symgs_ima_med
  # web-Google dir
  bfs_web_dir sssp_web_dir bc_web_dir symgs_web_dir
  # flickr
  bfs_flickr_dir bfs_flickr_sym sssp_flickr_dir sssp_flickr_sym
  bc_flickr_dir bc_flickr_sym cc_flickr spmv_flickr
  # roadNet-CA
  bfs_road_dir bfs_road_sym sssp_road_dir sssp_road_sym
  bc_road_dir bc_road_sym cc_road spmv_road symgs_road_dir
  # soc-LiveJournal1
  bfs_socLJ_dir bfs_socLJ_sym spmv_socLJ
)

GRASP_KEYS=(
  # cit-Patents sym=1
  bfs_ima_high sssp_ima_high bc_ima_high cc_ima_high spmv_ima_high
  vc_ima_high symgs_ima_high
  # cit-Patents dir
  bfs_cit_dir sssp_cit_dir bc_cit_dir symgs_cit_dir
  # web-Google sym=1
  bfs_ima_med sssp_ima_med bc_ima_med cc_ima_med spmv_ima_med
  vc_ima_med symgs_ima_med
  # web-Google dir
  bfs_web_dir sssp_web_dir bc_web_dir symgs_web_dir
  # flickr
  bfs_flickr_dir bfs_flickr_sym sssp_flickr_dir sssp_flickr_sym
  bc_flickr_dir bc_flickr_sym cc_flickr spmv_flickr
  # roadNet-CA
  bfs_road_dir bfs_road_sym sssp_road_dir sssp_road_sym
  bc_road_dir bc_road_sym cc_road spmv_road symgs_road_dir
  # soc-LiveJournal1
  bfs_socLJ_dir bfs_socLJ_sym spmv_socLJ
)

# ── report init ────────────────────────────────────────
init_report() {
  cat > "$REPORT" << HEADER
# Batch Experiment Report — $(date '+%Y-%m-%d %H:%M')

## System
- RAM: $(free -h | awk '/Mem:/{print $2}')
- Cores: $(nproc)
- Mode: $MODE

## Results

| Key | Mode | Status | Kernels (done/total) | Time | Peak RSS (MB) | Log |
|-----|------|--------|---------------------|------|---------------|-----|
HEADER
}

# ── launch one experiment ──────────────────────────────
launch() {
  local key="$1"
  local mode="$2"   # baseline | grasp
  local logname="${key}_${mode}"
  local grasp_flag=""
  [ "$mode" = "grasp" ] && grasp_flag="--grasp"

  "$TRACEL1" $grasp_flag $COMMON_FLAGS "$key" "$logname" \
      > /dev/null 2>&1 &
  local pid=$!
  PIDS[$pid]="$key $mode"
  START_T[$pid]=$(date +%s)
  echo "[LAUNCH] $logname (PID=$pid)"
}

# ── check one finished process ─────────────────────────
check_finished() {
  local pid="$1"
  local info="${PIDS[$pid]}"
  local key=$(echo "$info" | awk '{print $1}')
  local mode=$(echo "$info" | awk '{print $2}')
  local logname="${key}_${mode}"
  local logfile="$LOG_DIR/${logname}.log"
  local elapsed=$(( $(date +%s) - ${START_T[$pid]} ))
  local hours=$(echo "scale=1; $elapsed/3600" | bc)

  # Check exit code
  wait "$pid" 2>/dev/null
  local exit_code=$?

  # Check kernel completion
  local completed=0
  [ -f "$logfile" ] && completed=$(grep -c "kernel_name" "$logfile" 2>/dev/null)

  # Check if killed by OOM
  local status="COMPLETE"
  if [ $exit_code -ne 0 ]; then
    if dmesg 2>/dev/null | tail -50 | grep -q "Out of memory.*$pid"; then
      status="OOM_KILLED"
    elif [ $exit_code -eq 137 ] || [ $exit_code -eq 9 ]; then
      status="KILLED(sig=$exit_code)"
    else
      status="FAILED(exit=$exit_code)"
    fi
  fi

  # Get peak RSS from log if available
  local peak_rss="—"

  echo "[$status] $logname: ${completed} kernels, ${hours}h"
  echo "| $key | $mode | $status | $completed | ${hours}h | $peak_rss | ${logname}.log |" >> "$REPORT"

  unset PIDS[$pid]
  unset START_T[$pid]
}

# ── memory monitor ─────────────────────────────────────
log_memory() {
  local used=$(free -g | awk '/Mem:/{print $3}')
  local total=$(free -g | awk '/Mem:/{print $2}')
  local pct=$(( used * 100 / total ))
  local running=${#PIDS[@]}
  echo "[MEM] ${used}/${total} GB (${pct}%) | ${running} running"
  if [ $pct -gt 85 ]; then
    echo "[MEM WARNING] Memory usage > 85%!" | tee -a "$REPORT"
  fi
}

# ── main ───────────────────────────────────────────────
echo "============================================"
echo "Batch Experiment Runner — $(date)"
echo "Mode: $MODE"
echo "============================================"

init_report

# Launch baselines
if [ "$MODE" = "baseline" ] || [ "$MODE" = "all" ]; then
  echo ""
  echo "--- Launching ${#BASELINE_KEYS[@]} baselines ---"
  for key in "${BASELINE_KEYS[@]}"; do
    launch "$key" "baseline"
  done
fi

# Launch GRASP
if [ "$MODE" = "grasp" ] || [ "$MODE" = "all" ]; then
  echo ""
  echo "--- Launching ${#GRASP_KEYS[@]} GRASP experiments ---"
  for key in "${GRASP_KEYS[@]}"; do
    launch "$key" "grasp"
  done
fi

total_launched=${#PIDS[@]}
echo ""
echo "Total launched: $total_launched"
echo ""

# ── monitor loop ───────────────────────────────────────
echo "--- Monitoring (every 60s) ---"
while [ ${#PIDS[@]} -gt 0 ]; do
  sleep 60
  log_memory

  # Check for finished processes
  for pid in "${!PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      check_finished "$pid"
    fi
  done
done

# ── summary ────────────────────────────────────────────
echo ""
echo "============================================"
echo "ALL DONE — $(date)"
echo "============================================"

# Count results
completed=$(grep -c "| COMPLETE |" "$REPORT" 2>/dev/null || echo 0)
failed=$(grep -c "| FAILED\|KILLED\|OOM" "$REPORT" 2>/dev/null || echo 0)

echo "Completed: $completed / $total_launched"
echo "Failed/Killed: $failed"

cat >> "$REPORT" << FOOTER

## Summary
- Total: $total_launched
- Completed: $completed
- Failed/Killed: $failed
- Finished: $(date '+%Y-%m-%d %H:%M')
FOOTER

echo ""
echo "Report: $REPORT"
