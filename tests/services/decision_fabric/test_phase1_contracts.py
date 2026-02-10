from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.decision_fabric.contracts import (
    ActionIntent,
    DecisionFabricContractError,
    DecisionResponse,
    validate_action_intent_lineage,
)


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
        "decision": {"disposition": "ALLOW"},
    }


def _action_payload() -> dict[str, object]:
    return {
        "action_id": "5" * 32,
        "decision_id": "a" * 32,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": "6" * 64,
        "pins": {
            "platform_run_id": "platform_20260207T102700Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "requested_at_utc": "2026-02-07T10:27:00.000000Z",
        "actor_principal": "decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8"},
        "run_config_digest": "4" * 64,
        "action_payload": {"target_topic": "topic.rtdl.action"},
    }


def test_decision_and_action_contract_schemas_are_valid() -> None:
    decision_schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/real_time_decision_loop/decision_payload.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    action_schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/real_time_decision_loop/action_intent.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(decision_schema)
    Draft202012Validator.check_schema(action_schema)
    assert "run_config_digest" in decision_schema["required"]
    assert "policy_rev" in action_schema["required"]


def test_decision_response_contract_accepts_valid_payload() -> None:
    response = DecisionResponse.from_payload(_decision_payload())
    assert response.decision_id == "a" * 32


def test_decision_response_contract_rejects_missing_required_field() -> None:
    payload = _decision_payload()
    payload.pop("run_config_digest")
    with pytest.raises(DecisionFabricContractError):
        DecisionResponse.from_payload(payload)


def test_action_intent_contract_accepts_valid_payload() -> None:
    intent = ActionIntent.from_payload(_action_payload())
    assert intent.action_id == "5" * 32


def test_action_intent_contract_rejects_invalid_origin() -> None:
    payload = _action_payload()
    payload["origin"] = "UNKNOWN"
    with pytest.raises(DecisionFabricContractError):
        ActionIntent.from_payload(payload)


def test_action_intent_lineage_validation_rejects_decision_id_mismatch() -> None:
    decision = DecisionResponse.from_payload(_decision_payload())
    payload = _action_payload()
    payload["decision_id"] = "7" * 32
    intent = ActionIntent.from_payload(payload)
    with pytest.raises(DecisionFabricContractError):
        validate_action_intent_lineage(decision, [intent])
