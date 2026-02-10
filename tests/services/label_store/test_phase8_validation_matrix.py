from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from fraud_detection.case_mgmt import (
    EMISSION_ACCEPTED,
    EMISSION_PENDING,
    INTAKE_NEW_TRIGGER,
    CaseLabelHandshakeCoordinator,
    CaseTriggerIntakeLedger,
    load_label_emission_policy,
)
from fraud_detection.label_store import (
    LS_AS_OF_RESOLVED,
    LS_WRITE_ACCEPTED,
    LS_WRITE_REJECTED,
    REASON_ASSERTION_REPLAY_MATCH,
    REASON_CONTRACT_INVALID,
    REASON_PAYLOAD_HASH_MISMATCH,
    LabelStoreRunReporter,
    LabelStoreWriterBoundary,
)


SCENARIO_RUN_ID = "1" * 32


@dataclass(frozen=True)
class _Processed:
    case_id: str
    source_case_event_id: str
    event_id: str
    label_assertion_id: str
    assertion_ref: str | None
    label_submission: dict[str, Any]


class _UnavailableWriter:
    def write_label_assertion(self, assertion_payload: Mapping[str, Any]) -> Any:  # pragma: no cover - simple stub
        raise RuntimeError("label store unavailable")


def _pins(*, platform_run_id: str, scenario_run_id: str = SCENARIO_RUN_ID) -> dict[str, object]:
    return {
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 91,
    }


def _trigger_payload(
    *,
    platform_run_id: str,
    scenario_run_id: str,
    index: int,
) -> dict[str, object]:
    event_id = f"evt_ls_case_{index:06d}"
    minute = index % 60
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": f"decision:dec_ls_{index:06d}",
        "case_subject_key": {
            "platform_run_id": platform_run_id,
            "event_class": "traffic_fraud",
            "event_id": event_id,
        },
        "pins": _pins(platform_run_id=platform_run_id, scenario_run_id=scenario_run_id),
        "observed_time": f"2026-02-09T21:{minute:02d}:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": f"dec_ls_{index:06d}"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_ls_{index:06d}"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def _label_submission(
    *,
    platform_run_id: str,
    scenario_run_id: str,
    case_id: str,
    source_case_event_id: str,
    index: int,
    label_value: str = "FRAUD_CONFIRMED",
) -> dict[str, Any]:
    event_id = f"evt_ls_case_{index:06d}"
    minute = index % 60
    return {
        "case_id": case_id,
        "source_case_event_id": source_case_event_id,
        "label_subject_key": {
            "platform_run_id": platform_run_id,
            "event_id": event_id,
        },
        "pins": _pins(platform_run_id=platform_run_id, scenario_run_id=scenario_run_id),
        "label_type": "fraud_disposition",
        "label_value": label_value,
        "effective_time": f"2026-02-09T21:{minute:02d}:03.000000Z",
        "observed_time": f"2026-02-09T21:{minute:02d}:03.000000Z",
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_01",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": f"dec_ls_{index:06d}"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_ls_{index:06d}"},
        ],
        "requested_at_utc": f"2026-02-09T21:{minute:02d}:04.000000Z",
        "label_payload": {"notes": "ls phase8 parity assertion"},
    }


def _assertion_payload_from_submission(submission: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_timeline_event_id": submission["source_case_event_id"],
        "label_subject_key": dict(submission["label_subject_key"]),
        "pins": dict(submission["pins"]),
        "label_type": submission["label_type"],
        "label_value": submission["label_value"],
        "effective_time": submission["effective_time"],
        "observed_time": submission["observed_time"],
        "source_type": submission["source_type"],
        "actor_id": submission["actor_id"],
        "evidence_refs": [dict(item) for item in submission["evidence_refs"]],
        "label_payload": dict(submission.get("label_payload") or {}),
    }


def _build_stack(
    *,
    locator: str,
    label_store_writer: Any,
) -> tuple[CaseTriggerIntakeLedger, CaseLabelHandshakeCoordinator]:
    ledger = CaseTriggerIntakeLedger(locator)
    policy = load_label_emission_policy(Path("config/platform/case_mgmt/label_emission_policy_v0.yaml"))
    label = CaseLabelHandshakeCoordinator(
        locator=locator,
        intake_ledger=ledger,
        policy=policy,
        label_store_writer=label_store_writer,
    )
    return ledger, label


