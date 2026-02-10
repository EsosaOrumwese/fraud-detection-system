from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from fraud_detection.online_feature_plane.observability import OfpObservabilityReporter
from fraud_detection.online_feature_plane.projector import OnlineFeatureProjector
from fraud_detection.online_feature_plane.serve import OfpGetFeaturesService
from fraud_detection.online_feature_plane.snapshots import OfpSnapshotMaterializer


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260206T190000Z",
        "scenario_run_id": "d" * 32,
        "scenario_id": "baseline_v1",
        "manifest_fingerprint": "b" * 64,
        "parameter_hash": "c" * 64,
        "seed": 7,
        "run_id": "e" * 32,
    }


def _format_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
                "required_platform_run_id": "platform_20260206T190000Z",
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


def _write_bus_record(bus_root: Path, topic: str, *, event_ts_utc: str) -> None:
    pins = _pins()
    envelope = {
        "event_id": "1" * 64,
        "event_type": "s3_event_stream_with_fraud_6B",
        "schema_version": "v1",
        "ts_utc": event_ts_utc,
        "manifest_fingerprint": pins["manifest_fingerprint"],
        "parameter_hash": pins["parameter_hash"],
        "seed": pins["seed"],
        "scenario_id": pins["scenario_id"],
        "platform_run_id": pins["platform_run_id"],
        "scenario_run_id": pins["scenario_run_id"],
        "run_id": pins["run_id"],
        "payload": {"flow_id": "obs-flow-1", "amount": 12.5},
    }
    topic_dir = bus_root / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    (topic_dir / "partition=0.jsonl").write_text(
        json.dumps({"envelope": envelope}, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _setup_profile(tmp_path: Path, *, write_event: bool = True) -> tuple[Path, str]:
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
    if write_event:
        _write_bus_record(bus_root, topic, event_ts_utc=_format_ts(datetime.now(tz=timezone.utc)))
    return profile_path, topic


def test_phase7_metrics_and_health_export(tmp_path) -> None:
    profile_path, _ = _setup_profile(tmp_path)
    projector = OnlineFeatureProjector.build(str(profile_path))
    assert projector.run_once() == 1

    materializer = OfpSnapshotMaterializer.build(str(profile_path))
    materializer.materialize(
        platform_run_id=str(_pins()["platform_run_id"]),
        scenario_run_id=str(_pins()["scenario_run_id"]),
    )

    as_of = datetime.now(tz=timezone.utc)
    stale_graph = as_of - timedelta(seconds=60)

    def _resolver(_: dict[str, object]) -> dict[str, str]:
        return {
            "version_id": "f" * 32,
            "stream": "ieg.v0::platform_20260206T190000Z",
            "basis_digest": "a" * 64,
            "watermark_ts_utc": _format_ts(stale_graph),
        }

    service = OfpGetFeaturesService.build(str(profile_path), graph_version_resolver=_resolver)
    payload = {
        "pins": {
            "platform_run_id": _pins()["platform_run_id"],
            "scenario_run_id": _pins()["scenario_run_id"],
            "scenario_id": _pins()["scenario_id"],
            "manifest_fingerprint": _pins()["manifest_fingerprint"],
            "parameter_hash": _pins()["parameter_hash"],
            "seed": _pins()["seed"],
            "run_id": _pins()["run_id"],
        },
        "as_of_time_utc": _format_ts(as_of),
        "feature_keys": [
            {"key_type": "flow_id", "key_id": "obs-flow-1"},
            {"key_type": "flow_id", "key_id": "obs-flow-missing"},
        ],
        "feature_groups": [{"name": "core_features", "version": "v1"}],
        "graph_resolution_mode": "resolve_if_needed",
        "request_id": "phase7-req",
    }
    response = service.get_features(payload)
    assert response["status"] == "OK"

    reporter = OfpObservabilityReporter.build(str(profile_path))
    summary = reporter.collect(scenario_run_id=str(_pins()["scenario_run_id"]))

    metrics = summary["metrics"]
    for name in [
        "snapshots_built",
        "snapshot_failures",
        "events_applied",
        "duplicates",
        "stale_graph_version",
        "missing_features",
    ]:
        assert name in metrics
    assert metrics["snapshots_built"] >= 1
    assert metrics["events_applied"] >= 1
    assert metrics["missing_features"] >= 1
    assert metrics["stale_graph_version"] >= 1
    assert summary["watermark_age_seconds"] is not None
    assert summary["health_state"] in {"AMBER", "RED"}

    output_root = tmp_path / "run_export"
    reporter.export(
        scenario_run_id=str(_pins()["scenario_run_id"]),
        output_root=output_root,
    )
    metrics_path = output_root / "online_feature_plane" / "metrics" / "last_metrics.json"
    health_path = output_root / "online_feature_plane" / "health" / "last_health.json"
    assert metrics_path.exists()
    assert health_path.exists()
    health_payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert health_payload["health_state"] in {"AMBER", "RED"}


def test_snapshot_failure_counter_is_exported(tmp_path) -> None:
    profile_path, _ = _setup_profile(tmp_path, write_event=False)
    materializer = OfpSnapshotMaterializer.build(str(profile_path))

    with pytest.raises(RuntimeError):
        materializer.materialize(
            platform_run_id=str(_pins()["platform_run_id"]),
            scenario_run_id=str(_pins()["scenario_run_id"]),
        )

    reporter = OfpObservabilityReporter.build(str(profile_path))
    summary = reporter.collect(scenario_run_id=str(_pins()["scenario_run_id"]))
    assert summary["metrics"]["snapshot_failures"] >= 1


def test_phase7_build_applies_env_threshold_overrides(tmp_path, monkeypatch) -> None:
    profile_path, _ = _setup_profile(tmp_path, write_event=False)
    monkeypatch.setenv("OFP_HEALTH_AMBER_CHECKPOINT_AGE_SECONDS", "777")
    monkeypatch.setenv("OFP_HEALTH_RED_CHECKPOINT_AGE_SECONDS", "999")

    reporter = OfpObservabilityReporter.build(str(profile_path))

    assert reporter.thresholds.amber_checkpoint_age_seconds == 777.0
    assert reporter.thresholds.red_checkpoint_age_seconds == 999.0
