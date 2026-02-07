from __future__ import annotations

import sqlite3
from pathlib import Path

import yaml

from fraud_detection.event_bus import FileEventBusPublisher
from fraud_detection.context_store_flow_binding.intake import ContextStoreFlowBindingInlet


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
                "poll_max_records": 200,
                "poll_sleep_seconds": 0.0,
            },
        }
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_phase3_context_apply_and_authoritative_binding(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T000000Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    db_path = tmp_path / "csfb.sqlite"
    topic_arrival = "fp.bus.context.arrival_events.v1"
    topic_anchor = "fp.bus.context.flow_anchor.baseline.v1"
    publisher = FileEventBusPublisher(bus_root)
    publisher.publish(
        topic_arrival,
        "pk",
        _envelope(
            pins=pins,
            event_id="1" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T00:00:01.000000Z",
            payload={"merchant_id": "m-1", "arrival_seq": 1},
        ),
    )
    publisher.publish(
        topic_anchor,
        "pk",
        _envelope(
            pins=pins,
            event_id="2" * 64,
            event_type="s2_flow_anchor_baseline_6B",
            ts_utc="2026-02-07T00:00:02.000000Z",
            payload={"merchant_id": "m-1", "arrival_seq": 1, "flow_id": "flow-1"},
        ),
    )

    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        projection_db=db_path,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[topic_arrival, topic_anchor],
        context_event_classes=["context_arrival", "context_flow_baseline"],
    )

    inlet = ContextStoreFlowBindingInlet.build(str(policy_path))
    assert inlet.run_once() == 2

    with sqlite3.connect(db_path) as conn:
        join_frame = conn.execute(
            "SELECT frame_payload_json FROM csfb_join_frames WHERE merchant_id = ? AND arrival_seq = ?",
            ("m-1", 1),
        ).fetchone()
        flow_binding = conn.execute(
            "SELECT flow_id, authoritative_source_event_type FROM csfb_flow_bindings"
        ).fetchone()
        checkpoints = conn.execute(
            "SELECT topic, next_offset FROM csfb_join_checkpoints ORDER BY topic ASC"
        ).fetchall()

    assert join_frame is not None
    assert '"context_complete":true' in str(join_frame[0])
    assert '"flow_id":"flow-1"' in str(join_frame[0])
    assert flow_binding is not None
    assert flow_binding[0] == "flow-1"
    assert flow_binding[1] == "s2_flow_anchor_baseline_6B"
    assert checkpoints == [
        (topic_arrival, "1"),
        (topic_anchor, "1"),
    ]


def test_phase3_dedupe_duplicate_advances_checkpoint_no_extra_mutation(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T000100Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    db_path = tmp_path / "csfb.sqlite"
    topic_arrival = "fp.bus.context.arrival_events.v1"
    publisher = FileEventBusPublisher(bus_root)
    event = _envelope(
        pins=pins,
        event_id="3" * 64,
        event_type="arrival_events_5B",
        ts_utc="2026-02-07T00:01:01.000000Z",
        payload={"merchant_id": "m-2", "arrival_seq": 5},
    )
    publisher.publish(topic_arrival, "pk", event)
    publisher.publish(topic_arrival, "pk", event)

    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        projection_db=db_path,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[topic_arrival],
        context_event_classes=["context_arrival"],
    )

    inlet = ContextStoreFlowBindingInlet.build(str(policy_path))
    assert inlet.run_once() == 2

    with sqlite3.connect(db_path) as conn:
        dedupe_count = conn.execute("SELECT COUNT(*) FROM csfb_intake_dedupe").fetchone()[0]
        join_frame_count = conn.execute("SELECT COUNT(*) FROM csfb_join_frames").fetchone()[0]
        failure_count = conn.execute("SELECT COUNT(*) FROM csfb_join_apply_failures").fetchone()[0]
        checkpoint = conn.execute(
            "SELECT next_offset FROM csfb_join_checkpoints WHERE topic = ? AND partition_id = 0",
            (topic_arrival,),
        ).fetchone()

    assert dedupe_count == 1
    assert join_frame_count == 1
    assert failure_count == 0
    assert checkpoint is not None
    assert str(checkpoint[0]) == "2"


