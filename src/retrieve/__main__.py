"""Module entrypoint: `uv run python -m src.retrieve query "..."`."""

from __future__ import annotations

from src.retrieve.cli import app

if __name__ == "__main__":
    app()
