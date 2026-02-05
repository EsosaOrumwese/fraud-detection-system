"""IEG projection store (SQLite/Postgres)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import sqlite3

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .hints import IdentityHint


@dataclass(frozen=True)
class ApplyResult:
    status: str
    graph_version: str | None
    reason: str | None = None


@dataclass(frozen=True)
class Checkpoint:
    next_offset: str
    offset_kind: str


def build_store(dsn: str, *, stream_id: str) -> "ProjectionStore":
    if is_postgres_dsn(dsn):
        return PostgresProjectionStore(dsn=dsn, stream_id=stream_id)
    path = _sqlite_path(dsn)
    return SqliteProjectionStore(path=Path(path), stream_id=stream_id)


class ProjectionStore:
    def get_checkpoint(self, *, topic: str, partition: int) -> Checkpoint | None:
        raise NotImplementedError

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        raise NotImplementedError

    def record_failure(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        scenario_run_id: str | None,
        reason_code: str,
        details: dict[str, Any] | None,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        raise NotImplementedError

    def apply_mutation(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        class_name: str,
        scenario_run_id: str,
        pins: dict[str, Any],
        payload_hash: str,
        identity_hints: list[IdentityHint],
        event_ts_utc: str | None,
    ) -> ApplyResult:
        raise NotImplementedError


@dataclass
class SqliteProjectionStore(ProjectionStore):
    path: Path
    stream_id: str

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ieg_dedupe (
                    dedupe_key TEXT PRIMARY KEY,
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
                    basis_json TEXT,
                    watermark_ts_utc TEXT,
                    updated_at_utc TEXT
                )
                """
            )

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        with self._connect() as conn:
            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            graph_version = self._update_graph_version(conn)
        return ApplyResult(status="IRRELEVANT", graph_version=graph_version)

    def get_checkpoint(self, *, topic: str, partition: int) -> Checkpoint | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT next_offset, offset_kind
                FROM ieg_checkpoints WHERE stream_id = ? AND topic = ? AND partition_id = ?
                """,
                (self.stream_id, topic, partition),
            ).fetchone()
        if not row:
            return None
        return Checkpoint(next_offset=str(row[0]), offset_kind=str(row[1]))

    def record_failure(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        scenario_run_id: str | None,
        reason_code: str,
        details: dict[str, Any] | None,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        failure_id = _failure_id(topic, partition, offset, reason_code, event_id)
        recorded_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO ieg_apply_failures
                (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                 scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    failure_id,
                    self.stream_id,
                    topic,
                    partition,
                    str(offset),
                    offset_kind,
                    event_id,
                    event_type,
                    scenario_run_id,
                    reason_code,
                    _json_dump(details),
                    event_ts_utc,
                    recorded_at,
                ),
            )
            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            graph_version = self._update_graph_version(conn)
        return ApplyResult(status="UNUSABLE", graph_version=graph_version, reason=reason_code)

    def apply_mutation(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        class_name: str,
        scenario_run_id: str,
        pins: dict[str, Any],
        payload_hash: str,
        identity_hints: list[IdentityHint],
        event_ts_utc: str | None,
    ) -> ApplyResult:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_hash FROM ieg_dedupe WHERE dedupe_key = ?",
                (pins["dedupe_key"],),
            ).fetchone()
            if row:
                if row[0] and row[0] != payload_hash:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO ieg_apply_failures
                        (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                         scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _failure_id(topic, partition, offset, "PAYLOAD_HASH_MISMATCH", event_id),
                            self.stream_id,
                            topic,
                            partition,
                            str(offset),
                            offset_kind,
                            event_id,
                            event_type,
                            scenario_run_id,
                            "PAYLOAD_HASH_MISMATCH",
                            None,
                            event_ts_utc,
                            _utc_now(),
                        ),
                    )
                    self._update_checkpoint(
                        conn,
                        topic=topic,
                        partition=partition,
                        offset=offset,
                        offset_kind=offset_kind,
                        event_ts_utc=event_ts_utc,
                    )
                    graph_version = self._update_graph_version(conn)
                    return ApplyResult(status="PAYLOAD_MISMATCH", graph_version=graph_version)
                self._update_checkpoint(
                    conn,
                    topic=topic,
                    partition=partition,
                    offset=offset,
                    offset_kind=offset_kind,
                    event_ts_utc=event_ts_utc,
                )
                graph_version = self._update_graph_version(conn)
                return ApplyResult(status="DUPLICATE", graph_version=graph_version)

            conn.execute(
                """
                INSERT INTO ieg_dedupe
                (dedupe_key, scenario_run_id, class_name, topic, event_id, payload_hash,
                 first_offset, offset_kind, first_seen_ts_utc, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pins["dedupe_key"],
                    scenario_run_id,
                    class_name,
                    topic,
                    event_id,
                    payload_hash,
                    str(offset),
                    offset_kind,
                    event_ts_utc,
                    _utc_now(),
                ),
            )

            for hint in identity_hints:
                self._upsert_entity(conn, hint, pins, event_ts_utc)
                self._upsert_identifier(conn, hint, pins, event_ts_utc)

            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            graph_version = self._update_graph_version(conn)
        return ApplyResult(status="APPLIED", graph_version=graph_version)

    def _upsert_entity(
        self, conn: sqlite3.Connection, hint: IdentityHint, pins: dict[str, Any], event_ts_utc: str | None
    ) -> None:
        conn.execute(
            """
            INSERT INTO ieg_entities
            (entity_id, entity_type, platform_run_id, scenario_run_id, scenario_id, run_id,
             manifest_fingerprint, parameter_hash, seed, first_seen_ts_utc, last_seen_ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_id, scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed)
            DO UPDATE SET
                first_seen_ts_utc = CASE
                    WHEN excluded.first_seen_ts_utc < first_seen_ts_utc THEN excluded.first_seen_ts_utc
                    ELSE first_seen_ts_utc
                END,
                last_seen_ts_utc = CASE
                    WHEN excluded.last_seen_ts_utc > last_seen_ts_utc THEN excluded.last_seen_ts_utc
                    ELSE last_seen_ts_utc
                END
            """,
            (
                hint.entity_id,
                hint.entity_type,
                pins.get("platform_run_id"),
                pins.get("scenario_run_id"),
                pins.get("scenario_id"),
                pins.get("run_id"),
                pins.get("manifest_fingerprint"),
                pins.get("parameter_hash"),
                str(pins.get("seed") or ""),
                event_ts_utc,
                event_ts_utc,
            ),
        )

    def _upsert_identifier(
        self, conn: sqlite3.Connection, hint: IdentityHint, pins: dict[str, Any], event_ts_utc: str | None
    ) -> None:
        conn.execute(
            """
            INSERT INTO ieg_identifiers
            (identifier_type, identifier_value, entity_id, entity_type, platform_run_id, scenario_run_id,
             scenario_id, run_id, manifest_fingerprint, parameter_hash, seed,
             first_seen_ts_utc, last_seen_ts_utc, source_event_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                identifier_type, identifier_value, entity_id,
                scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed
            )
            DO UPDATE SET
                first_seen_ts_utc = CASE
                    WHEN excluded.first_seen_ts_utc < first_seen_ts_utc THEN excluded.first_seen_ts_utc
                    ELSE first_seen_ts_utc
                END,
                last_seen_ts_utc = CASE
                    WHEN excluded.last_seen_ts_utc > last_seen_ts_utc THEN excluded.last_seen_ts_utc
                    ELSE last_seen_ts_utc
                END
            """,
            (
                hint.identifier_type,
                hint.identifier_value,
                hint.entity_id,
                hint.entity_type,
                pins.get("platform_run_id"),
                pins.get("scenario_run_id"),
                pins.get("scenario_id"),
                pins.get("run_id"),
                pins.get("manifest_fingerprint"),
                pins.get("parameter_hash"),
                str(pins.get("seed") or ""),
                event_ts_utc,
                event_ts_utc,
                hint.source_event_id,
            ),
        )

    def _update_checkpoint(
        self,
        conn: sqlite3.Connection,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> None:
        next_offset = _next_offset(offset, offset_kind)
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO ieg_checkpoints
            (stream_id, topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stream_id, topic, partition_id)
            DO UPDATE SET
                next_offset = excluded.next_offset,
                offset_kind = excluded.offset_kind,
                watermark_ts_utc = CASE
                    WHEN excluded.watermark_ts_utc IS NULL THEN watermark_ts_utc
                    WHEN watermark_ts_utc IS NULL THEN excluded.watermark_ts_utc
                    WHEN excluded.watermark_ts_utc > watermark_ts_utc THEN excluded.watermark_ts_utc
                    ELSE watermark_ts_utc
                END,
                updated_at_utc = excluded.updated_at_utc
            """,
            (
                self.stream_id,
                topic,
                partition,
                next_offset,
                offset_kind,
                event_ts_utc,
                now,
            ),
        )

    def _update_graph_version(self, conn: sqlite3.Connection) -> str:
        rows = conn.execute(
            """
            SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc
            FROM ieg_checkpoints WHERE stream_id = ?
            """,
            (self.stream_id,),
        ).fetchall()
        basis, watermark = _basis_from_rows(self.stream_id, rows)
        graph_version = _graph_version_from_basis(basis)
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO ieg_graph_versions
            (stream_id, graph_version, basis_json, watermark_ts_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(stream_id) DO UPDATE SET
                graph_version = excluded.graph_version,
                basis_json = excluded.basis_json,
                watermark_ts_utc = excluded.watermark_ts_utc,
                updated_at_utc = excluded.updated_at_utc
            """,
            (self.stream_id, graph_version, _json_dump(basis), watermark, now),
        )
        return graph_version

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

