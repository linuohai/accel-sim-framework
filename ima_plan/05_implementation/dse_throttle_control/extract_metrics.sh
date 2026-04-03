#!/usr/bin/env bash
# Extract GRASP throttle DSE metrics from experiment logs.
# Usage: ./extract_metrics.sh <log_file> [<log_file2> ...]
#        ./extract_metrics.sh result/log/bfs_1sm_tc_*.log
#
# Output: TSV table with key metrics for each log.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULT_DIR="$SCRIPT_DIR/results"
mkdir -p "$RESULT_DIR"

# Header
printf "Label\tIPC\tData_Miss\tAccuracy%%\tUseful\tUseless\tLate\tRFAIL\tThrottled\tMQ_Peak\tMSHR_Peak\n"

for log in "$@"; do
  label=$(basename "$log" .log)

  # IPC
  ipc=$(grep -oP 'gpu_tot_ipc\s*=\s*\K[\d.]+' "$log" 2>/dev/null | tail -1 || echo "N/A")

  # GRASP_DEMAND SM0
  demand_line=$(grep 'GRASP_DEMAND SM0:' "$log" 2>/dev/null | tail -1 || echo "")
  global_misses=$(echo "$demand_line" | grep -oP 'global_misses=\K\d+' || echo "N/A")
  throttled=$(echo "$demand_line" | grep -oP 'throttle_suppressed=\K\d+' || echo "N/A")

  # GRASP_EFFECT SM0
  effect_line=$(grep 'GRASP_EFFECT SM0:' "$log" 2>/dev/null | tail -1 || echo "")
  useful=$(echo "$effect_line" | grep -oP 'pf_useful=\K\d+' || echo "N/A")
  useless=$(echo "$effect_line" | grep -oP 'pf_useless=\K\d+' || echo "N/A")
  late=$(echo "$effect_line" | grep -oP 'pf_late=\K\d+' || echo "N/A")
  accuracy=$(echo "$effect_line" | grep -oP 'accuracy=\K[\d.]+' || echo "N/A")

  # GRASP_RFAIL SM0
  rfail_line=$(grep 'GRASP_RFAIL SM0:' "$log" 2>/dev/null | tail -1 || echo "")
  rfail=$(echo "$rfail_line" | grep -oP 'total=\K\d+' || echo "N/A")

  # GRASP_L1MQ SM0
  mq_line=$(grep 'GRASP_L1MQ SM0:' "$log" 2>/dev/null | tail -1 || echo "")
  mq_peak=$(echo "$mq_line" | grep -oP 'miss_queue_peak=\K[\d/]+' || echo "N/A")
  mshr_peak=$(echo "$mq_line" | grep -oP 'mshr_peak=\K[\d/]+' || echo "N/A")

  # IMA_DEMAND (global, for data misses)
  ima_line=$(grep '^IMA_DEMAND:' "$log" 2>/dev/null | tail -1 || echo "")
  if [ -n "$ima_line" ]; then
    data_misses=$(echo "$ima_line" | grep -oP 'data_misses=\K\d+' || echo "$global_misses")
  else
    data_misses="$global_misses"
  fi

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$label" "$ipc" "$data_misses" "$accuracy" "$useful" "$useless" "$late" \
    "$rfail" "$throttled" "$mq_peak" "$mshr_peak"
done
