from __future__ import annotations

import argparse
from pathlib import Path

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

from app.config import Settings
from app.transcriber import JournalTranscriber, ProcessingMode


class FakeVoxtralClient:
    def chat_with_audio(self, audio_path: Path, prompt: str, max_tokens: int = 8192) -> str:
        return f"Smoke transcript for {audio_path.name}."

    def transcribe_audio(self, audio_path: Path, language: str = "en") -> str:
        return f"Smoke raw transcript for {audio_path.name}."

    def chat_text(self, prompt: str, max_tokens: int = 8192) -> str:
        return "Date: Smoke Test\nSubject: The audio pipeline completed successfully.\n\nSmoke polished transcript."


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local audio pipeline without a live vLLM server.")
    parser.add_argument("audio_file", type=Path)
    parser.add_argument("--chunk-seconds", type=int, default=300)
    parser.add_argument("--overlap-seconds", type=int, default=30)
    args = parser.parse_args()

    ffmpeg_bin = "ffmpeg"
    ffprobe_bin = "ffprobe"
    if imageio_ffmpeg is not None:
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe_bin = "__missing_ffprobe_for_fallback_test__"

    settings = Settings(ffmpeg_bin=ffmpeg_bin, ffprobe_bin=ffprobe_bin)
    transcriber = JournalTranscriber(settings=settings, client=FakeVoxtralClient())
    artifacts = transcriber.process(
        args.audio_file,
        "Smoke Test",
        "en",
        ProcessingMode.ALWAYS_CHUNK,
        args.chunk_seconds,
        args.overlap_seconds,
        progress=lambda value, message: print(f"{value:.0%} {message}"),
    )

    print(f"session_id={artifacts.session_id}")
    print(f"normalized_wav={artifacts.normalized_wav}")
    print(f"chunks={len(artifacts.chunk_audio_files)}")
    print(f"chunk_transcripts={len(artifacts.chunk_transcripts)}")
    print(f"final_markdown={artifacts.final_markdown}")
    print(f"transcript_json={artifacts.transcript_json}")
    print(f"raw_merged_markdown={artifacts.raw_merged_markdown}")
    print(f"chunks_zip={artifacts.chunks_zip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

