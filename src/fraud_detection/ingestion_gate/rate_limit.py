"""Simple in-memory rate limiter."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from time import monotonic


@dataclass
class RateLimiter:
    max_per_minute: int
    _events: deque[float] = field(default_factory=deque)

    def allow(self) -> bool:
        if self.max_per_minute <= 0:
            return True
        now = monotonic()
        window_start = now - 60.0
        while self._events and self._events[0] < window_start:
            self._events.popleft()
        if len(self._events) >= self.max_per_minute:
            return False
        self._events.append(now)
        return True
