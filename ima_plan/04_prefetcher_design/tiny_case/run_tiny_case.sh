#!/usr/bin/env bash
# run_tiny_case.sh -- build, trace, simulate, and analyze the standalone IMA tiny-case benchmark.

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
TINY_DIR="$(cd "$(dirname "$0")" && pwd)"

SUITE_NAME="ima_tiny_case"
TRACE_KEY="ima_tiny_case"
BASE_CONFIG="SM80_A100_1SM_NOSUBCORE"
PREFETCH_CONFIG="SM80_A100_1SM_NOSUBCORE_IMAPF"
PREFETCH_MODE="both"    # baseline|imapf|both
SCHEDULER_MODE="both"   # lrr|gto|both
PLOTS_MODE="gantt"      # gantt|all
DEVICE_NUM=0
SKIP_BUILD=0
SKIP_TRACE=0
SKIP_SIM=0
RUN_NATIVE_CHECK=1
FORMAT="svg"
TOP_WARPS=2

CTAS=1
WARPS_PER_CTA=8
WARMUP_ITERS=256
IMA_ITERS=4096
TAIL_ITERS=256
DATA_LINES=2048
MAPPING_SEED=1
COMPUTE_GAP=8

LOG_STEM="ima_tiny_case"
METADATA_NAME="ima_tiny_case_metadata.json"
BUNDLES_ROOT="$TINY_DIR/trace_bundles"
OUT_DIR=""

BUNDLE_ID=""
BUNDLE_DIR=""
BUNDLE_NATIVE_DIR=""
BUNDLE_METADATA_DIR=""
BUNDLE_SRC_DIR=""
BUNDLE_SASS_DIR=""
BUNDLE_TRACE_DIR=""
BUNDLE_SIM_DIR=""
BUNDLE_ANALYSIS_DIR=""
BUNDLE_FIG_DIR=""

usage() {
    cat <<EOF
Usage: $0 [options]
  --device N              GPU device for run_hw_trace.py (default: $DEVICE_NUM)
  --scheduler MODE        lrr | gto | both (default: $SCHEDULER_MODE)
  --prefetch MODE         baseline | imapf | both (default: $PREFETCH_MODE)
  --plots MODE            gantt | all (default: $PLOTS_MODE)
  --skip-build            Skip benchmark build
  --skip-trace            Skip hardware trace generation
  --skip-sim              Skip trace-driven simulation
  --skip-native-check     Skip the native benchmark sanity run
  --format FMT            svg | png | pdf (default: $FORMAT)
  --top-warps N           Number of chain-detail warps to plot when --plots all (default: $TOP_WARPS)
  --log STEM              Result log stem (default: $LOG_STEM)
  --out-dir DIR           Deprecated in bundle mode; figures always go to bundle analysis/figures
  --ctas N                Benchmark CTA count (default: $CTAS)
  --warps-per-cta N       Benchmark warps per CTA (default: $WARPS_PER_CTA)
  --warmup-iters N        Warmup iterations (default: $WARMUP_ITERS)
  --ima-iters N           IMA region iterations (default: $IMA_ITERS)
  --tail-iters N          Tail iterations (default: $TAIL_ITERS)
  --data-lines N          Data working-set size in cache lines (default: $DATA_LINES)
  --mapping-seed N        Mapping permutation seed (default: $MAPPING_SEED)
  --compute-gap N         Integer ops between IMA chains (default: $COMPUTE_GAP)
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --device)            DEVICE_NUM="$2"; shift 2 ;;
        --scheduler)         SCHEDULER_MODE="$2"; shift 2 ;;
        --prefetch)          PREFETCH_MODE="$2"; shift 2 ;;
        --plots)             PLOTS_MODE="$2"; shift 2 ;;
        --skip-build)        SKIP_BUILD=1; shift ;;
        --skip-trace)        SKIP_TRACE=1; shift ;;
        --skip-sim)          SKIP_SIM=1; shift ;;
        --skip-native-check) RUN_NATIVE_CHECK=0; shift ;;
        --format)            FORMAT="$2"; shift 2 ;;
        --top-warps)         TOP_WARPS="$2"; shift 2 ;;
        --log)               LOG_STEM="$2"; shift 2 ;;
        --out-dir)           OUT_DIR="$2"; shift 2 ;;
        --ctas)              CTAS="$2"; shift 2 ;;
        --warps-per-cta)     WARPS_PER_CTA="$2"; shift 2 ;;
        --warmup-iters)      WARMUP_ITERS="$2"; shift 2 ;;
        --ima-iters)         IMA_ITERS="$2"; shift 2 ;;
        --tail-iters)        TAIL_ITERS="$2"; shift 2 ;;
        --data-lines)        DATA_LINES="$2"; shift 2 ;;
        --mapping-seed)      MAPPING_SEED="$2"; shift 2 ;;
        --compute-gap)       COMPUTE_GAP="$2"; shift 2 ;;
        -h|--help)           usage ;;
        *)                   echo "Unknown option: $1"; usage ;;
    esac
