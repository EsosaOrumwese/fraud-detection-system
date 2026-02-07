from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.decision_log_audit.config import load_intake_policy
from fraud_detection.decision_log_audit.intake import DlaBusInput, DecisionLogAuditIntakeProcessor
from fraud_detection.decision_log_audit.observability import (
    DecisionLogAuditHealthThresholds,
    DecisionLogAuditObservabilityError,
    DecisionLogAuditObservabilityReporter,
    DecisionLogAuditSecurityPolicy,
)
from fraud_detection.decision_log_audit.storage import DecisionLogAuditIntakeStore


PINS = {
    "platform_run_id": "platform_20260207T212000Z",
    "scenario_run_id": "1" * 32,
    "manifest_fingerprint": "2" * 64,
    "parameter_hash": "3" * 64,
    "scenario_id": "scenario.v0",
    "seed": 42,
    "run_id": "1" * 32,
}


def _policy():
    return load_intake_policy(Path("config/platform/dla/intake_policy_v0.yaml"))


def _decision_payload(*, decision_id: str = "a" * 32, amount: float = 100.0) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decision_kind": "txn_disposition",
        "bundle_ref": {"bundle_id": "b" * 64, "bundle_version": "2026.02.07", "registry_ref": "registry://active"},
        "snapshot_hash": "c" * 64,
        "graph_version": {"version_id": "d" * 32, "watermark_ts_utc": "2026-02-07T10:27:00.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "101"}],
        },
        "degrade_posture": {
            "mode": "NORMAL",
            "capabilities_mask": {
                "allow_ieg": True,
                "allowed_feature_groups": ["core_features"],
                "allow_model_primary": True,
                "allow_model_stage2": True,
                "allow_fallback_heuristics": True,
                "action_posture": "NORMAL",
            },
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1"},
            "posture_seq": 3,
            "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        },
        "pins": {
            "platform_run_id": PINS["platform_run_id"],
            "scenario_run_id": PINS["scenario_run_id"],
            "manifest_fingerprint": PINS["manifest_fingerprint"],
            "parameter_hash": PINS["parameter_hash"],
            "scenario_id": PINS["scenario_id"],
            "seed": PINS["seed"],
            "run_id": PINS["run_id"],
        },
        "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8"},
        "run_config_digest": "4" * 64,
        "source_event": {
            "event_id": "evt_src",
            "event_type": "transaction_authorization",
            "ts_utc": "2026-02-07T10:26:59.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "100",
                "offset_kind": "kinesis_sequence",
            },
        },
        "decision": {"disposition": "ALLOW", "amount": amount},
    }


def _envelope(*, event_id: str, decision_id: str = "a" * 32, amount: float = 100.0) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "decision_response",
        "schema_version": "v1",
        "ts_utc": "2026-02-07T10:45:00.000000Z",
        "manifest_fingerprint": PINS["manifest_fingerprint"],
        "parameter_hash": PINS["parameter_hash"],
        "seed": PINS["seed"],
        "scenario_id": PINS["scenario_id"],
        "platform_run_id": PINS["platform_run_id"],
        "scenario_run_id": PINS["scenario_run_id"],
        "run_id": PINS["run_id"],
        "payload": _decision_payload(decision_id=decision_id, amount=amount),
    }


def _process(processor: DecisionLogAuditIntakeProcessor, *, offset: str, payload: dict[str, object]):
    return processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset=offset,
            offset_kind="file_line",
            payload=payload,
        )
    )


def test_phase7_observability_collects_metrics_reconciliation_and_governance(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    _process(processor, offset="0", payload=_envelope(event_id="evt_decision_a"))
    _process(processor, offset="0", payload=_envelope(event_id="evt_decision_drift", amount=999.0))
    _process(processor, offset="1", payload={"bad": "envelope"})

    reporter = DecisionLogAuditObservabilityReporter(
        store=store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
        thresholds=DecisionLogAuditHealthThresholds(
            amber_replay_divergence_total=1,
            red_replay_divergence_total=1,
        ),
    )
    payload = reporter.collect()
    metrics = payload["metrics"]

    assert metrics["append_success_total"] >= 2
    assert metrics["candidate_total"] == 1
    assert metrics["quarantine_total"] >= 1
    assert metrics["replay_divergence_total"] >= 1
    assert payload["health_state"] == "RED"
    assert "REPLAY_DIVERGENCE_RED" in payload["health_reasons"]

    governance = payload["governance_stamps"]
    assert "policy://df.policy.v0@r8" in governance["policy_refs"]
    assert "bundle://%s@2026.02.07" % ("b" * 64) in governance["bundle_refs"]
    assert "4" * 64 in governance["run_config_digests"]


def test_phase7_export_redacts_sensitive_anomaly_details(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)
    _process(processor, offset="0", payload=_envelope(event_id="evt_decision_a"))
    _process(processor, offset="1", payload={"bad": "envelope"})

    store.record_intake_attempt(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="9",
        offset_kind="file_line",
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
        event_type="decision_response",
        event_id="evt_sensitive",
        accepted=False,
        reason_code="TEST_SENSITIVE",
        write_status="NEW",
        checkpoint_advanced=False,
        detail="api_key=super-secret",
    )

    reporter = DecisionLogAuditObservabilityReporter(
        store=store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
        security_policy=DecisionLogAuditSecurityPolicy(allow_custom_output_root=True, allowed_root=tmp_path),
    )
    reporter.export(output_root=tmp_path / PINS["platform_run_id"])
    reconciliation_path = (
        tmp_path / PINS["platform_run_id"] / "decision_log_audit" / "reconciliation" / "last_reconciliation.json"
    )
    payload = json.loads(reconciliation_path.read_text(encoding="utf-8"))
    attempts = payload["reconciliation"]["recent_attempts"]
    sensitive_attempts = [item for item in attempts if item["reason_code"] == "TEST_SENSITIVE"]
    assert sensitive_attempts
    assert sensitive_attempts[0]["detail"] == "[REDACTED]"


def test_phase7_security_policy_blocks_unapproved_output_root(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    reporter = DecisionLogAuditObservabilityReporter(
        store=store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    with pytest.raises(DecisionLogAuditObservabilityError):
        reporter.export(output_root=tmp_path / "outside")
