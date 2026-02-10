from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from fraud_detection.model_factory import (
    MfGatePolicyConfig,
    MfGatePolicyEvaluator,
    MfPhase5GateError,
    MfTrainBuildRequest,
    MfTrainEvalExecutor,
    MfTrainEvalExecutorConfig,
    MfTrainPlanResolver,
    MfTrainPlanResolverConfig,
)


def _write_manifest(
    path: Path,
    *,
    platform_run_id: str = "platform_20260210T141300Z",
    resolution_rule: str = "observed_time<=label_asof_utc",
) -> None:
    payload = {
        "schema_version": "learning.dataset_manifest.v0",
        "dataset_manifest_id": "dm_20260210_005",
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
        "revision": "r5",
        "feature_definition_set": {
            "feature_set_id": "core_features",
            "feature_set_version": "v1",
        },
        "expected_manifest_schema_version": "learning.dataset_manifest.v0",
        "split_strategy": "time_based",
        "seed_policy": {
            "recipe": "mf.phase4.seed.v0",
            "base_seed": 41,
        },
        "leakage": {
            "expected_label_rule": "observed_time<=label_asof_utc",
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_governance_profile(path: Path, *, min_auc: float, min_precision: float) -> None:
    payload = {
        "policy_id": "mf.governance.policy.v0",
        "revision": "r9",
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
        "request_id": "mf.phase5.req.001",
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T141300Z",
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
        "mf_code_release_id": "git:mfphase5",
        "publish_allowed": True,
    }


def _prepare_phase4_receipt(
    *,
    tmp_path: Path,
    min_auc: float,
    min_precision: float,
):
    store_root = tmp_path / "store"
    manifest_ref = "platform_20260210T141300Z/ofs/manifests/dm_005.json"
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
    resolver = MfTrainPlanResolver(config=MfTrainPlanResolverConfig(object_store_root=str(store_root)))
    plan = resolver.resolve(request=request)
    executor = MfTrainEvalExecutor(config=MfTrainEvalExecutorConfig(object_store_root=str(store_root)))
    receipt = executor.execute(plan=plan, execution_started_at_utc="2026-02-10T14:13:00Z")
    return store_root, plan, receipt


def test_phase5_pass_gate_is_publish_eligible(tmp_path: Path) -> None:
    store_root, plan, receipt = _prepare_phase4_receipt(tmp_path=tmp_path, min_auc=0.10, min_precision=0.10)
    evaluator = MfGatePolicyEvaluator(config=MfGatePolicyConfig(object_store_root=str(store_root)))

    result = evaluator.evaluate(plan=plan, train_eval_receipt=receipt)

    assert result.gate_receipt.gate_decision == "PASS"
    assert result.publish_eligibility.eligible is True
    assert result.publish_eligibility.decision == "ELIGIBLE"
    assert "PASS_READY" in result.publish_eligibility.reason_codes
    assert Path(result.gate_receipt_ref).exists()
    assert Path(result.publish_eligibility_ref).exists()


def test_phase5_fail_gate_is_forensics_only_ineligible(tmp_path: Path) -> None:
    store_root, plan, receipt = _prepare_phase4_receipt(tmp_path=tmp_path, min_auc=0.9999, min_precision=0.9999)
    evaluator = MfGatePolicyEvaluator(config=MfGatePolicyConfig(object_store_root=str(store_root)))

    result = evaluator.evaluate(plan=plan, train_eval_receipt=receipt)

    assert result.gate_receipt.gate_decision == "FAIL"
    assert result.publish_eligibility.eligible is False
    assert result.publish_eligibility.decision == "INELIGIBLE"
    assert "GATE_FAIL" in result.publish_eligibility.reason_codes


def test_phase5_fails_closed_when_eval_report_evidence_missing(tmp_path: Path) -> None:
    store_root, plan, receipt = _prepare_phase4_receipt(tmp_path=tmp_path, min_auc=0.10, min_precision=0.10)
    evaluator = MfGatePolicyEvaluator(config=MfGatePolicyConfig(object_store_root=str(store_root)))
    Path(receipt.eval_report_ref).unlink()

    with pytest.raises(MfPhase5GateError) as exc:
        evaluator.evaluate(plan=plan, train_eval_receipt=receipt)
    assert exc.value.code == "EVAL_REPORT_UNRESOLVED"


def test_phase5_detects_gate_receipt_immutability_drift(tmp_path: Path) -> None:
    store_root, plan, receipt = _prepare_phase4_receipt(tmp_path=tmp_path, min_auc=0.10, min_precision=0.10)
    evaluator = MfGatePolicyEvaluator(config=MfGatePolicyConfig(object_store_root=str(store_root)))
    first = evaluator.evaluate(plan=plan, train_eval_receipt=receipt)

    gate_receipt_path = Path(first.gate_receipt_ref)
    payload = json.loads(gate_receipt_path.read_text(encoding="utf-8"))
    payload["gate_decision"] = "FAIL"
    gate_receipt_path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")

    with pytest.raises(MfPhase5GateError) as exc:
        evaluator.evaluate(plan=plan, train_eval_receipt=receipt)
    assert exc.value.code == "GATE_RECEIPT_IMMUTABILITY_VIOLATION"
