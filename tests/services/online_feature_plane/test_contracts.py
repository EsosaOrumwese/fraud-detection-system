from __future__ import annotations

import pytest

from fraud_detection.online_feature_plane.contracts import (
    OfpContractError,
    build_get_features_error,
    build_get_features_success,
    build_snapshot_hash,
    error_status,
    validate_get_features_request,
)


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260206T000000Z",
        "scenario_run_id": "a" * 32,
        "scenario_id": "baseline_v1",
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "run_id": "a" * 32,
    }


def _snapshot() -> dict[str, object]:
    return {
        "pins": _pins(),
        "created_at_utc": "2026-02-06T00:00:00.000000Z",
        "as_of_time_utc": "2026-02-06T00:00:01.000000Z",
        "feature_groups": [
            {"name": "txn_velocity", "version": "v1"},
            {"name": "merchant_risk", "version": "v1"},
        ],
        "feature_def_policy_rev": {"policy_id": "ofp.features.v0", "revision": "r1", "content_digest": "d" * 64},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "100"}],
        },
        "graph_version": {"version_id": "e" * 32, "watermark_ts_utc": "2026-02-06T00:00:01.000000Z"},
        "run_config_digest": "f" * 64,
        "features": {"txn_count_24h": 9, "merchant_chargeback_rate_30d": 0.01},
        "freshness": {"stale_groups": [], "missing_groups": []},
    }


def test_validate_get_features_request_requires_pins() -> None:
    with pytest.raises(OfpContractError) as exc:
        validate_get_features_request(
            {
                "pins": {},
                "as_of_time_utc": "2026-02-06T00:00:01.000000Z",
                "feature_keys": [{"key_type": "flow_id", "key_id": "flow-1"}],
                "feature_groups": [{"name": "txn_velocity", "version": "v1"}],
            }
        )
    assert exc.value.code == "MISSING_PINS"


def test_snapshot_hash_is_deterministic_for_group_order() -> None:
    snap_a = _snapshot()
    snap_b = _snapshot()
    snap_b["feature_groups"] = [
        {"name": "merchant_risk", "version": "v1"},
        {"name": "txn_velocity", "version": "v1"},
    ]
    assert build_snapshot_hash(snap_a) == build_snapshot_hash(snap_b)


def test_build_success_populates_snapshot_hash() -> None:
    snapshot = _snapshot()
    snapshot.pop("snapshot_hash", None)
    payload = build_get_features_success(snapshot, request_id="req-1")
    assert payload["status"] == "OK"
    assert payload["request_id"] == "req-1"
    assert payload["snapshot"]["snapshot_hash"]


def test_error_defaults_for_not_found_and_unavailable() -> None:
    not_found = build_get_features_error("NOT_FOUND", detail="key missing")
    unavailable = build_get_features_error("UNAVAILABLE")
    assert not_found["retryable"] is False
    assert unavailable["retryable"] is True
    assert error_status("NOT_FOUND") == 404
    assert error_status("UNAVAILABLE") == 503
