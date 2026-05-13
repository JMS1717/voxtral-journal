from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


INDEX_RELATIVE_PATH = Path("history") / "index.json"


def history_index_path(data_dir: Path) -> Path:
    return data_dir / INDEX_RELATIVE_PATH


def load_history_entries(data_dir: Path, final_transcripts_dir: Path, limit: int | None = None) -> list[dict[str, Any]]:
    index_path = history_index_path(data_dir)
    if index_path.exists():
        entries = _read_index(index_path)
    else:
        entries = scan_transcript_history(final_transcripts_dir)
        write_history_index(data_dir, entries)

    entries = sorted(entries, key=lambda entry: entry.get("created_at") or "", reverse=True)
    if limit is not None:
        return entries[:limit]
    return entries


def scan_transcript_history(final_transcripts_dir: Path) -> list[dict[str, Any]]:
    if not final_transcripts_dir.exists():
        return []

    entries: list[dict[str, Any]] = []
    for transcript_json in sorted(final_transcripts_dir.glob("*/transcript.json")):
        entry = entry_from_transcript_json(transcript_json)
        if entry is not None:
            entries.append(entry)
    return entries


def entry_from_transcript_json(transcript_json: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(transcript_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    metadata = payload.get("metadata") if isinstance(payload, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    session_dir = transcript_json.parent
    job_id = str(metadata.get("session_id") or session_dir.name)
    final_markdown = session_dir / "final_journal_transcript.md"
    raw_merged = session_dir / "raw_merged_transcript.md"
    chunks_zip = session_dir / "chunks.zip"

    return normalize_history_entry(
        {
            "job_id": job_id,
            "created_at": metadata.get("created_at") or _mtime_iso(transcript_json),
            "source_filename": _source_filename(metadata),
            "audio_duration_seconds": metadata.get("audio_duration_seconds"),
            "mode": metadata.get("mode"),
            "status": metadata.get("status") or "completed",
            "final_markdown_path": str(final_markdown) if final_markdown.exists() else None,
            "json_path": str(transcript_json),
            "raw_merged_path": str(raw_merged) if raw_merged.exists() else None,
            "chunks_zip_path": str(chunks_zip) if chunks_zip.exists() else None,
            "error": metadata.get("error"),
        }
    )


def upsert_history_entry(data_dir: Path, entry: dict[str, Any]) -> list[dict[str, Any]]:
    index_path = history_index_path(data_dir)
    entries = _read_index(index_path) if index_path.exists() else []
    normalized = normalize_history_entry(entry)
    job_id = normalized["job_id"]

    replaced = False
    updated: list[dict[str, Any]] = []
    for existing in entries:
        if existing.get("job_id") == job_id:
            updated.append({**existing, **normalized})
            replaced = True
        else:
            updated.append(normalize_history_entry(existing))
    if not replaced:
        updated.append(normalized)

    updated = sorted(updated, key=lambda item: item.get("created_at") or "", reverse=True)
    write_history_index(data_dir, updated)
    return updated


def write_history_index(data_dir: Path, entries: list[dict[str, Any]]) -> None:
    index_path = history_index_path(data_dir)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "jobs": [normalize_history_entry(entry) for entry in entries]}
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def history_rows(entries: list[dict[str, Any]]) -> list[list[Any]]:
    return [
        [
            entry.get("created_at") or "",
            entry.get("source_filename") or "",
            entry.get("audio_duration_seconds"),
            entry.get("mode") or "",
            entry.get("status") or "",
            entry.get("final_markdown_path") or "",
            entry.get("json_path") or "",
            entry.get("job_id") or "",
        ]
        for entry in entries
    ]


def normalize_history_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": str(entry.get("job_id") or ""),
        "created_at": entry.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        "source_filename": entry.get("source_filename") or "",
        "audio_duration_seconds": entry.get("audio_duration_seconds"),
        "mode": entry.get("mode") or "",
        "status": entry.get("status") or "completed",
        "final_markdown_path": entry.get("final_markdown_path"),
        "json_path": entry.get("json_path"),
        "raw_merged_path": entry.get("raw_merged_path"),
        "chunks_zip_path": entry.get("chunks_zip_path"),
        "error": entry.get("error"),
    }


def _read_index(index_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(payload, list):
        jobs = payload
    elif isinstance(payload, dict):
        jobs = payload.get("jobs", [])
    else:
        jobs = []

    return [normalize_history_entry(job) for job in jobs if isinstance(job, dict)]


def _source_filename(metadata: dict[str, Any]) -> str:
    source = metadata.get("source_file") or metadata.get("uploaded_file") or ""
    if not source:
        return ""
    return Path(str(source)).name


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
