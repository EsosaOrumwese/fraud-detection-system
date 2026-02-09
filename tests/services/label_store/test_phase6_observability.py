from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.label_store import (
    LabelStoreEvidenceAccessAuditRequest,
    LabelStoreEvidenceAccessAuditor,
    LabelStoreObservabilityError,
    LabelStoreRunReporter,
    LabelStoreWriterBoundary,
)


PLATFORM_RUN_ID = "platform_20260209T210500Z"
SCENARIO_RUN_ID = "1" * 32


def _pins(*, platform_run_id: str = PLATFORM_RUN_ID, scenario_run_id: str = SCENARIO_RUN_ID) -> dict[str, object]:
    return {
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 77,
    }


def _subject(*, platform_run_id: str = PLATFORM_RUN_ID, event_id: str = "evt_ls_001") -> dict[str, str]:
    return {
        "platform_run_id": platform_run_id,
        "event_id": event_id,
    }


def _assertion_payload(
    *,
    case_timeline_event_id: str,
    label_value: str,
    pins: dict[str, object] | None = None,
    subject: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "case_timeline_event_id": case_timeline_event_id,
        "label_subject_key": dict(subject or _subject()),
        "pins": dict(pins or _pins()),
        "label_type": "fraud_disposition",
        "label_value": label_value,
        "effective_time": "2026-02-09T21:05:00.000000Z",
        "observed_time": "2026-02-09T21:06:00.000000Z",
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_007",
        "evidence_refs": [
            {"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "label_payload": {"notes": "top-secret-note-should-not-leak"},
    }


def test_phase6_export_emits_run_scoped_metrics_governance_and_reconciliation(tmp_path: Path) -> None:
    locator = str(tmp_path / "label_store_phase6.sqlite")
    writer = LabelStoreWriterBoundary(locator)

    first_payload = _assertion_payload(case_timeline_event_id="a" * 32, label_value="FRAUD_CONFIRMED")
    writer.write_label_assertion(first_payload)
    writer.write_label_assertion(first_payload)
    mismatch_payload = _assertion_payload(case_timeline_event_id="a" * 32, label_value="LEGIT_CONFIRMED")
    writer.write_label_assertion(mismatch_payload)

    output_root = tmp_path / "runs" / PLATFORM_RUN_ID
    reporter = LabelStoreRunReporter(
        locator=locator,
        platform_run_id=PLATFORM_RUN_ID,
        scenario_run_id=SCENARIO_RUN_ID,
    )
    payload = reporter.export(output_root=output_root)

    metrics = payload["metrics"]
    assert metrics["accepted"] == 1
    assert metrics["duplicate"] == 1
    assert metrics["rejected"] == 1
    assert metrics["pending"] == 0
    assert metrics["payload_hash_mismatch"] == 1
    assert payload["health_state"] in {"AMBER", "RED"}

    lanes = {item["kind"] for item in payload["anomalies"]["lanes"]}
    assert "PAYLOAD_HASH_MISMATCH" in lanes

    governance_path = output_root / "label_store" / "governance" / "events.jsonl"
    assert governance_path.exists()
    governance_events = [
        json.loads(line)
        for line in governance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert governance_events
    assert governance_events[0]["lifecycle_type"] == "LABEL_ACCEPTED"
    assert governance_events[0]["actor"]["actor_id"] == "HUMAN::investigator_007"
    assert "label_payload" not in governance_events[0]["details"]
    assert "top-secret-note-should-not-leak" not in governance_path.read_text(encoding="utf-8")

    metrics_path = output_root / "label_store" / "metrics" / "last_metrics.json"
    health_path = output_root / "label_store" / "health" / "last_health.json"
    reconciliation_path = output_root / "label_store" / "reconciliation" / "last_reconciliation.json"
    assert metrics_path.exists()
    assert health_path.exists()
    assert reconciliation_path.exists()

    day_stamp = str(payload["generated_at_utc"]).split("T", 1)[0]
    dated_reconciliation = output_root / "case_labels" / "reconciliation" / f"{day_stamp}.json"
    latest_reconciliation = output_root / "case_labels" / "reconciliation" / "label_store_reconciliation.json"
    assert dated_reconciliation.exists()
    assert latest_reconciliation.exists()
    summary = json.loads(latest_reconciliation.read_text(encoding="utf-8"))["summary"]
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1


def test_phase6_governance_export_is_idempotent(tmp_path: Path) -> None:
    locator = str(tmp_path / "label_store_phase6_idempotent.sqlite")
    writer = LabelStoreWriterBoundary(locator)
    writer.write_label_assertion(_assertion_payload(case_timeline_event_id="b" * 32, label_value="FRAUD_SUSPECTED"))

    output_root = tmp_path / "runs" / PLATFORM_RUN_ID
    reporter = LabelStoreRunReporter(
        locator=locator,
        platform_run_id=PLATFORM_RUN_ID,
        scenario_run_id=SCENARIO_RUN_ID,
    )
    first = reporter.export(output_root=output_root)
    second = reporter.export(output_root=output_root)

    assert first["governance"]["emitted_total"] > 0
    assert second["governance"]["emitted_total"] == 0
    assert second["governance"]["duplicate_skipped_total"] >= first["governance"]["emitted_total"]


def test_phase6_collect_is_run_scoped_by_platform_and_scenario(tmp_path: Path) -> None:
    locator = str(tmp_path / "label_store_phase6_scope.sqlite")
    writer = LabelStoreWriterBoundary(locator)

    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="c" * 32,
            label_value="FRAUD_CONFIRMED",
            pins=_pins(platform_run_id=PLATFORM_RUN_ID, scenario_run_id=SCENARIO_RUN_ID),
            subject=_subject(platform_run_id=PLATFORM_RUN_ID, event_id="evt_scope_001"),
        )
    )
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="d" * 32,
            label_value="FRAUD_SUSPECTED",
            pins=_pins(platform_run_id=PLATFORM_RUN_ID, scenario_run_id="9" * 32),
            subject=_subject(platform_run_id=PLATFORM_RUN_ID, event_id="evt_scope_002"),
        )
    )
    writer.write_label_assertion(
        _assertion_payload(
            case_timeline_event_id="e" * 32,
            label_value="FRAUD_SUSPECTED",
            pins=_pins(platform_run_id="platform_20260209T211000Z", scenario_run_id=SCENARIO_RUN_ID),
            subject=_subject(platform_run_id="platform_20260209T211000Z", event_id="evt_scope_003"),
        )
    )

    reporter = LabelStoreRunReporter(
        locator=locator,
        platform_run_id=PLATFORM_RUN_ID,
        scenario_run_id=SCENARIO_RUN_ID,
    )
    payload = reporter.collect()
    assert payload["metrics"]["accepted"] == 1


