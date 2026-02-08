"""CSFB schema migrations for SQLite/Postgres stores (Phase 2)."""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Iterable

import psycopg


def apply_sqlite_migrations(conn: sqlite3.Connection) -> None:
    _ensure_migrations_table_sqlite(conn)
    current = _sqlite_schema_version(conn)
    for version in _migration_versions():
        if version <= current:
            continue
        if version == 1:
            _sqlite_migration_v1(conn)
        elif version == 2:
            _sqlite_migration_v2(conn)
        _record_sqlite_migration(conn, version)


def apply_postgres_migrations(conn: psycopg.Connection) -> None:
    _ensure_migrations_table_postgres(conn)
    current = _postgres_schema_version(conn)
    for version in _migration_versions():
        if version <= current:
            continue
        if version == 1:
            _postgres_migration_v1(conn)
        elif version == 2:
            _postgres_migration_v2(conn)
        _record_postgres_migration(conn, version)


def _migration_versions() -> Iterable[int]:
    return (1, 2)


def _ensure_migrations_table_sqlite(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc TEXT NOT NULL
        )
        """
    )


def _ensure_migrations_table_postgres(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc TEXT NOT NULL
        )
        """
    )


def _sqlite_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM csfb_schema_migrations").fetchone()
    if not row or row[0] is None:
        return 0
    return int(row[0])


