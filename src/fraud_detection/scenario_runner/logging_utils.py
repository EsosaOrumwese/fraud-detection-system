"""Logging helpers for Scenario Runner."""

from __future__ import annotations

import logging
import os
from pathlib import Path


class NarrativeFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if record.levelno >= logging.WARNING:
            return True
        if getattr(record, "narrative", False):
            return True
        if record.name.startswith("fraud_detection.platform_narrative"):
            return True
        return False


def configure_logging(level: int = logging.INFO, log_paths: list[str] | None = None) -> None:
    """Configure default logging if no handlers are present."""
    root = logging.getLogger()
    if root.handlers:
        return
    handlers: list[logging.Handler] = []
    handlers.append(logging.StreamHandler())

    narrative_path = log_paths[0] if log_paths else None
    if narrative_path:
        path = Path(narrative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        narrative_handler = logging.FileHandler(path, encoding="utf-8")
        narrative_handler.addFilter(NarrativeFilter())
        handlers.append(narrative_handler)

    component = (os.getenv("PLATFORM_COMPONENT") or "").strip()
    if component:
        try:
            from fraud_detection.platform_runtime import platform_run_root

            run_root = platform_run_root(create_if_missing=True)
            if run_root:
                component_dir = Path(run_root) / component
                component_dir.mkdir(parents=True, exist_ok=True)
                component_path = component_dir / f"{component}.log"
                handlers.append(logging.FileHandler(component_path, encoding="utf-8"))
        except Exception:
            pass

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
