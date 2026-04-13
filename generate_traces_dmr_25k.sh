#!/bin/bash
# Standalone trace generator for ls_dmr_25k (extension of generate_traces_new_benchmarks.sh)
# Usage: bash generate_traces_dmr_25k.sh

set -u  # don't set -e: we want to print status even on failure

export PATH=/usr/local/cuda-12.6/bin:$PATH

TRACER="/workspace/prefetch/util/tracer_nvbit/tracer_tool/tracer_tool.so"
POST="/workspace/prefetch/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing"
TRACE_OUT="/workspace/prefetch/hw_run/traces/device-0/12.6"

LSGPU_BIN="/workspace/prefetch/gpu-app-collection/src/cuda/lonestargpu-2.0/bin"
LSGPU_INPUTS="/workspace/prefetch/gpu-app-collection/data_dirs/cuda/lonestargpu-2.0/inputs"

name="ls_dmr_25k"
binary="$LSGPU_BIN/dmr"
workdir="$LSGPU_INPUTS"
args=("25k" "5")  # 5 iterations: enough to trigger check_triangles + refine pattern, keeps trace size manageable

dest="$TRACE_OUT/$name"

if [ -f "$dest/traces/kernelslist.g" ]; then
    echo "[SKIP] $name (already exists at $dest)"
    exit 0
fi

if [ ! -x "$binary" ]; then
    echo "[FAIL] DMR binary not executable: $binary"
    exit 1
fi

for f in 25k.ele 25k.node 25k.poly; do
    if [ ! -f "$workdir/$f" ]; then
        echo "[FAIL] Missing input: $workdir/$f"
        exit 1
    fi
done

echo "[GEN] $name ..."
tmpdir=$(mktemp -d /workspace/prefetch/tmp_trace_XXXXXX)
cd "$tmpdir" || exit 1

# Symlink input files into tmpdir (dmr expects 25k.ele/.node/.poly in CWD-relative path)
for f in "$workdir"/*; do
    ln -sf "$f" . 2>/dev/null
done

echo "[RUN] LD_PRELOAD=$TRACER $binary ${args[*]}"
if ! LD_PRELOAD="$TRACER" "$binary" "${args[@]}" > stdout.log 2>&1; then
    echo "[WARN] binary returned non-zero, checking traces anyway..."
fi

kl=$(find . -name "kernelslist*" -path "*/traces/*" 2>/dev/null | head -1)
if [ -z "$kl" ]; then
    echo "[FAIL] No kernelslist generated. stdout tail:"
    tail -20 stdout.log
    rm -rf "$tmpdir"
    exit 1
fi

traces_dir=$(dirname "$kl")
echo "[POST] post-processing $kl ..."
"$POST" "$kl" 2>&1 | tail -5

if [ ! -f "$traces_dir/kernelslist.g" ]; then
    echo "[FAIL] post-processing did not produce kernelslist.g"
    rm -rf "$tmpdir"
    exit 1
fi

kcount=$(grep -c "^kernel-" "$traces_dir/kernelslist.g" 2>/dev/null || echo 0)
echo "[OK] $name — $kcount kernels in $traces_dir"

# Move to final destination
mkdir -p "$dest"
mv "$traces_dir" "$dest/traces"
rm -rf "$tmpdir"
echo "[DONE] moved to $dest/traces"
ls -la "$dest/traces/" | head -10
