"""Shared corridor anomaly taxonomy mapping."""

from __future__ import annotations

from typing import Iterable


ANOMALY_SCHEMA_POLICY_MISSING = "SCHEMA_POLICY_MISSING"
ANOMALY_PUBLISH_AMBIGUOUS = "PUBLISH_AMBIGUOUS"
ANOMALY_REPLAY_BASIS_MISMATCH = "REPLAY_BASIS_MISMATCH"
ANOMALY_REF_ACCESS_DENIED = "REF_ACCESS_DENIED"
ANOMALY_INCOMPATIBILITY = "INCOMPATIBILITY"
ANOMALY_UNKNOWN = "UNKNOWN"


def classify_anomaly(reason_code: str | None, *, reason_codes: Iterable[str] | None = None) -> str:
    primary = _upper(reason_code)
    all_codes = {primary} if primary else set()
    if reason_codes:
        all_codes.update({_upper(item) for item in reason_codes if _upper(item)})

    if _has_prefix(all_codes, "REF_ACCESS_DENIED"):
        return ANOMALY_REF_ACCESS_DENIED
    if _has_prefix(all_codes, "PUBLISH_AMBIGUOUS") or _has_prefix(all_codes, "IG_PUSH_RETRY_EXHAUSTED"):
        return ANOMALY_PUBLISH_AMBIGUOUS
    if _has_prefix(all_codes, "REPLAY_DIVERGENCE") or _has_prefix(all_codes, "DLA_INTAKE_REPLAY_DIVERGENCE"):
        return ANOMALY_REPLAY_BASIS_MISMATCH
    if _has_prefix(all_codes, "SCHEMA_") or _has_prefix(all_codes, "PINS_MISSING"):
        return ANOMALY_SCHEMA_POLICY_MISSING
    if _has_prefix(all_codes, "FEATURE_GROUP_VERSION_MISMATCH") or _has_prefix(
        all_codes, "CAPABILITY_MISMATCH"
    ) or _has_prefix(all_codes, "ACTIVE_BUNDLE_INCOMPATIBLE"):
        return ANOMALY_INCOMPATIBILITY
    return ANOMALY_UNKNOWN


def _has_prefix(values: set[str], prefix: str) -> bool:
    target = prefix.upper()
    return any(item.startswith(target) for item in values)


def _upper(value: str | None) -> str:
    return str(value or "").strip().upper()
