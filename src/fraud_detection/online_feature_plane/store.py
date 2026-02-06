"""OFP projection store (SQLite/Postgres)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn


@dataclass(frozen=True)
class ApplyResult:
    status: str
    input_basis_digest: str | None = None


@dataclass(frozen=True)
class Checkpoint:
    next_offset: str
    offset_kind: str


def build_store(
    dsn: str,
    *,
    stream_id: str,
    basis_stream: str,
    run_config_digest: str | None = None,
) -> "OfpStore":
    if is_postgres_dsn(dsn):
        return PostgresOfpStore(
            dsn=dsn,
            stream_id=stream_id,
            basis_stream=basis_stream,
            run_config_digest=run_config_digest,
        )
    return SqliteOfpStore(
        path=Path(_sqlite_path(dsn)),
        stream_id=stream_id,
        basis_stream=basis_stream,
        run_config_digest=run_config_digest,
    )


class OfpStore:
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
        scenario_run_id: str | None,
        count_as: str | None,
    ) -> None:
        raise NotImplementedError

    def apply_event(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        payload_hash: str,
        event_ts_utc: str | None,
        pins: dict[str, Any],
        key_type: str,
        key_id: str,
        group_name: str,
        group_version: str,
        amount: float,
    ) -> ApplyResult:
        raise NotImplementedError

    def input_basis(self) -> dict[str, Any] | None:
        raise NotImplementedError

    def get_group_state(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        key_type: str,
        key_id: str,
        group_name: str,
        group_version: str,
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    def metrics_summary(self, *, scenario_run_id: str) -> dict[str, int]:
        raise NotImplementedError


@dataclass
class SqliteOfpStore(OfpStore):
    path: Path
    stream_id: str
    basis_stream: str
    run_config_digest: str | None = None

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ofp_applied_events (
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    partition_id INTEGER NOT NULL,
                    offset TEXT NOT NULL,
                    offset_kind TEXT NOT NULL,
                    event_id TEXT,
                    payload_hash TEXT,
                    ts_utc TEXT,
                    platform_run_id TEXT,
                    scenario_run_id TEXT,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, topic, partition_id, offset_kind, offset)
                );

                CREATE TABLE IF NOT EXISTS ofp_feature_state (
                    stream_id TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    scenario_id TEXT,
                    run_id TEXT,
                    manifest_fingerprint TEXT,
                    parameter_hash TEXT,
                    seed TEXT,
                    key_type TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    group_version TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    amount_sum REAL NOT NULL,
                    last_event_ts_utc TEXT,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (
                        stream_id, platform_run_id, scenario_run_id,
                        key_type, key_id, group_name, group_version
                    )
                );

                CREATE TABLE IF NOT EXISTS ofp_checkpoints (
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    partition_id INTEGER NOT NULL,
                    next_offset TEXT NOT NULL,
                    offset_kind TEXT NOT NULL,
                    watermark_ts_utc TEXT,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, topic, partition_id)
                );

                CREATE TABLE IF NOT EXISTS ofp_metrics (
                    stream_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value INTEGER NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scenario_run_id, metric_name)
                );
                """
            )

    def get_checkpoint(self, *, topic: str, partition: int) -> Checkpoint | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT next_offset, offset_kind
                FROM ofp_checkpoints
                WHERE stream_id = ? AND topic = ? AND partition_id = ?
                """,
                (self.stream_id, topic, partition),
            ).fetchone()
        if not row:
            return None
        return Checkpoint(next_offset=str(row[0]), offset_kind=str(row[1]))

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
        scenario_run_id: str | None,
        count_as: str | None,
    ) -> None:
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

    def apply_event(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        payload_hash: str,
        event_ts_utc: str | None,
        pins: dict[str, Any],
        key_type: str,
        key_id: str,
        group_name: str,
        group_version: str,
        amount: float,
    ) -> ApplyResult:
        scenario_run_id = str(pins.get("scenario_run_id") or "")
        if not scenario_run_id:
            return ApplyResult(status="INVALID_PINS")

        with self._connect() as conn:
            self._increment_metric(conn, scenario_run_id, "events_seen", 1)
            row = conn.execute(
                """
                INSERT OR IGNORE INTO ofp_applied_events (
                    stream_id, topic, partition_id, offset, offset_kind, event_id, payload_hash,
                    ts_utc, platform_run_id, scenario_run_id, created_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.stream_id,
                    topic,
                    partition,
                    str(offset),
                    offset_kind,
                    event_id,
                    payload_hash,
                    event_ts_utc,
                    str(pins.get("platform_run_id") or ""),
                    scenario_run_id,
                    _utc_now(),
                ),
            )
            inserted = row.rowcount == 1
            if inserted:
                self._increment_metric(conn, scenario_run_id, "events_applied", 1)
                conn.execute(
                    """
                    INSERT INTO ofp_feature_state (
                        stream_id, platform_run_id, scenario_run_id, scenario_id, run_id,
                        manifest_fingerprint, parameter_hash, seed,
                        key_type, key_id, group_name, group_version,
                        event_count, amount_sum, last_event_ts_utc, updated_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (
                        stream_id, platform_run_id, scenario_run_id, key_type, key_id, group_name, group_version
                    )
                    DO UPDATE SET
                        event_count = ofp_feature_state.event_count + excluded.event_count,
                        amount_sum = ofp_feature_state.amount_sum + excluded.amount_sum,
                        last_event_ts_utc = CASE
                            WHEN excluded.last_event_ts_utc IS NULL THEN ofp_feature_state.last_event_ts_utc
                            WHEN ofp_feature_state.last_event_ts_utc IS NULL THEN excluded.last_event_ts_utc
                            WHEN excluded.last_event_ts_utc > ofp_feature_state.last_event_ts_utc THEN excluded.last_event_ts_utc
                            ELSE ofp_feature_state.last_event_ts_utc
                        END,
                        updated_at_utc = excluded.updated_at_utc
                    """,
                    (
                        self.stream_id,
                        str(pins.get("platform_run_id") or ""),
                        scenario_run_id,
                        str(pins.get("scenario_id") or ""),
                        str(pins.get("run_id") or ""),
                        str(pins.get("manifest_fingerprint") or ""),
                        str(pins.get("parameter_hash") or ""),
                        str(pins.get("seed") or ""),
                        key_type,
                        key_id,
                        group_name,
                        group_version,
                        1,
                        float(amount),
                        event_ts_utc,
                        _utc_now(),
                    ),
                )
                status = "APPLIED"
            else:
                self._increment_metric(conn, scenario_run_id, "duplicates", 1)
                status = "DUPLICATE"

            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            basis = self._input_basis(conn)
        return ApplyResult(status=status, input_basis_digest=(basis or {}).get("basis_digest"))

    def input_basis(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            return self._input_basis(conn)

    def get_group_state(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        key_type: str,
        key_id: str,
        group_name: str,
        group_version: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT event_count, amount_sum, last_event_ts_utc, updated_at_utc
                FROM ofp_feature_state
                WHERE stream_id = ?
                  AND platform_run_id = ?
                  AND scenario_run_id = ?
                  AND key_type = ?
                  AND key_id = ?
                  AND group_name = ?
                  AND group_version = ?
                """,
                (
                    self.stream_id,
                    platform_run_id,
                    scenario_run_id,
                    key_type,
                    key_id,
                    group_name,
                    group_version,
                ),
            ).fetchone()
        if not row:
            return None
        return {
            "event_count": int(row[0]),
            "amount_sum": float(row[1]),
            "last_event_ts_utc": row[2],
            "updated_at_utc": row[3],
        }

    def metrics_summary(self, *, scenario_run_id: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metric_name, metric_value
                FROM ofp_metrics
                WHERE stream_id = ? AND scenario_run_id = ?
                """,
                (self.stream_id, scenario_run_id),
            ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def _input_basis(self, conn: sqlite3.Connection) -> dict[str, Any] | None:
        rows = conn.execute(
            """
            SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc
            FROM ofp_checkpoints
            WHERE stream_id = ?
            ORDER BY topic ASC, partition_id ASC
            """,
            (self.stream_id,),
        ).fetchall()
        if not rows:
            return None

        offsets: list[dict[str, Any]] = []
        watermark = None
        offset_kind = str(rows[0][3])
        for row in rows:
            offsets.append({"partition": int(row[1]), "offset": str(row[2])})
            current_watermark = row[4]
            if current_watermark and (watermark is None or str(current_watermark) > str(watermark)):
                watermark = str(current_watermark)

        basis: dict[str, Any] = {
            "stream": self.basis_stream,
            "offset_kind": offset_kind,
            "offsets": offsets,
        }
        canonical = json.dumps(basis, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        basis["basis_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if watermark:
            basis["window_end_utc"] = watermark
        return basis

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
            INSERT INTO ofp_checkpoints (
                stream_id, topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stream_id, topic, partition_id)
            DO UPDATE SET
                next_offset = CASE
                    WHEN _fd_offset_after(excluded.next_offset, ofp_checkpoints.next_offset) THEN excluded.next_offset
                    ELSE ofp_checkpoints.next_offset
                END,
                offset_kind = excluded.offset_kind,
                watermark_ts_utc = CASE
                    WHEN excluded.watermark_ts_utc IS NULL THEN ofp_checkpoints.watermark_ts_utc
                    WHEN ofp_checkpoints.watermark_ts_utc IS NULL THEN excluded.watermark_ts_utc
                    WHEN excluded.watermark_ts_utc > ofp_checkpoints.watermark_ts_utc THEN excluded.watermark_ts_utc
                    ELSE ofp_checkpoints.watermark_ts_utc
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

    def _increment_metric(
        self,
        conn: sqlite3.Connection,
        scenario_run_id: str,
        metric_name: str,
        delta: int,
    ) -> None:
        conn.execute(
            """
            INSERT INTO ofp_metrics (stream_id, scenario_run_id, metric_name, metric_value, updated_at_utc)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(stream_id, scenario_run_id, metric_name)
            DO UPDATE SET
                metric_value = ofp_metrics.metric_value + excluded.metric_value,
                updated_at_utc = excluded.updated_at_utc
            """,
            (self.stream_id, scenario_run_id, metric_name, int(delta), _utc_now()),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.create_function("_fd_offset_after", 2, _sqlite_offset_after)
        return conn


@dataclass
class PostgresOfpStore(OfpStore):
    dsn: str
    stream_id: str
    basis_stream: str
    run_config_digest: str | None = None

    def __post_init__(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ofp_applied_events (
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    partition_id INTEGER NOT NULL,
                    offset TEXT NOT NULL,
                    offset_kind TEXT NOT NULL,
                    event_id TEXT,
                    payload_hash TEXT,
                    ts_utc TEXT,
                    platform_run_id TEXT,
                    scenario_run_id TEXT,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, topic, partition_id, offset_kind, offset)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ofp_feature_state (
                    stream_id TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    scenario_id TEXT,
                    run_id TEXT,
                    manifest_fingerprint TEXT,
                    parameter_hash TEXT,
                    seed TEXT,
                    key_type TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    group_version TEXT NOT NULL,
                    event_count BIGINT NOT NULL,
                    amount_sum DOUBLE PRECISION NOT NULL,
                    last_event_ts_utc TEXT,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (
                        stream_id, platform_run_id, scenario_run_id,
                        key_type, key_id, group_name, group_version
                    )
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ofp_checkpoints (
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
                CREATE TABLE IF NOT EXISTS ofp_metrics (
                    stream_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value BIGINT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scenario_run_id, metric_name)
                )
                """
            )

    def get_checkpoint(self, *, topic: str, partition: int) -> Checkpoint | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT next_offset, offset_kind
                FROM ofp_checkpoints
                WHERE stream_id = %s AND topic = %s AND partition_id = %s
                """,
                (self.stream_id, topic, partition),
            ).fetchone()
        if not row:
            return None
        return Checkpoint(next_offset=str(row[0]), offset_kind=str(row[1]))

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
        scenario_run_id: str | None,
        count_as: str | None,
    ) -> None:
        with self._connect() as conn, conn.transaction():
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

    def apply_event(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_id: str,
        payload_hash: str,
        event_ts_utc: str | None,
        pins: dict[str, Any],
        key_type: str,
        key_id: str,
        group_name: str,
        group_version: str,
        amount: float,
    ) -> ApplyResult:
        scenario_run_id = str(pins.get("scenario_run_id") or "")
        if not scenario_run_id:
            return ApplyResult(status="INVALID_PINS")

        with self._connect() as conn, conn.transaction():
            self._increment_metric(conn, scenario_run_id, "events_seen", 1)
            row = conn.execute(
                """
                INSERT INTO ofp_applied_events (
                    stream_id, topic, partition_id, offset, offset_kind, event_id, payload_hash,
                    ts_utc, platform_run_id, scenario_run_id, created_at_utc
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (stream_id, topic, partition_id, offset_kind, offset) DO NOTHING
                """,
                (
                    self.stream_id,
                    topic,
                    partition,
                    str(offset),
                    offset_kind,
                    event_id,
                    payload_hash,
                    event_ts_utc,
                    str(pins.get("platform_run_id") or ""),
                    scenario_run_id,
                    _utc_now(),
                ),
            )
            inserted = row.rowcount == 1
            if inserted:
                self._increment_metric(conn, scenario_run_id, "events_applied", 1)
                conn.execute(
                    """
                    INSERT INTO ofp_feature_state (
                        stream_id, platform_run_id, scenario_run_id, scenario_id, run_id,
                        manifest_fingerprint, parameter_hash, seed,
                        key_type, key_id, group_name, group_version,
                        event_count, amount_sum, last_event_ts_utc, updated_at_utc
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (
                        stream_id, platform_run_id, scenario_run_id, key_type, key_id, group_name, group_version
                    )
                    DO UPDATE SET
                        event_count = ofp_feature_state.event_count + EXCLUDED.event_count,
                        amount_sum = ofp_feature_state.amount_sum + EXCLUDED.amount_sum,
                        last_event_ts_utc = CASE
                            WHEN EXCLUDED.last_event_ts_utc IS NULL THEN ofp_feature_state.last_event_ts_utc
                            WHEN ofp_feature_state.last_event_ts_utc IS NULL THEN EXCLUDED.last_event_ts_utc
                            WHEN EXCLUDED.last_event_ts_utc > ofp_feature_state.last_event_ts_utc THEN EXCLUDED.last_event_ts_utc
                            ELSE ofp_feature_state.last_event_ts_utc
                        END,
                        updated_at_utc = EXCLUDED.updated_at_utc
                    """,
                    (
                        self.stream_id,
                        str(pins.get("platform_run_id") or ""),
                        scenario_run_id,
                        str(pins.get("scenario_id") or ""),
                        str(pins.get("run_id") or ""),
                        str(pins.get("manifest_fingerprint") or ""),
                        str(pins.get("parameter_hash") or ""),
                        str(pins.get("seed") or ""),
                        key_type,
                        key_id,
                        group_name,
                        group_version,
                        1,
                        float(amount),
                        event_ts_utc,
                        _utc_now(),
                    ),
                )
                status = "APPLIED"
            else:
                self._increment_metric(conn, scenario_run_id, "duplicates", 1)
                status = "DUPLICATE"

            self._update_checkpoint(
                conn,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )
            basis = self._input_basis(conn)
        return ApplyResult(status=status, input_basis_digest=(basis or {}).get("basis_digest"))

    def input_basis(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            return self._input_basis(conn)

    def get_group_state(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        key_type: str,
        key_id: str,
        group_name: str,
        group_version: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT event_count, amount_sum, last_event_ts_utc, updated_at_utc
                FROM ofp_feature_state
                WHERE stream_id = %s
                  AND platform_run_id = %s
                  AND scenario_run_id = %s
                  AND key_type = %s
                  AND key_id = %s
                  AND group_name = %s
                  AND group_version = %s
                """,
                (
                    self.stream_id,
                    platform_run_id,
                    scenario_run_id,
                    key_type,
                    key_id,
                    group_name,
                    group_version,
                ),
            ).fetchone()
        if not row:
            return None
        return {
            "event_count": int(row[0]),
            "amount_sum": float(row[1]),
            "last_event_ts_utc": row[2],
            "updated_at_utc": row[3],
        }

    def metrics_summary(self, *, scenario_run_id: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metric_name, metric_value
                FROM ofp_metrics
                WHERE stream_id = %s AND scenario_run_id = %s
                """,
                (self.stream_id, scenario_run_id),
            ).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def _input_basis(self, conn: psycopg.Connection) -> dict[str, Any] | None:
        rows = conn.execute(
            """
            SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc
            FROM ofp_checkpoints
            WHERE stream_id = %s
            ORDER BY topic ASC, partition_id ASC
            """,
            (self.stream_id,),
        ).fetchall()
        if not rows:
            return None

        offsets: list[dict[str, Any]] = []
        watermark = None
        offset_kind = str(rows[0][3])
        for row in rows:
            offsets.append({"partition": int(row[1]), "offset": str(row[2])})
            current_watermark = row[4]
            if current_watermark and (watermark is None or str(current_watermark) > str(watermark)):
                watermark = str(current_watermark)

        basis: dict[str, Any] = {
            "stream": self.basis_stream,
            "offset_kind": offset_kind,
            "offsets": offsets,
        }
        canonical = json.dumps(basis, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        basis["basis_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if watermark:
            basis["window_end_utc"] = watermark
        return basis

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
        row = conn.execute(
            """
            SELECT next_offset, watermark_ts_utc
            FROM ofp_checkpoints
            WHERE stream_id = %s AND topic = %s AND partition_id = %s
            """,
            (self.stream_id, topic, partition),
        ).fetchone()
        next_offset = _next_offset(offset, offset_kind)
        now = _utc_now()
        if not row:
            conn.execute(
                """
                INSERT INTO ofp_checkpoints (
                    stream_id, topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (self.stream_id, topic, partition, next_offset, offset_kind, event_ts_utc, now),
            )
            return

        current_offset = str(row[0])
        current_watermark = row[1]
        updated_offset = next_offset if _offset_after(next_offset, current_offset) else current_offset
        updated_watermark = current_watermark
        if event_ts_utc and (updated_watermark is None or str(event_ts_utc) > str(updated_watermark)):
            updated_watermark = event_ts_utc
        conn.execute(
            """
            UPDATE ofp_checkpoints
            SET next_offset = %s,
                offset_kind = %s,
                watermark_ts_utc = %s,
                updated_at_utc = %s
            WHERE stream_id = %s AND topic = %s AND partition_id = %s
            """,
            (
                updated_offset,
                offset_kind,
                updated_watermark,
                now,
                self.stream_id,
                topic,
                partition,
            ),
        )

    def _increment_metric(
        self,
        conn: psycopg.Connection,
        scenario_run_id: str,
        metric_name: str,
        delta: int,
    ) -> None:
        conn.execute(
            """
            INSERT INTO ofp_metrics (stream_id, scenario_run_id, metric_name, metric_value, updated_at_utc)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (stream_id, scenario_run_id, metric_name)
            DO UPDATE SET
                metric_value = ofp_metrics.metric_value + EXCLUDED.metric_value,
                updated_at_utc = EXCLUDED.updated_at_utc
            """,
            (self.stream_id, scenario_run_id, metric_name, int(delta), _utc_now()),
        )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _next_offset(offset: str, offset_kind: str) -> str:
    if offset_kind == "file_line":
        try:
            return str(int(offset) + 1)
        except (TypeError, ValueError):
            return str(offset)
    return str(offset)


def _offset_after(left: str, right: str) -> bool:
    return _offset_compare(left, right) > 0


def _offset_compare(left: str, right: str) -> int:
    try:
        left_value = int(left)
        right_value = int(right)
    except (TypeError, ValueError):
        if left < right:
            return -1
        if left > right:
            return 1
        return 0
    if left_value < right_value:
        return -1
    if left_value > right_value:
        return 1
    return 0


def _sqlite_offset_after(left: str, right: str) -> int:
    return 1 if _offset_after(str(left), str(right)) else 0


def _sqlite_path(dsn: str) -> str:
    if dsn.startswith("sqlite:///"):
        return dsn.replace("sqlite:///", "", 1)
    if dsn.startswith("sqlite://"):
        return dsn.replace("sqlite://", "", 1)
    return dsn
