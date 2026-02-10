from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fraud_detection.model_factory import (
    MfPhase3ResolverError,
    MfTrainBuildRequest,
    MfTrainPlanResolver,
    MfTrainPlanResolverConfig,
)


def _request_payload(
    *,
    manifest_refs: list[str],
    training_config_ref: str,
    governance_profile_ref: str,
) -> dict[str, object]:
    return {
        "schema_version": "learning.mf_train_build_request.v0",
        "request_id": "mf.phase3.req.001",
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T140100Z",
        "dataset_manifest_refs": manifest_refs,
        "training_config_ref": training_config_ref,
        "governance_profile_ref": governance_profile_ref,
        "requester_principal": "SYSTEM::run_operate",
        "target_scope": {
            "environment": "local_parity",
            "mode": "fraud",
            "bundle_slot": "primary",
        },
        "policy_revision": "mf-policy-v0",
        "config_revision": "local-parity-v0",
        "mf_code_release_id": "git:mfphase3",
        "publish_allowed": True,
    }


def _request(
    *,
    manifest_refs: list[str],
    training_config_ref: str,
    governance_profile_ref: str,
) -> MfTrainBuildRequest:
    return MfTrainBuildRequest.from_payload(
        _request_payload(
            manifest_refs=manifest_refs,
            training_config_ref=training_config_ref,
            governance_profile_ref=governance_profile_ref,
        )
    )


def _write_manifest(
    path: Path,
    *,
    platform_run_id: str = "platform_20260210T140100Z",
    feature_set_id: str = "core_features",
    feature_set_version: str = "v1",
    schema_version: str = "learning.dataset_manifest.v0",
) -> None:
    payload = {
        "schema_version": schema_version,
        "dataset_manifest_id": "dm_20260210_001",
        "dataset_fingerprint": "a" * 64,
        "platform_run_id": platform_run_id,
        "scenario_run_ids": ["run_001"],
        "replay_basis": [
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "start_offset": "100",
                "end_offset": "200",
            }
        ],
        "label_basis": {
            "label_asof_utc": "2026-02-10T13:50:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
            "maturity_days": 30,
        },
        "feature_definition_set": {
            "feature_set_id": feature_set_id,
            "feature_set_version": feature_set_version,
        },
        "provenance": {
            "ofs_code_release_id": "git:ofsphase10",
            "config_revision": "local-parity-v0",
            "run_config_digest": "b" * 64,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")


def _write_training_config(
    path: Path,
    *,
    feature_set_id: str = "core_features",
    feature_set_version: str = "v1",
    expected_manifest_schema_version: str = "learning.dataset_manifest.v0",
) -> None:
    payload = {
        "policy_id": "mf.train.policy.v0",
        "revision": "r1",
        "feature_definition_set": {
            "feature_set_id": feature_set_id,
            "feature_set_version": feature_set_version,
        },
        "expected_manifest_schema_version": expected_manifest_schema_version,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_governance_profile(path: Path) -> None:
    payload = {
        "policy_id": "mf.governance.policy.v0",
        "revision": "r3",
        "controls": {"require_pass_gate": True},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_phase3_resolves_train_plan_and_emits_immutable_artifact(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140100Z/ofs/manifests/dm_001.json"
    manifest_path = store_root / manifest_ref
    _write_manifest(manifest_path)
    training_config = tmp_path / "train_profile_v0.yaml"
    governance_profile = tmp_path / "governance_profile_v0.yaml"
    _write_training_config(training_config)
    _write_governance_profile(governance_profile)
    request = _request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(training_config),
        governance_profile_ref=str(governance_profile),
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))

    plan = resolver.resolve(request=request)
    assert plan.platform_run_id == "platform_20260210T140100Z"
    assert len(plan.dataset_manifests) == 1
    assert plan.training_profile.resolved_revision == "mf.train.policy.v0@r1"
    assert plan.governance_profile.resolved_revision == "mf.governance.policy.v0@r3"
    first_ref = resolver.emit_immutable(plan=plan)
    second_ref = resolver.emit_immutable(plan=plan)
    assert first_ref == second_ref
    assert Path(first_ref).exists()


def test_phase3_fails_closed_on_run_scope_mismatch(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140100Z/ofs/manifests/dm_001.json"
    manifest_path = store_root / manifest_ref
    _write_manifest(manifest_path, platform_run_id="platform_20990101T000000Z")
    training_config = tmp_path / "train_profile_v0.yaml"
    governance_profile = tmp_path / "governance_profile_v0.yaml"
    _write_training_config(training_config)
    _write_governance_profile(governance_profile)
    request = _request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(training_config),
        governance_profile_ref=str(governance_profile),
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))

    with pytest.raises(MfPhase3ResolverError) as exc:
        resolver.resolve(request=request)
    assert exc.value.code == "RUN_SCOPE_INVALID"


def test_phase3_fails_closed_on_feature_schema_incompatibility(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140100Z/ofs/manifests/dm_001.json"
    manifest_path = store_root / manifest_ref
    _write_manifest(manifest_path, feature_set_version="v1")
    training_config = tmp_path / "train_profile_v0.yaml"
    governance_profile = tmp_path / "governance_profile_v0.yaml"
    _write_training_config(training_config, feature_set_version="v2")
    _write_governance_profile(governance_profile)
    request = _request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(training_config),
        governance_profile_ref=str(governance_profile),
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))

    with pytest.raises(MfPhase3ResolverError) as exc:
        resolver.resolve(request=request)
    assert exc.value.code == "FEATURE_SCHEMA_INCOMPATIBLE"


