"""Contextual retrieval prefix (Anthropic, 2024).

Each chunk gets a short context line prepended **at embed time only**. The
stored `text` column keeps the raw chunk. The prefix lifts recall@5 by an
expected 35-50% on hard queries because the embedding now knows what call,
speaker, and section it came from without depending on the chunk text
containing those entities verbatim.

Format used in this project:

    "From {company}'s {Q#} {year} earnings call, {speaker} ({role}) in {Section}: {chunk_text}"

Where Section is "prepared remarks" or "Q&A". Example:

    "From Apple's Q3 2024 earnings call, Tim Cook (CEO) in prepared remarks:
     We delivered our best September quarter ever..."
"""

from __future__ import annotations

_SECTION_LABEL: dict[str, str] = {
    "prepared": "prepared remarks",
    "qa": "Q&A",
}


def build_prefix(
    *,
    company: str,
    ticker: str,
    quarter: str,
    year: int,
    speaker_name: str,
    role: str,
    section: str,
) -> str:
    """Return the contextual prefix line (without the chunk text appended)."""
    if section not in _SECTION_LABEL:
        raise ValueError(
            f"Unknown section {section!r}; expected one of {sorted(_SECTION_LABEL)}"
        )
    section_label = _SECTION_LABEL[section]
    return (
        f"From {company}'s {quarter} {year} earnings call, "
        f"{speaker_name} ({role}) in {section_label}:"
    )


def prepend_prefix(
    *,
    chunk_text: str,
    company: str,
    ticker: str,
    quarter: str,
    year: int,
    speaker_name: str,
    role: str,
    section: str,
) -> str:
    """Return prefix + chunk_text, separated by a single space."""
    prefix = build_prefix(
        company=company,
        ticker=ticker,
        quarter=quarter,
        year=year,
        speaker_name=speaker_name,
        role=role,
        section=section,
    )
    return f"{prefix} {chunk_text}"
