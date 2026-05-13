#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."
mkdir -p data/logs

: > data/logs/vllm_launcher.log
: > data/logs/vllm.log
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-32768}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.90}"
VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-}"
VLLM_ENFORCE_EAGER="${VLLM_ENFORCE_EAGER:-false}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"

if [[ "${VLLM_EXTRA_ARGS}" =~ --(gpu-memory-utilization|max-model-len|max-num-seqs|enforce-eager)([[:space:]=]|$) ]]; then
  {
    echo "ERROR: VLLM_EXTRA_ARGS contains a core vLLM flag."
    echo "Use VLLM_MAX_MODEL_LEN, VLLM_GPU_MEMORY_UTILIZATION, VLLM_MAX_NUM_SEQS, or VLLM_ENFORCE_EAGER instead."
  } | tee -a data/logs/vllm_launcher.log
  exit 1
fi

{
  echo "Starting vLLM from $(pwd)"
  echo "vLLM log: $(pwd)/data/logs/vllm.log"
  echo "Effective VLLM_MAX_MODEL_LEN=${VLLM_MAX_MODEL_LEN}"
  echo "Effective VLLM_GPU_MEMORY_UTILIZATION=${VLLM_GPU_MEMORY_UTILIZATION}"
  echo "Effective VLLM_MAX_NUM_SEQS=${VLLM_MAX_NUM_SEQS}"
  echo "Effective VLLM_ENFORCE_EAGER=${VLLM_ENFORCE_EAGER}"
  echo "Effective VLLM_EXTRA_ARGS=${VLLM_EXTRA_ARGS}"
} | tee -a data/logs/vllm_launcher.log

exec bash scripts/start_vllm_mini3b.sh > >(tee -a data/logs/vllm.log data/logs/vllm_launcher.log) 2>&1
