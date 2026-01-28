"""Checkpoint backends for WSP streaming progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Protocol

import psycopg


@dataclass(frozen=True)
class CheckpointCursor:
    pack_key: str
    output_id: str
    last_file: str
    last_row_index: int
    last_ts_utc: str | None


class CheckpointStore(Protocol):
    def load(self, pack_key: str, output_id: str) -> CheckpointCursor | None:
        ...

    def save(self, cursor: CheckpointCursor) -> None:
        ...


class FileCheckpointStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, pack_key: str, output_id: str) -> CheckpointCursor | None:
        path = self._cursor_path(pack_key, output_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CheckpointCursor(
            pack_key=payload["pack_key"],
            output_id=payload["output_id"],
            last_file=payload["last_file"],
            last_row_index=int(payload["last_row_index"]),
            last_ts_utc=payload.get("last_ts_utc"),
        )

    def save(self, cursor: CheckpointCursor) -> None:
        payload = {
            "pack_key": cursor.pack_key,
            "output_id": cursor.output_id,
            "last_file": cursor.last_file,
            "last_row_index": cursor.last_row_index,
            "last_ts_utc": cursor.last_ts_utc,
            "updated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        cursor_path = self._cursor_path(cursor.pack_key, cursor.output_id)
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cursor_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        tmp_path.replace(cursor_path)
        log_path = cursor_path.with_suffix(".jsonl")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def _cursor_path(self, pack_key: str, output_id: str) -> Path:
        safe_output = output_id.replace("/", "_")
        return self.root / pack_key / f"output_id={safe_output}" / "cursor.json"


class PostgresCheckpointStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._ensure_table()

    def load(self, pack_key: str, output_id: str) -> CheckpointCursor | None:
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                """
                SELECT last_file, last_row_index, last_ts_utc
                FROM wsp_checkpoint
                WHERE pack_key = %s AND output_id = %s
                """,
                (pack_key, output_id),
            ).fetchone()
        if not row:
            return None
        return CheckpointCursor(
            pack_key=pack_key,
            output_id=output_id,
            last_file=row[0],
            last_row_index=int(row[1]),
            last_ts_utc=row[2],
        )

    def save(self, cursor: CheckpointCursor) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                INSERT INTO wsp_checkpoint (pack_key, output_id, last_file, last_row_index, last_ts_utc, updated_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (pack_key, output_id)
                DO UPDATE SET last_file = EXCLUDED.last_file,
                              last_row_index = EXCLUDED.last_row_index,
                              last_ts_utc = EXCLUDED.last_ts_utc,
                              updated_at_utc = EXCLUDED.updated_at_utc
                """,
                (
                    cursor.pack_key,
                    cursor.output_id,
                    cursor.last_file,
                    cursor.last_row_index,
                    cursor.last_ts_utc,
                    datetime.now(tz=timezone.utc),
                ),
            )

    def _ensure_table(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wsp_checkpoint (
                    pack_key TEXT NOT NULL,
                    output_id TEXT NOT NULL,
                    last_file TEXT NOT NULL,
                    last_row_index INTEGER NOT NULL,
                    last_ts_utc TEXT NULL,
                    updated_at_utc TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (pack_key, output_id)
                )
                """
            )
