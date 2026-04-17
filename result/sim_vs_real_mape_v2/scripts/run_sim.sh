#!/usr/bin/env bash
# Usage: run_sim.sh <cfg_id>
# Emits result/sim_vs_real_mape_v2/sim_logs/cfg_<id>.log (named by cfg_tag)
set -euo pipefail

CFG_ID="${1:?cfg_id required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CFGS="$ROOT/result/sim_vs_real_mape_v2/scripts/configs.csv"

ROW=$(awk -F, -v id="$CFG_ID" 'NR>1 && $1==id' "$CFGS" | tr -d '\r')
[ -z "$ROW" ] && { echo "config $CFG_ID not found"; exit 1; }
IFS=, read -r id workload label seq batch nheads kv_heads head_dim page_size M K N rms_M rms_hidden kernel_regex cfg_tag <<<"$ROW"

echo "[cfg $CFG_ID] label=$label cfg_tag=$cfg_tag"

# Load simulator env if not already done
if [ -z "${ACCELSIM_SETUP_ENVIRONMENT_WAS_RUN:-}" ]; then
    set +eu
    source "$ROOT/gpu-simulator/setup_environment.sh" release
    SETUP_EXIT=$?
    set -eu
    [ $SETUP_EXIT -ne 0 ] && { echo "ERROR: setup_environment.sh failed (exit $SETUP_EXIT)"; exit 1; }
fi

SIM_BIN="$ROOT/gpu-simulator/bin/release/accel-sim.out"
TRACE_CONFIG="$ROOT/gpu-simulator/configs/tested-cfgs/SM80_A100/trace.config"
GPGPU_CONFIG_ORIG="$ROOT/gpu-simulator/gpgpu-sim/configs/tested-cfgs/SM80_A100/gpgpusim.config"

TRACE_ROOT="$ROOT/result/sim_vs_real_mape_v2/traces/$cfg_tag"

# Prefer freshly generated trace; fall back to reuse paths (hw_run layouts)
KERNELSLIST="$TRACE_ROOT/traces/kernelslist.g"
if [ ! -f "$KERNELSLIST" ]; then
    for p in "$TRACE_ROOT/_reuse_src/traces/kernelslist.g" \
             "$TRACE_ROOT/_reuse_src/NO_ARGS/traces/kernelslist.g"; do
        if [ -f "$p" ]; then KERNELSLIST="$p"; break; fi
    done
fi
[ -f "$KERNELSLIST" ] || { echo "no trace for $cfg_tag (last tried: $KERNELSLIST)"; exit 1; }

echo "[cfg $CFG_ID] trace=$KERNELSLIST"

mkdir -p "$ROOT/result/sim_vs_real_mape_v2/sim_logs"
LOG="$ROOT/result/sim_vs_real_mape_v2/sim_logs/${cfg_tag}.log"

# Create a temp config with expensive traces disabled
TEMP_CONFIG=$(mktemp /tmp/gpgpusim_cfg_XXXXXX.config)
trap 'rm -f "$TEMP_CONFIG"' EXIT

# Copy original config, then disable all trace outputs
cp "$GPGPU_CONFIG_ORIG" "$TEMP_CONFIG"

# Disable or append trace-disable entries
for flag in l1_trace_enable l2_trace_enable issue_trace_enable; do
    if grep -q "^-${flag}[[:space:]]" "$TEMP_CONFIG"; then
        sed -i "s|^-${flag}[[:space:]].*|-${flag} 0|g" "$TEMP_CONFIG"
    else
        echo "-${flag} 0" >> "$TEMP_CONFIG"
    fi
done
if grep -q '^-hbm_partition_trace_enable[[:space:]]' "$TEMP_CONFIG"; then
    sed -i "s|^-hbm_partition_trace_enable[[:space:]].*|-hbm_partition_trace_enable 0|g" "$TEMP_CONFIG"
else
    echo "-hbm_partition_trace_enable 0" >> "$TEMP_CONFIG"
fi

echo "[cfg $CFG_ID] running sim -> $LOG"

# Run from repo root (required by accel-sim for relative paths in configs)
(
    cd "$ROOT"
    "$SIM_BIN" \
        -trace "$KERNELSLIST" \
        -config "$TRACE_CONFIG" \
        -config "$TEMP_CONFIG" \
        > "$LOG" 2>&1
)
SIM_EXIT=$?

if [ $SIM_EXIT -ne 0 ]; then
    echo "[cfg $CFG_ID] sim exit=$SIM_EXIT"
    tail -20 "$LOG"
    exit 2
fi

echo "[cfg $CFG_ID] sim done. log=$LOG"
grep -E "^(gpu_tot_sim_cycle|gpu_tot_ipc|gpu_tot_sim_insn|gpgpu_simulation_time)" "$LOG" | tail -8
