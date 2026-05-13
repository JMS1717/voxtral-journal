#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${VLLM_BASE_URL:-http://localhost:8000/v1}"
curl --fail --show-error --silent "${BASE_URL}/models" | python3 -m json.tool

