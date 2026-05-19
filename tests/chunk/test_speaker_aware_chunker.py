"""Tests for src/chunk/speaker_aware_chunker.py.

Covers:
- Role classification from role-hint text (MF-style transcripts have `Name\\n--\\nRole`).
- Role inference from speaker name when role-hint is missing (Tesla-style transcripts).
- Parsing of Motley Fool format (the majority of our 41 calls).
- Parsing of Tesla format (no `--`, just `Name:`).
- Section flip from `prepared` to `qa` on the Q&A cue.
- Operator turns get the `Operator` role even though they have no role hint.
"""

from __future__ import annotations

from src.chunk.speaker_aware_chunker import (
    SpeakerTurn,
    classify_role,
    detect_format,
    parse_speaker_turns,
)


# --------------------------------------------------------------------------- #
# classify_role
# --------------------------------------------------------------------------- #


def test_classify_role_ceo_from_role_hint() -> None:
    assert classify_role("Chief Executive Officer") == "CEO"
    assert classify_role("President and Chief Executive Officer") == "CEO"
    assert classify_role("CEO") == "CEO"


def test_classify_role_cfo_from_role_hint() -> None:
    assert classify_role("Chief Financial Officer") == "CFO"
    assert classify_role("Senior Vice President, Chief Financial Officer") == "CFO"
    assert (
        classify_role("Chief Financial Officer, Executive Vice President") == "CFO"
    )


def test_classify_role_analyst_from_role_hint() -> None:
    assert classify_role("Analyst") == "Analyst"
    assert classify_role("Goldman Sachs -- Analyst") == "Analyst"
    assert classify_role("Senior Analyst, Morgan Stanley") == "Analyst"


def test_classify_role_ir_from_role_hint() -> None:
    assert classify_role("Director, Investor Relations") == "IR"
    assert classify_role("General Manager, Investor Relations") == "IR"


def test_classify_role_operator_when_speaker_is_operator() -> None:
    assert classify_role(None, speaker_name="Operator") == "Operator"


def test_classify_role_falls_back_to_other_when_unknown() -> None:
    assert classify_role(None, speaker_name="Some Random Person") == "Other"
    assert classify_role("Unknown Title") == "Other"


def test_classify_role_uses_exec_lookup_when_role_hint_missing() -> None:
    lookup = {"Elon Musk": "CEO", "Vaibhav Taneja": "CFO"}
    assert classify_role(None, speaker_name="Elon Musk", exec_lookup=lookup) == "CEO"
    assert classify_role(None, speaker_name="Vaibhav Taneja", exec_lookup=lookup) == "CFO"


def test_classify_role_prefers_role_hint_over_lookup() -> None:
    # If the transcript explicitly tags someone, trust the transcript.
    lookup = {"Elon Musk": "Other"}
    assert classify_role("Chief Executive Officer", speaker_name="Elon Musk", exec_lookup=lookup) == "CEO"


# --------------------------------------------------------------------------- #
# detect_format
# --------------------------------------------------------------------------- #


def test_detect_format_motley_fool_style() -> None:
    body = (
        "Operator\nWelcome.\n"
        "Tim Cook\n--\nChief Executive Officer\n\nThanks everyone.\n"
        "Luca Maestri\n--\nCFO\n\nRevenue was up.\n"
    )
    assert detect_format(body) == "mf"


def test_detect_format_tesla_style() -> None:
    body = (
        "Elon Musk:\nWe are at an inflection point.\n"
        "Vaibhav Taneja:\nFinancials look good.\n"
        "Travis Axelrod:\nQuestions now.\n"
    )
    assert detect_format(body) == "colon"


# --------------------------------------------------------------------------- #
# parse_speaker_turns — Motley Fool format
# --------------------------------------------------------------------------- #


def test_parse_mf_returns_speaker_turns_with_roles() -> None:
    body = (
        "Operator\nGood afternoon and welcome to the call.\n\n"
        "Tim Cook\n--\nChief Executive Officer\n\n"
        "Thanks for joining today. We delivered a strong September quarter.\n\n"
        "Luca Maestri\n--\nChief Financial Officer\n\n"
        "Revenue was 94.9 billion, up 6% year over year.\n\n"
        "Operator\nWe will now begin the question-and-answer session.\n\n"
        "Michael Ng\n--\nGoldman Sachs -- Analyst\n\n"
        "On Apple Intelligence, can you talk about adoption?\n\n"
        "Tim Cook\n--\nChief Executive Officer\n\n"
        "Michael, we see strong early engagement."
    )
    turns = parse_speaker_turns(body)
    # 6 turns total: Operator, Tim, Luca, Operator (q&a), Analyst, Tim
    assert len(turns) == 6
    assert turns[0].speaker_name == "Operator"
    assert turns[0].role == "Operator"
    assert turns[1].speaker_name == "Tim Cook"
    assert turns[1].role == "CEO"
    assert turns[2].speaker_name == "Luca Maestri"
    assert turns[2].role == "CFO"
    assert turns[4].speaker_name == "Michael Ng"
    assert turns[4].role == "Analyst"


