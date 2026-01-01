"""Helpers for formatting and parsing HashGate `_passed.flag` files."""

from __future__ import annotations

import re

_PASS_FLAG_RE = re.compile(r"^sha256_hex\s*=\s*([0-9a-f]{64})$", re.IGNORECASE)


def format_passed_flag(digest_hex: str) -> str:
    """Return the canonical `_passed.flag` contents for ``digest_hex``."""
    return f"sha256_hex={digest_hex}\n"


def parse_passed_flag(text: str) -> str:
    """Parse `_passed.flag` contents and return the declared digest."""
    match = _PASS_FLAG_RE.match(text.strip())
    if not match:
        raise ValueError("invalid _passed.flag contents")
    return match.group(1).lower()


__all__ = ["format_passed_flag", "parse_passed_flag"]
