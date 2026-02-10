from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from fraud_detection.context_store_flow_binding.intake import ContextStoreFlowBindingInlet
from fraud_detection.context_store_flow_binding.replay import CsfbReplayManifest
from fraud_detection.event_bus import FileEventBusPublisher


def _pins(platform_run_id: str) -> dict[str, object]:
    return {
        "platform_run_id": platform_run_id,
        "scenario_run_id": "a" * 32,
        "scenario_id": "baseline_v1",
        "run_id": "b" * 32,
        "manifest_fingerprint": "c" * 64,
        "parameter_hash": "d" * 64,
        "seed": 7,
    }


def _envelope(
    *,
    pins: dict[str, object],
    event_id: str,
    event_type: str,
    ts_utc: str,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ts_utc": ts_utc,
        "schema_version": "v1",
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


def _write_policy(
    path: Path,
    *,
    projection_db: Path,
    bus_root: Path,
    required_platform_run_id: str,
    context_topics: list[str],
    context_event_classes: list[str],
    poll_max_records: int,
) -> None:
    repo_root = Path.cwd()
    payload = {
        "context_store_flow_binding": {
            "policy": {
                "stream_id": "csfb.v0",
                "class_map_ref": str(repo_root / "config/platform/ig/class_map_v0.yaml"),
                "context_event_classes": context_event_classes,
                "context_topics": context_topics,
            },
            "wiring": {
                "projection_db_dsn": str(projection_db),
                "event_bus_kind": "file",
                "event_bus_root": str(bus_root),
                "event_bus_stream": "auto",
                "event_bus_start_position": "trim_horizon",
                "engine_contracts_root": str(repo_root / "docs/model_spec/data-engine/interface_pack/contracts"),
                "required_platform_run_id": required_platform_run_id,
                "poll_max_records": poll_max_records,
                "poll_sleep_seconds": 0.0,
            },
        }
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _snapshot(db_path: Path) -> dict[str, object]:
    with sqlite3.connect(db_path) as conn:
        join_frames = conn.execute(
            """
            SELECT platform_run_id, scenario_run_id, merchant_id, arrival_seq, payload_hash, frame_payload_json
            FROM csfb_join_frames
            ORDER BY merchant_id, arrival_seq
            """
        ).fetchall()
        flow_bindings = conn.execute(
            """
            SELECT platform_run_id, scenario_run_id, flow_id, payload_hash, binding_payload_json
            FROM csfb_flow_bindings
            ORDER BY flow_id
            """
        ).fetchall()
        checkpoints = conn.execute(
            """
            SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc
            FROM csfb_join_checkpoints
            ORDER BY topic, partition_id
            """
        ).fetchall()
        counts = {
            "dedupe": conn.execute("SELECT COUNT(*) FROM csfb_intake_dedupe").fetchone()[0],
            "failures": conn.execute("SELECT COUNT(*) FROM csfb_join_apply_failures").fetchone()[0],
        }
    return {
        "join_frames": join_frames,
        "flow_bindings": flow_bindings,
        "checkpoints": checkpoints,
        "counts": counts,
    }


def test_phase4_restart_resumes_from_checkpoints_without_duplicate_mutation(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T010000Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    topic = "fp.bus.context.arrival_events.v1"
    publisher = FileEventBusPublisher(bus_root)
    publisher.publish(
        topic,
        "pk",
        _envelope(
            pins=pins,
            event_id="1" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T01:00:01.000000Z",
            payload={"merchant_id": "m-1", "arrival_seq": 1},
        ),
    )
    publisher.publish(
        topic,
        "pk",
        _envelope(
            pins=pins,
            event_id="2" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T01:00:02.000000Z",
            payload={"merchant_id": "m-1", "arrival_seq": 2},
        ),
    )
    publisher.publish(
        topic,
        "pk",
        _envelope(
            pins=pins,
            event_id="3" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T01:00:03.000000Z",
            payload={"merchant_id": "m-1", "arrival_seq": 3},
        ),
    )

    db_restart = tmp_path / "csfb_restart.sqlite"
    policy_restart = tmp_path / "policy_restart.yaml"
    _write_policy(
        policy_restart,
        projection_db=db_restart,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[topic],
        context_event_classes=["context_arrival"],
        poll_max_records=1,
    )

    inlet_first = ContextStoreFlowBindingInlet.build(str(policy_restart))
    assert inlet_first.run_once() == 1

    inlet_resume = ContextStoreFlowBindingInlet.build(str(policy_restart))
    safety = 0
    while True:
        processed = inlet_resume.run_once()
        safety += 1
        if processed == 0:
            break
        assert safety < 10

    restart_snapshot = _snapshot(db_restart)

    db_reference = tmp_path / "csfb_reference.sqlite"
    policy_reference = tmp_path / "policy_reference.yaml"
    _write_policy(
        policy_reference,
        projection_db=db_reference,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[topic],
        context_event_classes=["context_arrival"],
        poll_max_records=200,
    )
    inlet_reference = ContextStoreFlowBindingInlet.build(str(policy_reference))
    assert inlet_reference.run_once() == 3
    assert inlet_reference.run_once() == 0

    reference_snapshot = _snapshot(db_reference)
    assert restart_snapshot == reference_snapshot
    assert restart_snapshot["counts"]["dedupe"] == 3
    assert restart_snapshot["counts"]["failures"] == 0


def test_phase4_replay_same_basis_yields_identical_state(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T011000Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    arrival_topic = "fp.bus.context.arrival_events.v1"
    anchor_topic = "fp.bus.context.flow_anchor.baseline.v1"
    publisher = FileEventBusPublisher(bus_root)
    publisher.publish(
        arrival_topic,
        "pk",
        _envelope(
            pins=pins,
            event_id="4" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T01:10:01.000000Z",
            payload={"merchant_id": "m-7", "arrival_seq": 1},
        ),
    )
    publisher.publish(
        anchor_topic,
        "pk",
        _envelope(
            pins=pins,
            event_id="5" * 64,
            event_type="s2_flow_anchor_baseline_6B",
            ts_utc="2026-02-07T01:10:02.000000Z",
            payload={"merchant_id": "m-7", "arrival_seq": 1, "flow_id": "flow-7"},
        ),
    )

    manifest = CsfbReplayManifest.from_payload(
        {
            "pins": {"platform_run_id": platform_run_id},
            "topics": [
                {
                    "topic": arrival_topic,
                    "partitions": [{"partition": 0, "from_offset": "0", "to_offset": "0", "offset_kind": "file_line"}],
                },
                {
                    "topic": anchor_topic,
                    "partitions": [{"partition": 0, "from_offset": "0", "to_offset": "0", "offset_kind": "file_line"}],
                },
            ],
        }
    )

    db_a = tmp_path / "csfb_a.sqlite"
    policy_a = tmp_path / "policy_a.yaml"
    _write_policy(
        policy_a,
        projection_db=db_a,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[arrival_topic, anchor_topic],
        context_event_classes=["context_arrival", "context_flow_baseline"],
        poll_max_records=200,
    )
    inlet_a = ContextStoreFlowBindingInlet.build(str(policy_a))
    assert inlet_a.run_replay_once(manifest) == 2

    db_b = tmp_path / "csfb_b.sqlite"
    policy_b = tmp_path / "policy_b.yaml"
    _write_policy(
        policy_b,
        projection_db=db_b,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[arrival_topic, anchor_topic],
        context_event_classes=["context_arrival", "context_flow_baseline"],
        poll_max_records=200,
    )
    inlet_b = ContextStoreFlowBindingInlet.build(str(policy_b))
    assert inlet_b.run_replay_once(manifest) == 2

    assert _snapshot(db_a) == _snapshot(db_b)


def test_phase4_replay_manifest_requires_explicit_offset_basis() -> None:
    with pytest.raises(ValueError):
        CsfbReplayManifest.from_payload(
            {
                "topics": [
                    {
                        "topic": "fp.bus.context.arrival_events.v1",
                        "partitions": [{"partition": 0}],
                    }
                ]
            }
        )


def test_phase4_replay_pin_mismatch_is_fail_closed_and_checkpoint_advances(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T012000Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    topic = "fp.bus.context.arrival_events.v1"
    publisher = FileEventBusPublisher(bus_root)
    publisher.publish(
        topic,
        "pk",
        _envelope(
            pins=pins,
            event_id="6" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T01:20:01.000000Z",
            payload={"merchant_id": "m-8", "arrival_seq": 1},
        ),
    )

    db_path = tmp_path / "csfb.sqlite"
    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        projection_db=db_path,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[topic],
        context_event_classes=["context_arrival"],
        poll_max_records=200,
    )
    inlet = ContextStoreFlowBindingInlet.build(str(policy_path))
    manifest = CsfbReplayManifest.from_payload(
        {
            "pins": {"platform_run_id": "platform_20260207T999999Z"},
            "topics": [
                {"topic": topic, "partitions": [{"partition": 0, "from_offset": "0", "to_offset": "0"}]}
            ],
        }
    )
    assert inlet.run_replay_once(manifest) == 1

    with sqlite3.connect(db_path) as conn:
        join_count = conn.execute("SELECT COUNT(*) FROM csfb_join_frames").fetchone()[0]
        reason = conn.execute("SELECT reason_code, details_json FROM csfb_join_apply_failures").fetchone()
        checkpoint = conn.execute(
            "SELECT next_offset FROM csfb_join_checkpoints WHERE topic = ? AND partition_id = 0",
            (topic,),
        ).fetchone()
    assert join_count == 0
    assert reason is not None
    assert str(reason[0]) == "REPLAY_PINS_MISMATCH"
    details = json.loads(str(reason[1]))
    assert "platform_run_id" in details.get("mismatches", {})
    assert checkpoint is not None
    assert str(checkpoint[0]) == "1"
