from __future__ import annotations

from datetime import datetime


JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT = """You are an expert transcriptionist tasked with transcribing a personal audio journal. Your goal is to create a clean, readable text that captures the core narrative and emotional journey of the entry, rather than a moment-by-moment log of every sound and tonal shift.

Follow these transcription guidelines:

Header
Start with a header containing the date, time, and a detailed summary. The summary should be a concise paragraph that outlines the main topics discussed, key events, and the overall emotional arc of the entry (e.g., from frustration to resolution).

Transcription Style
Transcribe the speech using a clean verbatim style. This means you should write down every word exactly as spoken, but omit filler words like "um," "uh," and false starts.

Contextual Notations
Use notations for tone and sound sparingly. Only include them when they are critical to the narrative or mark a significant emotional turning point. Avoid noting minor background noises (like a chair creaking or pencil tapping) unless the speaker directly interacts with or is clearly affected by the sound.

* Tone: Note a clear emotional shift at the end of a key phrase, formatted as [tone: descriptive].
* Significant Sounds: Note only non-verbal sounds that add meaning to the narrative (e.g., a heavy sigh before bad news, a laugh of relief), formatted as [sound: description].
* Inaudible Speech: If you cannot understand a word or phrase, use [inaudible].

Example of Output:
Date: Tuesday, September 23, 2025 9:32pm
Subject: The entry covers the disappointment of being rejected for a job in favor of an internal candidate. The initial tone is one of dejection and frustration, but the speaker resolves to seek support, ending on a more hopeful note about the future.

So, I finally heard back about the job application today. [sound: deep sigh] It wasn't the news I was hoping for. [tone: dejected] They said they went with an internal candidate. I just... I don't know what to do next. It feels like I'm stuck. [tone: frustrated] Maybe I'll call mom tomorrow. Yeah, that might help. [tone: hopeful]"""


def current_journal_datetime(now: datetime | None = None) -> str:
    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        current = current.astimezone()
    formatted = current.strftime("%A, %B %d, %Y %I:%M %p")
    formatted = formatted.replace(" 0", " ").strip()
    return formatted


def build_full_file_audio_prompt(journal_datetime: str, language: str) -> str:
    return f"""{JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT}

Journal date/time to use in the header: {journal_datetime}
Language hint: {language}

Transcribe the attached audio journal as the final polished journal transcript. Create the Date and Subject header, preserve the speaker's wording, remove filler words and false starts, avoid overusing [tone:] and [sound:] notations, and mark uncertain sections as [inaudible]."""


def build_chunk_transcription_prompt(language: str) -> str:
    return f"""Transcribe this audio chunk in {language}.

Use clean verbatim text. Remove filler words like "um" and "uh" and obvious false starts. Do not summarize. Do not add a Date or Subject header. Use [inaudible] for uncertain words or phrases."""


def build_polish_from_merged_prompt(merged_transcript: str, journal_datetime: str, language: str) -> str:
    return f"""{JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT}

Journal date/time to use in the header: {journal_datetime}
Language hint: {language}

Below is the merged raw transcript from one or more audio chunks. Produce the final polished journal transcript. Create the Date and Subject header, preserve the speaker's wording, remove filler words and false starts, avoid overusing [tone:] and [sound:] notations, and mark uncertain sections as [inaudible].

Merged raw transcript:
---
{merged_transcript}
---"""


def build_segment_cleanup_prompt(segment_text: str, segment_index: int, total_segments: int, language: str) -> str:
    return f"""Clean this raw transcript segment in {language}.

This is segment {segment_index} of {total_segments}. Preserve the speaker's wording, sequence of events, emotional shifts, and any important context needed for the final journal transcript. Remove filler words and obvious false starts. Do not invent details. Do not write the final Date or Subject header.

Raw transcript segment:
---
{segment_text}
---"""


def build_polish_from_cleaned_segments_prompt(
    cleaned_segments: str,
    journal_datetime: str,
    language: str,
) -> str:
    return f"""{JOURNAL_TRANSCRIPTION_SYSTEM_PROMPT}

Journal date/time to use in the header: {journal_datetime}
Language hint: {language}

Below are cleaned transcript segments from one longer audio journal. Produce one coherent final polished journal transcript. Preserve the requested date/time, the emotional arc, narrative continuity, and the speaker's wording where possible. Create the Date and Subject header, avoid overusing [tone:] and [sound:] notations, and mark uncertain sections as [inaudible].

Cleaned transcript segments:
---
{cleaned_segments}
---"""
