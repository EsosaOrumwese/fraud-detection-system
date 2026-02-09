from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.label_store.contracts import (
    LabelAssertion,
    LabelStoreContractError,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260209T153000Z",
        "scenario_run_id": "1" * 32,
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "scenario_id": "scenario.v0",
        "seed": 42,
    }


def _label_subject_key() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T153000Z",
        "event_id": "evt_decision_trigger_001",
    }


def _assertion_payload() -> dict[str, object]:
    return {
        "case_timeline_event_id": "a" * 32,
        "label_subject_key": _label_subject_key(),
        "pins": _pins(),
        "label_type": "fraud_disposition",
        "label_value": "FRAUD_CONFIRMED",
        "effective_time": "2026-02-09T15:10:00.000000Z",
        "observed_time": "2026-02-09T15:32:00.000000Z",
        "source_type": "HUMAN",
        "actor_id": "HUMAN::investigator_001",
        "evidence_refs": [
            {"ref_type": "CASE_EVENT", "ref_id": "case_evt_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "label_payload": {"notes": "confirmed by analyst"},
    }


def test_label_assertion_schema_is_valid() -> None:
    schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/case_and_labels/label_assertion.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert "label_assertion_id" in schema["required"]
    assert "payload_hash" in schema["required"]


def test_label_assertion_contract_accepts_valid_payload_and_derives_ids() -> None:
    assertion = LabelAssertion.from_payload(_assertion_payload())
    assert len(assertion.label_assertion_id) == 32
    assert len(assertion.payload_hash) == 64
    assert assertion.dedupe_tuple()[2] == "fraud_disposition"


def test_label_assertion_contract_rejects_human_without_actor() -> None:
    payload = _assertion_payload()
    payload.pop("actor_id")
    with pytest.raises(LabelStoreContractError):
        LabelAssertion.from_payload(payload)


def test_label_assertion_contract_rejects_value_not_allowed_for_type() -> None:
    payload = _assertion_payload()
    payload["label_value"] = "CHARGEBACK"
    with pytest.raises(LabelStoreContractError):
        LabelAssertion.from_payload(payload)


def test_label_assertion_contract_rejects_subject_pin_mismatch() -> None:
    payload = _assertion_payload()
    payload["label_subject_key"] = {
        "platform_run_id": "platform_20260209T153001Z",
        "event_id": "evt_decision_trigger_001",
    }
    with pytest.raises(LabelStoreContractError):
        LabelAssertion.from_payload(payload)


def test_label_assertion_contract_rejects_payload_hash_mismatch() -> None:
    payload = _assertion_payload()
    payload["payload_hash"] = "f" * 64
    with pytest.raises(LabelStoreContractError):
        LabelAssertion.from_payload(payload)
