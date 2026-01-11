"""Logging helpers for the engine."""

from __future__ import annotations

import logging
from typing import Optional


_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for CLI/runner usage."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)sZ %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    _CONFIGURED = True


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Return a configured logger with optional level override."""
    configure_logging()
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger
