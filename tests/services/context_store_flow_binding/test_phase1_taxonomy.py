from __future__ import annotations

import pytest

from fraud_detection.context_store_flow_binding.taxonomy import (
    ContextStoreFlowBindingTaxonomyError,
    ensure_authoritative_flow_binding_event_type,
)


def test_authoritative_event_type_accepts_allowed_values() -> None:
    assert ensure_authoritative_flow_binding_event_type("s2_flow_anchor_baseline_6B") == "s2_flow_anchor_baseline_6B"
    assert ensure_authoritative_flow_binding_event_type("s3_flow_anchor_with_fraud_6B") == "s3_flow_anchor_with_fraud_6B"


def test_authoritative_event_type_rejects_unknown_values() -> None:
    with pytest.raises(ContextStoreFlowBindingTaxonomyError):
        ensure_authoritative_flow_binding_event_type("arrival_events_5B")
