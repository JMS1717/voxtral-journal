import json

from app.history import history_index_path, history_rows, load_history_entries, upsert_history_entry


def test_history_backfills_from_existing_transcript_json(tmp_path):
    data_dir = tmp_path / "data"
    final_dir = data_dir / "final_transcripts"
    session_dir = final_dir / "session-1"
    session_dir.mkdir(parents=True)
    (session_dir / "final_journal_transcript.md").write_text("final", encoding="utf-8")
    (session_dir / "raw_merged_transcript.md").write_text("raw", encoding="utf-8")
    transcript_json = session_dir / "transcript.json"
    transcript_json.write_text(
        json.dumps(
            {
                "metadata": {
                    "session_id": "session-1",
                    "created_at": "2026-05-13T16:32:00",
                    "source_file": "C:\\Audio\\journal.m4a",
                    "audio_duration_seconds": 42.5,
                    "mode": "always chunk",
                }
            }
        ),
        encoding="utf-8",
    )

    entries = load_history_entries(data_dir, final_dir)

    assert history_index_path(data_dir).exists()
    assert entries[0]["job_id"] == "session-1"
    assert entries[0]["source_filename"] == "journal.m4a"
    assert entries[0]["audio_duration_seconds"] == 42.5
    assert entries[0]["status"] == "completed"
    assert entries[0]["final_markdown_path"].endswith("final_journal_transcript.md")
    assert entries[0]["json_path"].endswith("transcript.json")


def test_upsert_history_entry_replaces_existing_job(tmp_path):
    data_dir = tmp_path / "data"
    upsert_history_entry(
        data_dir,
        {
            "job_id": "job-1",
            "created_at": "2026-05-13T16:00:00",
            "source_filename": "first.m4a",
            "status": "failed",
            "error": "old error",
        },
    )

    entries = upsert_history_entry(
        data_dir,
        {
            "job_id": "job-1",
            "created_at": "2026-05-13T16:01:00",
            "source_filename": "first.m4a",
            "status": "completed",
            "error": None,
        },
    )

    assert len(entries) == 1
    assert entries[0]["status"] == "completed"
    assert entries[0]["error"] is None


def test_history_rows_include_download_paths(tmp_path):
    rows = history_rows(
        [
            {
                "job_id": "job-1",
                "created_at": "2026-05-13T16:00:00",
                "source_filename": "entry.m4a",
                "audio_duration_seconds": None,
                "mode": "raw transcription only",
                "status": "completed",
                "final_markdown_path": "final.md",
                "json_path": "transcript.json",
            }
        ]
    )

    assert rows == [
        [
            "2026-05-13T16:00:00",
            "entry.m4a",
            None,
            "raw transcription only",
            "completed",
            "final.md",
            "transcript.json",
            "job-1",
        ]
    ]
