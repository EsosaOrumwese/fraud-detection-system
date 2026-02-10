from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any

import pytest

from fraud_detection.case_mgmt import (
    AL_SUBMIT_ACCEPTED,
    EMISSION_ACCEPTED,
    EMISSION_DUPLICATE,
    EMISSION_PENDING,
    INTAKE_DUPLICATE_TRIGGER,
    INTAKE_NEW_TRIGGER,
    INTAKE_TRIGGER_PAYLOAD_MISMATCH,
    LS_WRITE_ACCEPTED,
    SUBMIT_SUBMITTED,
    ActionSubmitWriteResult,
    CaseActionHandshakeCoordinator,
    CaseLabelHandshakeCoordinator,
    CaseMgmtRunReporter,
    CaseTriggerIntakeLedger,
    LabelStoreWriteResult,
    load_action_emission_policy,
    load_label_emission_policy,
)


PINS = {
    "platform_run_id": "platform_20260209T210000Z",
    "scenario_run_id": "1" * 32,
    "manifest_fingerprint": "2" * 64,
    "parameter_hash": "3" * 64,
    "scenario_id": "scenario.v0",
    "seed": 84,
}


@dataclass
class _ActionWriter:
    calls: int = 0

    def write_action_intent(self, intent_payload: dict[str, Any]) -> ActionSubmitWriteResult:
        self.calls += 1
        return ActionSubmitWriteResult(
            status=AL_SUBMIT_ACCEPTED,
            reason_code="AL_ACCEPTED",
            intent_ref=f"al://intent/{self.calls:06d}",
        )


@dataclass
class _LabelWriter:
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
        return LabelStoreWriteResult(
            status=LS_WRITE_ACCEPTED,
            reason_code="LS_ACCEPTED",
            assertion_ref=f"ls://assertions/{self.calls:06d}",
        )


@dataclass(frozen=True)
class _Processed:
    case_id: str
    case_trigger_id: str
    trigger_payload: dict[str, Any]
    trigger_timeline_event_id: str
    action_outcome_timeline_event_id: str
    action_outcome_id: str
    label_assertion_id: str
    label_submission: dict[str, Any]


@dataclass(frozen=True)
class _ParityProof:
    expected_events: int
    case_triggers: int
    cases_created: int
    timeline_events_appended: int
    label_assertions: int
    labels_accepted: int
    labels_pending: int
    labels_rejected: int
    action_submitted: int
    action_outcome_attached: int
    trigger_replay_total: int
    trigger_mismatch_total: int
    anomalies_total: int
    status: str
    reasons: tuple[str, ...]
    artifact_path: str


def _trigger_payload(*, index: int, severity: str = "HIGH") -> dict[str, Any]:
    decision_ref = f"dec_{index:06d}"
    event_id = f"evt_case_{index:06d}"
    minute = index % 60
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": f"decision:{decision_ref}",
        "case_subject_key": {
            "platform_run_id": PINS["platform_run_id"],
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "pins": dict(PINS),
        "observed_time": f"2026-02-09T21:{minute:02d}:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": decision_ref},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{decision_ref}"},
        ],
        "trigger_payload": {"severity": severity},
    }


def _label_submission(
    *,
    case_id: str,
    source_case_event_id: str,
    index: int,
    action_outcome_id: str,
) -> dict[str, Any]:
    event_id = f"evt_case_{index:06d}"
    minute = index % 60
    return {
        "case_id": case_id,
        "source_case_event_id": source_case_event_id,
        "label_subject_key": {
            "platform_run_id": PINS["platform_run_id"],
            "event_id": event_id,
        },
        "pins": dict(PINS),
        "label_type": "fraud_disposition",
        "label_value": "FRAUD_CONFIRMED",
        "effective_time": f"2026-02-09T21:{minute:02d}:03.000000Z",
        "observed_time": f"2026-02-09T21:{minute:02d}:03.000000Z",
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_01",
        "evidence_refs": [
            {"ref_type": "ACTION_OUTCOME", "ref_id": action_outcome_id},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_outcome_{index:06d}"},
        ],
        "requested_at_utc": f"2026-02-09T21:{minute:02d}:04.000000Z",
        "label_payload": {"notes": "phase8 parity adjudication"},
    }


