from app.main import (
    EMPTY_HISTORY_ROW,
    build_demo,
    history_downloads_for_job,
    history_table_value,
    refresh_history_tab,
    settings,
)


def test_gradio_demo_builds():
    demo = build_demo()
    assert demo.blocks


def test_history_table_value_keeps_empty_dataframe_shape():
    assert history_table_value([]) == EMPTY_HISTORY_ROW


def test_refresh_history_tab_handles_load_failure(monkeypatch):
    def fail_load(*args, **kwargs):
        raise RuntimeError("bad history")

    monkeypatch.setattr("app.main.load_history_entries", fail_load)

    rows, dropdown_update, final_path, json_path = refresh_history_tab()

    assert rows == EMPTY_HISTORY_ROW
    assert dropdown_update["choices"] == []
    assert dropdown_update["value"] is None
    assert final_path is None
    assert json_path is None


def test_refresh_history_tab_does_not_auto_download_first_job(monkeypatch):
    monkeypatch.setattr(
        "app.main.load_history_entries",
        lambda *args, **kwargs: [{"job_id": "job-1", "created_at": "2026-05-13T19:00:00"}],
    )

    rows, dropdown_update, final_path, json_path = refresh_history_tab()

    assert rows[0][-1] == "job-1"
    assert dropdown_update["choices"] == ["job-1"]
    assert dropdown_update["value"] is None
    assert final_path is None
    assert json_path is None


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
