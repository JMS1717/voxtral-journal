#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y \
  build-essential \
  curl \
  ffmpeg \
  git \
  python3-pip \
  python3-venv

if command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 found: $(python3.11 --version)"
elif python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  echo "python3 is 3.11+: $(python3 --version)"
else
  echo "Python 3.11+ was not found. Install python3.11/python3.11-venv for your Ubuntu release, then rerun make setup." >&2
  exit 1
fi

echo "System dependencies installed. Next: make setup"

