from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from fraud_detection.case_mgmt import (
    ACTION_NEW,
    ACTION_PAYLOAD_MISMATCH,
    AL_SUBMIT_ACCEPTED,
    AL_SUBMIT_PENDING,
    CaseActionHandshakeCoordinator,
    CaseActionHandshakeError,
    CaseTriggerIntakeLedger,
    OUTCOME_DENIED,
    SUBMIT_FAILED_FATAL,
    SUBMIT_FAILED_RETRYABLE,
    SUBMIT_SUBMITTED,
    ActionSubmitWriteResult,
    load_action_emission_policy,
)


def _trigger_payload(*, source_ref_id: str, event_id: str, observed_time: str) -> dict[str, object]:
    suffix = source_ref_id.split(":")[-1]
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T190000Z",
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "pins": {
            "platform_run_id": "platform_20260209T190000Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 19,
        },
        "observed_time": observed_time,
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": suffix},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{suffix}"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def _submission(
    *,
    case_id: str,
    source_case_event_id: str,
    action_kind: str = "BLOCK_ACCOUNT",
    reason_code: str = "MANUAL_BLOCK_REQUESTED",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "source_case_event_id": source_case_event_id,
        "action_kind": action_kind,
        "target_ref": {"ref_type": "ACCOUNT", "ref_id": "acct_001"},
        "pins": {
            "platform_run_id": "platform_20260209T190000Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 19,
        },
        "actor_principal": "HUMAN::investigator_01",
        "source_type": "HUMAN",
        "requested_at_utc": "2026-02-09T19:00:01.000000Z",
        "reason_code": reason_code,
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_dec_001"},
        ],
        "constraints": {"ttl_seconds": 900},
    }


@dataclass
class _StubActionWriter:
    outcomes: list[object]

    def __post_init__(self) -> None:
        self.calls: int = 0
        self.payloads: list[dict[str, Any]] = []

    def write_action_intent(self, intent_payload: dict[str, Any]) -> ActionSubmitWriteResult:
        self.calls += 1
        self.payloads.append(dict(intent_payload))
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            if isinstance(outcome, ActionSubmitWriteResult):
                return outcome
        return ActionSubmitWriteResult(status=AL_SUBMIT_PENDING, reason_code="AL_PENDING")


def _coordinator(locator: str, writer: _StubActionWriter) -> tuple[CaseTriggerIntakeLedger, CaseActionHandshakeCoordinator]:
    ledger = CaseTriggerIntakeLedger(locator)
    policy = load_action_emission_policy(Path("config/platform/case_mgmt/action_emission_policy_v0.yaml"))
    coordinator = CaseActionHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=policy,
        action_intent_writer=writer,
    )
    return ledger, coordinator


def _ingest_case(ledger: CaseTriggerIntakeLedger):
    return ledger.ingest_case_trigger(
        payload=_trigger_payload(
            source_ref_id="decision:dec_001",
            event_id="evt_case_001",
            observed_time="2026-02-09T19:00:00.000000Z",
        ),
        ingested_at_utc="2026-02-09T19:00:00.500000Z",
    )


def _action_submit_statuses(ledger: CaseTriggerIntakeLedger, case_id: str) -> list[str]:
    statuses: list[str] = []
    for row in ledger.list_timeline_events(case_id):
        if row.timeline_event_type != "ACTION_INTENT_REQUESTED":
            continue
        timeline_payload = row.event_payload.get("timeline_payload")
        payload = dict(timeline_payload) if isinstance(timeline_payload, dict) else {}
        status = str(payload.get("submit_status") or "").strip().upper()
        if status:
            statuses.append(status)
    return statuses


def test_phase6_submit_manual_action_records_requested_and_submitted(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase6_submit.sqlite")
    writer = _StubActionWriter(
        [ActionSubmitWriteResult(status=AL_SUBMIT_ACCEPTED, reason_code="AL_ACCEPTED", intent_ref="al://intent/001")]
    )
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    result = coordinator.submit_manual_action(
        **_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
        )
    )

    assert result.disposition == ACTION_NEW
    assert result.submission_status == SUBMIT_SUBMITTED
    assert result.submit_attempt_count == 1

    statuses = _action_submit_statuses(ledger, intake.case_id)
    assert statuses == ["REQUESTED", "SUBMITTED"]

    projection = ledger.project_case(intake.case_id)
    assert projection is not None
    assert projection.pending_action_outcome is True
    assert projection.status == "ACTION_PENDING"


