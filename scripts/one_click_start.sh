#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."
mkdir -p data/logs

LOG="data/logs/one_click_start.log"
: > "$LOG"

status() {
  local line
  line="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$line"
  echo "$line" >> "$LOG"
}

wait_http() {
  local name="$1"
  local url="$2"
  local timeout_seconds="$3"
  local status_every_seconds="$4"
  local start now next_status
  start="$(date +%s)"
  next_status="$start"

  while true; do
    if curl --fail --silent --show-error --max-time 10 "$url" >/dev/null 2>&1; then
      status "$name is ready: $url"
      return 0
    fi

    now="$(date +%s)"
    if (( now - start >= timeout_seconds )); then
      return 1
    fi

    if (( now >= next_status )); then
      status "Waiting for $name at $url. Timeout in $((timeout_seconds - (now - start)))s."
      next_status=$((now + status_every_seconds))
    fi

    sleep 5
  done
}

status "Stopping stale vLLM and Gradio processes."
pkill -f "[v]llm serve" || true
pkill -f "[m]istralai/Voxtral-Mini-3B-2507" || true
pkill -f "[p]ython -m app.main" || true
sleep 3

status "Starting vLLM with VLLM_MAX_MODEL_LEN=${VLLM_MAX_MODEL_LEN:-16384}."
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-16384}" nohup bash scripts/run_vllm_logged.sh >/dev/null 2>&1 &

if ! wait_http "vLLM" "http://localhost:8000/v1/models" 1800 25; then
  status "vLLM failed to become ready. Tail of data/logs/vllm.log:"
  tail -n 120 data/logs/vllm.log || true
  exit 1
fi

status "Starting Gradio UI."
nohup bash scripts/run_ui_logged.sh > data/logs/gradio_launcher.log 2>&1 &

if ! wait_http "Gradio UI" "http://localhost:7860" 240 20; then
  status "Gradio failed to become ready. Tail of data/logs/gradio.log:"
  tail -n 120 data/logs/gradio.log || true
  exit 1
fi

status "Ready."
echo "UI: http://localhost:7860"
echo "vLLM: http://localhost:8000/v1/models"
echo "Logs:"
echo "  data/logs/vllm.log"
echo "  data/logs/vllm_launcher.log"
echo "  data/logs/gradio.log"
echo "  data/logs/one_click_start.log"
