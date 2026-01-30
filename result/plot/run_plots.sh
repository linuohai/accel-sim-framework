#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

LOG_NAME=""
FORMAT="svg"
BACKEND="local" # local | session

PARALLEL=true
BACKGROUND=false

SESSION_NAME=""
ATTACH=false
KILL_EXISTING=false
AUTO_CLOSE=false
MONITOR=false

DRY_RUN=false

usage() {
  cat <<'EOF'
Usage:
  result/plot/run_plots.sh --log-name <name> [options]

Runs up to 6 plots in parallel:
  - stall reason breakdown (from lightweight stats)
  - stall reason -> topK PC + OTHER (from lightweight stats)
  - L1 cache status over time
  - L2 cache status over time
  - HBM partition bandwidth over time

Options:
  --format <svg|png|both>   Output format (default: svg)
  --backend <local|session> local runs in this shell; session creates a tmux session (default: local)
  --background              (local) detach jobs and return immediately (no final summary)
  --session <name>          (session) tmux session name (default: plots_<log>_<timestamp>)
  --attach                  (session) attach after creating windows
  --kill-existing           (session) kill existing session with same name
  --auto-close              (session) close plot windows on success
  --monitor                 (session) add a monitor window (tails logs)
  --dry-run                 Print what would run
  -h, --help                Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --log-name)
      LOG_NAME="${2:-}"; shift 2 ;;
    --format)
      FORMAT="${2:-}"; shift 2 ;;
    --backend)
      BACKEND="${2:-}"; shift 2 ;;
    --background)
      BACKGROUND=true; shift ;;
    --session)
      SESSION_NAME="${2:-}"; shift 2 ;;
    --attach)
      ATTACH=true; shift ;;
    --kill-existing)
      KILL_EXISTING=true; shift ;;
    --auto-close)
      AUTO_CLOSE=true; shift ;;
    --monitor)
      MONITOR=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2 ;;
  esac
done

if [[ -z "$LOG_NAME" ]]; then
  echo "error: --log-name is required" >&2
  usage
  exit 2
fi

FORMAT="$(echo "$FORMAT" | tr 'A-Z' 'a-z')"
case "$FORMAT" in
  svg|png|both) ;;
  *)
    echo "error: --format must be one of svg|png|both (got: $FORMAT)" >&2
    exit 2 ;;
esac

BACKEND="$(echo "$BACKEND" | tr 'A-Z' 'a-z')"
case "$BACKEND" in
  local|session) ;;
  *)
    echo "error: --backend must be one of local|session (got: $BACKEND)" >&2
    exit 2 ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 not found in PATH" >&2
  exit 127
fi

if [[ "$BACKEND" == "session" ]] && ! command -v tmux >/dev/null 2>&1; then
  echo "error: backend=session requires tmux in PATH" >&2
  exit 127
fi

RUN_ID="plots_${LOG_NAME}_$(date +%Y%m%d_%H%M%S)"
if [[ "$BACKEND" == "session" ]]; then
  LOG_DIR="$BASE_DIR/result/plot/tmux_logs/$RUN_ID"
else
  LOG_DIR="$BASE_DIR/result/plot/direct_logs/$RUN_ID"
fi
mkdir -p "$LOG_DIR"

MATPLOTLIB_OK=false
if python3 -c "import matplotlib, numpy" >/dev/null 2>&1; then
  MATPLOTLIB_OK=true
fi

want_svg=false
want_png=false
case "$FORMAT" in
  svg) want_svg=true ;;
  png) want_png=true ;;
  both) want_svg=true; want_png=true ;;
esac

stall_stats_dir="$BASE_DIR/result/issue_trace/stall_reason_pc_stats/$LOG_NAME"
stall_breakdown_csv="$stall_stats_dir/${LOG_NAME}_stall_reason_breakdown.csv"
stall_hist_csv="$stall_stats_dir/${LOG_NAME}_stall_reason_pc_hist.csv"
stall_topk_csv="$stall_stats_dir/${LOG_NAME}_stall_reason_pc_topk_other.csv"
l1_csv="$BASE_DIR/result/L1cache_trace/${LOG_NAME}_l1.csv"
l2_csv="$BASE_DIR/result/L2cache_trace/${LOG_NAME}_l2.csv"
icnt_bw_csv="$BASE_DIR/result/icnt_bw/${LOG_NAME}_icnt_bw.csv"
l2_bw_csv="$BASE_DIR/result/l2_bw/${LOG_NAME}_l2_bw.csv"
part_csv="$BASE_DIR/result/bandwidth/${LOG_NAME}_hbm_partition.csv"

