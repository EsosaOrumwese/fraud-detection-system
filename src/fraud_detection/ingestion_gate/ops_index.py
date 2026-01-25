"""Ops index for receipts/quarantine (query surface)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
                    eb_offset INTEGER,
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
                (receipt_id, event_id, event_type, dedupe_key, decision, eb_topic, eb_partition, eb_offset,
                 policy_id, policy_revision, policy_digest, created_at_utc, receipt_ref, pins_json,
                 reason_codes_json, evidence_refs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def lookup_event(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_id, event_id, event_type, decision, receipt_ref FROM receipts WHERE event_id = ?",
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

    def probe(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
