from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fraud_detection.online_feature_plane.projector import OnlineFeatureProjector
from fraud_detection.online_feature_plane.snapshots import OfpSnapshotMaterializer


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
        "payload": {"flow_id": "snap-flow-1", "amount": 12.5},
    }
    topic_dir = bus_root / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    (topic_dir / "partition=0.jsonl").write_text(
        json.dumps({"envelope": envelope}, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _to_legacy_snapshot_ref(snapshot_ref: str) -> str:
    normalized = snapshot_ref.replace("\\", "/")
    if "/online_feature_plane/snapshots/" in normalized:
        normalized = normalized.replace("/online_feature_plane/snapshots/", "/ofp/snapshots/")
    if "\\" in snapshot_ref and "/" in normalized:
        return normalized.replace("/", "\\")
    return normalized


def test_snapshot_materialize_writes_artifact_and_index(tmp_path) -> None:
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

    materializer = OfpSnapshotMaterializer.build(str(profile_path))
    snapshot_a = materializer.materialize(
        platform_run_id="platform_20260206T170000Z",
        scenario_run_id="d" * 32,
    )
    snapshot_b = materializer.materialize(
        platform_run_id="platform_20260206T170000Z",
        scenario_run_id="d" * 32,
    )

    assert snapshot_a["snapshot_hash"] == snapshot_b["snapshot_hash"]
    assert "/online_feature_plane/snapshots/" in str(snapshot_a["snapshot_ref"]).replace("\\", "/")
    assert snapshot_a["snapshot_ref"].endswith(f"{snapshot_a['snapshot_hash']}.json")
    assert snapshot_a["feature_def_policy_rev"]["policy_id"] == "ofp.features.v0"
    assert snapshot_a["feature_def_policy_rev"]["revision"] == "r1"
    assert snapshot_a["features"]["flow_id:snap-flow-1"]["event_count"] == 1
    assert snapshot_a["features"]["flow_id:snap-flow-1"]["amount_sum"] == 12.5

    snapshot_hash = snapshot_a["snapshot_hash"]
    index_row = materializer.get_snapshot_index(snapshot_hash)
    assert index_row is not None
    assert index_row["snapshot_ref"] == snapshot_a["snapshot_ref"]
    assert index_row["platform_run_id"] == "platform_20260206T170000Z"
    assert index_row["scenario_run_id"] == "d" * 32

    loaded = materializer.load_snapshot(snapshot_hash)
    assert loaded is not None
    assert loaded["snapshot_hash"] == snapshot_hash
    assert loaded["features"]["flow_id:snap-flow-1"]["event_count"] == 1


def test_snapshot_load_supports_legacy_index_ref_fallback(tmp_path) -> None:
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

    materializer = OfpSnapshotMaterializer.build(str(profile_path))
    snapshot = materializer.materialize(
        platform_run_id="platform_20260206T170000Z",
        scenario_run_id="d" * 32,
    )

    snapshot_hash = str(snapshot["snapshot_hash"])
    legacy_ref = _to_legacy_snapshot_ref(str(snapshot["snapshot_ref"]))
    with sqlite3.connect(snapshot_index_db) as conn:
        conn.execute(
            "UPDATE ofp_snapshot_index SET snapshot_ref = ? WHERE snapshot_hash = ?",
            (legacy_ref, snapshot_hash),
        )

    loaded = materializer.load_snapshot(snapshot_hash)
    assert loaded is not None
    assert loaded["snapshot_hash"] == snapshot_hash
