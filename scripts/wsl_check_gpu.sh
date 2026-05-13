#!/usr/bin/env bash
set -euo pipefail

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi was not found inside WSL. Install/update the Windows NVIDIA driver with WSL CUDA support." >&2
  exit 1
fi

nvidia-smi