def _submission_time(index: int) -> str:
    minute = index % 60
    return f"2026-02-09T21:{minute:02d}:01.000000Z"


def _build_stack(locator: str, *, label_writer: _LabelWriter | None = None) -> tuple[
    CaseTriggerIntakeLedger,
    CaseActionHandshakeCoordinator,
    CaseLabelHandshakeCoordinator,
    _LabelWriter,
]:
    ledger = CaseTriggerIntakeLedger(locator)
    action = CaseActionHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=load_action_emission_policy(Path("config/platform/case_mgmt/action_emission_policy_v0.yaml")),
        action_intent_writer=_ActionWriter(),
    )
    chosen_writer = label_writer or _LabelWriter(outcomes=[])
    label = CaseLabelHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=load_label_emission_policy(Path("config/platform/case_mgmt/label_emission_policy_v0.yaml")),
        label_store_writer=chosen_writer,
    )
    return ledger, action, label, chosen_writer


def _process_event(
    *,
    index: int,
    ledger: CaseTriggerIntakeLedger,
    action: CaseActionHandshakeCoordinator,
    label: CaseLabelHandshakeCoordinator,
) -> _Processed:
    payload = _trigger_payload(index=index)
    intake = ledger.ingest_case_trigger(
        payload=payload,
        ingested_at_utc=_submission_time(index),
    )
    assert intake.outcome == INTAKE_NEW_TRIGGER

    action_result = action.submit_manual_action(
        case_id=intake.case_id,
        source_case_event_id=intake.timeline_event_id,
        action_kind="BLOCK_ACCOUNT",
        target_ref={"ref_type": "ACCOUNT", "ref_id": f"acct_{index:06d}"},
        pins=dict(PINS),
        actor_principal="HUMAN::investigator_01",
        source_type="HUMAN",
        requested_at_utc=f"2026-02-09T21:{index % 60:02d}:02.000000Z",
        reason_code="MANUAL_BLOCK_REQUESTED",
        evidence_refs=[{"ref_type": "DECISION", "ref_id": f"dec_{index:06d}"}],
    )
    assert action_result.submission_status == SUBMIT_SUBMITTED

    action_outcome_id = f"outcome_{index:06d}"
    attached = action.attach_action_outcome(
        case_id=intake.case_id,
        action_idempotency_key=action_result.action_idempotency_key,
        action_outcome_id=action_outcome_id,
        outcome_status="DENIED",
        observed_at_utc=f"2026-02-09T21:{index % 60:02d}:02.500000Z",
        actor_id="SYSTEM::action_layer",
        source_type="SYSTEM",
        evidence_refs=[{"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_outcome_{index:06d}"}],
        outcome_ref=f"dla://audit/outcome_{index:06d}",
    )
    label_submission = _label_submission(
        case_id=intake.case_id,
        source_case_event_id=attached.timeline_event_id,
        index=index,
        action_outcome_id=action_outcome_id,
    )
    label_result = label.submit_label_assertion(**label_submission)
    assert label_result.status == EMISSION_ACCEPTED

    return _Processed(
        case_id=intake.case_id,
        case_trigger_id=intake.case_trigger_id,
        trigger_payload=payload,
        trigger_timeline_event_id=intake.timeline_event_id,
        action_outcome_timeline_event_id=attached.timeline_event_id,
        action_outcome_id=action_outcome_id,
        label_assertion_id=label_result.label_assertion_id,
        label_submission=label_submission,
    )


def _trigger_replay_total(locator: str) -> int:
    with sqlite3.connect(locator) as conn:
        row = conn.execute("SELECT COALESCE(SUM(replay_count), 0) FROM cm_case_trigger_intake").fetchone()
    return int(row[0] or 0)


