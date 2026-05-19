"""CLI entrypoint: `uv run python -m src.ingest --all-mag7`.

Wraps `src.ingest.cli:app` so the package is callable as a module.
"""

from __future__ import annotations

from src.ingest.cli import app

if __name__ == "__main__":
    app()
