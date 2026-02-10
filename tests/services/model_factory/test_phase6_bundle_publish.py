from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fraud_detection.learning_registry.contracts import BundlePublicationContract
from fraud_detection.model_factory import (
    MfBundlePublisher,
    MfBundlePublisherConfig,
    MfGatePolicyConfig,
    MfGatePolicyEvaluator,
    MfPhase6PublishError,
    MfTrainBuildRequest,
    MfTrainEvalExecutor,
    MfTrainEvalExecutorConfig,
    MfTrainPlanResolver,
    MfTrainPlanResolverConfig,
)


def _write_manifest(
    path: Path,
    *,
    platform_run_id: str = "platform_20260210T141900Z",
    resolution_rule: str = "observed_time<=label_asof_utc",
) -> None:
    payload = {
        "schema_version": "learning.dataset_manifest.v0",
        "dataset_manifest_id": "dm_20260210_006",
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
            "resolution_rule": resolution_rule,
            "maturity_days": 30,
        },
        "feature_definition_set": {
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "provenance": {
            "ofs_code_release_id": "git:ofsphase10",
            "config_revision": "local-parity-v0",
            "run_config_digest": "b" * 64,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")


def _write_training_profile(path: Path) -> None:
    payload = {
        "policy_id": "mf.train.policy.v0",
        "revision": "r6",
        "feature_definition_set": {
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "expected_manifest_schema_version": "learning.dataset_manifest.v0",
        "split_strategy": "time_based",
        "seed_policy": {
            "recipe": "mf.phase4.seed.v0",
            "base_seed": 17,
        },
        "leakage": {
            "expected_label_rule": "observed_time<=label_asof_utc",
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_governance_profile(path: Path, *, min_auc: float, min_precision: float) -> None:
    payload = {
        "policy_id": "mf.governance.policy.v0",
        "revision": "r11",
        "eval_thresholds": {
            "min_auc_roc": min_auc,
            "min_precision_at_50": min_precision,
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _request_payload(
    *,
    manifest_ref: str,
    training_config_ref: str,
    governance_profile_ref: str,
) -> dict[str, object]:
    return {
        "schema_version": "learning.mf_train_build_request.v0",
        "request_id": "mf.phase6.req.001",
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T141900Z",
        "dataset_manifest_refs": [manifest_ref],
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
        "mf_code_release_id": "git:mfphase6",
        "publish_allowed": True,
    }


def _prepare_phase5(
    *,
    tmp_path: Path,
    min_auc: float,
    min_precision: float,
):
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T141900Z/ofs/manifests/dm_006.json"
    _write_manifest(store_root / manifest_ref)
    training_profile = tmp_path / "train_profile.yaml"
    governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(training_profile)
    _write_governance_profile(governance_profile, min_auc=min_auc, min_precision=min_precision)
    request = MfTrainBuildRequest.from_payload(
        _request_payload(
            manifest_ref=manifest_ref,
            training_config_ref=str(training_profile),
            governance_profile_ref=str(governance_profile),
        )
    )
    plan = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root))).resolve(request=request)
    phase4_receipt = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root))).execute(
        plan=plan,
        execution_started_at_utc="2026-02-10T14:19:00Z",
    )
    phase5_result = MfGatePolicyEvaluator(config=MfGatePolicyConfig(object_store_root=str(store_root))).evaluate(
        plan=plan,
        train_eval_receipt=phase4_receipt,
        evaluated_at_utc="2026-02-10T14:19:10Z",
    )
    return store_root, plan, phase5_result


def test_phase6_packages_bundle_and_publishes_once(tmp_path: Path) -> None:
    store_root, plan, phase5_result = _prepare_phase5(tmp_path=tmp_path, min_auc=0.10, min_precision=0.10)
    publisher = MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(store_root)))

    result = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:19:20Z")

    assert result.publish_receipt.publication_status == "PUBLISHED"
    assert len(result.bundle_publication.bundle_id) == 64
    assert result.bundle_publication.bundle_version.startswith("v0-")
    payload = json.loads(Path(result.bundle_publication.bundle_publication_ref).read_text(encoding="utf-8"))
    contract = BundlePublicationContract.from_payload(payload)
    assert contract.payload["bundle_id"] == result.bundle_publication.bundle_id
    assert Path(result.publish_receipt.registry_lifecycle_event_ref).exists()
    assert Path(result.publish_receipt_ref).exists()


def test_phase6_publish_is_idempotent_by_bundle_identity(tmp_path: Path) -> None:
    store_root, plan, phase5_result = _prepare_phase5(tmp_path=tmp_path, min_auc=0.10, min_precision=0.10)
    publisher = MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(store_root)))

    first = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:19:20Z")
    second = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:19:21Z")

    assert first.bundle_publication.bundle_id == second.bundle_publication.bundle_id
    assert first.bundle_publication.bundle_version == second.bundle_publication.bundle_version
    assert second.publish_receipt.publication_status == "ALREADY_PUBLISHED"
    assert first.publish_receipt.registry_bundle_ref == second.publish_receipt.registry_bundle_ref


def test_phase6_publish_conflict_fails_closed_when_registry_payload_drifts(tmp_path: Path) -> None:
    store_root, plan, phase5_result = _prepare_phase5(tmp_path=tmp_path, min_auc=0.10, min_precision=0.10)
    publisher = MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(store_root)))
    first = publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:19:20Z")

    registry_payload = json.loads(Path(first.publish_receipt.registry_bundle_ref).read_text(encoding="utf-8"))
    registry_payload["provenance"]["mf_code_release_id"] = "git:drifted"
    Path(first.publish_receipt.registry_bundle_ref).write_text(
        json.dumps(registry_payload, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )

    with pytest.raises(MfPhase6PublishError) as exc:
        publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:19:21Z")
    assert exc.value.code == "PUBLISH_CONFLICT"


def test_phase6_publish_fails_closed_for_ineligible_phase5_result(tmp_path: Path) -> None:
    store_root, plan, phase5_result = _prepare_phase5(tmp_path=tmp_path, min_auc=0.9999, min_precision=0.9999)
    publisher = MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(store_root)))

    with pytest.raises(MfPhase6PublishError) as exc:
        publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:19:20Z")
    assert exc.value.code == "PUBLISH_NOT_ELIGIBLE"


def test_phase6_publish_fails_closed_when_required_evidence_unresolved(tmp_path: Path) -> None:
    store_root, plan, phase5_result = _prepare_phase5(tmp_path=tmp_path, min_auc=0.10, min_precision=0.10)
    evidence_pack_ref = phase5_result.publish_eligibility.required_evidence_refs["evidence_pack_ref"]
    Path(evidence_pack_ref).unlink()
    publisher = MfBundlePublisher(config=MfBundlePublisherConfig(object_store_root=str(store_root)))

    with pytest.raises(MfPhase6PublishError) as exc:
        publisher.publish(plan=plan, phase5_result=phase5_result, published_at_utc="2026-02-10T14:19:20Z")
    assert exc.value.code == "EVIDENCE_UNRESOLVED"
