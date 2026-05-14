from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import gradio as gr

from app.config import settings
from app.diagnostics import diagnostics_snapshot
from app.history import load_history_entries
from app.output_writer import artifact_paths_for_gradio
from app.prompts import current_journal_datetime
from app.token_budget import CleanupContextError
from app.transcriber import JournalTranscriber, ProcessingMode


logger = logging.getLogger(__name__)

HISTORY_HEADERS = [
    "created_at",
    "file",
    "duration",
    "mode",
    "status",
    "job_id",
]
EMPTY_HISTORY_TEXT = "No history loaded. Click Refresh history."
EMPTY_HISTORY_DETAILS = "Select a history job to show download details."
EMPTY_DIAGNOSTICS_TEXT = "No diagnostics loaded. Click Refresh diagnostics."


def configure_logging() -> None:
    settings.ensure_dirs()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(settings.logs_dir / "webui.log", encoding="utf-8"),
        ],
    )


def transcribe_ui(
    audio_files: str | list[str],
    journal_datetime: str,
    language: str,
    mode_value: str,
    chunk_length_seconds: int,
    overlap_seconds: int,
    progress: gr.Progress = gr.Progress(track_tqdm=False),
):
    input_paths = _audio_file_paths(audio_files)
    if not input_paths:
        raise gr.Error("Upload one or more audio files first.")

    mode = ProcessingMode(mode_value)
    transcriber = JournalTranscriber(settings)
    results: list[tuple[Path, object]] = []
    failures: list[tuple[Path, str]] = []

    total = len(input_paths)
    for index, input_path in enumerate(input_paths):
        file_number = index + 1
        progress(index / total, desc=f"Starting {file_number}/{total}: {input_path.name}")
        try:
            artifacts = transcriber.process(
                input_path,
                journal_datetime.strip() or current_journal_datetime(),
                (language or settings.default_language).strip(),
                mode,
                int(chunk_length_seconds),
                int(overlap_seconds),
                progress=lambda value, message, idx=index, path=input_path: progress(
                    (idx + value) / total,
                    desc=f"{idx + 1}/{total} {path.name}: {message}",
                ),
            )
            results.append((input_path, artifacts))
        except CleanupContextError as exc:
            logger.exception("Cleanup failed due to context limits for %s", input_path)
            failures.append((input_path, str(exc)))
            if total == 1:
                raise gr.Error(str(exc)) from exc
        except Exception as exc:
            logger.exception("Transcription failed for %s", input_path)
            failures.append((input_path, str(exc)))
            if total == 1:
                raise gr.Error(str(exc)) from exc

    progress(1.0, desc="Batch complete" if total > 1 else "Done")
    if not results:
        failure_text = "\n".join(f"- {path.name}: {error}" for path, error in failures)
        raise gr.Error(f"All files failed.\n{failure_text}")

    latest_input, latest_artifacts = results[-1]
    final_md, transcript_json, raw_md, chunks_zip = artifact_paths_for_gradio(latest_artifacts)
    status = _batch_status_text(results, failures, latest_input)
    return latest_artifacts.final_text, final_md, transcript_json, raw_md, chunks_zip, status


def _audio_file_paths(audio_files: str | list[str]) -> list[Path]:
    if not audio_files:
        return []
    if isinstance(audio_files, (str, Path)):
        return [Path(audio_files)]
    return [Path(path) for path in audio_files if path]


def _batch_status_text(results: list[tuple[Path, object]], failures: list[tuple[Path, str]], latest_input: Path) -> str:
    total = len(results) + len(failures)
    lines = [
        f"Batch complete: {len(results)} succeeded, {len(failures)} failed, {total} total.",
        f"Download widgets show latest successful job: {latest_input.name}",
        "",
    ]
    for index, (path, artifacts) in enumerate(results, start=1):
        session_id = getattr(artifacts, "session_id", "")
        lines.append(f"{index}. completed: {path.name} -> {session_id}")
    for path, error in failures:
        lines.append(f"- failed: {path.name} -> {error}")
    return "\n".join(lines)


