#!/usr/bin/env bash
# regenerate_traces.sh — 容器内执行：重新生成 paper 用到的 67.5 GB trace
#
# 前提：
#   1. 目标机器有 A100 GPU × 1-8
#   2. /workspace/prefetch/gpu-app-collection/{data_dirs,gardenia/datasets} 已解压到位
#   3. NVBit tracer 位于 /workspace/prefetch/util/tracer_nvbit/（镜像自带）
#   4. /usr/local/cuda-12.6 可用
#
# 本脚本是现有 generate_traces_*.sh 的调度器，不重新实现 tracer 逻辑。

set -euo pipefail

PREFETCH_ROOT="${PREFETCH_ROOT:-/workspace/prefetch}"
cd "$PREFETCH_ROOT"

# ================================================================
# 1. 前置检查
# ================================================================
echo "=== 前置检查 ==="

if ! command -v nvidia-smi >/dev/null 2>&1; then
    cat <<EOF >&2
错误: 未找到 nvidia-smi——目标机器没有 GPU。

Trace 重生成需要真实 GPU 运行 NVBit tracer。无 GPU 机器请使用镜像内置的
mini flickr trace bundle（已在 §5.5 解压到位），可直接跑 smoke + 5 算法 ×
flickr 的 baseline/GRASP 对比，例如：

    ./traceL1 --max-completed-cta 200 bfs_flickr_sym bfs_flickr_base
    ./traceL1 --grasp --max-completed-cta 200 bfs_flickr_sym bfs_flickr_grasp
    ./traceL1 --grasp --max-completed-cta 200 cc_flickr_sym cc_flickr_grasp
    # ...

详见 MIGRATION.md §5.10 + §6。
EOF
    exit 2
fi

if [ ! -f util/tracer_nvbit/tracer_tool/tracer_tool.so ]; then
    echo "错误: NVBit tracer.so 未找到" >&2
    echo "请检查 util/tracer_nvbit/ 是否在镜像内；若不在，需编译：" >&2
    echo "  cd util/tracer_nvbit && make" >&2
    exit 3
fi

if [ ! -d gpu-app-collection/data_dirs ]; then
    echo "错误: gpu-app-collection/data_dirs 不存在——IMA 数据集未解压" >&2
    echo "请回到 MIGRATION.md §5.5 完成数据集解压" >&2
    exit 4
fi

GPU_COUNT=$(nvidia-smi -L | wc -l)
echo "检测到 $GPU_COUNT 个 GPU"
if [ "$GPU_COUNT" -lt 1 ]; then
    echo "错误: 没有可用 GPU" >&2
    exit 5
fi

# ================================================================
# 2. 运行所有现有 generate_traces_*.sh 脚本
# ================================================================
# 这些脚本是原始机器上按批次写的，覆盖 paper 的 70 个子目录。
# 新机器上按顺序跑一遍即可。

SCRIPTS=(
    generate_traces.sh
    generate_traces_parallel.sh
    generate_traces_new_benchmarks.sh
    generate_traces_dmr_25k.sh
)

echo "=== 将依次执行以下脚本 ==="
for s in "${SCRIPTS[@]}"; do
    if [ -x "$s" ]; then
        echo "  [OK]   $s"
    elif [ -f "$s" ]; then
        echo "  [RD]   $s（只读权限）"
    else
        echo "  [MISS] $s（未找到）"
    fi
done

if [ "${DRY_RUN:-0}" = "1" ]; then
    echo "DRY_RUN=1 — 不实际执行，exit"
    exit 0
fi

echo ""
echo "开始执行。每个脚本完成后会打印 === done ==="

START_TS=$(date +%s)

for s in "${SCRIPTS[@]}"; do
    if [ -x "$s" ]; then
        echo ""
        echo "=== 运行 $s ==="
        ./"$s" || {
            echo "警告: $s 退出码非零——检查 log 后决定是否继续" >&2
            if [ "${HALT_ON_ERROR:-0}" = "1" ]; then
                exit 10
            fi
        }
        echo "=== $s done ==="
    elif [ -f "$s" ]; then
        bash "$s" || echo "警告: $s 退出码非零"
    fi
done

END_TS=$(date +%s)
DURATION=$((END_TS - START_TS))

echo ""
echo "=== 全部完成，总耗时 $((DURATION / 60)) 分钟 ==="
echo ""

# ================================================================
# 3. 验证产物
# ================================================================
TRACE_DIR="hw_run/traces/device-0/12.6"
if [ -d "$TRACE_DIR" ]; then
    TOTAL_SIZE=$(du -sh "$TRACE_DIR" | cut -f1)
    SUBDIRS=$(ls "$TRACE_DIR" | wc -l)
    echo "产物目录: $TRACE_DIR"
    echo "总大小:   $TOTAL_SIZE（期望 ~67.5 GB 左右）"
    echo "子目录数: $SUBDIRS（期望 70+ 覆盖 paper 用到的）"
else
    echo "错误: $TRACE_DIR 不存在——trace 生成失败" >&2
    exit 11
fi

echo ""
echo "下一步：跑 smoke test"
echo "  ./traceL1 --max-completed-cta 50 bfs_cit_sym regen_verify"
echo "  grep 'status=COMPLETE' result/log/regen_verify.log"