done

if [[ "$SCHEDULER_MODE" != "lrr" && "$SCHEDULER_MODE" != "gto" && "$SCHEDULER_MODE" != "both" ]]; then
    echo "ERROR: --scheduler must be one of lrr|gto|both"
    exit 1
fi

if [[ "$PREFETCH_MODE" != "baseline" && "$PREFETCH_MODE" != "imapf" && "$PREFETCH_MODE" != "both" ]]; then
    echo "ERROR: --prefetch must be one of baseline|imapf|both"
    exit 1
fi

if [[ "$PLOTS_MODE" != "gantt" && "$PLOTS_MODE" != "all" ]]; then
    echo "ERROR: --plots must be one of gantt|all"
    exit 1
fi

load_gpuapps_env() {
    # shellcheck disable=SC1091
    source "$BASE_DIR/gpu-app-collection/src/setup_environment" >/dev/null
}

bundle_id() {
    printf "cta%s_w%s_wu%s_ima%s_tail%s_dl%s_seed%s_gap%s" \
        "$CTAS" \
        "$WARPS_PER_CTA" \
        "$WARMUP_ITERS" \
        "$IMA_ITERS" \
        "$TAIL_ITERS" \
        "$DATA_LINES" \
        "$MAPPING_SEED" \
        "$COMPUTE_GAP"
}

init_bundle_paths() {
    BUNDLE_ID="$(bundle_id)"
    BUNDLE_DIR="$BUNDLES_ROOT/$BUNDLE_ID"
    BUNDLE_NATIVE_DIR="$BUNDLE_DIR/native"
    BUNDLE_METADATA_DIR="$BUNDLE_DIR/metadata"
    BUNDLE_SRC_DIR="$BUNDLE_DIR/src"
    BUNDLE_SASS_DIR="$BUNDLE_DIR/sass"
    BUNDLE_TRACE_DIR="$BUNDLE_DIR/trace"
    BUNDLE_SIM_DIR="$BUNDLE_DIR/sim"
    BUNDLE_ANALYSIS_DIR="$BUNDLE_DIR/analysis"
    BUNDLE_FIG_DIR="$BUNDLE_ANALYSIS_DIR/figures"
    if [[ -n "$OUT_DIR" ]]; then
        echo "WARNING: --out-dir is ignored in bundle mode; using $BUNDLE_FIG_DIR"
    fi
    OUT_DIR="$BUNDLE_FIG_DIR"
}

mkdir_bundle_dirs() {
    mkdir -p \
        "$BUNDLES_ROOT" \
        "$BUNDLE_NATIVE_DIR" \
        "$BUNDLE_METADATA_DIR" \
        "$BUNDLE_SRC_DIR" \
        "$BUNDLE_SASS_DIR" \
        "$BUNDLE_TRACE_DIR" \
        "$BUNDLE_SIM_DIR" \
        "$BUNDLE_ANALYSIS_DIR" \
        "$OUT_DIR"
}

validate_environment() {
    if [[ ! -x "$BASE_DIR/traceL1" ]]; then
        echo "ERROR: missing traceL1 under $BASE_DIR"
        exit 1
    fi
    if [[ ! -f "$BASE_DIR/util/tracer_nvbit/run_hw_trace.py" ]]; then
        echo "ERROR: missing run_hw_trace.py"
        exit 1
    fi
    if [[ ! -f "$BASE_DIR/gpu-simulator/gpgpu-sim/configs/tested-cfgs/$BASE_CONFIG/gpgpusim.config" ]]; then
        echo "ERROR: missing GPGPU-Sim config for $BASE_CONFIG"
        exit 1
    fi
    if [[ ! -f "$BASE_DIR/gpu-simulator/configs/tested-cfgs/$BASE_CONFIG/trace.config" ]]; then
        echo "ERROR: missing trace config for $BASE_CONFIG"
        exit 1
    fi
    if [[ "$PREFETCH_MODE" != "baseline" ]]; then
        if [[ ! -f "$BASE_DIR/gpu-simulator/gpgpu-sim/configs/tested-cfgs/$PREFETCH_CONFIG/gpgpusim.config" ]]; then
            echo "ERROR: missing GPGPU-Sim config for $PREFETCH_CONFIG"
            exit 1
        fi
        if [[ ! -f "$BASE_DIR/gpu-simulator/configs/tested-cfgs/$PREFETCH_CONFIG/trace.config" ]]; then
            echo "ERROR: missing trace config for $PREFETCH_CONFIG"
            exit 1
        fi
    fi
}

