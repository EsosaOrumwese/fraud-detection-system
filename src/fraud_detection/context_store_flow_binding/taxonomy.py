"""Context Store + FlowBinding taxonomy guards (Phase 1)."""

from __future__ import annotations


SUPPORTED_AUTHORITATIVE_FLOW_BINDING_EVENT_TYPES: tuple[str, ...] = (
    "s2_flow_anchor_baseline_6B",
    "s3_flow_anchor_with_fraud_6B",
)


class ContextStoreFlowBindingTaxonomyError(ValueError):
    """Raised when CSFB taxonomy checks fail."""


def ensure_authoritative_flow_binding_event_type(event_type: str) -> str:
    normalized = str(event_type or "").strip()
    if normalized not in SUPPORTED_AUTHORITATIVE_FLOW_BINDING_EVENT_TYPES:
        raise ContextStoreFlowBindingTaxonomyError(
            "authoritative flow-binding source event_type not allowed: "
            f"{normalized!r}"
        )
    return normalized
