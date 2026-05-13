from __future__ import annotations

import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _default_ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=PROJECT_ROOT / ".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        project_root: Path = PROJECT_ROOT
        data_dir: Path = Field(default=PROJECT_ROOT / "data")
        uploads_dir: Path = Field(default=PROJECT_ROOT / "data" / "uploads")
        normalized_dir: Path = Field(default=PROJECT_ROOT / "data" / "normalized")
        chunks_dir: Path = Field(default=PROJECT_ROOT / "data" / "chunks")
        raw_transcripts_dir: Path = Field(default=PROJECT_ROOT / "data" / "raw_transcripts")
        final_transcripts_dir: Path = Field(default=PROJECT_ROOT / "data" / "final_transcripts")
        logs_dir: Path = Field(default=PROJECT_ROOT / "data" / "logs")

        vllm_base_url: str = "http://localhost:8000/v1"
        vllm_api_key: str = "EMPTY"
        voxtral_model: str = "mistralai/Voxtral-Mini-3B-2507"
        gradio_host: str = "0.0.0.0"
        gradio_port: int = 7860
        request_timeout_seconds: int = 1800
        connect_timeout_seconds: int = 30
        default_language: str = "en"
        default_chunk_seconds: int = 300
        default_overlap_seconds: int = 30
        ffmpeg_bin: str = Field(default_factory=lambda: _default_ffmpeg_bin())
        ffprobe_bin: str = "ffprobe"
        log_level: str = "INFO"
        debug: bool = False

        def ensure_dirs(self) -> None:
            for path in data_directories(self):
                path.mkdir(parents=True, exist_ok=True)

except Exception:

    class Settings:
        def __init__(self, **overrides: Any) -> None:
            self.project_root = Path(overrides.get("project_root", PROJECT_ROOT))
            self.data_dir = Path(os.getenv("DATA_DIR", self.project_root / "data"))
            self.uploads_dir = Path(os.getenv("UPLOADS_DIR", self.data_dir / "uploads"))
            self.normalized_dir = Path(os.getenv("NORMALIZED_DIR", self.data_dir / "normalized"))
            self.chunks_dir = Path(os.getenv("CHUNKS_DIR", self.data_dir / "chunks"))
            self.raw_transcripts_dir = Path(
                os.getenv("RAW_TRANSCRIPTS_DIR", self.data_dir / "raw_transcripts")
            )
            self.final_transcripts_dir = Path(
                os.getenv("FINAL_TRANSCRIPTS_DIR", self.data_dir / "final_transcripts")
            )
            self.logs_dir = Path(os.getenv("LOGS_DIR", self.data_dir / "logs"))
            self.vllm_base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
            self.vllm_api_key = os.getenv("VLLM_API_KEY", "EMPTY")
            self.voxtral_model = os.getenv("VOXTRAL_MODEL", "mistralai/Voxtral-Mini-3B-2507")
            self.gradio_host = os.getenv("GRADIO_HOST", "0.0.0.0")
            self.gradio_port = int(os.getenv("GRADIO_PORT", "7860"))
            self.request_timeout_seconds = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "1800"))
            self.connect_timeout_seconds = int(os.getenv("CONNECT_TIMEOUT_SECONDS", "30"))
            self.default_language = os.getenv("DEFAULT_LANGUAGE", "en")
            self.default_chunk_seconds = int(os.getenv("DEFAULT_CHUNK_SECONDS", "300"))
            self.default_overlap_seconds = int(os.getenv("DEFAULT_OVERLAP_SECONDS", "30"))
            self.ffmpeg_bin = os.getenv("FFMPEG_BIN", _default_ffmpeg_bin())
            self.ffprobe_bin = os.getenv("FFPROBE_BIN", "ffprobe")
            self.log_level = os.getenv("LOG_LEVEL", "INFO")
            self.debug = _bool(os.getenv("DEBUG"), False)
            for key, value in overrides.items():
                setattr(self, key, value)

        def ensure_dirs(self) -> None:
            for path in data_directories(self):
                path.mkdir(parents=True, exist_ok=True)


def data_directories(settings: Settings) -> list[Path]:
    return [
        settings.uploads_dir,
        settings.normalized_dir,
        settings.chunks_dir,
        settings.raw_transcripts_dir,
        settings.final_transcripts_dir,
        settings.logs_dir,
    ]


settings = Settings()
