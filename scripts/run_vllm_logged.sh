#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."
mkdir -p data/logs

: > data/logs/vllm_launcher.log
{
  echo "Starting vLLM from $(pwd)"
  echo "vLLM log: $(pwd)/data/logs/vllm.log"
  echo "Effective VLLM_MAX_MODEL_LEN=${VLLM_MAX_MODEL_LEN:-32768}"
  echo "Effective VLLM_EXTRA_ARGS=${VLLM_EXTRA_ARGS:-}"
} | tee -a data/logs/vllm_launcher.log

exec bash scripts/start_vllm_mini3b.sh > data/logs/vllm.log 2>&1
