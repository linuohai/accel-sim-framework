#!/usr/bin/env bash
# restore.sh — 一键复刻调度器（目标机器宿主上执行）
# 串联 MIGRATION.md §5.2–§5.9 的步骤。每个步骤独立可重跑。
#
# 用法：
#   export HOST_PREFETCH_PATH=/data/prefetch
#   cd $HOST_PREFETCH_PATH         # 已 git clone 主仓库
#   bash migration/restore.sh
#
# 出错时会打印失败步骤号；定位到 MIGRATION.md 对应 §5.X 重跑即可。

set -euo pipefail

# ================================================================
# 配置
# ================================================================
: "${HOST_PREFETCH_PATH:?需要 HOST_PREFETCH_PATH=/path/on/host}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_TAG="${IMAGE_TAG:-ghcr.io/linuohai/accel-sim-framework:migration-20260423}"
CONTAINER_NAME="${CONTAINER_NAME:-prefetch-env}"
NO_GPU="${NO_GPU:-0}"

log() {
    echo ""
    echo "=== [restore] $* ==="
}

fail() {
    echo "" >&2
    echo "!!! 失败于 $1 — 定位到 MIGRATION.md §$2 重跑" >&2
    exit 1
}

# ================================================================
# 5.3 — docker pull
# ================================================================
step_5_3_pull() {
    log "Step 5.3: docker pull $IMAGE_TAG"
    docker pull "$IMAGE_TAG" || fail "docker pull" "5.3"
}

# ================================================================
# 5.4 — docker run
# ================================================================
step_5_4_run() {
    log "Step 5.4: 启动容器 $CONTAINER_NAME"
    IMAGE_TAG="$IMAGE_TAG" CONTAINER_NAME="$CONTAINER_NAME" NO_GPU="$NO_GPU" \
        bash "$SCRIPT_DIR/docker-bootstrap.sh" bootstrap \
        || fail "docker run" "5.4"
}

# ================================================================
# 5.5 — 解压 IMA 数据集 + mini trace
# ================================================================
step_5_5_extract() {
    log "Step 5.5: 解压 IMA 数据集 + mini trace"
    docker exec "$CONTAINER_NAME" bash -c '
        set -e
        mkdir -p /workspace/prefetch/hw_run/traces/device-0/12.6

        if [ -f /opt/prefetch_staging/data_dirs.tar.xz ]; then
            tar -I "xz -T0" -xf /opt/prefetch_staging/data_dirs.tar.xz \
                -C /workspace/prefetch/gpu-app-collection/
            echo "  data_dirs 解压完成"
        fi

        if [ -f /opt/prefetch_staging/gardenia_datasets.tar.xz ]; then
            tar -I "xz -T0" -xf /opt/prefetch_staging/gardenia_datasets.tar.xz \
                -C /workspace/prefetch/gpu-app-collection/gardenia/
            echo "  gardenia/datasets 解压完成"
        fi

        if [ -f /opt/prefetch_staging/traces_mini.tar ]; then
            tar -xf /opt/prefetch_staging/traces_mini.tar \
                -C /workspace/prefetch/hw_run/traces/device-0/12.6/
            echo "  mini flickr trace 解压完成"
        fi
    ' || fail "解压 staging" "5.5"
}

# ================================================================
# 5.6 — clone 子仓库
# ================================================================
step_5_6_clone_subrepos() {
    log "Step 5.6: clone 子仓库 + 重建 worktree"
    docker exec "$CONTAINER_NAME" bash -c '
        cd /workspace/prefetch && bash migration/clone_subrepos.sh
    ' || fail "clone 子仓库" "5.6"
}

# ================================================================
# 5.7 — 编译 accel-sim
# ================================================================
step_5_7_build() {
    log "Step 5.7: 编译 accel-sim"
    docker exec "$CONTAINER_NAME" bash -lc '
        cd /workspace/prefetch
        source gpu-simulator/setup_environment.sh
        make -j -C gpu-simulator/
    ' || fail "编译 accel-sim" "5.7"
}

# ================================================================
# 5.9 — smoke test
# ================================================================
step_5_9_smoke() {
    log "Step 5.9: smoke test"
    docker exec "$CONTAINER_NAME" bash -lc '
        cd /workspace/prefetch
        ./traceL1 --max-completed-cta 50 bfs_flickr_sym migration_smoke
        if grep -q "status=COMPLETE" result/log/migration_smoke.log; then
            echo "OK: smoke test 通过"
        else
            echo "FAIL: smoke test 未得到 status=COMPLETE" >&2
            exit 1
        fi
    ' || fail "smoke test" "5.9"
}

# ================================================================
# 主流程
# ================================================================
cat <<EOF

==============================================
  GRASP 环境复刻 restore.sh
  宿主路径: $HOST_PREFETCH_PATH
  镜像:     $IMAGE_TAG
  容器名:   $CONTAINER_NAME
  GPU 模式: $([ "$NO_GPU" = "1" ] && echo "无 GPU（跳过 --gpus all）" || echo "启用 GPU")
==============================================

接下来会依次执行：
  5.3  docker pull
  5.4  docker run 起容器
  5.5  容器内解压数据集 + mini trace
  5.6  容器内 clone 子仓库
  5.7  容器内编译 accel-sim
  5.9  smoke test

5.8 首次登录 agent (claude/codex login) 需交互，**不在本脚本范围**。
跑完后需手动 \`docker exec -it $CONTAINER_NAME bash\` 登录。

EOF

step_5_3_pull
step_5_4_run
step_5_5_extract
step_5_6_clone_subrepos
step_5_7_build
step_5_9_smoke

cat <<EOF

==============================================
  restore.sh 完成！
==============================================

下一步人工操作：

1. 进容器手动登录 Claude Code 和 Codex：
   docker exec -it $CONTAINER_NAME bash
   claude login
   codex login

2. (可选) 手填 POE_API_KEY：
   jq '.env.POE_API_KEY = "<your-key>"' ~/.claude/settings.json \
     > /tmp/s.json && mv /tmp/s.json ~/.claude/settings.json

3. (仅有 GPU 机器需要) 重生成全量 paper trace：
   docker exec -it $CONTAINER_NAME bash
   bash /workspace/prefetch/migration/regenerate_traces.sh

详见 MIGRATION.md §5.8、§6。

EOF
