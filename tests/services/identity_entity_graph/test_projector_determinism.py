from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from fraud_detection.event_bus import FileEventBusPublisher
from fraud_detection.identity_entity_graph.projector import IdentityGraphProjector


def _base_pins(platform_run_id: str) -> dict[str, object]:
    return {
        "platform_run_id": platform_run_id,
        "scenario_run_id": "c" * 32,
        "scenario_id": "baseline_v1",
        "run_id": "d" * 32,
        "manifest_fingerprint": "a" * 64,
        "parameter_hash": "b" * 64,
        "seed": 42,
    }


def _envelope(event_type: str, event_id: str, payload: dict[str, object], ts_utc: str, pins: dict[str, object]) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ts_utc": ts_utc,
        "manifest_fingerprint": pins["manifest_fingerprint"],
        "parameter_hash": pins["parameter_hash"],
        "seed": pins["seed"],
        "scenario_id": pins["scenario_id"],
        "run_id": pins["run_id"],
        "platform_run_id": pins["platform_run_id"],
        "scenario_run_id": pins["scenario_run_id"],
        "producer": "test",
        "payload": payload,
    }


def _write_profile(
    tmp_path: Path,
    *,
    bus_root: Path,
    projection_db: Path,
    platform_run_id: str,
    topics: list[str],
) -> Path:
    repo_root = Path.cwd()
    profile = {
        "ieg": {
            "policy": {
                "classification_ref": str(repo_root / "config/platform/ieg/classification_v0.yaml"),
                "identity_hints_ref": str(repo_root / "config/platform/ieg/identity_hints_v0.yaml"),
                "retention_ref": str(repo_root / "config/platform/ieg/retention_local_v0.yaml"),
                "class_map_ref": str(repo_root / "config/platform/ig/class_map_v0.yaml"),
                "partitioning_profiles_ref": str(repo_root / "config/platform/ig/partitioning_profiles_v0.yaml"),
                "graph_stream_id": "ieg.v0",
            },
            "wiring": {
                "profile_id": "test",
                "projection_db_dsn": str(projection_db),
                "event_bus_kind": "file",
                "event_bus": {"root": str(bus_root), "topics": topics},
                "engine_contracts_root": str(repo_root / "docs/model_spec/data-engine/interface_pack/contracts"),
                "poll_max_records": 100,
                "poll_sleep_seconds": 0.0,
                "checkpoint_every": 1,
                "max_inflight": 100,
                "batch_size": 50,
                "required_platform_run_id": platform_run_id,
                "lock_run_scope_on_first_event": True,
            },
        }
    }
    path = tmp_path / f"ieg_profile_{platform_run_id}.yaml"
    path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    return path


def _run_projector(profile_path: Path) -> dict[str, object]:
    projector = IdentityGraphProjector.build(str(profile_path))
    while True:
        processed = projector.run_once()
        if processed == 0:
            break
    db_path = Path(projector.profile.wiring.projection_db_dsn)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT graph_version, run_config_digest FROM ieg_graph_versions"
        ).fetchone()
        graph_version = row[0]
        run_config_digest = row[1]
        counts = {
            "dedupe": conn.execute("SELECT COUNT(*) FROM ieg_dedupe").fetchone()[0],
            "entities": conn.execute("SELECT COUNT(*) FROM ieg_entities").fetchone()[0],
            "identifiers": conn.execute("SELECT COUNT(*) FROM ieg_identifiers").fetchone()[0],
            "apply_failures": conn.execute("SELECT COUNT(*) FROM ieg_apply_failures").fetchone()[0],
        }
        watermark = conn.execute("SELECT MAX(watermark_ts_utc) FROM ieg_checkpoints").fetchone()[0]
    return {
        "graph_version": graph_version,
        "run_config_digest": run_config_digest,
        "counts": counts,
        "watermark": watermark,
    }


def _seed_bus(bus_root: Path, *, platform_run_id: str) -> list[tuple[str, dict[str, object]]]:
    publisher = FileEventBusPublisher(bus_root)
    pins = _base_pins(platform_run_id)
    events = [
        (
            "fp.bus.context.arrival_events.v1",
            _envelope(
                "arrival_events_5B",
                "e" * 64,
                {"merchant_id": "m1"},
                "2026-02-05T00:00:00.000000Z",
                pins,
            ),
        ),
        (
            "fp.bus.context.arrival_entities.v1",
            _envelope(
                "s1_arrival_entities_6B",
                "f" * 64,
                {
                    "merchant_id": "m1",
                    "party_id": "p1",
                    "account_id": "a1",
                    "instrument_id": "i1",
                    "device_id": "d1",
                    "ip_id": "ip1",
                    "session_id": "s1",
                },
                "2026-02-05T00:00:01.000000Z",
                pins,
            ),
        ),
        (
            "fp.bus.context.flow_anchor.fraud.v1",
            _envelope(
                "s3_flow_anchor_with_fraud_6B",
                "1" * 64,
                {
                    "flow_id": "flow-1",
                    "merchant_id": "m1",
                    "party_id": "p1",
                    "account_id": "a1",
                    "instrument_id": "i1",
                    "device_id": "d1",
                    "ip_id": "ip1",
                },
                "2026-02-05T00:00:02.000000Z",
                pins,
            ),
        ),
        (
            "fp.bus.traffic.fraud.v1",
            _envelope(
                "s3_event_stream_with_fraud_6B",
                "2" * 64,
                {"flow_id": "flow-1"},
                "2026-02-05T00:00:03.000000Z",
                pins,
            ),
        ),
    ]
    for topic, envelope in events:
        publisher.publish(topic, "pk", envelope)
    return events


