from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fraud_detection.model_factory import (
    MfBundlePublisher,
    MfBundlePublisherConfig,
    MfGatePolicyConfig,
    MfGatePolicyEvaluator,
    MfPhase3ResolverError,
    MfPhase5GateError,
    MfPhase6PublishError,
    MfTrainBuildRequest,
    MfTrainEvalExecutor,
    MfTrainEvalExecutorConfig,
    MfTrainPlanResolver,
    MfTrainPlanResolverConfig,
    classify_failure_code,
    deterministic_run_key,
    is_known_failure_code,
    known_failure_codes,
)


def _write_manifest(
    path: Path,
    *,
    dataset_manifest_id: str = "dm_20260210_007",
    dataset_fingerprint: str = "a" * 64,
    platform_run_id: str = "platform_20260210T143500Z",
    feature_set_id: str = "core_features",
    feature_set_version: str = "v1",
    schema_version: str = "learning.dataset_manifest.v0",
    resolution_rule: str = "observed_time<=label_asof_utc",
) -> None:
    payload = {
        "schema_version": schema_version,
        "dataset_manifest_id": dataset_manifest_id,
        "dataset_fingerprint": dataset_fingerprint,
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
            "resolution_rule": resolution_rule,
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


def _write_training_profile(
    path: Path,
    *,
    feature_set_id: str = "core_features",
    feature_set_version: str = "v1",
    expected_manifest_schema_version: str = "learning.dataset_manifest.v0",
) -> None:
    payload = {
        "policy_id": "mf.train.policy.v0",
        "revision": "r7",
        "feature_definition_set": {
            "feature_set_id": feature_set_id,
            "feature_set_version": feature_set_version,
        },
        "expected_manifest_schema_version": expected_manifest_schema_version,
        "split_strategy": "time_based",
        "seed_policy": {
            "recipe": "mf.phase4.seed.v0",
            "base_seed": 31,
        },
        "leakage": {
            "expected_label_rule": "observed_time<=label_asof_utc",
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_governance_profile(path: Path, *, min_auc: float, min_precision: float) -> None:
    payload = {
        "policy_id": "mf.governance.policy.v0",
        "revision": "r12",
        "eval_thresholds": {
            "min_auc_roc": min_auc,
            "min_precision_at_50": min_precision,
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _request_payload(
    *,
    manifest_refs: list[str],
    training_config_ref: str,
    governance_profile_ref: str,
) -> dict[str, object]:
    return {
        "schema_version": "learning.mf_train_build_request.v0",
        "request_id": "mf.phase7.req.001",
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T143500Z",
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
        "mf_code_release_id": "git:mfphase7",
        "publish_allowed": True,
    }


def _build_request(
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


def _prepare_phase5(
    *,
    tmp_path: Path,
    min_auc: float,
    min_precision: float,
):
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T143500Z/ofs/manifests/dm_007.json"
    _write_manifest(store_root / manifest_ref)
    training_profile = tmp_path / "train_profile.yaml"
    governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(training_profile)
    _write_governance_profile(governance_profile, min_auc=min_auc, min_precision=min_precision)
    request = _build_request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(training_profile),
        governance_profile_ref=str(governance_profile),
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))
    plan = resolver.resolve(request=request)
    phase4_receipt = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root))).execute(
        plan=plan,
        execution_started_at_utc="2026-02-10T14:35:00Z",
    )
    phase5_result = MfGatePolicyEvaluator(config=MfGatePolicyConfig(object_store_root=str(store_root))).evaluate(
        plan=plan,
        train_eval_receipt=phase4_receipt,
        evaluated_at_utc="2026-02-10T14:35:10Z",
    )
    return store_root, request, plan, phase4_receipt, phase5_result


def test_phase7_negative_matrix_has_typed_known_codes(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    base_training_profile = tmp_path / "train_profile.yaml"
    base_governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(base_training_profile)
    _write_governance_profile(base_governance_profile, min_auc=0.10, min_precision=0.10)

    observed_codes: list[str] = []

    missing_manifest_request = _build_request(
        manifest_refs=["platform_20260210T143500Z/ofs/manifests/missing.json"],
        training_config_ref=str(base_training_profile),
        governance_profile_ref=str(base_governance_profile),
    )
    with pytest.raises(MfPhase3ResolverError) as exc_missing_manifest:
        MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root))).resolve(
            request=missing_manifest_request
        )
    assert exc_missing_manifest.value.code == "MANIFEST_UNRESOLVED"
    observed_codes.append(exc_missing_manifest.value.code)

    manifest_ref = "platform_20260210T143500Z/ofs/manifests/dm_007.json"
    _write_manifest(store_root / manifest_ref)
    missing_training_request = _build_request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(tmp_path / "missing_training.yaml"),
        governance_profile_ref=str(base_governance_profile),
    )
    with pytest.raises(MfPhase3ResolverError) as exc_missing_training:
        MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root))).resolve(
            request=missing_training_request
        )
    assert exc_missing_training.value.code == "TRAINING_PROFILE_UNRESOLVED"
    observed_codes.append(exc_missing_training.value.code)

    manifest_ref_a = "platform_20260210T143500Z/ofs/manifests/dm_007a.json"
    manifest_ref_b = "platform_20260210T143500Z/ofs/manifests/dm_007b.json"
    _write_manifest(store_root / manifest_ref_a, dataset_manifest_id="dm_immutable", dataset_fingerprint="1" * 64)
    _write_manifest(store_root / manifest_ref_b, dataset_manifest_id="dm_immutable", dataset_fingerprint="2" * 64)
    digest_mismatch_request = _build_request(
        manifest_refs=[manifest_ref_a, manifest_ref_b],
        training_config_ref=str(base_training_profile),
        governance_profile_ref=str(base_governance_profile),
    )
    with pytest.raises(MfPhase3ResolverError) as exc_digest:
        MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root))).resolve(
            request=digest_mismatch_request
        )
    assert exc_digest.value.code == "MANIFEST_IMMUTABILITY_VIOLATION"
    observed_codes.append(exc_digest.value.code)

    incompatible_training_profile = tmp_path / "train_profile_incompatible.yaml"
    _write_training_profile(incompatible_training_profile, feature_set_version="v2")
    incompatible_request = _build_request(
        manifest_refs=[manifest_ref],
        training_config_ref=str(incompatible_training_profile),
        governance_profile_ref=str(base_governance_profile),
    )
    with pytest.raises(MfPhase3ResolverError) as exc_incompatible:
        MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root))).resolve(
            request=incompatible_request
        )
    assert exc_incompatible.value.code == "FEATURE_SCHEMA_INCOMPATIBLE"
    observed_codes.append(exc_incompatible.value.code)

    phase5_store, _, phase5_plan, phase4_receipt, phase5_result = _prepare_phase5(
        tmp_path=tmp_path / "neg_phase5",
        min_auc=0.10,
        min_precision=0.10,
    )
    Path(phase4_receipt.eval_report_ref).unlink()
    with pytest.raises(MfPhase5GateError) as exc_missing_eval:
        MfGatePolicyEvaluator(config=MfGatePolicyConfig(object_store_root=str(phase5_store))).evaluate(
            plan=phase5_plan,
            train_eval_receipt=phase4_receipt,
        )
    assert exc_missing_eval.value.code == "EVAL_REPORT_UNRESOLVED"
    observed_codes.append(exc_missing_eval.value.code)

    Path(phase5_result.gate_receipt_ref).unlink()
    with pytest.raises(MfPhase6PublishError) as exc_missing_gate:
        MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(phase5_store))).publish(
            plan=phase5_plan,
            phase5_result=phase5_result,
            published_at_utc="2026-02-10T14:35:20Z",
        )
    assert exc_missing_gate.value.code == "EVIDENCE_UNRESOLVED"
    observed_codes.append(exc_missing_gate.value.code)

    assert observed_codes
    for code in observed_codes:
        assert is_known_failure_code(code)
        classification = classify_failure_code(code)
        assert classification.known is True
        assert classification.category != "UNKNOWN"
    assert len(set(observed_codes)) <= 8
    assert len(known_failure_codes()) <= 40


