from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _df_envelope(*, event_id: str, ts_utc: str, event_type: str) -> dict[str, object]:
    pins = _pins()
    return {
        "event_id": event_id,
        "event_type": event_type,
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
            "decision_id": "d" * 32,
            "source_event": {"event_id": "s" * 64},
            "pins": {"scenario_run_id": pins["scenario_run_id"]},
        },
    }


def _write_bus_records(bus_root: Path, topic: str, envelopes: list[dict[str, object]]) -> None:
    topic_dir = bus_root / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    path = topic_dir / "partition=0.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for envelope in envelopes:
            handle.write(json.dumps({"envelope": envelope}, sort_keys=True, ensure_ascii=True) + "\n")


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
                    {"window": "7d", "duration": "7d", "ttl": "7d"},
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_profile(path: Path, *, bus_root: Path, db_path: Path, topics: list[str]) -> None:
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
                "projection_db_dsn": str(db_path),
                "event_bus_kind": "file",
                "required_platform_run_id": "platform_20260206T000000Z",
                "event_bus": {
                    "root": str(bus_root),
                    "topics": topics,
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
        "event_class": "traffic_fraud",
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


def test_store_semantic_dedupe_and_payload_hash_mismatch(tmp_path) -> None:
    db_path = tmp_path / "ofp.db"
    store = build_store(str(db_path), stream_id="ofp.v0", basis_stream="fp.bus.traffic.fraud.v1")
    pins = _pins()
    base = {
        "topic": "fp.bus.traffic.fraud.v1",
        "partition": 0,
        "offset_kind": "file_line",
        "event_class": "traffic_fraud",
        "event_id": "9" * 64,
        "event_ts_utc": "2026-02-06T00:00:01.000000Z",
        "pins": pins,
        "key_type": "flow_id",
        "key_id": "flow-9",
        "group_name": "core_features",
        "group_version": "v1",
        "amount": 12.0,
    }
    first = store.apply_event(offset="0", payload_hash="a" * 64, **base)
    replay = store.apply_event(offset="1", payload_hash="a" * 64, **base)
    mismatch = store.apply_event(offset="2", payload_hash="b" * 64, **base)

    state = store.get_group_state(
        platform_run_id=str(pins["platform_run_id"]),
        scenario_run_id=str(pins["scenario_run_id"]),
        key_type="flow_id",
        key_id="flow-9",
        group_name="core_features",
        group_version="v1",
    )
    metrics = store.metrics_summary(scenario_run_id=str(pins["scenario_run_id"]))

    assert first.status == "APPLIED"
    assert replay.status == "DUPLICATE"
    assert mismatch.status == "PAYLOAD_HASH_MISMATCH"
    assert state is not None
    assert state["event_count"] == 1
    assert state["amount_sum"] == 12.0
    assert metrics.get("events_seen") == 3
    assert metrics.get("events_applied") == 1
    assert metrics.get("duplicates") == 1
    assert metrics.get("payload_hash_mismatch") == 1


def test_semantic_dedupe_is_stream_independent(tmp_path) -> None:
    db_path = tmp_path / "ofp.db"
    store_a = build_store(str(db_path), stream_id="ofp.v0::a", basis_stream="fp.bus.traffic.fraud.v1")
    store_b = build_store(str(db_path), stream_id="ofp.v0::b", basis_stream="fp.bus.traffic.fraud.v1")
    pins = _pins()
    base = {
        "topic": "fp.bus.traffic.fraud.v1",
        "partition": 0,
        "offset_kind": "file_line",
        "event_class": "traffic_fraud",
        "event_id": "8" * 64,
        "event_ts_utc": "2026-02-06T00:00:01.000000Z",
        "pins": pins,
        "key_type": "flow_id",
        "key_id": "flow-8",
        "group_name": "core_features",
        "group_version": "v1",
        "amount": 8.0,
    }
    first = store_a.apply_event(offset="0", payload_hash="a" * 64, **base)
    replay_other_stream = store_b.apply_event(offset="1", payload_hash="a" * 64, **base)
    mismatch_other_stream = store_b.apply_event(offset="2", payload_hash="b" * 64, **base)

    assert first.status == "APPLIED"
    assert replay_other_stream.status == "DUPLICATE"
    assert mismatch_other_stream.status == "PAYLOAD_HASH_MISMATCH"


def test_projector_file_bus_updates_state_and_basis(tmp_path) -> None:
    topic = "fp.bus.traffic.fraud.v1"
    bus_root = tmp_path / "bus"
    db_path = tmp_path / "ofp_projection.db"
    profile_path = tmp_path / "profile.json"
    _write_profile(profile_path, bus_root=bus_root, db_path=db_path, topics=[topic])
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
    assert basis["offsets"] == [{"topic": topic, "partition": 0, "offset": "2"}]

    second_processed = projector.run_once()
    assert second_processed == 0


def test_projector_uses_runtime_observability_threshold_env_overrides(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    topic = "fp.bus.traffic.fraud.v1"
    bus_root = tmp_path / "bus"
    db_path = tmp_path / "ofp_projection.db"
    profile_path = tmp_path / "profile.json"
    _write_profile(profile_path, bus_root=bus_root, db_path=db_path, topics=[topic])
    monkeypatch.setenv("OFP_HEALTH_AMBER_WATERMARK_AGE_SECONDS", "111")
    monkeypatch.setenv("OFP_HEALTH_RED_WATERMARK_AGE_SECONDS", "222")
    monkeypatch.setenv("OFP_HEALTH_AMBER_CHECKPOINT_AGE_SECONDS", "333")
    monkeypatch.setenv("OFP_HEALTH_RED_CHECKPOINT_AGE_SECONDS", "444")

    projector = OnlineFeatureProjector.build(str(profile_path))

    assert projector._observability.thresholds.amber_watermark_age_seconds == 111.0
    assert projector._observability.thresholds.red_watermark_age_seconds == 222.0
    assert projector._observability.thresholds.amber_checkpoint_age_seconds == 333.0
    assert projector._observability.thresholds.red_checkpoint_age_seconds == 444.0


def test_projector_file_bus_supports_multiple_topics_and_topic_metrics(tmp_path) -> None:
    traffic_topic = "fp.bus.traffic.fraud.v1"
    context_topic = "fp.bus.context.arrival_events.v1"
    bus_root = tmp_path / "bus"
    db_path = tmp_path / "ofp_projection.db"
    profile_path = tmp_path / "profile.json"
    _write_profile(
        profile_path,
        bus_root=bus_root,
        db_path=db_path,
        topics=[traffic_topic, context_topic],
    )
    _write_bus_records(
        bus_root,
        traffic_topic,
        [_envelope(event_id="3" * 64, ts_utc="2026-02-06T00:00:03.000000Z", flow_id="flow-a", amount=3.0)],
    )
    _write_bus_records(
        bus_root,
        context_topic,
        [_envelope(event_id="4" * 64, ts_utc="2026-02-06T00:00:04.000000Z", flow_id="flow-b", amount=4.0)],
    )

    projector = OnlineFeatureProjector.build(str(profile_path))
    processed = projector.run_once()
    assert processed == 2

    state_a = projector.store.get_group_state(
        platform_run_id="platform_20260206T000000Z",
        scenario_run_id="a" * 32,
        key_type="flow_id",
        key_id="flow-a",
        group_name="core_features",
        group_version="v1",
    )
    state_b = projector.store.get_group_state(
        platform_run_id="platform_20260206T000000Z",
        scenario_run_id="a" * 32,
        key_type="flow_id",
        key_id="flow-b",
        group_name="core_features",
        group_version="v1",
    )
    assert state_a is not None
    assert state_b is not None
    assert state_a["event_count"] == 1
    assert state_b["event_count"] == 1

    metrics = projector.store.metrics_summary(scenario_run_id="a" * 32)
    assert metrics.get(f"events_seen|topic={traffic_topic}") == 1
    assert metrics.get(f"events_seen|topic={context_topic}") == 1
    assert metrics.get(f"events_applied|topic={traffic_topic}") == 1
    assert metrics.get(f"events_applied|topic={context_topic}") == 1

    basis = projector.store.input_basis()
    assert basis is not None
    assert basis["stream"] == "multi"
    assert {"topic": traffic_topic, "partition": 0, "offset": "1"} in basis["offsets"]
    assert {"topic": context_topic, "partition": 0, "offset": "1"} in basis["offsets"]


@pytest.mark.parametrize("event_type", ["decision_response", "action_intent", "action_outcome"])
def test_projector_ignores_rtdl_non_apply_families_on_shared_traffic_topic(tmp_path, event_type: str) -> None:
    topic = "fp.bus.traffic.fraud.v1"
    bus_root = tmp_path / "bus"
    db_path = tmp_path / "ofp_projection.db"
    profile_path = tmp_path / "profile.json"
    _write_profile(profile_path, bus_root=bus_root, db_path=db_path, topics=[topic])
    _write_bus_records(
        bus_root,
        topic,
        [_df_envelope(event_id="9" * 64, ts_utc="2026-02-06T00:00:09.000000Z", event_type=event_type)],
    )

    projector = OnlineFeatureProjector.build(str(profile_path))
    processed = projector.run_once()
    assert processed == 1

    states = projector.store.list_group_states(
        platform_run_id="platform_20260206T000000Z",
        scenario_run_id="a" * 32,
        group_name="core_features",
        group_version="v1",
    )
    assert states == []

    metrics = projector.store.metrics_summary(scenario_run_id="a" * 32)
    assert metrics.get("events_seen") == 1
    assert metrics.get("ignored_event_type") == 1
    assert metrics.get(f"ignored_event_type|topic={topic}") == 1
    assert metrics.get("events_applied") in (None, 0)

    basis = projector.store.input_basis()
    assert basis is not None
    assert basis["offsets"] == [{"topic": topic, "partition": 0, "offset": "1"}]
