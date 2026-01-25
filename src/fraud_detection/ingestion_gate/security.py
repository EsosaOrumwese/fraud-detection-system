"""Auth helpers for IG ingress."""

from __future__ import annotations

from pathlib import Path


def load_allowlist(path: str | None) -> list[str]:
    if not path:
        return []
    allowlist: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        allowlist.append(value)
    return allowlist


def authorize(auth_mode: str, token: str | None, allowlist: list[str]) -> tuple[bool, str | None]:
    mode = (auth_mode or "disabled").lower()
    if mode == "disabled":
        return True, None
    if mode == "api_key":
        if token and token in allowlist:
            return True, None
        return False, "UNAUTHORIZED"
    if mode == "jwt":
        return False, "AUTH_MODE_UNSUPPORTED"
    return False, "AUTH_MODE_UNKNOWN"
