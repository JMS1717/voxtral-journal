from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from app.audio_utils import (
    audio_duration_seconds,
    chunk_audio,
    normalize_audio,
    safe_stem,
    validate_audio_extension,
)
from app.config import Settings
from app.history import upsert_history_entry
from app.output_writer import OutputWriter, TranscriptArtifacts
from app.prompts import (
    build_chunk_transcription_prompt,
    build_full_file_audio_prompt,
    build_polish_from_cleaned_segments_prompt,
    build_polish_from_merged_prompt,
    build_segment_cleanup_prompt,
)
from app.token_budget import CleanupContextError, cleanup_token_budget, split_text_by_token_estimate
from app.vllm_client import VLLMClientError, VoxtralVLLMClient


LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[float, str], None]


class ProcessingMode(str, Enum):
    FULL_FILE_FIRST = "full-file first, fallback to chunks"
    ALWAYS_CHUNK = "always chunk"
    RAW_ONLY = "raw transcription only"
    POLISHED_FROM_RAW = "polished journal transcript"


class JournalTranscriber:
    def __init__(
        self,
        settings: Settings,
        client: VoxtralVLLMClient | None = None,
        writer: OutputWriter | None = None,
    ) -> None:
        self.settings = settings
        self.settings.ensure_dirs()
        self.client = client or VoxtralVLLMClient(settings)
        self.writer = writer or OutputWriter(settings.final_transcripts_dir, settings.raw_transcripts_dir)

    def process(
        self,
        input_path: Path,
        journal_datetime: str,
        language: str,
        mode: ProcessingMode,
        chunk_length_seconds: int,
        overlap_seconds: int,
        progress: ProgressCallback | None = None,
    ) -> TranscriptArtifacts:
        self._progress(progress, 0.02, "Preparing upload")
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        metadata = {
            "session_id": session_id,
            "source_file": str(input_path),
            "journal_datetime": journal_datetime,
            "language": language,
            "mode": mode.value,
            "chunk_length_seconds": chunk_length_seconds,
            "overlap_seconds": overlap_seconds,
            "model": self.settings.voxtral_model,
        }

        try:
            validate_audio_extension(input_path)
            upload_path = self.settings.uploads_dir / f"{session_id}_{safe_stem(input_path)}{input_path.suffix.lower()}"
            shutil.copy2(input_path, upload_path)
            metadata["uploaded_file"] = str(upload_path)

            self._progress(progress, 0.10, "Normalizing audio to mono 16 kHz WAV")
            normalized_wav = normalize_audio(
                upload_path,
                self.settings.normalized_dir / session_id,
                ffmpeg_bin=self.settings.ffmpeg_bin,
            )
            metadata["audio_duration_seconds"] = self._safe_audio_duration(normalized_wav)

            if mode == ProcessingMode.ALWAYS_CHUNK:
                return self._chunk_then_optionally_polish(
                    session_id,
                    normalized_wav,
                    journal_datetime,
                    language,
                    chunk_length_seconds,
                    overlap_seconds,
                    metadata,
                    raw_only=False,
                    progress=progress,
                )

            if mode == ProcessingMode.RAW_ONLY:
                return self._raw_full_file_with_chunk_fallback(
                    session_id,
                    normalized_wav,
                    language,
                    chunk_length_seconds,
                    overlap_seconds,
                    metadata,
                    progress=progress,
                )

            if mode == ProcessingMode.POLISHED_FROM_RAW:
                raw_artifacts = self._raw_full_file_with_chunk_fallback(
                    session_id,
                    normalized_wav,
                    language,
                    chunk_length_seconds,
                    overlap_seconds,
                    metadata,
                    progress=progress,
                    write_outputs=False,
                )
                self._progress(progress, 0.90, "Polishing merged transcript with global context")
                final_text = self._polish_with_context_budget(
                    session_id,
                    raw_artifacts.raw_merged_text,
                    journal_datetime,
                    language,
                    progress=progress,
                )
                return self.writer.write_outputs(
                    session_id,
                    final_text,
                    raw_artifacts.raw_merged_text,
                    {**metadata, "chunked": bool(raw_artifacts.chunk_audio_files)},
                    normalized_wav,
                    raw_artifacts.chunk_audio_files,
                    raw_artifacts.chunk_transcripts,
                )

            return self._full_file_first(
                session_id,
                normalized_wav,
                journal_datetime,
                language,
                chunk_length_seconds,
                overlap_seconds,
                metadata,
                progress,
            )
        except Exception as exc:
            self._record_failed_history(metadata, str(exc))
            raise

    def _full_file_first(
        self,
        session_id: str,
        normalized_wav: Path,
        journal_datetime: str,
        language: str,
        chunk_length_seconds: int,
        overlap_seconds: int,
        metadata: dict[str, object],
        progress: ProgressCallback | None,
    ) -> TranscriptArtifacts:
        try:
            self._progress(progress, 0.35, "Trying full-file journal transcription")
            final_text = self.client.chat_with_audio(
                normalized_wav,
                build_full_file_audio_prompt(journal_datetime, language),
            )
            self._progress(progress, 0.95, "Writing transcript files")
            return self.writer.write_outputs(
                session_id,
                final_text,
                final_text,
                {**metadata, "chunked": False, "full_file_first_succeeded": True},
                normalized_wav,
            )
        except VLLMClientError as exc:
            LOGGER.warning("Full-file audio chat failed, falling back to chunks: %s", exc)
            self._progress(progress, 0.42, "Full-file request failed; falling back to chunks")
            return self._chunk_then_optionally_polish(
                session_id,
                normalized_wav,
                journal_datetime,
                language,
                chunk_length_seconds,
                overlap_seconds,
                {**metadata, "full_file_error": str(exc)},
                raw_only=False,
                progress=progress,
            )

    def _raw_full_file_with_chunk_fallback(
        self,
        session_id: str,
        normalized_wav: Path,
        language: str,
        chunk_length_seconds: int,
        overlap_seconds: int,
        metadata: dict[str, object],
        progress: ProgressCallback | None,
        write_outputs: bool = True,
    ) -> TranscriptArtifacts:
        try:
            self._progress(progress, 0.35, "Trying full-file raw transcription")
            raw_text = self.client.transcribe_audio(normalized_wav, language=language)
            if write_outputs:
                return self.writer.write_outputs(
                    session_id,
                    raw_text,
                    raw_text,
                    {**metadata, "chunked": False, "raw_only": True},
                    normalized_wav,
                )
            return TranscriptArtifacts(
                session_id=session_id,
                final_markdown=Path(),
                transcript_json=Path(),
                raw_merged_markdown=Path(),
                chunks_zip=None,
                final_text=raw_text,
                raw_merged_text=raw_text,
                chunk_transcripts=[],
                normalized_wav=normalized_wav,
                chunk_audio_files=[],
            )
        except VLLMClientError as exc:
            LOGGER.warning("Full-file raw transcription failed, falling back to chunks: %s", exc)
            return self._chunk_then_optionally_polish(
                session_id,
                normalized_wav,
                "",
                language,
                chunk_length_seconds,
                overlap_seconds,
                {**metadata, "full_file_error": str(exc)},
                raw_only=True,
                progress=progress,
                write_outputs=write_outputs,
            )

    def _chunk_then_optionally_polish(
        self,
        session_id: str,
        normalized_wav: Path,
        journal_datetime: str,
        language: str,
        chunk_length_seconds: int,
        overlap_seconds: int,
        metadata: dict[str, object],
        raw_only: bool,
        progress: ProgressCallback | None,
        write_outputs: bool = True,
    ) -> TranscriptArtifacts:
        self._progress(progress, 0.45, "Creating overlapped audio chunks")
        chunk_dir = self.settings.chunks_dir / session_id
        chunk_paths = chunk_audio(
            normalized_wav,
            chunk_dir,
            chunk_length_seconds=chunk_length_seconds,
            overlap_seconds=overlap_seconds,
            ffmpeg_bin=self.settings.ffmpeg_bin,
            ffprobe_bin=self.settings.ffprobe_bin,
        )
        if not chunk_paths:
            raise RuntimeError("No chunks were created from the normalized audio.")

        chunk_transcripts: list[Path] = []
        raw_parts: list[str] = []
        chunk_prompt = build_chunk_transcription_prompt(language)
        for index, chunk_path in enumerate(chunk_paths, start=1):
            base = 0.50
            span = 0.30
            self._progress(
                progress,
                base + span * ((index - 1) / max(len(chunk_paths), 1)),
                f"Transcribing chunk {index} of {len(chunk_paths)}",
            )
            text = self.client.chat_with_audio(chunk_path, chunk_prompt, max_tokens=4096)
            raw_parts.append(f"## Chunk {index:03d}\n\n{text.strip()}")
            chunk_transcripts.append(self.writer.write_chunk_transcript(session_id, index, text))

        raw_merged_text = "\n\n".join(raw_parts).strip()
        if raw_only:
            final_text = raw_merged_text
        else:
            self._progress(progress, 0.86, "Polishing merged transcript with global context")
            final_text = self._polish_with_context_budget(
                session_id,
                raw_merged_text,
                journal_datetime,
                language,
                progress=progress,
            )

        if not write_outputs:
            return TranscriptArtifacts(
                session_id=session_id,
                final_markdown=Path(),
                transcript_json=Path(),
                raw_merged_markdown=Path(),
                chunks_zip=None,
                final_text=final_text,
                raw_merged_text=raw_merged_text,
                chunk_transcripts=chunk_transcripts,
                normalized_wav=normalized_wav,
                chunk_audio_files=chunk_paths,
            )

        self._progress(progress, 0.95, "Writing transcript files")
        return self.writer.write_outputs(
            session_id,
            final_text,
            raw_merged_text,
            {**metadata, "chunked": True, "raw_only": raw_only},
            normalized_wav,
            chunk_paths,
            chunk_transcripts,
        )

    @staticmethod
    def _progress(progress: ProgressCallback | None, value: float, message: str) -> None:
        LOGGER.info(message)
        if progress:
            progress(value, message)

    def _safe_audio_duration(self, audio_path: Path) -> float | None:
        try:
            return audio_duration_seconds(
                audio_path,
                ffprobe_bin=self.settings.ffprobe_bin,
                ffmpeg_bin=self.settings.ffmpeg_bin,
            )
        except Exception as exc:
            LOGGER.warning("Could not read audio duration for history metadata: %s", exc)
            return None

    def _record_failed_history(self, metadata: dict[str, object], error: str) -> None:
        try:
            upsert_history_entry(
                self.settings.data_dir,
                {
                    "job_id": metadata.get("session_id"),
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "source_filename": Path(str(metadata.get("source_file") or "")).name,
                    "audio_duration_seconds": metadata.get("audio_duration_seconds"),
                    "mode": metadata.get("mode"),
                    "status": "failed",
                    "final_markdown_path": None,
                    "json_path": None,
                    "raw_merged_path": None,
                    "chunks_zip_path": None,
                    "error": error,
                },
            )
        except Exception:
            LOGGER.exception("Failed to update history index for failed job")

    def _polish_with_context_budget(
        self,
        session_id: str,
        raw_merged_text: str,
        journal_datetime: str,
        language: str,
        progress: ProgressCallback | None,
    ) -> str:
        prompt = build_polish_from_merged_prompt(raw_merged_text, journal_datetime, language)
        try:
            return self._chat_text_with_cleanup_budget(prompt)
        except CleanupContextError:
            self._progress(progress, 0.88, "Transcript is long; using hierarchical cleanup")
            return self._hierarchical_cleanup(
                session_id,
                raw_merged_text,
                journal_datetime,
                language,
            )

    def _hierarchical_cleanup(
        self,
        session_id: str,
        raw_merged_text: str,
        journal_datetime: str,
        language: str,
    ) -> str:
        segments = split_text_by_token_estimate(raw_merged_text, self.settings.long_transcript_chunk_tokens)
        if not segments:
            raise CleanupContextError(
                "The transcript is too long for the current context profile. "
                "The app tried hierarchical cleanup. If this still fails, use Balanced 16k or shorter chunks."
            )

        intermediate_dir = self.settings.final_transcripts_dir / session_id / "hierarchical_cleanup_segments"
        intermediate_dir.mkdir(parents=True, exist_ok=True)

        cleaned_segments: list[str] = []
        total_segments = len(segments)
        for index, segment in enumerate(segments, start=1):
            prompt = build_segment_cleanup_prompt(segment, index, total_segments, language)
            cleaned = self._chat_text_with_cleanup_budget(prompt)
            cleaned_segments.append(f"## Cleaned segment {index:03d}\n\n{cleaned.strip()}")
            (intermediate_dir / f"segment_{index:03d}.md").write_text(cleaned.strip() + "\n", encoding="utf-8")

        combined = "\n\n".join(cleaned_segments)
        final_prompt = build_polish_from_cleaned_segments_prompt(combined, journal_datetime, language)
        return self._chat_text_with_cleanup_budget(final_prompt)

    def _chat_text_with_cleanup_budget(self, prompt: str) -> str:
        budget = cleanup_token_budget(
            prompt,
            context_window=self.settings.vllm_context_window,
            cleanup_max_output_tokens=self.settings.cleanup_max_output_tokens,
            safety_margin=self.settings.cleanup_token_safety_margin,
            cleanup_min_output_tokens=self.settings.cleanup_min_output_tokens,
        )
        LOGGER.info(
            "Cleanup token budget: context_window=%s estimated_input_tokens=%s "
            "requested_output_tokens=%s safety_margin=%s",
            budget.context_window,
            budget.estimated_input_tokens,
            budget.requested_output_tokens,
            budget.safety_margin,
        )
        return self.client.chat_text(prompt, max_tokens=budget.requested_output_tokens)
