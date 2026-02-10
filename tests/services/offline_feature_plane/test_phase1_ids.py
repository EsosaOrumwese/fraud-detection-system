from __future__ import annotations

from fraud_detection.offline_feature_plane import (
    canonical_dataset_identity,
    dataset_fingerprint,
    deterministic_dataset_manifest_id,
)


def _identity_payload() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260210T091951Z",
        "scenario_run_ids": ["run_b", "run_a"],
        "replay_basis": [
            {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset_kind": "kinesis_sequence",
                "start_offset": "100",
                "end_offset": "200",
            },
            {
                "topic": "fp.bus.context.arrival_events.v1",
                "partition": 1,
                "offset_kind": "kinesis_sequence",
                "start_offset": "10",
                "end_offset": "90",
            },
        ],
        "label_basis": {
            "label_asof_utc": "2026-02-10T10:00:00Z",
            "resolution_rule": "observed_time<=label_asof_utc",
            "maturity_days": 30,
        },
        "feature_definition_set": {"feature_set_id": "core", "feature_set_version": "v1"},
        "join_scope": {"subject_key": "platform_run_id,event_id"},
        "filters": {"country": ["US"], "merchant_segment": ["enterprise", "sm_biz"]},
        "policy_revision": "ofs-policy-v0",
        "config_revision": "local-parity-v0",
        "ofs_code_release_id": "git:abc123",
    }


def test_dataset_fingerprint_is_order_stable() -> None:
    first = _identity_payload()
    second = _identity_payload()
    second["scenario_run_ids"] = ["run_a", "run_b"]
    second["replay_basis"] = list(reversed(second["replay_basis"]))
    second["filters"] = {"merchant_segment": ["enterprise", "sm_biz"], "country": ["US"]}
    assert dataset_fingerprint(first) == dataset_fingerprint(second)


def test_dataset_fingerprint_changes_when_label_asof_changes() -> None:
    first = _identity_payload()
    second = _identity_payload()
    second["label_basis"] = {
        "label_asof_utc": "2026-02-11T10:00:00Z",
        "resolution_rule": "observed_time<=label_asof_utc",
        "maturity_days": 30,
    }
    assert dataset_fingerprint(first) != dataset_fingerprint(second)


def test_manifest_id_is_deterministic_from_fingerprint() -> None:
    fingerprint = dataset_fingerprint(_identity_payload())
    first = deterministic_dataset_manifest_id(fingerprint)
    second = deterministic_dataset_manifest_id(fingerprint)
    assert first == second
    assert first.startswith("dm_")
    assert len(first) == 35


def test_canonical_identity_normalizes_replay_and_scenario_order() -> None:
    identity = canonical_dataset_identity(_identity_payload())
    replay_basis = identity["replay_basis"]
    assert replay_basis[0]["topic"] == "fp.bus.context.arrival_events.v1"
    assert replay_basis[1]["topic"] == "fp.bus.traffic.fraud.v1"
    assert identity["scenario_run_ids"] == ["run_a", "run_b"]
