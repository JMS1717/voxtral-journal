from app.main import (
    build_demo,
    current_journal_datetime,
    history_downloads_for_job,
    history_text_value,
    refresh_diagnostics_section,
    refresh_history_tab,
    settings,
)


def test_gradio_demo_builds():
    demo = build_demo()
    assert demo.blocks


def test_main_ui_no_unstable_tab_or_dataframe_components():
    source = (settings.project_root / "app" / "main.py").read_text(encoding="utf-8")

    assert "gr.Tab(" not in source
    assert "gr.Tabs(" not in source
    assert ".select(" not in source
    assert "gr.Dataframe(" not in source


def test_current_journal_datetime_default_available():
    assert current_journal_datetime()


def test_history_text_value_formats_rows():
    text = history_text_value(
        [
            {
                "job_id": "job-1",
                "created_at": "2026-05-13T19:00:00",
                "source_filename": "entry.m4a",
                "status": "completed",
            }
        ]
    )

    assert "created_at | source filename" in text
    assert "2026-05-13T19:00:00 | entry.m4a" in text
    assert "job-1" in text


def test_refresh_history_tab_handles_load_failure(monkeypatch):
    def fail_load(*args, **kwargs):
        raise RuntimeError("bad history")

    monkeypatch.setattr("app.main.load_history_entries", fail_load)

    rows, dropdown_update, final_path, json_path = refresh_history_tab()

    assert rows == "No history entries found."
    assert dropdown_update["choices"] == []
    assert dropdown_update["value"] is None
    assert final_path is None
    assert json_path is None


def test_refresh_history_tab_does_not_auto_download_first_job(monkeypatch):
    monkeypatch.setattr(
        "app.main.load_history_entries",
        lambda *args, **kwargs: [{"job_id": "job-1", "created_at": "2026-05-13T19:00:00"}],
    )

    text, dropdown_update, final_path, json_path = refresh_history_tab()

    assert "job-1" in text
    assert dropdown_update["choices"] == ["job-1"]
    assert dropdown_update["value"] is None
    assert final_path is None
    assert json_path is None


def test_refresh_diagnostics_section_uses_snapshot(monkeypatch):
    monkeypatch.setattr(
        "app.main.diagnostics_snapshot",
        lambda settings: ("OK", "mistralai/Voxtral-Mini-3B-2507", "vllm tail", "gradio tail"),
    )

    text = refresh_diagnostics_section()

    assert "vLLM health\n\nOK" in text
    assert "mistralai/Voxtral-Mini-3B-2507" in text
    assert "vllm tail" in text
    assert "gradio tail" in text


def test_history_downloads_handles_load_failure(monkeypatch):
    def fail_load(*args, **kwargs):
        raise RuntimeError("bad history")

    monkeypatch.setattr("app.main.load_history_entries", fail_load)

    assert history_downloads_for_job("job-1") == (None, None)


def test_history_downloads_prefers_runtime_artifact_paths(monkeypatch, tmp_path):
    runtime_final_dir = tmp_path / "runtime" / "data" / "final_transcripts"
    session_dir = runtime_final_dir / "job-1"
    session_dir.mkdir(parents=True)
    final_md = session_dir / "final_journal_transcript.md"
    transcript_json = session_dir / "transcript.json"
    final_md.write_text("final", encoding="utf-8")
    transcript_json.write_text("{}", encoding="utf-8")

    stale_dir = tmp_path / "stale"
    stale_dir.mkdir()
    stale_final = stale_dir / "final_journal_transcript.md"
    stale_json = stale_dir / "transcript.json"
    stale_final.write_text("stale", encoding="utf-8")
    stale_json.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(settings, "project_root", tmp_path / "runtime")
    monkeypatch.setattr(settings, "final_transcripts_dir", runtime_final_dir)
    monkeypatch.setattr(
        "app.main.load_history_entries",
        lambda *args, **kwargs: [
            {
                "job_id": "job-1",
                "final_markdown_path": str(stale_final),
                "json_path": str(stale_json),
            }
        ],
    )

    assert history_downloads_for_job("job-1") == (str(final_md), str(transcript_json))
