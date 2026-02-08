"""Auth helpers for IG ingress."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import os
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


@dataclass(frozen=True)
class AuthContext:
    actor_id: str
    source_type: str
    auth_mode: str
    principal: str


def authorize(
    auth_mode: str,
    token: str | None,
    allowlist: list[str],
    *,
    service_token_secrets: list[str] | None = None,
) -> tuple[bool, str | None, AuthContext | None]:
    mode = (auth_mode or "disabled").lower()
    if mode == "disabled":
        context = AuthContext(
            actor_id="SYSTEM::ANONYMOUS",
            source_type="SYSTEM",
            auth_mode=mode,
            principal="ANONYMOUS",
        )
        return True, None, context
    if mode == "api_key":
        if token and token in allowlist:
            context = AuthContext(
                actor_id=_to_actor_id(token),
                source_type="SYSTEM",
                auth_mode=mode,
                principal=token,
            )
            return True, None, context
        return False, "UNAUTHORIZED", None
    if mode == "service_token":
        principal, reason = _verify_service_token(token, service_token_secrets)
        if not principal:
            return False, reason or "UNAUTHORIZED", None
        actor_id = _to_actor_id(principal)
        allowset = {item.strip() for item in allowlist if str(item).strip()}
        if allowset and principal not in allowset and actor_id not in allowset:
            return False, "UNAUTHORIZED", None
        context = AuthContext(
            actor_id=actor_id,
            source_type="SYSTEM",
            auth_mode=mode,
            principal=principal,
        )
        return True, None, context
    if mode == "jwt":
        return False, "AUTH_MODE_UNSUPPORTED", None
    return False, "AUTH_MODE_UNKNOWN", None


def build_service_token(principal: str, secret: str) -> str:
    identity = str(principal or "").strip()
    key = str(secret or "").strip()
    if not identity:
        raise ValueError("principal is required")
    if not key:
        raise ValueError("secret is required")
    principal_b64 = base64.urlsafe_b64encode(identity.encode("utf-8")).decode("ascii").rstrip("=")
    signature = _token_signature(identity, key)
    return f"st.v1.{principal_b64}.{signature}"


def _verify_service_token(
    token: str | None,
    service_token_secrets: list[str] | None,
) -> tuple[str | None, str | None]:
    raw = str(token or "").strip()
    if not raw:
        return None, "UNAUTHORIZED"
    parts = raw.split(".")
    if len(parts) != 4 or parts[0] != "st" or parts[1] != "v1":
        return None, "UNAUTHORIZED"
    principal = _decode_principal(parts[2])
    if not principal:
        return None, "UNAUTHORIZED"
    secrets = _service_token_secrets(service_token_secrets)
    if not secrets:
        return None, "AUTH_SERVICE_TOKEN_SECRET_MISSING"
    provided = parts[3].strip().lower()
    for secret in secrets:
        expected = _token_signature(principal, secret)
        if hmac.compare_digest(provided, expected):
            return principal, None
    return None, "UNAUTHORIZED"


def _decode_principal(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    pad = "=" * ((4 - len(text) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode((text + pad).encode("ascii")).decode("utf-8")
    except Exception:
        return None
    identity = decoded.strip()
    return identity or None


def _token_signature(principal: str, secret: str) -> str:
    raw = f"v1|{principal}"
    return hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _service_token_secrets(explicit: list[str] | None) -> list[str]:
    if explicit:
        cleaned = [item.strip() for item in explicit if str(item).strip()]
        if cleaned:
            return cleaned
    raw = (os.getenv("IG_SERVICE_TOKEN_SECRETS") or "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _to_actor_id(principal: str) -> str:
    text = str(principal or "").strip()
    if not text:
        return "SYSTEM::UNKNOWN"
    if text.upper().startswith("SYSTEM::") or text.upper().startswith("HUMAN::"):
        return text
    return f"SYSTEM::{text}"
