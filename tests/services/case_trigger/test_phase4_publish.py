from __future__ import annotations

from pathlib import Path

import pytest
import requests

import fraud_detection.case_trigger.storage as storage_module
from fraud_detection.case_mgmt.contracts import CaseTrigger
from fraud_detection.case_trigger.publish import (
    PUBLISH_ADMIT,
    PUBLISH_AMBIGUOUS,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
    CaseTriggerIgPublisher,
    CaseTriggerPublishError,
    build_case_trigger_envelope,
)
from fraud_detection.case_trigger.storage import CaseTriggerPublishStore, CaseTriggerStorageError


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


def _trigger_payload() -> dict[str, object]:
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": "decision:dec_001",
        "case_subject_key": {
            "platform_run_id": "platform_20260209T161300Z",
            "event_class": "traffic_fraud",
            "event_id": "evt_decision_trigger_001",
        },
        "pins": {
            "platform_run_id": "platform_20260209T161300Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": "2026-02-09T16:13:00.123456+00:00",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def _trigger() -> CaseTrigger:
    return CaseTrigger.from_payload(_trigger_payload())


def _publisher(
    session: _StubSession,
    *,
    publish_store: CaseTriggerPublishStore | None = None,
) -> CaseTriggerIgPublisher:
    return CaseTriggerIgPublisher(
        ig_ingest_url="http://localhost:8081",
        api_key="case_trigger_writer",
        max_attempts=3,
        retry_base_delay_ms=0,
        retry_max_delay_ms=0,
        timeout_seconds=0.1,
        session=session,  # type: ignore[arg-type]
        publish_store=publish_store,
    )


def test_build_case_trigger_envelope_normalizes_observed_time() -> None:
    envelope = build_case_trigger_envelope(_trigger())
    assert envelope["event_id"] == _trigger().case_trigger_id
    assert envelope["event_type"] == "case_trigger"
    assert envelope["schema_version"] == "v1"
    assert envelope["ts_utc"] == "2026-02-09T16:13:00.123456Z"


@pytest.mark.parametrize("decision", [PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE])
def test_phase4_publisher_maps_ig_decisions_and_persists(decision: str, tmp_path: Path) -> None:
    store = CaseTriggerPublishStore(locator=str(tmp_path / "case_trigger_publish.sqlite"))
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
    publisher = _publisher(session, publish_store=store)
    record = publisher.publish_case_trigger(_trigger())
    assert record.decision == decision
    assert record.actor_principal == "SYSTEM::case_trigger_writer"
    stored = store.lookup(_trigger().case_trigger_id)
    assert stored is not None
    assert stored.publish_decision == decision
    assert stored.receipt_id == "r1"
    assert stored.actor_principal == "SYSTEM::case_trigger_writer"


def test_phase4_publisher_returns_ambiguous_on_retry_exhaustion() -> None:
    session = _StubSession([requests.Timeout(), _StubResponse(500, text="internal"), requests.Timeout()])
    publisher = _publisher(session)
    record = publisher.publish_case_trigger(_trigger())
    assert record.decision == PUBLISH_AMBIGUOUS
    assert record.reason_code is not None
    assert record.reason_code.startswith("IG_PUSH_RETRY_EXHAUSTED:")
    assert session.calls == 3


def test_phase4_publisher_fails_closed_on_unknown_ig_decision() -> None:
    session = _StubSession([_StubResponse(200, {"decision": "UNKNOWN"})])
    publisher = _publisher(session)
    with pytest.raises(CaseTriggerPublishError, match="IG_DECISION_UNKNOWN"):
        publisher.publish_case_trigger(_trigger())


def test_phase4_publish_store_detects_hash_mismatch(tmp_path: Path) -> None:
    store = CaseTriggerPublishStore(locator=str(tmp_path / "case_trigger_publish.sqlite"))
    trigger = _trigger()
    first = store.register_publish_result(
        case_trigger_id=trigger.case_trigger_id,
        event_id=trigger.case_trigger_id,
        event_type="case_trigger",
        publish_decision=PUBLISH_ADMIT,
        receipt={"receipt_id": "r1"},
        receipt_ref="runs/fraud-platform/x/ig/receipts/r1.json",
        reason_code=None,
        actor_principal="SYSTEM::case_trigger_writer",
        actor_source_type="SYSTEM",
        published_at_utc="2026-02-09T16:14:00.000000Z",
    )
    assert first.status == "NEW"

    duplicate = store.register_publish_result(
        case_trigger_id=trigger.case_trigger_id,
        event_id=trigger.case_trigger_id,
        event_type="case_trigger",
        publish_decision=PUBLISH_ADMIT,
        receipt={"receipt_id": "r1"},
        receipt_ref="runs/fraud-platform/x/ig/receipts/r1.json",
        reason_code=None,
        actor_principal="SYSTEM::case_trigger_writer",
        actor_source_type="SYSTEM",
        published_at_utc="2026-02-09T16:14:01.000000Z",
    )
    assert duplicate.status == "DUPLICATE"

    mismatch = store.register_publish_result(
        case_trigger_id=trigger.case_trigger_id,
        event_id=trigger.case_trigger_id,
        event_type="case_trigger",
        publish_decision=PUBLISH_AMBIGUOUS,
        receipt=None,
        receipt_ref=None,
        reason_code="IG_PUSH_RETRY_EXHAUSTED:timeout",
        actor_principal="SYSTEM::case_trigger_writer",
        actor_source_type="SYSTEM",
        published_at_utc="2026-02-09T16:14:02.000000Z",
    )
    assert mismatch.status == "HASH_MISMATCH"


def test_phase4_postgres_sql_placeholders_follow_psycopg_contract() -> None:
    rendered, ordered = storage_module._render_sql_with_params(  # noqa: SLF001
        "SELECT 1 FROM case_trigger_publish WHERE case_trigger_id = {p2} AND published_at_utc = {p1}",
        "postgres",
        ("2026-02-10T04:42:00.000000Z", "trigger_001"),
    )
    assert rendered.count("%s") == 2
    assert "{p1}" not in rendered and "{p2}" not in rendered
    assert ordered == ("trigger_001", "2026-02-10T04:42:00.000000Z")


def test_phase4_placeholder_index_out_of_range_fails_closed() -> None:
    with pytest.raises(CaseTriggerStorageError, match="out of range"):
        storage_module._render_sql_with_params("SELECT * FROM case_trigger_publish WHERE case_trigger_id = {p4}", "postgres", ("trigger_001",))  # noqa: SLF001