def test_phase3_payload_hash_mismatch_records_failure_and_advances_checkpoint(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T000200Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    db_path = tmp_path / "csfb.sqlite"
    topic_arrival = "fp.bus.context.arrival_events.v1"
    publisher = FileEventBusPublisher(bus_root)
    publisher.publish(
        topic_arrival,
        "pk",
        _envelope(
            pins=pins,
            event_id="4" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T00:02:01.000000Z",
            payload={"merchant_id": "m-3", "arrival_seq": 9},
        ),
    )
    publisher.publish(
        topic_arrival,
        "pk",
        _envelope(
            pins=pins,
            event_id="4" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T00:02:02.000000Z",
            payload={"merchant_id": "m-3", "arrival_seq": 9, "mutated": True},
        ),
    )

    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        projection_db=db_path,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[topic_arrival],
        context_event_classes=["context_arrival"],
    )

    inlet = ContextStoreFlowBindingInlet.build(str(policy_path))
    assert inlet.run_once() == 2

    with sqlite3.connect(db_path) as conn:
        reason = conn.execute(
            "SELECT reason_code FROM csfb_join_apply_failures ORDER BY recorded_at_utc DESC LIMIT 1"
        ).fetchone()
        checkpoint = conn.execute(
            "SELECT next_offset FROM csfb_join_checkpoints WHERE topic = ? AND partition_id = 0",
            (topic_arrival,),
        ).fetchone()
        join_frame_count = conn.execute("SELECT COUNT(*) FROM csfb_join_frames").fetchone()[0]

    assert reason is not None
    assert str(reason[0]) == "INTAKE_PAYLOAD_HASH_MISMATCH"
    assert checkpoint is not None
    assert str(checkpoint[0]) == "2"
    assert join_frame_count == 1


def test_phase3_missing_and_late_context_are_machine_readable(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T000300Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    db_path = tmp_path / "csfb.sqlite"
    topic_arrival = "fp.bus.context.arrival_events.v1"
    publisher = FileEventBusPublisher(bus_root)
    publisher.publish(
        topic_arrival,
        "pk",
        _envelope(
            pins=pins,
            event_id="5" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T00:03:02.000000Z",
            payload={"merchant_id": "m-4", "arrival_seq": 1},
        ),
    )
    publisher.publish(
        topic_arrival,
        "pk",
        _envelope(
            pins=pins,
            event_id="6" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T00:03:01.000000Z",
            payload={"merchant_id": "m-4", "arrival_seq": 2},
        ),
    )
    publisher.publish(
        topic_arrival,
        "pk",
        _envelope(
            pins=pins,
            event_id="7" * 64,
            event_type="arrival_events_5B",
            ts_utc="2026-02-07T00:03:03.000000Z",
            payload={"merchant_id": "m-4"},
        ),
    )

    policy_path = tmp_path / "policy.yaml"
    _write_policy(
        policy_path,
        projection_db=db_path,
        bus_root=bus_root,
        required_platform_run_id=platform_run_id,
        context_topics=[topic_arrival],
        context_event_classes=["context_arrival"],
    )

    inlet = ContextStoreFlowBindingInlet.build(str(policy_path))
    assert inlet.run_once() == 3

    with sqlite3.connect(db_path) as conn:
        reasons = {
            str(row[0])
            for row in conn.execute(
                "SELECT reason_code FROM csfb_join_apply_failures"
            ).fetchall()
        }
        checkpoint = conn.execute(
            "SELECT next_offset FROM csfb_join_checkpoints WHERE topic = ? AND partition_id = 0",
            (topic_arrival,),
        ).fetchone()

    assert "LATE_CONTEXT_EVENT" in reasons
    assert "JOIN_KEY_MISSING" in reasons
    assert checkpoint is not None
    assert str(checkpoint[0]) == "3"
