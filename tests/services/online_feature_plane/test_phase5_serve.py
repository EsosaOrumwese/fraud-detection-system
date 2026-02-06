from __future__ import annotations

import json
from pathlib import Path

from fraud_detection.online_feature_plane.projector import OnlineFeatureProjector
from fraud_detection.online_feature_plane.serve import OfpGetFeaturesService


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260206T170000Z",
        "scenario_run_id": "d" * 32,
        "scenario_id": "baseline_v1",
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "run_id": "e" * 32,
    }


def _write_features(path: Path) -> None:
    payload = {
        "policy_id": "ofp.features.v0",
        "revision": "r1",
        "feature_groups": [
            {
                "name": "core_features",
                "version": "v1",
                "key_type": "flow_id",
                "windows": [
                    {"window": "1h", "duration": "1h", "ttl": "1h"},
                    {"window": "24h", "duration": "24h", "ttl": "24h"},
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_profile(
    path: Path,
    *,
    bus_root: Path,
    projection_db: Path,
    snapshot_index_db: Path,
    snapshot_store_root: Path,
    topic: str,
) -> None:
    features_path = path.parent / "features.json"
    _write_features(features_path)
    profile = {
        "ofp": {
            "policy": {
                "stream_id": "ofp.v0",
                "features_ref": str(features_path),
                "feature_group_name": "core_features",
                "feature_group_version": "v1",
                "key_precedence": ["flow_id", "event_id"],
                "amount_fields": ["amount"],
            },
            "wiring": {
                "projection_db_dsn": str(projection_db),
                "snapshot_index_dsn": str(snapshot_index_db),
                "snapshot_store_root": str(snapshot_store_root),
                "event_bus_kind": "file",
                "required_platform_run_id": "platform_20260206T170000Z",
                "event_bus": {
                    "root": str(bus_root),
                    "topics": [topic],
                },
                "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
                "poll_max_records": 200,
                "poll_sleep_seconds": 0.01,
            },
        }
    }
    path.write_text(json.dumps(profile), encoding="utf-8")


def _write_bus_record(bus_root: Path, topic: str) -> None:
    pins = _pins()
    envelope = {
        "event_id": "1" * 64,
        "event_type": "s3_event_stream_with_fraud_6B",
        "schema_version": "v1",
        "ts_utc": "2026-02-06T17:05:00.123456Z",
        "manifest_fingerprint": pins["manifest_fingerprint"],
        "parameter_hash": pins["parameter_hash"],
        "seed": pins["seed"],
        "scenario_id": pins["scenario_id"],
        "platform_run_id": pins["platform_run_id"],
        "scenario_run_id": pins["scenario_run_id"],
        "run_id": pins["run_id"],
        "payload": {"flow_id": "serve-flow-1", "amount": 12.5},
    }
    topic_dir = bus_root / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    (topic_dir / "partition=0.jsonl").write_text(
        json.dumps({"envelope": envelope}, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _build_service(tmp_path: Path) -> tuple[OfpGetFeaturesService, str]:
    topic = "fp.bus.traffic.fraud.v1"
    bus_root = tmp_path / "bus"
    profile_path = tmp_path / "profile.json"
    projection_db = tmp_path / "projection.db"
    snapshot_index_db = tmp_path / "snapshot_index.db"
    snapshot_store_root = tmp_path / "snapshots"
    _write_profile(
        profile_path,
        bus_root=bus_root,
        projection_db=projection_db,
        snapshot_index_db=snapshot_index_db,
        snapshot_store_root=snapshot_store_root,
        topic=topic,
    )
    _write_bus_record(bus_root, topic)
    projector = OnlineFeatureProjector.build(str(profile_path))
    assert projector.run_once() == 1
    return OfpGetFeaturesService.build(str(profile_path)), str(profile_path)


def _request_payload(*, as_of_time_utc: str, feature_keys: list[dict[str, str]], graph_resolution_mode: str = "resolve_if_needed") -> dict[str, object]:
    pins = _pins()
    return {
        "pins": {
            "platform_run_id": pins["platform_run_id"],
            "scenario_run_id": pins["scenario_run_id"],
            "scenario_id": pins["scenario_id"],
            "manifest_fingerprint": pins["manifest_fingerprint"],
            "parameter_hash": pins["parameter_hash"],
            "seed": pins["seed"],
            "run_id": pins["run_id"],
        },
        "as_of_time_utc": as_of_time_utc,
        "feature_keys": feature_keys,
        "feature_groups": [{"name": "core_features", "version": "v1"}],
        "graph_resolution_mode": graph_resolution_mode,
        "request_id": "req-phase5",
    }


def test_get_features_requires_as_of_time_utc(tmp_path) -> None:
    service, _ = _build_service(tmp_path)
    payload = _request_payload(
        as_of_time_utc="2026-02-06T17:05:00.123456Z",
        feature_keys=[{"key_type": "flow_id", "key_id": "serve-flow-1"}],
    )
    payload.pop("as_of_time_utc")
    response = service.get_features(payload)
    assert response["status"] == "ERROR"
    assert response["code"] == "INVALID_REQUEST"


def test_get_features_stamps_graph_version_when_resolver_is_used(tmp_path) -> None:
    _, profile_path = _build_service(tmp_path)

    def _resolver(_: dict[str, object]) -> dict[str, str]:
        return {
            "version_id": "f" * 32,
            "stream": "ieg.v0::platform_20260206T170000Z",
            "basis_digest": "a" * 64,
            "watermark_ts_utc": "2026-02-06T17:05:00.123456Z",
        }

    service = OfpGetFeaturesService.build(profile_path, graph_version_resolver=_resolver)
    response = service.get_features(
        _request_payload(
            as_of_time_utc="2026-02-06T17:05:00.123456Z",
            feature_keys=[{"key_type": "flow_id", "key_id": "serve-flow-1"}],
        )
    )
    assert response["status"] == "OK"
    snapshot = response["snapshot"]
    assert snapshot["as_of_time_utc"] == "2026-02-06T17:05:00.123456Z"
    assert snapshot["graph_version"]["version_id"] == "f" * 32
    assert snapshot["eb_offset_basis"]["basis_digest"]
    assert snapshot["freshness"]["state"] == "GREEN"


def test_get_features_surfaces_stale_and_missing_posture_flags(tmp_path) -> None:
    service, _ = _build_service(tmp_path)
    response = service.get_features(
        _request_payload(
            as_of_time_utc="2026-02-07T17:05:00.123456Z",
            feature_keys=[
                {"key_type": "flow_id", "key_id": "serve-flow-1"},
                {"key_type": "flow_id", "key_id": "serve-flow-missing"},
            ],
            graph_resolution_mode="none",
        )
    )
    assert response["status"] == "OK"
    freshness = response["snapshot"]["freshness"]
    assert freshness["state"] == "RED"
    assert "MISSING_FEATURE_STATE" in freshness["flags"]
    assert "STALE_INPUT_BASIS" in freshness["flags"]
    assert "core_features" in freshness["stale_groups"]
    assert "core_features" in freshness["missing_groups"]
    assert "flow_id:serve-flow-missing" in freshness["missing_feature_keys"]


def test_get_features_require_ieg_fails_closed_without_resolver(tmp_path) -> None:
    service, _ = _build_service(tmp_path)
    response = service.get_features(
        _request_payload(
            as_of_time_utc="2026-02-06T17:05:00.123456Z",
            feature_keys=[{"key_type": "flow_id", "key_id": "serve-flow-1"}],
            graph_resolution_mode="require_ieg",
        )
    )
    assert response["status"] == "ERROR"
    assert response["code"] == "UNAVAILABLE"
