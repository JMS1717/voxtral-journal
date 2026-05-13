#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "Stopping Voxtral journal stack."
pkill -f "[v]llm serve" || true
pkill -f "[m]istralai/Voxtral-Mini-3B-2507" || true
pkill -f "[p]ython -m app.main" || true

echo "Remaining matching processes, if any:"
pgrep -af "vllm|Voxtral|mistralai|app.main" || true
echo "Stop command finished. Logs and data were not deleted."