def test_phase6_access_audit_hook_emits_idempotent_allow_and_deny_events(tmp_path: Path) -> None:
    auditor = LabelStoreEvidenceAccessAuditor()
    output_root = tmp_path / "runs" / PLATFORM_RUN_ID

    allowed = auditor.audit(
        LabelStoreEvidenceAccessAuditRequest(
            actor_id="SYSTEM::ofs_reader",
            source_type="SYSTEM",
            purpose="ofs_training_join",
            ref_type="DLA_AUDIT_RECORD",
            ref_id="audit_777",
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id=SCENARIO_RUN_ID,
            resolution_status="ALLOWED",
            dedupe_key="allow-1",
        ),
        output_root=output_root,
    )
    allowed_dup = auditor.audit(
        LabelStoreEvidenceAccessAuditRequest(
            actor_id="SYSTEM::ofs_reader",
            source_type="SYSTEM",
            purpose="ofs_training_join",
            ref_type="DLA_AUDIT_RECORD",
            ref_id="audit_777",
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id=SCENARIO_RUN_ID,
            resolution_status="ALLOWED",
            dedupe_key="allow-1",
        ),
        output_root=output_root,
    )
    denied = auditor.audit(
        LabelStoreEvidenceAccessAuditRequest(
            actor_id="SYSTEM::unknown_reader",
            source_type="SYSTEM",
            purpose="forbidden_read",
            ref_type="DECISION",
            ref_id="dec_777",
            platform_run_id=PLATFORM_RUN_ID,
            scenario_run_id=SCENARIO_RUN_ID,
            resolution_status="DENIED",
            reason_code="ACCESS_DENIED",
            dedupe_key="deny-1",
        ),
        output_root=output_root,
    )

    assert allowed.emitted is True
    assert allowed_dup.emitted is False
    assert denied.emitted is True

    events_path = output_root / "label_store" / "access_audit" / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(events) == 2
    statuses = {item["details"]["resolution_status"] for item in events}
    assert statuses == {"ALLOWED", "DENIED"}

    with pytest.raises(LabelStoreObservabilityError, match="resolution_status must be ALLOWED or DENIED"):
        auditor.audit(
            LabelStoreEvidenceAccessAuditRequest(
                actor_id="SYSTEM::bad",
                source_type="SYSTEM",
                purpose="invalid",
                ref_type="DECISION",
                ref_id="dec_bad",
                platform_run_id=PLATFORM_RUN_ID,
                resolution_status="MAYBE",
            ),
            output_root=output_root,
        )