def test_parse_mf_section_flips_to_qa_after_qa_cue() -> None:
    body = (
        "Operator\nGood afternoon.\n\n"
        "Tim Cook\n--\nChief Executive Officer\n\nPrepared remark here.\n\n"
        "Operator\nWe will now begin the question-and-answer session.\n\n"
        "Michael Ng\n--\nGoldman Sachs -- Analyst\n\nFirst question.\n\n"
        "Tim Cook\n--\nChief Executive Officer\n\nAnswer to first question."
    )
    turns = parse_speaker_turns(body)
    prepared_turns = [t for t in turns if t.section == "prepared"]
    qa_turns = [t for t in turns if t.section == "qa"]
    assert len(prepared_turns) >= 2, "operator + Tim Cook prepared remarks"
    assert len(qa_turns) >= 2, "analyst question + Tim's answer"
    # The Q&A operator-cue turn itself can be either side; the analyst MUST be qa.
    analyst_turns = [t for t in turns if t.speaker_name == "Michael Ng"]
    assert all(t.section == "qa" for t in analyst_turns)


def test_parse_mf_preserves_text_content() -> None:
    body = (
        "Tim Cook\n--\nChief Executive Officer\n\n"
        "We delivered our best September quarter ever, with revenue of $94.9 billion."
    )
    turns = parse_speaker_turns(body)
    assert len(turns) == 1
    assert "$94.9 billion" in turns[0].text


# --------------------------------------------------------------------------- #
# parse_speaker_turns — Tesla format
# --------------------------------------------------------------------------- #


def test_parse_colon_returns_turns_with_lookup_roles() -> None:
    body = (
        "Elon Musk:\nThank you. We are at a critical inflection point. We see continued momentum.\n"
        "Vaibhav Taneja:\nMargins expanded in the quarter and free cash flow was strong.\n"
        "Travis Axelrod:\nOn to the question and answer portion.\n"
        "Adam Jonas:\nElon, on FSD adoption, what's the trajectory?\n"
        "Elon Musk:\nFSD adoption is accelerating across the fleet."
    )
    lookup = {
        "Elon Musk": "CEO",
        "Vaibhav Taneja": "CFO",
        "Travis Axelrod": "IR",
    }
    turns = parse_speaker_turns(body, exec_lookup=lookup)
    assert len(turns) == 5
    assert turns[0].role == "CEO"
    assert turns[1].role == "CFO"
    assert turns[2].role == "IR"
    # Adam Jonas isn't in the lookup; the parser falls back to Analyst
    # (heuristic: any speaker after the QA marker who isn't an exec is an Analyst).
    assert turns[3].role == "Analyst"
    assert turns[4].role == "CEO"


def test_parse_colon_section_flips_on_question_cue() -> None:
    body = (
        "Elon Musk:\nOpening remarks about our strategy and product roadmap.\n"
        "Travis Axelrod:\nWe'll now move on to questions from analysts.\n"
        "Adam Jonas:\nQuestion about robotaxi.\n"
        "Elon Musk:\nRobotaxi is on track."
    )
    lookup = {"Elon Musk": "CEO", "Travis Axelrod": "IR"}
    turns = parse_speaker_turns(body, exec_lookup=lookup)
    qa_turns = [t for t in turns if t.section == "qa"]
    # At minimum the analyst Adam Jonas and Elon's response are in qa.
    qa_speakers = {t.speaker_name for t in qa_turns}
    assert "Adam Jonas" in qa_speakers
    assert "Elon Musk" in qa_speakers


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #


def test_parse_empty_body_returns_empty_list() -> None:
    assert parse_speaker_turns("") == []


def test_parse_turn_positions_are_sequential() -> None:
    body = (
        "Operator\nWelcome.\n\n"
        "Tim Cook\n--\nCEO\n\nFirst remark.\n\n"
        "Luca Maestri\n--\nCFO\n\nSecond remark."
    )
    turns = parse_speaker_turns(body)
    assert [t.position for t in turns] == list(range(len(turns)))


def test_speaker_turn_is_immutable_dataclass() -> None:
    t = SpeakerTurn(
        speaker_name="Tim Cook",
        role="CEO",
        role_hint="Chief Executive Officer",
        text="Hello",
        section="prepared",
        position=0,
    )
    import dataclasses

    assert dataclasses.is_dataclass(t)
    # frozen=True means setting an attribute raises
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        t.text = "changed"  # type: ignore[misc]
