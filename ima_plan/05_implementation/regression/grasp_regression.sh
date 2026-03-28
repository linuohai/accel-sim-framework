#!/usr/bin/env bash
# GRASP Prefetcher Regression Test
# Runs baseline + GRASP simulations on IMA workloads, compares IPC against golden baseline.
# Location: ima_plan/05_implementation/regression/
set -euo pipefail

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
GOLDEN_FILE="$SCRIPT_DIR/golden_ipc.json"
TRACEL1="$BASE_DIR/traceL1"
LOG_DIR="$BASE_DIR/result/log"
LOG_PREFIX="regress"

# ─── Defaults ─────────────────────────────────────────────────────────────────
MODE="check"
THRESHOLD=2.0
MAX_CTA=0
REBUILD=false
VERBOSE=false
QUICK=true

# ─── Workloads (order matters for deterministic output) ───────────────────────
WORKLOAD_ORDER=("bfs" "sssp" "spmv" "bc")
declare -A TRACE_KEYS=(
    ["bfs"]="bfs_ima_small"
    ["sssp"]="sssp_ima_small"
    ["spmv"]="spmv_ima_med"
    ["bc"]="bc_ima_small"
)

# ─── Usage ────────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $(basename "$0") [record|check] [OPTIONS]

Modes:
  record    Run all workloads and save IPC to golden_ipc.json
  check     Run all workloads and compare against golden (default)

Options:
  --quick, -q                Quick mode: only run BFS (~34 min, default)
  --full                     Full mode: run all 4 workloads in parallel (~44 min)
  --threshold <pct>          Regression threshold (default: $THRESHOLD%)
  --max-completed-cta <N>    Limit CTA count, 0=full (default: $MAX_CTA)
  --rebuild                  Rebuild simulator before running
  --verbose, -v              Show traceL1 output
  -h, --help                 Show this help
EOF
    exit 0
}

# ─── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        record|check) MODE="$1"; shift ;;
        --threshold)  THRESHOLD="$2"; shift 2 ;;
        --max-completed-cta) MAX_CTA="$2"; shift 2 ;;
        --quick|-q)   QUICK=true; shift ;;
        --full)       QUICK=false; shift ;;
        --rebuild)    REBUILD=true; shift ;;
        --verbose|-v) VERBOSE=true; shift ;;
        -h|--help)    usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ─── Helpers ──────────────────────────────────────────────────────────────────
extract_final_ipc() {
    local log_file="$1"
    grep 'gpu_tot_ipc' "$log_file" | tail -1 | awk -F'=' '{print $2}' | tr -d ' '
}

compute_delta_pct() {
    local actual="$1" expected="$2"
    awk -v a="$actual" -v e="$expected" 'BEGIN { printf "%.2f", (a - e) / e * 100 }'
}

# Returns 0 if NOT regressed, 1 if regressed
is_regressed() {
    local actual="$1" expected="$2" thresh="$3"
    awk -v a="$actual" -v e="$expected" -v t="$thresh" \
        'BEGIN { delta = (e - a) / e * 100; exit (delta > t) ? 1 : 0 }'
}

run_sim() {
    local trace_key="$1" log_name="$2" use_grasp="$3"

    local args=("--no-stall-reason-pc-stats")
    if [[ "$MAX_CTA" -gt 0 ]]; then
        args+=("--max-completed-cta" "$MAX_CTA")
    fi
    if [[ "$use_grasp" == "true" ]]; then
        args+=("--grasp")
    fi
    args+=("$trace_key" "$log_name")

    if [[ "$VERBOSE" == "true" ]]; then
        "$TRACEL1" "${args[@]}"
    else
        "$TRACEL1" "${args[@]}" > /dev/null 2>&1
    fi
}

build_simulator() {
    echo "[build] Rebuilding simulator..."
    (
        cd "$BASE_DIR"
        source ./gpu-simulator/setup_environment.sh
        make -j -C ./gpu-simulator/
    )
    echo "[build] Done."
}

# ─── Pre-checks ──────────────────────────────────────────────────────────────
if [[ ! -x "$TRACEL1" ]]; then
    echo "ERROR: traceL1 not found at $TRACEL1"
    exit 2
fi

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required but not found"
    exit 2
fi

if [[ "$REBUILD" == "true" ]]; then
    build_simulator