def _process_event(
    *,
    index: int,
    platform_run_id: str,
    scenario_run_id: str,
    ledger: CaseTriggerIntakeLedger,
    label: CaseLabelHandshakeCoordinator,
) -> _Processed:
    intake = ledger.ingest_case_trigger(
        payload=_trigger_payload(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            index=index,
        ),
        ingested_at_utc=f"2026-02-09T21:{index % 60:02d}:01.000000Z",
    )
    assert intake.outcome == INTAKE_NEW_TRIGGER

    submission = _label_submission(
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        case_id=intake.case_id,
        source_case_event_id=intake.timeline_event_id,
        index=index,
    )
    result = label.submit_label_assertion(**submission)
    assert result.status == EMISSION_ACCEPTED

    return _Processed(
        case_id=intake.case_id,
        source_case_event_id=intake.timeline_event_id,
        event_id=f"evt_ls_case_{index:06d}",
        label_assertion_id=result.label_assertion_id,
        assertion_ref=result.assertion_ref,
        label_submission=submission,
    )


def _artifact_run_root(platform_run_id: str) -> Path:
    root = Path("runs/fraud-platform") / platform_run_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def test_phase8_end_to_end_continuity_cm_to_ls_ack_to_as_of_read(tmp_path: Path) -> None:
    platform_run_id = "platform_20260209T213000Z"
    scenario_run_id = SCENARIO_RUN_ID
    locator = str(tmp_path / "ls_phase8_continuity.sqlite")

    writer = LabelStoreWriterBoundary(locator)
    ledger, label = _build_stack(locator=locator, label_store_writer=writer)
    processed = _process_event(
        index=0,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        ledger=ledger,
        label=label,
    )

    assertion = writer.lookup_assertion(label_assertion_id=processed.label_assertion_id)
    assert assertion is not None
    assert assertion.assertion_ref.endswith(f"{processed.label_assertion_id}.json")
    assert processed.assertion_ref == assertion.assertion_ref

    as_of = writer.label_as_of(
        platform_run_id=platform_run_id,
        event_id=processed.event_id,
        label_type="fraud_disposition",
        as_of_observed_time=processed.label_submission["observed_time"],
    )
    assert as_of.status == LS_AS_OF_RESOLVED
    assert as_of.selected_assertion_id == processed.label_assertion_id
    assert as_of.selected_label_value == "FRAUD_CONFIRMED"

    run_root = _artifact_run_root(platform_run_id)
    reporter = LabelStoreRunReporter(
        locator=locator,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )
    exported = reporter.export(output_root=run_root)
    assert int(exported["metrics"]["accepted"]) == 1
    assert int(exported["metrics"]["rejected"]) == 0
    assert int(exported["metrics"]["pending"]) == 0

    governance_path = run_root / "label_store" / "governance" / "events.jsonl"
    governance_events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert governance_events
    assert governance_events[0]["lifecycle_type"] == "LABEL_ACCEPTED"
    assert governance_events[0]["details"]["evidence_refs"]