def test_replay_determinism_same_offsets(tmp_path: Path) -> None:
    bus_root = tmp_path / "eb"
    platform_run_id = "platform_20260205T000000Z"
    events = _seed_bus(bus_root, platform_run_id=platform_run_id)
    topics = sorted({topic for topic, _ in events})

    profile_a = _write_profile(
        tmp_path,
        bus_root=bus_root,
        projection_db=tmp_path / "ieg_a.db",
        platform_run_id=platform_run_id,
        topics=topics,
    )
    profile_b = _write_profile(
        tmp_path,
        bus_root=bus_root,
        projection_db=tmp_path / "ieg_b.db",
        platform_run_id=platform_run_id,
        topics=topics,
    )

    state_a = _run_projector(profile_a)
    state_b = _run_projector(profile_b)

    assert state_a["graph_version"] == state_b["graph_version"]
    assert state_a["run_config_digest"] == state_b["run_config_digest"]
    assert state_a["run_config_digest"]
    assert state_a["counts"] == state_b["counts"]


def test_watermark_monotonicity(tmp_path: Path) -> None:
    bus_root = tmp_path / "eb"
    publisher = FileEventBusPublisher(bus_root)
    platform_run_id = "platform_20260205T000000Z"
    pins = _base_pins(platform_run_id)
    topic = "fp.bus.context.arrival_events.v1"
    publisher.publish(
        topic,
        "pk",
        _envelope(
            "arrival_events_5B",
            "3" * 64,
            {"merchant_id": "m1"},
            "2026-02-05T00:00:02.000000Z",
            pins,
        ),
    )
    publisher.publish(
        topic,
        "pk",
        _envelope(
            "arrival_events_5B",
            "4" * 64,
            {"merchant_id": "m1"},
            "2026-02-05T00:00:01.000000Z",
            pins,
        ),
    )
    profile = _write_profile(
        tmp_path,
        bus_root=bus_root,
        projection_db=tmp_path / "ieg_watermark.db",
        platform_run_id=platform_run_id,
        topics=[topic],
    )
    state = _run_projector(profile)
    assert state["watermark"] == "2026-02-05T00:00:02.000000Z"


def test_integration_projection_from_file_bus(tmp_path: Path) -> None:
    bus_root = tmp_path / "eb"
    platform_run_id = "platform_20260205T000000Z"
    events = _seed_bus(bus_root, platform_run_id=platform_run_id)
    topics = sorted({topic for topic, _ in events})
    profile = _write_profile(
        tmp_path,
        bus_root=bus_root,
        projection_db=tmp_path / "ieg_integration.db",
        platform_run_id=platform_run_id,
        topics=topics,
    )
    state = _run_projector(profile)

    assert state["graph_version"]
    assert state["counts"]["apply_failures"] == 0
    assert state["counts"]["dedupe"] == 4
    assert state["counts"]["entities"] == 8
    assert state["counts"]["identifiers"] == 8


@pytest.mark.parametrize("event_type", ["decision_response", "action_intent", "action_outcome"])
def test_rtdl_output_families_are_irrelevant_no_apply_failure(tmp_path: Path, event_type: str) -> None:
    bus_root = tmp_path / "eb"
    publisher = FileEventBusPublisher(bus_root)
    platform_run_id = "platform_20260205T000000Z"
    pins = _base_pins(platform_run_id)
    topic = "fp.bus.traffic.fraud.v1"
    publisher.publish(
        topic,
        "pk",
        _envelope(
            event_type,
            "d" * 64,
            {"decision_id": "x" * 32},
            "2026-02-05T00:00:05.000000Z",
            pins,
        ),
    )

    profile = _write_profile(
        tmp_path,
        bus_root=bus_root,
        projection_db=tmp_path / "ieg_irrelevant.db",
        platform_run_id=platform_run_id,
        topics=[topic],
    )
    state = _run_projector(profile)

    assert state["counts"]["apply_failures"] == 0
    assert state["counts"]["dedupe"] == 0

    with sqlite3.connect(tmp_path / "ieg_irrelevant.db") as conn:
        irrelevant = conn.execute(
            "SELECT metric_value FROM ieg_metrics WHERE metric_name = 'irrelevant'"
        ).fetchone()
        checkpoint = conn.execute(
            "SELECT next_offset FROM ieg_checkpoints WHERE topic = ? AND partition_id = 0",
            (topic,),
        ).fetchone()
    assert irrelevant is not None
    assert int(irrelevant[0]) == 1
    assert checkpoint is not None
    assert str(checkpoint[0]) == "1"
