#!/usr/bin/env bash
# run_tiny_case.sh — Tiny BFS IMA run + issue-trace-driven visualization.
#
# Default behavior:
#   * generate SVG outputs
#   * compare both lrr and gto
#   * force issue trace on, because the plots are issue-trace driven
#
# Examples:
#   ./run_tiny_case.sh
#   ./run_tiny_case.sh --scheduler lrr --skip-sim
#   ./run_tiny_case.sh --scheduler both --warp 0,38,39,47 --cycle-range 600000-720000

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
TINY_DIR="$(cd "$(dirname "$0")" && pwd)"

MAX_CTA=5
TRACE_KEY="bfs_ima_small"
LOG_STEM=""
SKIP_SIM=0
FMT="svg"
WORKLOAD="bfs_ima_high"
WARP_LIST=""
CYCLE_RANGE=""
SCHEDULER_MODE="both"  # lrr|gto|both
TOP_WARPS=4
MAX_CHAINS=40
LEGACY_PATTERN=0

PC_CLASS="$BASE_DIR/ima_plan/01_ima_characterization/l1_miss_breakdown/data/pc_classification.csv"
OUT_DIR="$TINY_DIR/figures"

usage() {
    cat <<EOF
Usage: $0 [options]
  --cta N             Max completed CTAs (default: $MAX_CTA)
  --trace KEY         Trace key (default: $TRACE_KEY)
  --log STEM          Base log stem without scheduler suffix (default: auto-generated)
  --scheduler MODE    lrr | gto | both (default: $SCHEDULER_MODE)
  --skip-sim          Skip simulation, only re-plot from existing traces
  --format FMT        Output format: svg | png | pdf (default: $FMT)
  --out-dir DIR       Figure output directory (default: $OUT_DIR)
  --pc-class PATH     pc_classification.csv override (default: $PC_CLASS)
  --workload KEY      Workload key in pc_classification.csv (default: $WORKLOAD)
  --warp W1,W2,...    Warp IDs for chain plots
  --cycle-range S-E   Optional cycle range passed to plot script
  --top-warps N       Auto-selected chain-detail warps when --warp is omitted
  --max-chains N      Max recovered chains shown per warp detail plot
  --legacy-pattern    Also generate legacy absolute/aligned/chain/scatter plots
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cta)         MAX_CTA="$2"; shift 2 ;;
        --trace)       TRACE_KEY="$2"; shift 2 ;;
        --log)         LOG_STEM="$2"; shift 2 ;;
        --scheduler)   SCHEDULER_MODE="$2"; shift 2 ;;
        --skip-sim)    SKIP_SIM=1; shift ;;
        --format)      FMT="$2"; shift 2 ;;
        --out-dir)     OUT_DIR="$2"; shift 2 ;;
        --pc-class)    PC_CLASS="$2"; shift 2 ;;
        --workload)    WORKLOAD="$2"; shift 2 ;;
        --warp)        WARP_LIST="$2"; shift 2 ;;
        --cycle-range) CYCLE_RANGE="$2"; shift 2 ;;
        --top-warps)   TOP_WARPS="$2"; shift 2 ;;
        --max-chains)  MAX_CHAINS="$2"; shift 2 ;;
        --legacy-pattern) LEGACY_PATTERN=1; shift ;;
        -h|--help)     usage ;;
        *)             echo "Unknown option: $1"; usage ;;
    esac
done

if [[ "$SCHEDULER_MODE" != "lrr" && "$SCHEDULER_MODE" != "gto" && "$SCHEDULER_MODE" != "both" ]]; then
    echo "ERROR: --scheduler must be one of lrr|gto|both (got: $SCHEDULER_MODE)"
    exit 1
fi

if [[ -z "$LOG_STEM" ]]; then
    if [[ "$TRACE_KEY" == "bfs_ima_small" ]]; then
        LOG_STEM="bfs_1sm_cta${MAX_CTA}"
    else
        LOG_STEM="${TRACE_KEY}_1sm_cta${MAX_CTA}"
    fi
fi

mkdir -p "$OUT_DIR"

