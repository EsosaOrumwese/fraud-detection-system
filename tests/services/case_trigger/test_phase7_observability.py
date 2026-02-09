from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.case_trigger.observability import (
    CaseTriggerGovernanceEmitter,
    CaseTriggerObservabilityError,
    CaseTriggerRunMetrics,
)
from fraud_detection.case_trigger.publish import (
    PUBLISH_ADMIT,
    PUBLISH_AMBIGUOUS,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
)
from fraud_detection.case_trigger.reconciliation import (
    CaseTriggerReconciliationBuilder,
    CaseTriggerReconciliationError,
)
from fraud_detection.case_trigger.replay import REPLAY_MATCH, REPLAY_PAYLOAD_MISMATCH
from fraud_detection.scenario_runner.storage import LocalObjectStore


def _trigger_payload(
    *,
    source_ref_id: str = "decision:dec_001",
    severity: str = "HIGH",
) -> dict[str, object]:
    suffix = source_ref_id.split(":")[-1]
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T164200Z",
            "event_class": "traffic_fraud",
            "event_id": "evt_case_trigger_001",
        },
        "pins": {
            "platform_run_id": "platform_20260209T164200Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": "2026-02-09T16:42:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": suffix},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": f"audit_{suffix}"},
        ],
        "trigger_payload": {"severity": severity},
    }


def test_phase7_metrics_counts_publish_outcomes_and_exports(tmp_path: Path) -> None:
    metrics = CaseTriggerRunMetrics(
        platform_run_id="platform_20260209T164200Z",
        scenario_run_id="1" * 32,
    )
    metrics.record_trigger_seen(trigger_payload=_trigger_payload())
    metrics.record_publish(decision=PUBLISH_ADMIT)
    metrics.record_publish(decision=PUBLISH_DUPLICATE)
    metrics.record_publish(decision=PUBLISH_QUARANTINE)
    metrics.record_publish(decision=PUBLISH_AMBIGUOUS, reason_code="IG_PUSH_RETRY_EXHAUSTED:timeout")

    snapshot = metrics.snapshot(generated_at_utc="2026-02-09T16:42:10.000000Z")
    assert snapshot["metrics"]["triggers_seen"] == 1
    assert snapshot["metrics"]["published"] == 1
    assert snapshot["metrics"]["duplicates"] == 1
    assert snapshot["metrics"]["quarantine"] == 1
    assert snapshot["metrics"]["publish_ambiguous"] == 1

    out = tmp_path / "case_trigger_metrics.json"
    exported = metrics.export(output_path=out, generated_at_utc="2026-02-09T16:42:11.000000Z")
    assert out.exists()
    assert exported["platform_run_id"] == "platform_20260209T164200Z"


def test_phase7_metrics_rejects_run_scope_mismatch() -> None:
    metrics = CaseTriggerRunMetrics(
        platform_run_id="platform_20260209T164200Z",
        scenario_run_id="1" * 32,
    )
    bad = _trigger_payload()
    bad_pins = dict(bad["pins"])  # type: ignore[index]
    bad_pins["platform_run_id"] = "platform_20260209T999999Z"
    bad["pins"] = bad_pins
    with pytest.raises(CaseTriggerObservabilityError):
        metrics.record_trigger_seen(trigger_payload=bad)


def test_phase7_governance_emits_structured_corridor_anomalies(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "fraud-platform")
    emitter = CaseTriggerGovernanceEmitter(
        store=store,
        platform_run_id="platform_20260209T164200Z",
        scenario_run_id="1" * 32,
        run_config_digest="a" * 64,
        environment="test",
        config_revision="test-v0",
    )

    first = emitter.emit_collision_anomaly(case_trigger_id="b" * 32)
    assert first is not None
    duplicate = emitter.emit_collision_anomaly(case_trigger_id="b" * 32)
    assert duplicate is None

    publish = emitter.emit_publish_anomaly(
        case_trigger_id="c" * 32,
        publish_decision=PUBLISH_AMBIGUOUS,
        reason_code="IG_PUSH_RETRY_EXHAUSTED:timeout",
        receipt_ref="runs/fraud-platform/platform_20260209T164200Z/ig/receipts/r1.json",
    )
    assert publish is not None
    assert publish["details"]["anomaly_category"] == "PUBLISH_AMBIGUOUS"

    events_path = tmp_path / "fraud-platform" / "platform_20260209T164200Z" / "obs" / "governance" / "events.jsonl"
    lines = [line for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert {item["event_family"] for item in events} == {"CORRIDOR_ANOMALY"}
    assert all(item["actor"]["actor_id"] == "SYSTEM::case_trigger" for item in events)


def test_phase7_reconciliation_exports_refs_and_counters(tmp_path: Path) -> None:
    builder = CaseTriggerReconciliationBuilder(
        platform_run_id="platform_20260209T164200Z",
        scenario_run_id="1" * 32,
    )
    first = _trigger_payload(source_ref_id="decision:dec_001")
    second = _trigger_payload(source_ref_id="decision:dec_002")
    builder.add_record(
        trigger_payload=first,
        publish_record={
            "decision": PUBLISH_ADMIT,
            "receipt_ref": "runs/fraud-platform/platform_20260209T164200Z/ig/receipts/r1.json",
        },
        replay_outcome=REPLAY_MATCH,
    )
    builder.add_record(
        trigger_payload=second,
        publish_record={"decision": PUBLISH_DUPLICATE},
        replay_outcome=REPLAY_PAYLOAD_MISMATCH,
    )

    out = tmp_path / "case_trigger_reconciliation.json"
    payload = builder.export(output_path=out, generated_at_utc="2026-02-09T16:42:20.000000Z")
    assert out.exists()
    assert payload["totals"]["triggers_seen"] == 2
    assert payload["totals"]["published"] == 1
    assert payload["totals"]["duplicates"] == 1
    assert payload["totals"]["payload_mismatch"] == 1
    assert len(payload["evidence_refs"]) == 1


def test_phase7_reconciliation_rejects_run_scope_mismatch() -> None:
    builder = CaseTriggerReconciliationBuilder(
        platform_run_id="platform_20260209T164200Z",
        scenario_run_id="1" * 32,
    )
    bad = _trigger_payload()
    pins = dict(bad["pins"])  # type: ignore[index]
    pins["scenario_run_id"] = "9" * 32
    bad["pins"] = pins
    with pytest.raises(CaseTriggerReconciliationError):
        builder.add_record(trigger_payload=bad)
