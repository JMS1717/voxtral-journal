from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".aac", ".flac"}


class AudioProcessingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChunkRange:
    index: int
    start_seconds: float
    duration_seconds: float

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.duration_seconds


def safe_stem(path: Path) -> str:
    stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in path.stem)
    return stem.strip("._") or "audio"


def validate_audio_extension(path: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise AudioProcessingError(f"Unsupported audio type '{path.suffix}'. Supported: {supported}.")


def require_binary(binary: str) -> None:
    if shutil.which(binary) is None:
        raise AudioProcessingError(f"Required executable '{binary}' was not found on PATH.")


def run_subprocess(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise AudioProcessingError(details) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioProcessingError(f"Command timed out after {timeout} seconds: {args[0]}") from exc


def audio_duration_seconds(path: Path, ffprobe_bin: str = "ffprobe", ffmpeg_bin: str = "ffmpeg") -> float:
    if shutil.which(ffprobe_bin):
        result = run_subprocess(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            timeout=60,
        )
        try:
            return float(result.stdout.strip())
        except ValueError as exc:
            raise AudioProcessingError(f"Could not read audio duration for {path}") from exc

    require_binary(ffmpeg_bin)
    result = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr + result.stdout)
    if not match:
        raise AudioProcessingError(f"Could not read audio duration for {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def normalize_audio(
    input_path: Path,
    output_dir: Path,
    ffmpeg_bin: str = "ffmpeg",
    sample_rate: int = 16000,
) -> Path:
    validate_audio_extension(input_path)
    require_binary(ffmpeg_bin)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{safe_stem(input_path)}_normalized.wav"
    run_subprocess(
        [
            ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        timeout=600,
    )
    return output_path


def compute_chunk_ranges(
    duration_seconds: float,
    chunk_length_seconds: int = 300,
    overlap_seconds: int = 30,
) -> list[ChunkRange]:
    if chunk_length_seconds <= 0:
        raise AudioProcessingError("Chunk length must be greater than 0 seconds.")
    if overlap_seconds < 0:
        raise AudioProcessingError("Overlap must be 0 seconds or greater.")
    if overlap_seconds >= chunk_length_seconds:
        raise AudioProcessingError("Overlap must be smaller than chunk length.")
    if duration_seconds <= 0:
        return []

    ranges: list[ChunkRange] = []
    step = chunk_length_seconds - overlap_seconds
    start = 0.0
    index = 1
    while start < duration_seconds:
        remaining = duration_seconds - start
        length = min(chunk_length_seconds, remaining)
        ranges.append(ChunkRange(index=index, start_seconds=start, duration_seconds=length))
        if math.isclose(start + length, duration_seconds) or start + length >= duration_seconds:
            break
        start += step
        index += 1
    return ranges


def chunk_audio(
    normalized_wav: Path,
    output_dir: Path,
    chunk_length_seconds: int = 300,
    overlap_seconds: int = 30,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
) -> list[Path]:
    require_binary(ffmpeg_bin)
    duration = audio_duration_seconds(normalized_wav, ffprobe_bin=ffprobe_bin, ffmpeg_bin=ffmpeg_bin)
    ranges = compute_chunk_ranges(duration, chunk_length_seconds, overlap_seconds)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_paths: list[Path] = []
    for chunk_range in ranges:
        chunk_path = output_dir / f"{safe_stem(normalized_wav)}_chunk_{chunk_range.index:03d}.wav"
        run_subprocess(
            [
                ffmpeg_bin,
                "-y",
                "-hide_banner",
                "-ss",
                f"{chunk_range.start_seconds:.3f}",
                "-t",
                f"{chunk_range.duration_seconds:.3f}",
                "-i",
                str(normalized_wav),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(chunk_path),
            ],
            timeout=600,
        )
        chunk_paths.append(chunk_path)
    return chunk_paths