def refresh_history_tab():
    logger.info(
        "History refresh requested: data_dir=%s final_transcripts_dir=%s",
        settings.data_dir,
        settings.final_transcripts_dir,
    )
    try:
        entries = load_history_entries(settings.data_dir, settings.final_transcripts_dir, limit=50)
    except Exception:
        logger.exception("Failed to load history")
        entries = []
    job_ids = [entry["job_id"] for entry in entries if entry.get("job_id")]
    logger.info("History refresh loaded %d entries with %d downloadable job ids", len(entries), len(job_ids))
    return (
        history_text_value(entries),
        gr.update(choices=job_ids, value=None),
        None,
        None,
        EMPTY_HISTORY_DETAILS,
    )


def history_downloads_for_job(job_id: str | None):
    logger.info("History download selection changed: job_id=%s", job_id)
    if not job_id:
        logger.info("History download selection cleared")
        return None, None, EMPTY_HISTORY_DETAILS
    try:
        entries = load_history_entries(settings.data_dir, settings.final_transcripts_dir, limit=None)
    except Exception:
        logger.exception("Failed to load history downloads")
        return None, None
    for entry in entries:
        if entry.get("job_id") == job_id:
            paths = (
                _history_artifact_file(entry, "final_markdown_path", "final_journal_transcript.md"),
                _history_artifact_file(entry, "json_path", "transcript.json"),
            )
            logger.info("History download paths for %s: final=%s json=%s", job_id, paths[0], paths[1])
            return paths[0], paths[1], _history_details_text(entry, paths[0], paths[1])
    logger.warning("History job id not found for download: %s", job_id)
    return None, None, f"History job not found: {job_id}"


def refresh_diagnostics_tab():
    return diagnostics_snapshot(settings)


def refresh_diagnostics_section():
    health_text, models_text, vllm_tail, gradio_tail = refresh_diagnostics_tab()
    return "\n\n".join(
        [
            "vLLM health",
            health_text,
            "Model ids from /v1/models",
            models_text,
            "Last 80 lines of data/logs/vllm.log",
            vllm_tail,
            "Last 80 lines of data/logs/gradio.log",
            gradio_tail,
        ]
    )


def history_text_value(entries):
    logger.info("History text returning %d rows", len(entries))
    if not entries:
        return "No history entries found."
    lines = [" | ".join(HISTORY_HEADERS)]
    lines.append(" | ".join("-" * len(header) for header in HISTORY_HEADERS))
    for entry in entries:
        lines.append(" | ".join(_history_cell_text(value) for value in _compact_history_row(entry)))
    return "\n".join(lines)


def _compact_history_row(entry: dict) -> list[object]:
    return [
        entry.get("created_at") or "",
        entry.get("source_filename") or "",
        _duration_text(entry.get("audio_duration_seconds")),
        entry.get("mode") or "",
        entry.get("status") or "",
        entry.get("job_id") or "",
    ]


def _duration_text(value: object) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):.1f}s"
    except (TypeError, ValueError):
        return str(value)


def _history_details_text(entry: dict, final_path: str | None, json_path: str | None) -> str:
    return "\n".join(
        [
            f"Job: {entry.get('job_id') or ''}",
            f"Created: {entry.get('created_at') or ''}",
            f"File: {entry.get('source_filename') or ''}",
            f"Duration: {_duration_text(entry.get('audio_duration_seconds'))}",
            f"Mode: {entry.get('mode') or ''}",
            f"Status: {entry.get('status') or ''}",
            f"Final markdown: {final_path or 'not available'}",
            f"Transcript JSON: {json_path or 'not available'}",
        ]
    )


def _history_cell_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("\r", " ")


def _history_artifact_file(entry: dict, key: str, filename: str) -> str | None:
    job_id = entry.get("job_id")
    if job_id:
        runtime_path = settings.final_transcripts_dir / str(job_id) / filename
        logger.info(
            "History artifact runtime candidate: job_id=%s key=%s path=%s exists=%s",
            job_id,
            key,
            runtime_path,
            runtime_path.exists(),
        )
        if runtime_path.exists():
            return str(runtime_path)
    logger.info("History artifact falling back to stored path: key=%s value=%s", key, entry.get(key))
    return _existing_file(entry.get(key))


