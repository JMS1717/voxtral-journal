import json

from app.output_writer import OutputWriter


def test_output_writer_creates_download_artifacts(tmp_path):
    writer = OutputWriter(tmp_path / "final", tmp_path / "raw")
    normalized = tmp_path / "entry.wav"
    normalized.write_bytes(b"wav")
    chunk = tmp_path / "chunk.wav"
    chunk.write_bytes(b"chunk")
    chunk_transcript = writer.write_chunk_transcript("session", 1, "raw chunk")

    artifacts = writer.write_outputs(
        "session",
        "final text",
        "raw text",
        {"mode": "test"},
        normalized,
        [chunk],
        [chunk_transcript],
    )

    assert artifacts.final_markdown.read_text(encoding="utf-8").strip() == "final text"
    assert artifacts.raw_merged_markdown.read_text(encoding="utf-8").strip() == "raw text"
    payload = json.loads(artifacts.transcript_json.read_text(encoding="utf-8"))
    assert payload["metadata"]["mode"] == "test"
    assert artifacts.chunks_zip is not None
    assert artifacts.chunks_zip.exists()

