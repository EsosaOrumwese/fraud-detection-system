from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Iterator
import uuid

import psycopg
from psycopg import sql
import pytest

from fraud_detection.ingestion_gate.pg_index import PostgresOpsIndex

pytestmark = pytest.mark.parity


def _base_dsn() -> str:
    return (
        os.getenv("IG_TEST_PG_DSN")
        or os.getenv("PARITY_IG_ADMISSION_DSN")
        or os.getenv("SR_TEST_PG_DSN")
        or "postgresql://platform:platform@localhost:5434/platform"
    )


def _schema_scoped_dsn(base_dsn: str, schema: str) -> str:
    return psycopg.conninfo.make_conninfo(base_dsn, options=f"-c search_path={schema}")


@contextmanager
def _temp_schema_dsn() -> Iterator[str]:
    base_dsn = _base_dsn()
    schema = f"ig_ops_idx_{uuid.uuid4().hex[:12]}"
    try:
        with psycopg.connect(base_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    except Exception as exc:
        pytest.skip(f"Postgres unavailable for parity test: {exc}")
    dsn = _schema_scoped_dsn(base_dsn, schema)
    try:
        yield dsn
    finally:
        with psycopg.connect(base_dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


def _receipt(*, receipt_id: str, platform_run_id: str, event_id: str) -> dict[str, object]:
    return {
        "receipt_id": receipt_id,
        "event_id": event_id,
        "event_type": "s3_event_stream_with_fraud_6B",
        "event_class": "traffic",
        "dedupe_key": "k" * 64,
        "decision": "ADMIT",
        "platform_run_id": platform_run_id,
        "scenario_run_id": "scenario_x",
        "run_config_digest": "d" * 64,
        "policy_rev": {"policy_id": "ig", "revision": "v1", "content_digest": "d" * 64},
        "pins": {
            "manifest_fingerprint": "m" * 64,
            "platform_run_id": platform_run_id,
            "scenario_run_id": "scenario_x",
        },
        "eb_ref": {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset": "1", "offset_kind": "kinesis_sequence"},
    }


def test_postgres_ops_index_accepts_same_receipt_id_across_platform_runs() -> None:
    with _temp_schema_dsn() as dsn:
        index = PostgresOpsIndex(dsn)
        shared = "a" * 32
        index.record_receipt(
            _receipt(receipt_id=shared, platform_run_id="platform_20260101T000000Z", event_id="evt-1"),
            "s3://fraud-platform/platform_20260101T000000Z/ig/receipts/r1.json",
        )
        index.record_receipt(
            _receipt(receipt_id=shared, platform_run_id="platform_20260102T000000Z", event_id="evt-2"),
            "s3://fraud-platform/platform_20260102T000000Z/ig/receipts/r1.json",
        )

        with psycopg.connect(dsn) as conn:
            rows = conn.execute(
                """
                SELECT platform_run_id, receipt_id
                FROM receipts
                WHERE receipt_id = %s
                ORDER BY platform_run_id
                """,
                (shared,),
            ).fetchall()
        assert rows == [
            ("platform_20260101T000000Z", shared),
            ("platform_20260102T000000Z", shared),
        ]


def test_postgres_ops_index_migrates_legacy_receipt_pk() -> None:
    with _temp_schema_dsn() as dsn:
        shared = "b" * 32
        with psycopg.connect(dsn) as conn:
            conn.execute(
                """
                CREATE TABLE receipts (
                    receipt_id TEXT PRIMARY KEY,
                    event_id TEXT,
                    event_type TEXT,
                    dedupe_key TEXT,
                    decision TEXT,
                    eb_topic TEXT,
                    eb_partition INTEGER,
                    eb_offset TEXT,
                    eb_offset_kind TEXT,
                    policy_id TEXT,
                    policy_revision TEXT,
                    policy_digest TEXT,
                    created_at_utc TEXT,
                    receipt_ref TEXT,
                    pins_json TEXT,
                    reason_codes_json TEXT,
                    evidence_refs_json TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO receipts (
                    receipt_id, event_id, event_type, dedupe_key, decision, eb_topic, eb_partition,
                    eb_offset, eb_offset_kind, policy_id, policy_revision, policy_digest, created_at_utc,
                    receipt_ref, pins_json, reason_codes_json, evidence_refs_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    shared,
                    "evt-legacy",
                    "s3_event_stream_with_fraud_6B",
                    "x" * 64,
                    "ADMIT",
                    "fp.bus.traffic.fraud.v1",
                    0,
                    "1",
                    "kinesis_sequence",
                    "ig",
                    "v1",
                    "d" * 64,
                    "2026-01-01T00:00:00+00:00",
                    "s3://fraud-platform/platform_20260101T000000Z/ig/receipts/r1.json",
                    json.dumps({"platform_run_id": "platform_20260101T000000Z"}, ensure_ascii=True),
                    "[]",
                    "[]",
                ),
            )

        index = PostgresOpsIndex(dsn)
        index.record_receipt(
            _receipt(receipt_id=shared, platform_run_id="platform_20260102T000000Z", event_id="evt-2"),
            "s3://fraud-platform/platform_20260102T000000Z/ig/receipts/r1.json",
        )

        with psycopg.connect(dsn) as conn:
            rows = conn.execute(
                """
                SELECT platform_run_id, receipt_id
                FROM receipts
                WHERE receipt_id = %s
                ORDER BY platform_run_id
                """,
                (shared,),
            ).fetchall()
            constraint_rows = conn.execute(
                """
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE con.contype = 'p'
                  AND rel.relname = 'receipts'
                  AND nsp.nspname = current_schema()
                """
            ).fetchall()

        assert rows == [
            ("platform_20260101T000000Z", shared),
            ("platform_20260102T000000Z", shared),
        ]
        assert constraint_rows == []
