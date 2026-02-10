"""Security helpers: auth allowlists and redaction."""

from __future__ import annotations

import re
from typing import Iterable


def is_authorized(actor: str | None, allowlist: Iterable[str], mode: str) -> bool:
    if mode.lower() == "disabled":
        return True
    if actor is None or actor.strip() == "":
        return False
    normalized = {item.strip() for item in allowlist if item.strip()}
    return actor in normalized


def redact_dsn(value: str) -> str:
    # Masks password in scheme://user:pass@host
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", value)


def redact_env(env: dict[str, str], sensitive_keys: Iterable[str] | None = None) -> dict[str, str]:
    keys = {key.upper() for key in (sensitive_keys or [])}
    redacted: dict[str, str] = {}
    for key, value in env.items():
        if key.upper() in keys or "SECRET" in key.upper() or "PASSWORD" in key.upper():
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted
