"""Tests for src/ingest/parser.py.

The parser's job is narrow: take the raw text dump from the HF dataset (which
includes a JSON-LD prelude and footer), strip the noise, and return the part
that actually contains the earnings call. Speaker-turn parsing is a later
phase's responsibility.
"""

from __future__ import annotations

from src.ingest.parser import (
    extract_call_body,
    is_likely_transcript,
)


def _long_body_paragraph() -> str:
    """A realistic-length transcript body paragraph for fixtures."""
    return (
        "Thanks for joining us today. We delivered strong results this quarter "
        "driven by Services and our installed base of devices. We continue to "
        "invest in AI infrastructure and customer-facing features. "
    )


def test_extract_call_body_skips_json_ld_prelude() -> None:
    raw = (
        'Earnings Call Transcript","datePublished":"2024-11-01T00:15:11.000Z",'
        'datasetdetails":"junk","about":[...long header...]'
        "\n\nPrepared Remarks:\n\nOperator\nGood afternoon. Welcome to the Apple Q4 call. "
        + (_long_body_paragraph() * 15)
    )
    body = extract_call_body(raw)
    assert body.startswith("Prepared Remarks:") or body.lstrip().startswith("Operator")
    assert "Welcome to the Apple Q4 call" in body
    assert '"datePublished"' not in body


def test_extract_call_body_falls_back_to_first_operator_when_no_prepared_marker() -> None:
    raw = (
        '{"@context":"https://schema.org"} ... junk junk junk\n'
        "Operator\nGood day. Welcome to the call. "
        + (_long_body_paragraph() * 15)
    )
    body = extract_call_body(raw)
    assert "Operator" in body
    assert "Good day" in body
    # The JSON-LD prelude is gone.
    assert "@context" not in body


def test_extract_call_body_preserves_text_when_no_prelude_to_strip() -> None:
    # A speaker-led call (Tesla-style) has no JSON-LD prelude and no
    # `Prepared Remarks:` header. The parser should not slice away its content.
    raw = "Elon Musk:\n" + (_long_body_paragraph() * 15) + "\nTravis Axelrod:\nFinancials."
    body = extract_call_body(raw)
    assert body.startswith("Elon Musk:")
    assert "Travis Axelrod" in body


def test_extract_call_body_does_not_slice_to_footer_operator() -> None:
    # If the only Operator line is in the last 20% of the text (a closing
    # footer like "And that concludes our Q&A"), the parser should NOT slice
    # there and lose 80% of the real content.
    main_content = "Sundar Pichai:\n" + (_long_body_paragraph() * 30)
    footer = "\nOperator:\nAnd that concludes our question and answer session."
    raw = main_content + footer
    body = extract_call_body(raw)
    assert body.startswith("Sundar Pichai:")
    assert len(body) > 2000


def test_extract_call_body_handles_empty_input() -> None:
    assert extract_call_body("") == ""


def test_is_likely_transcript_accepts_real_content() -> None:
    paragraph = (
        "Thanks for joining today. We delivered our best September quarter ever, "
        "with revenue of $94.9 billion, up 6% year over year. Services hit "
        "an all-time record and we're seeing strong customer response to "
        "Apple Intelligence across the installed base. "
    )
    body = (
        "Prepared Remarks:\n\n"
        "Operator\nWelcome to the Apple Q4 2024 earnings call.\n"
        "Tim Cook\n--\nChief Executive Officer\n"
        + (paragraph * 4)
    )
    assert is_likely_transcript(body) is True


def test_is_likely_transcript_rejects_too_short() -> None:
    assert is_likely_transcript("Operator\nWelcome.") is False


def test_is_likely_transcript_rejects_pure_metadata_dump() -> None:
    metadata = '"datePublished":"x","author":"y","publisher":"z"' * 50
    assert is_likely_transcript(metadata) is False


def test_is_likely_transcript_accepts_tesla_style_no_operator() -> None:
    # Tesla calls have no Operator header; just speaker names with colons.
    body = (
        "Elon Musk:\nThank you. We are at a critical inflection point for Tesla. "
        "And our strategy going forward as we bring AI into the real world is "
        "to scale humanoid robotics aggressively. "
        + "We see continued strong growth in Energy storage. " * 40
        + "\nTravis Axelrod:\nI'll cover the financials now. Revenue was up. "
        + "\nVaibhav Taneja:\nMargins expanded in the quarter. "
        + "\nElon Musk:\nThanks Vaibhav. On to questions. "
        + "\nAdam Jonas:\nGreat. Elon, on FSD adoption. "
        + "\nElon Musk:\nFSD is critical for our long-term strategy. "
    )
    assert len(body) >= 2000, f"test fixture too short: {len(body)}"
    assert is_likely_transcript(body) is True