def test_phase3_fails_closed_when_manifest_ref_is_unresolved(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    training_config = tmp_path / "train_profile_v0.yaml"
    governance_profile = tmp_path / "governance_profile_v0.yaml"
    _write_training_config(training_config)
    _write_governance_profile(governance_profile)
    request = _request(
        manifest_refs=["platform_20260210T140100Z/ofs/manifests/missing.json"],
        training_config_ref=str(training_config),
        governance_profile_ref=str(governance_profile),
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))

    with pytest.raises(MfPhase3ResolverError) as exc:
        resolver.resolve(request=request)
    assert exc.value.code == "MANIFEST_UNRESOLVED"


def test_phase3_fails_closed_when_training_profile_is_unresolved(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140100Z/ofs/manifests/dm_001.json"
    manifest_path = store_root / manifest_ref
    _write_manifest(manifest_path)
    governance_profile = tmp_path / "governance_profile_v0.yaml"
    _write_governance_profile(governance_profile)
    request = _request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(tmp_path / "missing_train_profile.yaml"),
        governance_profile_ref=str(governance_profile),
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))

    with pytest.raises(MfPhase3ResolverError) as exc:
        resolver.resolve(request=request)
    assert exc.value.code == "TRAINING_PROFILE_UNRESOLVED"


def test_phase3_resolved_plan_artifact_detects_immutability_drift(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140100Z/ofs/manifests/dm_001.json"
    manifest_path = store_root / manifest_ref
    _write_manifest(manifest_path)
    training_config = tmp_path / "train_profile_v0.yaml"
    governance_profile = tmp_path / "governance_profile_v0.yaml"
    _write_training_config(training_config)
    _write_governance_profile(governance_profile)
    request = _request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(training_config),
        governance_profile_ref=str(governance_profile),
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))
    plan = resolver.resolve(request=request)
    emitted_path = Path(resolver.emit_immutable(plan=plan))

    drifted = plan.as_dict()
    drifted["input_refs"]["mf_code_release_id"] = "git:drifted"
    emitted_path.write_text(json.dumps(drifted, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    with pytest.raises(MfPhase3ResolverError) as exc:
        resolver.emit_immutable(plan=plan)
    assert exc.value.code == "RESOLVED_TRAIN_PLAN_IMMUTABILITY_VIOLATION"
