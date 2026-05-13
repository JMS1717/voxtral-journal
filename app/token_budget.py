from __future__ import annotations

import math
from dataclasses import dataclass


class CleanupContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class TokenBudget:
    context_window: int
    estimated_input_tokens: int
    requested_output_tokens: int
    safety_margin: int


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def cleanup_token_budget(
    prompt: str,
    context_window: int,
    cleanup_max_output_tokens: int,
    safety_margin: int,
    cleanup_min_output_tokens: int,
) -> TokenBudget:
    estimated_input_tokens = estimate_tokens(prompt)
    available = context_window - estimated_input_tokens - safety_margin
    effective_max = min(cleanup_max_output_tokens, max(1, context_window // 2))
    requested = min(effective_max, available)

    if estimated_input_tokens > 0 and requested >= context_window:
        requested = context_window - safety_margin - estimated_input_tokens

    if requested < cleanup_min_output_tokens:
        raise CleanupContextError(
            "The transcript is too long for the current context profile. "
            "The app tried hierarchical cleanup. If this still fails, use Balanced 16k or shorter chunks."
        )

    return TokenBudget(
        context_window=context_window,
        estimated_input_tokens=estimated_input_tokens,
        requested_output_tokens=max(1, requested),
        safety_margin=safety_margin,
    )


def split_text_by_token_estimate(text: str, target_tokens: int) -> list[str]:
    if not text.strip():
        return []

    target_chars = max(1, target_tokens * 4)
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    segments: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        if len(paragraph) > target_chars:
            if current_parts:
                segments.append("\n\n".join(current_parts))
                current_parts = []
                current_len = 0
            segments.extend(_split_long_text(paragraph, target_chars))
            continue

        separator_len = 2 if current_parts else 0
        if current_parts and current_len + separator_len + len(paragraph) > target_chars:
            segments.append("\n\n".join(current_parts))
            current_parts = [paragraph]
            current_len = len(paragraph)
        else:
            current_parts.append(paragraph)
            current_len += separator_len + len(paragraph)

    if current_parts:
        segments.append("\n\n".join(current_parts))

    return segments


def _split_long_text(text: str, target_chars: int) -> list[str]:
    segments: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target_chars)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        segment = text[start:end].strip()
        if segment:
            segments.append(segment)
        start = end
    return segments
