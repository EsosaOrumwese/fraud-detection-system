from __future__ import annotations

import json
from pathlib import Path

from fraud_detection.online_feature_plane.projector import OnlineFeatureProjector
from fraud_detection.online_feature_plane.snapshots import OfpSnapshotMaterializer


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260206T180000Z",
        "scenario_run_id": "d" * 32,
        "scenario_id": "baseline_v1",
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "run_id": "e" * 32,
    }


def _write_features(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    poll_max_records: int = 200,
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
                "required_platform_run_id": "platform_20260206T180000Z",
                "event_bus": {
                    "root": str(bus_root),
                    "topics": [topic],
                },
                "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
                "poll_max_records": int(poll_max_records),
                "poll_sleep_seconds": 0.01,
            },
        }
    }
    path.write_text(json.dumps(profile), encoding="utf-8")


def _envelope(*, event_id: str, ts_utc: str, flow_id: str, amount: float) -> dict[str, object]:
    pins = _pins()
    return {
        "event_id": event_id,
        "event_type": "s3_event_stream_with_fraud_6B",
        "schema_version": "v1",
        "ts_utc": ts_utc,
        "manifest_fingerprint": pins["manifest_fingerprint"],
        "parameter_hash": pins["parameter_hash"],
        "seed": pins["seed"],
        "scenario_id": pins["scenario_id"],
        "platform_run_id": pins["platform_run_id"],
        "scenario_run_id": pins["scenario_run_id"],
        "run_id": pins["run_id"],
        "payload": {
            "flow_id": flow_id,
            "amount": amount,
        },
    }


def _write_bus_records(bus_root: Path, topic: str, envelopes: list[dict[str, object]]) -> None:
    topic_dir = bus_root / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    path = topic_dir / "partition=0.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for envelope in envelopes:
            handle.write(json.dumps({"envelope": envelope}, sort_keys=True, ensure_ascii=True) + "\n")


def _run_to_completion(projector: OnlineFeatureProjector) -> int:
    total = 0
    while True:
        processed = projector.run_once()
        total += processed
        if processed == 0:
            return total


def _snapshot_for_profile(profile_path: Path) -> dict[str, object]:
    materializer = OfpSnapshotMaterializer.build(str(profile_path))
    return materializer.materialize(
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
        as_of_time_utc="2026-02-06T17:05:00.123456Z",
    )


def _build_pipeline(tmp_path: Path, *, name: str, envelopes: list[dict[str, object]], poll_max_records: int = 200) -> Path:
    topic = "fp.bus.traffic.fraud.v1"
    root = tmp_path / name
    bus_root = root / "bus"
    projection_db = root / "projection.db"
    snapshot_index_db = root / "snapshot_index.db"
    snapshot_store_root = root / "snapshots"
    profile_path = root / "profile.json"
    _write_profile(
        profile_path,
        bus_root=bus_root,
        projection_db=projection_db,
        snapshot_index_db=snapshot_index_db,
        snapshot_store_root=snapshot_store_root,
        topic=topic,
        poll_max_records=poll_max_records,
    )
    _write_bus_records(bus_root, topic, envelopes)
    return profile_path


def _event_set() -> list[dict[str, object]]:
    return [
        _envelope(
            event_id="1" * 64,
            ts_utc="2026-02-06T17:03:00.123456Z",
            flow_id="flow-1",
            amount=10.0,
        ),
        _envelope(
            event_id="2" * 64,
            ts_utc="2026-02-06T17:05:00.123456Z",
            flow_id="flow-1",
            amount=3.5,
        ),
        _envelope(
            event_id="3" * 64,
            ts_utc="2026-02-06T17:04:00.123456Z",
            flow_id="flow-2",
            amount=7.0,
        ),
    ]


def test_replay_same_basis_yields_identical_snapshot_hash(tmp_path) -> None:
    events = _event_set()
    profile_a = _build_pipeline(tmp_path, name="run_a", envelopes=events)
    profile_b = _build_pipeline(tmp_path, name="run_b", envelopes=events)

    _run_to_completion(OnlineFeatureProjector.build(str(profile_a)))
    _run_to_completion(OnlineFeatureProjector.build(str(profile_b)))

    snapshot_a = _snapshot_for_profile(profile_a)
    snapshot_b = _snapshot_for_profile(profile_b)

    assert snapshot_a["snapshot_hash"] == snapshot_b["snapshot_hash"]
    assert snapshot_a["features"] == snapshot_b["features"]
    assert snapshot_a["eb_offset_basis"] == snapshot_b["eb_offset_basis"]


def test_restart_resume_matches_single_pass_snapshot(tmp_path) -> None:
    events = _event_set()
    profile_restart = _build_pipeline(
        tmp_path,
        name="restart",
        envelopes=events,
        poll_max_records=1,
    )
    profile_single = _build_pipeline(
        tmp_path,
        name="single",
        envelopes=events,
        poll_max_records=200,
    )

    restart_first = OnlineFeatureProjector.build(str(profile_restart))
    assert restart_first.run_once() == 1
    restart_second = OnlineFeatureProjector.build(str(profile_restart))
    _run_to_completion(restart_second)

    _run_to_completion(OnlineFeatureProjector.build(str(profile_single)))

    snapshot_restart = _snapshot_for_profile(profile_restart)
    snapshot_single = _snapshot_for_profile(profile_single)

    assert snapshot_restart["snapshot_hash"] == snapshot_single["snapshot_hash"]
    assert snapshot_restart["features"] == snapshot_single["features"]
    assert snapshot_restart["eb_offset_basis"] == snapshot_single["eb_offset_basis"]


def test_out_of_order_event_time_arrival_is_deterministic(tmp_path) -> None:
    ordered = _event_set()
    reordered = [ordered[1], ordered[2], ordered[0]]

    profile_ordered = _build_pipeline(tmp_path, name="ordered", envelopes=ordered)
    profile_reordered = _build_pipeline(tmp_path, name="reordered", envelopes=reordered)

    _run_to_completion(OnlineFeatureProjector.build(str(profile_ordered)))
    _run_to_completion(OnlineFeatureProjector.build(str(profile_reordered)))

    snapshot_ordered = _snapshot_for_profile(profile_ordered)
    snapshot_reordered = _snapshot_for_profile(profile_reordered)

    assert snapshot_ordered["snapshot_hash"] == snapshot_reordered["snapshot_hash"]
    assert snapshot_ordered["features"] == snapshot_reordered["features"]
    assert snapshot_ordered["eb_offset_basis"] == snapshot_reordered["eb_offset_basis"]


def test_reprocessing_after_checkpoint_is_noop_for_snapshot_hash(tmp_path) -> None:
    events = _event_set()
    profile_path = _build_pipeline(tmp_path, name="checkpoint_noop", envelopes=events)

    projector = OnlineFeatureProjector.build(str(profile_path))
    assert _run_to_completion(projector) == 3
    snapshot_first = _snapshot_for_profile(profile_path)

    # Checkpoint must prevent re-apply on a second pass over the same source.
    assert projector.run_once() == 0
    snapshot_second = _snapshot_for_profile(profile_path)

    assert snapshot_first["snapshot_hash"] == snapshot_second["snapshot_hash"]
    assert snapshot_first["features"] == snapshot_second["features"]
    assert snapshot_first["eb_offset_basis"] == snapshot_second["eb_offset_basis"]
