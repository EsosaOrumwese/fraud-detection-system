from __future__ import annotations

import pytest
import requests

from fraud_detection.decision_fabric.publish import (
    PUBLISH_ADMIT,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
    DecisionFabricIgPublisher,
    DecisionFabricPublishError,
)


class _StubResponse:
    def __init__(self, status_code: int, body: dict[str, object] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text

    def json(self) -> dict[str, object]:
        return dict(self._body)


class _StubSession:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def post(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        if not self._responses:
            raise AssertionError("no stub responses configured")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


def _envelope(event_id: str, event_type: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "schema_version": "v1",
        "ts_utc": "2026-02-07T11:00:00.000000Z",
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "seed": 7,
        "scenario_id": "fraud_synth_v1",
        "platform_run_id": "platform_20260207T110000Z",
        "scenario_run_id": "c" * 32,
        "payload": {"k": "v"},
    }


def _publisher(session: _StubSession) -> DecisionFabricIgPublisher:
    return DecisionFabricIgPublisher(
        ig_ingest_url="http://localhost:8081",
        max_attempts=3,
        retry_base_delay_ms=0,
        retry_max_delay_ms=0,
        timeout_seconds=0.1,
        session=session,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("decision", [PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE])
def test_publish_maps_ig_decision_codes(decision: str) -> None:
    session = _StubSession(
        [
            _StubResponse(
                200,
                {
                    "decision": decision,
                    "receipt": {"receipt_id": "r1"},
                    "receipt_ref": "runs/fraud-platform/x/ig/receipts/r1.json",
                },
            )
        ]
    )
    publisher = _publisher(session)
    record = publisher.publish_envelope(_envelope("evt_1", "decision_response"))
    assert record.decision == decision
    assert record.receipt["receipt_id"] == "r1"


def test_publish_retries_on_transient_failures() -> None:
    session = _StubSession(
        [
            requests.Timeout(),
            _StubResponse(500, text="internal error"),
            _StubResponse(200, {"decision": PUBLISH_ADMIT, "receipt": {"receipt_id": "r2"}}),
        ]
    )
    publisher = _publisher(session)
    record = publisher.publish_envelope(_envelope("evt_2", "decision_response"))
    assert record.decision == PUBLISH_ADMIT
    assert session.calls == 3


def test_publish_fails_closed_on_unknown_ig_decision() -> None:
    session = _StubSession([_StubResponse(200, {"decision": "UNKNOWN", "receipt": {"receipt_id": "r3"}})])
    publisher = _publisher(session)
    with pytest.raises(DecisionFabricPublishError, match="IG_DECISION_UNKNOWN"):
        publisher.publish_envelope(_envelope("evt_3", "decision_response"))


def test_publish_batch_halts_when_decision_quarantined() -> None:
    session = _StubSession([_StubResponse(200, {"decision": PUBLISH_QUARANTINE, "receipt": {"receipt_id": "r4"}})])
    publisher = _publisher(session)
    result = publisher.publish_decision_and_intents(
        decision_envelope=_envelope("evt_4", "decision_response"),
        action_envelopes=(_envelope("evt_5", "action_intent"),),
    )
    assert result.halted is True
    assert result.halt_reason == "DECISION_QUARANTINED"
    assert session.calls == 1


def test_publish_batch_halts_when_action_quarantined() -> None:
    session = _StubSession(
        [
            _StubResponse(200, {"decision": PUBLISH_ADMIT, "receipt": {"receipt_id": "r5"}}),
            _StubResponse(200, {"decision": PUBLISH_QUARANTINE, "receipt": {"receipt_id": "r6"}}),
        ]
    )
    publisher = _publisher(session)
    result = publisher.publish_decision_and_intents(
        decision_envelope=_envelope("evt_6", "decision_response"),
        action_envelopes=(_envelope("evt_7", "action_intent"),),
    )
    assert result.halted is True
    assert result.halt_reason == "ACTION_QUARANTINED"
    assert session.calls == 2


def test_publish_rejects_invalid_envelope_before_send() -> None:
    session = _StubSession([])
    publisher = _publisher(session)
    invalid = {"event_id": "x", "payload": {}}
    with pytest.raises(DecisionFabricPublishError, match="CANONICAL_ENVELOPE_INVALID"):
        publisher.publish_envelope(invalid)
    assert session.calls == 0
