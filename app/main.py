from __future__ import annotations

import logging
from pathlib import Path

import gradio as gr

from app.config import settings
from app.output_writer import artifact_paths_for_gradio
from app.prompts import current_journal_datetime
from app.transcriber import JournalTranscriber, ProcessingMode


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
    except Exception as exc:
        logging.exception("Transcription failed")
        raise gr.Error(str(exc)) from exc


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Voxtral Journal Windows") as demo:
        gr.Markdown("# Voxtral Journal Windows")
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
                    value=ProcessingMode.FULL_FILE_FIRST.value,
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

        run.click(
            fn=transcribe_ui,
            inputs=[audio, journal_datetime, language, mode, chunk_length, overlap],
            outputs=[final_text, final_md, transcript_json, raw_md, chunks_zip, status],
        )
        use_current_time.click(fn=current_journal_datetime, outputs=journal_datetime)
        demo.load(fn=current_journal_datetime, outputs=journal_datetime)
    return demo


if __name__ == "__main__":
    configure_logging()
    app = build_demo()
    app.queue(default_concurrency_limit=1)
    app.launch(server_name=settings.gradio_host, server_port=settings.gradio_port)
