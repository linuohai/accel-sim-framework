#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
EXTRA_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACT_SCRIPT="$EXTRA_DIR/extract_warp_tables.py"
SUMMARY_SCRIPT="$EXTRA_DIR/summarize_prefetch_design.py"
PLOT_SCRIPT="$EXTRA_DIR/plot_prefetch_design.py"
OUT_ROOT="$EXTRA_DIR/small_1sm_cta5"
BC_WORK_DIR="$OUT_ROOT/_bc_work"
SCHEDULER_LABEL="lrr"
RUN_TRACE=true
RUN_ANALYSIS=true

usage() {
    cat <<EOF
Usage: $0 [options]
  --skip-trace            Reuse existing fresh trace files
  --skip-analysis         Only regenerate traces
  --out-root DIR          Output root (default: $OUT_ROOT)
  --scheduler-label LAB   Output scheduler label (default: $SCHEDULER_LABEL)
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-trace) RUN_TRACE=false; shift ;;
        --skip-analysis) RUN_ANALYSIS=false; shift ;;
        --out-root) OUT_ROOT="$2"; shift 2 ;;
        --scheduler-label) SCHEDULER_LABEL="$2"; shift 2 ;;
        -h|--help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

mkdir -p "$OUT_ROOT"

declare -A STEM_BY_TRACE=(
    ["bfs_ima_small"]="bfs_ima_small_1sm_cta5_fresh"
    ["sssp_ima_small"]="sssp_ima_small_1sm_cta5_fresh"
    ["spmv_ima_small"]="spmv_ima_small_1sm_cta5_fresh"
    ["cc_ima_small"]="cc_ima_small_1sm_cta5_fresh"
    ["bc_ima_small"]="bc_ima_small_1sm_cta5_fresh"
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

trace_once() {
    local trace_key="$1"
    local stem="$2"
    echo "============================================"
    echo "Trace: $trace_key -> $stem"
    echo "============================================"
    "$BASE_DIR/traceL1" \
        -c SM80_A100_1SM \
        --max-completed-cta 5 \
        --issue-trace \
        --l2-trace-print-bw \
        --l2-trace-print-compute \
        --no-hbm-trace \
        --no-icnt-bw-trace \
        --no-l2-bw-trace \
        "$trace_key" \
        "$stem"
}

fresh_trace_paths() {
    local stem="$1"
    local l1 l2 issue
    l1="$(resolve_file "$BASE_DIR/result/L1cache_trace" "$stem" "_l1.csv")" || return 1
    l2="$(resolve_file "$BASE_DIR/result/L2cache_trace" "$stem" "_l2.csv")" || return 1
    issue="$(resolve_file "$BASE_DIR/result/issue_trace" "$stem" "_issue.csv")" || return 1
    printf '%s\n%s\n%s\n' "$l1" "$l2" "$issue"
}

check_fill() {
    local l1_trace="$1"
    python3 - "$l1_trace" <<'PY'
import gzip
import sys
from pathlib import Path

path = Path(sys.argv[1])
opener = gzip.open if path.suffix == ".gz" else open
with opener(path, "rt", newline="") as handle:
    for line in handle:
        if ",FILL," in line:
            print("fill_observed=1")
            raise SystemExit(0)
print("fill_observed=0")
PY
}

analyze_one() {
    local l1_trace="$1"
    local l2_trace="$2"
    local issue_trace="$3"
    local workload="$4"
    local out_dir="$5"
    mkdir -p "$out_dir"
    rm -f \
        "$out_dir/warp_load_events_${SCHEDULER_LABEL}.csv" \
        "$out_dir/warp_load_sectors_${SCHEDULER_LABEL}.csv" \
        "$out_dir/ima_window_summary_${SCHEDULER_LABEL}.csv" \
        "$out_dir/ima_l2_window_summary_${SCHEDULER_LABEL}.csv" \
        "$out_dir/ima_window_role_breakdown_${SCHEDULER_LABEL}.csv" \
        "$out_dir/ima_chain_latency_${SCHEDULER_LABEL}.csv" \
        "$out_dir/ima_chain_summary_${SCHEDULER_LABEL}.csv"
    python3 "$EXTRACT_SCRIPT" \
        --l1-trace "$l1_trace" \
        --l2-trace "$l2_trace" \
        --issue-trace "$issue_trace" \
        --workload "$workload" \
        --scheduler-label "$SCHEDULER_LABEL" \
        --out-dir "$out_dir"
}

for trace_key in bfs_ima_small sssp_ima_small spmv_ima_small cc_ima_small bc_ima_small; do
    stem="${STEM_BY_TRACE[$trace_key]}"

    if [[ "$RUN_TRACE" == true ]]; then
        if fresh_paths="$(fresh_trace_paths "$stem" 2>/dev/null)"; then
            echo "Reuse existing fresh trace for $trace_key ($stem)"
        else
            if ! trace_once "$trace_key" "$stem"; then
                echo "[warn] traceL1 failed for $trace_key ($stem); checking whether fresh traces were still emitted"
            fi
        fi
    fi

    if [[ "$RUN_ANALYSIS" != true ]]; then
        continue
    fi

    case "$trace_key" in
        bc_ima_small)
            bc_forward_issue="$BC_WORK_DIR/bc_forward_snapshot_issue.csv"
            bc_forward_l1="$BC_WORK_DIR/bc_forward_snapshot_l1.csv"
            bc_forward_l2="$BC_WORK_DIR/bc_forward_snapshot_l2.csv"
            bc_reverse_issue="$BC_WORK_DIR/bc_reverse_snapshot_issue.csv"
            bc_reverse_l1="$BC_WORK_DIR/bc_reverse_snapshot_l1.csv"
            bc_reverse_l2="$BC_WORK_DIR/bc_reverse_snapshot_l2.csv"
            if [[ -f "$bc_forward_issue" && -f "$bc_forward_l1" && -f "$bc_forward_l2" && -f "$bc_reverse_issue" && -f "$bc_reverse_l1" && -f "$bc_reverse_l2" ]]; then
                echo "bc_ima_small_forward(snapshot): $(check_fill "$bc_forward_l1")"
                echo "bc_ima_small_reverse(snapshot): $(check_fill "$bc_reverse_l1")"
                analyze_one "$bc_forward_l1" "$bc_forward_l2" "$bc_forward_issue" "bc_ima_small_forward" "$OUT_ROOT/bc_ima_small_forward"
                analyze_one "$bc_reverse_l1" "$bc_reverse_l2" "$bc_reverse_issue" "bc_ima_small_reverse" "$OUT_ROOT/bc_ima_small_reverse"
            else
                l1_trace="$(resolve_file "$BASE_DIR/result/L1cache_trace" "$stem" "_l1.csv")" || {
                    echo "ERROR: missing L1 trace for $trace_key ($stem)"
                    exit 1
                }
                l2_trace="$(resolve_file "$BASE_DIR/result/L2cache_trace" "$stem" "_l2.csv")" || {
                    echo "ERROR: missing L2 trace for $trace_key ($stem)"
                    exit 1
                }
                issue_trace="$(resolve_file "$BASE_DIR/result/issue_trace" "$stem" "_issue.csv")" || {
                    echo "ERROR: missing issue trace for $trace_key ($stem)"
                    exit 1
                }
                echo "$trace_key: $(check_fill "$l1_trace")"
                analyze_one "$l1_trace" "$l2_trace" "$issue_trace" "bc_ima_small_forward" "$OUT_ROOT/bc_ima_small_forward"
                analyze_one "$l1_trace" "$l2_trace" "$issue_trace" "bc_ima_small_reverse" "$OUT_ROOT/bc_ima_small_reverse"
            fi
            ;;
        *)
            l1_trace="$(resolve_file "$BASE_DIR/result/L1cache_trace" "$stem" "_l1.csv")" || {
                echo "ERROR: missing L1 trace for $trace_key ($stem)"
                exit 1
            }
            l2_trace="$(resolve_file "$BASE_DIR/result/L2cache_trace" "$stem" "_l2.csv")" || {
                echo "ERROR: missing L2 trace for $trace_key ($stem)"
                exit 1
            }
            issue_trace="$(resolve_file "$BASE_DIR/result/issue_trace" "$stem" "_issue.csv")" || {
                echo "ERROR: missing issue trace for $trace_key ($stem)"
                exit 1
            }
            echo "$trace_key: $(check_fill "$l1_trace")"
            analyze_one "$l1_trace" "$l2_trace" "$issue_trace" "$trace_key" "$OUT_ROOT/$trace_key"
            ;;
    esac
done

if [[ "$RUN_ANALYSIS" == true ]]; then
    python3 "$SUMMARY_SCRIPT" \
        --root "$OUT_ROOT" \
        --scheduler-label "$SCHEDULER_LABEL"
    python3 "$PLOT_SCRIPT" \
        --root "$OUT_ROOT" \
        --scheduler-label "$SCHEDULER_LABEL" \
        --format svg
fi

echo "Done. Results under: $OUT_ROOT"
