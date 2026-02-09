from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.case_trigger.adapters import (
    CaseTriggerAdapterError,
    adapt_case_trigger_from_source,
    adapt_from_al_outcome,
    adapt_from_df_decision,
    adapt_from_dla_audit,
    adapt_from_external_signal,
    adapt_from_manual_assertion,
)
from fraud_detection.case_trigger.config import load_trigger_policy


def _policy():
    return load_trigger_policy(Path("config/platform/case_trigger/trigger_policy_v0.yaml"))


def _decision_payload() -> dict[str, object]:
    return {
        "decision_id": "a" * 32,
        "decision_kind": "txn_disposition",
        "bundle_ref": {"bundle_id": "b" * 64, "bundle_version": "2026.02.07", "registry_ref": "registry://active"},
        "snapshot_hash": "c" * 64,
        "graph_version": {"version_id": "d" * 32, "watermark_ts_utc": "2026-02-07T10:27:00.000000Z"},
        "eb_offset_basis": {
            "stream": "topic.rtdl.traffic",
            "offset_kind": "kafka_offset",
            "offsets": [{"partition": 0, "offset": "101"}],
            "basis_digest": "e" * 64,
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
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1", "content_digest": "f" * 64},
            "posture_seq": 3,
            "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        },
        "pins": {
            "platform_run_id": "platform_20260207T102700Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8", "content_digest": "9" * 64},
        "run_config_digest": "4" * 64,
        "source_event": {
            "event_id": "evt_abc",
            "event_type": "transaction_authorization",
            "ts_utc": "2026-02-07T10:26:59.000000Z",
            "origin_offset": {
                "topic": "topic.rtdl.traffic",
                "partition": 0,
                "offset": "100",
                "offset_kind": "kafka_offset",
            },
            "eb_ref": {"topic": "topic.rtdl.traffic", "partition": 0, "offset": "100", "offset_kind": "kafka_offset"},
        },
        "decision": {"action_kind": "QUEUE_REVIEW"},
    }


def _outcome_payload() -> dict[str, object]:
    return {
        "outcome_id": "8" * 32,
        "decision_id": "2" * 32,
        "action_id": "1" * 32,
        "action_kind": "txn_disposition_publish",
        "status": "FAILED",
        "idempotency_key": "merchant_42:evt_123:publish",
        "actor_principal": "SYSTEM::action_layer",
        "origin": "DF",
        "authz_policy_rev": {"policy_id": "al.authz.v0", "revision": "r5", "content_digest": "9" * 64},
        "run_config_digest": "7" * 64,
        "pins": {
            "platform_run_id": "platform_20260207T182000Z",
            "scenario_run_id": "3" * 32,
            "manifest_fingerprint": "4" * 64,
            "parameter_hash": "5" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "completed_at_utc": "2026-02-07T18:20:01.000000Z",
        "attempt_seq": 1,
        "outcome_payload": {"receipt": "failed"},
    }


def _audit_payload() -> dict[str, object]:
    return {
        "audit_id": "a" * 32,
        "decision_event": {
            "event_id": "b" * 32,
            "event_type": "decision_response",
            "ts_utc": "2026-02-07T18:20:00.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "100",
                "offset_kind": "kinesis_sequence",
            },
        },
        "action_intents": [],
        "action_outcomes": [],
        "bundle_ref": {"bundle_id": "c" * 64, "bundle_version": "2026.02.07", "registry_ref": "registry://active"},
        "snapshot_hash": "d" * 64,
        "graph_version": {"version_id": "e" * 32, "watermark_ts_utc": "2026-02-07T18:19:58.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "100"}],
            "basis_digest": "f" * 64,
        },
        "degrade_posture": {
            "mode": "FAIL_CLOSED",
            "capabilities_mask": {
                "allow_ieg": True,
                "allowed_feature_groups": ["core_features"],
                "allow_model_primary": True,
                "allow_model_stage2": True,
                "allow_fallback_heuristics": True,
                "action_posture": "NORMAL",
            },
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r2"},
            "posture_seq": 5,
            "decided_at_utc": "2026-02-07T18:20:00.000000Z",
        },
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r9"},
        "run_config_digest": "1" * 64,
        "pins": {
            "platform_run_id": "platform_20260207T182000Z",
            "scenario_run_id": "2" * 32,
            "manifest_fingerprint": "3" * 64,
            "parameter_hash": "4" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "recorded_at_utc": "2026-02-07T18:20:01.000000Z",
    }


def _external_payload() -> dict[str, object]:
    return {
        "external_ref_id": "chargeback:cb_1001",
        "case_subject_key": {
            "platform_run_id": "platform_20260207T182000Z",
            "event_class": "traffic_fraud",
            "event_id": "evt_ext_1",
        },
        "pins": {
            "platform_run_id": "platform_20260207T182000Z",
            "scenario_run_id": "2" * 32,
            "manifest_fingerprint": "3" * 64,
            "parameter_hash": "4" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": "2026-02-07T18:30:00.000000Z",
        "trigger_payload": {"source": "chargeback_feed"},
    }


def _manual_payload() -> dict[str, object]:
    return {
        "manual_assertion_id": "investigator:assert_500",
        "case_subject_key": {
            "platform_run_id": "platform_20260207T182000Z",
            "event_class": "traffic_fraud",
            "event_id": "evt_manual_1",
        },
        "pins": {
            "platform_run_id": "platform_20260207T182000Z",
            "scenario_run_id": "2" * 32,
            "manifest_fingerprint": "3" * 64,
            "parameter_hash": "4" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": "2026-02-07T18:31:00.000000Z",
        "trigger_payload": {"actor_id": "HUMAN::ops_analyst"},
    }


def test_phase2_df_adapter_builds_case_trigger() -> None:
    trigger = adapt_from_df_decision(
        decision_payload=_decision_payload(),
        audit_record_id="audit_df_001",
        policy=_policy(),
    )
    assert trigger.trigger_type == "DECISION_ESCALATION"
    assert trigger.source_ref_id == "decision:" + ("a" * 32)
    assert {ref.ref_type for ref in trigger.evidence_refs} == {"DECISION", "DLA_AUDIT_RECORD"}


def test_phase2_df_adapter_fails_closed_without_audit_ref() -> None:
    with pytest.raises(CaseTriggerAdapterError):
        adapt_from_df_decision(
            decision_payload=_decision_payload(),
            audit_record_id=None,
            policy=_policy(),
        )


def test_phase2_al_adapter_builds_failure_trigger() -> None:
    trigger = adapt_from_al_outcome(
        outcome_payload=_outcome_payload(),
        audit_record_id="audit_al_001",
        source_event_id="evt_al_failure_1",
        policy=_policy(),
    )
    assert trigger.trigger_type == "ACTION_FAILURE"
    assert trigger.source_ref_id == "action_outcome:" + ("8" * 32)
    assert {ref.ref_type for ref in trigger.evidence_refs} == {"ACTION_OUTCOME", "DLA_AUDIT_RECORD"}


def test_phase2_al_adapter_rejects_non_failure_status() -> None:
    payload = _outcome_payload()
    payload["status"] = "EXECUTED"
    with pytest.raises(CaseTriggerAdapterError):
        adapt_from_al_outcome(
            outcome_payload=payload,
            audit_record_id="audit_al_001",
            source_event_id="evt_al_success_1",
            policy=_policy(),
        )


def test_phase2_dla_adapter_builds_anomaly_trigger() -> None:
    trigger = adapt_from_dla_audit(
        audit_payload=_audit_payload(),
        policy=_policy(),
    )
    assert trigger.trigger_type == "ANOMALY"
    assert trigger.source_ref_id == "audit:" + ("a" * 32)
    assert {ref.ref_type for ref in trigger.evidence_refs} == {"DLA_AUDIT_RECORD"}


def test_phase2_external_and_manual_adapters_build_triggers() -> None:
    external = adapt_from_external_signal(
        source_payload=_external_payload(),
        policy=_policy(),
    )
    manual = adapt_from_manual_assertion(
        source_payload=_manual_payload(),
        policy=_policy(),
    )
    assert external.trigger_type == "EXTERNAL_SIGNAL"
    assert manual.trigger_type == "MANUAL_ASSERTION"


def test_phase2_dispatcher_rejects_unknown_source_class() -> None:
    with pytest.raises(CaseTriggerAdapterError):
        adapt_case_trigger_from_source(
            source_class="UNKNOWN_SOURCE",
            source_payload=_decision_payload(),
            policy=_policy(),
        )


def test_phase2_dispatcher_routes_df_source() -> None:
    trigger = adapt_case_trigger_from_source(
        source_class="DF_DECISION",
        source_payload=_decision_payload(),
        policy=_policy(),
        audit_record_id="audit_df_002",
    )
    assert trigger.trigger_type == "DECISION_ESCALATION"
