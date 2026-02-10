from __future__ import annotations

from fraud_detection.identity_entity_graph import query as query_module
from fraud_detection.identity_entity_graph.hints import IdentityHint
from fraud_detection.identity_entity_graph.ids import dedupe_key
from fraud_detection.identity_entity_graph.query import IdentityGraphQuery
from fraud_detection.identity_entity_graph.store import build_store


def _pins() -> dict[str, object]:
    return {
        "platform_run_id": "platform_20260205T000000Z",
        "scenario_run_id": "scnrun123",
        "scenario_id": "42",
        "run_id": "run-abc",
        "manifest_fingerprint": "f" * 64,
        "parameter_hash": "p" * 64,
        "seed": "7",
    }


def _apply_event(store, pins: dict[str, object], *, event_id: str, entity_id: str) -> None:
    class_name = "traffic"
    pins["dedupe_key"] = dedupe_key(str(pins["platform_run_id"]), class_name, event_id)
    hint = IdentityHint(
        identifier_type="account_id",
        identifier_value="acc-1",
        entity_type="account",
        entity_id=entity_id,
        source_event_id=event_id,
    )
    store.apply_mutation(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset=event_id,
        offset_kind="file_line",
        event_id=event_id,
        event_type="s3_event_stream_with_fraud_6B",
        class_name=class_name,
        platform_run_id=str(pins["platform_run_id"]),
        scenario_run_id=str(pins["scenario_run_id"]),
        pins=pins,
        payload_hash=f"hash-{event_id}",
        identity_hints=[hint],
        event_ts_utc="2026-02-05T00:00:00.000000+00:00",
    )


def test_resolve_identity_conflict_and_order(tmp_path) -> None:
    db_path = tmp_path / "ieg.db"
    store = build_store(str(db_path), stream_id="ieg.v0")
    pins = _pins()
    _apply_event(store, pins, event_id="evt-1", entity_id="entity-1")
    _apply_event(store, pins, event_id="evt-2", entity_id="entity-2")

    query = IdentityGraphQuery(store, "ieg.v0")
    result = query.resolve_identity(
        pins=_pins(),
        identifier_type="account_id",
        identifier_value="acc-1",
        limit=10,
    )
    candidates = result["identifier"]["candidates"]
    assert [item["entity_id"] for item in candidates] == ["entity-1", "entity-2"]
    assert result["identifier"]["conflict"] is True


def test_neighbors_shared_identifier(tmp_path) -> None:
    db_path = tmp_path / "ieg.db"
    store = build_store(str(db_path), stream_id="ieg.v0")
    pins = _pins()
    _apply_event(store, pins, event_id="evt-1", entity_id="entity-1")
    _apply_event(store, pins, event_id="evt-2", entity_id="entity-2")

    query = IdentityGraphQuery(store, "ieg.v0")
    result = query.get_neighbors(
        pins=_pins(),
        entity_id="entity-1",
        entity_type="account",
        limit=10,
    )
    neighbors = result["neighbors"]
    assert len(neighbors) == 1
    assert neighbors[0]["entity_id"] == "entity-2"
    assert neighbors[0]["shared_identifiers"][0]["identifier_value"] == "acc-1"


def test_integrity_status_degraded_on_failure(tmp_path) -> None:
    db_path = tmp_path / "ieg.db"
    store = build_store(str(db_path), stream_id="ieg.v0")
    pins = _pins()
    store.record_failure(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="0",
        offset_kind="file_line",
        event_id="evt-9",
        event_type="s3_event_stream_with_fraud_6B",
        platform_run_id=str(pins["platform_run_id"]),
        scenario_run_id=str(pins["scenario_run_id"]),
        reason_code="IDENTITY_HINTS_MISSING",
        details=None,
        event_ts_utc="2026-02-05T00:00:00.000000+00:00",
    )
    query = IdentityGraphQuery(store, "ieg.v0")
    result = query.resolve_identity(
        pins=_pins(),
        identifier_type="account_id",
        identifier_value="acc-1",
        limit=10,
    )
    assert result["integrity_status"] == "DEGRADED"


def test_health_thresholds_support_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("IEG_HEALTH_AMBER_WATERMARK_AGE_SECONDS", "10")
    monkeypatch.setenv("IEG_HEALTH_RED_WATERMARK_AGE_SECONDS", "20")

    health = query_module._derive_health(
        failure_count=0,
        watermark_age_seconds=15.0,
        checkpoint_age_seconds=0.0,
    )
    assert health["state"] == "AMBER"
    assert "WATERMARK_LAGGING" in health["reasons"]
