from __future__ import annotations

import json
from pathlib import Path
import sqlite3

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


def _action_intent_envelope(*, event_id: str, decision_id: str, action_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "action_intent",
        "schema_version": "v1",
        "ts_utc": "2026-02-07T10:45:01.000000Z",
        "manifest_fingerprint": PINS["manifest_fingerprint"],
        "parameter_hash": PINS["parameter_hash"],
        "seed": PINS["seed"],
        "scenario_id": PINS["scenario_id"],
        "platform_run_id": PINS["platform_run_id"],
        "scenario_run_id": PINS["scenario_run_id"],
        "run_id": PINS["run_id"],
        "payload": {
            "action_id": action_id,
            "decision_id": decision_id,
            "action_kind": "txn_disposition_publish",
            "idempotency_key": "merchant_42:evt_123:publish",
            "pins": {
                "platform_run_id": PINS["platform_run_id"],
                "scenario_run_id": PINS["scenario_run_id"],
                "manifest_fingerprint": PINS["manifest_fingerprint"],
                "parameter_hash": PINS["parameter_hash"],
                "scenario_id": PINS["scenario_id"],
                "seed": PINS["seed"],
                "run_id": PINS["run_id"],
            },
            "requested_at_utc": "2026-02-07T10:45:01.000000Z",
            "actor_principal": "SYSTEM::decision_fabric",
            "origin": "DF",
            "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8"},
            "run_config_digest": "4" * 64,
            "action_payload": {"target": "fraud.disposition"},
        },
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

    processor.process_record(
        DlaBusInput(
            topic="fp.bus.rtdl.v1",
            partition=0,
            offset="0",
            offset_kind="file_line",
            payload=_envelope(event_id="evt_decision_good"),
        )
    )
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
    assert metrics["accepted_total"] == 1
    assert metrics["rejected_total"] >= 1
    assert metrics["candidate_total"] == 1
    assert metrics["quarantine_total"] >= 1
    assert metrics["append_failure_total"] >= 1
    assert payload["health_state"] == "AMBER"
    assert "QUARANTINE_AMBER" in payload["health_reasons"]
    assert "APPEND_FAILURE_AMBER" in payload["health_reasons"]

    governance = payload["governance_stamps"]
    assert "policy://df.policy.v0@r8" in governance["policy_refs"]
    assert "bundle://%s@2026.02.07" % ("b" * 64) in governance["bundle_refs"]
    assert "4" * 64 in governance["run_config_digests"]
    recent_attempts = payload["reconciliation"]["recent_attempts"]
    assert recent_attempts
    first_attempt = recent_attempts[0]
    assert first_attempt["origin_offset"]["topic"] == first_attempt["topic"]
    assert first_attempt["origin_offset"]["partition"] == first_attempt["partition"]
    assert first_attempt["origin_offset"]["offset"] == first_attempt["source_offset"]
    assert first_attempt["origin_offset"]["offset_kind"] == first_attempt["source_offset_kind"]


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
    assert sensitive_attempts[0]["origin_offset"]["offset"] == sensitive_attempts[0]["source_offset"]


def test_phase7_security_policy_blocks_unapproved_output_root(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    reporter = DecisionLogAuditObservabilityReporter(
        store=store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
    )
    with pytest.raises(DecisionLogAuditObservabilityError):
        reporter.export(output_root=tmp_path / "outside")


def test_phase7_zero_state_export_is_readable(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    reporter = DecisionLogAuditObservabilityReporter(
        store=store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
        security_policy=DecisionLogAuditSecurityPolicy(allow_custom_output_root=True, allowed_root=tmp_path),
    )

    payload = reporter.export(output_root=tmp_path / PINS["platform_run_id"])

    metrics_path = tmp_path / PINS["platform_run_id"] / "decision_log_audit" / "metrics" / "last_metrics.json"
    health_path = tmp_path / PINS["platform_run_id"] / "decision_log_audit" / "health" / "last_health.json"
    assert metrics_path.exists()
    assert health_path.exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["append_success_total"] == 0
    assert metrics["metrics"]["append_success_total"] == 0
    assert health["platform_run_id"] == PINS["platform_run_id"]
    assert health["scenario_run_id"] == PINS["scenario_run_id"]


def test_phase7_transient_unresolved_is_not_red_until_it_is_stale(tmp_path: Path) -> None:
    store = DecisionLogAuditIntakeStore(locator=str(tmp_path / "dla_intake.sqlite"))
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    processor.process_record(
        DlaBusInput(
            topic="fp.bus.rtdl.v1",
            partition=0,
            offset="0",
            offset_kind="file_line",
            payload=_action_intent_envelope(
                event_id="evt_intent_only",
                decision_id="d" * 32,
                action_id="e" * 32,
            ),
        )
    )

    reporter = DecisionLogAuditObservabilityReporter(
        store=store,
        platform_run_id=PINS["platform_run_id"],
        scenario_run_id=PINS["scenario_run_id"],
        thresholds=DecisionLogAuditHealthThresholds(
            amber_checkpoint_age_seconds=9999.0,
            red_checkpoint_age_seconds=19999.0,
            amber_unresolved_stale_seconds=60.0,
            red_unresolved_stale_seconds=240.0,
            amber_unresolved_stale_total=1,
            red_unresolved_stale_total=2,
        ),
    )
    payload = reporter.collect()

    assert payload["health_state"] == "GREEN"
    assert "UNRESOLVED_IN_FLIGHT" in payload["health_reasons"]
    assert "UNRESOLVED_RED" not in payload["health_reasons"]
    lineage = payload["reconciliation"]["lineage"]["unresolved_age_seconds"]
    assert lineage["stale_over_amber_total"] == 0
    assert lineage["stale_over_red_total"] == 0

    with sqlite3.connect(str(tmp_path / "dla_intake.sqlite")) as conn:
        conn.execute(
            "UPDATE dla_lineage_chains SET updated_at_utc = ?",
            ("2026-02-07T10:20:00.000000Z",),
        )
        conn.commit()

    stale_payload = reporter.collect()
    assert stale_payload["health_state"] == "AMBER"
    assert "UNRESOLVED_AMBER" in stale_payload["health_reasons"]
