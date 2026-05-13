PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: setup check-gpu start-vllm start-ui smoke-vllm test clean

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	mkdir -p data/uploads data/normalized data/chunks data/raw_transcripts data/final_transcripts data/logs

check-gpu:
	bash scripts/wsl_check_gpu.sh

start-vllm:
	bash scripts/start_vllm_mini3b.sh

start-ui:
	bash scripts/start_ui.sh

smoke-vllm:
	test -n "$(AUDIO)" || (echo 'Usage: make smoke-vllm AUDIO="/path/to/audio.m4a"' && exit 2)
	$(PY) scripts/smoke_vllm_audio_real.py "$(AUDIO)"

test:
	$(PY) -m pytest

clean:
	find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".ruff_cache" \) -prune -exec rm -rf {} +
