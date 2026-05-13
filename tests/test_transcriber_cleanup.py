from pathlib import Path

from app.transcriber import JournalTranscriber


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.data_dir = root / "data"
        self.uploads_dir = self.data_dir / "uploads"
        self.normalized_dir = self.data_dir / "normalized"
        self.chunks_dir = self.data_dir / "chunks"
        self.raw_transcripts_dir = self.data_dir / "raw_transcripts"
        self.final_transcripts_dir = self.data_dir / "final_transcripts"
        self.logs_dir = self.data_dir / "logs"
        self.vllm_context_window = 1200
        self.cleanup_max_output_tokens = 600
        self.cleanup_token_safety_margin = 100
        self.cleanup_min_output_tokens = 100
        self.long_transcript_chunk_tokens = 50
        self.ffmpeg_bin = "ffmpeg"
        self.ffprobe_bin = "ffprobe"
        self.voxtral_model = "mistralai/Voxtral-Mini-3B-2507"

    def ensure_dirs(self) -> None:
        for path in [
            self.uploads_dir,
            self.normalized_dir,
            self.chunks_dir,
            self.raw_transcripts_dir,
            self.final_transcripts_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def chat_text(self, prompt: str, max_tokens: int) -> str:
        self.calls.append((prompt, max_tokens))
        if "Clean this raw transcript segment" in prompt:
            return "cleaned segment output"
        return "final journal output"


def test_hierarchical_cleanup_runs_when_single_prompt_is_too_large(tmp_path):
    settings = FakeSettings(tmp_path)
    client = FakeClient()
    transcriber = JournalTranscriber(settings, client=client)
    raw_text = "\n\n".join(f"important content {index} " * 20 for index in range(12))

    result = transcriber._polish_with_context_budget(
        "session-1",
        raw_text,
        "Wednesday, May 13, 2026 4:32 PM",
        "en",
        progress=None,
    )

    assert result == "final journal output"
    assert len(client.calls) > 1
    assert all(max_tokens < settings.vllm_context_window for _, max_tokens in client.calls)
    assert any("Wednesday, May 13, 2026 4:32 PM" in prompt for prompt, _ in client.calls)
    assert (settings.final_transcripts_dir / "session-1" / "hierarchical_cleanup_segments").exists()
