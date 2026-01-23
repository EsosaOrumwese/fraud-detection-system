"""Time helpers aligned to engine schema requirements."""

from __future__ import annotations

import datetime as dt
import time
from typing import Any, Optional


def utc_now_rfc3339_micro() -> str:
    """Return UTC timestamp with exactly 6 fractional digits and trailing Z."""
    now = dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def utc_now_ns() -> int:
    """Return UTC time as nanoseconds since the Unix epoch."""
    return time.time_ns()


def parse_rfc3339(value: Any) -> Optional[dt.datetime]:
    """Parse RFC3339 timestamp string into a timezone-aware datetime."""
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def utc_day_from_receipt(receipt: Any) -> str:
    """Return YYYY-MM-DD derived from run_receipt.created_utc, fallback to now."""
    created = None
    if isinstance(receipt, dict):
        created = parse_rfc3339(receipt.get("created_utc"))
    if created is None:
        created = dt.datetime.now(dt.timezone.utc)
    return created.strftime("%Y-%m-%d")
