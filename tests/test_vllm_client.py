from app.vllm_client import _sanitize_transcription_request


def test_sanitize_transcription_request_removes_streaming_field():
    req = {
        "model": "mistralai/Voxtral-Mini-3B-2507",
        "file": object(),
        "target_streaming_delay_ms": None,
    }

    sanitized = _sanitize_transcription_request(req)

    assert "target_streaming_delay_ms" not in sanitized
    assert sanitized["model"] == "mistralai/Voxtral-Mini-3B-2507"