def _existing_file(value: object) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    if not path.exists():
        logger.info("History file does not exist: %s", path)
        return None
    try:
        resolved = path.resolve()
    except OSError:
        return None
    allowed_roots = [settings.project_root.resolve(), Path(tempfile.gettempdir()).resolve()]
    if any(resolved.is_relative_to(root) for root in allowed_roots):
        return str(resolved)
    logger.warning("Ignoring history file outside Gradio allowed paths: %s", resolved)
    return None


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Voxtral Mini Audio Journal") as demo:
        gr.Markdown("# Voxtral Mini Personal Audio Journal")
        gr.Markdown("## Transcribe")
        with gr.Row():
            with gr.Column(scale=1):
                audio = gr.File(
                    label="Audio journal files",
                    file_types=[".mp3", ".wav", ".m4a", ".mp4", ".webm", ".aac", ".flac"],
                    file_count="multiple",
                    type="filepath",
                )
                with gr.Row():
                    journal_datetime = gr.Textbox(
                        label="Journal date/time",
                        value=current_journal_datetime(),
                    )
                    use_current_time = gr.Button("Use current time", variant="secondary")
                language = gr.Textbox(label="Language", value=settings.default_language)
                mode = gr.Dropdown(
                    label="Processing mode",
                    choices=[mode.value for mode in ProcessingMode],
                    value=ProcessingMode.ALWAYS_CHUNK.value,
                )
                with gr.Row():
                    chunk_length = gr.Number(
                        label="Chunk length seconds",
                        value=settings.default_chunk_seconds,
                        precision=0,
                    )
                    overlap = gr.Number(
                        label="Overlap seconds",
                        value=settings.default_overlap_seconds,
                        precision=0,
                    )
                run = gr.Button("Transcribe", variant="primary")
            with gr.Column(scale=2):
                final_text = gr.Textbox(
                    label="Latest final polished transcript",
                    lines=26,
                    max_lines=42,
                )
                status = gr.Textbox(label="Status", interactive=False)
                with gr.Row():
                    final_md = gr.File(label="final_journal_transcript.md")
                    transcript_json = gr.File(label="transcript.json")
                with gr.Row():
                    raw_md = gr.File(label="raw_merged_transcript.md")
                    chunks_zip = gr.File(label="chunks.zip")

        gr.Markdown("## History")
        gr.Markdown("Recent completed and failed jobs from `data/history/index.json` and existing transcript artifacts.")
        history_refresh = gr.Button("Refresh history", variant="secondary")
        history_table = gr.Textbox(
            label="History",
            value=EMPTY_HISTORY_TEXT,
            lines=12,
            max_lines=24,
            interactive=False,
        )
        history_job = gr.Dropdown(label="Job downloads", choices=[], interactive=True)
        history_details = gr.Textbox(
            label="Selected job details",
            value=EMPTY_HISTORY_DETAILS,
            lines=8,
            max_lines=12,
            interactive=False,
        )
        with gr.Row():
            history_final_md = gr.File(label="Selected final markdown")
            history_json = gr.File(label="Selected transcript JSON")

        gr.Markdown("## Diagnostics")
        diagnostics_refresh = gr.Button("Refresh diagnostics", variant="secondary")
        diagnostics_text = gr.Textbox(
            label="Diagnostics",
            value=EMPTY_DIAGNOSTICS_TEXT,
            lines=24,
            max_lines=40,
            interactive=False,
        )

        run.click(
            fn=transcribe_ui,
            inputs=[audio, journal_datetime, language, mode, chunk_length, overlap],
            outputs=[final_text, final_md, transcript_json, raw_md, chunks_zip, status],
        )
        use_current_time.click(fn=current_journal_datetime, outputs=journal_datetime)
        demo.load(fn=current_journal_datetime, outputs=journal_datetime)
        history_refresh.click(
            fn=refresh_history_tab,
            outputs=[history_table, history_job, history_final_md, history_json, history_details],
        )
        history_job.change(
            fn=history_downloads_for_job,
            inputs=history_job,
            outputs=[history_final_md, history_json, history_details],
        )
        diagnostics_refresh.click(
            fn=refresh_diagnostics_section,
            outputs=diagnostics_text,
        )
    return demo


if __name__ == "__main__":
    configure_logging()
    app = build_demo()
    app.queue(default_concurrency_limit=1)
    app.launch(server_name=settings.gradio_host, server_port=settings.gradio_port)
