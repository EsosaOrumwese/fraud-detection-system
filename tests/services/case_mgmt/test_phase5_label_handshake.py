from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from fraud_detection.case_mgmt import (
    EMISSION_ACCEPTED,
    EMISSION_DUPLICATE,
    EMISSION_NEW,
    EMISSION_PAYLOAD_MISMATCH,
    EMISSION_PENDING,
    EMISSION_REJECTED,
    LS_WRITE_ACCEPTED,
    LS_WRITE_PENDING,
    CaseLabelHandshakeCoordinator,
    CaseLabelHandshakeError,
    CaseTriggerIntakeLedger,
    LabelStoreWriteResult,
    load_label_emission_policy,
)


def _trigger_payload(*, source_ref_id: str, event_id: str, observed_time: str) -> dict[str, object]:
    suffix = source_ref_id.split(":")[-1]
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T180000Z",
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "pins": {
            "platform_run_id": "platform_20260209T180000Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 24,
        },
        "observed_time": observed_time,
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": suffix},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{suffix}"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def _label_submission(
    *,
    case_id: str,
    source_case_event_id: str,
    event_id: str,
    label_value: str = "FRAUD_CONFIRMED",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "source_case_event_id": source_case_event_id,
        "label_subject_key": {
            "platform_run_id": "platform_20260209T180000Z",
            "event_id": event_id,
        },
        "pins": {
            "platform_run_id": "platform_20260209T180000Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 24,
        },
        "label_type": "fraud_disposition",
        "label_value": label_value,
        "effective_time": "2026-02-09T18:00:01.000000Z",
        "observed_time": "2026-02-09T18:00:01.000000Z",
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_01",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_dec_001"},
        ],
        "requested_at_utc": "2026-02-09T18:00:02.000000Z",
        "label_payload": {"notes": "manual adjudication"},
    }


@dataclass
class _StubWriter:
    outcomes: list[object]

    def __post_init__(self) -> None:
        self.calls: int = 0
        self.payloads: list[dict[str, Any]] = []

    def write_label_assertion(self, assertion_payload: dict[str, Any]) -> LabelStoreWriteResult:
        self.calls += 1
        self.payloads.append(dict(assertion_payload))
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            if isinstance(outcome, LabelStoreWriteResult):
                return outcome
        return LabelStoreWriteResult(status=LS_WRITE_PENDING, reason_code="LS_PENDING")


def _coordinator(locator: str, writer: _StubWriter) -> tuple[CaseTriggerIntakeLedger, CaseLabelHandshakeCoordinator]:
    ledger = CaseTriggerIntakeLedger(locator)
    policy = load_label_emission_policy(Path("config/platform/case_mgmt/label_emission_policy_v0.yaml"))
    coordinator = CaseLabelHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=policy,
        label_store_writer=writer,
    )
    return ledger, coordinator


def _ingest_case(ledger: CaseTriggerIntakeLedger):
    return ledger.ingest_case_trigger(
        payload=_trigger_payload(
            source_ref_id="decision:dec_001",
            event_id="evt_case_001",
            observed_time="2026-02-09T18:00:00.000000Z",
        ),
        ingested_at_utc="2026-02-09T18:00:00.500000Z",
    )


def test_phase5_pending_then_accepted_timeline_sequence(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase5_accept.sqlite")
    writer = _StubWriter(
        [
            LabelStoreWriteResult(
                status=LS_WRITE_ACCEPTED,
                reason_code="LS_ACCEPTED",
                assertion_ref="ls://assertions/001",
            )
        ]
    )
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    result = coordinator.submit_label_assertion(
        **_label_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            event_id="evt_case_001",
        )
    )

    assert result.disposition == EMISSION_NEW
    assert result.status == EMISSION_ACCEPTED
    assert result.attempt_count == 1

    emission = coordinator.lookup_emission(label_assertion_id=result.label_assertion_id)
    assert emission is not None
    assert emission.status == EMISSION_ACCEPTED
    assert emission.assertion_ref == "ls://assertions/001"

    timeline_types = [item.timeline_event_type for item in ledger.list_timeline_events(intake.case_id)]
    assert timeline_types == ["CASE_TRIGGERED", "LABEL_PENDING", "LABEL_ACCEPTED"]


