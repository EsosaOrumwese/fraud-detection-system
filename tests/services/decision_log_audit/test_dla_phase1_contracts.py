from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.decision_log_audit.contracts import (
    AuditRecord,
    DecisionLogAuditContractError,
)


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
        "snapshot_ref": "s3://fraud-platform/snapshots/a",
        "graph_version": {"version_id": "e" * 32, "watermark_ts_utc": "2026-02-07T18:19:58.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "100"}],
            "basis_digest": "f" * 64,
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
        "context_refs": [
            {
                "event_id": "flow_evt_1",
                "event_type": "context_flow_fraud",
                "role": "flow_anchor",
                "eb_ref": {
                    "topic": "fp.bus.context.flow_anchor.fraud.v1",
                    "partition": 0,
                    "offset": "11",
                    "offset_kind": "kinesis_sequence",
                },
            }
        ],
        "recorded_at_utc": "2026-02-07T18:20:01.000000Z",
    }


def test_dla_audit_schema_is_valid() -> None:
    schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/real_time_decision_loop/audit_record.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert "run_config_digest" in schema["required"]


def test_audit_record_contract_accepts_valid_payload() -> None:
    record = AuditRecord.from_payload(_audit_payload())
    assert record.audit_id == "a" * 32
    assert record.platform_run_id == "platform_20260207T182000Z"


def test_audit_record_contract_rejects_invalid_context_role() -> None:
    payload = _audit_payload()
    payload["context_refs"][0]["role"] = "not_allowed"  # type: ignore[index]
    with pytest.raises(DecisionLogAuditContractError):
        AuditRecord.from_payload(payload)


def test_audit_record_contract_rejects_empty_offsets() -> None:
    payload = _audit_payload()
    payload["eb_offset_basis"]["offsets"] = []  # type: ignore[index]
    with pytest.raises(DecisionLogAuditContractError):
        AuditRecord.from_payload(payload)

