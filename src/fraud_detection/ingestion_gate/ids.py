"""Deterministic identifiers for IG."""

from __future__ import annotations

import hashlib
from typing import Any

from .errors import IngestionError


def dedupe_key(platform_run_id: str, event_class: str, event_id: str) -> str:
    return hashlib.sha256(f"{platform_run_id}:{event_class}:{event_id}".encode("utf-8")).hexdigest()


def derive_engine_event_id(
    output_id: str,
    primary_keys: list[str],
    row: dict[str, Any],
    pins: dict[str, Any],
) -> str:
    parts: list[str] = [output_id]
    for key in primary_keys:
        value = row.get(key)
        if value is None:
            raise IngestionError("PRIMARY_KEY_MISSING", key)
        parts.append(str(value))
    for pin_key in ("manifest_fingerprint", "parameter_hash", "seed", "scenario_id"):
        value = pins.get(pin_key)
        if value is not None:
            parts.append(str(value))
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def receipt_id_from(event_id: str, decision: str) -> str:
    return hashlib.sha256(f"{decision}:{event_id}".encode("utf-8")).hexdigest()[:32]


def quarantine_id_from(event_id: str) -> str:
    return hashlib.sha256(f"QUARANTINE:{event_id}".encode("utf-8")).hexdigest()[:32]