declare -a JOB_ORDER=("stall_breakdown" "stall_reason_pc" "l1" "l2" "bandwidth")
declare -A JOB_CMD=(
  ["stall_breakdown"]="python3 result/issue_trace/plot/script/plot_single_issue_breakdown.py ${stall_breakdown_csv} --out-name ${LOG_NAME} --format ${FORMAT}"
  ["stall_reason_pc"]="python3 result/issue_trace/plot/script/plot_stall_reason_pc_topk_other.py ${stall_hist_csv} --out-name ${LOG_NAME} --top-k 5 --format ${FORMAT}"
  ["l1"]="python3 result/L1cache_trace/plot/script/plot_l1_status_over_time.py --stem ${LOG_NAME}_l1 --format ${FORMAT}"
  ["l2"]="python3 result/L2cache_trace/plot/script/plot_l2_status_over_time.py --stem ${LOG_NAME}_l2 --format ${FORMAT}"
  ["bandwidth"]="python3 result/bandwidth/plot/script/plot_partition_bandwidth_over_time.py --stem ${LOG_NAME}_hbm_partition --format ${FORMAT}"
)
declare -A JOB_INPUT=(
  ["stall_breakdown"]="$stall_breakdown_csv"
  ["stall_reason_pc"]="$stall_hist_csv"
  ["l1"]="$l1_csv"
  ["l2"]="$l2_csv"
  ["bandwidth"]="$part_csv"
)
declare -A JOB_LOG=(
  ["stall_breakdown"]="$LOG_DIR/stall_breakdown.log"
  ["stall_reason_pc"]="$LOG_DIR/stall_reason_pc.log"
  ["l1"]="$LOG_DIR/l1.log"
  ["l2"]="$LOG_DIR/l2.log"
  ["bandwidth"]="$LOG_DIR/bandwidth.log"
)

needs_matplotlib() {
  local job="$1"
  case "$job" in
    bandwidth)
      return 0 ;;
    stall_breakdown|stall_reason_pc|l1|l2)
      if "$want_png"; then
        return 0
      fi
      return 1 ;;
    *)
      return 1 ;;
  esac
}

