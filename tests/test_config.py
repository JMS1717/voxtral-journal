from app.config import Settings, data_directories


def test_defaults_use_voxtral_mini_3b_only(tmp_path):
    settings = Settings(project_root=tmp_path)
    assert settings.voxtral_model == "mistralai/Voxtral-Mini-3B-2507"
    assert "4B-Realtime" not in settings.voxtral_model


def test_data_directories_are_named():
    settings = Settings()
    names = {path.name for path in data_directories(settings)}
    assert {"uploads", "normalized", "chunks", "raw_transcripts", "final_transcripts", "logs"} <= names

