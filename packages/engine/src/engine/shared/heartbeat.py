"""Shared heartbeat logger for long-running states."""

from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Iterator


def _resolve_interval_seconds() -> float:
    raw = os.environ.get("ENGINE_STATE_HEARTBEAT_SECS", "60")
    try:
        value = float(raw)
    except ValueError:
        value = 60.0
    return value


@contextmanager
def state_heartbeat(logger, label: str) -> Iterator[None]:
    """Emit a periodic 'still running' log while the wrapped block executes."""

    interval = _resolve_interval_seconds()
    if interval <= 0:
        yield
        return

    stop_event = threading.Event()
    start = time.monotonic()

    def _run() -> None:
        while not stop_event.wait(interval):
            elapsed = time.monotonic() - start
            logger.info("%s still running (elapsed=%.1fs)", label, elapsed)

    thread = threading.Thread(target=_run, name="engine_state_heartbeat", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=1.0)