check_outputs() {
  local job="$1"
  local start_ts="$2"

  local base=""
  case "$job" in
    stall_breakdown)
      base="$BASE_DIR/result/issue_trace/plot/result/single_issue_breakdown/${LOG_NAME}_stall_breakdown" ;;
    stall_reason_pc)
      base="$BASE_DIR/result/issue_trace/plot/result/stall_reason_pc/${LOG_NAME}_stall_reason_pc_topk_other" ;;
    l1)
      base="$BASE_DIR/result/L1cache_trace/plot/result/l1_cache/${LOG_NAME}_l1_l1_status_stack" ;;
    l2)
      base="$BASE_DIR/result/L2cache_trace/plot/result/l2_cache/${LOG_NAME}_l2_l2_status_stack" ;;
    bandwidth)
      base="$BASE_DIR/result/bandwidth/plot/result/${LOG_NAME}_hbm_partition_partition_bandwidth" ;;
    *)
      echo "unknown job: $job"
      return 1 ;;
  esac

  local -a missing=()
  if "$want_svg"; then
    path="${base}.svg"
    if [[ ! -s "$path" ]]; then
      missing+=("$path")
    else
      mtime=$(stat -c %Y "$path" 2>/dev/null || echo 0)
      if (( mtime < start_ts )); then
        missing+=("${path}(not-updated)")
      fi
    fi
  fi
  if "$want_png"; then
    path="${base}.png"
    if [[ ! -s "$path" ]]; then
      missing+=("$path")
    else
      mtime=$(stat -c %Y "$path" 2>/dev/null || echo 0)
      if (( mtime < start_ts )); then
        missing+=("${path}(not-updated)")
      fi
    fi
  fi

  if (( ${#missing[@]} == 0 )); then
    return 0
  fi
  printf '%s' "${missing[*]}"
  return 1
}

declare -A SKIP_REASON=()
declare -A EXIT_STATUS=()

select_runnable_jobs() {
  SKIP_REASON=()
  local -a runnable=()
  for job in "${JOB_ORDER[@]}"; do
    input="${JOB_INPUT[$job]}"
    if [[ ! -f "$input" ]]; then
      SKIP_REASON["$job"]="missing input: $input"
      continue
    fi
    if needs_matplotlib "$job" && [[ "$MATPLOTLIB_OK" != "true" ]]; then
      SKIP_REASON["$job"]="requires matplotlib+numpy (python3 cannot import them)"
      continue
    fi
    runnable+=("$job")
  done
  printf '%s\n' "${runnable[@]}"
}

run_one() {
  local job="$1"
  local cmd="$2"
  local log_file="$3"

  if "$DRY_RUN"; then
    echo "[dry-run] ($job) $cmd"
    return 0
  fi

  (
    cd "$BASE_DIR"
    set -o pipefail
    export PYTHONUNBUFFERED=1
    {
      echo "[cwd] $(pwd)"
      echo "[job] $job"
      echo "[cmd] $cmd"
      bash -c "$cmd"
    } |& tee "$log_file"
    status=${PIPESTATUS[0]}
    echo "[exit] $status" |& tee -a "$log_file"
    exit "$status"
  )
}

run_local() {
  local start_ts
  start_ts="$(date +%s)"

  mapfile -t runnable < <(select_runnable_jobs)

  echo "run_id: $RUN_ID"
  echo "logs: $LOG_DIR"
  echo "plots: ${JOB_ORDER[*]}"
  echo "format: $FORMAT"
  echo "parallel: true"
  echo ""

  if "$DRY_RUN"; then
    for job in "${JOB_ORDER[@]}"; do
      if [[ -n "${SKIP_REASON[$job]:-}" ]]; then
        echo "[skip] $job: ${SKIP_REASON[$job]}"
        continue
      fi
      echo "[dry-run] ($job) ${JOB_CMD[$job]} -> ${JOB_LOG[$job]}"
    done
    return 0
  fi

  local -a pids=()
  local -a pid_jobs=()

  for job in "${runnable[@]}"; do
    cmd="${JOB_CMD[$job]}"
    log_file="${JOB_LOG[$job]}"
    echo "[start] $job -> $log_file"
    run_one "$job" "$cmd" "$log_file" &
    pids+=("$!")
    pid_jobs+=("$job")
  done

  if "$BACKGROUND"; then
    echo ""
    echo "detached: true"
    echo "hint: tail -f $LOG_DIR/*.log"
    disown || true
    return 0
  fi

  total="${#pids[@]}"
  if (( total == 0 )); then
    echo "[warn] no runnable plots (see summary below)" >&2
  fi

  last_done=-1
  while (( total > 0 )); do
    done_count=0
    for job in "${pid_jobs[@]}"; do
      log_file="${JOB_LOG[$job]}"
      if [[ -f "$log_file" ]] && grep -q '^[[]exit[]]' "$log_file" 2>/dev/null; then
        done_count=$((done_count + 1))
      fi
    done
    if [[ "$done_count" -ne "$last_done" ]]; then
      echo "[progress] ${done_count}/${total} done"
      last_done="$done_count"
    fi
    if (( done_count >= total )); then
      break
    fi
    sleep 2
  done

  for idx in "${!pids[@]}"; do
    pid="${pids[$idx]}"
    job="${pid_jobs[$idx]}"
    if wait "$pid"; then
      EXIT_STATUS["$job"]=0
    else
      EXIT_STATUS["$job"]=$?
    fi
  done

  failures=0
  skips=0
  echo ""
  echo "=========================================="
  echo "Plot Summary"
  echo "log_name: $LOG_NAME"
  echo "format: $FORMAT"
  echo "logs: $LOG_DIR"
  echo "=========================================="
  for job in "${JOB_ORDER[@]}"; do
    if [[ -n "${SKIP_REASON[$job]:-}" ]]; then
      echo "[SKIP] $job: ${SKIP_REASON[$job]}"
      skips=$((skips + 1))
      continue
    fi
    status="${EXIT_STATUS[$job]:-}"
    if [[ -z "$status" ]]; then
      echo "[FAIL] $job: not run (internal)"
      failures=$((failures + 1))
      continue
    fi
    if (( status != 0 )); then
      echo "[FAIL] $job: exit=$status (log: ${JOB_LOG[$job]})"
      failures=$((failures + 1))
      continue
    fi
    missing="$(check_outputs "$job" "$start_ts" || true)"
    if [[ -n "$missing" ]]; then
      echo "[FAIL] $job: missing outputs: $missing"
      failures=$((failures + 1))
      continue
    fi
    echo "[OK]   $job"
  done

  if (( failures != 0 )); then
    echo "RESULT: FAIL ($failures)"
    return 1
  fi
  if (( skips != 0 )); then
    echo "RESULT: OK (skipped=$skips)"
    return 0
  fi
  echo "RESULT: OK"
  return 0
}

run_session() {
  mapfile -t runnable < <(select_runnable_jobs)

  local session="$SESSION_NAME"
  if [[ -z "$session" ]]; then
    session="$RUN_ID"
  fi

  if tmux has-session -t "$session" >/dev/null 2>&1; then
    if "$KILL_EXISTING"; then
      "$DRY_RUN" || tmux kill-session -t "$session"
    else
      echo "error: session already exists: $session (use --kill-existing)" >&2
      return 1
    fi
  fi

  echo "run_id: $RUN_ID"
  echo "logs: $LOG_DIR"

  if "$DRY_RUN"; then
    echo "[dry-run] create session: $session"
    for job in "${runnable[@]}"; do
      echo "[dry-run] window: $job cmd: ${JOB_CMD[$job]}"
    done
    return 0
  fi

  tmux new-session -d -s "$session" -c "$BASE_DIR" -n "shell" "bash"
  tmux set-option -t "$session" -g remain-on-exit on

  if "$MONITOR"; then
    monitor_cmd=$(
      cat <<EOF
cd "$BASE_DIR"
shopt -s nullglob
while true; do
  clear
  echo "session: $session"
  echo "log_name: $LOG_NAME"
  echo "logs: $LOG_DIR"
  echo "time: \$(date)"
  echo ""
  for f in "$LOG_DIR"/*.log; do
    name=\$(basename "\$f")
    last=\$(tail -n 1 "\$f" 2>/dev/null || true)
    printf "%-22s %s\\n" "\$name" "\$last"
  done
  sleep 2
done
EOF
    )
    tmux new-window -t "$session" -n "monitor" -c "$BASE_DIR" "bash -lc $(printf '%q' "$monitor_cmd")"
  fi

  for job in "${runnable[@]}"; do
    log_file="${JOB_LOG[$job]}"
    cmd="${JOB_CMD[$job]}"
    window_cmd=$(
      cat <<EOF
cd "$BASE_DIR"
set -o pipefail
export PYTHONUNBUFFERED=1
{
  echo "[cwd] \$(pwd)"
  echo "[job] $job"
  echo "[cmd] $cmd"
  $cmd
} |& tee "$log_file"
status=\${PIPESTATUS[0]}
echo "[exit] \$status" |& tee -a "$log_file"
if "$AUTO_CLOSE" && [[ "\$status" -eq 0 ]]; then
  tmux kill-window -t "$session:$job" >/dev/null 2>&1 || true
fi
exit \$status
EOF
    )
    tmux new-window -t "$session" -n "$job" -c "$BASE_DIR" "bash -lc $(printf '%q' "$window_cmd")"
  done

  echo "session: $session"
  echo "attach: tmux attach -t $session"
  if "$ATTACH"; then
    tmux attach -t "$session"
  fi
}

if [[ "$BACKEND" == "session" ]]; then
  run_session
else
  run_local
fi