def _trigger_mismatch_total(locator: str) -> int:
    with sqlite3.connect(locator) as conn:
        row = conn.execute("SELECT COUNT(1) FROM cm_case_trigger_mismatches").fetchone()
    return int(row[0] or 0)


def test_phase8_end_to_end_continuity_from_rtdl_evidence_to_ls_ack(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase8_continuity.sqlite")
    ledger, action, label, _writer = _build_stack(locator)
    processed = _process_event(index=0, ledger=ledger, action=action, label=label)

    timeline = ledger.list_timeline_events(processed.case_id)
    timeline_types = [row.timeline_event_type for row in timeline]
    assert timeline_types[0] == "CASE_TRIGGERED"
    assert "ACTION_OUTCOME_ATTACHED" in timeline_types
    assert timeline_types[-2:] == ["LABEL_PENDING", "LABEL_ACCEPTED"]

    by_outcome = ledger.find_case_ids_by_linked_ref(ref_type="action_outcome_id", ref_id=processed.action_outcome_id)
    assert processed.case_id in by_outcome
    by_decision = ledger.find_case_ids_by_linked_ref(ref_type="decision_id", ref_id="dec_000000")
    assert processed.case_id in by_decision

    reporter = CaseMgmtRunReporter(
        locator=locator,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    payload = reporter.collect()
    assert payload["metrics"]["case_triggers"] == 1
    assert payload["metrics"]["cases_created"] == 1
    assert payload["metrics"]["labels_accepted"] == 1
    assert payload["metrics"]["action_outcome_attached"] == 1

    export_root = tmp_path / "runs" / PINS["platform_run_id"]
    exported = reporter.export(output_root=export_root)
    assert exported["governance"]["emitted_total"] >= 2
    governance_path = export_root / "case_mgmt" / "governance" / "events.jsonl"
    events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    lifecycle_types = {str(item.get("lifecycle_type") or "") for item in events}
    assert {"LABEL_SUBMITTED", "LABEL_ACCEPTED"}.issubset(lifecycle_types)


@pytest.mark.parametrize("event_count", [20, 200])
def test_phase8_component_local_parity_proof(event_count: int, tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase8_parity.sqlite")
    ledger, action, label, _writer = _build_stack(locator)
    processed: list[_Processed] = []

    for index in range(event_count):
        processed.append(_process_event(index=index, ledger=ledger, action=action, label=label))

    duplicate_replay_total = 0
    duplicate_label_total = 0
    for index, item in enumerate(processed):
        duplicate = ledger.ingest_case_trigger(
            payload=item.trigger_payload,
            ingested_at_utc=f"2026-02-09T22:{index % 60:02d}:01.000000Z",
        )
        assert duplicate.outcome == INTAKE_DUPLICATE_TRIGGER
        duplicate_replay_total += 1

        duplicated_label = label.submit_label_assertion(**item.label_submission)
        assert duplicated_label.disposition == EMISSION_DUPLICATE
        assert duplicated_label.status == EMISSION_ACCEPTED
        duplicate_label_total += 1

    reporter = CaseMgmtRunReporter(
        locator=locator,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    payload = reporter.collect()
    metrics = payload["metrics"]
    replay_total = _trigger_replay_total(locator)
    mismatch_total = _trigger_mismatch_total(locator)

    reasons: list[str] = []
    if int(metrics.get("case_triggers", 0)) != event_count:
        reasons.append(f"CASE_TRIGGERS_MISMATCH:{metrics.get('case_triggers', 0)}:{event_count}")
    if int(metrics.get("cases_created", 0)) != event_count:
        reasons.append(f"CASES_CREATED_MISMATCH:{metrics.get('cases_created', 0)}:{event_count}")
    if int(metrics.get("label_assertions", 0)) != event_count:
        reasons.append(f"LABEL_ASSERTIONS_MISMATCH:{metrics.get('label_assertions', 0)}:{event_count}")
    if int(metrics.get("labels_accepted", 0)) != event_count:
        reasons.append(f"LABELS_ACCEPTED_MISMATCH:{metrics.get('labels_accepted', 0)}:{event_count}")
    if int(metrics.get("labels_pending", 0)) != 0:
        reasons.append(f"LABELS_PENDING_NONZERO:{metrics.get('labels_pending', 0)}")
    if int(metrics.get("labels_rejected", 0)) != 0:
        reasons.append(f"LABELS_REJECTED_NONZERO:{metrics.get('labels_rejected', 0)}")
    if int(metrics.get("action_submitted", 0)) != event_count:
        reasons.append(f"ACTION_SUBMITTED_MISMATCH:{metrics.get('action_submitted', 0)}:{event_count}")
    if int(metrics.get("action_outcome_attached", 0)) != event_count:
        reasons.append(
            f"ACTION_OUTCOME_ATTACHED_MISMATCH:{metrics.get('action_outcome_attached', 0)}:{event_count}"
        )
    if replay_total != event_count:
        reasons.append(f"TRIGGER_REPLAY_MISMATCH:{replay_total}:{event_count}")
    if mismatch_total != 0:
        reasons.append(f"TRIGGER_MISMATCH_NONZERO:{mismatch_total}")
    if int(payload["anomalies"]["total"]) != 0:
        reasons.append(f"ANOMALIES_NONZERO:{payload['anomalies']['total']}")
    if duplicate_replay_total != event_count:
        reasons.append(f"DUPLICATE_REPLAY_LOOP_MISMATCH:{duplicate_replay_total}:{event_count}")
    if duplicate_label_total != event_count:
        reasons.append(f"DUPLICATE_LABEL_LOOP_MISMATCH:{duplicate_label_total}:{event_count}")

    artifact_dir = Path("runs/fraud-platform") / PINS["platform_run_id"] / "case_mgmt" / "reconciliation"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"phase8_parity_proof_{event_count}.json"
    proof = _ParityProof(
        expected_events=event_count,
        case_triggers=int(metrics.get("case_triggers", 0)),
        cases_created=int(metrics.get("cases_created", 0)),
        timeline_events_appended=int(metrics.get("timeline_events_appended", 0)),
        label_assertions=int(metrics.get("label_assertions", 0)),
        labels_accepted=int(metrics.get("labels_accepted", 0)),
        labels_pending=int(metrics.get("labels_pending", 0)),
        labels_rejected=int(metrics.get("labels_rejected", 0)),
        action_submitted=int(metrics.get("action_submitted", 0)),
        action_outcome_attached=int(metrics.get("action_outcome_attached", 0)),
        trigger_replay_total=replay_total,
        trigger_mismatch_total=mismatch_total,
        anomalies_total=int(payload["anomalies"]["total"]),
        status="PASS" if not reasons else "FAIL",
        reasons=tuple(reasons),
        artifact_path=str(artifact_path),
    )
    artifact_path.write_text(
        json.dumps(
            {
                "expected_events": proof.expected_events,
                "case_triggers": proof.case_triggers,
                "cases_created": proof.cases_created,
                "timeline_events_appended": proof.timeline_events_appended,
                "label_assertions": proof.label_assertions,
                "labels_accepted": proof.labels_accepted,
                "labels_pending": proof.labels_pending,
                "labels_rejected": proof.labels_rejected,
                "action_submitted": proof.action_submitted,
                "action_outcome_attached": proof.action_outcome_attached,
                "trigger_replay_total": proof.trigger_replay_total,
                "trigger_mismatch_total": proof.trigger_mismatch_total,
                "anomalies_total": proof.anomalies_total,
                "status": proof.status,
                "reasons": list(proof.reasons),
                "artifact_path": proof.artifact_path,
            },
            sort_keys=True,
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert proof.status == "PASS"


def test_phase8_negative_path_proof_fail_closed_and_retry_idempotency(tmp_path: Path) -> None:
    locator = str(tmp_path / "cm_phase8_negative.sqlite")
    flaky_writer = _LabelWriter(
        outcomes=[
            RuntimeError("ls down"),
            LabelStoreWriteResult(status=LS_WRITE_ACCEPTED, reason_code="LS_ACCEPTED", assertion_ref="ls://assertions/retry"),
        ]
    )
    ledger, _action, label, _writer = _build_stack(locator, label_writer=flaky_writer)

    base_payload = _trigger_payload(index=7, severity="HIGH")
    first = ledger.ingest_case_trigger(payload=base_payload, ingested_at_utc="2026-02-09T21:07:01.000000Z")
    duplicate = ledger.ingest_case_trigger(payload=base_payload, ingested_at_utc="2026-02-09T21:07:02.000000Z")
    mutated_payload = _trigger_payload(index=7, severity="CRITICAL")
    mismatch = ledger.ingest_case_trigger(payload=mutated_payload, ingested_at_utc="2026-02-09T21:07:03.000000Z")

    pending = label.submit_label_assertion(
        **_label_submission(
            case_id=first.case_id,
            source_case_event_id=first.timeline_event_id,
            index=7,
            action_outcome_id="outcome_000007",
        )
    )
    retried = label.retry_pending(
        label_assertion_id=pending.label_assertion_id,
        retried_at_utc="2026-02-09T21:07:05.000000Z",
    )
    duplicate_after_accept = label.submit_label_assertion(
        **_label_submission(
            case_id=first.case_id,
            source_case_event_id=first.timeline_event_id,
            index=7,
            action_outcome_id="outcome_000007",
        )
    )

    reasons: list[str] = []
    if first.outcome != INTAKE_NEW_TRIGGER:
        reasons.append(f"FIRST_TRIGGER_UNEXPECTED:{first.outcome}")
    if duplicate.outcome != INTAKE_DUPLICATE_TRIGGER:
        reasons.append(f"DUPLICATE_NOT_IDEMPOTENT:{duplicate.outcome}")
    if mismatch.outcome != INTAKE_TRIGGER_PAYLOAD_MISMATCH:
        reasons.append(f"MISMATCH_NOT_FAIL_CLOSED:{mismatch.outcome}")
    if pending.status != EMISSION_PENDING:
        reasons.append(f"LS_UNAVAILABLE_NOT_PENDING:{pending.status}")
    if retried.status != EMISSION_ACCEPTED:
        reasons.append(f"RETRY_NOT_ACCEPTED:{retried.status}")
    if retried.label_assertion_id != pending.label_assertion_id:
        reasons.append("RETRY_IDENTITY_DRIFT")
    if duplicate_after_accept.disposition != EMISSION_DUPLICATE:
        reasons.append(f"POST_ACCEPT_DUPLICATE_FAILED:{duplicate_after_accept.disposition}")
    if flaky_writer.calls != 2:
        reasons.append(f"UNEXPECTED_LS_CALL_COUNT:{flaky_writer.calls}:2")

    artifact_dir = Path("runs/fraud-platform") / PINS["platform_run_id"] / "case_mgmt" / "reconciliation"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "phase8_negative_path_proof.json"
    artifact_path.write_text(
        json.dumps(
            {
                "duplicate_trigger_outcome": duplicate.outcome,
                "mismatch_trigger_outcome": mismatch.outcome,
                "label_first_status": pending.status,
                "label_retry_status": retried.status,
                "label_id_stable_across_retry": retried.label_assertion_id == pending.label_assertion_id,
                "post_accept_duplicate_disposition": duplicate_after_accept.disposition,
                "label_writer_calls": flaky_writer.calls,
                "status": "PASS" if not reasons else "FAIL",
                "reasons": reasons,
            },
            sort_keys=True,
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert not reasons
