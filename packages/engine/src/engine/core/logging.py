"""Logging helpers for the engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


_CONFIGURED = False
_FILE_HANDLERS: dict[str, logging.Handler] = {}
_LOG_FORMAT = "%(asctime)s,%(msecs)03d [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for CLI/runner usage."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
    )
    _CONFIGURED = True


def add_file_handler(path: Path, level: int = logging.INFO) -> None:
    """Add a file handler for run-scoped logs once per path."""
    configure_logging(level=level)
    resolved = str(path.resolve())
    if resolved in _FILE_HANDLERS:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            _LOG_FORMAT,
            datefmt=_DATE_FORMAT,
        )
    )
    logging.getLogger().addHandler(handler)
    _FILE_HANDLERS[resolved] = handler


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Return a configured logger with optional level override."""
    configure_logging()
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger
