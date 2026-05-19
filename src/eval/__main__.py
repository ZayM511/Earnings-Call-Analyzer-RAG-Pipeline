"""Module entrypoint: `uv run python -m src.eval baseline`."""

from __future__ import annotations

from src.eval.cli import app

if __name__ == "__main__":
    app()
