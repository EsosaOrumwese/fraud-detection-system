"""IEG identity + dedupe identifiers."""

from __future__ import annotations

import hashlib
from typing import Any

from .hints import IdentityHint


def dedupe_key(platform_run_id: str, scenario_run_id: str, class_name: str, event_id: str) -> str:
    payload = f"{platform_run_id}:{scenario_run_id}:{class_name}:{event_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def entity_id_from_hint(hint: IdentityHint, pins: dict[str, Any]) -> str:
    if hint.entity_id:
        return hint.entity_id
    scope = _scope_key(pins)
    payload = f"{hint.entity_type}:{hint.identifier_type}:{hint.identifier_value}:{scope}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _scope_key(pins: dict[str, Any]) -> str:
    tokens = [
        str(pins.get("platform_run_id") or ""),
        pins.get("manifest_fingerprint") or "",
        pins.get("parameter_hash") or "",
        str(pins.get("seed") or ""),
        str(pins.get("scenario_id") or ""),
        str(pins.get("scenario_run_id") or ""),
        str(pins.get("run_id") or ""),
    ]
    return "|".join(tokens)
