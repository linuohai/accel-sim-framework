#!/usr/bin/env bash
set -euo pipefail

# Extract SM80 SASS for 6 gardenia algorithms
# - Group A (4): from compiled binary via cuobjdump
# - Group B (2): from source via nvcc -cubin

CUDA=/usr/local/cuda-12.6/bin
ROOT=/workspace/prefetch
GARDENIA=${ROOT}/gpu-app-collection/gardenia
BIN_DIR=${GARDENIA}/bin
SRC_DIR=${GARDENIA}/src
INC_DIR=${GARDENIA}/include
OUT_DIR=${ROOT}/ima_plan/01_ima_characterization/sass_analysis/gardenia_sm80

mkdir -p "${OUT_DIR}"

extract_from_binary() {
  local workload=$1 cubin_in_binary=$2 outname=$3
  echo "--- Extracting ${outname} from ${workload} ---"

  cd "${OUT_DIR}"
  # Remove stale cubin if exists (from previous run)
  rm -f "${cubin_in_binary}"

  ${CUDA}/cuobjdump -xelf "${cubin_in_binary}" "${BIN_DIR}/${workload}"
  mv "${cubin_in_binary}" "${outname}.sm80.cubin"

  ${CUDA}/nvdisasm --print-code --print-line-info --separate-functions \
    "${outname}.sm80.cubin" > "${outname}.sm80.sass"

  local lines
  lines=$(wc -l < "${outname}.sm80.sass")
  echo "OK: ${outname}.sm80.sass (${lines} lines)"
}

compile_from_source() {
  local source=$1 outname=$2
  shift 2
  local extra_flags=("$@")
  echo "--- Compiling ${outname} from ${source} ---"

  ${CUDA}/nvcc -O3 -w -lineinfo -std=c++11 \
    -DTHRUST_IGNORE_CUB_VERSION_CHECK \
    "${extra_flags[@]}" \
    -gencode arch=compute_80,code=sm_80 \
    -I"${INC_DIR}" -I/usr/local/cuda/include \
    -cubin "${source}" \
    -o "${OUT_DIR}/${outname}.sm80.cubin"

  ${CUDA}/nvdisasm --print-code --print-line-info --separate-functions \
    "${OUT_DIR}/${outname}.sm80.cubin" > "${OUT_DIR}/${outname}.sm80.sass"

  local lines
  lines=$(wc -l < "${OUT_DIR}/${outname}.sm80.sass")
  echo "OK: ${outname}.sm80.sass (${lines} lines)"
}

echo "====== Phase 1: Group A - Extract from binaries ======"

extract_from_binary pr_base          "base.sm_80.cubin"          pr_base
extract_from_binary symgs_base       "base.sm_80.cubin"          symgs_base
extract_from_binary tc_gpu_base      "gpu_base.sm_80.cubin"      tc_gpu_base
extract_from_binary vc_linear_base   "linear_base.sm_80.cubin"   vc_linear_base

echo ""
echo "====== Phase 2: Group B - Compile from source ======"

compile_from_source "${SRC_DIR}/scc/base.cu" scc_base -include thrust/sort.h
compile_from_source "${SRC_DIR}/mst/main.cu" mst_main

echo ""
echo "====== All extractions complete ======"
ls -lh "${OUT_DIR}"/*.sass
