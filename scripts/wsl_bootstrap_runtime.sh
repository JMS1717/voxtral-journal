#!/usr/bin/env bash
set -euo pipefail

RUNTIME_DIR="${HOME}/apps/voxtral-journal-windows"

if [[ "$(pwd -P)" != "${RUNTIME_DIR}" ]]; then
  echo "This script must run from ${RUNTIME_DIR}."
  echo "Current directory: $(pwd -P)"
  exit 1
fi

if [[ ! -f "requirements.txt" ]]; then
  echo "requirements.txt is missing in $(pwd -P)."
  exit 1
fi

mkdir -p data/logs

if ! command -v uv >/dev/null 2>&1; then
  if command -v curl >/dev/null 2>&1; then
    echo "uv is missing. Installing uv in user space."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
  else
    echo "uv is missing and curl is not installed."
    echo "Install uv, then rerun:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv installation did not put uv on PATH."
  echo "Add ~/.local/bin or ~/.cargo/bin to PATH, then rerun this script."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "Creating runtime virtual environment with uv."
  uv venv .venv
fi

echo "Installing project requirements."
uv pip install --python .venv/bin/python -r requirements.txt

echo "Installing runtime ML packages."
uv pip install --python .venv/bin/python "vllm[audio]" imageio-ffmpeg huggingface_hub

echo "Verifying runtime imports."
.venv/bin/python -c "import torch, vllm, mistral_common; print(vllm.__version__); print(torch.cuda.is_available())"

sha256sum requirements.txt | awk '{print $1}' > .runtime_requirements.sha256
date -Is > .runtime_ready

echo "Runtime bootstrap complete: $(pwd -P)/.runtime_ready"
