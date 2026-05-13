# AGENTS.md

## Project Goal

Build and maintain a local-first Windows 11 + WSL2 Ubuntu WebUI for personal audio journal transcription using only `mistralai/Voxtral-Mini-3B-2507` served by local vLLM.

## Hard Constraints

- Do not switch to `mistralai/Voxtral-Mini-4B-Realtime-2602`.
- Do not build around realtime streaming.
- Do not require Mistral, OpenAI, or other cloud APIs for the core workflow.
- Run vLLM and the Gradio app in WSL2 Ubuntu, not native Windows Python.
- Bind services to `0.0.0.0`; Windows should open the UI at `http://localhost:7860`.
- Preserve the user prompt style in `app/prompts.py`.
- Use temperature `0.0` for transcription and cleanup.
- Do not run long-running server commands inside Codex.
- Do not start vLLM or Gradio inside Codex.
- Only create or update scripts and run syntax checks inside Codex.
- The user will run `start_voxtral_webui.cmd` manually.

## Expected Workflow

1. Upload a journal audio file.
2. Normalize it to mono 16 kHz WAV.
3. Try full-file processing when requested.
4. Fall back to 5-minute chunks with 30-second overlap when full-file processing fails or when always-chunk mode is selected.
5. Keep raw chunk transcripts.
6. Merge chunk transcripts.
7. Run a second global-context polishing pass for the final journal transcript.
8. Write Markdown, JSON, raw merged Markdown, and `chunks.zip` outputs.

## Compatibility Notes

The official Voxtral Mini 3B model card says true system prompts are not yet supported. Keep journal instructions in user-message content for Voxtral compatibility, while still storing the canonical long prompt in `app/prompts.py`.
