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
                    eb_offset INTEGER
                )
                """
            )
            conn.commit()

    def lookup(self, dedupe_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_ref, eb_topic, eb_partition, eb_offset FROM admissions WHERE dedupe_key = ?",
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
            }
            if row[1] is not None
            else None,
        }

    def record(self, dedupe_key: str, receipt_ref: str, eb_ref: dict[str, Any] | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO admissions
                (dedupe_key, receipt_ref, eb_topic, eb_partition, eb_offset)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    receipt_ref,
                    eb_ref.get("topic") if eb_ref else None,
                    eb_ref.get("partition") if eb_ref else None,
                    eb_ref.get("offset") if eb_ref else None,
                ),
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
