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
                    receipt_ref TEXT NOT NULL,
                    eb_topic TEXT,
                    eb_partition INTEGER,
                    eb_offset TEXT,
                    eb_offset_kind TEXT
                )
                """
            )
            _ensure_columns(
                conn,
                "admissions",
                {
                    "eb_offset": "TEXT",
                    "eb_offset_kind": "TEXT",
                },
            )
            conn.commit()

    def lookup(self, dedupe_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_ref, eb_topic, eb_partition, eb_offset, eb_offset_kind FROM admissions WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
        if not row:
            return None
        return {
            "receipt_ref": row[0],
            "eb_ref": {
                "topic": row[1],
                "partition": row[2],
                "offset": row[3],
                "offset_kind": row[4],
            }
            if row[1] is not None
            else None,
        }

    def record(self, dedupe_key: str, receipt_ref: str, eb_ref: dict[str, Any] | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO admissions
                (dedupe_key, receipt_ref, eb_topic, eb_partition, eb_offset, eb_offset_kind)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    receipt_ref,
                    eb_ref.get("topic") if eb_ref else None,
                    eb_ref.get("partition") if eb_ref else None,
                    eb_ref.get("offset") if eb_ref else None,
                    eb_ref.get("offset_kind") if eb_ref else None,
                ),
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, col_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
