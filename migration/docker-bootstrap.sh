#!/usr/bin/env bash
# docker-bootstrap.sh — 双用途脚本
#   bootstrap         目标机器：启动 prefetch-env 容器
#   prepare-and-push  源机器：双阶段 commit（不影响源容器）→ push 到 ghcr.io

set -euo pipefail

# ================================================================
# 配置
# ================================================================
IMAGE_TAG="${IMAGE_TAG:-ghcr.io/linuohai/accel-sim-framework:migration-20260423}"
CONTAINER_NAME="${CONTAINER_NAME:-prefetch-env}"
NO_GPU="${NO_GPU:-0}"

# ================================================================
# 目标机器模式：启动容器
# ================================================================
bootstrap_container() {
    : "${HOST_PREFETCH_PATH:?bootstrap 模式需要 HOST_PREFETCH_PATH=/path/on/host}"

    if [ ! -d "$HOST_PREFETCH_PATH" ]; then
        echo "错误: HOST_PREFETCH_PATH=$HOST_PREFETCH_PATH 不存在" >&2
        exit 1
    fi

    local GPU_ARGS=""
    if [ "$NO_GPU" != "1" ]; then
        GPU_ARGS="--gpus all"
        if ! command -v nvidia-smi >/dev/null 2>&1; then
            echo "警告: 未找到 nvidia-smi；若确实无 GPU 请设 NO_GPU=1" >&2
        fi
    fi

    if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
        echo "容器 $CONTAINER_NAME 已存在，尝试启动..."
        docker start "$CONTAINER_NAME"
        return
    fi

    echo "从 $IMAGE_TAG 启动新容器 $CONTAINER_NAME..."
    docker run -dit --name "$CONTAINER_NAME" \
        $GPU_ARGS \
        --network host \
        --shm-size 64m \
        --ipc host \
        --privileged \
        --cap-add sys_ptrace \
        --security-opt seccomp=unconfined \
        --security-opt label=disable \
        --workdir /workspace/prefetch \
        --entrypoint /opt/nvidia/nvidia_entrypoint.sh \
        -v "${HOST_PREFETCH_PATH}:/workspace/prefetch:rw" \
        "$IMAGE_TAG" \
        /bin/bash

    echo "容器已启动:"
    docker ps --filter name="$CONTAINER_NAME"
}

