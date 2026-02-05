"""IEG projection store (SQLite/Postgres)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from typing import Any

import sqlite3

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .config import IegRetention
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


@dataclass(frozen=True)
class IdentifierCandidate:
    entity_id: str
    entity_type: str
    first_seen_ts_utc: str | None
    last_seen_ts_utc: str | None


@dataclass(frozen=True)
class SharedIdentifier:
    identifier_type: str
    identifier_value: str


@dataclass(frozen=True)
class NeighborCandidate:
    entity_id: str
    entity_type: str
    first_seen_ts_utc: str | None
    last_seen_ts_utc: str | None
    shared_identifiers: list[SharedIdentifier]


def build_store(dsn: str, *, stream_id: str) -> "ProjectionStore":
    if is_postgres_dsn(dsn):
        return PostgresProjectionStore(dsn=dsn, stream_id=stream_id)
    path = _sqlite_path(dsn)
    return SqliteProjectionStore(path=Path(path), stream_id=stream_id)


class ProjectionStore:
    def get_checkpoint(self, *, topic: str, partition: int) -> Checkpoint | None:
        raise NotImplementedError

    def current_graph_version(self) -> str | None:
        raise NotImplementedError

    def graph_basis(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def checkpoint_summary(self) -> dict[str, Any]:
        raise NotImplementedError

    def metrics_summary(self, *, scenario_run_id: str) -> dict[str, int]:
        raise NotImplementedError

    def apply_failure_count(self, *, scenario_run_id: str, platform_run_id: str | None = None) -> int:
        raise NotImplementedError

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        count_as: str | None = None,
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
        platform_run_id: str | None,
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
        platform_run_id: str,
        scenario_run_id: str,
        pins: dict[str, Any],
        payload_hash: str,
        identity_hints: list[IdentityHint],
        event_ts_utc: str | None,
    ) -> ApplyResult:
        raise NotImplementedError

    def rebind_stream_id(self, new_stream_id: str) -> None:
        raise NotImplementedError

    def record_replay_basis(
        self,
        *,
        replay_id: str,
        manifest_json: str,
        basis_json: str,
        graph_version: str | None,
    ) -> None:
        raise NotImplementedError

    def prune(self, policy: IegRetention) -> dict[str, int]:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError

    def resolve_identifier_candidates(
        self,
        *,
        pins: dict[str, Any],
        identifier_type: str,
        identifier_value: str,
        limit: int,
        after: tuple[str, str] | None,
    ) -> list[IdentifierCandidate]:
        raise NotImplementedError

    def fetch_entity_profile(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def fetch_neighbors(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
        limit: int,
        after: tuple[str, str] | None,
    ) -> list[NeighborCandidate]:
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
            _ensure_sqlite_column(conn, "ieg_dedupe", "platform_run_id", "TEXT")
            _ensure_sqlite_column(conn, "ieg_apply_failures", "platform_run_id", "TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ieg_apply_failures_scope
                ON ieg_apply_failures(stream_id, platform_run_id, scenario_run_id)
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
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        count_as: str | None = None,
    ) -> ApplyResult:
        with self._connect() as conn:
            if scenario_run_id:
                self._increment_metric(conn, scenario_run_id, "events_seen", 1)
                if count_as:
                    self._increment_metric(conn, scenario_run_id, count_as, 1)
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

    def current_graph_version(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT graph_version FROM ieg_graph_versions WHERE stream_id = ?",
                (self.stream_id,),
            ).fetchone()
        if not row or not row[0]:
            return None
        return str(row[0])

    def graph_basis(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT graph_version, basis_json FROM ieg_graph_versions WHERE stream_id = ?",
                (self.stream_id,),
            ).fetchone()
        if not row or not row[1]:
            return None
        basis = json.loads(row[1])
        return {"graph_version": row[0], "basis": basis}

    def checkpoint_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(watermark_ts_utc), MAX(updated_at_utc), COUNT(*)
                FROM ieg_checkpoints WHERE stream_id = ?
                """,
                (self.stream_id,),
            ).fetchone()
        return {
            "watermark_ts_utc": row[0] if row else None,
            "updated_at_utc": row[1] if row else None,
            "partition_count": int(row[2]) if row else 0,
        }

    def metrics_summary(self, *, scenario_run_id: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metric_name, metric_value FROM ieg_metrics
                WHERE stream_id = ? AND scenario_run_id = ?
                """,
                (self.stream_id, scenario_run_id),
            ).fetchall()
        return {str(row[0]): int(row[1] or 0) for row in rows}

    def apply_failure_count(self, *, scenario_run_id: str, platform_run_id: str | None = None) -> int:
        with self._connect() as conn:
            if platform_run_id:
                row = conn.execute(
                    """
                    SELECT COUNT(*) FROM ieg_apply_failures
                    WHERE stream_id = ? AND scenario_run_id = ? AND platform_run_id = ?
                    """,
                    (self.stream_id, scenario_run_id, platform_run_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) FROM ieg_apply_failures
                    WHERE stream_id = ? AND scenario_run_id = ?
                    """,
                    (self.stream_id, scenario_run_id),
                ).fetchone()
        if not row:
            return 0
        return int(row[0] or 0)

    def record_failure(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        platform_run_id: str | None,
        scenario_run_id: str | None,
        reason_code: str,
        details: dict[str, Any] | None,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        failure_id = _failure_id(topic, partition, offset, reason_code, event_id)
        recorded_at = _utc_now()
        with self._connect() as conn:
            if scenario_run_id:
                self._increment_metric(conn, scenario_run_id, "events_seen", 1)
                self._increment_metric(conn, scenario_run_id, "unusable", 1)
            conn.execute(
                """
                INSERT OR IGNORE INTO ieg_apply_failures
                (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                 platform_run_id, scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    platform_run_id,
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
        platform_run_id: str,
        scenario_run_id: str,
        pins: dict[str, Any],
        payload_hash: str,
        identity_hints: list[IdentityHint],
        event_ts_utc: str | None,
    ) -> ApplyResult:
        with self._connect() as conn:
            self._increment_metric(conn, scenario_run_id, "events_seen", 1)
            row = conn.execute(
                "SELECT payload_hash FROM ieg_dedupe WHERE dedupe_key = ?",
                (pins["dedupe_key"],),
            ).fetchone()
            if row:
                if row[0] and row[0] != payload_hash:
                    self._increment_metric(conn, scenario_run_id, "payload_mismatch", 1)
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO ieg_apply_failures
                        (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                         platform_run_id, scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            platform_run_id,
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
                self._increment_metric(conn, scenario_run_id, "duplicate", 1)
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
                (dedupe_key, platform_run_id, scenario_run_id, class_name, topic, event_id, payload_hash,
                 first_offset, offset_kind, first_seen_ts_utc, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pins["dedupe_key"],
                    platform_run_id,
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
            self._increment_metric(conn, scenario_run_id, "mutating_applied", 1)

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

    def _increment_metric(
        self, conn: sqlite3.Connection, scenario_run_id: str, metric_name: str, delta: int
    ) -> None:
        conn.execute(
            """
            INSERT INTO ieg_metrics
            (stream_id, scenario_run_id, metric_name, metric_value, updated_at_utc)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(stream_id, scenario_run_id, metric_name)
            DO UPDATE SET
                metric_value = ieg_metrics.metric_value + excluded.metric_value,
                updated_at_utc = excluded.updated_at_utc
            """,
            (self.stream_id, scenario_run_id, metric_name, int(delta), _utc_now()),
        )

    def record_replay_basis(
        self,
        *,
        replay_id: str,
        manifest_json: str,
        basis_json: str,
        graph_version: str | None,
    ) -> None:
        recorded_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ieg_replay_basis
                (replay_id, stream_id, manifest_json, basis_json, graph_version, recorded_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(replay_id) DO UPDATE SET
                    manifest_json = excluded.manifest_json,
                    basis_json = excluded.basis_json,
                    graph_version = excluded.graph_version,
                    recorded_at_utc = excluded.recorded_at_utc
                """,
                (
                    replay_id,
                    self.stream_id,
                    manifest_json,
                    basis_json,
                    graph_version,
                    recorded_at,
                ),
            )

    def prune(self, policy: IegRetention) -> dict[str, int]:
        if not policy.is_enabled():
            return {}
        results: dict[str, int] = {}
        with self._connect() as conn:
            results["ieg_entities"] = _prune_table_sqlite(
                conn, "ieg_entities", "last_seen_ts_utc", _retention_cutoff(policy.entity_days)
            )
            results["ieg_identifiers"] = _prune_table_sqlite(
                conn, "ieg_identifiers", "last_seen_ts_utc", _retention_cutoff(policy.identifier_days)
            )
            results["ieg_edges"] = _prune_table_sqlite(
                conn, "ieg_edges", "last_seen_ts_utc", _retention_cutoff(policy.edge_days)
            )
            results["ieg_apply_failures"] = _prune_table_sqlite(
                conn, "ieg_apply_failures", "recorded_at_utc", _retention_cutoff(policy.apply_failure_days)
            )
            results["ieg_checkpoints"] = _prune_table_sqlite(
                conn, "ieg_checkpoints", "updated_at_utc", _retention_cutoff(policy.checkpoint_days)
            )
            if results.get("ieg_checkpoints", 0) > 0:
                self._update_graph_version(conn)
        return results

    def reset(self) -> None:
        tables = [
            "ieg_dedupe",
            "ieg_apply_failures",
            "ieg_entities",
            "ieg_identifiers",
            "ieg_edges",
            "ieg_checkpoints",
            "ieg_graph_versions",
            "ieg_metrics",
            "ieg_replay_basis",
        ]
        with self._connect() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table}")

    def rebind_stream_id(self, new_stream_id: str) -> None:
        if not new_stream_id or new_stream_id == self.stream_id:
            return
        with self._connect() as conn:
            conn.execute(
                "UPDATE ieg_checkpoints SET stream_id = %s WHERE stream_id = %s",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_graph_versions SET stream_id = %s WHERE stream_id = %s",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_metrics SET stream_id = %s WHERE stream_id = %s",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_apply_failures SET stream_id = %s WHERE stream_id = %s",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_replay_basis SET stream_id = %s WHERE stream_id = %s",
                (new_stream_id, self.stream_id),
            )
        self.stream_id = new_stream_id

    def rebind_stream_id(self, new_stream_id: str) -> None:
        if not new_stream_id or new_stream_id == self.stream_id:
            return
        with self._connect() as conn:
            conn.execute(
                "UPDATE ieg_checkpoints SET stream_id = ? WHERE stream_id = ?",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_graph_versions SET stream_id = ? WHERE stream_id = ?",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_metrics SET stream_id = ? WHERE stream_id = ?",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_apply_failures SET stream_id = ? WHERE stream_id = ?",
                (new_stream_id, self.stream_id),
            )
            conn.execute(
                "UPDATE ieg_replay_basis SET stream_id = ? WHERE stream_id = ?",
                (new_stream_id, self.stream_id),
            )
        self.stream_id = new_stream_id

    def resolve_identifier_candidates(
        self,
        *,
        pins: dict[str, Any],
        identifier_type: str,
        identifier_value: str,
        limit: int,
        after: tuple[str, str] | None,
    ) -> list[IdentifierCandidate]:
        platform_run_id, scenario_run_id, scenario_id, manifest_fingerprint, parameter_hash, seed = _pin_tuple(pins)
        if not platform_run_id or not scenario_run_id:
            return []
        params: list[Any] = [
            platform_run_id,
            scenario_run_id,
            scenario_id,
            manifest_fingerprint,
            parameter_hash,
            seed,
            identifier_type,
            identifier_value,
        ]
        after_clause = ""
        if after:
            after_clause = " AND (entity_type > ? OR (entity_type = ? AND entity_id > ?))"
            params.extend([after[0], after[0], after[1]])
        params.append(limit)
        query = f"""
            SELECT entity_id, entity_type, first_seen_ts_utc, last_seen_ts_utc
            FROM ieg_identifiers
            WHERE platform_run_id = ?
              AND scenario_run_id = ?
              AND scenario_id = ?
              AND manifest_fingerprint = ?
              AND parameter_hash = ?
              AND seed = ?
              AND identifier_type = ?
              AND identifier_value = ?
              {after_clause}
            ORDER BY entity_type ASC, entity_id ASC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            IdentifierCandidate(
                entity_id=str(row[0]),
                entity_type=str(row[1]),
                first_seen_ts_utc=row[2],
                last_seen_ts_utc=row[3],
            )
            for row in rows
        ]

    def fetch_entity_profile(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
    ) -> dict[str, Any] | None:
        platform_run_id, scenario_run_id, scenario_id, manifest_fingerprint, parameter_hash, seed = _pin_tuple(pins)
        if not platform_run_id or not scenario_run_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT first_seen_ts_utc, last_seen_ts_utc
                FROM ieg_entities
                WHERE platform_run_id = ?
                  AND scenario_run_id = ?
                  AND scenario_id = ?
                  AND manifest_fingerprint = ?
                  AND parameter_hash = ?
                  AND seed = ?
                  AND entity_id = ?
                  AND entity_type = ?
                LIMIT 1
                """,
                (
                    platform_run_id,
                    scenario_run_id,
                    scenario_id,
                    manifest_fingerprint,
                    parameter_hash,
                    seed,
                    entity_id,
                    entity_type,
                ),
            ).fetchone()
        if not row:
            return None
        return {"entity_id": entity_id, "entity_type": entity_type, "first_seen_ts_utc": row[0], "last_seen_ts_utc": row[1]}

    def fetch_neighbors(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
        limit: int,
        after: tuple[str, str] | None,
    ) -> list[NeighborCandidate]:
        platform_run_id, scenario_run_id, scenario_id, manifest_fingerprint, parameter_hash, seed = _pin_tuple(pins)
        if not platform_run_id or not scenario_run_id:
            return []
        params: list[Any] = [
            platform_run_id,
            scenario_run_id,
            scenario_id,
            manifest_fingerprint,
            parameter_hash,
            seed,
            entity_id,
            entity_type,
            entity_id,
            entity_type,
        ]
        after_clause = ""
        if after:
            after_clause = " AND (other.entity_type > ? OR (other.entity_type = ? AND other.entity_id > ?))"
            params.extend([after[0], after[0], after[1]])
        query = f"""
            SELECT other.entity_id, other.entity_type, other.identifier_type, other.identifier_value,
                   other.first_seen_ts_utc, other.last_seen_ts_utc
            FROM ieg_identifiers self
            JOIN ieg_identifiers other
              ON self.identifier_type = other.identifier_type
             AND self.identifier_value = other.identifier_value
             AND self.platform_run_id = other.platform_run_id
             AND self.scenario_run_id = other.scenario_run_id
             AND self.scenario_id = other.scenario_id
             AND self.manifest_fingerprint = other.manifest_fingerprint
             AND self.parameter_hash = other.parameter_hash
             AND self.seed = other.seed
            WHERE self.platform_run_id = ?
              AND self.scenario_run_id = ?
              AND self.scenario_id = ?
              AND self.manifest_fingerprint = ?
              AND self.parameter_hash = ?
              AND self.seed = ?
              AND self.entity_id = ?
              AND self.entity_type = ?
              AND NOT (other.entity_id = ? AND other.entity_type = ?)
              {after_clause}
            ORDER BY other.entity_type ASC, other.entity_id ASC, other.identifier_type ASC, other.identifier_value ASC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        grouped: list[NeighborCandidate] = []
        current_key: tuple[str, str] | None = None
        shared: list[SharedIdentifier] = []
        first_seen = None
        last_seen = None

        def _flush() -> None:
            if current_key is None:
                return
            grouped.append(
                NeighborCandidate(
                    entity_id=current_key[1],
                    entity_type=current_key[0],
                    first_seen_ts_utc=first_seen,
                    last_seen_ts_utc=last_seen,
                    shared_identifiers=shared.copy(),
                )
            )

        for row in rows:
            neighbor_type = str(row[1])
            neighbor_id = str(row[0])
            key = (neighbor_type, neighbor_id)
            if current_key != key:
                if current_key is not None and len(grouped) >= limit:
                    break
                _flush()
                current_key = key
                shared = []
                first_seen = row[4]
                last_seen = row[5]
            shared.append(SharedIdentifier(identifier_type=str(row[2]), identifier_value=str(row[3])))
            if row[4] and (first_seen is None or row[4] < first_seen):
                first_seen = row[4]
            if row[5] and (last_seen is None or row[5] > last_seen):
                last_seen = row[5]

        if current_key is not None and len(grouped) < limit:
            _flush()
        return grouped

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
            _ensure_postgres_column(conn, "ieg_dedupe", "platform_run_id", "TEXT")
            _ensure_postgres_column(conn, "ieg_apply_failures", "platform_run_id", "TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ieg_apply_failures_scope
                ON ieg_apply_failures(stream_id, platform_run_id, scenario_run_id)
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
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        count_as: str | None = None,
    ) -> ApplyResult:
        with self._connect() as conn:
            if scenario_run_id:
                self._increment_metric(conn, scenario_run_id, "events_seen", 1)
                if count_as:
                    self._increment_metric(conn, scenario_run_id, count_as, 1)
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

    def current_graph_version(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT graph_version FROM ieg_graph_versions WHERE stream_id = %s",
                (self.stream_id,),
            ).fetchone()
        if not row or not row[0]:
            return None
        return str(row[0])

    def graph_basis(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT graph_version, basis_json FROM ieg_graph_versions WHERE stream_id = %s",
                (self.stream_id,),
            ).fetchone()
        if not row or not row[1]:
            return None
        basis = json.loads(row[1])
        return {"graph_version": row[0], "basis": basis}

    def checkpoint_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(watermark_ts_utc), MAX(updated_at_utc), COUNT(*)
                FROM ieg_checkpoints WHERE stream_id = %s
                """,
                (self.stream_id,),
            ).fetchone()
        return {
            "watermark_ts_utc": row[0] if row else None,
            "updated_at_utc": row[1] if row else None,
            "partition_count": int(row[2]) if row else 0,
        }

    def metrics_summary(self, *, scenario_run_id: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metric_name, metric_value FROM ieg_metrics
                WHERE stream_id = %s AND scenario_run_id = %s
                """,
                (self.stream_id, scenario_run_id),
            ).fetchall()
        return {str(row[0]): int(row[1] or 0) for row in rows}

    def apply_failure_count(self, *, scenario_run_id: str, platform_run_id: str | None = None) -> int:
        with self._connect() as conn:
            if platform_run_id:
                row = conn.execute(
                    """
                    SELECT COUNT(*) FROM ieg_apply_failures
                    WHERE stream_id = %s AND scenario_run_id = %s AND platform_run_id = %s
                    """,
                    (self.stream_id, scenario_run_id, platform_run_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) FROM ieg_apply_failures
                    WHERE stream_id = %s AND scenario_run_id = %s
                    """,
                    (self.stream_id, scenario_run_id),
                ).fetchone()
        if not row:
            return 0
        return int(row[0] or 0)

    def record_failure(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        event_type: str,
        platform_run_id: str | None,
        scenario_run_id: str | None,
        reason_code: str,
        details: dict[str, Any] | None,
        event_ts_utc: str | None,
    ) -> ApplyResult:
        failure_id = _failure_id(topic, partition, offset, reason_code, event_id)
        recorded_at = _utc_now()
        with self._connect() as conn:
            if scenario_run_id:
                self._increment_metric(conn, scenario_run_id, "events_seen", 1)
                self._increment_metric(conn, scenario_run_id, "unusable", 1)
            conn.execute(
                """
                INSERT INTO ieg_apply_failures
                (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                 platform_run_id, scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    platform_run_id,
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
        platform_run_id: str,
        scenario_run_id: str,
        pins: dict[str, Any],
        payload_hash: str,
        identity_hints: list[IdentityHint],
        event_ts_utc: str | None,
    ) -> ApplyResult:
        with self._connect() as conn:
            self._increment_metric(conn, scenario_run_id, "events_seen", 1)
            row = conn.execute(
                "SELECT payload_hash FROM ieg_dedupe WHERE dedupe_key = %s",
                (pins["dedupe_key"],),
            ).fetchone()
            if row:
                if row[0] and row[0] != payload_hash:
                    self._increment_metric(conn, scenario_run_id, "payload_mismatch", 1)
                    conn.execute(
                        """
                        INSERT INTO ieg_apply_failures
                        (failure_id, stream_id, topic, partition_id, offset, offset_kind, event_id, event_type,
                         platform_run_id, scenario_run_id, reason_code, details_json, ts_utc, recorded_at_utc)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                            platform_run_id,
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
                self._increment_metric(conn, scenario_run_id, "duplicate", 1)
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
                (dedupe_key, platform_run_id, scenario_run_id, class_name, topic, event_id, payload_hash,
                 first_offset, offset_kind, first_seen_ts_utc, created_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pins["dedupe_key"],
                    platform_run_id,
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
            self._increment_metric(conn, scenario_run_id, "mutating_applied", 1)

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

    def _increment_metric(
        self, conn: psycopg.Connection, scenario_run_id: str, metric_name: str, delta: int
    ) -> None:
        conn.execute(
            """
            INSERT INTO ieg_metrics
            (stream_id, scenario_run_id, metric_name, metric_value, updated_at_utc)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (stream_id, scenario_run_id, metric_name)
            DO UPDATE SET
                metric_value = ieg_metrics.metric_value + EXCLUDED.metric_value,
                updated_at_utc = EXCLUDED.updated_at_utc
            """,
            (self.stream_id, scenario_run_id, metric_name, int(delta), _utc_now()),
        )

    def record_replay_basis(
        self,
        *,
        replay_id: str,
        manifest_json: str,
        basis_json: str,
        graph_version: str | None,
    ) -> None:
        recorded_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ieg_replay_basis
                (replay_id, stream_id, manifest_json, basis_json, graph_version, recorded_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (replay_id) DO UPDATE SET
                    manifest_json = excluded.manifest_json,
                    basis_json = excluded.basis_json,
                    graph_version = excluded.graph_version,
                    recorded_at_utc = excluded.recorded_at_utc
                """,
                (
                    replay_id,
                    self.stream_id,
                    manifest_json,
                    basis_json,
                    graph_version,
                    recorded_at,
                ),
            )

    def prune(self, policy: IegRetention) -> dict[str, int]:
        if not policy.is_enabled():
            return {}
        results: dict[str, int] = {}
        with self._connect() as conn:
            results["ieg_entities"] = _prune_table_postgres(
                conn, "ieg_entities", "last_seen_ts_utc", _retention_cutoff(policy.entity_days)
            )
            results["ieg_identifiers"] = _prune_table_postgres(
                conn, "ieg_identifiers", "last_seen_ts_utc", _retention_cutoff(policy.identifier_days)
            )
            results["ieg_edges"] = _prune_table_postgres(
                conn, "ieg_edges", "last_seen_ts_utc", _retention_cutoff(policy.edge_days)
            )
            results["ieg_apply_failures"] = _prune_table_postgres(
                conn, "ieg_apply_failures", "recorded_at_utc", _retention_cutoff(policy.apply_failure_days)
            )
            results["ieg_checkpoints"] = _prune_table_postgres(
                conn, "ieg_checkpoints", "updated_at_utc", _retention_cutoff(policy.checkpoint_days)
            )
            if results.get("ieg_checkpoints", 0) > 0:
                self._update_graph_version(conn)
        return results

    def reset(self) -> None:
        tables = [
            "ieg_dedupe",
            "ieg_apply_failures",
            "ieg_entities",
            "ieg_identifiers",
            "ieg_edges",
            "ieg_checkpoints",
            "ieg_graph_versions",
            "ieg_metrics",
            "ieg_replay_basis",
        ]
        with self._connect() as conn:
            for table in tables:
                conn.execute(f"DELETE FROM {table}")

    def resolve_identifier_candidates(
        self,
        *,
        pins: dict[str, Any],
        identifier_type: str,
        identifier_value: str,
        limit: int,
        after: tuple[str, str] | None,
    ) -> list[IdentifierCandidate]:
        platform_run_id, scenario_run_id, scenario_id, manifest_fingerprint, parameter_hash, seed = _pin_tuple(pins)
        if not platform_run_id or not scenario_run_id:
            return []
        params: list[Any] = [
            platform_run_id,
            scenario_run_id,
            scenario_id,
            manifest_fingerprint,
            parameter_hash,
            seed,
            identifier_type,
            identifier_value,
        ]
        after_clause = ""
        if after:
            after_clause = " AND (entity_type > %s OR (entity_type = %s AND entity_id > %s))"
            params.extend([after[0], after[0], after[1]])
        params.append(limit)
        query = f"""
            SELECT entity_id, entity_type, first_seen_ts_utc, last_seen_ts_utc
            FROM ieg_identifiers
            WHERE platform_run_id = %s
              AND scenario_run_id = %s
              AND scenario_id = %s
              AND manifest_fingerprint = %s
              AND parameter_hash = %s
              AND seed = %s
              AND identifier_type = %s
              AND identifier_value = %s
              {after_clause}
            ORDER BY entity_type ASC, entity_id ASC
            LIMIT %s
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            IdentifierCandidate(
                entity_id=str(row[0]),
                entity_type=str(row[1]),
                first_seen_ts_utc=row[2],
                last_seen_ts_utc=row[3],
            )
            for row in rows
        ]

    def fetch_entity_profile(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
    ) -> dict[str, Any] | None:
        platform_run_id, scenario_run_id, scenario_id, manifest_fingerprint, parameter_hash, seed = _pin_tuple(pins)
        if not platform_run_id or not scenario_run_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT first_seen_ts_utc, last_seen_ts_utc
                FROM ieg_entities
                WHERE platform_run_id = %s
                  AND scenario_run_id = %s
                  AND scenario_id = %s
                  AND manifest_fingerprint = %s
                  AND parameter_hash = %s
                  AND seed = %s
                  AND entity_id = %s
                  AND entity_type = %s
                LIMIT 1
                """,
                (
                    platform_run_id,
                    scenario_run_id,
                    scenario_id,
                    manifest_fingerprint,
                    parameter_hash,
                    seed,
                    entity_id,
                    entity_type,
                ),
            ).fetchone()
        if not row:
            return None
        return {"entity_id": entity_id, "entity_type": entity_type, "first_seen_ts_utc": row[0], "last_seen_ts_utc": row[1]}

    def fetch_neighbors(
        self,
        *,
        pins: dict[str, Any],
        entity_id: str,
        entity_type: str,
        limit: int,
        after: tuple[str, str] | None,
    ) -> list[NeighborCandidate]:
        platform_run_id, scenario_run_id, scenario_id, manifest_fingerprint, parameter_hash, seed = _pin_tuple(pins)
        if not platform_run_id or not scenario_run_id:
            return []
        params: list[Any] = [
            platform_run_id,
            scenario_run_id,
            scenario_id,
            manifest_fingerprint,
            parameter_hash,
            seed,
            entity_id,
            entity_type,
            entity_id,
            entity_type,
        ]
        after_clause = ""
        if after:
            after_clause = " AND (other.entity_type > %s OR (other.entity_type = %s AND other.entity_id > %s))"
            params.extend([after[0], after[0], after[1]])
        query = f"""
            SELECT other.entity_id, other.entity_type, other.identifier_type, other.identifier_value,
                   other.first_seen_ts_utc, other.last_seen_ts_utc
            FROM ieg_identifiers self
            JOIN ieg_identifiers other
              ON self.identifier_type = other.identifier_type
             AND self.identifier_value = other.identifier_value
             AND self.platform_run_id = other.platform_run_id
             AND self.scenario_run_id = other.scenario_run_id
             AND self.scenario_id = other.scenario_id
             AND self.manifest_fingerprint = other.manifest_fingerprint
             AND self.parameter_hash = other.parameter_hash
             AND self.seed = other.seed
            WHERE self.platform_run_id = %s
              AND self.scenario_run_id = %s
              AND self.scenario_id = %s
              AND self.manifest_fingerprint = %s
              AND self.parameter_hash = %s
              AND self.seed = %s
              AND self.entity_id = %s
              AND self.entity_type = %s
              AND NOT (other.entity_id = %s AND other.entity_type = %s)
              {after_clause}
            ORDER BY other.entity_type ASC, other.entity_id ASC, other.identifier_type ASC, other.identifier_value ASC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        grouped: list[NeighborCandidate] = []
        current_key: tuple[str, str] | None = None
        shared: list[SharedIdentifier] = []
        first_seen = None
        last_seen = None

        def _flush() -> None:
            if current_key is None:
                return
            grouped.append(
                NeighborCandidate(
                    entity_id=current_key[1],
                    entity_type=current_key[0],
                    first_seen_ts_utc=first_seen,
                    last_seen_ts_utc=last_seen,
                    shared_identifiers=shared.copy(),
                )
            )

        for row in rows:
            neighbor_type = str(row[1])
            neighbor_id = str(row[0])
            key = (neighbor_type, neighbor_id)
            if current_key != key:
                if current_key is not None and len(grouped) >= limit:
                    break
                _flush()
                current_key = key
                shared = []
                first_seen = row[4]
                last_seen = row[5]
            shared.append(SharedIdentifier(identifier_type=str(row[2]), identifier_value=str(row[3])))
            if row[4] and (first_seen is None or row[4] < first_seen):
                first_seen = row[4]
            if row[5] and (last_seen is None or row[5] > last_seen):
                last_seen = row[5]

        if current_key is not None and len(grouped) < limit:
            _flush()
        return grouped

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


def _pin_tuple(pins: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None, str | None, str]:
    platform_run_id = pins.get("platform_run_id")
    scenario_run_id = pins.get("scenario_run_id")
    scenario_id = pins.get("scenario_id")
    manifest_fingerprint = pins.get("manifest_fingerprint")
    parameter_hash = pins.get("parameter_hash")
    seed = str(pins.get("seed") or "")
    return (
        str(platform_run_id) if platform_run_id is not None else None,
        str(scenario_run_id) if scenario_run_id is not None else None,
        str(scenario_id) if scenario_id is not None else None,
        str(manifest_fingerprint) if manifest_fingerprint is not None else None,
        str(parameter_hash) if parameter_hash is not None else None,
        seed,
    )


def _retention_cutoff(days: int | None) -> str | None:
    if days is None:
        return None
    if days <= 0:
        return None
    return (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()


def _prune_table_sqlite(conn: sqlite3.Connection, table: str, column: str, cutoff: str | None) -> int:
    if cutoff is None:
        return 0
    cursor = conn.execute(
        f"DELETE FROM {table} WHERE {column} IS NOT NULL AND {column} < ?",
        (cutoff,),
    )
    return int(cursor.rowcount or 0)


def _prune_table_postgres(conn: psycopg.Connection, table: str, column: str, cutoff: str | None) -> int:
    if cutoff is None:
        return 0
    cursor = conn.execute(
        f"DELETE FROM {table} WHERE {column} IS NOT NULL AND {column} < %s",
        (cutoff,),
    )
    return int(cursor.rowcount or 0)


def _sqlite_path(dsn: str) -> str:
    if dsn.startswith("sqlite:///"):
        return dsn.replace("sqlite:///", "", 1)
    if dsn.startswith("sqlite://"):
        return dsn.replace("sqlite://", "", 1)
    return dsn


def _ensure_sqlite_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return
    existing = {row[1] for row in rows}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _ensure_postgres_column(conn: psycopg.Connection, table: str, column: str, column_type: str) -> None:
    conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {column_type}")


def hashlib_sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
