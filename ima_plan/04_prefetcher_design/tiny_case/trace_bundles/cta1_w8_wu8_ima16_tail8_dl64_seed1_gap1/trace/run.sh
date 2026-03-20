set -e

export DYNAMIC_KERNEL_RANGE=""

export CUDA_VERSION="12.6"; export CUDA_VISIBLE_DEVICES="0" ; 
rm -f traces/*
export TRACES_FOLDER=/workspace/prefetch/hw_run/traces/device-0/12.6/ima_tiny_case/NO_ARGS; ENABLE_SPINLOCK_FAST_FORWARD=0 SPINLOCK_ITER_TO_KEEP=1 CUDA_INJECTION64_PATH=/workspace/prefetch/util/tracer_nvbit/tracer_tool/tracer_tool.so /workspace/prefetch/gpu-app-collection/src/..//bin/12.6/release/ima_tiny_case  ; /workspace/prefetch/util/tracer_nvbit/tracer_tool/traces-processing/post-traces-processing /workspace/prefetch/hw_run/traces/device-0/12.6/ima_tiny_case/NO_ARGS/traces ; rm -f /workspace/prefetch/hw_run/traces/device-0/12.6/ima_tiny_case/NO_ARGS/traces/*.trace ; rm -f /workspace/prefetch/hw_run/traces/device-0/12.6/ima_tiny_case/NO_ARGS/traces/kernelslist 