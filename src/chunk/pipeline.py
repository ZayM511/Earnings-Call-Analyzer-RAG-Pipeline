"""Chunking pipeline orchestrator.

Reads `data/raw/{TICKER}_{YYYY}_{Q#}.json`, runs the speaker-aware parser +
size-bounds, and writes `data/interim/{TICKER}_{YYYY}_{Q#}_chunks.jsonl`.

Each line in the output JSONL is one chunk:

    {
      "ticker": "AAPL",
      "company": "Apple",
      "quarter": "Q4",
      "year": 2024,
      "call_date": "2024-10-31",
      "speaker_name": "Tim Cook",
      "speaker_role": "CEO",
      "section": "prepared",
      "chunk_index": 5,
      "text": "We delivered record September quarter...",
      "approx_tokens": 412
    }

Enrichment (hedging_score, sentiment, topics) and embedding happen in Phase 6
and Phase 7 respectively. This phase stops at the JSONL on disk.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.chunk.exec_lookup import MAG7_EXEC_LOOKUP
from src.chunk.merge_split import apply_size_bounds, estimate_tokens
from src.chunk.speaker_aware_chunker import SpeakerTurn, parse_speaker_turns

logger = logging.getLogger(__name__)


def chunk_call(
    raw_call: dict[str, Any],
    *,
    floor: int = 200,
    ceiling: int = 600,
) -> list[dict[str, Any]]:
    """Produce a list of chunk records from one raw transcript JSON object.

    `raw_call` is the dict shape produced by `src/ingest/transcript_loaders.py`:
    {ticker, company, quarter, year, date, full_text, ...}.
    """
    body = raw_call["full_text"]
    turns: list[SpeakerTurn] = parse_speaker_turns(body, exec_lookup=MAG7_EXEC_LOOKUP)
    bounded = apply_size_bounds(turns, floor=floor, ceiling=ceiling)

    chunks: list[dict[str, Any]] = []
    for chunk_idx, turn in enumerate(bounded):
        chunks.append(
            {
                "ticker": raw_call["ticker"],
                "company": raw_call["company"],
                "quarter": raw_call["quarter"],
                "year": int(raw_call["year"]),
                "call_date": str(raw_call["date"]),
                "speaker_name": turn.speaker_name,
                "speaker_role": turn.role,
                "section": turn.section,
                "chunk_index": chunk_idx,
                "text": turn.text,
                "approx_tokens": estimate_tokens(turn.text),
                "content_sha256": hashlib.sha256(turn.text.encode("utf-8", errors="replace")).hexdigest(),
            }
        )
    return chunks


def chunk_all_in_directory(
    raw_dir: Path | str,
    out_dir: Path | str,
    *,
    floor: int = 200,
    ceiling: int = 600,
) -> dict[str, int]:
    """Read every `data/raw/*.json` and write a `_chunks.jsonl` per call.

    Returns a summary `{"calls_chunked": N, "total_chunks": M}`.
    """
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    calls = 0
    total = 0
    for raw_path in sorted(raw_dir.glob("*.json")):
        raw_call = json.loads(raw_path.read_text(encoding="utf-8"))
        chunks = chunk_call(raw_call, floor=floor, ceiling=ceiling)
        out_path = out_dir / f"{raw_path.stem}_chunks.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        calls += 1
        total += len(chunks)
        logger.info(
            "chunked %s: %d chunks (avg %d tokens)",
            raw_path.stem,
            len(chunks),
            sum(c["approx_tokens"] for c in chunks) // max(1, len(chunks)),
        )

    return {"calls_chunked": calls, "total_chunks": total}


def load_chunked_jsonl(path: Path | str) -> Iterable[dict[str, Any]]:
    """Iterate the chunks JSONL produced by `chunk_all_in_directory`."""
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