validate_environment() {
    if [[ ! -f "$PC_CLASS" ]]; then
        echo "ERROR: pc classification file not found: $PC_CLASS"
        exit 1
    fi
    if [[ ! -f "$BASE_DIR/gpu-simulator/setup_environment.sh" ]]; then
        echo "ERROR: missing simulator environment script under $BASE_DIR/gpu-simulator/"
        echo "Run this inside the fa container with /workspace/prefetch mounted as the repo root."
        exit 1
    fi
    if [[ $SKIP_SIM -eq 0 && ! -e "$BASE_DIR/traceL1" ]]; then
        echo "ERROR: missing traceL1 launcher under $BASE_DIR"
        echo "Run this inside the fa container after the simulator environment is prepared."
        exit 1
    fi
}

resolve_log_name() {
    local scheduler="$1"
    local base="${LOG_STEM%_gto}"
    if [[ "$scheduler" == "gto" ]]; then
        echo "${base}_gto"
    else
        echo "$base"
    fi
}

resolve_l1_trace() {
    local stem="$1"
    local plain="$BASE_DIR/result/L1cache_trace/${stem}_l1.csv"
    local gz="${plain}.gz"
    if [[ -f "$plain" ]]; then
        echo "$plain"
        return 0
    fi
    if [[ -f "$gz" ]]; then
        echo "$gz"
        return 0
    fi
    return 1
}

resolve_issue_trace() {
    local stem="$1"
    local plain="$BASE_DIR/result/issue_trace/${stem}_issue.csv"
    local gz="${plain}.gz"
    if [[ -f "$plain" ]]; then
        echo "$plain"
        return 0
    fi
    if [[ -f "$gz" ]]; then
        echo "$gz"
        return 0
    fi
    return 1
}

resolve_log_path() {
    local stem="$1"
    local plain="$BASE_DIR/result/log/${stem}.log"
    if [[ -f "$plain" ]]; then
        echo "$plain"
        return 0
    fi
    return 1
}

run_simulation() {
    local scheduler="$1"
    local log_name="$2"
    local rc=0
    local cmd=(
        ./traceL1
        -c SM80_A100_1SM
        --max-completed-cta "$MAX_CTA"
        --issue-trace
    )
    if [[ "$scheduler" == "gto" ]]; then
        cmd+=(-gto)
    fi
    cmd+=("$TRACE_KEY" "$log_name")

    echo "  Running ${scheduler} simulation: ${cmd[*]}"
    (cd "$BASE_DIR" && source ./gpu-simulator/setup_environment.sh 2>/dev/null && "${cmd[@]}") || rc=$?
    if [[ $rc -ne 0 ]]; then
        if resolve_l1_trace "$log_name" >/dev/null 2>&1 && resolve_issue_trace "$log_name" >/dev/null 2>&1; then
            echo "  WARN: traceL1 returned rc=$rc for $log_name, but required traces exist; continuing."
            return 0
        fi
        echo "ERROR: simulation failed for scheduler=$scheduler log_name=$log_name (rc=$rc)"
        return "$rc"
    fi
}

cleanup_scheduler_outputs() {
    local scheduler="$1"
    find "$OUT_DIR" -maxdepth 1 -type f \
        \( -name "ima_windowed_${scheduler}.*" \
        -o -name "ima_pattern_${scheduler}_*" \
        -o -name "ima_scatter_*_${scheduler}.*" \
        -o -name "ima_chain_${scheduler}_w*" \) \
        -delete
    rm -f \
        "$TINY_DIR/ima_window_summary_${scheduler}.csv" \
        "$TINY_DIR/ima_window_role_breakdown_${scheduler}.csv" \
        "$TINY_DIR/dcache_window_timeseries_${scheduler}.csv" \
        "$TINY_DIR/ima_chain_detail_${scheduler}.csv" \
        "$TINY_DIR/ima_warp_stats_${scheduler}.csv" \
        "$TINY_DIR/warp_load_events_${scheduler}.csv" \
        "$TINY_DIR/warp_load_sectors_${scheduler}.csv"
}

