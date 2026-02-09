from __future__ import annotations

import pytest

from fraud_detection.case_trigger.taxonomy import (
    CaseTriggerTaxonomyError,
    ensure_source_class_allowed_for_trigger_type,
    ensure_supported_case_trigger_type,
    missing_required_evidence_ref_types,
)


def test_taxonomy_accepts_supported_trigger_type() -> None:
    assert ensure_supported_case_trigger_type("DECISION_ESCALATION") == "DECISION_ESCALATION"


def test_taxonomy_rejects_trigger_source_mismatch() -> None:
    with pytest.raises(CaseTriggerTaxonomyError):
        ensure_source_class_allowed_for_trigger_type("DECISION_ESCALATION", "AL_OUTCOME")


def test_taxonomy_detects_missing_required_evidence_refs() -> None:
    missing = missing_required_evidence_ref_types(
        "ACTION_FAILURE",
        ["ACTION_OUTCOME"],
    )
    assert missing == ("DLA_AUDIT_RECORD",)
