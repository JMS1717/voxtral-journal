#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: scripts/normalize_audio.sh input-audio [output-dir]" >&2
  exit 2
fi

INPUT="$1"
OUTPUT_DIR="${2:-data/normalized/manual}"
mkdir -p "$OUTPUT_DIR"
BASENAME="$(basename "${INPUT%.*}")"

ffmpeg -y -hide_banner -i "$INPUT" -vn -ac 1 -ar 16000 -c:a pcm_s16le "$OUTPUT_DIR/${BASENAME}_normalized.wav"

