"""Admission index for idempotency (sqlite)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AdmissionIndex:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admissions (
                    dedupe_key TEXT PRIMARY KEY,
                    state TEXT,
                    platform_run_id TEXT,
                    event_class TEXT,
                    event_id TEXT,
                    payload_hash TEXT,
                    receipt_ref TEXT,
                    receipt_write_failed INTEGER,
                    admitted_at_utc TEXT,
                    eb_topic TEXT,
                    eb_partition INTEGER,
                    eb_offset TEXT,
                    eb_offset_kind TEXT,
                    eb_published_at_utc TEXT
                )
                """
            )
            _ensure_columns(
                conn,
                "admissions",
                {
                    "state": "TEXT",
                    "platform_run_id": "TEXT",
                    "event_class": "TEXT",
                    "event_id": "TEXT",
                    "payload_hash": "TEXT",
                    "receipt_ref": "TEXT",
                    "receipt_write_failed": "INTEGER",
                    "admitted_at_utc": "TEXT",
                    "eb_offset": "TEXT",
                    "eb_offset_kind": "TEXT",
                    "eb_published_at_utc": "TEXT",
                },
            )
            conn.commit()

    def lookup(self, dedupe_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state, payload_hash, receipt_ref, receipt_write_failed, admitted_at_utc,
                       eb_topic, eb_partition, eb_offset, eb_offset_kind, eb_published_at_utc,
                       platform_run_id, event_class, event_id
                FROM admissions WHERE dedupe_key = ?
                """,
                (dedupe_key,),
            ).fetchone()
        if not row:
            return None
        receipt_ref = row[2] or None
        return {
            "state": row[0],
            "payload_hash": row[1],
            "receipt_ref": receipt_ref,
            "receipt_write_failed": bool(row[3]) if row[3] is not None else None,
            "admitted_at_utc": row[4],
            "eb_ref": {
                "topic": row[5],
                "partition": row[6],
                "offset": row[7],
                "offset_kind": row[8],
                "published_at_utc": row[9],
            }
            if row[5] is not None
            else None,
            "platform_run_id": row[10],
            "event_class": row[11],
            "event_id": row[12],
        }

    def record_in_flight(
        self,
        dedupe_key: str,
        *,
        platform_run_id: str,
        event_class: str,
        event_id: str,
        payload_hash: str,
    ) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO admissions
                (dedupe_key, state, platform_run_id, event_class, event_id, payload_hash, receipt_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    "PUBLISH_IN_FLIGHT",
                    platform_run_id,
                    event_class,
                    event_id,
                    payload_hash,
                    "",
                ),
            )
            conn.commit()
            return cursor.rowcount == 1

    def record_admitted(
        self,
        dedupe_key: str,
        *,
        eb_ref: dict[str, Any],
        admitted_at_utc: str,
        payload_hash: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE admissions SET
                    state = ?,
                    payload_hash = ?,
                    admitted_at_utc = ?,
                    eb_topic = ?,
                    eb_partition = ?,
                    eb_offset = ?,
                    eb_offset_kind = ?,
                    eb_published_at_utc = ?
                WHERE dedupe_key = ?
                """,
                (
                    "ADMITTED",
                    payload_hash,
                    admitted_at_utc,
                    eb_ref.get("topic"),
                    eb_ref.get("partition"),
                    eb_ref.get("offset"),
                    eb_ref.get("offset_kind"),
                    eb_ref.get("published_at_utc"),
                    dedupe_key,
                ),
            )
            conn.commit()

    def record_ambiguous(self, dedupe_key: str, payload_hash: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE admissions SET
                    state = ?,
                    payload_hash = COALESCE(payload_hash, ?)
                WHERE dedupe_key = ?
                """,
                (
                    "PUBLISH_AMBIGUOUS",
                    payload_hash,
                    dedupe_key,
                ),
            )
            conn.commit()

    def record_receipt(self, dedupe_key: str, receipt_ref: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE admissions SET
                    receipt_ref = ?,
                    receipt_write_failed = 0
                WHERE dedupe_key = ?
                """,
                (receipt_ref, dedupe_key),
            )
            conn.commit()

    def mark_receipt_failed(self, dedupe_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE admissions SET receipt_write_failed = 1 WHERE dedupe_key = ?",
                (dedupe_key,),
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, col_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
