"""Module entrypoint: `uv run python -m src.chunk all`."""

from __future__ import annotations

from src.chunk.cli import app

if __name__ == "__main__":
    app()
