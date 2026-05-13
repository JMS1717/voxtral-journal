import pytest

from app.token_budget import CleanupContextError, cleanup_token_budget, split_text_by_token_estimate


def test_cleanup_budget_caps_output_to_half_context_even_if_configured_higher():
    prompt = "x" * (1599 * 4)

    budget = cleanup_token_budget(
        prompt,
        context_window=8192,
        cleanup_max_output_tokens=8192,
        safety_margin=512,
        cleanup_min_output_tokens=512,
    )

    assert budget.estimated_input_tokens == 1599
    assert budget.requested_output_tokens <= 4096


def test_cleanup_budget_never_requests_full_context_for_non_empty_input():
    budget = cleanup_token_budget(
        "non-empty input",
        context_window=8192,
        cleanup_max_output_tokens=8192,
        safety_margin=512,
        cleanup_min_output_tokens=512,
    )

    assert budget.requested_output_tokens < budget.context_window


def test_oversized_input_raises_readable_cleanup_error():
    prompt = "x" * (7900 * 4)

    with pytest.raises(CleanupContextError, match="transcript is too long"):
        cleanup_token_budget(
            prompt,
            context_window=8192,
            cleanup_max_output_tokens=4096,
            safety_margin=512,
            cleanup_min_output_tokens=512,
        )


def test_split_text_by_token_estimate_preserves_content_order():
    text = "\n\n".join(f"paragraph {index}" for index in range(20))

    segments = split_text_by_token_estimate(text, target_tokens=8)

    assert len(segments) > 1
    recombined = "\n\n".join(segments)
    for index in range(20):
        assert f"paragraph {index}" in recombined
    assert recombined.index("paragraph 0") < recombined.index("paragraph 19")
