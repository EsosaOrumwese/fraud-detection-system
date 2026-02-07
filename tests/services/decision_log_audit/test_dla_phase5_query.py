from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from fraud_detection.decision_log_audit.query import (
    DecisionLogAuditQueryError,
    DecisionLogAuditQueryService,
    DecisionLogAuditReadAccessPolicy,
)
from fraud_detection.decision_log_audit.storage import DecisionLogAuditIntakeStore


def _payload_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(str(sorted(payload.items())).encode("utf-8")).hexdigest()


def _source_ref(*, offset: str) -> dict[str, object]:
    return {
        "topic": "fp.bus.traffic.fraud.v1",
        "partition": 0,
        "offset": offset,
        "offset_kind": "file_line",
    }


def _decision_payload(*, decision_id: str, decided_at_utc: str) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decided_at_utc": decided_at_utc,
    }


def _intent_payload(*, decision_id: str, action_id: str, requested_at_utc: str) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "action_id": action_id,
        "requested_at_utc": requested_at_utc,
    }


def _outcome_payload(*, decision_id: str, action_id: str, outcome_id: str, completed_at_utc: str) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "action_id": action_id,
        "outcome_id": outcome_id,
        "status": "EXECUTED",
        "completed_at_utc": completed_at_utc,
    }


def _apply_resolved_chain(
    store: DecisionLogAuditIntakeStore,
    *,
    platform_run_id: str,
    scenario_run_id: str,
    decision_id: str,
    action_id: str,
    outcome_id: str,
    decision_event_id: str,
    intent_event_id: str,
    outcome_event_id: str,
    decision_ts_utc: str,
) -> None:
    decision_payload = _decision_payload(decision_id=decision_id, decided_at_utc=decision_ts_utc)
    intent_payload = _intent_payload(decision_id=decision_id, action_id=action_id, requested_at_utc=decision_ts_utc)
    outcome_payload = _outcome_payload(
        decision_id=decision_id,
        action_id=action_id,
        outcome_id=outcome_id,
        completed_at_utc=decision_ts_utc,
    )

    store.apply_lineage_candidate(
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        event_type="decision_response",
        event_id=decision_event_id,
        schema_version="v1",
        payload_hash=_payload_hash(decision_payload),
        payload=decision_payload,
        source_ref=_source_ref(offset="0"),
    )
    store.apply_lineage_candidate(
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        event_type="action_intent",
        event_id=intent_event_id,
        schema_version="v1",
        payload_hash=_payload_hash(intent_payload),
        payload=intent_payload,
        source_ref=_source_ref(offset="1"),
    )
    store.apply_lineage_candidate(
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        event_type="action_outcome",
        event_id=outcome_event_id,
        schema_version="v1",
        payload_hash=_payload_hash(outcome_payload),
        payload=outcome_payload,
        source_ref=_source_ref(offset="2"),
    )


