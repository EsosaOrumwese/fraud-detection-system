"""Decision Fabric event taxonomy and schema compatibility guards (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import re


SUPPORTED_DF_EVENT_TYPES: tuple[str, ...] = ("decision_response", "action_intent")

SCHEMA_MAJOR_BY_EVENT_TYPE: dict[str, int] = {
    "decision_response": 1,
    "action_intent": 1,
}

_SCHEMA_VERSION_RE = re.compile(r"^v(?P<major>\d+)(?:\.(?P<minor>\d+))?$")


class DecisionFabricTaxonomyError(ValueError):
    """Raised when DF event taxonomy or schema compatibility checks fail."""


@dataclass(frozen=True)
class SchemaVersion:
    raw: str
    major: int
    minor: int


def ensure_supported_event_schema(event_type: str, schema_version: str) -> SchemaVersion:
    normalized_event_type = str(event_type or "").strip()
    if normalized_event_type not in SUPPORTED_DF_EVENT_TYPES:
        raise DecisionFabricTaxonomyError(
            f"event_type not allowed for DF contract: {normalized_event_type!r}"
        )

    version = parse_schema_version(schema_version)
    supported_major = SCHEMA_MAJOR_BY_EVENT_TYPE[normalized_event_type]
    if version.major != supported_major:
        raise DecisionFabricTaxonomyError(
            "schema major mismatch (fail-closed): "
            f"event_type={normalized_event_type} expected=v{supported_major} got={version.raw}"
        )
    return version


def parse_schema_version(schema_version: str) -> SchemaVersion:
    text = str(schema_version or "").strip()
    match = _SCHEMA_VERSION_RE.fullmatch(text)
    if match is None:
        raise DecisionFabricTaxonomyError(
            f"schema_version must match v<major>[.<minor>] format; got {text!r}"
        )
    major = int(match.group("major"))
    minor = int(match.group("minor") or 0)
    return SchemaVersion(raw=text, major=major, minor=minor)
