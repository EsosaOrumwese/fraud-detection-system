from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.case_mgmt.contracts import (
    CaseMgmtContractError,
    CaseTimelineEvent,
    CaseTrigger,
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


def _case_subject_key() -> dict[str, str]:
    return {
        "platform_run_id": "platform_20260209T153000Z",
        "event_class": "traffic_fraud",
        "event_id": "evt_decision_trigger_001",
    }


def _case_trigger_payload() -> dict[str, object]:
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": "decision:dec_001",
        "case_subject_key": _case_subject_key(),
        "pins": _pins(),
        "observed_time": "2026-02-09T15:30:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def _timeline_payload(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "timeline_event_type": "CASE_TRIGGERED",
        "source_ref_id": "decision:dec_001",
        "pins": _pins(),
        "case_subject_key": _case_subject_key(),
        "observed_time": "2026-02-09T15:31:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "timeline_payload": {"queue": "fraud_high_risk"},
    }


def test_case_contract_schemas_are_valid() -> None:
    case_trigger_schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/case_and_labels/case_trigger.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    timeline_schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/case_and_labels/case_timeline_event.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(case_trigger_schema)
    Draft202012Validator.check_schema(timeline_schema)
    assert "trigger_type" in case_trigger_schema["required"]
    assert "timeline_event_type" in timeline_schema["required"]


def test_case_trigger_contract_accepts_valid_payload_and_derives_ids() -> None:
    trigger = CaseTrigger.from_payload(_case_trigger_payload())
    assert len(trigger.case_id) == 32
    assert len(trigger.case_trigger_id) == 32
    assert len(trigger.payload_hash) == 64
    assert trigger.dedupe_tuple() == (trigger.case_id, "DECISION_ESCALATION", "decision:dec_001")


def test_case_trigger_contract_rejects_invalid_trigger_type() -> None:
    payload = _case_trigger_payload()
    payload["trigger_type"] = "UNSUPPORTED"
    with pytest.raises(CaseMgmtContractError):
        CaseTrigger.from_payload(payload)


def test_case_trigger_contract_rejects_case_id_mismatch() -> None:
    payload = _case_trigger_payload()
    payload["case_id"] = "a" * 32
    with pytest.raises(CaseMgmtContractError):
        CaseTrigger.from_payload(payload)


def test_case_timeline_event_contract_accepts_valid_payload() -> None:
    trigger = CaseTrigger.from_payload(_case_trigger_payload())
    timeline = CaseTimelineEvent.from_payload(_timeline_payload(trigger.case_id))
    assert len(timeline.case_timeline_event_id) == 32
    assert len(timeline.payload_hash) == 64
    assert timeline.dedupe_tuple() == (trigger.case_id, "CASE_TRIGGERED", "decision:dec_001")


def test_case_timeline_event_contract_rejects_invalid_type() -> None:
    trigger = CaseTrigger.from_payload(_case_trigger_payload())
    payload = _timeline_payload(trigger.case_id)
    payload["timeline_event_type"] = "UNKNOWN_EVENT"
    with pytest.raises(CaseMgmtContractError):
        CaseTimelineEvent.from_payload(payload)


def test_case_timeline_event_contract_rejects_payload_hash_mismatch() -> None:
    trigger = CaseTrigger.from_payload(_case_trigger_payload())
    payload = _timeline_payload(trigger.case_id)
    payload["payload_hash"] = "f" * 64
    with pytest.raises(CaseMgmtContractError):
        CaseTimelineEvent.from_payload(payload)
