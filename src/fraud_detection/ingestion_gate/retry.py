"""Retry helpers with bounded backoff."""

from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


def with_retry(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.2,
    max_delay_seconds: float = 2.0,
    on_retry: Callable[[int, float, Exception], None] | None = None,
) -> T:
    if attempts <= 1:
        return func()
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            delay = min(base_delay_seconds * (2 ** (attempt - 1)), max_delay_seconds)
            if on_retry:
                on_retry(attempt, delay, exc)
            time.sleep(delay)
    if last_exc is None:
        raise RuntimeError("RETRY_FAILED")
    raise last_exc