fi

# ─── Record Mode ──────────────────────────────────────────────────────────────
record_mode() {
    local git_hash
    git_hash=$(cd "$BASE_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local timestamp
    timestamp=$(date +%Y-%m-%d)

    echo "============================================================"
    echo "GRASP Regression — RECORD mode"
    echo "CTA limit: $([ "$MAX_CTA" -eq 0 ] && echo 'full' || echo "$MAX_CTA")"
    echo "============================================================"

    # Build JSON incrementally
    local json_tmp
    json_tmp=$(mktemp)
    trap "rm -f '$json_tmp'" RETURN

    echo '{}' | jq \
        --arg ts "$timestamp" \
        --arg git "$git_hash" \
        --argjson cta "$MAX_CTA" \
        '.metadata = {recorded_at: $ts, git_commit: $git, max_completed_cta: $cta}' \
        > "$json_tmp"

    for name in "${WORKLOAD_ORDER[@]}"; do
        local trace_key="${TRACE_KEYS[$name]}"
        local log_base="${LOG_PREFIX}_${name}_baseline"
        local log_grasp="${LOG_PREFIX}_${name}_grasp"

        printf "[%-4s] Running baseline (%s)... " "$name" "$trace_key"
        if ! run_sim "$trace_key" "$log_base" "false"; then
            echo "FAILED"
            continue
        fi
        local b_ipc
        b_ipc=$(extract_final_ipc "$LOG_DIR/${log_base}.log")
        echo "IPC=$b_ipc"

        printf "[%-4s] Running GRASP    (%s)... " "$name" "$trace_key"
        if ! run_sim "$trace_key" "$log_grasp" "true"; then
            echo "FAILED"
            continue
        fi
        local g_ipc
        g_ipc=$(extract_final_ipc "$LOG_DIR/${log_grasp}.log")
        local delta
        delta=$(compute_delta_pct "$g_ipc" "$b_ipc")
        echo "IPC=$g_ipc (${delta}%)"

        jq --arg name "$name" \
           --arg tk "$trace_key" \
           --argjson bipc "$b_ipc" \
           --argjson gipc "$g_ipc" \
           '.workloads[$name] = {trace_key: $tk, baseline_ipc: $bipc, grasp_ipc: $gipc}' \
           "$json_tmp" > "${json_tmp}.new" && mv "${json_tmp}.new" "$json_tmp"
    done

    cp "$json_tmp" "$GOLDEN_FILE"
    echo ""
    echo "Golden IPC saved to: $GOLDEN_FILE"
    jq . "$GOLDEN_FILE"
}

# ─── Check Mode ──────────────────────────────────────────────────────────────
check_mode() {
    if [[ ! -f "$GOLDEN_FILE" ]]; then
        echo "ERROR: No golden baseline found at $GOLDEN_FILE"
        echo "Run: $(basename "$0") record"
        exit 2
    fi

    # Quick mode: only run BFS
    local check_workloads=("${WORKLOAD_ORDER[@]}")
    if [[ "$QUICK" == "true" ]]; then
        check_workloads=("bfs")
    fi

    # Read golden metadata
    local golden_date golden_commit golden_cta
    golden_date=$(jq -r '.metadata.recorded_at' "$GOLDEN_FILE")
    golden_commit=$(jq -r '.metadata.git_commit' "$GOLDEN_FILE")
    golden_cta=$(jq -r '.metadata.max_completed_cta' "$GOLDEN_FILE")

    # Warn on CTA mismatch
    if [[ "$golden_cta" != "$MAX_CTA" ]]; then
        echo "WARNING: Golden recorded with max_cta=$golden_cta, current=$MAX_CTA — IPC may differ"
    fi

    echo "============================================================"
    echo "GRASP Regression Test"
    echo "Mode: $([ "$QUICK" == "true" ] && echo 'QUICK (bfs only)' || echo "FULL (${#check_workloads[@]} workloads, parallel)")"
    echo "Threshold: ${THRESHOLD}% | CTA: $([ "$MAX_CTA" -eq 0 ] && echo 'full' || echo "$MAX_CTA")"
    echo "Golden: $golden_date (commit $golden_commit)"
    echo "============================================================"

    # ── Phase 1: Launch all GRASP simulations in parallel ──
    declare -A SIM_PIDS
    declare -A SIM_STATUS
    for name in "${check_workloads[@]}"; do
        local trace_key="${TRACE_KEYS[$name]}"
        local log_grasp="${LOG_PREFIX}_${name}_grasp"
        echo "[launch] $name ($trace_key) ..."
        run_sim "$trace_key" "$log_grasp" "true" &
        SIM_PIDS[$name]=$!
    done
    echo ""
    echo "Waiting for ${#check_workloads[@]} simulation(s) to complete..."

    # ── Phase 2: Wait for all to finish ──
    for name in "${check_workloads[@]}"; do
        if wait "${SIM_PIDS[$name]}" 2>/dev/null; then
            SIM_STATUS[$name]="ok"
        else
            SIM_STATUS[$name]="fail"
        fi
    done

    # ── Phase 3: Collect results and print table ──
    echo ""
    printf "%-8s | %12s | %12s | %12s | %8s | %s\n" \
        "Workload" "Golden Base" "GRASP IPC" "Expected" "Delta%" "Status"
    printf "%-8s-|-%12s-|-%12s-|-%12s-|-%8s-|-%s\n" \
        "--------" "------------" "------------" "------------" "--------" "------"

    local total=0 passed=0 failed=0 errors=0

    for name in "${check_workloads[@]}"; do
        local log_grasp="${LOG_PREFIX}_${name}_grasp"
        local display_name="$name"
        [[ "$name" == "spmv" ]] && display_name="spmv*"

        total=$((total + 1))

        # Read golden values (baseline from golden, no re-run)
        local golden_baseline expected_grasp
        golden_baseline=$(jq -r ".workloads.${name}.baseline_ipc" "$GOLDEN_FILE")
        expected_grasp=$(jq -r ".workloads.${name}.grasp_ipc" "$GOLDEN_FILE")

        if [[ "$expected_grasp" == "null" ]]; then
            printf "%-8s | %12s | %12s | %12s | %8s | %s\n" \
                "$display_name" "-" "-" "-" "-" "SKIP (no golden)"
            continue
        fi

        # Check simulation result
        if [[ "${SIM_STATUS[$name]}" != "ok" ]]; then
            printf "%-8s | %12.4f | %12s | %12.4f | %8s | %s\n" \
                "$display_name" "$golden_baseline" "ERROR" "$expected_grasp" "-" "ERROR"
            errors=$((errors + 1))
            continue
        fi

        local actual_grasp
        actual_grasp=$(extract_final_ipc "$LOG_DIR/${log_grasp}.log")
        if [[ -z "$actual_grasp" ]]; then
            printf "%-8s | %12.4f | %12s | %12.4f | %8s | %s\n" \
                "$display_name" "$golden_baseline" "NO IPC" "$expected_grasp" "-" "ERROR"
            errors=$((errors + 1))
            continue
        fi

        # Compare GRASP IPC against golden
        local delta status
        delta=$(compute_delta_pct "$actual_grasp" "$expected_grasp")

        if is_regressed "$actual_grasp" "$expected_grasp" "$THRESHOLD"; then
            status="PASS"
            passed=$((passed + 1))
        else
            status="FAIL"
            failed=$((failed + 1))
        fi

        printf "%-8s | %12.4f | %12.4f | %12.4f | %+7.2f%% | %s\n" \
            "$display_name" "$golden_baseline" "$actual_grasp" "$expected_grasp" "$delta" "$status"
    done

    echo "============================================================"
    echo "* Baseline IPC from golden (not re-run). Use 'record' to update."
    [[ " ${check_workloads[*]} " == *" spmv "* ]] && echo "* spmv uses spmv_ima_med (spmv_ima_small not available)"
    echo ""

    if [[ $errors -gt 0 ]]; then
        echo "Overall: $passed PASS, $failed FAIL, $errors ERROR (out of $total)"
        exit 2
    elif [[ $failed -gt 0 ]]; then
        echo "Overall: FAIL ($passed/$total passed, $failed regression(s))"
        exit 1
    else
        echo "Overall: PASS ($passed/$total)"
        exit 0
    fi
}

# ─── Main ─────────────────────────────────────────────────────────────────────
case "$MODE" in
    record) record_mode ;;
    check)  check_mode ;;
esac
