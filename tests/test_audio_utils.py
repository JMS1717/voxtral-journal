from pathlib import Path

import pytest

from app.audio_utils import AudioProcessingError, compute_chunk_ranges, safe_stem, validate_audio_extension


def test_compute_chunk_ranges_with_overlap():
    ranges = compute_chunk_ranges(610, chunk_length_seconds=300, overlap_seconds=30)
    assert len(ranges) == 3
    assert ranges[0].start_seconds == 0
    assert ranges[1].start_seconds == 270
    assert ranges[2].start_seconds == 540
    assert ranges[2].duration_seconds == 70


def test_overlap_must_be_smaller_than_chunk():
    with pytest.raises(AudioProcessingError):
        compute_chunk_ranges(100, chunk_length_seconds=30, overlap_seconds=30)


def test_safe_stem_removes_problem_characters():
    assert safe_stem(Path("my journal entry!.mp3")) == "my_journal_entry"


def test_supported_audio_extension():
    validate_audio_extension(Path("entry.m4a"))
    with pytest.raises(AudioProcessingError):
        validate_audio_extension(Path("entry.txt"))

