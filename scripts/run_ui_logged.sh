#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."
mkdir -p data/logs

export GRADIO_ANALYTICS_ENABLED=False
export HF_HUB_DISABLE_TELEMETRY=1

echo "Starting Gradio. Log: $(pwd)/data/logs/gradio.log"
exec bash scripts/start_ui.sh > data/logs/gradio.log 2>&1
