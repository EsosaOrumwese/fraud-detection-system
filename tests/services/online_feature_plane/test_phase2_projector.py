from __future__ import annotations

import json
from pathlib import Path

from fraud_detection.online_feature_plane.projector import OnlineFeatureProjector
from fraud_detection.online_feature_plane.store import build_store


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


def _write_profile(path: Path, *, bus_root: Path, db_path: Path, topic: str) -> None:
    profile = {
        "ofp": {
            "policy": {
                "stream_id": "ofp.v0",
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
                    "topics": [topic],
                },
                "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
                "poll_max_records": 200,
                "poll_sleep_seconds": 0.01,
            },
        }
    }
    path.write_text(json.dumps(profile), encoding="utf-8")


def test_store_apply_is_idempotent_for_same_offset(tmp_path) -> None:
    db_path = tmp_path / "ofp.db"
    store = build_store(str(db_path), stream_id="ofp.v0", basis_stream="fp.bus.traffic.fraud.v1")
    pins = _pins()

    args = {
        "topic": "fp.bus.traffic.fraud.v1",
        "partition": 0,
        "offset": "0",
        "offset_kind": "file_line",
        "event_id": "e" * 64,
        "payload_hash": "f" * 64,
        "event_ts_utc": "2026-02-06T00:00:01.000000Z",
        "pins": pins,
        "key_type": "flow_id",
        "key_id": "flow-1",
        "group_name": "core_features",
        "group_version": "v1",
        "amount": 10.0,
    }
    first = store.apply_event(**args)
    second = store.apply_event(**args)
    state = store.get_group_state(
        platform_run_id=str(pins["platform_run_id"]),
        scenario_run_id=str(pins["scenario_run_id"]),
        key_type="flow_id",
        key_id="flow-1",
        group_name="core_features",
        group_version="v1",
    )
    assert first.status == "APPLIED"
    assert second.status == "DUPLICATE"
    assert state is not None
    assert state["event_count"] == 1
    assert state["amount_sum"] == 10.0


def test_projector_file_bus_updates_state_and_basis(tmp_path) -> None:
    topic = "fp.bus.traffic.fraud.v1"
    bus_root = tmp_path / "bus"
    db_path = tmp_path / "ofp_projection.db"
    profile_path = tmp_path / "profile.json"
    _write_profile(profile_path, bus_root=bus_root, db_path=db_path, topic=topic)
    _write_bus_records(
        bus_root,
        topic,
        [
            _envelope(event_id="1" * 64, ts_utc="2026-02-06T00:00:01.000000Z", flow_id="flow-1", amount=10.0),
            _envelope(event_id="2" * 64, ts_utc="2026-02-06T00:00:02.000000Z", flow_id="flow-1", amount=5.0),
        ],
    )

    projector = OnlineFeatureProjector.build(str(profile_path))
    processed = projector.run_once()
    assert processed == 2

    state = projector.store.get_group_state(
        platform_run_id="platform_20260206T000000Z",
        scenario_run_id="a" * 32,
        key_type="flow_id",
        key_id="flow-1",
        group_name="core_features",
        group_version="v1",
    )
    assert state is not None
    assert state["event_count"] == 2
    assert state["amount_sum"] == 15.0

    basis = projector.store.input_basis()
    assert basis is not None
    assert basis["stream"] == topic
    assert basis["offset_kind"] == "file_line"
    assert basis["offsets"] == [{"partition": 0, "offset": "2"}]

    second_processed = projector.run_once()
    assert second_processed == 0