def _postgres_schema_version(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM csfb_schema_migrations").fetchone()
    if not row or row[0] is None:
        return 0
    return int(row[0])


def _record_sqlite_migration(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO csfb_schema_migrations(version, applied_at_utc) VALUES (?, ?)",
        (version, _utc_now()),
    )


def _record_postgres_migration(conn: psycopg.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO csfb_schema_migrations(version, applied_at_utc) VALUES (%s, %s)",
        (version, _utc_now()),
    )


def _sqlite_migration_v1(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_join_frames (
            stream_id TEXT NOT NULL,
            platform_run_id TEXT NOT NULL,
            scenario_run_id TEXT NOT NULL,
            merchant_id TEXT NOT NULL,
            arrival_seq INTEGER NOT NULL,
            run_id TEXT,
            payload_hash TEXT NOT NULL,
            frame_payload_json TEXT NOT NULL,
            source_event_json TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            source_event_type TEXT NOT NULL,
            source_topic TEXT NOT NULL,
            source_partition INTEGER NOT NULL,
            source_offset TEXT NOT NULL,
            source_offset_kind TEXT NOT NULL,
            source_ts_utc TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, platform_run_id, scenario_run_id, merchant_id, arrival_seq)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_flow_bindings (
            stream_id TEXT NOT NULL,
            platform_run_id TEXT NOT NULL,
            scenario_run_id TEXT NOT NULL,
            flow_id TEXT NOT NULL,
            merchant_id TEXT NOT NULL,
            arrival_seq INTEGER NOT NULL,
            run_id TEXT,
            authoritative_source_event_type TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            binding_payload_json TEXT NOT NULL,
            source_event_json TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            source_event_type TEXT NOT NULL,
            source_topic TEXT NOT NULL,
            source_partition INTEGER NOT NULL,
            source_offset TEXT NOT NULL,
            source_offset_kind TEXT NOT NULL,
            source_ts_utc TEXT NOT NULL,
            bound_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, platform_run_id, scenario_run_id, flow_id),
            UNIQUE (stream_id, platform_run_id, scenario_run_id, merchant_id, arrival_seq)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_join_apply_failures (
            failure_id TEXT PRIMARY KEY,
            stream_id TEXT NOT NULL,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            topic TEXT,
            partition_id INTEGER,
            "offset" TEXT,
            offset_kind TEXT,
            event_id TEXT,
            event_type TEXT,
            reason_code TEXT NOT NULL,
            details_json TEXT,
            recorded_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_join_checkpoints (
            stream_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            partition_id INTEGER NOT NULL,
            next_offset TEXT NOT NULL,
            offset_kind TEXT NOT NULL,
            watermark_ts_utc TEXT,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, topic, partition_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_join_frames_scope
        ON csfb_join_frames(stream_id, platform_run_id, scenario_run_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_flow_bindings_scope
        ON csfb_flow_bindings(stream_id, platform_run_id, scenario_run_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_apply_failures_scope
        ON csfb_join_apply_failures(stream_id, platform_run_id, scenario_run_id)
        """
    )


def _postgres_migration_v1(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_join_frames (
            stream_id TEXT NOT NULL,
            platform_run_id TEXT NOT NULL,
            scenario_run_id TEXT NOT NULL,
            merchant_id TEXT NOT NULL,
            arrival_seq BIGINT NOT NULL,
            run_id TEXT,
            payload_hash TEXT NOT NULL,
            frame_payload_json TEXT NOT NULL,
            source_event_json TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            source_event_type TEXT NOT NULL,
            source_topic TEXT NOT NULL,
            source_partition INTEGER NOT NULL,
            source_offset TEXT NOT NULL,
            source_offset_kind TEXT NOT NULL,
            source_ts_utc TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, platform_run_id, scenario_run_id, merchant_id, arrival_seq)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_flow_bindings (
            stream_id TEXT NOT NULL,
            platform_run_id TEXT NOT NULL,
            scenario_run_id TEXT NOT NULL,
            flow_id TEXT NOT NULL,
            merchant_id TEXT NOT NULL,
            arrival_seq BIGINT NOT NULL,
            run_id TEXT,
            authoritative_source_event_type TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            binding_payload_json TEXT NOT NULL,
            source_event_json TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            source_event_type TEXT NOT NULL,
            source_topic TEXT NOT NULL,
            source_partition INTEGER NOT NULL,
            source_offset TEXT NOT NULL,
            source_offset_kind TEXT NOT NULL,
            source_ts_utc TEXT NOT NULL,
            bound_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, platform_run_id, scenario_run_id, flow_id),
            UNIQUE (stream_id, platform_run_id, scenario_run_id, merchant_id, arrival_seq)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_join_apply_failures (
            failure_id TEXT PRIMARY KEY,
            stream_id TEXT NOT NULL,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            topic TEXT,
            partition_id INTEGER,
            "offset" TEXT,
            offset_kind TEXT,
            event_id TEXT,
            event_type TEXT,
            reason_code TEXT NOT NULL,
            details_json TEXT,
            recorded_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_join_checkpoints (
            stream_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            partition_id INTEGER NOT NULL,
            next_offset TEXT NOT NULL,
            offset_kind TEXT NOT NULL,
            watermark_ts_utc TEXT,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, topic, partition_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_join_frames_scope
        ON csfb_join_frames(stream_id, platform_run_id, scenario_run_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_flow_bindings_scope
        ON csfb_flow_bindings(stream_id, platform_run_id, scenario_run_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_apply_failures_scope
        ON csfb_join_apply_failures(stream_id, platform_run_id, scenario_run_id)
        """
    )


def _sqlite_migration_v2(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_intake_dedupe (
            stream_id TEXT NOT NULL,
            platform_run_id TEXT NOT NULL,
            event_class TEXT NOT NULL,
            event_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            first_topic TEXT NOT NULL,
            first_partition INTEGER NOT NULL,
            first_offset TEXT NOT NULL,
            offset_kind TEXT NOT NULL,
            first_seen_ts_utc TEXT,
            created_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, platform_run_id, event_class, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_dedupe_scope
        ON csfb_intake_dedupe(stream_id, platform_run_id, event_class)
        """
    )


def _postgres_migration_v2(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS csfb_intake_dedupe (
            stream_id TEXT NOT NULL,
            platform_run_id TEXT NOT NULL,
            event_class TEXT NOT NULL,
            event_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            first_topic TEXT NOT NULL,
            first_partition INTEGER NOT NULL,
            first_offset TEXT NOT NULL,
            offset_kind TEXT NOT NULL,
            first_seen_ts_utc TEXT,
            created_at_utc TEXT NOT NULL,
            PRIMARY KEY (stream_id, platform_run_id, event_class, event_id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_csfb_dedupe_scope
        ON csfb_intake_dedupe(stream_id, platform_run_id, event_class)
        """
    )


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

