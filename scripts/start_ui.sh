#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export GRADIO_ANALYTICS_ENABLED="${GRADIO_ANALYTICS_ENABLED:-False}"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"

exec python -m app.main
