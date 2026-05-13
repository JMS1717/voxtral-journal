#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec vllm serve mistralai/Voxtral-Mini-3B-2507 \
  --host 0.0.0.0 \
  --port 8000 \
  --tokenizer_mode mistral \
  --config_format mistral \
  --load_format mistral \
  --gpu-memory-utilization 0.90 \
  --max-model-len "${VLLM_MAX_MODEL_LEN:-32768}" \
  ${VLLM_EXTRA_ARGS:-}
