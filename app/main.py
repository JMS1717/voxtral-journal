from __future__ import annotations

import logging
from pathlib import Path

import gradio as gr

from app.config import settings
from app.diagnostics import diagnostics_snapshot
from app.history import history_rows, load_history_entries
from app.output_writer import artifact_paths_for_gradio
from app.prompts import current_journal_datetime
from app.token_budget import CleanupContextError
from app.transcriber import JournalTranscriber, ProcessingMode


HISTORY_HEADERS = [
    "created_at",
    "source filename",
    "duration seconds",
    "processing mode",
    "status",
    "final markdown path",
    "transcript JSON path",
    "job_id",
]


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
    audio_file: str,
    journal_datetime: str,
    language: str,
    mode_value: str,
    chunk_length_seconds: int,
    overlap_seconds: int,
    progress: gr.Progress = gr.Progress(track_tqdm=False),
):
    if not audio_file:
        raise gr.Error("Upload an audio file first.")
    try:
        mode = ProcessingMode(mode_value)
        transcriber = JournalTranscriber(settings)
        artifacts = transcriber.process(
            Path(audio_file),
            journal_datetime.strip() or current_journal_datetime(),
            (language or settings.default_language).strip(),
            mode,
            int(chunk_length_seconds),
            int(overlap_seconds),
            progress=lambda value, message: progress(value, desc=message),
        )
        final_md, transcript_json, raw_md, chunks_zip = artifact_paths_for_gradio(artifacts)
        status = f"Done. Session: {artifacts.session_id}"
        return artifacts.final_text, final_md, transcript_json, raw_md, chunks_zip, status
    except CleanupContextError as exc:
        logging.exception("Cleanup failed due to context limits")
        raise gr.Error(str(exc)) from exc
    except Exception as exc:
        logging.exception("Transcription failed")
        raise gr.Error(str(exc)) from exc


def refresh_history_tab():
    entries = load_history_entries(settings.data_dir, settings.final_transcripts_dir, limit=50)
    job_ids = [entry["job_id"] for entry in entries if entry.get("job_id")]
    selected_job_id = job_ids[0] if job_ids else None
    final_path, json_path = history_downloads_for_job(selected_job_id)
    return (
        history_rows(entries),
        gr.update(choices=job_ids, value=selected_job_id),
        final_path,
        json_path,
    )


def history_downloads_for_job(job_id: str | None):
    if not job_id:
        return None, None
    entries = load_history_entries(settings.data_dir, settings.final_transcripts_dir, limit=None)
    for entry in entries:
        if entry.get("job_id") == job_id:
            return _existing_file(entry.get("final_markdown_path")), _existing_file(entry.get("json_path"))
    return None, None


def refresh_diagnostics_tab():
    return diagnostics_snapshot(settings)


def _existing_file(value: object) -> str | None:
    if not value:
        return None
    path = Path(str(value))
    return str(path) if path.exists() else None


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Voxtral Mini Audio Journal") as demo:
        gr.Markdown("# Voxtral Mini Personal Audio Journal")
        with gr.Tab("Transcribe"):
            with gr.Row():
                with gr.Column(scale=1):
                    audio = gr.File(
                        label="Audio journal file",
                        file_types=[".mp3", ".wav", ".m4a", ".mp4", ".webm", ".aac", ".flac"],
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
                        label="Final polished transcript",
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

        with gr.Tab("History"):
            gr.Markdown("Recent completed and failed jobs from `data/history/index.json` and existing transcript artifacts.")
            history_refresh = gr.Button("Refresh history", variant="secondary")
            history_table = gr.Dataframe(
                headers=HISTORY_HEADERS,
                value=[],
                interactive=False,
                wrap=True,
            )
            history_job = gr.Dropdown(label="Job downloads", choices=[], interactive=True)
            with gr.Row():
                history_final_md = gr.File(label="Selected final markdown")
                history_json = gr.File(label="Selected transcript JSON")

        with gr.Tab("Diagnostics"):
            gr.Markdown("Local service health and log tails. This does not read transcript contents.")
            diagnostics_refresh = gr.Button("Refresh diagnostics", variant="secondary")
            vllm_health = gr.Textbox(label="vLLM health check", interactive=False)
            vllm_models = gr.Textbox(label="Model ids from /v1/models", lines=3, interactive=False)
            vllm_log_tail = gr.Textbox(label="Last 80 lines of data/logs/vllm.log", lines=18, interactive=False)
            gradio_log_tail = gr.Textbox(label="Last 80 lines of data/logs/gradio.log", lines=18, interactive=False)

        run.click(
            fn=transcribe_ui,
            inputs=[audio, journal_datetime, language, mode, chunk_length, overlap],
            outputs=[final_text, final_md, transcript_json, raw_md, chunks_zip, status],
        )
        use_current_time.click(fn=current_journal_datetime, outputs=journal_datetime)
        demo.load(fn=current_journal_datetime, outputs=journal_datetime)
        history_refresh.click(
            fn=refresh_history_tab,
            outputs=[history_table, history_job, history_final_md, history_json],
        )
        history_job.change(
            fn=history_downloads_for_job,
            inputs=history_job,
            outputs=[history_final_md, history_json],
        )
        diagnostics_refresh.click(
            fn=refresh_diagnostics_tab,
            outputs=[vllm_health, vllm_models, vllm_log_tail, gradio_log_tail],
        )
    return demo


if __name__ == "__main__":
    configure_logging()
    app = build_demo()
    app.queue(default_concurrency_limit=1)
    app.launch(server_name=settings.gradio_host, server_port=settings.gradio_port)
