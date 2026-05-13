from types import SimpleNamespace

from app import diagnostics
from app.diagnostics import diagnostics_snapshot, read_log_tail


def test_read_log_tail_returns_last_lines(tmp_path):
    log_path = tmp_path / "vllm.log"
    log_path.write_text("\n".join(f"line {index}" for index in range(100)), encoding="utf-8")

    tail = read_log_tail(log_path, lines=3)

    assert tail == "line 97\nline 98\nline 99"


def test_diagnostics_snapshot_uses_health_and_log_tails(tmp_path, monkeypatch):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "vllm.log").write_text("vllm ok", encoding="utf-8")
    (logs_dir / "gradio.log").write_text("gradio ok", encoding="utf-8")
    settings = SimpleNamespace(vllm_base_url="http://localhost:8000/v1", logs_dir=logs_dir)

    monkeypatch.setattr(
        diagnostics,
        "check_vllm_health",
        lambda settings: {
            "ok": True,
            "url": "http://localhost:8000/v1/models",
            "status_code": 200,
            "model_ids": ["mistralai/Voxtral-Mini-3B-2507"],
            "error": None,
        },
    )

    health, models, vllm_tail, gradio_tail = diagnostics_snapshot(settings)

    assert "OK" in health
    assert models == "mistralai/Voxtral-Mini-3B-2507"
    assert vllm_tail == "vllm ok"
    assert gradio_tail == "gradio ok"
