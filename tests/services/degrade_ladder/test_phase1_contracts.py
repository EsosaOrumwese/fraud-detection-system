from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.degrade_ladder.contracts import (
    DegradeContractError,
    DegradeDecision,
    MODE_SEQUENCE,
)


def _payload() -> dict[str, object]:
    return {
        "mode": "DEGRADED_1",
        "capabilities_mask": {
            "allow_ieg": True,
            "allowed_feature_groups": ["core_features", "velocity"],
            "allow_model_primary": True,
            "allow_model_stage2": False,
            "allow_fallback_heuristics": True,
            "action_posture": "STEP_UP_ONLY",
        },
        "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1", "content_digest": "a" * 64},
        "posture_seq": 7,
        "decided_at_utc": "2026-02-07T02:57:00.000000Z",
        "reason": "latency corridor breached",
        "evidence_refs": [{"kind": "metrics_ref", "ref": "s3://fraud-platform/run/rtdl/metrics.json"}],
    }


def test_degrade_posture_schema_is_valid_and_has_required_fields() -> None:
    path = Path("docs/model_spec/platform/contracts/real_time_decision_loop/degrade_posture.schema.yaml")
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["required"] == ["mode", "capabilities_mask", "policy_rev", "posture_seq", "decided_at_utc"]
    assert schema["properties"]["mode"]["enum"] == list(MODE_SEQUENCE)
    assert "evidence_refs" in schema["properties"]


def test_degrade_decision_normalizes_and_hashes_deterministically() -> None:
    decision = DegradeDecision.from_payload(_payload())
    digest_a = decision.digest()
    digest_b = DegradeDecision.from_payload(_payload()).digest()
    assert digest_a == digest_b


def test_degrade_decision_requires_fields() -> None:
    payload = _payload()
    payload.pop("mode")
    with pytest.raises(DegradeContractError):
        DegradeDecision.from_payload(payload)


def test_degrade_decision_rejects_invalid_mask_shape() -> None:
    payload = _payload()
    payload["capabilities_mask"] = {"allow_ieg": True}
    with pytest.raises(DegradeContractError):
        DegradeDecision.from_payload(payload)
