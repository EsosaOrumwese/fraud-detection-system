from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import yaml

from fraud_detection.context_store_flow_binding import (
    ContextStoreFlowBindingInlet,
    ContextStoreFlowBindingQueryService,
    CsfbInletPolicy,
    CsfbObservabilityReporter,
)
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


def _write_topics(path: Path, *, fraud_only: bool = True) -> None:
    topics = [
        "fp.bus.context.arrival_events.v1",
        "fp.bus.context.arrival_entities.v1",
        "fp.bus.context.flow_anchor.fraud.v1",
    ]
    if not fraud_only:
        topics.append("fp.bus.context.flow_anchor.baseline.v1")
    payload = {"version": "0.1.0", "topics": topics}
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_profile(
    path: Path,
    *,
    projection_dsn: str,
    event_bus_root: str,
    topics_ref: Path,
    required_platform_run_id: str,
) -> None:
    payload: dict[str, Any] = {
        "profile_id": "local_parity",
        "context_store_flow_binding": {
            "policy": {
                "stream_id": "csfb.v0",
                "class_map_ref": "config/platform/ig/class_map_v0.yaml",
                "context_event_classes": [
                    "context_arrival",
                    "context_arrival_entities",
                    "context_flow_fraud",
                ],
            },
            "wiring": {
                "projection_db_dsn": projection_dsn,
                "event_bus_kind": "file",
                "event_bus": {
                    "root": event_bus_root,
                    "topics_ref": str(topics_ref),
                    "start_position": "trim_horizon",
                },
                "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
                "required_platform_run_id": required_platform_run_id,
                "poll_max_records": 5000,
                "poll_sleep_seconds": 0.0,
            },
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _publish_context_triplets(*, publisher: FileEventBusPublisher, pins: dict[str, object], count: int) -> None:
    for seq in range(1, count + 1):
        merchant_id = f"m-{(seq % 7) + 1}"
        flow_id = f"flow-{seq}"
        ts = f"2026-02-07T05:{((seq - 1) // 60):02d}:{((seq - 1) % 60):02d}.000000Z"
        publisher.publish(
            "fp.bus.context.arrival_events.v1",
            "pk",
            _envelope(
                pins=pins,
                event_id=f"{seq:064x}",
                event_type="arrival_events_5B",
                ts_utc=ts,
                payload={"merchant_id": merchant_id, "arrival_seq": seq},
            ),
        )
        publisher.publish(
            "fp.bus.context.arrival_entities.v1",
            "pk",
            _envelope(
                pins=pins,
                event_id=f"{seq + 1_000:064x}",
                event_type="s1_arrival_entities_6B",
                ts_utc=ts,
                payload={
                    "merchant_id": merchant_id,
                    "arrival_seq": seq,
                    "party_id": f"party-{seq}",
                },
            ),
        )
        publisher.publish(
            "fp.bus.context.flow_anchor.fraud.v1",
            "pk",
            _envelope(
                pins=pins,
                event_id=f"{seq + 2_000:064x}",
                event_type="s3_flow_anchor_with_fraud_6B",
                ts_utc=ts,
                payload={"merchant_id": merchant_id, "arrival_seq": seq, "flow_id": flow_id},
            ),
        )


def test_phase7_profile_loader_supports_parity_profile_shape_and_env(monkeypatch, tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T171700Z"
    topics_ref = tmp_path / "topics.yaml"
    _write_topics(topics_ref)
    profile_path = tmp_path / "profile.yaml"
    bus_root = tmp_path / "eb"
    projection_db = tmp_path / "projection.db"

    monkeypatch.setenv("CSFB_EVENT_BUS_ROOT", str(bus_root))
    monkeypatch.setenv("CSFB_PROJECTION_DSN", str(projection_db))
    monkeypatch.setenv("CSFB_REQUIRED_PLATFORM_RUN_ID", platform_run_id)

    _write_profile(
        profile_path,
        projection_dsn="${CSFB_PROJECTION_DSN}",
        event_bus_root="${CSFB_EVENT_BUS_ROOT}",
        topics_ref=topics_ref,
        required_platform_run_id="${CSFB_REQUIRED_PLATFORM_RUN_ID}",
    )

    policy = CsfbInletPolicy.load(profile_path)
    assert policy.event_bus_kind == "file"
    assert policy.event_bus_root == str(bus_root)
    assert policy.projection_db_dsn == str(projection_db)
    assert policy.required_platform_run_id == platform_run_id
    assert policy.context_topics == (
        "fp.bus.context.arrival_events.v1",
        "fp.bus.context.arrival_entities.v1",
        "fp.bus.context.flow_anchor.fraud.v1",
    )


def test_phase7_monitored_20_event_pass_records_join_hits_and_ready_query(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T171800Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    projection_db = tmp_path / "projection.db"
    topics_ref = tmp_path / "topics.yaml"
    _write_topics(topics_ref)
    profile_path = tmp_path / "profile.yaml"
    _write_profile(
        profile_path,
        projection_dsn=str(projection_db),
        event_bus_root=str(bus_root),
        topics_ref=topics_ref,
        required_platform_run_id=platform_run_id,
    )

    publisher = FileEventBusPublisher(bus_root)
    _publish_context_triplets(publisher=publisher, pins=pins, count=20)

    inlet = ContextStoreFlowBindingInlet.build(str(profile_path))
    assert inlet.run_once() == 60

    reporter = CsfbObservabilityReporter.build(locator=projection_db, stream_id="csfb.v0")
    metrics = reporter.collect(platform_run_id=platform_run_id, scenario_run_id=str(pins["scenario_run_id"]))
    assert metrics["metrics"]["join_hits"] == 20
    assert metrics["metrics"]["join_misses"] == 0
    assert metrics["metrics"]["apply_failures"] == 0

    query = ContextStoreFlowBindingQueryService.build_from_policy(profile_path)
    response = query.query(
        {
            "request_id": "phase7-ready-query",
            "query_kind": "resolve_flow_binding",
            "flow_id": "flow-7",
            "pins": dict(pins),
        }
    )
    assert response["status"] == "READY"
    assert response["flow_binding"]["flow_id"] == "flow-7"
    assert response["join_frame_key"]["arrival_seq"] == 7


def test_phase7_monitored_200_event_pass_is_checkpoint_stable_on_repoll(tmp_path: Path) -> None:
    platform_run_id = "platform_20260207T171900Z"
    pins = _pins(platform_run_id)
    bus_root = tmp_path / "eb"
    projection_db = tmp_path / "projection.db"
    topics_ref = tmp_path / "topics.yaml"
    _write_topics(topics_ref)
    profile_path = tmp_path / "profile.yaml"
    _write_profile(
        profile_path,
        projection_dsn=str(projection_db),
        event_bus_root=str(bus_root),
        topics_ref=topics_ref,
        required_platform_run_id=platform_run_id,
    )

    publisher = FileEventBusPublisher(bus_root)
    _publish_context_triplets(publisher=publisher, pins=pins, count=200)

    inlet = ContextStoreFlowBindingInlet.build(str(profile_path))
    assert inlet.run_once() == 600

    reporter = CsfbObservabilityReporter.build(locator=projection_db, stream_id="csfb.v0")
    first = reporter.collect(platform_run_id=platform_run_id, scenario_run_id=str(pins["scenario_run_id"]))
    first_digest = str((first.get("applied_offset_basis") or {}).get("basis_digest") or "")
    assert first["metrics"]["join_hits"] == 200
    assert first["metrics"]["join_misses"] == 0

    with sqlite3.connect(projection_db) as conn:
        first_counts = {
            "frames": int(conn.execute("SELECT COUNT(*) FROM csfb_join_frames").fetchone()[0]),
            "bindings": int(conn.execute("SELECT COUNT(*) FROM csfb_flow_bindings").fetchone()[0]),
            "failures": int(conn.execute("SELECT COUNT(*) FROM csfb_join_apply_failures").fetchone()[0]),
        }

    # Re-poll with no new records: no state mutation and stable basis.
    assert inlet.run_once() == 0
    second = reporter.collect(platform_run_id=platform_run_id, scenario_run_id=str(pins["scenario_run_id"]))
    second_digest = str((second.get("applied_offset_basis") or {}).get("basis_digest") or "")
    with sqlite3.connect(projection_db) as conn:
        second_counts = {
            "frames": int(conn.execute("SELECT COUNT(*) FROM csfb_join_frames").fetchone()[0]),
            "bindings": int(conn.execute("SELECT COUNT(*) FROM csfb_flow_bindings").fetchone()[0]),
            "failures": int(conn.execute("SELECT COUNT(*) FROM csfb_join_apply_failures").fetchone()[0]),
        }

    assert first_counts == {"frames": 200, "bindings": 200, "failures": 0}
    assert second_counts == first_counts
    assert first_digest
    assert second_digest == first_digest
