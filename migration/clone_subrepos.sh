#!/usr/bin/env bash
# clone_subrepos.sh — 容器内执行：clone 3 个自有 fork + 3 个上游只读 clone + 重建 worktree
# 读取 migration/manifest.json 获取 URL 和锁定 SHA

set -euo pipefail

MANIFEST="migration/manifest.json"
if [ ! -f "$MANIFEST" ]; then
    echo "错误: 在当前目录找不到 $MANIFEST；请确保 cwd 是 /workspace/prefetch" >&2
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "错误: 需要 jq" >&2
    exit 1
fi

# ================================================================
# Helper: clone repo 到指定 path，checkout 到指定 SHA / ref
# ================================================================
clone_to_ref() {
    local name="$1"
    local url="$2"
    local path="$3"
    local ref="$4"
    local branch="${5:-}"

    if [ "$ref" = "<TBD-after-prep>" ] || [ "$ref" = "null" ] || [ -z "$ref" ]; then
        echo "跳过 $name: ref 是 TBD 或空，等待源机器 Git prep 完成并更新 manifest" >&2
        return 1
    fi

    if [ -d "$path/.git" ]; then
        echo "[$name] 已存在 $path/.git，跳过 clone；尝试 fetch + checkout"
        (cd "$path" && git fetch origin && git checkout "$ref")
        return 0
    fi

    echo "[$name] clone $url -> $path"
    git clone "$url" "$path"
    (cd "$path" && git checkout "$ref")

    # 若指定了 branch，尝试把 HEAD 设到 branch（让后续 pull 有 upstream）
    if [ -n "$branch" ]; then
        (cd "$path" && git checkout -B "$branch" "$ref") || true
    fi
}

# ================================================================
# 1. 自有 fork — 非 worktree 的 3 个（gpgpu-sim, gpu-app-collection, gardenia）
# ================================================================
echo "=== 1. 自有 fork (自主仓库，通过 jq 从 manifest 读 SHA) ==="

# gpgpu-sim (dev)
URL=$(jq -r '.repos["gpgpu-sim_distribution"].url' "$MANIFEST")
PATH_REL=$(jq -r '.repos["gpgpu-sim_distribution"].path' "$MANIFEST")
SHA=$(jq -r '.repos["gpgpu-sim_distribution"].branches.dev.sha' "$MANIFEST")
clone_to_ref "gpgpu-sim@dev" "$URL" "$PATH_REL" "$SHA" "dev"

# gpu-app-collection (dev)
URL=$(jq -r '.repos["gpu-app-collection"].url' "$MANIFEST")
PATH_REL=$(jq -r '.repos["gpu-app-collection"].path' "$MANIFEST")
SHA=$(jq -r '.repos["gpu-app-collection"].branches.dev.sha' "$MANIFEST")
clone_to_ref "gpu-app-collection@dev" "$URL" "$PATH_REL" "$SHA" "dev"

# gardenia (master) — 嵌套在 gpu-app-collection 下
URL=$(jq -r '.repos.gardenia.url' "$MANIFEST")
PATH_REL=$(jq -r '.repos.gardenia.path' "$MANIFEST")
SHA=$(jq -r '.repos.gardenia.branches.master.sha' "$MANIFEST")
clone_to_ref "gardenia@master" "$URL" "$PATH_REL" "$SHA" "master"

# ================================================================
# 2. 上游只读 clone — pannotia / lonestargpu / pybind11
# ================================================================
echo "=== 2. 上游只读 clone ==="

for key in pannotia lonestargpu pybind11; do
    URL=$(jq -r ".upstream_readonly.$key.url" "$MANIFEST")
    PATH_REL=$(jq -r ".upstream_readonly.$key.path" "$MANIFEST")
    REF=$(jq -r ".upstream_readonly.$key.ref" "$MANIFEST")
    clone_to_ref "$key (upstream)" "$URL" "$PATH_REL" "$REF" ""
done

# ================================================================
# 3. worktrees/sota_stride — 父仓库的 worktree
# ================================================================
echo "=== 3. worktrees/sota_stride ==="

if [ -d "worktrees/sota_stride" ]; then
    echo "worktrees/sota_stride 已存在，跳过"
else
    git worktree add worktrees/sota_stride exp/sota_stride
fi

# ================================================================
# 4. sota_stride 内嵌的 gpgpu-sim — 独立 clone，分支 exp/sota_stride
# ================================================================
echo "=== 4. sota_stride 内嵌 gpgpu-sim（独立 clone，非 worktree）==="

URL=$(jq -r '.repos["gpgpu-sim_distribution"].url' "$MANIFEST")
SHA=$(jq -r '.repos["gpgpu-sim_distribution"].branches["exp/sota_stride"].sha' "$MANIFEST")
NESTED_PATH="worktrees/sota_stride/gpu-simulator/gpgpu-sim"
clone_to_ref "sota_stride/gpgpu-sim@exp/sota_stride" "$URL" "$NESTED_PATH" "$SHA" "exp/sota_stride"

# ================================================================
# 5. 可选：gpu-app-collection/gardenia/cub (upstream cub)
# ================================================================
# gardenia 的子依赖 cub 通常 gardenia 仓库自己管（submodule / git clone in Makefile）
# 若 gardenia 仓库内部没有自动拉 cub，此处可以手动 init

echo "=== 完成。所有仓库 clone 到位。==="
echo ""
echo "下一步："
echo "  1. 回到 docker 外，或 docker exec 重进入 prefetch-env"
echo "  2. source gpu-simulator/setup_environment.sh && make -j -C gpu-simulator/"
echo "  3. ./traceL1 --max-completed-cta 50 bfs_flickr_sym migration_smoke"