@pytest.mark.parametrize(
    ("event_count", "platform_run_id"),
    [
        (20, "platform_20260209T213020Z"),
        (200, "platform_20260209T213200Z"),
    ],
)
def test_phase8_component_local_parity_proof(
    event_count: int,
    platform_run_id: str,
    tmp_path: Path,
) -> None:
    scenario_run_id = SCENARIO_RUN_ID
    locator = str(tmp_path / f"ls_phase8_parity_{event_count}.sqlite")
    writer = LabelStoreWriterBoundary(locator)
    ledger, label = _build_stack(locator=locator, label_store_writer=writer)

    processed: list[_Processed] = []
    as_of_resolved_total = 0
    duplicate_replay_total = 0
    assertion_refs: list[str] = []
    for index in range(event_count):
        item = _process_event(
            index=index,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            ledger=ledger,
            label=label,
        )
        processed.append(item)
        if item.assertion_ref:
            assertion_refs.append(item.assertion_ref)
        as_of = writer.label_as_of(
            platform_run_id=platform_run_id,
            event_id=item.event_id,
            label_type="fraud_disposition",
            as_of_observed_time=item.label_submission["observed_time"],
        )
        assert as_of.status == LS_AS_OF_RESOLVED
        as_of_resolved_total += 1

        replay = writer.write_label_assertion(_assertion_payload_from_submission(item.label_submission))
        assert replay.status == LS_WRITE_ACCEPTED
        assert replay.reason_code == REASON_ASSERTION_REPLAY_MATCH
        duplicate_replay_total += 1

    run_root = _artifact_run_root(platform_run_id)
    reporter = LabelStoreRunReporter(
        locator=locator,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )
    payload = reporter.export(output_root=run_root)
    metrics = payload["metrics"]

    reasons: list[str] = []
    if int(metrics["accepted"]) != event_count:
        reasons.append(f"ACCEPTED_MISMATCH:{metrics['accepted']}:{event_count}")
    if int(metrics["rejected"]) != 0:
        reasons.append(f"REJECTED_NONZERO:{metrics['rejected']}")
    if int(metrics["pending"]) != 0:
        reasons.append(f"PENDING_NONZERO:{metrics['pending']}")
    if int(metrics["duplicate"]) != event_count:
        reasons.append(f"DUPLICATE_MISMATCH:{metrics['duplicate']}:{event_count}")
    if as_of_resolved_total != event_count:
        reasons.append(f"AS_OF_RESOLVED_MISMATCH:{as_of_resolved_total}:{event_count}")
    if duplicate_replay_total != event_count:
        reasons.append(f"DUPLICATE_REPLAY_LOOP_MISMATCH:{duplicate_replay_total}:{event_count}")
    if int(payload["anomalies"]["total"]) != 0:
        reasons.append(f"ANOMALIES_NONZERO:{payload['anomalies']['total']}")

    artifact_path = run_root / "label_store" / "reconciliation" / f"phase8_parity_proof_{event_count}.json"
    proof_payload = {
        "expected_events": event_count,
        "labels_accepted": int(metrics["accepted"]),
        "labels_rejected": int(metrics["rejected"]),
        "labels_pending": int(metrics["pending"]),
        "labels_duplicate_replay": int(metrics["duplicate"]),
        "as_of_resolved_total": as_of_resolved_total,
        "anomalies_total": int(payload["anomalies"]["total"]),
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "evidence_refs": [
            {"ref_type": "RECONCILIATION", "ref_id": "label_store/reconciliation/last_reconciliation.json"},
            {"ref_type": "GOVERNANCE", "ref_id": "label_store/governance/events.jsonl"},
            {
                "ref_type": "CASE_LABELS_RECONCILIATION",
                "ref_id": "case_labels/reconciliation/label_store_reconciliation.json",
            },
        ],
        "assertion_refs_sample": sorted(assertion_refs)[:5],
        "artifact_path": str(artifact_path),
    }
    _write_json(artifact_path, proof_payload)
    assert proof_payload["status"] == "PASS"


