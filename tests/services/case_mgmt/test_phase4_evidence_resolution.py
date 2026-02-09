from __future__ import annotations

from pathlib import Path

from fraud_detection.case_mgmt import (
    EVIDENCE_FORBIDDEN,
    EVIDENCE_PENDING,
    EVIDENCE_RESOLVED,
    EVIDENCE_UNAVAILABLE,
    REQUEST_DUPLICATE,
    REQUEST_FORBIDDEN,
    REQUEST_NEW,
    EVIDENCE_SOURCE_TYPE_HUMAN,
    EVIDENCE_SOURCE_TYPE_SYSTEM,
    CaseEvidenceResolutionCorridor,
    CaseTriggerIntakeLedger,
    load_evidence_resolution_policy,
)


def _trigger_payload(*, source_ref_id: str, event_id: str, observed_time: str) -> dict[str, object]:
    suffix = source_ref_id.split(":")[-1]
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T171500Z",
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "pins": {
            "platform_run_id": "platform_20260209T171500Z",
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


def _corridor(locator: str) -> CaseEvidenceResolutionCorridor:
    policy = load_evidence_resolution_policy(Path("config/platform/case_mgmt/evidence_resolution_policy_v0.yaml"))
    return CaseEvidenceResolutionCorridor(locator=locator, policy=policy)


def _ingest_case(ledger: CaseTriggerIntakeLedger):
    return ledger.ingest_case_trigger(
        payload=_trigger_payload(
            source_ref_id="decision:dec_001",
            event_id="evt_case_trigger_001",
            observed_time="2026-02-09T17:15:00.000000Z",
        ),
        ingested_at_utc="2026-02-09T17:15:10.000000Z",
    )


def test_phase4_request_pending_then_resolve_by_ref(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase4.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    intake = _ingest_case(ledger)
    corridor = _corridor(locator)

    request = corridor.request_resolution(
        case_id=intake.case_id,
        case_timeline_event_id=intake.timeline_event_id,
        ref_type="DLA_AUDIT_RECORD",
        ref_id="audit_dec_001",
        actor_id="SYSTEM::case_mgmt_evidence",
        source_type=EVIDENCE_SOURCE_TYPE_SYSTEM,
        requested_at_utc="2026-02-09T17:15:11.000000Z",
        locator_ref="runs/fraud-platform/platform_20260209T171500Z/dla/audit/audit_dec_001.json",
    )
    assert request.disposition == REQUEST_NEW
    assert request.snapshot.status == EVIDENCE_PENDING

    resolved = corridor.record_resolution(
        request_id=request.snapshot.request_id,
        status=EVIDENCE_RESOLVED,
        reason_code="REF_RESOLVED",
        actor_id="SYSTEM::case_mgmt_evidence",
        source_type=EVIDENCE_SOURCE_TYPE_SYSTEM,
        observed_at_utc="2026-02-09T17:15:12.000000Z",
        locator_ref="runs/fraud-platform/platform_20260209T171500Z/dla/audit/audit_dec_001.json",
    )
    assert resolved.status == EVIDENCE_RESOLVED
    assert resolved.reason_code == "REF_RESOLVED"
    assert corridor.event_count(request_id=resolved.request_id) == 2


def test_phase4_fail_closed_on_unsupported_ref_type(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase4_forbidden.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    intake = _ingest_case(ledger)
    corridor = _corridor(locator)

    forbidden = corridor.request_resolution(
        case_id=intake.case_id,
        case_timeline_event_id=intake.timeline_event_id,
        ref_type="EXTERNAL_REF",
        ref_id="external:abc",
        actor_id="SYSTEM::case_mgmt_evidence",
        source_type=EVIDENCE_SOURCE_TYPE_SYSTEM,
        requested_at_utc="2026-02-09T17:16:00.000000Z",
    )
    assert forbidden.disposition == REQUEST_FORBIDDEN
    assert forbidden.snapshot.status == EVIDENCE_FORBIDDEN
    assert forbidden.snapshot.reason_code == "UNSUPPORTED_REF_TYPE"

    duplicate = corridor.request_resolution(
        case_id=intake.case_id,
        case_timeline_event_id=intake.timeline_event_id,
        ref_type="EXTERNAL_REF",
        ref_id="external:abc",
        actor_id="SYSTEM::case_mgmt_evidence",
        source_type=EVIDENCE_SOURCE_TYPE_SYSTEM,
        requested_at_utc="2026-02-09T17:16:01.000000Z",
    )
    assert duplicate.disposition == REQUEST_DUPLICATE
    assert duplicate.snapshot.status == EVIDENCE_FORBIDDEN
    assert corridor.event_count(request_id=duplicate.snapshot.request_id) == 1


def test_phase4_missing_evidence_is_explicit_unavailable_without_truth_mutation(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase4_unavailable.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    intake = _ingest_case(ledger)
    corridor = _corridor(locator)

    initial_timeline = ledger.list_timeline_events(intake.case_id)
    assert len(initial_timeline) == 1

    requested = corridor.request_resolution(
        case_id=intake.case_id,
        case_timeline_event_id=intake.timeline_event_id,
        ref_type="DECISION",
        ref_id="dec_001",
        actor_id="SYSTEM::case_mgmt_evidence",
        source_type=EVIDENCE_SOURCE_TYPE_SYSTEM,
        requested_at_utc="2026-02-09T17:17:00.000000Z",
    )
    assert requested.snapshot.status == EVIDENCE_PENDING

    unavailable = corridor.record_resolution(
        request_id=requested.snapshot.request_id,
        status=EVIDENCE_UNAVAILABLE,
        reason_code="REF_NOT_FOUND",
        actor_id="SYSTEM::case_mgmt_evidence",
        source_type=EVIDENCE_SOURCE_TYPE_SYSTEM,
        observed_at_utc="2026-02-09T17:17:01.000000Z",
    )
    assert unavailable.status == EVIDENCE_UNAVAILABLE
    assert unavailable.reason_code == "REF_NOT_FOUND"

    final_timeline = ledger.list_timeline_events(intake.case_id)
    assert len(final_timeline) == 1


def test_phase4_actor_gate_blocks_unknown_principal_prefix(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase4_actor_gate.sqlite")
    ledger = CaseTriggerIntakeLedger(locator)
    intake = _ingest_case(ledger)
    corridor = _corridor(locator)

    blocked = corridor.request_resolution(
        case_id=intake.case_id,
        case_timeline_event_id=intake.timeline_event_id,
        ref_type="DECISION",
        ref_id="dec_001",
        actor_id="SERVICE::opaque",
        source_type=EVIDENCE_SOURCE_TYPE_HUMAN,
        requested_at_utc="2026-02-09T17:18:00.000000Z",
    )
    assert blocked.disposition == REQUEST_FORBIDDEN
    assert blocked.snapshot.status == EVIDENCE_FORBIDDEN
    assert blocked.snapshot.reason_code == "ACTOR_FORBIDDEN"
