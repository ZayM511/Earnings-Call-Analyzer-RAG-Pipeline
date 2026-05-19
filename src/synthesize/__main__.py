"""Module entrypoint: `uv run python -m src.synthesize ask "..."`."""

from __future__ import annotations

from src.synthesize.cli import app

if __name__ == "__main__":
    app()
