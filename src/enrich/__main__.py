"""Module entrypoint: `uv run python -m src.enrich all`."""

from __future__ import annotations

from src.enrich.cli import app

if __name__ == "__main__":
    app()
