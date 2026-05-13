from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


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

        final_markdown = session_dir / "final_journal_transcript.md"
        raw_merged_markdown = session_dir / "raw_merged_transcript.md"
        transcript_json = session_dir / "transcript.json"
        chunks_zip = session_dir / "chunks.zip" if chunk_audio_files or chunk_transcripts else None

        final_markdown.write_text(final_text.strip() + "\n", encoding="utf-8")
        raw_merged_markdown.write_text(raw_merged_text.strip() + "\n", encoding="utf-8")

        payload = {
            "metadata": {
                **metadata,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "normalized_wav": str(normalized_wav),
                "chunk_audio_files": [str(path) for path in chunk_audio_files],
                "chunk_transcripts": [str(path) for path in chunk_transcripts],
            },
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

