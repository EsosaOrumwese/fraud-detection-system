from __future__ import annotations

from pathlib import Path

from fraud_detection.case_mgmt import (
    CASE_CREATED,
    CASE_EXISTING,
    INTAKE_NEW_TRIGGER,
    SOURCE_TYPE_HUMAN,
    SOURCE_TYPE_SYSTEM,
    TIMELINE_EVENT_DUPLICATE,
    TIMELINE_EVENT_NEW,
    TIMELINE_EVENT_PAYLOAD_MISMATCH,
    CaseTriggerIntakeLedger,
)


def _trigger_payload(*, source_ref_id: str, event_id: str, observed_time: str) -> dict[str, object]:
    suffix = source_ref_id.split(":")[-1]
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T170000Z",
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "pins": {
            "platform_run_id": "platform_20260209T170000Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": observed_time,
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": suffix},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{suffix}"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def _timeline_payload(
    *,
    case_id: str,
    event_type: str,
    source_ref_id: str,
    observed_time: str,
    event_id: str,
    timeline_payload: dict[str, object] | None = None,
    evidence_refs: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": case_id,
        "timeline_event_type": event_type,
        "source_ref_id": source_ref_id,
        "pins": {
            "platform_run_id": "platform_20260209T170000Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": observed_time,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T170000Z",
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "evidence_refs": evidence_refs or [],
    }
    if timeline_payload is not None:
        payload["timeline_payload"] = dict(timeline_payload)
    return payload


def _ingest(ledger: CaseTriggerIntakeLedger, *, source_ref_id: str, event_id: str, observed_time: str):
    result = ledger.ingest_case_trigger(
        payload=_trigger_payload(source_ref_id=source_ref_id, event_id=event_id, observed_time=observed_time),
        ingested_at_utc="2026-02-09T17:00:10.000000Z",
    )
    assert result.outcome == INTAKE_NEW_TRIGGER
    assert result.case_status in {CASE_CREATED, CASE_EXISTING}
    return result


def test_phase3_append_only_actor_attributed_timeline_semantics(tmp_path: Path) -> None:
    ledger = CaseTriggerIntakeLedger(tmp_path / "cm_phase3.sqlite")
    intake = _ingest(
        ledger,
        source_ref_id="decision:dec_001",
        event_id="evt_case_trigger_001",
        observed_time="2026-02-09T17:00:00.000000Z",
    )

    payload = _timeline_payload(
        case_id=intake.case_id,
        event_type="INVESTIGATOR_ASSERTION",
        source_ref_id="assertion:1",
        observed_time="2026-02-09T17:01:00.000000Z",
        event_id="evt_case_trigger_001",
        timeline_payload={"assignee": "analyst_a", "note": "first investigation note"},
        evidence_refs=[{"ref_type": "DECISION", "ref_id": "dec_001"}],
    )

    first = ledger.append_timeline_event(
        payload=payload,
        actor_id="HUMAN::analyst_a",
        source_type=SOURCE_TYPE_HUMAN,
        appended_at_utc="2026-02-09T17:01:05.000000Z",
    )
    assert first.outcome == TIMELINE_EVENT_NEW

    duplicate = ledger.append_timeline_event(
        payload=payload,
        actor_id="HUMAN::analyst_a",
        source_type=SOURCE_TYPE_HUMAN,
        appended_at_utc="2026-02-09T17:01:06.000000Z",
    )
    assert duplicate.outcome == TIMELINE_EVENT_DUPLICATE
    assert duplicate.replay_count == 1

    mismatch_payload = _timeline_payload(
        case_id=intake.case_id,
        event_type="INVESTIGATOR_ASSERTION",
        source_ref_id="assertion:1",
        observed_time="2026-02-09T17:01:00.000000Z",
        event_id="evt_case_trigger_001",
        timeline_payload={"assignee": "analyst_b", "note": "mutated"},
        evidence_refs=[{"ref_type": "DECISION", "ref_id": "dec_001"}],
    )
    mismatch = ledger.append_timeline_event(
        payload=mismatch_payload,
        actor_id="HUMAN::analyst_b",
        source_type=SOURCE_TYPE_HUMAN,
        appended_at_utc="2026-02-09T17:01:07.000000Z",
    )
    assert mismatch.outcome == TIMELINE_EVENT_PAYLOAD_MISMATCH
    assert mismatch.mismatch_count == 1

    timeline = ledger.list_timeline_events(intake.case_id)
    assert len(timeline) == 2
    investigator = [item for item in timeline if item.timeline_event_type == "INVESTIGATOR_ASSERTION"][0]
    assert investigator.actor_id == "HUMAN::analyst_a"
    assert investigator.source_type == SOURCE_TYPE_HUMAN


def test_phase3_projection_derives_status_queue_and_pending_flags(tmp_path: Path) -> None:
    ledger = CaseTriggerIntakeLedger(tmp_path / "cm_phase3_projection.sqlite")
    intake = _ingest(
        ledger,
        source_ref_id="decision:dec_020",
        event_id="evt_case_trigger_020",
        observed_time="2026-02-09T17:10:00.000000Z",
    )

    events = [
        _timeline_payload(
            case_id=intake.case_id,
            event_type="ACTION_INTENT_REQUESTED",
            source_ref_id="action_request:1",
            observed_time="2026-02-09T17:11:00.000000Z",
            event_id="evt_case_trigger_020",
            timeline_payload={"decision_id": "dec_020", "action_intent_id": "ai_1"},
            evidence_refs=[{"ref_type": "DECISION", "ref_id": "dec_020"}],
        ),
        _timeline_payload(
            case_id=intake.case_id,
            event_type="ACTION_OUTCOME_ATTACHED",
            source_ref_id="action_outcome:ao_1",
            observed_time="2026-02-09T17:12:00.000000Z",
            event_id="evt_case_trigger_020",
            timeline_payload={"action_outcome_id": "ao_1", "outcome_status": "EXECUTED"},
            evidence_refs=[{"ref_type": "ACTION_OUTCOME", "ref_id": "ao_1"}],
        ),
        _timeline_payload(
            case_id=intake.case_id,
            event_type="LABEL_PENDING",
            source_ref_id="label_pending:1",
            observed_time="2026-02-09T17:13:00.000000Z",
            event_id="evt_case_trigger_020",
            timeline_payload={"decision_id": "dec_020"},
        ),
        _timeline_payload(
            case_id=intake.case_id,
            event_type="LABEL_ACCEPTED",
            source_ref_id="label_accept:1",
            observed_time="2026-02-09T17:14:00.000000Z",
            event_id="evt_case_trigger_020",
            timeline_payload={"decision_id": "dec_020"},
        ),
    ]
    for index, payload in enumerate(events):
        appended = ledger.append_timeline_event(
            payload=payload,
            actor_id="SYSTEM::case_mgmt",
            source_type=SOURCE_TYPE_SYSTEM,
            appended_at_utc=f"2026-02-09T17:14:0{index}.000000Z",
        )
        assert appended.outcome == TIMELINE_EVENT_NEW

    projection = ledger.project_case(intake.case_id)
    assert projection is not None
    assert projection.status == "RESOLVED"
    assert projection.queue_state == "resolved"
    assert projection.pending_action_outcome is False
    assert projection.pending_label_write is False
    assert projection.is_open is False
    assert projection.event_count == 5


def test_phase3_linked_ref_and_state_time_queries(tmp_path: Path) -> None:
    ledger = CaseTriggerIntakeLedger(tmp_path / "cm_phase3_queries.sqlite")
    one = _ingest(
        ledger,
        source_ref_id="decision:dec_100",
        event_id="evt_case_trigger_100",
        observed_time="2026-02-09T17:20:00.000000Z",
    )
    two = _ingest(
        ledger,
        source_ref_id="decision:dec_200",
        event_id="evt_case_trigger_200",
        observed_time="2026-02-09T17:25:00.000000Z",
    )

    pending = ledger.append_timeline_event(
        payload=_timeline_payload(
            case_id=two.case_id,
            event_type="ACTION_INTENT_REQUESTED",
            source_ref_id="action_request:pending",
            observed_time="2026-02-09T17:26:00.000000Z",
            event_id="evt_case_trigger_200",
            timeline_payload={"decision_id": "dec_200"},
            evidence_refs=[{"ref_type": "DECISION", "ref_id": "dec_200"}],
        ),
        actor_id="SYSTEM::case_mgmt",
        source_type=SOURCE_TYPE_SYSTEM,
        appended_at_utc="2026-02-09T17:26:01.000000Z",
    )
    assert pending.outcome == TIMELINE_EVENT_NEW

    accepted = ledger.append_timeline_event(
        payload=_timeline_payload(
            case_id=one.case_id,
            event_type="LABEL_ACCEPTED",
            source_ref_id="label_accept:100",
            observed_time="2026-02-09T17:27:00.000000Z",
            event_id="evt_case_trigger_100",
            timeline_payload={"audit_record_id": "audit_resolved_100"},
            evidence_refs=[{"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_resolved_100"}],
        ),
        actor_id="SYSTEM::case_mgmt",
        source_type=SOURCE_TYPE_SYSTEM,
        appended_at_utc="2026-02-09T17:27:01.000000Z",
    )
    assert accepted.outcome == TIMELINE_EVENT_NEW

    by_decision = ledger.find_case_ids_by_linked_ref(ref_type="decision_id", ref_id="dec_100")
    assert by_decision == (one.case_id,)

    by_audit = ledger.find_case_ids_by_linked_ref(ref_type="audit_record_id", ref_id="audit_resolved_100")
    assert by_audit == (one.case_id,)

    resolved = ledger.query_case_projections(status="RESOLVED")
    assert [item.case_id for item in resolved] == [one.case_id]

    pending_action = ledger.query_case_projections(queue_state="pending_action")
    assert [item.case_id for item in pending_action] == [two.case_id]

    window = ledger.query_case_projections(observed_from_utc="2026-02-09T17:26:30.000000Z")
    assert [item.case_id for item in window] == [one.case_id]


def test_phase3_same_timestamp_ordering_is_deterministic(tmp_path: Path) -> None:
    ledger = CaseTriggerIntakeLedger(tmp_path / "cm_phase3_order.sqlite")
    intake = _ingest(
        ledger,
        source_ref_id="decision:dec_300",
        event_id="evt_case_trigger_300",
        observed_time="2026-02-09T17:30:00.000000Z",
    )

    first = ledger.append_timeline_event(
        payload=_timeline_payload(
            case_id=intake.case_id,
            event_type="INVESTIGATOR_ASSERTION",
            source_ref_id="assertion:A",
            observed_time="2026-02-09T17:31:00.000000Z",
            event_id="evt_case_trigger_300",
            timeline_payload={"assignee": "analyst_a"},
        ),
        actor_id="HUMAN::analyst_a",
        source_type=SOURCE_TYPE_HUMAN,
        appended_at_utc="2026-02-09T17:31:05.000000Z",
    )
    second = ledger.append_timeline_event(
        payload=_timeline_payload(
            case_id=intake.case_id,
            event_type="INVESTIGATOR_ASSERTION",
            source_ref_id="assertion:B",
            observed_time="2026-02-09T17:31:00.000000Z",
            event_id="evt_case_trigger_300",
            timeline_payload={"assignee": "analyst_b"},
        ),
        actor_id="HUMAN::analyst_b",
        source_type=SOURCE_TYPE_HUMAN,
        appended_at_utc="2026-02-09T17:31:06.000000Z",
    )
    assert first.outcome == TIMELINE_EVENT_NEW
    assert second.outcome == TIMELINE_EVENT_NEW

    timeline = ledger.list_timeline_events(intake.case_id)
    ties = [item.case_timeline_event_id for item in timeline if item.observed_time == "2026-02-09T17:31:00.000000Z"]
    assert ties == sorted(ties)
