#!/usr/bin/env python3
"""Generate models_snapshot.json from the models.dev API.

Usage::

    # From project root:
    uv run python scripts/generate_models_snapshot.py

    # Or directly:
    PYTHONPATH=. python scripts/generate_models_snapshot.py

This fetches the latest model metadata from https://models.dev/api.json,
converts it to the internal ModelMetadata format, and writes the snapshot
to ``src/infrastructure/llm/models_snapshot.json``.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.infrastructure.llm.models_dev_fetcher import (
    convert_to_model_metadata,
    fetch_models_dev,
    generate_snapshot,
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger = logging.getLogger(__name__)
    logger.info("Fetching model data from models.dev...")

    raw = fetch_models_dev()
    models = convert_to_model_metadata(raw)
    path = generate_snapshot(models)

    logger.info("Generated snapshot with %d models at %s", len(models), path)

    # Summary by provider
    providers: dict[str, int] = {}
    for meta in models.values():
        p = meta.provider or "unknown"
        providers[p] = providers.get(p, 0) + 1
    reasoning_count = sum(1 for m in models.values() if m.reasoning)
    logger.info(
        "Providers: %s",
        ", ".join(f"{k}: {v}" for k, v in sorted(providers.items())),
    )
    logger.info("Reasoning models: %d / %d", reasoning_count, len(models))


if __name__ == "__main__":
    main()