native_exec_path() {
    load_gpuapps_env
    echo "$GPUAPPS_ROOT/bin/$CUDA_VERSION/release/ima_tiny_case"
}

trace_run_dir() {
    load_gpuapps_env
    echo "$BASE_DIR/hw_run/traces/device-$DEVICE_NUM/$CUDA_VERSION/ima_tiny_case/NO_ARGS"
}

export_tiny_env() {
    export IMA_TINY_CTAS="$CTAS"
    export IMA_TINY_WARPS_PER_CTA="$WARPS_PER_CTA"
    export IMA_TINY_WARMUP_ITERS="$WARMUP_ITERS"
    export IMA_TINY_IMA_ITERS="$IMA_ITERS"
    export IMA_TINY_TAIL_ITERS="$TAIL_ITERS"
    export IMA_TINY_DATA_LINES="$DATA_LINES"
    export IMA_TINY_MAPPING_SEED="$MAPPING_SEED"
    export IMA_TINY_COMPUTE_GAP="$COMPUTE_GAP"
    export IMA_TINY_METADATA_OUT="./$METADATA_NAME"
}

write_bundle_manifest() {
    local config_path="$BUNDLE_METADATA_DIR/config.json"
    cat >"$config_path" <<EOF
{
  "bundle_id": "$BUNDLE_ID",
  "trace_key": "$TRACE_KEY",
  "device_num": $DEVICE_NUM,
  "plots_mode": "$PLOTS_MODE",
  "prefetch_mode": "$PREFETCH_MODE",
  "scheduler_mode": "$SCHEDULER_MODE",
  "base_config": "$BASE_CONFIG",
  "prefetch_config": "$PREFETCH_CONFIG",
  "params": {
    "ctas": $CTAS,
    "warps_per_cta": $WARPS_PER_CTA,
    "warmup_iters": $WARMUP_ITERS,
    "ima_iters": $IMA_ITERS,
    "tail_iters": $TAIL_ITERS,
    "data_lines": $DATA_LINES,
    "mapping_seed": $MAPPING_SEED,
    "compute_gap": $COMPUTE_GAP
  }
}
EOF
}

capture_source_snapshot() {
    cp "$BASE_DIR/gpu-app-collection/src/cuda/custom-apps/ima_tiny_case/ima_tiny_case.cu" \
        "$BUNDLE_SRC_DIR/ima_tiny_case.cu"
}

