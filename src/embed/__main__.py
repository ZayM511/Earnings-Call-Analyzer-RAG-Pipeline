"""Module entrypoint: `uv run python -m src.embed all`."""

from __future__ import annotations

from src.embed.cli import app

if __name__ == "__main__":
    app()
