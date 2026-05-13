from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.config import Settings


def check_vllm_health(settings: Settings, timeout_seconds: float = 3.0) -> dict[str, Any]:
    url = settings.vllm_base_url.rstrip("/") + "/models"
    try:
        response = httpx.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        model_ids = _extract_model_ids(payload)
        return {
            "ok": True,
            "url": url,
            "status_code": response.status_code,
            "model_ids": model_ids,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "status_code": None,
            "model_ids": [],
            "error": str(exc),
        }


def read_log_tail(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return f"{path} does not exist."
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"Could not read {path}: {exc}"
    return "\n".join(content[-lines:])


def diagnostics_snapshot(settings: Settings) -> tuple[str, str, str, str]:
    health = check_vllm_health(settings)
    if health["ok"]:
        health_text = f"OK: {health['url']} returned HTTP {health['status_code']}."
    else:
        health_text = f"Unavailable: {health['url']} ({health['error']})"

    model_ids = health.get("model_ids") or []
    models_text = "\n".join(model_ids) if model_ids else "No model id returned."
    vllm_tail = read_log_tail(settings.logs_dir / "vllm.log", lines=80)
    gradio_tail = read_log_tail(settings.logs_dir / "gradio.log", lines=80)
    return health_text, models_text, vllm_tail, gradio_tail


def _extract_model_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    model_ids: list[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            model_ids.append(str(item["id"]))
    return model_ids
