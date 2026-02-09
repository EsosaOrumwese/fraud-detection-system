from __future__ import annotations

import re

from fraud_detection.decision_fabric.worker import _flow_id, _utc_now


def test_worker_flow_id_prefers_explicit_flow_id() -> None:
    envelope = {
        "flow_id": "envelope-flow",
        "payload": {"flow_id": "payload-flow", "event_id": "evt-1"},
    }
    assert _flow_id(envelope) == "payload-flow"


def test_worker_flow_id_uses_envelope_flow_id_when_payload_missing() -> None:
    envelope = {"flow_id": "envelope-flow", "payload": {}}
    assert _flow_id(envelope) == "envelope-flow"


def test_worker_flow_id_does_not_fallback_to_event_id() -> None:
    envelope = {"payload": {"event_id": "evt-1"}}
    assert _flow_id(envelope) is None


def test_worker_utc_now_emits_canonical_zulu_timestamp() -> None:
    stamp = _utc_now()
    assert re.fullmatch(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$", stamp)
