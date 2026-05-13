#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-32768}"
VLLM_GPU_MEMORY_UTILIZATION="${VLLM_GPU_MEMORY_UTILIZATION:-0.90}"
VLLM_MAX_NUM_SEQS="${VLLM_MAX_NUM_SEQS:-}"
VLLM_ENFORCE_EAGER="${VLLM_ENFORCE_EAGER:-false}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"

if [[ "${VLLM_EXTRA_ARGS}" =~ --(gpu-memory-utilization|max-model-len|max-num-seqs|enforce-eager)([[:space:]=]|$) ]]; then
  echo "ERROR: VLLM_EXTRA_ARGS must not contain core vLLM flags."
  echo "Move --gpu-memory-utilization, --max-model-len, --max-num-seqs, and --enforce-eager to their dedicated VLLM_* environment variables."
  exit 1
fi

cmd=(
  vllm serve mistralai/Voxtral-Mini-3B-2507
  --host 0.0.0.0
  --port 8000
  --tokenizer_mode mistral
  --config_format mistral
  --load_format mistral
  --max-model-len "${VLLM_MAX_MODEL_LEN}"
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION}"
)

if [[ -n "${VLLM_MAX_NUM_SEQS}" ]]; then
  cmd+=(--max-num-seqs "${VLLM_MAX_NUM_SEQS}")
fi

if [[ "${VLLM_ENFORCE_EAGER}" == "true" ]]; then
  cmd+=(--enforce-eager)
fi

if [[ -n "${VLLM_EXTRA_ARGS}" ]]; then
  # shellcheck disable=SC2206
  extra_args=(${VLLM_EXTRA_ARGS})
  cmd+=("${extra_args[@]}")
fi

printf 'Final vLLM command line:'
printf ' %q' "${cmd[@]}"
printf '\n'

exec "${cmd[@]}"
