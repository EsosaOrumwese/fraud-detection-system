from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from fraud_detection.ingestion_gate.config import SchemaPolicy, SchemaPolicyEntry
from fraud_detection.ingestion_gate.pg_index import PostgresAdmissionIndex, PostgresOpsIndex
from fraud_detection.ingestion_gate.schema import SchemaEnforcer


class _NoopRegistry:
    def validate(self, _name: str, _payload: dict[str, Any]) -> None:
        return None


@dataclass
class _FakeResult:
    row: tuple[Any, ...] | None = None
    rows: list[tuple[Any, ...]] | None = None
    rowcount: int = 1

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows or []


class _FakeConn:
    def __init__(self) -> None:
        self.closed = 0
        self.queries: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> _FakeResult:
        text = str(query)
        self.queries.append((text, params))
        if "SELECT state, payload_hash" in text:
            return _FakeResult(row=None)
        if "SELECT receipt_id, event_id, event_type, decision, receipt_ref" in text:
            return _FakeResult(row=None)
        if "ON CONFLICT (dedupe_key) DO NOTHING" in text:
            return _FakeResult(rowcount=1)
        return _FakeResult(rowcount=1)

    def close(self) -> None:
        self.closed = 1


def test_schema_enforcer_caches_payload_schema_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"count": 0}

    def _fake_load_schema_ref(_root: Path, _schema_ref: str):
        calls["count"] += 1
        return ({"type": "object"}, object())

    def _fake_validate_with_schema(
        _schema: dict[str, Any], _payload: dict[str, Any], *, registry: Any
    ) -> None:
        return None

    import fraud_detection.ingestion_gate.schema as schema_module

    monkeypatch.setattr(schema_module, "_load_schema_ref", _fake_load_schema_ref)
    monkeypatch.setattr(schema_module, "_validate_with_schema", _fake_validate_with_schema)

    policy = SchemaPolicy(
        default_action="quarantine",
        policies={
            "test_event": SchemaPolicyEntry(
                event_type="test_event",
                class_name="traffic",
                schema_version_required=False,
                allowed_schema_versions=None,
                payload_schema_ref="dummy.schema.yaml",
            )
        },
    )
    enforcer = SchemaEnforcer(
        envelope_registry=_NoopRegistry(),
        payload_registry_root=tmp_path,
        policy=policy,
    )

    envelope = {"schema_version": "v1", "payload": {"id": "evt-1"}}
    enforcer.validate_payload("test_event", envelope)
    enforcer.validate_payload("test_event", envelope)

    assert calls["count"] == 1


def test_postgres_admission_index_reuses_thread_local_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[_FakeConn] = []

    def _fake_connect(*_args, **_kwargs):
        conn = _FakeConn()
        created.append(conn)
        return conn

    import fraud_detection.ingestion_gate.pg_index as pg_index_module

    monkeypatch.setattr(pg_index_module.psycopg, "connect", _fake_connect)

    index = PostgresAdmissionIndex("postgresql://platform:platform@localhost:5434/platform")
    assert len(created) == 1
    index.lookup("dedupe-1")
    index.record_in_flight(
        "dedupe-1",
        platform_run_id="platform_20260210T000000Z",
        event_class="traffic",
        event_id="evt-1",
        payload_hash="a" * 64,
    )
    index.record_admitted(
        "dedupe-1",
        eb_ref={"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset": "1", "offset_kind": "kinesis_sequence"},
        admitted_at_utc="2026-02-10T00:00:00+00:00",
        payload_hash="a" * 64,
    )
    index.record_receipt("dedupe-1", "s3://fraud-platform/platform_20260210T000000Z/ig/receipts/r1.json")
    index.mark_receipt_failed("dedupe-1")
    assert index.probe() is True
    assert len(created) == 1

    # Closed connections are re-established on the next operation.
    created[0].closed = 1
    assert index.probe() is True
    assert len(created) == 2


def test_postgres_ops_index_reuses_thread_local_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[_FakeConn] = []

    def _fake_connect(*_args, **_kwargs):
        conn = _FakeConn()
        created.append(conn)
        return conn

    import fraud_detection.ingestion_gate.pg_index as pg_index_module

    monkeypatch.setattr(pg_index_module.psycopg, "connect", _fake_connect)

    index = PostgresOpsIndex("postgresql://platform:platform@localhost:5434/platform")
    assert len(created) == 1
    index.record_receipt(
        {
            "receipt_id": "r1",
            "event_id": "evt-1",
            "event_type": "s3_event_stream_with_fraud_6B",
            "dedupe_key": "d" * 64,
            "decision": "ADMIT",
            "platform_run_id": "platform_20260210T000000Z",
            "policy_rev": {"policy_id": "ig", "revision": "v0", "content_digest": "c" * 64},
            "pins": {"platform_run_id": "platform_20260210T000000Z"},
            "eb_ref": {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset": "1", "offset_kind": "kinesis_sequence"},
        },
        "s3://fraud-platform/platform_20260210T000000Z/ig/receipts/r1.json",
    )
    assert index.lookup_receipt("r1") is None
    assert index.lookup_dedupe("d" * 64) is None
    assert index.lookup_event("evt-1") is None
    assert index.probe() is True
    assert len(created) == 1

    created[0].closed = 1
    assert index.probe() is True
    assert len(created) == 2
