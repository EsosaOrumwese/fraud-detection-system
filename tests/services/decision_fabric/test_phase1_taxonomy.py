from __future__ import annotations

import pytest

from fraud_detection.decision_fabric.taxonomy import (
    DecisionFabricTaxonomyError,
    ensure_supported_event_schema,
    parse_schema_version,
)


def test_parse_schema_version_supports_major_minor() -> None:
    version = parse_schema_version("v1.3")
    assert version.major == 1
    assert version.minor == 3


def test_ensure_supported_event_schema_accepts_v1() -> None:
    version = ensure_supported_event_schema("decision_response", "v1")
    assert version.major == 1


def test_ensure_supported_event_schema_rejects_unknown_event_type() -> None:
    with pytest.raises(DecisionFabricTaxonomyError):
        ensure_supported_event_schema("unknown_event", "v1")


def test_ensure_supported_event_schema_rejects_major_mismatch_fail_closed() -> None:
    with pytest.raises(DecisionFabricTaxonomyError):
        ensure_supported_event_schema("action_intent", "v2")


def test_parse_schema_version_rejects_invalid_format() -> None:
    with pytest.raises(DecisionFabricTaxonomyError):
        parse_schema_version("1.0")