capture_sass_snapshot() {
    local trace_dir="$1"
    load_gpuapps_env
    local cuobjdump_bin="${CUDA_INSTALL_PATH}/bin/cuobjdump"
    local nvdisasm_bin="${CUDA_INSTALL_PATH}/bin/nvdisasm"

    shopt -s nullglob
    local cubins=("$trace_dir"/traces/*.cubin)
    local static_maps=("$trace_dir"/traces/*.static_map.csv)

    if [[ ${#cubins[@]} -eq 0 ]]; then
        echo "ERROR: no cubin files found under $trace_dir/traces"
        shopt -u nullglob
        exit 1
    fi

    for static_map in "${static_maps[@]}"; do
        cp "$static_map" "$BUNDLE_SASS_DIR/"
    done

    local cubin
    for cubin in "${cubins[@]}"; do
        local base_name
        base_name="$(basename "$cubin" .cubin)"
        if [[ -x "$cuobjdump_bin" ]]; then
            "$cuobjdump_bin" --dump-sass "$cubin" >"$BUNDLE_SASS_DIR/${base_name}.sass"
        elif [[ -x "$nvdisasm_bin" ]]; then
            "$nvdisasm_bin" "$cubin" >"$BUNDLE_SASS_DIR/${base_name}.sass"
        else
            echo "ERROR: neither cuobjdump nor nvdisasm is available under $CUDA_INSTALL_PATH/bin"
            shopt -u nullglob
            exit 1
        fi
    done
    shopt -u nullglob
}

capture_trace_bundle() {
    local run_dir="$1"
    rm -rf "$BUNDLE_TRACE_DIR" "$BUNDLE_SASS_DIR" "$BUNDLE_SRC_DIR"
    mkdir -p "$BUNDLE_TRACE_DIR" "$BUNDLE_SASS_DIR" "$BUNDLE_SRC_DIR"

    cp "$run_dir/run.sh" "$BUNDLE_TRACE_DIR/"
    cp "$run_dir/run_spinlock_detection.sh" "$BUNDLE_TRACE_DIR/"
    cp -a "$run_dir/traces" "$BUNDLE_TRACE_DIR/"
    cp "$run_dir/$METADATA_NAME" "$BUNDLE_METADATA_DIR/trace_metadata.json"

    capture_source_snapshot
    capture_sass_snapshot "$run_dir"
}

require_existing_bundle_trace() {
    if [[ ! -f "$BUNDLE_METADATA_DIR/trace_metadata.json" ]]; then
        echo "ERROR: --skip-trace was set, but bundle metadata is missing: $BUNDLE_METADATA_DIR/trace_metadata.json"
        exit 1
    fi
    if [[ ! -f "$BUNDLE_TRACE_DIR/traces/kernelslist.g" ]]; then
        echo "ERROR: --skip-trace was set, but bundle trace is missing: $BUNDLE_TRACE_DIR/traces/kernelslist.g"
        exit 1
    fi
}

build_benchmark() {
    echo "[build] Building ima_tiny_case..."
    (
        cd "$BASE_DIR/gpu-app-collection/src"
        # shellcheck disable=SC1091
        source ./setup_environment >/dev/null
        make -C cuda/custom-apps/ima_tiny_case
    )
}

run_native_check() {
    local native_log="$BUNDLE_NATIVE_DIR/${LOG_STEM}_native_stdout.txt"
    local native_meta="$BUNDLE_NATIVE_DIR/${LOG_STEM}_native_metadata.json"
    local exec_path
    exec_path="$(native_exec_path)"
    if [[ ! -x "$exec_path" ]]; then
        echo "ERROR: benchmark binary not found: $exec_path"
        exit 1
    fi
    echo "[native] Running benchmark sanity check..."
    (
        cd "$BUNDLE_NATIVE_DIR"
        export_tiny_env
        "$exec_path" \
            --ctas "$CTAS" \
            --warps-per-cta "$WARPS_PER_CTA" \
            --warmup-iters "$WARMUP_ITERS" \
            --ima-iters "$IMA_ITERS" \
            --tail-iters "$TAIL_ITERS" \
            --data-lines "$DATA_LINES" \
            --mapping-seed "$MAPPING_SEED" \
            --compute-gap "$COMPUTE_GAP" \
            --metadata-out "$native_meta" \
            >"$native_log"
    )
    echo "  Native stdout:   $native_log"
    echo "  Native metadata: $native_meta"
}

generate_trace() {
    local run_dir
    run_dir="$(trace_run_dir)"
    echo "[trace] Generating NVBit trace into $run_dir ..."
    rm -rf "$run_dir"
    (
        cd "$BASE_DIR"
        # shellcheck disable=SC1091
        source "$BASE_DIR/gpu-app-collection/src/setup_environment" >/dev/null
        export_tiny_env
        python3 util/tracer_nvbit/run_hw_trace.py -B "$SUITE_NAME" -D "$DEVICE_NUM"
    )
    if [[ ! -f "$run_dir/traces/kernelslist.g" ]]; then
        echo "ERROR: missing kernelslist.g after trace generation"
        exit 1
    fi
    if [[ ! -f "$run_dir/$METADATA_NAME" ]]; then
        echo "ERROR: metadata file not found in trace run dir: $run_dir/$METADATA_NAME"
        exit 1
    fi

    capture_trace_bundle "$run_dir"
    echo "  Bundle trace dir: $BUNDLE_TRACE_DIR"
}

cleanup_label_outputs() {
    local label="$1"
    find "$OUT_DIR" -maxdepth 1 -type f \
        \( -name "warp_gantt_${label}.*" \
        -o -name "phase_timeline_${label}.*" \
        -o -name "ima_chain_${label}_w*" \
        -o -name "overall_cacheline_*_${label}.*" \) \
        -delete
    rm -f \
        "$BUNDLE_ANALYSIS_DIR/phase_summary_${label}.csv" \
        "$BUNDLE_ANALYSIS_DIR/ima_region_summary_${label}.csv" \
        "$BUNDLE_ANALYSIS_DIR/chain_summary_${label}.csv"
}

plot_label() {
    local label="$1"
    local log_name="$2"
    local metadata="$BUNDLE_METADATA_DIR/trace_metadata.json"
    cleanup_label_outputs "$label"
    python3 "$TINY_DIR/analyze_tiny_case.py" \
        --metadata "$metadata" \
        --l1-trace "$BASE_DIR/result/L1cache_trace/${log_name}_l1.csv" \
        --issue-trace "$BASE_DIR/result/issue_trace/${log_name}_issue.csv" \
        --scheduler-label "$label" \
        --out-dir "$OUT_DIR" \
        --format "$FORMAT" \
        --plots "$PLOTS_MODE" \
        --top-warps "$TOP_WARPS"
}

log_name_for() {
    local variant="$1"
    local scheduler="$2"
    local stem="$LOG_STEM"
    if [[ "$variant" == "baseline" ]]; then
        stem+="_base"
    else
        stem+="_pf"
    fi
    if [[ "$scheduler" == "gto" ]]; then
        stem+="_gto"
    fi
    echo "$stem"
}

label_for() {
    local variant="$1"
    local scheduler="$2"
    local prefix="base"
    if [[ "$variant" == "imapf" ]]; then
        prefix="pf"
    fi
    echo "${prefix}_${scheduler}"
}

config_for() {
    local variant="$1"
    if [[ "$variant" == "baseline" ]]; then
        echo "$BASE_CONFIG"
    else
        echo "$PREFETCH_CONFIG"
    fi
}

archive_sim_outputs() {
    local label="$1"
    local log_name="$2"
    local target_dir="$BUNDLE_SIM_DIR/$label"
    mkdir -p "$target_dir/stall_reason_pc_stats"

    cp "$BASE_DIR/result/log/${log_name}.log" "$target_dir/"
    cp "$BASE_DIR/result/L1cache_trace/${log_name}_l1.csv" "$target_dir/"
    cp "$BASE_DIR/result/L2cache_trace/${log_name}_l2.csv" "$target_dir/"
    cp "$BASE_DIR/result/issue_trace/${log_name}_issue.csv" "$target_dir/"
    cp "$BASE_DIR/result/bandwidth/${log_name}_hbm_partition.csv" "$target_dir/"
    cp -a "$BASE_DIR/result/issue_trace/stall_reason_pc_stats/${log_name}/." "$target_dir/stall_reason_pc_stats/"
}

run_simulation() {
    local variant="$1"
    local scheduler="$2"
    local config_model
    local label
    local log_name
    config_model="$(config_for "$variant")"
    label="$(label_for "$variant" "$scheduler")"
    log_name="$(log_name_for "$variant" "$scheduler")"

    local -a cmd=(
        "$BASE_DIR/traceL1"
        -c "$config_model"
        --issue-trace
    )
    if [[ "$scheduler" == "gto" ]]; then
        cmd+=(-gto)
    fi
    cmd+=("$TRACE_KEY" "$log_name")

    echo "[sim] ${cmd[*]}"
    (cd "$BASE_DIR" && "${cmd[@]}")
    archive_sim_outputs "$label" "$log_name"
    plot_label "$label" "$log_name"
}

write_prefetch_compare() {
    if [[ "$PREFETCH_MODE" != "both" ]]; then
        return
    fi
    python3 - "$BUNDLE_ANALYSIS_DIR" "$SCHEDULER_MODE" <<'PY'
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1])
requested = sys.argv[2]
if requested == "both":
    schedulers = ("lrr", "gto")
else:
    schedulers = (requested,)

rows = []
for scheduler in schedulers:
    base_path = root / f"ima_region_summary_base_{scheduler}.csv"
    pf_path = root / f"ima_region_summary_pf_{scheduler}.csv"
    if not base_path.exists() or not pf_path.exists():
        continue
    with base_path.open() as handle:
        base_rows = {row["role"]: row for row in csv.DictReader(handle)}
    with pf_path.open() as handle:
        pf_rows = {row["role"]: row for row in csv.DictReader(handle)}
    for role in ("index_load", "data_load"):
        if role not in base_rows or role not in pf_rows:
            continue
        base = base_rows[role]
        pf = pf_rows[role]
        base_miss = float(base["miss_like_rate"])
        pf_miss = float(pf["miss_like_rate"])
        base_lat = float(base["avg_service_cycles"])
        pf_lat = float(pf["avg_service_cycles"])
        rows.append(
            {
                "scheduler": scheduler,
                "role": role,
                "base_issue_count": base["issue_count"],
                "pf_issue_count": pf["issue_count"],
                "base_hit_count": base["hit_count"],
                "pf_hit_count": pf["hit_count"],
                "base_miss_like_count": base["miss_like_count"],
                "pf_miss_like_count": pf["miss_like_count"],
                "base_resfail_count": base["resfail_count"],
                "pf_resfail_count": pf["resfail_count"],
                "base_unknown_count": base["unknown_count"],
                "pf_unknown_count": pf["unknown_count"],
                "base_miss_like_rate": base["miss_like_rate"],
                "pf_miss_like_rate": pf["miss_like_rate"],
                "miss_like_rate_delta": f"{pf_miss - base_miss:.4f}",
                "base_avg_service_cycles": base["avg_service_cycles"],
                "pf_avg_service_cycles": pf["avg_service_cycles"],
                "avg_service_cycles_delta": f"{pf_lat - base_lat:.1f}",
            }
        )

out_path = root / "prefetch_compare.csv"
with out_path.open("w", newline="") as handle:
    fieldnames = [
        "scheduler",
        "role",
        "base_issue_count",
        "pf_issue_count",
        "base_hit_count",
        "pf_hit_count",
        "base_miss_like_count",
        "pf_miss_like_count",
        "base_resfail_count",
        "pf_resfail_count",
        "base_unknown_count",
        "pf_unknown_count",
        "base_miss_like_rate",
        "pf_miss_like_rate",
        "miss_like_rate_delta",
        "base_avg_service_cycles",
        "pf_avg_service_cycles",
        "avg_service_cycles_delta",
    ]
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f"  Saved: {out_path}")
PY
}

run_requested_variants() {
    local variants=()
    if [[ "$PREFETCH_MODE" == "baseline" || "$PREFETCH_MODE" == "both" ]]; then
        variants+=("baseline")
    fi
    if [[ "$PREFETCH_MODE" == "imapf" || "$PREFETCH_MODE" == "both" ]]; then
        variants+=("imapf")
    fi

    local schedulers=()
    if [[ "$SCHEDULER_MODE" == "both" ]]; then
        schedulers=("lrr" "gto")
    else
        schedulers=("$SCHEDULER_MODE")
    fi

    local variant
    local scheduler
    for variant in "${variants[@]}"; do
        for scheduler in "${schedulers[@]}"; do
            run_simulation "$variant" "$scheduler"
        done
    done
}

init_bundle_paths
mkdir_bundle_dirs
write_bundle_manifest
validate_environment

echo "============================================"
echo "IMA Tiny Case"
echo "  Bundle ID:        $BUNDLE_ID"
echo "  Bundle dir:       $BUNDLE_DIR"
echo "  Base config:      $BASE_CONFIG"
echo "  Prefetch config:  $PREFETCH_CONFIG"
echo "  Prefetch mode:    $PREFETCH_MODE"
echo "  Scheduler(s):     $SCHEDULER_MODE"
echo "  Plots:            $PLOTS_MODE"
echo "  Default launch:   ${CTAS} CTA(s) x ${WARPS_PER_CTA} warp(s)"
echo "  Phases:           warmup=$WARMUP_ITERS ima=$IMA_ITERS tail=$TAIL_ITERS"
echo "  Data lines:       $DATA_LINES"
echo "  Compute gap:      $COMPUTE_GAP"
echo "  Device:           $DEVICE_NUM"
echo "  Output format:    $FORMAT"
echo "============================================"

if [[ $SKIP_BUILD -eq 0 ]]; then
    build_benchmark
fi

if [[ $RUN_NATIVE_CHECK -eq 1 ]]; then
    run_native_check
fi

if [[ $SKIP_TRACE -eq 0 ]]; then
    generate_trace
else
    require_existing_bundle_trace
fi

if [[ $SKIP_SIM -eq 0 ]]; then
    run_requested_variants
    write_prefetch_compare
fi

echo "Done."