def test_phase5_retry_advances_pending_to_accepted_without_duplicate_pending_rows(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase5_retry.sqlite")
    writer = _StubWriter(
        [
            LabelStoreWriteResult(status=LS_WRITE_PENDING, reason_code="LS_UNAVAILABLE"),
            LabelStoreWriteResult(status=LS_WRITE_ACCEPTED, reason_code="LS_ACCEPTED"),
        ]
    )
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    submitted = coordinator.submit_label_assertion(
        **_label_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            event_id="evt_case_001",
        )
    )
    assert submitted.status == EMISSION_PENDING
    assert submitted.attempt_count == 1

    retried = coordinator.retry_pending(
        label_assertion_id=submitted.label_assertion_id,
        retried_at_utc="2026-02-09T18:00:03.000000Z",
    )
    assert retried.disposition == EMISSION_DUPLICATE
    assert retried.status == EMISSION_ACCEPTED
    assert retried.attempt_count == 2

    timeline_types = [item.timeline_event_type for item in ledger.list_timeline_events(intake.case_id)]
    assert timeline_types == ["CASE_TRIGGERED", "LABEL_PENDING", "LABEL_ACCEPTED"]


def test_phase5_payload_mismatch_is_fail_closed_and_logged(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase5_mismatch.sqlite")
    writer = _StubWriter([LabelStoreWriteResult(status=LS_WRITE_ACCEPTED, reason_code="LS_ACCEPTED")])
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    first = coordinator.submit_label_assertion(
        **_label_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            event_id="evt_case_001",
            label_value="FRAUD_CONFIRMED",
        )
    )
    assert first.status == EMISSION_ACCEPTED

    mismatch = coordinator.submit_label_assertion(
        **_label_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            event_id="evt_case_001",
            label_value="LEGIT_CONFIRMED",
        )
    )
    assert mismatch.disposition == EMISSION_PAYLOAD_MISMATCH
    assert mismatch.reason_code == "PAYLOAD_MISMATCH"

    with sqlite3.connect(locator) as conn:
        row = conn.execute("SELECT COUNT(1) FROM cm_label_emission_mismatches").fetchone()
    assert int(row[0] or 0) == 1


def test_phase5_retry_limit_emits_label_rejected(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase5_retry_limit.sqlite")
    writer = _StubWriter(
        [
            LabelStoreWriteResult(status=LS_WRITE_PENDING, reason_code="LS_UNAVAILABLE"),
            LabelStoreWriteResult(status=LS_WRITE_PENDING, reason_code="LS_UNAVAILABLE"),
            LabelStoreWriteResult(status=LS_WRITE_PENDING, reason_code="LS_UNAVAILABLE"),
        ]
    )
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    submitted = coordinator.submit_label_assertion(
        **_label_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            event_id="evt_case_001",
        )
    )
    assert submitted.status == EMISSION_PENDING
    assert submitted.attempt_count == 1

    coordinator.retry_pending(
        label_assertion_id=submitted.label_assertion_id,
        retried_at_utc="2026-02-09T18:00:03.000000Z",
    )
    coordinator.retry_pending(
        label_assertion_id=submitted.label_assertion_id,
        retried_at_utc="2026-02-09T18:00:04.000000Z",
    )
    limit = coordinator.retry_pending(
        label_assertion_id=submitted.label_assertion_id,
        retried_at_utc="2026-02-09T18:00:05.000000Z",
    )
    assert limit.status == EMISSION_REJECTED
    assert limit.reason_code == "RETRY_LIMIT_EXCEEDED"
    assert limit.attempt_count == 3

    timeline_types = [item.timeline_event_type for item in ledger.list_timeline_events(intake.case_id)]
    assert timeline_types == ["CASE_TRIGGERED", "LABEL_PENDING", "LABEL_REJECTED"]


def test_phase5_writer_exception_does_not_abort_handshake(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase5_writer_exception.sqlite")
    writer = _StubWriter([RuntimeError("label store unavailable")])
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    result = coordinator.submit_label_assertion(
        **_label_submission(
            case_id=intake.case_id,
            source_case_event_id=intake.timeline_event_id,
            event_id="evt_case_001",
        )
    )
    assert result.status == EMISSION_PENDING
    emission = coordinator.lookup_emission(label_assertion_id=result.label_assertion_id)
    assert emission is not None
    assert emission.last_reason_code is not None
    assert emission.last_reason_code.startswith("LS_WRITE_EXCEPTION:")


def test_phase5_fail_closed_if_source_case_event_ref_unknown(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase5_bad_ref.sqlite")
    writer = _StubWriter([LabelStoreWriteResult(status=LS_WRITE_ACCEPTED, reason_code="LS_ACCEPTED")])
    ledger, coordinator = _coordinator(locator, writer)
    intake = _ingest_case(ledger)

    with pytest.raises(CaseLabelHandshakeError):
        coordinator.submit_label_assertion(
            **_label_submission(
                case_id=intake.case_id,
                source_case_event_id="f" * 32,
                event_id="evt_case_001",
            )
        )
