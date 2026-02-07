from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.action_layer.contracts import (
    ActionIntent,
    ActionLayerContractError,
    ActionOutcome,
    build_semantic_idempotency_key,
    validate_outcome_lineage,
)


def _intent_payload() -> dict[str, object]:
    return {
        "action_id": "1" * 32,
        "decision_id": "2" * 32,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": "merchant_42:evt_123:publish",
        "pins": {
            "platform_run_id": "platform_20260207T182000Z",
            "scenario_run_id": "3" * 32,
            "manifest_fingerprint": "4" * 64,
            "parameter_hash": "5" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "requested_at_utc": "2026-02-07T18:20:00.000000Z",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "al.policy.v0", "revision": "r1", "content_digest": "6" * 64},
        "run_config_digest": "7" * 64,
        "action_payload": {"target": "fraud.disposition"},
    }


def _outcome_payload() -> dict[str, object]:
    return {
        "outcome_id": "8" * 32,
        "decision_id": "2" * 32,
        "action_id": "1" * 32,
        "action_kind": "txn_disposition_publish",
        "status": "EXECUTED",
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
        "outcome_payload": {"receipt": "ok"},
    }


def test_action_contract_schemas_are_valid() -> None:
    intent_schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/real_time_decision_loop/action_intent.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    outcome_schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/real_time_decision_loop/action_outcome.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(intent_schema)
    Draft202012Validator.check_schema(outcome_schema)
    assert "idempotency_key" in intent_schema["required"]
    assert "authz_policy_rev" in outcome_schema["required"]


def test_action_intent_contract_accepts_valid_payload() -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    assert intent.action_id == "1" * 32


def test_action_outcome_contract_accepts_valid_payload() -> None:
    outcome = ActionOutcome.from_payload(_outcome_payload())
    assert outcome.outcome_id == "8" * 32


def test_action_contract_rejects_invalid_pin() -> None:
    payload = _intent_payload()
    payload["pins"]["platform_run_id"] = "run_bad"  # type: ignore[index]
    with pytest.raises(ActionLayerContractError):
        ActionIntent.from_payload(payload)


def test_action_outcome_lineage_rejects_decision_id_mismatch() -> None:
    intent = ActionIntent.from_payload(_intent_payload())
    payload = _outcome_payload()
    payload["decision_id"] = "a" * 32
    outcome = ActionOutcome.from_payload(payload)
    with pytest.raises(ActionLayerContractError):
        validate_outcome_lineage(intent, outcome)


def test_semantic_idempotency_key_is_stable_for_same_scope() -> None:
    payload_a = _intent_payload()
    payload_b = _intent_payload()
    payload_b["action_payload"] = {"other": "value"}
    assert build_semantic_idempotency_key(payload_a) == build_semantic_idempotency_key(payload_b)

