#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
EXTRA_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACT_SCRIPT="$EXTRA_DIR/extract_warp_tables.py"
SUMMARY_SCRIPT="$EXTRA_DIR/summarize_prefetch_design.py"
PC_CLASS="$BASE_DIR/ima_plan/01_ima_characterization/l1_miss_breakdown/data/pc_classification.csv"
OUT_ROOT="$EXTRA_DIR/workloads"
SCHEDULER_LABEL="lrr"
FMT="svg"
WORKLOAD_FILTER=""

usage() {
    cat <<EOF
Usage: $0 [options]
  --scheduler-label LABEL   Output scheduler label (default: $SCHEDULER_LABEL)
        --out-root DIR            Output root (default: $OUT_ROOT)
        --workloads A,B,C         Optional subset of workloads
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scheduler-label) SCHEDULER_LABEL="$2"; shift 2 ;;
        --out-root)        OUT_ROOT="$2"; shift 2 ;;
        --workloads)       WORKLOAD_FILTER="$2"; shift 2 ;;
        -h|--help)         usage ;;
        *)                 echo "Unknown option: $1"; usage ;;
    esac
done

declare -A INPUT_STEM_BY_WORKLOAD=(
    ["bfs_cit_ima"]="bfs_cit_ima"
    ["bfs_web"]="bfs_web"
    ["bfs_flickr"]="bfs_flickr"
    ["bfs_roadnet"]="bfs_roadnet"
    ["bfs_usa"]="bfs_usa"
)

declare -A PC_WORKLOAD_BY_WORKLOAD=(
    ["bfs_cit_ima"]="bfs_ima_high"
    ["bfs_web"]="bfs_ima_high"
    ["bfs_flickr"]="bfs_ima_high"
    ["bfs_roadnet"]="bfs_ima_high"
    ["bfs_usa"]="bfs_ima_high"
)

resolve_file() {
    local dir="$1"
    local stem="$2"
    local suffix="$3"
    local plain="$dir/${stem}${suffix}"
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

mkdir -p "$OUT_ROOT"

workloads=()
if [[ -n "$WORKLOAD_FILTER" ]]; then
    IFS=',' read -r -a workloads <<< "$WORKLOAD_FILTER"
else
    workloads=("bfs_cit_ima" "bfs_web" "bfs_flickr" "bfs_roadnet" "bfs_usa")
fi

for workload in "${workloads[@]}"; do
    stem="${INPUT_STEM_BY_WORKLOAD[$workload]:-}"
    pc_workload="${PC_WORKLOAD_BY_WORKLOAD[$workload]:-}"
    if [[ -z "$stem" ]]; then
        echo "ERROR: unsupported workload: $workload"
        exit 1
    fi

    l1_trace="$(resolve_file "$BASE_DIR/result/L1cache_trace" "${stem}" "_l1.csv")" || {
        echo "ERROR: missing L1 trace for $workload (stem=$stem)"
        exit 1
    }
    issue_trace="$(resolve_file "$BASE_DIR/result/issue_trace" "${stem}" "_issue.csv")" || {
        echo "ERROR: missing issue trace for $workload (stem=$stem)"
        exit 1
    }
    workload_dir="$OUT_ROOT/$workload"
    mkdir -p "$workload_dir"
    rm -f \
        "$workload_dir/ima_window_summary_${SCHEDULER_LABEL}.csv" \
        "$workload_dir/ima_window_role_breakdown_${SCHEDULER_LABEL}.csv" \
        "$workload_dir/warp_load_events_${SCHEDULER_LABEL}.csv" \
        "$workload_dir/warp_load_sectors_${SCHEDULER_LABEL}.csv"

    echo "============================================"
    echo "Workload: $workload"
    echo "  Input stem: $stem"
    echo "  L1:         $l1_trace"
    echo "  Issue:      $issue_trace"
    echo "  Output:     $workload_dir"
    echo "============================================"

    python3 "$EXTRACT_SCRIPT" \
        --l1-trace "$l1_trace" \
        --issue-trace "$issue_trace" \
        --pc-class "$PC_CLASS" \
        --workload "$pc_workload" \
        --scheduler-label "$SCHEDULER_LABEL" \
        --out-dir "$workload_dir"
done

python3 "$SUMMARY_SCRIPT" \
    --root "$OUT_ROOT" \
    --scheduler-label "$SCHEDULER_LABEL"

echo "Done. Results under: $OUT_ROOT"
