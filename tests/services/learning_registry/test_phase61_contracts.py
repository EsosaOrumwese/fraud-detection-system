from __future__ import annotations

import pytest

from fraud_detection.learning_registry.contracts import (
    DatasetManifestContract,
    DfBundleResolutionContract,
    load_ownership_boundaries,
)
from fraud_detection.learning_registry.schemas import LearningRegistrySchemaError


def test_dataset_manifest_contract_validates() -> None:
    payload = {
        "schema_version": "learning.dataset_manifest.v0",
        "dataset_manifest_id": "dm_001",
        "dataset_fingerprint": "f" * 32,
        "platform_run_id": "platform_20260210T000000Z",
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
            "label_asof_utc": "2026-02-10T00:00:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
        },
        "feature_definition_set": {"feature_set_id": "core", "feature_set_version": "v1"},
        "provenance": {"ofs_code_release_id": "git:abc123", "config_revision": "r1"},
    }
    contract = DatasetManifestContract.from_payload(payload)
    assert contract.payload["dataset_manifest_id"] == "dm_001"


def test_dataset_manifest_contract_fails_when_replay_basis_missing() -> None:
    payload = {
        "schema_version": "learning.dataset_manifest.v0",
        "dataset_manifest_id": "dm_001",
        "dataset_fingerprint": "f" * 32,
        "platform_run_id": "platform_20260210T000000Z",
        "label_basis": {
            "label_asof_utc": "2026-02-10T00:00:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
        },
        "feature_definition_set": {"feature_set_id": "core", "feature_set_version": "v1"},
        "provenance": {"ofs_code_release_id": "git:abc123", "config_revision": "r1"},
    }
    with pytest.raises(LearningRegistrySchemaError):
        DatasetManifestContract.from_payload(payload)


def test_df_bundle_resolution_contract_requires_policy_rev() -> None:
    payload = {
        "schema_version": "learning.df_bundle_resolution.v0",
        "scope_key": {"environment": "local_parity", "mode": "fraud", "bundle_slot": "primary"},
        "resolution_outcome": "RESOLVED",
    }
    with pytest.raises(LearningRegistrySchemaError):
        DfBundleResolutionContract.from_payload(payload)


def test_ownership_boundaries_file_loads() -> None:
    payload = load_ownership_boundaries()
    assert "owners" in payload
    assert "ofs" in payload["owners"]
