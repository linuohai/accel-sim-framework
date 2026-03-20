#!/usr/bin/env bash
set -euo pipefail

ROOT="/workspace/prefetch"
OUT_DIR="${ROOT}/ima_plan/01_ima_characterization/broader_sass_analysis/raw_sass"
INCLUDE_DIR="${ROOT}/gpu-app-collection/gardenia/include"
CUDA_INCLUDE="/usr/local/cuda/include"

declare -A SOURCES=(
  [pr]="${ROOT}/gpu-app-collection/gardenia/src/pr/base.cu"
  [vc]="${ROOT}/gpu-app-collection/gardenia/src/vc/linear_base.cu"
  [scc]="${ROOT}/gpu-app-collection/gardenia/src/scc/base.cu"
)

declare -A BASENAMES=(
  [pr]="pr_base"
  [vc]="vc_linear_base"
  [scc]="scc_base"
)

declare -A EXTRA_FLAGS=(
  [pr]=""
  [vc]=""
  [scc]="-include thrust/sort.h"
)

for algo in pr vc scc; do
  for sm in 70 80 90; do
    algo_dir="${OUT_DIR}/${algo}/sm${sm}"
    cubin_path="${algo_dir}/${BASENAMES[$algo]}.sm${sm}.cubin"
    sass_path="${algo_dir}/${BASENAMES[$algo]}.sm${sm}.sass"
    mkdir -p "${algo_dir}"
    nvcc -O3 -w -lineinfo -std=c++11 -DTHRUST_IGNORE_CUB_VERSION_CHECK \
      ${EXTRA_FLAGS[$algo]} \
      -gencode arch=compute_${sm},code=sm_${sm} \
      -I"${INCLUDE_DIR}" -I"${CUDA_INCLUDE}" \
      -cubin "${SOURCES[$algo]}" -o "${cubin_path}"
    nvdisasm --print-code --print-line-info --separate-functions "${cubin_path}" > "${sass_path}"
  done
done
