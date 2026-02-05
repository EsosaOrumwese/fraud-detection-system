from __future__ import annotations

import sqlite3

from fraud_detection.identity_entity_graph.hints import IdentityHint
from fraud_detection.identity_entity_graph.ids import dedupe_key
from fraud_detection.identity_entity_graph.store import build_store


def _base_pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260205T000000Z",
        "scenario_run_id": "scnrun123",
        "scenario_id": "42",
        "run_id": "run-abc",
        "manifest_fingerprint": "f" * 64,
        "parameter_hash": "p" * 64,
        "seed": 7,
    }


def test_apply_and_duplicate(tmp_path) -> None:
    db_path = tmp_path / "ieg.db"
    store = build_store(str(db_path), stream_id="ieg.v0")
    event_id = "evt-1"
    class_name = "traffic"
    pins = _base_pins()
    pins["dedupe_key"] = dedupe_key(str(pins["scenario_run_id"]), class_name, event_id)
    hint = IdentityHint(
        identifier_type="account_id",
        identifier_value="acc-1",
        entity_type="account",
        entity_id="entity-1",
        source_event_id=event_id,
    )
    result = store.apply_mutation(
        topic="fp.bus.traffic.v1",
        partition=0,
        offset="0",
        offset_kind="file_line",
        event_id=event_id,
        event_type="s3_event_stream_with_fraud_6B",
        class_name=class_name,
        scenario_run_id=str(pins["scenario_run_id"]),
        pins=pins,
        payload_hash="hash-1",
        identity_hints=[hint],
        event_ts_utc="2026-02-05T00:00:00.000000+00:00",
    )
    assert result.status == "APPLIED"

    dup = store.apply_mutation(
        topic="fp.bus.traffic.v1",
        partition=0,
        offset="1",
        offset_kind="file_line",
        event_id=event_id,
        event_type="s3_event_stream_with_fraud_6B",
        class_name=class_name,
        scenario_run_id=str(pins["scenario_run_id"]),
        pins=pins,
        payload_hash="hash-1",
        identity_hints=[hint],
        event_ts_utc="2026-02-05T00:00:00.000000+00:00",
    )
    assert dup.status == "DUPLICATE"

    with sqlite3.connect(db_path) as conn:
        entity_count = conn.execute("SELECT COUNT(*) FROM ieg_entities").fetchone()[0]
        assert entity_count == 1


def test_payload_hash_mismatch_records_failure(tmp_path) -> None:
    db_path = tmp_path / "ieg.db"
    store = build_store(str(db_path), stream_id="ieg.v0")
    event_id = "evt-2"
    class_name = "traffic"
    pins = _base_pins()
    pins["dedupe_key"] = dedupe_key(str(pins["scenario_run_id"]), class_name, event_id)
    hint = IdentityHint(
        identifier_type="device_id",
        identifier_value="dev-1",
        entity_type="device",
        entity_id="entity-2",
        source_event_id=event_id,
    )
    store.apply_mutation(
        topic="fp.bus.traffic.v1",
        partition=0,
        offset="0",
        offset_kind="file_line",
        event_id=event_id,
        event_type="s3_event_stream_with_fraud_6B",
        class_name=class_name,
        scenario_run_id=str(pins["scenario_run_id"]),
        pins=pins,
        payload_hash="hash-2",
        identity_hints=[hint],
        event_ts_utc="2026-02-05T00:00:00.000000+00:00",
    )
    mismatch = store.apply_mutation(
        topic="fp.bus.traffic.v1",
        partition=0,
        offset="1",
        offset_kind="file_line",
        event_id=event_id,
        event_type="s3_event_stream_with_fraud_6B",
        class_name=class_name,
        scenario_run_id=str(pins["scenario_run_id"]),
        pins=pins,
        payload_hash="hash-3",
        identity_hints=[hint],
        event_ts_utc="2026-02-05T00:00:00.000000+00:00",
    )
    assert mismatch.status == "PAYLOAD_MISMATCH"

    with sqlite3.connect(db_path) as conn:
        failure_count = conn.execute("SELECT COUNT(*) FROM ieg_apply_failures").fetchone()[0]
        assert failure_count == 1


def test_graph_version_is_deterministic(tmp_path) -> None:
    db_path = tmp_path / "ieg.db"
    store = build_store(str(db_path), stream_id="ieg.v0")
    event_id = "evt-3"
    class_name = "traffic"
    pins = _base_pins()
    pins["dedupe_key"] = dedupe_key(str(pins["scenario_run_id"]), class_name, event_id)
    hint = IdentityHint(
        identifier_type="email",
        identifier_value="user@example.com",
        entity_type="account",
        entity_id="entity-3",
        source_event_id=event_id,
    )
    store.apply_mutation(
        topic="fp.bus.traffic.v1",
        partition=0,
        offset="0",
        offset_kind="file_line",
        event_id=event_id,
        event_type="s3_event_stream_with_fraud_6B",
        class_name=class_name,
        scenario_run_id=str(pins["scenario_run_id"]),
        pins=pins,
        payload_hash="hash-4",
        identity_hints=[hint],
        event_ts_utc="2026-02-05T00:00:00.000000+00:00",
    )
    with sqlite3.connect(db_path) as conn:
        graph_version = conn.execute("SELECT graph_version FROM ieg_graph_versions").fetchone()[0]
        assert graph_version
