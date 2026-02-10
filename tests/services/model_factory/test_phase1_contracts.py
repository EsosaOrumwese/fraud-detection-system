from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.model_factory import MfPhase1ContractError, MfTrainBuildRequest


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "learning.mf_train_build_request.v0",
        "request_id": "mf.run.20260210T133900Z",
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T091951Z",
        "dataset_manifest_refs": [
            "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_a.json",
            "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_b.json",
        ],
        "training_config_ref": "s3://fraud-platform/config/mf/train_config_v0.yaml",
        "governance_profile_ref": "s3://fraud-platform/config/mf/governance_profile_v0.yaml",
        "requester_principal": "SYSTEM::run_operate",
        "target_scope": {
            "environment": "local_parity",
            "mode": "fraud",
            "bundle_slot": "primary",
        },
        "policy_revision": "mf-policy-v0",
        "config_revision": "local-parity-v0",
        "mf_code_release_id": "git:def456",
        "publish_allowed": True,
    }


def test_mf_train_build_request_schema_is_valid() -> None:
    schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/learning_registry/mf_train_build_request_v0.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert "request_id" in schema["required"]
    assert "dataset_manifest_refs" in schema["required"]


def test_mf_train_build_request_accepts_valid_payload() -> None:
    request = MfTrainBuildRequest.from_payload(_valid_payload())
    assert request.request_id == "mf.run.20260210T133900Z"
    run_key = request.deterministic_train_run_key()
    run_id = request.deterministic_train_run_id()
    assert len(run_key) == 64
    assert run_id.startswith("tr_")
    assert len(run_id) == 35


def test_mf_train_build_request_rejects_invalid_intent_kind() -> None:
    payload = _valid_payload()
    payload["intent_kind"] = "always_on_train"
    with pytest.raises(MfPhase1ContractError) as exc:
        MfTrainBuildRequest.from_payload(payload)
    assert exc.value.code == "INTENT_KIND_UNSUPPORTED"


def test_mf_train_build_request_rejects_missing_manifest_refs() -> None:
    payload = _valid_payload()
    payload["dataset_manifest_refs"] = []
    with pytest.raises(MfPhase1ContractError) as exc:
        MfTrainBuildRequest.from_payload(payload)
    assert exc.value.code == "MANIFEST_REF_MISSING"


def test_mf_train_build_request_rejects_missing_training_config_ref() -> None:
    payload = _valid_payload()
    payload["training_config_ref"] = " "
    with pytest.raises(MfPhase1ContractError) as exc:
        MfTrainBuildRequest.from_payload(payload)
    assert exc.value.code == "TRAIN_CONFIG_MISSING"


def test_mf_train_build_request_rejects_invalid_target_scope() -> None:
    payload = _valid_payload()
    payload["target_scope"] = {
        "environment": "local_parity",
        "mode": "fraud",
    }
    with pytest.raises(MfPhase1ContractError) as exc:
        MfTrainBuildRequest.from_payload(payload)
    assert exc.value.code == "TARGET_SCOPE_INVALID"


def test_mf_train_build_request_rejects_invalid_ownership_boundaries() -> None:
    payload = _valid_payload()
    ownership_path = Path("tests/services/model_factory/tmp_ownership_invalid.yaml")
    ownership_path.write_text(
        yaml.safe_dump(
            {
                "owners": {"ofs": "only-ofs"},
                "inputs": ["dataset_manifest_refs"],
                "outputs": ["dataset_manifest"],
            }
        ),
        encoding="utf-8",
    )
    try:
        with pytest.raises(MfPhase1ContractError) as exc:
            MfTrainBuildRequest.from_payload(payload, ownership_path=ownership_path)
        assert exc.value.code == "OWNERSHIP_BOUNDARY_VIOLATION"
    finally:
        if ownership_path.exists():
            ownership_path.unlink()

