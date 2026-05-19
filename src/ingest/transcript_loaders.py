"""Ingestion orchestrator.

Takes a filtered DataFrame of Rogersurf rows (Mag 7 in window) and writes
one JSON file per call into `data/raw/`. Each JSON carries the metadata
fields the downstream chunker needs.

Per Step 1 of the build guide: output is one JSON per call with
`{ticker, company, quarter, year, date, full_text, source_url, title}`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from src.ingest.hf_source import normalize_quarter
from src.ingest.parser import extract_call_body, is_likely_transcript

logger = logging.getLogger(__name__)


def output_path_for_call(
    output_dir: Path,
    *,
    ticker: str,
    year: int,
    quarter: str,
) -> Path:
    """Stable filename for a call's JSON. Mirrors the (ticker, year, quarter) key."""
    q = normalize_quarter(quarter)
    return output_dir / f"{ticker.upper()}_{year}_{q}.json"


def _build_record(row: pd.Series) -> dict[str, object]:
    """Convert a Rogersurf row into the on-disk JSON shape."""
    raw_text = str(row.get("transcript_clean") or row.get("transcript") or "")
    body = extract_call_body(raw_text)
    content_hash = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
    return {
        "ticker": str(row["ticker"]).upper(),
        "company": str(row.get("company") or row["ticker"]),
        "quarter": normalize_quarter(row["quarter"]),
        "year": int(row["earnings_year"]),
        "date": str(row["call_date"]),
        "title": str(row.get("title", "")),
        "source_url": str(row.get("source_url", "")),
        "content_sha256": content_hash,
        "full_text": body,
    }


def save_transcripts(
    df: pd.DataFrame,
    output_dir: Path | str,
) -> list[Path]:
    """Write one JSON per row. Skip rows whose body fails `is_likely_transcript`.

    Returns the list of paths actually written. Existing files are overwritten;
    the ingestion is idempotent and safe to re-run.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    skipped = 0
    for _, row in df.iterrows():
        record = _build_record(row)
        if not is_likely_transcript(record["full_text"]):  # type: ignore[arg-type]
            logger.warning(
                "skipping %s %s %s: body too short or not a transcript",
                record["ticker"],
                record["year"],
                record["quarter"],
            )
            skipped += 1
            continue
        path = output_path_for_call(
            output_dir,
            ticker=str(record["ticker"]),
            year=int(record["year"]),  # type: ignore[arg-type]
            quarter=str(record["quarter"]),
        )
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(path)

    logger.info("wrote %d transcripts; skipped %d", len(written), skipped)
    return written


def load_saved_transcripts(input_dir: Path | str) -> Iterable[dict[str, object]]:
    """Iterate the JSON files produced by `save_transcripts`."""
    for path in sorted(Path(input_dir).glob("*.json")):
        yield json.loads(path.read_text(encoding="utf-8"))
