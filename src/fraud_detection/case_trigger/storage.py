"""CaseTrigger publish outcome storage (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn


class CaseTriggerStorageError(RuntimeError):
    """Raised when CaseTrigger storage operations fail."""


@dataclass(frozen=True)
class CaseTriggerPublishRecord:
    case_trigger_id: str
    event_id: str
    event_type: str
    publish_decision: str
    receipt_id: str | None
    receipt_ref: str | None
    reason_code: str | None
    actor_principal: str
    actor_source_type: str
    published_at_utc: str
    publish_hash: str


@dataclass(frozen=True)
class CaseTriggerPublishWriteResult:
    status: str
    record: CaseTriggerPublishRecord


class CaseTriggerPublishStore:
    _PUBLISH_DECISIONS = {"ADMIT", "DUPLICATE", "QUARANTINE", "AMBIGUOUS"}

    def __init__(self, *, locator: str) -> None:
        self.locator = locator
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def register_publish_result(
        self,
        *,
        case_trigger_id: str,
        event_id: str,
        event_type: str,
        publish_decision: str,
        receipt: Mapping[str, Any] | None,
        receipt_ref: str | None,
        reason_code: str | None,
        actor_principal: str,
        actor_source_type: str,
        published_at_utc: str,
    ) -> CaseTriggerPublishWriteResult:
        trigger_id = str(case_trigger_id or "").strip()
        if not trigger_id:
            raise CaseTriggerStorageError("case_trigger_id is required")
        normalized_event_id = str(event_id or "").strip()
        normalized_event_type = str(event_type or "").strip()
        actor = str(actor_principal or "").strip()
        source_type = str(actor_source_type or "").strip()
        published_time = str(published_at_utc or "").strip()
        if not normalized_event_id or not normalized_event_type or not actor or not source_type or not published_time:
            raise CaseTriggerStorageError("publish result missing required fields")

        decision = str(publish_decision or "").strip().upper()
        if decision not in self._PUBLISH_DECISIONS:
            raise CaseTriggerStorageError(f"unsupported publish decision: {decision}")

        receipt_id = None
        if isinstance(receipt, Mapping):
            receipt_id_raw = receipt.get("receipt_id")
            receipt_id = str(receipt_id_raw).strip() if receipt_id_raw not in (None, "") else None
        receipt_ref_value = str(receipt_ref).strip() if receipt_ref not in (None, "") else None
        reason = str(reason_code).strip() if reason_code not in (None, "") else None

        publish_identity = {
            "case_trigger_id": trigger_id,
            "event_id": normalized_event_id,
            "event_type": normalized_event_type,
            "publish_decision": decision,
            "receipt_id": receipt_id,
            "receipt_ref": receipt_ref_value,
            "reason_code": reason,
            "actor_principal": actor,
            "actor_source_type": source_type,
        }
        publish_hash = hashlib.sha256(
            json.dumps(
                publish_identity,
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        receipt_json = (
            json.dumps(dict(receipt), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            if isinstance(receipt, Mapping)
            else None
        )

        params = (
            trigger_id,
            normalized_event_id,
            normalized_event_type,
            decision,
            receipt_id,
            receipt_ref_value,
            reason,
            actor,
            source_type,
            published_time,
            publish_hash,
            receipt_json,
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT event_id, event_type, publish_decision, receipt_id, receipt_ref,
                       reason_code, actor_principal, actor_source_type, published_at_utc, publish_hash
                FROM case_trigger_publish
                WHERE case_trigger_id = {p1}
                """,
                (trigger_id,),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO case_trigger_publish (
                        case_trigger_id, event_id, event_type, publish_decision, receipt_id,
                        receipt_ref, reason_code, actor_principal, actor_source_type,
                        published_at_utc, publish_hash, receipt_json
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10}, {p11}, {p12})
                    """,
                    params,
                )
                record = CaseTriggerPublishRecord(
                    case_trigger_id=trigger_id,
                    event_id=normalized_event_id,
                    event_type=normalized_event_type,
                    publish_decision=decision,
                    receipt_id=receipt_id,
                    receipt_ref=receipt_ref_value,
                    reason_code=reason,
                    actor_principal=actor,
                    actor_source_type=source_type,
                    published_at_utc=published_time,
                    publish_hash=publish_hash,
                )
                return CaseTriggerPublishWriteResult(status="NEW", record=record)

            existing = CaseTriggerPublishRecord(
                case_trigger_id=trigger_id,
                event_id=str(row[0]),
                event_type=str(row[1]),
                publish_decision=str(row[2]),
                receipt_id=None if row[3] in (None, "") else str(row[3]),
                receipt_ref=None if row[4] in (None, "") else str(row[4]),
                reason_code=None if row[5] in (None, "") else str(row[5]),
                actor_principal=str(row[6]),
                actor_source_type=str(row[7]),
                published_at_utc=str(row[8]),
                publish_hash=str(row[9]),
            )
            if existing.publish_hash == publish_hash:
                return CaseTriggerPublishWriteResult(status="DUPLICATE", record=existing)
            return CaseTriggerPublishWriteResult(status="HASH_MISMATCH", record=existing)

    def lookup(self, case_trigger_id: str) -> CaseTriggerPublishRecord | None:
        trigger_id = str(case_trigger_id or "").strip()
        if not trigger_id:
            return None
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT event_id, event_type, publish_decision, receipt_id, receipt_ref,
                       reason_code, actor_principal, actor_source_type, published_at_utc, publish_hash
                FROM case_trigger_publish
                WHERE case_trigger_id = {p1}
                """,
                (trigger_id,),
            )
        if row is None:
            return None
        return CaseTriggerPublishRecord(
            case_trigger_id=trigger_id,
            event_id=str(row[0]),
            event_type=str(row[1]),
            publish_decision=str(row[2]),
            receipt_id=None if row[3] in (None, "") else str(row[3]),
            receipt_ref=None if row[4] in (None, "") else str(row[4]),
            reason_code=None if row[5] in (None, "") else str(row[5]),
            actor_principal=str(row[6]),
            actor_source_type=str(row[7]),
            published_at_utc=str(row[8]),
            publish_hash=str(row[9]),
        )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS case_trigger_publish (
                    case_trigger_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    publish_decision TEXT NOT NULL,
                    receipt_id TEXT,
                    receipt_ref TEXT,
                    reason_code TEXT,
                    actor_principal TEXT NOT NULL,
                    actor_source_type TEXT NOT NULL,
                    published_at_utc TEXT NOT NULL,
                    publish_hash TEXT NOT NULL,
                    receipt_json TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_case_trigger_publish_decision
                    ON case_trigger_publish (publish_decision, published_at_utc);
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _render_sql(sql: str, backend: str) -> str:
    if backend == "postgres":
        rendered = sql
        for idx in range(1, 31):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
        return rendered
    rendered = sql
    for idx in range(1, 31):
        rendered = rendered.replace(f"{{p{idx}}}", "?")
    return rendered


def _query_one(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> Any:
    rendered = _render_sql(sql, backend)
    cur = conn.execute(rendered, params) if backend == "sqlite" else conn.cursor().execute(rendered, params)
    return cur.fetchone()


def _execute(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> None:
    rendered = _render_sql(sql, backend)
    if backend == "sqlite":
        conn.execute(rendered, params)
    else:
        conn.cursor().execute(rendered, params)


def _execute_script(conn: Any, backend: str, sql: str) -> None:
    if backend == "sqlite":
        conn.executescript(sql)
    else:
        statements = [item.strip() for item in sql.split(";") if item.strip()]
        cur = conn.cursor()
        for statement in statements:
            cur.execute(statement)