plot_scheduler() {
    local scheduler="$1"
    local log_name="$2"
    local l1_trace issue_trace log_path

    if ! l1_trace="$(resolve_l1_trace "$log_name")"; then
        echo "ERROR: missing L1 trace for $log_name"
        return 1
    fi
    if ! issue_trace="$(resolve_issue_trace "$log_name")"; then
        echo "ERROR: missing issue trace for $log_name"
        echo "The tiny-case plots now require issue trace. Re-run without --skip-sim."
        return 1
    fi
    if ! log_path="$(resolve_log_path "$log_name")"; then
        echo "ERROR: missing log file for $log_name"
        return 1
    fi

    cleanup_scheduler_outputs "$scheduler"

    local plot_cmd=(
        python3 "$TINY_DIR/plot_ima_timeline.py"
        --l1-trace "$l1_trace"
        --issue-trace "$issue_trace"
        --log "$log_path"
        --pc-class "$PC_CLASS"
        --workload "$WORKLOAD"
        --scheduler-label "$scheduler"
        --out-dir "$OUT_DIR"
        --format "$FMT"
        --top-warps "$TOP_WARPS"
        --max-chains "$MAX_CHAINS"
    )
    [[ -n "$WARP_LIST" ]] && plot_cmd+=(--warp "$WARP_LIST")
    [[ -n "$CYCLE_RANGE" ]] && plot_cmd+=(--cycle-range "$CYCLE_RANGE")
    [[ $LEGACY_PATTERN -eq 1 ]] && plot_cmd+=(--legacy-pattern)

    echo "  Plotting ${scheduler} from:"
    echo "    L1:    $l1_trace"
    echo "    Issue: $issue_trace"
    echo "    Log:   $log_path"
    "${plot_cmd[@]}"
}

SCHEDULERS=()
case "$SCHEDULER_MODE" in
    lrr)  SCHEDULERS=(lrr) ;;
    gto)  SCHEDULERS=(gto) ;;
    both) SCHEDULERS=(lrr gto) ;;
esac

validate_environment

echo "============================================"
echo "IMA Tiny Case"
echo "  Trace key:      $TRACE_KEY"
echo "  Max CTA:        $MAX_CTA"
echo "  Scheduler(s):   ${SCHEDULERS[*]}"
echo "  Workload key:   $WORKLOAD"
echo "  PC class file:  $PC_CLASS"
echo "  Issue trace:    forced on"
echo "  Output format:  $FMT"
echo "  Figure dir:     $OUT_DIR"
echo "  Legacy plots:   $LEGACY_PATTERN"
echo "============================================"

if [[ $SKIP_SIM -eq 0 ]]; then
    echo ""
    echo "[1/2] Running simulation(s)..."
    for scheduler in "${SCHEDULERS[@]}"; do
        log_name="$(resolve_log_name "$scheduler")"
        run_simulation "$scheduler" "$log_name"
    done
else
    echo ""
    echo "[1/2] Skipping simulation (--skip-sim)"
fi

echo ""
echo "[2/2] Plotting..."
for scheduler in "${SCHEDULERS[@]}"; do
    log_name="$(resolve_log_name "$scheduler")"
    plot_scheduler "$scheduler" "$log_name"
done

echo ""
echo "============================================"
echo "Done! Generated outputs:"
echo "  Figures: $OUT_DIR/"
echo "  CSVs:    $TINY_DIR/ima_window_summary_<scheduler>.csv"
echo "           $TINY_DIR/ima_window_role_breakdown_<scheduler>.csv"
echo "           $TINY_DIR/dcache_window_timeseries_<scheduler>.csv"
echo "           $TINY_DIR/warp_load_events_<scheduler>.csv"
echo "           $TINY_DIR/warp_load_sectors_<scheduler>.csv"
if [[ $LEGACY_PATTERN -eq 1 ]]; then
    echo "           $TINY_DIR/ima_chain_detail_<scheduler>.csv"
    echo "           $TINY_DIR/ima_warp_stats_<scheduler>.csv"
fi
for scheduler in "${SCHEDULERS[@]}"; do
    log_name="$(resolve_log_name "$scheduler")"
    echo "  ${scheduler} log:   $BASE_DIR/result/log/${log_name}.log"
done
echo "============================================"
