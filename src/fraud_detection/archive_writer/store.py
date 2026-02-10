"""Archive writer ledger + checkpoint store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3
from typing import Any

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.postgres_runtime import postgres_threadlocal_connection


ARCHIVE_OBS_NEW = "NEW"
ARCHIVE_OBS_DUPLICATE = "DUPLICATE"
ARCHIVE_OBS_PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"


@dataclass(frozen=True)
class ArchiveWriterObservation:
    outcome: str
    archive_ref: str | None
    payload_hash: str


class ArchiveWriterLedger:
    """Tracks immutable archive writes + offset tuple integrity."""

    def __init__(self, *, locator: str, stream_id: str) -> None:
        self.locator = str(locator or "").strip()
        self.stream_id = str(stream_id or "").strip()
        if not self.locator:
            raise ValueError("archive writer locator is required")
        if not self.stream_id:
            raise ValueError("archive writer stream_id is required")
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            sqlite_path = _sqlite_path(self.locator)
            sqlite3.connect(sqlite_path).close()
        self._ensure_schema()

    def observe(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        payload_hash: str,
        archive_ref: str,
        observed_at_utc: str,
    ) -> ArchiveWriterObservation:
        with self._connect() as conn:
            row = conn.execute(
                *self._sql_with_params(
                    """
                    SELECT payload_hash, archive_ref
                    FROM archive_writer_offsets
                    WHERE stream_id = {p1}
                      AND topic = {p2}
                      AND partition_id = {p3}
                      AND offset_kind = {p4}
                      AND offset_value = {p5}
                    """,
                    (
                        self.stream_id,
                        str(topic),
                        int(partition),
                        str(offset_kind),
                        str(offset),
                    ),
                )
            ).fetchone()
            if row is None:
                conn.execute(
                    *self._sql_with_params(
                        """
                        INSERT INTO archive_writer_offsets (
                            stream_id, topic, partition_id, offset_kind, offset_value,
                            payload_hash, archive_ref, first_seen_utc, last_seen_utc,
                            seen_count, mismatch_count
                        ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p8}, 1, 0)
                        """,
                        (
                            self.stream_id,
                            str(topic),
                            int(partition),
                            str(offset_kind),
                            str(offset),
                            str(payload_hash),
                            str(archive_ref),
                            str(observed_at_utc),
                        ),
                    )
                )
                return ArchiveWriterObservation(
                    outcome=ARCHIVE_OBS_NEW,
                    archive_ref=str(archive_ref),
                    payload_hash=str(payload_hash),
                )
            existing_hash = str(row[0] or "")
            existing_ref = str(row[1] or "")
            if existing_hash == str(payload_hash):
                conn.execute(
                    *self._sql_with_params(
                        """
                        UPDATE archive_writer_offsets
                           SET last_seen_utc = {p6},
                               seen_count = seen_count + 1
                         WHERE stream_id = {p1}
                           AND topic = {p2}
                           AND partition_id = {p3}
                           AND offset_kind = {p4}
                           AND offset_value = {p5}
                        """,
                        (
                            self.stream_id,
                            str(topic),
                            int(partition),
                            str(offset_kind),
                            str(offset),
                            str(observed_at_utc),
                        ),
                    )
                )
                return ArchiveWriterObservation(
                    outcome=ARCHIVE_OBS_DUPLICATE,
                    archive_ref=existing_ref or str(archive_ref),
                    payload_hash=existing_hash,
                )
            conn.execute(
                *self._sql_with_params(
                    """
                    INSERT INTO archive_writer_offset_mismatches (
                        stream_id, topic, partition_id, offset_kind, offset_value,
                        expected_payload_hash, observed_payload_hash,
                        expected_archive_ref, observed_archive_ref, observed_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10})
                    """,
                    (
                        self.stream_id,
                        str(topic),
                        int(partition),
                        str(offset_kind),
                        str(offset),
                        existing_hash,
                        str(payload_hash),
                        existing_ref,
                        str(archive_ref),
                        str(observed_at_utc),
                    ),
                )
            )
            conn.execute(
                *self._sql_with_params(
                    """
                    UPDATE archive_writer_offsets
                       SET mismatch_count = mismatch_count + 1,
                           last_seen_utc = {p6},
                           seen_count = seen_count + 1
                     WHERE stream_id = {p1}
                       AND topic = {p2}
                       AND partition_id = {p3}
                       AND offset_kind = {p4}
                       AND offset_value = {p5}
                    """,
                    (
                        self.stream_id,
                        str(topic),
                        int(partition),
                        str(offset_kind),
                        str(offset),
                        str(observed_at_utc),
                    ),
                )
            )
            return ArchiveWriterObservation(
                outcome=ARCHIVE_OBS_PAYLOAD_MISMATCH,
                archive_ref=existing_ref or str(archive_ref),
                payload_hash=existing_hash,
            )

    def next_offset(self, *, topic: str, partition: int) -> tuple[str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                *self._sql_with_params(
                    """
                    SELECT next_offset, offset_kind
                    FROM archive_writer_checkpoints
                    WHERE stream_id = {p1}
                      AND topic = {p2}
                      AND partition_id = {p3}
                    """,
                    (self.stream_id, str(topic), int(partition)),
                )
            ).fetchone()
        if row is None:
            return None
        return str(row[0]), str(row[1])

    def advance(self, *, topic: str, partition: int, offset: str, offset_kind: str) -> None:
        next_offset = str(offset)
        if str(offset_kind) in {"file_line", "kafka_offset"}:
            next_offset = str(int(offset) + 1)
        with self._connect() as conn:
            conn.execute(
                *self._sql_with_params(
                    """
                    INSERT INTO archive_writer_checkpoints (
                        stream_id, topic, partition_id, next_offset, offset_kind, updated_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6})
                    ON CONFLICT(stream_id, topic, partition_id) DO UPDATE SET
                        next_offset = excluded.next_offset,
                        offset_kind = excluded.offset_kind,
                        updated_at_utc = excluded.updated_at_utc
                    """,
                    (
                        self.stream_id,
                        str(topic),
                        int(partition),
                        next_offset,
                        str(offset_kind),
                        _utc_now(),
                    ),
                )
            )

    def clear_observation(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        payload_hash: str,
    ) -> None:
        """Best-effort rollback for NEW observations when archive write fails."""
        with self._connect() as conn:
            conn.execute(
                *self._sql_with_params(
                    """
                    DELETE FROM archive_writer_offsets
                    WHERE stream_id = {p1}
                      AND topic = {p2}
                      AND partition_id = {p3}
                      AND offset_kind = {p4}
                      AND offset_value = {p5}
                      AND payload_hash = {p6}
                      AND seen_count = 1
                      AND mismatch_count = 0
                    """,
                    (
                        self.stream_id,
                        str(topic),
                        int(partition),
                        str(offset_kind),
                        str(offset),
                        str(payload_hash),
                    ),
                )
            )

    def _connect(self) -> Any:
        if self.backend == "postgres":
            return postgres_threadlocal_connection(self.locator)
        return sqlite3.connect(_sqlite_path(self.locator))

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                _sql(
                    """
                    CREATE TABLE IF NOT EXISTS archive_writer_offsets (
                        stream_id TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        partition_id INTEGER NOT NULL,
                        offset_kind TEXT NOT NULL,
                        offset_value TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        archive_ref TEXT NOT NULL,
                        first_seen_utc TEXT NOT NULL,
                        last_seen_utc TEXT NOT NULL,
                        seen_count INTEGER NOT NULL DEFAULT 1,
                        mismatch_count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (stream_id, topic, partition_id, offset_kind, offset_value)
                    )
                    """,
                    self.backend,
                )
            )
            conn.execute(
                _sql(
                    """
                    CREATE TABLE IF NOT EXISTS archive_writer_offset_mismatches (
                        stream_id TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        partition_id INTEGER NOT NULL,
                        offset_kind TEXT NOT NULL,
                        offset_value TEXT NOT NULL,
                        expected_payload_hash TEXT NOT NULL,
                        observed_payload_hash TEXT NOT NULL,
                        expected_archive_ref TEXT NOT NULL,
                        observed_archive_ref TEXT NOT NULL,
                        observed_at_utc TEXT NOT NULL,
                        PRIMARY KEY (stream_id, topic, partition_id, offset_kind, offset_value, observed_at_utc)
                    )
                    """,
                    self.backend,
                )
            )
            conn.execute(
                _sql(
                    """
                    CREATE TABLE IF NOT EXISTS archive_writer_checkpoints (
                        stream_id TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        partition_id INTEGER NOT NULL,
                        next_offset TEXT NOT NULL,
                        offset_kind TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        PRIMARY KEY (stream_id, topic, partition_id)
                    )
                    """,
                    self.backend,
                )
            )

    def _sql_with_params(self, sql: str, params: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]]:
        rendered = _sql(sql, self.backend)
        ordered = _ordered_params(sql, params)
        return rendered, ordered


_PLACEHOLDER_PATTERN = re.compile(r"\{p(\d+)\}")


def _sql(sql: str, backend: str) -> str:
    if backend == "sqlite":
        return _PLACEHOLDER_PATTERN.sub("?", sql)
    if backend == "postgres":
        return _PLACEHOLDER_PATTERN.sub("%s", sql)
    raise ValueError(f"unsupported backend: {backend}")


def _ordered_params(sql: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
    if not params:
        return tuple()
    ordered: list[Any] = []
    for token in _PLACEHOLDER_PATTERN.findall(sql):
        idx = int(token) - 1
        if idx < 0 or idx >= len(params):
            raise ValueError(f"placeholder index out of range: p{token}")
        ordered.append(params[idx])
    return tuple(ordered)


def _sqlite_path(locator: str) -> str:
    text = str(locator or "").strip()
    if text.startswith("sqlite:///"):
        return text[len("sqlite:///") :]
    if text.startswith("sqlite://"):
        return text[len("sqlite://") :]
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
