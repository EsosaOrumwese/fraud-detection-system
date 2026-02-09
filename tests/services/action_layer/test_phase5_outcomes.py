from __future__ import annotations

from pathlib import Path

import pytest
import requests

from fraud_detection.action_layer.contracts import ActionOutcome
from fraud_detection.action_layer.publish import (
    PUBLISH_ADMIT,
    PUBLISH_AMBIGUOUS,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
    ActionLayerIgPublisher,
    ActionLayerPublishError,
    build_action_outcome_envelope,
)
from fraud_detection.action_layer.storage import ActionOutcomeStore


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


def _outcome_payload(*, outcome_id: str = "1" * 32) -> dict[str, object]:
    return {
        "outcome_id": outcome_id,
        "decision_id": "2" * 32,
        "action_id": "3" * 32,
        "action_kind": "txn_disposition_publish",
        "status": "EXECUTED",
        "idempotency_key": "merchant_42:evt_123:publish",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "authz_policy_rev": {"policy_id": "al.policy.v0", "revision": "r1"},
        "run_config_digest": "4" * 64,
        "pins": {
            "platform_run_id": "platform_20260207T190000Z",
            "scenario_run_id": "5" * 32,
            "manifest_fingerprint": "6" * 64,
            "parameter_hash": "7" * 64,
            "scenario_id": "scenario.v0",
            "seed": 9,
            "run_id": "8" * 32,
        },
        "completed_at_utc": "2026-02-07T19:00:00.000000Z",
        "attempt_seq": 1,
        "reason": "EXECUTED",
        "outcome_payload": {"terminal_state": "EXECUTED"},
    }


def _publisher(session: _StubSession) -> ActionLayerIgPublisher:
    return ActionLayerIgPublisher(
        ig_ingest_url="http://localhost:8081",
        max_attempts=3,
        retry_base_delay_ms=0,
        retry_max_delay_ms=0,
        timeout_seconds=0.1,
        session=session,  # type: ignore[arg-type]
    )


def test_outcome_store_append_is_append_only_with_hash_guard(tmp_path: Path) -> None:
    store = ActionOutcomeStore(locator=str(tmp_path / "al_outcomes.sqlite"))
    payload = _outcome_payload(outcome_id="a" * 32)

    created = store.register_outcome(
        outcome_payload=payload,
        recorded_at_utc="2026-02-07T19:00:01.000000Z",
    )
    assert created.status == "NEW"

    duplicate = store.register_outcome(
        outcome_payload=payload,
        recorded_at_utc="2026-02-07T19:00:02.000000Z",
    )
    assert duplicate.status == "DUPLICATE"
    assert duplicate.record.payload_hash == created.record.payload_hash

    mutated = dict(payload)
    mutated["status"] = "FAILED"
    mismatch = store.register_outcome(
        outcome_payload=mutated,
        recorded_at_utc="2026-02-07T19:00:03.000000Z",
    )
    assert mismatch.status == "HASH_MISMATCH"
    assert mismatch.record.status == "EXECUTED"


@pytest.mark.parametrize("decision", [PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE])
def test_publisher_maps_ig_decisions(decision: str) -> None:
    outcome = ActionOutcome.from_payload(_outcome_payload(outcome_id="b" * 32))
    envelope = build_action_outcome_envelope(outcome)
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
    record = publisher.publish_envelope(envelope)
    assert record.decision == decision
    assert record.receipt["receipt_id"] == "r1"


def test_publisher_returns_ambiguous_on_retry_exhausted_transient_errors() -> None:
    outcome = ActionOutcome.from_payload(_outcome_payload(outcome_id="c" * 32))
    envelope = build_action_outcome_envelope(outcome)
    session = _StubSession([requests.Timeout(), _StubResponse(500, text="internal error"), requests.Timeout()])
    publisher = _publisher(session)
    record = publisher.publish_envelope(envelope)
    assert record.decision == PUBLISH_AMBIGUOUS
    assert record.reason_code is not None
    assert record.reason_code.startswith("IG_PUSH_RETRY_EXHAUSTED:")
    assert session.calls == 3


def test_publisher_fails_closed_on_unknown_ig_decision() -> None:
    outcome = ActionOutcome.from_payload(_outcome_payload(outcome_id="d" * 32))
    envelope = build_action_outcome_envelope(outcome)
    session = _StubSession([_StubResponse(200, {"decision": "UNKNOWN"})])
    publisher = _publisher(session)
    with pytest.raises(ActionLayerPublishError, match="IG_DECISION_UNKNOWN"):
        publisher.publish_envelope(envelope)


def test_outcome_store_persists_publish_evidence_for_reconciliation(tmp_path: Path) -> None:
    store = ActionOutcomeStore(locator=str(tmp_path / "al_outcomes.sqlite"))
    payload = _outcome_payload(outcome_id="e" * 32)
    store.register_outcome(
        outcome_payload=payload,
        recorded_at_utc="2026-02-07T19:00:01.000000Z",
    )

    admitted = store.register_publish_result(
        outcome_id="e" * 32,
        event_id="e" * 32,
        event_type="action_outcome",
        publish_decision=PUBLISH_ADMIT,
        receipt={"receipt_id": "r1"},
        receipt_ref="runs/fraud-platform/x/ig/receipts/r1.json",
        reason_code=None,
        published_at_utc="2026-02-07T19:00:04.000000Z",
    )
    assert admitted.status == "NEW"
    assert admitted.record.publish_decision == PUBLISH_ADMIT
    assert admitted.record.receipt_id == "r1"

    duplicate = store.register_publish_result(
        outcome_id="e" * 32,
        event_id="e" * 32,
        event_type="action_outcome",
        publish_decision=PUBLISH_ADMIT,
        receipt={"receipt_id": "r1"},
        receipt_ref="runs/fraud-platform/x/ig/receipts/r1.json",
        reason_code=None,
        published_at_utc="2026-02-07T19:00:04.000000Z",
    )
    assert duplicate.status == "DUPLICATE"

    mismatch = store.register_publish_result(
        outcome_id="e" * 32,
        event_id="e" * 32,
        event_type="action_outcome",
        publish_decision=PUBLISH_AMBIGUOUS,
        receipt=None,
        receipt_ref=None,
        reason_code="IG_PUSH_RETRY_EXHAUSTED:timeout",
        published_at_utc="2026-02-07T19:00:05.000000Z",
    )
    assert mismatch.status == "HASH_MISMATCH"


def test_build_outcome_envelope_normalizes_offset_timestamp_to_canonical_z() -> None:
    payload = _outcome_payload(outcome_id="f" * 32)
    payload["completed_at_utc"] = "2026-02-07T19:00:00.123456+00:00"
    outcome = ActionOutcome.from_payload(payload)
    envelope = build_action_outcome_envelope(outcome)
    assert envelope["ts_utc"] == "2026-02-07T19:00:00.123456Z"


def test_build_outcome_envelope_rejects_invalid_timestamp() -> None:
    payload = _outcome_payload(outcome_id="a" * 32)
    payload["completed_at_utc"] = "not-a-timestamp"
    outcome = ActionOutcome.from_payload(payload)
    with pytest.raises(ActionLayerPublishError, match="payload.completed_at_utc must be an ISO-8601 timestamp"):
        build_action_outcome_envelope(outcome)
