"""Postgres-backed indices for IG admission/ops."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg


def is_postgres_dsn(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("postgres://") or value.startswith("postgresql://")


@dataclass
class PostgresAdmissionIndex:
    dsn: str

    def __post_init__(self) -> None:
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
            conn.execute("ALTER TABLE admissions ALTER COLUMN receipt_ref DROP NOT NULL")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS state TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS platform_run_id TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS event_class TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS event_id TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS payload_hash TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS receipt_ref TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS receipt_write_failed INTEGER")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS admitted_at_utc TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS eb_topic TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS eb_partition INTEGER")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS eb_offset TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS eb_offset_kind TEXT")
            conn.execute("ALTER TABLE admissions ADD COLUMN IF NOT EXISTS eb_published_at_utc TEXT")

    def lookup(self, dedupe_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state, payload_hash, receipt_ref, receipt_write_failed, admitted_at_utc,
                       eb_topic, eb_partition, eb_offset, eb_offset_kind, eb_published_at_utc,
                       platform_run_id, event_class, event_id
                FROM admissions WHERE dedupe_key = %s
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
            row = conn.execute(
                """
                INSERT INTO admissions
                (dedupe_key, state, platform_run_id, event_class, event_id, payload_hash, receipt_ref)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dedupe_key) DO NOTHING
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
            return row.rowcount == 1

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
                    state = %s,
                    payload_hash = %s,
                    admitted_at_utc = %s,
                    eb_topic = %s,
                    eb_partition = %s,
                    eb_offset = %s,
                    eb_offset_kind = %s,
                    eb_published_at_utc = %s
                WHERE dedupe_key = %s
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

    def record_ambiguous(self, dedupe_key: str, payload_hash: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE admissions SET
                    state = %s,
                    payload_hash = COALESCE(payload_hash, %s)
                WHERE dedupe_key = %s
                """,
                ("PUBLISH_AMBIGUOUS", payload_hash, dedupe_key),
            )

    def record_receipt(self, dedupe_key: str, receipt_ref: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE admissions SET
                    receipt_ref = %s,
                    receipt_write_failed = 0
                WHERE dedupe_key = %s
                """,
                (receipt_ref, dedupe_key),
            )

    def mark_receipt_failed(self, dedupe_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE admissions SET receipt_write_failed = 1 WHERE dedupe_key = %s",
                (dedupe_key,),
            )

    def probe(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


@dataclass
class PostgresOpsIndex:
    dsn: str

    def __post_init__(self) -> None:
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

    def record_receipt(self, receipt_payload: dict[str, Any], receipt_ref: str) -> None:
        created_at = datetime.now(tz=timezone.utc).isoformat()
        eb_ref = receipt_payload.get("eb_ref") or {}
        policy_rev = receipt_payload.get("policy_rev") or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO receipts
                (receipt_id, event_id, event_type, dedupe_key, decision, eb_topic, eb_partition, eb_offset, eb_offset_kind,
                 policy_id, policy_revision, policy_digest, created_at_utc, receipt_ref, pins_json,
                 reason_codes_json, evidence_refs_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (receipt_id) DO NOTHING
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

    def record_quarantine(self, quarantine_payload: dict[str, Any], quarantine_ref: str, event_id: str | None) -> None:
        created_at = datetime.now(tz=timezone.utc).isoformat()
        policy_rev = quarantine_payload.get("policy_rev") or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO quarantines
                (quarantine_id, event_id, decision, reason_codes_json, policy_id, policy_revision, policy_digest,
                 created_at_utc, evidence_ref, pins_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (quarantine_id) DO NOTHING
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
                    quarantine_ref,
                    _json_dump(quarantine_payload.get("pins")),
                ),
            )

    def lookup_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT receipt_id, event_id, event_type, decision, receipt_ref FROM receipts WHERE receipt_id = %s",
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
                """
                SELECT receipt_id, event_id, event_type, decision, receipt_ref
                FROM receipts WHERE dedupe_key = %s ORDER BY created_at_utc ASC LIMIT 1
                """,
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
                """
                SELECT receipt_id, event_id, event_type, decision, receipt_ref
                FROM receipts WHERE event_id = %s ORDER BY created_at_utc ASC LIMIT 1
                """,
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
        except Exception:
            return False

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


def _json_dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
