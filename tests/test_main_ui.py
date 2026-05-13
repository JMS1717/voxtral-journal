from app.main import EMPTY_HISTORY_ROW, build_demo, history_downloads_for_job, history_table_value, refresh_history_tab


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


def test_history_downloads_handles_load_failure(monkeypatch):
    def fail_load(*args, **kwargs):
        raise RuntimeError("bad history")

    monkeypatch.setattr("app.main.load_history_entries", fail_load)

    assert history_downloads_for_job("job-1") == (None, None)