def test_phase8_negative_path_proof(tmp_path: Path) -> None:
    platform_run_id = "platform_20260209T213400Z"
    scenario_run_id = "4" * 32
    locator = str(tmp_path / "ls_phase8_negative.sqlite")
    writer = LabelStoreWriterBoundary(locator)
    ledger, label = _build_stack(locator=locator, label_store_writer=writer)

    processed = _process_event(
        index=1,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        ledger=ledger,
        label=label,
    )
    base_payload = _assertion_payload_from_submission(processed.label_submission)

    duplicate = writer.write_label_assertion(base_payload)
    mismatch_payload = dict(base_payload)
    mismatch_payload["label_value"] = "LEGIT_CONFIRMED"
    mismatch = writer.write_label_assertion(mismatch_payload)
    invalid_subject_payload = dict(base_payload)
    invalid_subject_payload["label_subject_key"] = {
        "platform_run_id": platform_run_id,
        "event_id": "",
    }
    invalid_subject = writer.write_label_assertion(invalid_subject_payload)

    unavailable_ledger, unavailable_label = _build_stack(
        locator=locator,
        label_store_writer=_UnavailableWriter(),
    )
    unavailable_intake = unavailable_ledger.ingest_case_trigger(
        payload=_trigger_payload(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            index=2,
        ),
        ingested_at_utc="2026-02-09T21:02:01.000000Z",
    )
    pending_submission = _label_submission(
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        case_id=unavailable_intake.case_id,
        source_case_event_id=unavailable_intake.timeline_event_id,
        index=2,
    )
    unavailable = unavailable_label.submit_label_assertion(**pending_submission)

    run_root = _artifact_run_root(platform_run_id)
    reporter = LabelStoreRunReporter(
        locator=locator,
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )
    payload = reporter.export(output_root=run_root)
    metrics = payload["metrics"]

    as_of = writer.label_as_of(
        platform_run_id=platform_run_id,
        event_id=processed.event_id,
        label_type="fraud_disposition",
        as_of_observed_time=processed.label_submission["observed_time"],
    )
    assert as_of.status == LS_AS_OF_RESOLVED
    assert as_of.selected_label_value == "FRAUD_CONFIRMED"

    reasons: list[str] = []
    if duplicate.status != LS_WRITE_ACCEPTED or duplicate.reason_code != REASON_ASSERTION_REPLAY_MATCH:
        reasons.append(f"DUPLICATE_REPLAY_UNEXPECTED:{duplicate.status}:{duplicate.reason_code}")
    if mismatch.status != LS_WRITE_REJECTED or mismatch.reason_code != REASON_PAYLOAD_HASH_MISMATCH:
        reasons.append(f"HASH_MISMATCH_UNEXPECTED:{mismatch.status}:{mismatch.reason_code}")
    if invalid_subject.status != LS_WRITE_REJECTED:
        reasons.append(f"INVALID_SUBJECT_STATUS_UNEXPECTED:{invalid_subject.status}:{invalid_subject.reason_code}")
    if not str(invalid_subject.reason_code or "").startswith(REASON_CONTRACT_INVALID):
        reasons.append(f"INVALID_SUBJECT_REASON_UNEXPECTED:{invalid_subject.reason_code}")
    if unavailable.status != EMISSION_PENDING:
        reasons.append(f"UNAVAILABLE_WRITER_STATUS_UNEXPECTED:{unavailable.status}:{unavailable.reason_code}")
    if not str(unavailable.reason_code or "").startswith("LS_WRITE_EXCEPTION:"):
        reasons.append(f"UNAVAILABLE_WRITER_REASON_UNEXPECTED:{unavailable.reason_code}")
    if int(metrics["accepted"]) != 1:
        reasons.append(f"ACCEPTED_MISMATCH:{metrics['accepted']}:1")
    if int(metrics["rejected"]) != 1:
        reasons.append(f"REJECTED_MISMATCH:{metrics['rejected']}:1")
    if int(metrics["pending"]) != 0:
        reasons.append(f"PENDING_NONZERO:{metrics['pending']}")
    if int(metrics["duplicate"]) != 1:
        reasons.append(f"DUPLICATE_MISMATCH:{metrics['duplicate']}:1")

    artifact_path = run_root / "label_store" / "reconciliation" / "phase8_negative_path_proof.json"
    proof_payload = {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "negative_paths": {
            "hash_mismatch": {
                "status": mismatch.status,
                "reason_code": mismatch.reason_code,
            },
            "duplicate_assertion": {
                "status": duplicate.status,
                "reason_code": duplicate.reason_code,
            },
            "invalid_subject": {
                "status": invalid_subject.status,
                "reason_code": invalid_subject.reason_code,
            },
            "unavailable_writer_store": {
                "status": unavailable.status,
                "reason_code": unavailable.reason_code,
            },
        },
        "reconciliation_counts": {
            "accepted": int(metrics["accepted"]),
            "rejected": int(metrics["rejected"]),
            "pending": int(metrics["pending"]),
            "duplicate": int(metrics["duplicate"]),
        },
        "evidence_refs": [
            {"ref_type": "RECONCILIATION", "ref_id": "label_store/reconciliation/last_reconciliation.json"},
            {"ref_type": "GOVERNANCE", "ref_id": "label_store/governance/events.jsonl"},
            {"ref_type": "ASSERTION", "ref_id": processed.assertion_ref or ""},
        ],
        "artifact_path": str(artifact_path),
    }
    _write_json(artifact_path, proof_payload)
    assert proof_payload["status"] == "PASS"
