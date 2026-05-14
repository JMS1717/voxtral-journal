from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.history import upsert_history_entry


@dataclass
class TranscriptArtifacts:
    session_id: str
    final_markdown: Path
    transcript_json: Path
    raw_merged_markdown: Path
    chunks_zip: Path | None
    final_text: str
    raw_merged_text: str
    chunk_transcripts: list[Path]
    normalized_wav: Path
    chunk_audio_files: list[Path]


class OutputWriter:
    def __init__(self, final_dir: Path, raw_dir: Path) -> None:
        self.final_dir = final_dir
        self.raw_dir = raw_dir
        self.final_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def write_chunk_transcript(self, session_id: str, index: int, text: str) -> Path:
        chunk_dir = self.raw_dir / session_id
        chunk_dir.mkdir(parents=True, exist_ok=True)
        path = chunk_dir / f"chunk_{index:03d}.md"
        path.write_text(text.strip() + "\n", encoding="utf-8")
        return path

    def write_outputs(
        self,
        session_id: str,
        final_text: str,
        raw_merged_text: str,
        metadata: dict[str, Any],
        normalized_wav: Path,
        chunk_audio_files: list[Path] | None = None,
        chunk_transcripts: list[Path] | None = None,
    ) -> TranscriptArtifacts:
        session_dir = self.final_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        chunk_audio_files = chunk_audio_files or []
        chunk_transcripts = chunk_transcripts or []

        output_stem = _output_stem(metadata)
        final_markdown = session_dir / f"{output_stem}.md"
        raw_merged_markdown = session_dir / f"{output_stem}_raw.md"
        transcript_json = session_dir / f"{output_stem}.json"
        chunks_zip = session_dir / f"{output_stem}_chunks.zip" if chunk_audio_files or chunk_transcripts else None

        final_markdown.write_text(final_text.strip() + "\n", encoding="utf-8")
        raw_merged_markdown.write_text(raw_merged_text.strip() + "\n", encoding="utf-8")
        created_at = datetime.now().isoformat(timespec="seconds")
        chunk_statuses = _chunk_statuses(chunk_audio_files, chunk_transcripts)

        payload = {
            "metadata": {
                **metadata,
                "created_at": created_at,
                "normalized_wav": str(normalized_wav),
                "chunk_audio_files": [str(path) for path in chunk_audio_files],
                "chunk_transcripts": [str(path) for path in chunk_transcripts],
                "status": "completed",
            },
            "chunks": chunk_statuses,
            "raw_merged_transcript": raw_merged_text,
            "final_journal_transcript": final_text,
        }
        transcript_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        if chunks_zip is not None:
            with zipfile.ZipFile(chunks_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in chunk_audio_files:
                    zf.write(path, arcname=f"audio/{path.name}")
                for path in chunk_transcripts:
                    zf.write(path, arcname=f"transcripts/{path.name}")

        upsert_history_entry(
            self.final_dir.parent,
            {
                "job_id": session_id,
                "created_at": created_at,
                "source_filename": Path(str(metadata.get("source_file") or "")).name,
                "audio_duration_seconds": metadata.get("audio_duration_seconds"),
                "mode": metadata.get("mode"),
                "status": "completed",
                "final_markdown_path": str(final_markdown),
                "json_path": str(transcript_json),
                "raw_merged_path": str(raw_merged_markdown),
                "chunks_zip_path": str(chunks_zip) if chunks_zip else None,
                "error": None,
            },
        )

        return TranscriptArtifacts(
            session_id=session_id,
            final_markdown=final_markdown,
            transcript_json=transcript_json,
            raw_merged_markdown=raw_merged_markdown,
            chunks_zip=chunks_zip,
            final_text=final_text,
            raw_merged_text=raw_merged_text,
            chunk_transcripts=chunk_transcripts,
            normalized_wav=normalized_wav,
            chunk_audio_files=chunk_audio_files,
        )


def artifact_paths_for_gradio(artifacts: TranscriptArtifacts) -> tuple[str, str, str, str | None]:
    return (
        str(artifacts.final_markdown),
        str(artifacts.transcript_json),
        str(artifacts.raw_merged_markdown),
        str(artifacts.chunks_zip) if artifacts.chunks_zip else None,
    )


def _output_stem(metadata: dict[str, Any]) -> str:
    source_name = Path(str(metadata.get("source_file") or metadata.get("uploaded_file") or "transcript")).stem
    safe_name = "".join("_" if ch in '<>:"/\\|?*' or ord(ch) < 32 else ch for ch in source_name)
    return safe_name.strip(" ._") or "transcript"


def _chunk_statuses(chunk_audio_files: list[Path], chunk_transcripts: list[Path]) -> list[dict[str, Any]]:
    count = max(len(chunk_audio_files), len(chunk_transcripts))
    statuses: list[dict[str, Any]] = []
    for index in range(count):
        chunk_path = chunk_audio_files[index] if index < len(chunk_audio_files) else None
        transcript_path = chunk_transcripts[index] if index < len(chunk_transcripts) else None
        statuses.append(
            {
                "index": index + 1,
                "chunk_path": str(chunk_path) if chunk_path else None,
                "status": "completed" if transcript_path else "pending",
                "transcript_path": str(transcript_path) if transcript_path else None,
                "error": None,
            }
        )
    return statuses
