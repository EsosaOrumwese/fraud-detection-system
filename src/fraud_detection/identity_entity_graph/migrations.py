"""IEG schema migrations for SQLite/Postgres projection stores."""

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
        CREATE TABLE IF NOT EXISTS ieg_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc TEXT NOT NULL
        )
        """
    )


def _ensure_migrations_table_postgres(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc TEXT NOT NULL
        )
        """
    )


def _sqlite_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM ieg_schema_migrations").fetchone()
    if not row or row[0] is None:
        return 0
    return int(row[0])


def _postgres_schema_version(conn: psycopg.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM ieg_schema_migrations").fetchone()
    if not row or row[0] is None:
        return 0
    return int(row[0])


def _record_sqlite_migration(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO ieg_schema_migrations(version, applied_at_utc) VALUES (?, ?)",
        (version, _utc_now()),
    )


def _record_postgres_migration(conn: psycopg.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO ieg_schema_migrations(version, applied_at_utc) VALUES (%s, %s)",
        (version, _utc_now()),
    )


def _sqlite_migration_v1(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_dedupe (
            dedupe_key TEXT PRIMARY KEY,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            class_name TEXT,
            topic TEXT,
            event_id TEXT,
            payload_hash TEXT,
            first_offset TEXT,
            offset_kind TEXT,
            first_seen_ts_utc TEXT,
            created_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_apply_failures (
            failure_id TEXT PRIMARY KEY,
            stream_id TEXT,
            topic TEXT,
            partition_id INTEGER,
            offset TEXT,
            offset_kind TEXT,
            event_id TEXT,
            event_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            reason_code TEXT,
            details_json TEXT,
            ts_utc TEXT,
            recorded_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_entities (
            entity_id TEXT,
            entity_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            scenario_id TEXT,
            run_id TEXT,
            manifest_fingerprint TEXT,
            parameter_hash TEXT,
            seed TEXT,
            first_seen_ts_utc TEXT,
            last_seen_ts_utc TEXT,
            PRIMARY KEY (entity_id, scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_identifiers (
            identifier_type TEXT,
            identifier_value TEXT,
            entity_id TEXT,
            entity_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            scenario_id TEXT,
            run_id TEXT,
            manifest_fingerprint TEXT,
            parameter_hash TEXT,
            seed TEXT,
            first_seen_ts_utc TEXT,
            last_seen_ts_utc TEXT,
            source_event_id TEXT,
            PRIMARY KEY (
                identifier_type, identifier_value, entity_id,
                scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed
            )
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_edges (
            src_entity_id TEXT,
            dst_entity_id TEXT,
            edge_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            scenario_id TEXT,
            run_id TEXT,
            manifest_fingerprint TEXT,
            parameter_hash TEXT,
            seed TEXT,
            first_seen_ts_utc TEXT,
            last_seen_ts_utc TEXT,
            PRIMARY KEY (
                src_entity_id, dst_entity_id, edge_type,
                scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed
            )
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_checkpoints (
            stream_id TEXT,
            topic TEXT,
            partition_id INTEGER,
            next_offset TEXT,
            offset_kind TEXT,
            watermark_ts_utc TEXT,
            updated_at_utc TEXT,
            PRIMARY KEY (stream_id, topic, partition_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_graph_versions (
            stream_id TEXT PRIMARY KEY,
            graph_version TEXT,
            run_config_digest TEXT,
            basis_json TEXT,
            watermark_ts_utc TEXT,
            updated_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_metrics (
            stream_id TEXT,
            scenario_run_id TEXT,
            metric_name TEXT,
            metric_value INTEGER,
            updated_at_utc TEXT,
            PRIMARY KEY (stream_id, scenario_run_id, metric_name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_replay_basis (
            replay_id TEXT PRIMARY KEY,
            stream_id TEXT,
            manifest_json TEXT,
            basis_json TEXT,
            graph_version TEXT,
            recorded_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ieg_apply_failures_scope
        ON ieg_apply_failures(stream_id, platform_run_id, scenario_run_id)
        """
    )


def _sqlite_migration_v2(conn: sqlite3.Connection) -> None:
    _ensure_sqlite_column(conn, "ieg_dedupe", "platform_run_id", "TEXT")
    _ensure_sqlite_column(conn, "ieg_apply_failures", "platform_run_id", "TEXT")
    _ensure_sqlite_column(conn, "ieg_graph_versions", "run_config_digest", "TEXT")


def _postgres_migration_v1(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_dedupe (
            dedupe_key TEXT PRIMARY KEY,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            class_name TEXT,
            topic TEXT,
            event_id TEXT,
            payload_hash TEXT,
            first_offset TEXT,
            offset_kind TEXT,
            first_seen_ts_utc TEXT,
            created_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_apply_failures (
            failure_id TEXT PRIMARY KEY,
            stream_id TEXT,
            topic TEXT,
            partition_id INTEGER,
            offset TEXT,
            offset_kind TEXT,
            event_id TEXT,
            event_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            reason_code TEXT,
            details_json TEXT,
            ts_utc TEXT,
            recorded_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_entities (
            entity_id TEXT,
            entity_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            scenario_id TEXT,
            run_id TEXT,
            manifest_fingerprint TEXT,
            parameter_hash TEXT,
            seed TEXT,
            first_seen_ts_utc TEXT,
            last_seen_ts_utc TEXT,
            PRIMARY KEY (entity_id, scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_identifiers (
            identifier_type TEXT,
            identifier_value TEXT,
            entity_id TEXT,
            entity_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            scenario_id TEXT,
            run_id TEXT,
            manifest_fingerprint TEXT,
            parameter_hash TEXT,
            seed TEXT,
            first_seen_ts_utc TEXT,
            last_seen_ts_utc TEXT,
            source_event_id TEXT,
            PRIMARY KEY (
                identifier_type, identifier_value, entity_id,
                scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed
            )
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_edges (
            src_entity_id TEXT,
            dst_entity_id TEXT,
            edge_type TEXT,
            platform_run_id TEXT,
            scenario_run_id TEXT,
            scenario_id TEXT,
            run_id TEXT,
            manifest_fingerprint TEXT,
            parameter_hash TEXT,
            seed TEXT,
            first_seen_ts_utc TEXT,
            last_seen_ts_utc TEXT,
            PRIMARY KEY (
                src_entity_id, dst_entity_id, edge_type,
                scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed
            )
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_checkpoints (
            stream_id TEXT,
            topic TEXT,
            partition_id INTEGER,
            next_offset TEXT,
            offset_kind TEXT,
            watermark_ts_utc TEXT,
            updated_at_utc TEXT,
            PRIMARY KEY (stream_id, topic, partition_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_graph_versions (
            stream_id TEXT PRIMARY KEY,
            graph_version TEXT,
            run_config_digest TEXT,
            basis_json TEXT,
            watermark_ts_utc TEXT,
            updated_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_metrics (
            stream_id TEXT,
            scenario_run_id TEXT,
            metric_name TEXT,
            metric_value INTEGER,
            updated_at_utc TEXT,
            PRIMARY KEY (stream_id, scenario_run_id, metric_name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ieg_replay_basis (
            replay_id TEXT PRIMARY KEY,
            stream_id TEXT,
            manifest_json TEXT,
            basis_json TEXT,
            graph_version TEXT,
            recorded_at_utc TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ieg_apply_failures_scope
        ON ieg_apply_failures(stream_id, platform_run_id, scenario_run_id)
        """
    )


def _postgres_migration_v2(conn: psycopg.Connection) -> None:
    conn.execute("ALTER TABLE ieg_dedupe ADD COLUMN IF NOT EXISTS platform_run_id TEXT")
    conn.execute("ALTER TABLE ieg_apply_failures ADD COLUMN IF NOT EXISTS platform_run_id TEXT")
    conn.execute("ALTER TABLE ieg_graph_versions ADD COLUMN IF NOT EXISTS run_config_digest TEXT")


def _ensure_sqlite_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column in columns:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
