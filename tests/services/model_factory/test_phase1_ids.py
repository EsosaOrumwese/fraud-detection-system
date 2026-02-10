from __future__ import annotations

from fraud_detection.model_factory import (
    canonical_train_run_key_payload,
    deterministic_train_run_id,
    train_run_key,
)


def _run_key_payload() -> dict[str, object]:
    return {
        "intent_kind": "baseline_train",
        "platform_run_id": "platform_20260210T091951Z",
        "dataset_manifest_refs": [
            "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_b.json",
            "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_a.json",
        ],
        "training_config_ref": "s3://fraud-platform/config/mf/train_config_v0.yaml",
        "governance_profile_ref": "s3://fraud-platform/config/mf/governance_profile_v0.yaml",
        "target_scope": {
            "mode": "fraud",
            "environment": "local_parity",
            "bundle_slot": "primary",
        },
        "policy_revision": "mf-policy-v0",
        "config_revision": "local-parity-v0",
        "mf_code_release_id": "git:def456",
    }


def test_train_run_key_is_order_stable_for_manifest_refs() -> None:
    first = _run_key_payload()
    second = _run_key_payload()
    second["dataset_manifest_refs"] = list(reversed(second["dataset_manifest_refs"]))
    assert train_run_key(first) == train_run_key(second)


def test_train_run_key_changes_when_training_config_changes() -> None:
    first = _run_key_payload()
    second = _run_key_payload()
    second["training_config_ref"] = "s3://fraud-platform/config/mf/train_config_v1.yaml"
    assert train_run_key(first) != train_run_key(second)


def test_deterministic_train_run_id_is_stable_for_same_run_key() -> None:
    run_key = train_run_key(_run_key_payload())
    first = deterministic_train_run_id(run_key)
    second = deterministic_train_run_id(run_key)
    assert first == second
    assert first.startswith("tr_")
    assert len(first) == 35


def test_canonical_train_run_key_payload_normalizes_scope_and_refs() -> None:
    payload = canonical_train_run_key_payload(_run_key_payload())
    assert payload["dataset_manifest_refs"] == [
        "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_a.json",
        "s3://fraud-platform/platform_20260210T091951Z/ofs/manifests/dm_b.json",
    ]
    target_scope = payload["target_scope"]
    assert target_scope["bundle_slot"] == "primary"
    assert target_scope["environment"] == "local_parity"
    assert target_scope["mode"] == "fraud"

