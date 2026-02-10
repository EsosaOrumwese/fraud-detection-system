from __future__ import annotations

import json
from pathlib import Path

import pytest

from fraud_detection.online_feature_plane.config import OfpProfile
from fraud_detection.online_feature_plane.projector import OnlineFeatureProjector


def _write_profile(path: Path, *, bus_root: Path, db_path: Path, features_ref: str) -> None:
    profile = {
        "ofp": {
            "policy": {
                "stream_id": "ofp.v0",
                "features_ref": features_ref,
                "feature_group_name": "core_features",
                "feature_group_version": "v1",
                "key_precedence": ["flow_id", "event_id"],
                "amount_fields": ["amount"],
            },
            "wiring": {
                "projection_db_dsn": str(db_path),
                "event_bus_kind": "file",
                "required_platform_run_id": "platform_20260206T000000Z",
                "event_bus": {
                    "root": str(bus_root),
                    "topics": ["fp.bus.traffic.fraud.v1"],
                },
                "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
                "poll_max_records": 50,
                "poll_sleep_seconds": 0.01,
            },
        }
    }
    path.write_text(json.dumps(profile), encoding="utf-8")


def _write_features(path: Path, *, include_revision: bool = True, include_windows: bool = True) -> None:
    group: dict[str, object] = {
        "name": "core_features",
        "version": "v1",
        "key_type": "flow_id",
    }
    if include_windows:
        group["windows"] = [{"window": "1h", "duration": "1h", "ttl": "24h"}]
    payload: dict[str, object] = {
        "policy_id": "ofp.features.v0",
        "feature_groups": [group],
    }
    if include_revision:
        payload["revision"] = "r7"
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_one_event(bus_root: Path) -> None:
    topic_dir = bus_root / "fp.bus.traffic.fraud.v1"
    topic_dir.mkdir(parents=True, exist_ok=True)
    envelope = {
        "event_id": "1" * 64,
        "event_type": "s3_event_stream_with_fraud_6B",
        "schema_version": "v1",
        "ts_utc": "2026-02-06T00:00:01.000000Z",
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "scenario_id": "baseline_v1",
        "platform_run_id": "platform_20260206T000000Z",
        "scenario_run_id": "a" * 32,
        "run_id": "a" * 32,
        "payload": {"flow_id": "flow-1", "amount": 10.0},
    }
    (topic_dir / "partition=0.jsonl").write_text(
        json.dumps({"envelope": envelope}, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def test_profile_fails_closed_when_feature_revision_missing(tmp_path) -> None:
    features_path = tmp_path / "features_missing_revision.json"
    _write_features(features_path, include_revision=False)
    profile_path = tmp_path / "profile.json"
    _write_profile(
        profile_path,
        bus_root=tmp_path / "bus",
        db_path=tmp_path / "projection.db",
        features_ref=str(features_path),
    )
    with pytest.raises(ValueError, match="policy_id and revision"):
        OfpProfile.load(profile_path)


def test_profile_uses_default_windows_when_omitted(tmp_path) -> None:
    features_path = tmp_path / "features_no_windows.json"
    _write_features(features_path, include_revision=True, include_windows=False)
    profile_path = tmp_path / "profile.json"
    _write_profile(
        profile_path,
        bus_root=tmp_path / "bus",
        db_path=tmp_path / "projection.db",
        features_ref=str(features_path),
    )

    profile = OfpProfile.load(profile_path)
    group = profile.policy.feature_groups[0]
    assert [item.window for item in group.windows] == ["1h", "24h", "7d"]
    assert [item.duration_seconds for item in group.windows] == [3600, 86400, 604800]
    assert [item.ttl_seconds for item in group.windows] == [3600, 86400, 604800]
    assert profile.policy.feature_def_policy_rev.revision == "r7"


def test_projector_exposes_feature_policy_revision_in_store_meta(tmp_path) -> None:
    features_path = tmp_path / "features.json"
    _write_features(features_path, include_revision=True, include_windows=True)
    bus_root = tmp_path / "bus"
    db_path = tmp_path / "projection.db"
    profile_path = tmp_path / "profile.json"
    _write_profile(profile_path, bus_root=bus_root, db_path=db_path, features_ref=str(features_path))
    _write_one_event(bus_root)

    projector = OnlineFeatureProjector.build(str(profile_path))
    processed = projector.run_once()
    assert processed == 1

    meta = projector.store.projection_meta()
    assert meta is not None
    assert meta["feature_def_policy_id"] == "ofp.features.v0"
    assert meta["feature_def_revision"] == "r7"
    assert len(meta["feature_def_content_digest"]) == 64
    assert len(meta["run_config_digest"]) == 64
