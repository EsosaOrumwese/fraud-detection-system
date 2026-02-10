from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fraud_detection.learning_registry.contracts import EvalReportContract
from fraud_detection.model_factory import (
    MfPhase4ExecutionError,
    MfTrainBuildRequest,
    MfTrainEvalExecutor,
    MfTrainEvalExecutorConfig,
    MfTrainPlanResolver,
    MfTrainPlanResolverConfig,
)


def _write_manifest(
    path: Path,
    *,
    platform_run_id: str = "platform_20260210T140600Z",
    resolution_rule: str = "observed_time<=label_asof_utc",
    label_asof_utc: str = "2026-02-10T13:50:00Z",
) -> None:
    payload = {
        "schema_version": "learning.dataset_manifest.v0",
        "dataset_manifest_id": "dm_20260210_004",
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
            "label_asof_utc": label_asof_utc,
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


def _write_training_profile(
    path: Path,
    *,
    include_split: bool = True,
) -> None:
    payload: dict[str, object] = {
        "policy_id": "mf.train.policy.v0",
        "revision": "r2",
        "feature_definition_set": {
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "expected_manifest_schema_version": "learning.dataset_manifest.v0",
        "seed_policy": {
            "recipe": "mf.phase4.seed.v0",
            "base_seed": 41,
        },
        "leakage": {
            "expected_label_rule": "observed_time<=label_asof_utc",
        },
    }
    if include_split:
        payload["split_strategy"] = "time_based"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_governance_profile(path: Path, *, min_auc: float = 0.10, min_precision: float = 0.10) -> None:
    payload = {
        "policy_id": "mf.governance.policy.v0",
        "revision": "r7",
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
        "request_id": "mf.phase4.req.001",
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T140600Z",
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
        "mf_code_release_id": "git:mfphase4",
        "publish_allowed": True,
    }


def _resolve_plan(
    *,
    store_root: Path,
    manifest_ref: str,
    training_config_ref: str,
    governance_profile_ref: str,
):
    request = MfTrainBuildRequest.from_payload(
        _request_payload(
            manifest_ref=manifest_ref,
            training_config_ref=training_config_ref,
            governance_profile_ref=governance_profile_ref,
        )
    )
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))
    return resolver.resolve(request=request)


def test_phase4_executes_corridor_and_emits_schema_valid_eval_report(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140600Z/ofs/manifests/dm_004.json"
    _write_manifest(store_root / manifest_ref)
    training_profile = tmp_path / "train_profile.yaml"
    governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(training_profile)
    _write_governance_profile(governance_profile, min_auc=0.10, min_precision=0.10)
    plan = _resolve_plan(
        store_root=store_root,
        manifest_ref=manifest_ref,
        training_config_ref=str(training_profile),
        governance_profile_ref=str(governance_profile),
    )

    executor = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root)))
    receipt = executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:06:00Z")

    assert receipt.platform_run_id == "platform_20260210T140600Z"
    assert receipt.split_strategy == "time_based"
    assert receipt.seed_policy["base_seed"] == 41
    assert receipt.gate_decision in {"PASS", "FAIL"}
    eval_payload = json.loads(Path(receipt.eval_report_ref).read_text(encoding="utf-8"))
    contract = EvalReportContract.from_payload(eval_payload)
    assert contract.payload["eval_report_id"] == receipt.eval_report_id
    assert Path(receipt.execution_record_ref).exists()
    assert Path(receipt.train_artifact_ref).exists()
    assert Path(receipt.evidence_pack_ref).exists()


def test_phase4_fails_closed_when_split_strategy_missing(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140600Z/ofs/manifests/dm_004.json"
    _write_manifest(store_root / manifest_ref)
    training_profile = tmp_path / "train_profile.yaml"
    governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(training_profile, include_split=False)
    _write_governance_profile(governance_profile)
    plan = _resolve_plan(
        store_root=store_root,
        manifest_ref=manifest_ref,
        training_config_ref=str(training_profile),
        governance_profile_ref=str(governance_profile),
    )

    executor = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root)))
    with pytest.raises(MfPhase4ExecutionError) as exc:
        executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:06:00Z")
    assert exc.value.code == "TRAINING_PROFILE_INVALID"


def test_phase4_fails_closed_on_leakage_rule_mismatch(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140600Z/ofs/manifests/dm_004.json"
    _write_manifest(store_root / manifest_ref, resolution_rule="effective_time<=label_asof_utc")
    training_profile = tmp_path / "train_profile.yaml"
    governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(training_profile, include_split=True)
    _write_governance_profile(governance_profile)
    plan = _resolve_plan(
        store_root=store_root,
        manifest_ref=manifest_ref,
        training_config_ref=str(training_profile),
        governance_profile_ref=str(governance_profile),
    )

    executor = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root)))
    with pytest.raises(MfPhase4ExecutionError) as exc:
        executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:06:00Z")
    assert exc.value.code == "LEAKAGE_GUARD_VIOLATION"


def test_phase4_fails_closed_on_future_label_asof(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140600Z/ofs/manifests/dm_004.json"
    _write_manifest(store_root / manifest_ref, label_asof_utc="2026-02-10T14:07:00Z")
    training_profile = tmp_path / "train_profile.yaml"
    governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(training_profile, include_split=True)
    _write_governance_profile(governance_profile)
    plan = _resolve_plan(
        store_root=store_root,
        manifest_ref=manifest_ref,
        training_config_ref=str(training_profile),
        governance_profile_ref=str(governance_profile),
    )

    executor = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root)))
    with pytest.raises(MfPhase4ExecutionError) as exc:
        executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:06:00Z")
    assert exc.value.code == "LEAKAGE_GUARD_VIOLATION"


def test_phase4_eval_report_artifact_detects_immutability_drift(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T140600Z/ofs/manifests/dm_004.json"
    _write_manifest(store_root / manifest_ref)
    training_profile = tmp_path / "train_profile.yaml"
    governance_profile = tmp_path / "governance_profile.yaml"
    _write_training_profile(training_profile, include_split=True)
    _write_governance_profile(governance_profile)
    plan = _resolve_plan(
        store_root=store_root,
        manifest_ref=manifest_ref,
        training_config_ref=str(training_profile),
        governance_profile_ref=str(governance_profile),
    )
    executor = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root)))
    receipt = executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:06:00Z")

    eval_path = Path(receipt.eval_report_ref)
    payload = json.loads(eval_path.read_text(encoding="utf-8"))
    payload["metrics"]["scores"]["auc_roc"] = 0.001
    eval_path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    with pytest.raises(MfPhase4ExecutionError) as exc:
        executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:06:00Z")
    assert exc.value.code == "EVAL_REPORT_IMMUTABILITY_VIOLATION"
