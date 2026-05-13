# Voxtral Journal Windows

A Windows 11 + WSL2 local WebUI for personal audio journal transcription using Voxtral Mini 3B, vLLM, and Gradio.

This project is source-available for non-commercial use only under CC BY-NC 4.0. It is not OSI open source.

## What It Does

- Transcribes personal audio journal recordings with `mistralai/Voxtral-Mini-3B-2507`.
- Runs vLLM inside WSL2 Ubuntu for GPU inference.
- Opens the Gradio UI in your Windows browser.
- Writes transcripts, metadata, and logs locally on your machine.

## Local-First Privacy

This project is designed to keep audio and transcripts local. It does not require a cloud API for the core workflow.

Do not upload private audio, transcripts, logs, tokens, or model outputs to public issue trackers.

## Requirements

- Windows 11
- WSL2 Ubuntu
- An NVIDIA GPU with WSL CUDA support
- Voxtral Mini 3B only

A 16 GB VRAM GPU can work with the included launcher fallback settings. The one-click flow uses `VLLM_MAX_MODEL_LEN=16384`.

## Why WSL-Native Runtime Copy

The Windows source repo lives in:

```text
S:\dev\voxtral-journal-windows-public
```

The ML runtime runs from a WSL-native copy for speed:

```bash
~/apps/voxtral-journal-windows
```

Running Python, PyTorch, or vLLM from `/mnt/c` or `/mnt/s` can be much slower because imports and file access cross the Windows filesystem boundary. This repository syncs the source tree into the WSL runtime copy before launching the app.

## One-Click Start

From the Windows source repo:

```powershell
cd S:\dev\voxtral-journal-windows-public
.\start_voxtral_webui.cmd
```

Stop the stack:

```powershell
cd S:\dev\voxtral-journal-windows-public
.\stop_voxtral_webui.cmd
```

Logs are written in the WSL runtime copy:

```text
~/apps/voxtral-journal-windows/data/logs/
```

## Model And Runtime Notes

- The app uses `mistralai/Voxtral-Mini-3B-2507` only.
- It does not use Voxtral Realtime 4B.
- vLLM runs inside WSL2, not native Windows Python.
- Gradio opens in the Windows browser at `http://localhost:7860`.

## Troubleshooting

- If startup is slow, let the bootstrap and model load finish. First launch takes the longest.
- If vLLM fails to start, check `~/apps/voxtral-journal-windows/data/logs/vllm.log`.
- If the UI fails to start, check `~/apps/voxtral-journal-windows/data/logs/gradio.log`.
- If the launcher fails, check `~/apps/voxtral-journal-windows/data/logs/one_click_start.log`.

## Privacy Warning

Do not upload private audio, transcripts, or logs to GitHub issues.

## License

This repository is source-available for non-commercial use under the Creative Commons Attribution-NonCommercial 4.0 International license.

License link:

https://creativecommons.org/licenses/by-nc/4.0/

## Third-Party Dependencies

This repository does not include Voxtral model weights. Users are responsible for complying with the licenses and terms for Mistral/Voxtral, vLLM, PyTorch, Gradio, Hugging Face, and any other third-party dependencies or downloaded model artifacts.