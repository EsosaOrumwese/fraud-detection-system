"""Helpers for resolving full-token environment expressions with nested defaults."""

from __future__ import annotations

import os
from typing import Any


def resolve_env_token(value: Any) -> Any:
    """Resolve a full `${VAR}` or `${VAR:-default}` token, including nested defaults."""
    if not isinstance(value, str):
        return value
    token = value.strip()
    if not _looks_like_token(token):
        return value
    return _resolve_token(token)


def _looks_like_token(token: str) -> bool:
    return token.startswith("${") and token.endswith("}") and len(token) >= 4


def _resolve_token(token: str) -> str:
    inner = token[2:-1]
    key, default = _split_default(inner)
    key = key.strip()
    if not key:
        return ""
    resolved = os.getenv(key)
    if resolved not in (None, ""):
        return resolved
    if default is None:
        return ""
    default = default.strip()
    if _looks_like_token(default):
        return str(_resolve_token(default))
    return default


def _split_default(inner: str) -> tuple[str, str | None]:
    depth = 0
    i = 0
    limit = len(inner) - 1
    while i < limit:
        ch = inner[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == ":" and inner[i + 1] == "-" and depth == 0:
            return inner[:i], inner[i + 2 :]
        i += 1
    return inner, None
