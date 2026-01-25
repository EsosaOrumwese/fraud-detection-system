"""Logging helpers for Ingestion Gate."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(level: int = logging.INFO, log_path: str | None = None) -> None:
    """Configure default logging if no handlers are present."""
    root = logging.getLogger()
    if root.handlers:
        return
    handlers = None
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers = [
            logging.StreamHandler(),
            logging.FileHandler(path, encoding="utf-8"),
        ]
    kwargs = {
        "level": level,
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }
    if handlers:
        kwargs["handlers"] = handlers
    logging.basicConfig(**kwargs)
