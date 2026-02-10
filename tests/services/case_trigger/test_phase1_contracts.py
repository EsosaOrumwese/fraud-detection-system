from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.case_trigger.config import load_trigger_policy
from fraud_detection.case_trigger.contracts import (
    CaseTriggerContractError,
    validate_case_trigger_payload,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260209T155300Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def _case_subject_key() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T155300Z",
        "event_class": "traffic_fraud",
        "event_id": "evt_decision_trigger_001",
    }


def _trigger_payload() -> dict[str, object]:
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": "decision:dec_001",
        "case_subject_key": _case_subject_key(),
        "pins": _pins(),
        "observed_time": "2026-02-09T15:53:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def test_case_trigger_schema_is_valid() -> None:
    schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert "case_trigger_id" in schema["required"]


def test_validate_case_trigger_payload_accepts_valid_df_trigger() -> None:
    policy = load_trigger_policy(Path("config/platform/case_trigger/trigger_policy_v0.yaml"))
    trigger = validate_case_trigger_payload(
        _trigger_payload(),
        source_class="DF_DECISION",
        policy=policy,
    )
    assert len(trigger.case_id) == 32
    assert len(trigger.case_trigger_id) == 32
    assert len(trigger.payload_hash) == 64


def test_validate_case_trigger_payload_rejects_source_mismatch() -> None:
    policy = load_trigger_policy(Path("config/platform/case_trigger/trigger_policy_v0.yaml"))
    with pytest.raises(CaseTriggerContractError):
        validate_case_trigger_payload(
            _trigger_payload(),
            source_class="AL_OUTCOME",
            policy=policy,
        )


def test_validate_case_trigger_payload_rejects_missing_required_evidence() -> None:
    policy = load_trigger_policy(Path("config/platform/case_trigger/trigger_policy_v0.yaml"))
    payload = _trigger_payload()
    payload["evidence_refs"] = [
        {"ref_type": "DECISION", "ref_id": "dec_001"},
    ]
    with pytest.raises(CaseTriggerContractError):
        validate_case_trigger_payload(
            payload,
            source_class="DF_DECISION",
            policy=policy,
        )