# ================================================================
# 源机器模式：双阶段 commit，完全不碰源容器
#
# 流程：
#   1. docker commit SRC → intermediate 镜像（仅快照，不改 SRC）
#   2. docker run intermediate → worker 容器（挂相同 bind mount）
#   3. 在 worker 里做破坏性操作（清凭证、打包数据、打包 mini trace）
#   4. docker commit worker → 最终镜像（修 ENV）
#   5. docker push 最终镜像
#   6. 清理 worker 和 intermediate
#
# 源容器 SRC 在整个过程中不被修改（仅在 step 1 pause 几秒做快照）。
# ================================================================
prepare_and_push() {
    local SRC_CONTAINER="${1:-shn}"
    local NEW_TAG="${2:-$IMAGE_TAG}"
    local INTERMEDIATE_TAG="prefetch-migration-intermediate:$(date +%s)"
    local WORKER_NAME="migrate-worker-$$"

    if ! docker ps --format '{{.Names}}' | grep -qx "$SRC_CONTAINER"; then
        echo "错误: 源容器 $SRC_CONTAINER 不在运行中" >&2
        exit 1
    fi

    # 从 SRC 反推 /workspace/prefetch 的宿主路径，worker 挂相同 bind mount
    local BIND_SRC
    BIND_SRC=$(docker inspect "$SRC_CONTAINER" \
        --format '{{range .Mounts}}{{if eq .Destination "/workspace/prefetch"}}{{.Source}}{{end}}{{end}}')
    if [ -z "$BIND_SRC" ]; then
        echo "错误: 无法从 $SRC_CONTAINER 推断 /workspace/prefetch 的宿主路径" >&2
        exit 2
    fi
    echo "侦测到 bind mount 源: $BIND_SRC"

    cleanup() {
        echo "=== 清理临时资源 ==="
        docker rm -f "$WORKER_NAME" 2>/dev/null || true
        docker rmi "$INTERMEDIATE_TAG" 2>/dev/null || true
    }
    trap cleanup EXIT

    echo ""
    echo "=== Step 1/5: 快照源容器 → intermediate 镜像 ==="
    echo "  (仅对 $SRC_CONTAINER 做快照，pause 几秒；不改文件)"
    docker commit "$SRC_CONTAINER" "$INTERMEDIATE_TAG"

    echo ""
    echo "=== Step 2/5: 从 intermediate 起 worker 容器 ==="
    docker run -d --name "$WORKER_NAME" \
        -v "${BIND_SRC}:/workspace/prefetch:rw" \
        --entrypoint /bin/bash \
        "$INTERMEDIATE_TAG" \
        -c 'sleep infinity'
    sleep 2

    echo ""
    echo "=== Step 3/5: 在 worker 里清凭证 + 打数据包 ==="
    docker exec "$WORKER_NAME" bash -c '
        set -e

        # --- 清凭证 ---
        if command -v jq >/dev/null 2>&1 && [ -f ~/.claude/settings.json ]; then
            jq "del(.env.POE_API_KEY) | del(.POE_API_KEY)" ~/.claude/settings.json > /tmp/s.json
            mv /tmp/s.json ~/.claude/settings.json
        fi
        rm -rf ~/.claude/file-history ~/.claude/backups
        rm -f  ~/.claude/.credentials.json ~/.claude/history.jsonl ~/.claude.json
        rm -f  ~/.codex/auth.json ~/.codex/history.jsonl
        rm -f  ~/.bash_history ~/.viminfo ~/.ssh/known_hosts
        echo "  [1/3] 凭证清理完成"

        # --- 打 IMA 数据集 ---
        mkdir -p /opt/prefetch_staging
        tar -I "xz -T0 -3" -cf /opt/prefetch_staging/data_dirs.tar.xz \
            -C /workspace/prefetch/gpu-app-collection data_dirs
        tar -I "xz -T0 -3" -cf /opt/prefetch_staging/gardenia_datasets.tar.xz \
            -C /workspace/prefetch/gpu-app-collection/gardenia datasets
        echo "  [2/3] 数据集打包完成"

        # --- 打 mini flickr trace ---
        cd /workspace/prefetch/hw_run/traces/device-0/12.6
        tar -cf /opt/prefetch_staging/traces_mini.tar \
            bfs_linear_base/mtx___data_flickr_0_0_1586 \
            bfs_linear_base/mtx___data_flickr_1_0_1586 \
            sssp_linear_base/mtx___data_flickr_0_0_1586 \
            sssp_linear_base/mtx___data_flickr_1_0_1586 \
            bc_linear_base/mtx___data_flickr_0_0_1586 \
            bc_linear_base/mtx___data_flickr_1_0_1586 \
            cc_base/mtx___data_flickr_1_0 \
            spmv_base/mtx___data_flickr_1_0 \
            2>/dev/null || echo "  提示: 部分 flickr 子路径不存在，已跳过"
        echo "  [3/3] mini trace 打包完成"

        echo ""
        echo "  staging 汇总："
        du -sh /opt/prefetch_staging/*
    '

    echo ""
    echo "=== Step 4/5: commit worker → 最终镜像（修 ENV）==="
    docker commit \
        --change 'ENV PIP_INDEX_URL=https://pypi.org/simple/' \
        --change 'ENV ACCEL_SIM_HOME=/workspace/prefetch' \
        --change 'CMD ["/bin/bash"]' \
        "$WORKER_NAME" "$NEW_TAG"

    echo ""
    echo "=== Step 5/5: push 到 ghcr.io ==="
    docker push "$NEW_TAG"

    echo ""
    echo "==============================================="
    echo "完成。镜像已 push 到 $NEW_TAG"
    echo "源容器 $SRC_CONTAINER 全程未受影响。"
    echo "==============================================="
}

# ================================================================
# 入口
# ================================================================
case "${1:-bootstrap}" in
    bootstrap)
        bootstrap_container
        ;;
    prepare-and-push)
        shift
        prepare_and_push "$@"
        ;;
    *)
        cat <<EOF
Usage:
    # 目标机器（默认）:
    HOST_PREFETCH_PATH=/data/prefetch bash docker-bootstrap.sh
    HOST_PREFETCH_PATH=/data/prefetch bash docker-bootstrap.sh bootstrap

    # 源机器（双阶段 commit → push）:
    bash docker-bootstrap.sh prepare-and-push [src_container=shn] [new_tag]

环境变量:
    HOST_PREFETCH_PATH   bootstrap 模式必需，目标机器宿主代码根路径
    IMAGE_TAG            镜像 tag（默认 ghcr.io/linuohai/accel-sim-framework:migration-20260423）
    CONTAINER_NAME       容器名（默认 prefetch-env）
    NO_GPU               =1 跳过 --gpus all（无 GPU 机器）
EOF
        exit 1
        ;;
esac