def test_phase6_retry_pending_advances_to_submitted(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase6_retry.sqlite")
    writer = _StubActionWriter(
        [
            ActionSubmitWriteResult(status=AL_SUBMIT_PENDING, reason_code="AL_UNAVAILABLE"),
            ActionSubmitWriteResult(status=AL_SUBMIT_ACCEPTED, reason_code="AL_ACCEPTED"),
        ]
    )
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    submitted = coordinator.submit_manual_action(
        **_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
        )
    )
    assert submitted.submission_status == SUBMIT_FAILED_RETRYABLE
    assert submitted.submit_attempt_count == 1

    retried = coordinator.retry_pending(
        action_idempotency_key=submitted.action_idempotency_key,
        retried_at_utc="2026-02-09T19:00:03.000000Z",
    )
    assert retried.submission_status == SUBMIT_SUBMITTED
    assert retried.submit_attempt_count == 2

    statuses = _action_submit_statuses(ledger, intake.case_id)
    assert statuses == ["REQUESTED", "SUBMIT_FAILED_RETRYABLE", "SUBMITTED"]


def test_phase6_retry_limit_escalates_to_fatal_submit_failure(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase6_retry_limit.sqlite")
    writer = _StubActionWriter(
        [
            ActionSubmitWriteResult(status=AL_SUBMIT_PENDING, reason_code="AL_UNAVAILABLE"),
            ActionSubmitWriteResult(status=AL_SUBMIT_PENDING, reason_code="AL_UNAVAILABLE"),
            ActionSubmitWriteResult(status=AL_SUBMIT_PENDING, reason_code="AL_UNAVAILABLE"),
        ]
    )
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    submitted = coordinator.submit_manual_action(
        **_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
        )
    )
    assert submitted.submission_status == SUBMIT_FAILED_RETRYABLE
    coordinator.retry_pending(
        action_idempotency_key=submitted.action_idempotency_key,
        retried_at_utc="2026-02-09T19:00:03.000000Z",
    )
    limit = coordinator.retry_pending(
        action_idempotency_key=submitted.action_idempotency_key,
        retried_at_utc="2026-02-09T19:00:04.000000Z",
    )
    assert limit.submission_status == SUBMIT_FAILED_FATAL
    assert limit.reason_code == "RETRY_LIMIT_EXCEEDED"

    projection = ledger.project_case(intake.case_id)
    assert projection is not None
    assert projection.pending_action_outcome is False
    assert projection.status == "ACTION_FAILED"


def test_phase6_payload_mismatch_is_fail_closed_and_logged(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase6_mismatch.sqlite")
    writer = _StubActionWriter([ActionSubmitWriteResult(status=AL_SUBMIT_ACCEPTED, reason_code="AL_ACCEPTED")])
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    first = coordinator.submit_manual_action(
        **_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            reason_code="MANUAL_BLOCK_REQUESTED",
        )
    )
    assert first.submission_status == SUBMIT_SUBMITTED

    mismatch = coordinator.submit_manual_action(
        **_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            reason_code="MANUAL_BLOCK_REASON_CHANGED",
        )
    )
    assert mismatch.disposition == ACTION_PAYLOAD_MISMATCH
    assert mismatch.reason_code == "PAYLOAD_MISMATCH"

    with sqlite3.connect(locator) as conn:
        row = conn.execute("SELECT COUNT(1) FROM cm_action_intent_mismatches").fetchone()
    assert int(row[0] or 0) == 1


def test_phase6_attach_action_outcome_by_ref_updates_projection(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase6_outcome.sqlite")
    writer = _StubActionWriter([ActionSubmitWriteResult(status=AL_SUBMIT_ACCEPTED, reason_code="AL_ACCEPTED")])
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    submitted = coordinator.submit_manual_action(
        **_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
        )
    )

    attached = coordinator.attach_action_outcome(
        case_id=intake.case_id,
        action_idempotency_key=submitted.action_idempotency_key,
        action_outcome_id="outcome_001",
        outcome_status=OUTCOME_DENIED,
        observed_at_utc="2026-02-09T19:00:05.000000Z",
        actor_id="SYSTEM::case_evidence_bridge",
        source_type="SYSTEM",
        evidence_refs=[{"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_outcome_001"}],
        outcome_ref="dla://audit/outcome_001",
    )
    assert attached.outcome_status == OUTCOME_DENIED

    projection = ledger.project_case(intake.case_id)
    assert projection is not None
    assert projection.pending_action_outcome is False
    assert projection.status == "ACTION_FAILED"

    timeline_types = [item.timeline_event_type for item in ledger.list_timeline_events(intake.case_id)]
    assert timeline_types[-1] == "ACTION_OUTCOME_ATTACHED"


def test_phase6_attach_action_outcome_unknown_key_fails_closed(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase6_bad_key.sqlite")
    writer = _StubActionWriter([])
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    with pytest.raises(CaseActionHandshakeError):
        coordinator.attach_action_outcome(
            case_id=intake.case_id,
            action_idempotency_key="a" * 64,
            action_outcome_id="outcome_001",
            outcome_status=OUTCOME_DENIED,
            observed_at_utc="2026-02-09T19:00:05.000000Z",
            actor_id="SYSTEM::case_evidence_bridge",
            source_type="SYSTEM",
            evidence_refs=[{"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_outcome_001"}],
        )
