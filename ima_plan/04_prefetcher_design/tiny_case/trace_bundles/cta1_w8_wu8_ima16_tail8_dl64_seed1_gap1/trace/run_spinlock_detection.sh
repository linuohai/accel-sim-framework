set -e

export DYNAMIC_KERNEL_RANGE=""

export CUDA_VERSION="12.6"; export CUDA_VISIBLE_DEVICES="0" ; 
rm -f spinlock_detection/*
export TRACES_FOLDER=/workspace/prefetch/hw_run/traces/device-0/12.6/ima_tiny_case/NO_ARGS; SPINLOCK_PHASE=0 CUDA_INJECTION64_PATH=/workspace/prefetch/util/tracer_nvbit/others/spinlock_tool/spinlock_tool.so /workspace/prefetch/gpu-app-collection/src/..//bin/12.6/release/ima_tiny_case  ;  SPINLOCK_PHASE=1 CUDA_INJECTION64_PATH=/workspace/prefetch/util/tracer_nvbit/others/spinlock_tool/spinlock_tool.so /workspace/prefetch/gpu-app-collection/src/..//bin/12.6/release/ima_tiny_case  ; 