"""Ops index for receipts/quarantine (query surface)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..platform_runtime import platform_run_prefix


@dataclass
class OpsIndex:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    event_id TEXT,
                    event_type TEXT,
                    dedupe_key TEXT,
                    decision TEXT,
                    eb_topic TEXT,
                    eb_partition INTEGER,
                    eb_offset TEXT,
                    eb_offset_kind TEXT,
                    policy_id TEXT,
                    policy_revision TEXT,
                    policy_digest TEXT,
                    created_at_utc TEXT,
                    receipt_ref TEXT,
                    pins_json TEXT,
                    reason_codes_json TEXT,
                    evidence_refs_json TEXT
                )
                """
            )
            _ensure_columns(
                conn,
                "receipts",
                {
                    "eb_offset": "TEXT",
                    "eb_offset_kind": "TEXT",
                },
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quarantines (
                    quarantine_id TEXT PRIMARY KEY,
                    event_id TEXT,
                    decision TEXT,
                    reason_codes_json TEXT,
                    policy_id TEXT,
                    policy_revision TEXT,
                    policy_digest TEXT,
                    created_at_utc TEXT,
                    evidence_ref TEXT,
                    pins_json TEXT
                )
                """
            )
            conn.commit()

    def record_receipt(self, receipt_payload: dict[str, Any], receipt_ref: str) -> None:
        created_at = datetime.now(tz=timezone.utc).isoformat()
        eb_ref = receipt_payload.get("eb_ref") or {}
        policy_rev = receipt_payload.get("policy_rev") or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO receipts
                (receipt_id, event_id, event_type, dedupe_key, decision, eb_topic, eb_partition, eb_offset, eb_offset_kind,
                 policy_id, policy_revision, policy_digest, created_at_utc, receipt_ref, pins_json,
                 reason_codes_json, evidence_refs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_payload.get("receipt_id"),
                    receipt_payload.get("event_id"),
                    receipt_payload.get("event_type"),
                    receipt_payload.get("dedupe_key"),
                    receipt_payload.get("decision"),
                    eb_ref.get("topic"),
                    eb_ref.get("partition"),
                    eb_ref.get("offset"),
                    eb_ref.get("offset_kind"),
                    policy_rev.get("policy_id"),
                    policy_rev.get("revision"),
                    policy_rev.get("content_digest"),
                    created_at,
                    receipt_ref,
                    _json_dump(receipt_payload.get("pins")),
                    _json_dump(receipt_payload.get("reason_codes")),
                    _json_dump(receipt_payload.get("evidence_refs")),
                ),
            )
            conn.commit()

    def record_quarantine(
        self,
        quarantine_payload: dict[str, Any],
        quarantine_ref: str,
        event_id: str | None,
    ) -> None:
        created_at = datetime.now(tz=timezone.utc).isoformat()
        policy_rev = quarantine_payload.get("policy_rev") or {}
        evidence_ref = quarantine_ref
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO quarantines
                (quarantine_id, event_id, decision, reason_codes_json, policy_id, policy_revision, policy_digest,
                 created_at_utc, evidence_ref, pins_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quarantine_payload.get("quarantine_id"),
                    event_id,
                    quarantine_payload.get("decision"),
                    _json_dump(quarantine_payload.get("reason_codes")),
                    policy_rev.get("policy_id"),
                    policy_rev.get("revision"),
                    policy_rev.get("content_digest"),
                    created_at,
                    evidence_ref,
                    _json_dump(quarantine_payload.get("pins")),
                ),
            )
            conn.commit()

    def lookup_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_id, event_id, event_type, decision, receipt_ref FROM receipts WHERE receipt_id = ?",
                (receipt_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "receipt_id": row[0],
            "event_id": row[1],
            "event_type": row[2],
            "decision": row[3],
            "receipt_ref": row[4],
        }

    def lookup_dedupe(self, dedupe_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_id, event_id, event_type, decision, receipt_ref FROM receipts WHERE dedupe_key = ? ORDER BY created_at_utc ASC LIMIT 1",
                (dedupe_key,),
            ).fetchone()
        if not row:
            return None
        return {
            "receipt_id": row[0],
            "event_id": row[1],
            "event_type": row[2],
            "decision": row[3],
            "receipt_ref": row[4],
        }

    def lookup_event(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_id, event_id, event_type, decision, receipt_ref FROM receipts WHERE event_id = ? ORDER BY created_at_utc ASC LIMIT 1",
                (event_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "receipt_id": row[0],
            "event_id": row[1],
            "event_type": row[2],
            "decision": row[3],
            "receipt_ref": row[4],
        }

    def rebuild_from_store(
        self,
        store: Any,
        receipts_prefix: str | None = None,
        quarantine_prefix: str | None = None,
    ) -> None:
        if receipts_prefix is None or quarantine_prefix is None:
            run_prefix = platform_run_prefix(create_if_missing=False)
            if not run_prefix:
                raise RuntimeError("PLATFORM_RUN_ID required to rebuild ops index from store.")
            receipts_prefix = receipts_prefix or f"{run_prefix}/ig/receipts"
            quarantine_prefix = quarantine_prefix or f"{run_prefix}/ig/quarantine"
        self._clear()
        for payload, ref in _iter_store_json(store, receipts_prefix):
            self.record_receipt(payload, ref)
        for payload, ref in _iter_store_json(store, quarantine_prefix):
            event_id = payload.get("event_id") if isinstance(payload, dict) else None
            self.record_quarantine(payload, ref, event_id)

    def probe(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM receipts")
            conn.execute("DELETE FROM quarantines")
            conn.commit()


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, col_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _iter_store_json(store: Any, prefix: str) -> list[tuple[dict[str, Any], str]]:
    from .store import LocalObjectStore, S3ObjectStore

    results: list[tuple[dict[str, Any], str]] = []
    if isinstance(store, LocalObjectStore):
        root = store.root / prefix
        if root.exists():
            for path in root.glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                results.append((payload, str(path)))
        return results
    if isinstance(store, S3ObjectStore):
        client = store._client  # internal client
        prefix_key = store._key(prefix + "/")
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=store.bucket, Prefix=prefix_key):
            for item in page.get("Contents", []):
                key = item["Key"]
                obj = client.get_object(Bucket=store.bucket, Key=key)
                payload = json.loads(obj["Body"].read().decode("utf-8"))
                results.append((payload, f"s3://{store.bucket}/{key}"))
        return results
    return results
