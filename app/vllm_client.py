from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings


LOGGER = logging.getLogger(__name__)


class VLLMClientError(RuntimeError):
    pass


class VoxtralVLLMClient:
    """OpenAI-compatible vLLM client for Voxtral Mini 3B audio workflows."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise VLLMClientError("Install the OpenAI Python client: pip install openai") from exc

            timeout = httpx.Timeout(
                timeout=self.settings.request_timeout_seconds,
                connect=self.settings.connect_timeout_seconds,
            )
            self._client = OpenAI(
                api_key=self.settings.vllm_api_key,
                base_url=self.settings.vllm_base_url,
                timeout=timeout,
            )
        return self._client

    def list_models(self) -> list[str]:
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as exc:
            raise VLLMClientError(f"Could not reach vLLM at {self.settings.vllm_base_url}: {exc}") from exc

    def resolve_model(self) -> str:
        try:
            models = self.list_models()
        except VLLMClientError:
            return self.settings.voxtral_model
        return models[0] if models else self.settings.voxtral_model

    def transcribe_audio(self, audio_path: Path, language: str = "en") -> str:
        """Use Voxtral's dedicated transcription request format."""
        try:
            from mistral_common.audio import Audio
            from mistral_common.protocol.transcription.request import TranscriptionRequest

            try:
                from mistral_common.protocol.instruct.chunk import RawAudio
            except ImportError:
                from mistral_common.protocol.instruct.messages import RawAudio
        except ImportError as exc:
            raise VLLMClientError(
                'Install Voxtral audio client support: pip install "mistral-common[audio]"'
            ) from exc

        try:
            audio = Audio.from_file(str(audio_path), strict=False)
            raw_audio = RawAudio.from_audio(audio)
            req = TranscriptionRequest(
                model=self.resolve_model(),
                audio=raw_audio,
                language=language,
                temperature=0.0,
            ).to_openai(exclude=("top_p", "seed"))
            req = _sanitize_transcription_request(req)
            response = self.client.audio.transcriptions.create(**req)
            return _extract_text(response)
        except Exception as exc:
            raise VLLMClientError(f"Voxtral transcription failed for {audio_path.name}: {exc}") from exc

    def chat_with_audio(self, audio_path: Path, prompt: str, max_tokens: int = 8192) -> str:
        """Send one audio file plus text instruction through Mistral's chat audio objects."""
        try:
            from mistral_common.audio import Audio
            from mistral_common.protocol.instruct.messages import UserMessage

            try:
                from mistral_common.protocol.instruct.messages import AudioChunk, TextChunk
            except ImportError:
                from mistral_common.protocol.instruct.chunk import AudioChunk, TextChunk

            try:
                from mistral_common.protocol.instruct.chunk import RawAudio
            except ImportError:
                from mistral_common.protocol.instruct.messages import RawAudio
        except ImportError as exc:
            raise VLLMClientError(
                'Install Voxtral audio client support: pip install "mistral-common[audio]"'
            ) from exc

        try:
            audio = Audio.from_file(str(audio_path), strict=False)
            try:
                audio_chunk = AudioChunk.from_audio(audio)
            except AttributeError:
                audio_chunk = AudioChunk(input_audio=RawAudio.from_audio(audio))
            user_message = UserMessage(content=[audio_chunk, TextChunk(text=prompt)]).to_openai()
            response = self.client.chat.completions.create(
                model=self.resolve_model(),
                messages=[user_message],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise VLLMClientError(f"Voxtral audio chat failed for {audio_path.name}: {exc}") from exc

    def chat_text(self, prompt: str, max_tokens: int = 8192) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.resolve_model(),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise VLLMClientError(f"Voxtral text cleanup failed: {exc}") from exc


def _extract_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    text = getattr(response, "text", None)
    if text:
        return str(text)
    if isinstance(response, dict):
        for key in ("text", "transcript", "content"):
            if response.get(key):
                return str(response[key])
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        for key in ("text", "transcript", "content"):
            if dumped.get(key):
                return str(dumped[key])
    return str(response)


def _sanitize_transcription_request(req: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(req)
    sanitized.pop("target_streaming_delay_ms", None)
    return sanitized