@dataclass
class PostgresProjectionStore(ProjectionStore):
    dsn: str
    stream_id: str

    def __post_init__(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ieg_dedupe (
                    dedupe_key TEXT PRIMARY KEY,
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
                    basis_json TEXT,
                    watermark_ts_utc TEXT,
                    updated_at_utc TEXT
                )
                """
            )

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        with self._connect() as conn:
            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            graph_version = self._update_graph_version(conn)
        return ApplyResult(status="IRRELEVANT", graph_version=graph_version)

    def get_checkpoint(self, *, topic: str, partition: int) -> Checkpoint | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT next_offset, offset_kind
                FROM ieg_checkpoints WHERE stream_id = %s AND topic = %s AND partition_id = %s
                """,
                (self.stream_id, topic, partition),
            ).fetchone()
        if not row:
            return None
        return Checkpoint(next_offset=str(row[0]), offset_kind=str(row[1]))

    def record_failure(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        scenario_run_id: str | None,
        reason_code: str,
        details: dict[str, Any] | None,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        failure_id = _failure_id(topic, partition, offset, reason_code, event_id)
        recorded_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ieg_apply_failures
                (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                 scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (failure_id) DO NOTHING
                """,
                (
                    failure_id,
                    self.stream_id,
                    topic,
                    partition,
                    str(offset),
                    offset_kind,
                    event_id,
                    event_type,
                    scenario_run_id,
                    reason_code,
                    _json_dump(details),
                    event_ts_utc,
                    recorded_at,
                ),
            )
            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            graph_version = self._update_graph_version(conn)
        return ApplyResult(status="UNUSABLE", graph_version=graph_version, reason=reason_code)

    def apply_mutation(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        class_name: str,
        scenario_run_id: str,
        pins: dict[str, Any],
        payload_hash: str,
        identity_hints: list[IdentityHint],
        event_ts_utc: str | None,
    ) -> ApplyResult:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_hash FROM ieg_dedupe WHERE dedupe_key = %s",
                (pins["dedupe_key"],),
            ).fetchone()
            if row:
                if row[0] and row[0] != payload_hash:
                    conn.execute(
                        """
                        INSERT INTO ieg_apply_failures
                        (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                         scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (failure_id) DO NOTHING
                        """,
                        (
                            _failure_id(topic, partition, offset, "PAYLOAD_HASH_MISMATCH", event_id),
                            self.stream_id,
                            topic,
                            partition,
                            str(offset),
                            offset_kind,
                            event_id,
                            event_type,
                            scenario_run_id,
                            "PAYLOAD_HASH_MISMATCH",
                            None,
                            event_ts_utc,
                            _utc_now(),
                        ),
                    )
                    self._update_checkpoint(
                        conn,
                        topic=topic,
                        partition=partition,
                        offset=offset,
                        offset_kind=offset_kind,
                        event_ts_utc=event_ts_utc,
                    )
                    graph_version = self._update_graph_version(conn)
                    return ApplyResult(status="PAYLOAD_MISMATCH", graph_version=graph_version)
                self._update_checkpoint(
                    conn,
                    topic=topic,
                    partition=partition,
                    offset=offset,
                    offset_kind=offset_kind,
                    event_ts_utc=event_ts_utc,
                )
                graph_version = self._update_graph_version(conn)
                return ApplyResult(status="DUPLICATE", graph_version=graph_version)

            conn.execute(
                """
                INSERT INTO ieg_dedupe
                (dedupe_key, scenario_run_id, class_name, topic, event_id, payload_hash,
                 first_offset, offset_kind, first_seen_ts_utc, created_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pins["dedupe_key"],
                    scenario_run_id,
                    class_name,
                    topic,
                    event_id,
                    payload_hash,
                    str(offset),
                    offset_kind,
                    event_ts_utc,
                    _utc_now(),
                ),
            )

            for hint in identity_hints:
                self._upsert_entity(conn, hint, pins, event_ts_utc)
                self._upsert_identifier(conn, hint, pins, event_ts_utc)

            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            graph_version = self._update_graph_version(conn)
        return ApplyResult(status="APPLIED", graph_version=graph_version)

    def _upsert_entity(self, conn: psycopg.Connection, hint: IdentityHint, pins: dict[str, Any], event_ts_utc: str | None) -> None:
        conn.execute(
            """
            INSERT INTO ieg_entities
            (entity_id, entity_type, platform_run_id, scenario_run_id, scenario_id, run_id,
             manifest_fingerprint, parameter_hash, seed, first_seen_ts_utc, last_seen_ts_utc)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(entity_id, scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed)
            DO UPDATE SET
                first_seen_ts_utc = LEAST(ieg_entities.first_seen_ts_utc, excluded.first_seen_ts_utc),
                last_seen_ts_utc = GREATEST(ieg_entities.last_seen_ts_utc, excluded.last_seen_ts_utc)
            """,
            (
                hint.entity_id,
                hint.entity_type,
                pins.get("platform_run_id"),
                pins.get("scenario_run_id"),
                pins.get("scenario_id"),
                pins.get("run_id"),
                pins.get("manifest_fingerprint"),
                pins.get("parameter_hash"),
                str(pins.get("seed") or ""),
                event_ts_utc,
                event_ts_utc,
            ),
        )

    def _upsert_identifier(
        self, conn: psycopg.Connection, hint: IdentityHint, pins: dict[str, Any], event_ts_utc: str | None
    ) -> None:
        conn.execute(
            """
            INSERT INTO ieg_identifiers
            (identifier_type, identifier_value, entity_id, entity_type, platform_run_id, scenario_run_id,
             scenario_id, run_id, manifest_fingerprint, parameter_hash, seed,
             first_seen_ts_utc, last_seen_ts_utc, source_event_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(
                identifier_type, identifier_value, entity_id,
                scenario_run_id, manifest_fingerprint, parameter_hash, scenario_id, seed
            )
            DO UPDATE SET
                first_seen_ts_utc = LEAST(ieg_identifiers.first_seen_ts_utc, excluded.first_seen_ts_utc),
                last_seen_ts_utc = GREATEST(ieg_identifiers.last_seen_ts_utc, excluded.last_seen_ts_utc)
            """,
            (
                hint.identifier_type,
                hint.identifier_value,
                hint.entity_id,
                hint.entity_type,
                pins.get("platform_run_id"),
                pins.get("scenario_run_id"),
                pins.get("scenario_id"),
                pins.get("run_id"),
                pins.get("manifest_fingerprint"),
                pins.get("parameter_hash"),
                str(pins.get("seed") or ""),
                event_ts_utc,
                event_ts_utc,
                hint.source_event_id,
            ),
        )

    def _update_checkpoint(
        self,
        conn: psycopg.Connection,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> None:
        next_offset = _next_offset(offset, offset_kind)
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO ieg_checkpoints
            (stream_id, topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(stream_id, topic, partition_id)
            DO UPDATE SET
                next_offset = excluded.next_offset,
                offset_kind = excluded.offset_kind,
                watermark_ts_utc = CASE
                    WHEN excluded.watermark_ts_utc IS NULL THEN ieg_checkpoints.watermark_ts_utc
                    WHEN ieg_checkpoints.watermark_ts_utc IS NULL THEN excluded.watermark_ts_utc
                    WHEN excluded.watermark_ts_utc > ieg_checkpoints.watermark_ts_utc THEN excluded.watermark_ts_utc
                    ELSE ieg_checkpoints.watermark_ts_utc
                END,
                updated_at_utc = excluded.updated_at_utc
            """,
            (
                self.stream_id,
                topic,
                partition,
                next_offset,
                offset_kind,
                event_ts_utc,
                now,
            ),
        )

    def _update_graph_version(self, conn: psycopg.Connection) -> str:
        rows = conn.execute(
            """
            SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc
            FROM ieg_checkpoints WHERE stream_id = %s
            """,
            (self.stream_id,),
        ).fetchall()
        basis, watermark = _basis_from_rows(self.stream_id, rows)
        graph_version = _graph_version_from_basis(basis)
        now = _utc_now()
        conn.execute(
            """
            INSERT INTO ieg_graph_versions
            (stream_id, graph_version, basis_json, watermark_ts_utc, updated_at_utc)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (stream_id) DO UPDATE SET
                graph_version = excluded.graph_version,
                basis_json = excluded.basis_json,
                watermark_ts_utc = excluded.watermark_ts_utc,
                updated_at_utc = excluded.updated_at_utc
            """,
            (self.stream_id, graph_version, _json_dump(basis), watermark, now),
        )
        return graph_version

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


def _basis_from_rows(stream_id: str, rows: list[tuple[Any, ...]]) -> tuple[dict[str, Any], str | None]:
    topics: dict[str, dict[str, Any]] = {}
    watermark: str | None = None
    for topic, partition_id, next_offset, offset_kind, watermark_ts in rows:
        topic_map = topics.setdefault(str(topic), {"partitions": {}})
        topic_map["partitions"][str(partition_id)] = {
            "next_offset": str(next_offset),
            "offset_kind": str(offset_kind),
        }
        if watermark_ts:
            if watermark is None or str(watermark_ts) > watermark:
                watermark = str(watermark_ts)
    basis = {"stream_id": stream_id, "topics": topics}
    return basis, watermark


def _graph_version_from_basis(basis: dict[str, Any]) -> str:
    canonical = json.dumps(basis, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib_sha256(canonical.encode("utf-8"))


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _next_offset(offset: str, offset_kind: str) -> str:
    if offset_kind == "file_line":
        try:
            return str(int(offset) + 1)
        except ValueError:
            return str(offset)
    return str(offset)


def _failure_id(topic: str, partition: int, offset: str, reason: str, event_id: str) -> str:
    payload = f"{topic}:{partition}:{offset}:{reason}:{event_id}"
    return hashlib_sha256(payload.encode("utf-8"))[:32]


def _sqlite_path(dsn: str) -> str:
    if dsn.startswith("sqlite:///"):
        return dsn.replace("sqlite:///", "", 1)
    if dsn.startswith("sqlite://"):
        return dsn.replace("sqlite://", "", 1)
    return dsn


def hashlib_sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
