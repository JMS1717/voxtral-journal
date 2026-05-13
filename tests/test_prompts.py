from app.prompts import (
    JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT,
    current_journal_datetime,
    build_full_file_audio_prompt,
    build_polish_from_merged_prompt,
)

from datetime import datetime
import re


def test_prompt_contains_required_header_style():
    assert "Date: Tuesday, September 23, 2025 9:32pm" in JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT
    assert "Subject:" in JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT
    assert "[inaudible]" in JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT


def test_full_file_prompt_includes_datetime_and_language():
    prompt = build_full_file_audio_prompt("Wednesday, May 13, 2026 8:00pm", "en")
    assert "Wednesday, May 13, 2026 8:00pm" in prompt
    assert "Language hint: en" in prompt


def test_current_journal_datetime_formats_a_local_datetime():
    local_tz = datetime.now().astimezone().tzinfo
    assert local_tz is not None
    value = current_journal_datetime(datetime(2026, 5, 13, 16, 32, tzinfo=local_tz))
    assert value == "Wednesday, May 13, 2026 4:32 PM"


def test_current_journal_datetime_is_non_empty_and_includes_year_and_time():
    value = current_journal_datetime()
    assert value.strip()
    assert re.search(r"\b20\d{2}\b", value)
    assert re.search(r"\b\d{1,2}:\d{2}\s(AM|PM)\b", value)


def test_polish_prompt_includes_merged_transcript():
    prompt = build_polish_from_merged_prompt("hello world", "date", "en")
    assert "hello world" in prompt
    assert "Merged raw transcript" in prompt
