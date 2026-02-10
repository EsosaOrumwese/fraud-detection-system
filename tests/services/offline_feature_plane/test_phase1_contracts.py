from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from fraud_detection.offline_feature_plane import OfsBuildIntent, OfsPhase1ContractError


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "learning.ofs_build_intent.v0",
        "request_id": "ofs.run.20260210T112200Z",
        "intent_kind": "dataset_build",
        "platform_run_id": "platform_20260210T091951Z",
        "scenario_run_ids": ["74bd83db1ad3d1fa136e579115d55429"],
        "replay_basis": [
            {
                "topic": "fp.bus.context.arrival_events.v1",
                "partition": 1,
                "offset_kind": "kinesis_sequence",
                "start_offset": "10",
                "end_offset": "90",
            },
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "start_offset": "100",
                "end_offset": "200",
            },
        ],
        "label_basis": {
            "label_asof_utc": "2026-02-10T10:00:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
            "maturity_days": 30,
        },
        "feature_definition_set": {
            "feature_set_id": "core",
            "feature_set_version": "v1",
        },
        "join_scope": {
            "subject_key": "platform_run_id,event_id",
            "join_sources": ["flow_binding", "join_frame", "label_store"],
        },
        "filters": {
            "merchant_segment": ["enterprise", "sm_biz"],
            "country": ["US"],
        },
        "run_facts_ref": "s3://fraud-platform/platform_20260210T091951Z/sr/run_facts_view.json",
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
        "non_training_allowed": False,
    }


def test_ofs_build_intent_schema_is_valid() -> None:
    schema = yaml.safe_load(
        Path("docs/model_spec/platform/contracts/learning_registry/ofs_build_intent_v0.schema.yaml").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    assert "request_id" in schema["required"]
    assert "replay_basis" in schema["required"]


def test_ofs_build_intent_accepts_valid_payload_and_builds_manifest() -> None:
    intent = OfsBuildIntent.from_payload(_valid_payload())
    assert intent.request_id == "ofs.run.20260210T112200Z"
    manifest = intent.to_dataset_manifest()
    assert manifest.payload["schema_version"] == "learning.dataset_manifest.v0"
    assert manifest.payload["platform_run_id"] == "platform_20260210T091951Z"
    assert len(str(manifest.payload["dataset_fingerprint"])) == 64


def test_ofs_build_intent_rejects_invalid_intent_kind_with_taxonomy_code() -> None:
    payload = _valid_payload()
    payload["intent_kind"] = "always_on_stream"
    with pytest.raises(OfsPhase1ContractError) as exc:
        OfsBuildIntent.from_payload(payload)
    assert exc.value.code == "INTENT_KIND_UNSUPPORTED"


def test_ofs_build_intent_rejects_missing_label_asof_with_taxonomy_code() -> None:
    payload = _valid_payload()
    payload["label_basis"] = {
        "label_asof_utc": " ",
        "resolution_rule": "observed_time<=label_asof_utc",
    }
    with pytest.raises(OfsPhase1ContractError) as exc:
        OfsBuildIntent.from_payload(payload)
    assert exc.value.code == "LABEL_ASOF_MISSING"


def test_ofs_build_intent_rejects_unresolved_feature_profile_with_taxonomy_code() -> None:
    payload = _valid_payload()
    payload["feature_definition_set"] = {
        "feature_set_id": "core",
        "feature_set_version": " ",
    }
    with pytest.raises(OfsPhase1ContractError) as exc:
        OfsBuildIntent.from_payload(payload)
    assert exc.value.code == "FEATURE_PROFILE_UNRESOLVED"


def test_ofs_build_intent_rejects_missing_run_facts_ref_with_taxonomy_code() -> None:
    payload = _valid_payload()
    payload["run_facts_ref"] = " "
    with pytest.raises(OfsPhase1ContractError) as exc:
        OfsBuildIntent.from_payload(payload)
    assert exc.value.code == "RUN_FACTS_UNAVAILABLE"


def test_ofs_build_intent_rejects_invalid_ownership_boundaries() -> None:
    payload = _valid_payload()
    ownership_path = Path("tests/services/offline_feature_plane/tmp_ownership_invalid.yaml")
    ownership_path.write_text(
        yaml.safe_dump(
            {
                "owners": {"mf": "only-mf"},
                "inputs": ["dataset_manifest_refs"],
                "outputs": ["bundle_publication"],
            }
        ),
        encoding="utf-8",
    )
    try:
        with pytest.raises(OfsPhase1ContractError) as exc:
            OfsBuildIntent.from_payload(payload, ownership_path=ownership_path)
        assert exc.value.code == "OWNERSHIP_BOUNDARY_VIOLATION"
    finally:
        if ownership_path.exists():
            ownership_path.unlink()