def test_phase5_query_run_scope_time_range_and_provenance(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_query.sqlite"))
    run_id = "platform_20260207T210000Z"
    scenario_run_id = "1" * 32

    _apply_resolved_chain(
        store,
        platform_run_id=run_id,
        scenario_run_id=scenario_run_id,
        decision_id="a" * 32,
        action_id="5" * 32,
        outcome_id="8" * 32,
        decision_event_id="evt_decision_a",
        intent_event_id="evt_intent_a",
        outcome_event_id="evt_outcome_a",
        decision_ts_utc="2026-02-07T21:00:00.000000Z",
    )
    _apply_resolved_chain(
        store,
        platform_run_id=run_id,
        scenario_run_id=scenario_run_id,
        decision_id="b" * 32,
        action_id="6" * 32,
        outcome_id="9" * 32,
        decision_event_id="evt_decision_b",
        intent_event_id="evt_intent_b",
        outcome_event_id="evt_outcome_b",
        decision_ts_utc="2026-02-07T21:10:00.000000Z",
    )

    query = DecisionLogAuditQueryService(store=store)
    records = query.query_run_scope(platform_run_id=run_id, scenario_run_id=scenario_run_id, limit=10)
    assert [item["decision_id"] for item in records] == ["a" * 32, "b" * 32]
    assert records[0]["chain_status"] == "RESOLVED"
    assert records[0]["decision_ref"]["event_type"] == "decision_response"
    assert len(records[0]["intent_refs"]) == 1
    assert len(records[0]["outcome_refs"]) == 1

    ranged = query.query_run_scope(
        platform_run_id=run_id,
        scenario_run_id=scenario_run_id,
        start_ts_utc="2026-02-07T21:05:00.000000Z",
        end_ts_utc="2026-02-07T21:15:00.000000Z",
        limit=10,
    )
    assert [item["decision_id"] for item in ranged] == ["b" * 32]


def test_phase5_query_by_decision_action_outcome_and_duplicate_determinism(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_query.sqlite"))
    run_id = "platform_20260207T220000Z"
    scenario_run_id = "2" * 32
    decision_id = "c" * 32
    action_id = "7" * 32
    outcome_id = "a" * 32

    _apply_resolved_chain(
        store,
        platform_run_id=run_id,
        scenario_run_id=scenario_run_id,
        decision_id=decision_id,
        action_id=action_id,
        outcome_id=outcome_id,
        decision_event_id="evt_decision_c",
        intent_event_id="evt_intent_c",
        outcome_event_id="evt_outcome_c",
        decision_ts_utc="2026-02-07T22:00:00.000000Z",
    )

    # Replay duplicates should not create extra lineage edges.
    store.apply_lineage_candidate(
        platform_run_id=run_id,
        scenario_run_id=scenario_run_id,
        event_type="decision_response",
        event_id="evt_decision_c",
        schema_version="v1",
        payload_hash=_payload_hash(_decision_payload(decision_id=decision_id, decided_at_utc="2026-02-07T22:00:00.000000Z")),
        payload=_decision_payload(decision_id=decision_id, decided_at_utc="2026-02-07T22:00:00.000000Z"),
        source_ref=_source_ref(offset="0"),
    )

    query = DecisionLogAuditQueryService(store=store)
    decision = query.query_decision_id(decision_id=decision_id)
    assert decision is not None
    assert decision["intent_count"] == 1
    assert decision["outcome_count"] == 1

    by_action = query.query_action_id(action_id=action_id)
    assert len(by_action) == 1
    assert by_action[0]["decision_id"] == decision_id

    by_outcome = query.query_outcome_id(outcome_id=outcome_id)
    assert len(by_outcome) == 1
    assert by_outcome[0]["decision_id"] == decision_id

    # Deterministic read ordering/content under replay.
    assert query.query_action_id(action_id=action_id) == by_action


def test_phase5_query_access_policy_and_redaction_hook(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_query.sqlite"))
    run_id = "platform_20260207T230000Z"
    scenario_run_id = "3" * 32

    _apply_resolved_chain(
        store,
        platform_run_id=run_id,
        scenario_run_id=scenario_run_id,
        decision_id="d" * 32,
        action_id="8" * 32,
        outcome_id="b" * 32,
        decision_event_id="evt_decision_d",
        intent_event_id="evt_intent_d",
        outcome_event_id="evt_outcome_d",
        decision_ts_utc="2026-02-07T23:00:00.000000Z",
    )

    denied = DecisionLogAuditQueryService(
        store=store,
        access_policy=DecisionLogAuditReadAccessPolicy(allowed_platform_run_ids=("platform_20260207T999999Z",)),
    )
    with pytest.raises(DecisionLogAuditQueryError):
        denied.query_run_scope(platform_run_id=run_id, scenario_run_id=scenario_run_id, limit=10)

    def _redact(payload: dict[str, object]) -> dict[str, object]:
        payload["decision_payload_hash"] = "REDACTED"
        payload["decision_ref"] = None
        return payload

    allowed = DecisionLogAuditQueryService(
        store=store,
        access_policy=DecisionLogAuditReadAccessPolicy(allowed_platform_run_ids=(run_id,)),
        redaction_hook=_redact,
    )
    record = allowed.query_decision_id(decision_id="d" * 32)
    assert record is not None
    assert record["decision_payload_hash"] == "REDACTED"
    assert record["decision_ref"] is None
