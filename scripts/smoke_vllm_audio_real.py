from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover - exercised when optional fallback is missing
    imageio_ffmpeg = None

from app.audio_utils import AudioProcessingError, run_subprocess
from app.config import Settings
from app.vllm_client import VLLMClientError, VoxtralVLLMClient


def resolve_ffmpeg(settings: Settings) -> str:
    if settings.ffmpeg_bin:
        return settings.ffmpeg_bin
    if imageio_ffmpeg is not None:
        return imageio_ffmpeg.get_ffmpeg_exe()
    return "ffmpeg"


def check_vllm(base_url: str, timeout_seconds: int = 10) -> None:
    models_url = f"{base_url.rstrip('/')}/models"
    try:
        response = httpx.get(models_url, timeout=timeout_seconds)
        response.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"vLLM is not reachable at {models_url}: {exc}") from exc


def extract_first_seconds(audio_file: Path, output_wav: Path, seconds: int, ffmpeg_bin: str) -> Path:
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_subprocess(
            [
                ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-i",
                str(audio_file),
                "-t",
                str(seconds),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_wav),
            ],
            timeout=max(120, seconds + 120),
        )
    except AudioProcessingError as exc:
        raise RuntimeError(f"Could not extract {seconds}s smoke WAV with ffmpeg: {exc}") from exc
    return output_wav


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real Voxtral/vLLM 30-second audio smoke test.")
    parser.add_argument("audio_file", type=Path)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    if not args.audio_file.exists():
        print(f"Audio file does not exist: {args.audio_file}", file=sys.stderr)
        return 2
    if args.seconds <= 0:
        print("--seconds must be greater than 0", file=sys.stderr)
        return 2

    settings = Settings()
    settings.ensure_dirs()
    smoke_dir = settings.data_dir / "smoke"
    smoke_wav = smoke_dir / f"smoke_{args.seconds}s.wav"
    transcript_path = smoke_dir / "smoke_vllm_transcript.txt"

    try:
        print(f"Checking vLLM at {settings.vllm_base_url}/models")
        check_vllm(settings.vllm_base_url)
        ffmpeg_bin = resolve_ffmpeg(settings)
        print(f"Extracting first {args.seconds}s with ffmpeg: {ffmpeg_bin}")
        extract_first_seconds(args.audio_file, smoke_wav, args.seconds, ffmpeg_bin)
        print(f"Sending smoke WAV to Voxtral: {smoke_wav}")
        transcript = VoxtralVLLMClient(settings).transcribe_audio(smoke_wav, language=args.language)
    except ImportError as exc:
        print(f"Missing Python dependency for Voxtral audio requests: {exc}", file=sys.stderr)
        return 1
    except (RuntimeError, VLLMClientError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    smoke_dir.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(transcript.strip() + "\n", encoding="utf-8")
    print("\n--- Transcript ---")
    print(transcript.strip())
    print(f"\nSaved transcript: {transcript_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
