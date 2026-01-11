"""Time helpers aligned to engine schema requirements."""

from __future__ import annotations

import datetime as dt
import time


def utc_now_rfc3339_micro() -> str:
    """Return UTC timestamp with exactly 6 fractional digits and trailing Z."""
    now = dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def utc_now_ns() -> int:
    """Return UTC time as nanoseconds since the Unix epoch."""
    return time.time_ns()