def test_phase7_partial_publish_retry_recovers_missing_receipts(tmp_path: Path) -> None:
    store_root, _, plan, _, phase5_result = _prepare_phase5(
        tmp_path=tmp_path,
        min_auc=0.10,
        min_precision=0.10,
    )
    publisher = MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(store_root)))
    first = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:35:20Z")

    Path(first.publish_receipt.registry_lifecycle_event_ref).unlink()
    Path(first.publish_receipt_ref).unlink()
    second = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:35:21Z")

    assert second.publish_receipt.publication_status == "ALREADY_PUBLISHED"
    assert second.bundle_publication.bundle_id == first.bundle_publication.bundle_id
    assert second.bundle_publication.bundle_version == first.bundle_publication.bundle_version
    assert Path(second.publish_receipt.registry_lifecycle_event_ref).exists()
    assert Path(second.publish_receipt_ref).exists()


def test_phase7_train_and_publish_idempotency_under_retry(tmp_path: Path) -> None:
    store_root, request, plan, phase4_receipt, phase5_result = _prepare_phase5(
        tmp_path=tmp_path,
        min_auc=0.10,
        min_precision=0.10,
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))
    plan_again = resolver.resolve(request=request)
    assert deterministic_run_key(request) == plan.run_key
    assert plan_again.run_key == plan.run_key

    executor = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root)))
    second_receipt = executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:35:00Z")
    assert second_receipt.eval_report_ref == phase4_receipt.eval_report_ref
    assert second_receipt.execution_record_ref == phase4_receipt.execution_record_ref

    publisher = MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(store_root)))
    first_publish = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:35:20Z")
    second_publish = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:35:22Z")
    assert first_publish.bundle_publication.bundle_id == second_publish.bundle_publication.bundle_id
    assert second_publish.publish_receipt.publication_status == "ALREADY_PUBLISHED"
