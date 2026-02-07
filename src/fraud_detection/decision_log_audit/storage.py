"""Decision Log & Audit storage foundations (Phase 1 lockstep storage kickoff)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.platform_runtime import resolve_run_scoped_path

from .contracts import AuditRecord


class DecisionLogAuditIndexStoreError(RuntimeError):
    """Raised when DLA index operations fail."""


@dataclass(frozen=True)
class DecisionLogAuditStorageLayout:
    object_store_prefix: str
    index_locator: str

    def object_key_for(self, *, platform_run_id: str, audit_id: str) -> str:
        root = self.object_store_prefix.rstrip("/")
        return f"{root}/{platform_run_id}/decision_log_audit/records/{audit_id}.json"


@dataclass(frozen=True)
class DecisionLogAuditIndexWriteResult:
    status: str
    audit_id: str
    record_digest: str


def build_storage_layout(config: Mapping[str, Any] | None = None) -> DecisionLogAuditStorageLayout:
    mapped = dict(config or {})
    object_prefix = str(mapped.get("object_store_prefix") or "fraud-platform").strip()
    index_locator_raw = str(mapped.get("index_locator") or "").strip()
    index_locator = resolve_run_scoped_path(
        index_locator_raw or None,
        suffix="decision_log_audit/dla_index.sqlite",
        create_if_missing=True,
    )
    if not index_locator:
        raise DecisionLogAuditIndexStoreError("failed to resolve DLA index locator")
    return DecisionLogAuditStorageLayout(
        object_store_prefix=object_prefix,
        index_locator=index_locator,
    )


class DecisionLogAuditIndexStore:
    def __init__(self, *, locator: str) -> None:
        self.locator = locator
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def register_audit_record(
        self,
        record: AuditRecord,
        *,
        object_ref: str,
    ) -> DecisionLogAuditIndexWriteResult:
        payload = record.as_dict()
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        params = (
            record.audit_id,
            record.platform_run_id,
            record.scenario_run_id,
            str(payload["decision_event"]["event_id"]),
            str(payload["recorded_at_utc"]),
            digest,
            object_ref,
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                "SELECT record_digest FROM dla_audit_index WHERE audit_id = {p1}",
                (record.audit_id,),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO dla_audit_index (
                        audit_id,
                        platform_run_id,
                        scenario_run_id,
                        decision_event_id,
                        recorded_at_utc,
                        record_digest,
                        object_ref
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7})
                    """,
                    params,
                )
                return DecisionLogAuditIndexWriteResult(
                    status="NEW",
                    audit_id=record.audit_id,
                    record_digest=digest,
                )
            existing_digest = str(row[0])
            if existing_digest == digest:
                return DecisionLogAuditIndexWriteResult(
                    status="DUPLICATE",
                    audit_id=record.audit_id,
                    record_digest=existing_digest,
                )
            return DecisionLogAuditIndexWriteResult(
                status="HASH_MISMATCH",
                audit_id=record.audit_id,
                record_digest=existing_digest,
            )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS dla_audit_index (
                    audit_id TEXT PRIMARY KEY,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    decision_event_id TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL,
                    record_digest TEXT NOT NULL,
                    object_ref TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_dla_audit_index_run_scope
                    ON dla_audit_index (platform_run_id, scenario_run_id, recorded_at_utc);
                CREATE INDEX IF NOT EXISTS ix_dla_audit_index_decision_event
                    ON dla_audit_index (decision_event_id);
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
        for idx in range(1, 10):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
        return rendered
    rendered = sql
    for idx in range(1, 10):
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
        conn.commit()
        return
    cur = conn.cursor()
    cur.execute(rendered, params)
    conn.commit()
    cur.close()


def _execute_script(conn: Any, backend: str, sql: str) -> None:
    if backend == "sqlite":
        conn.executescript(sql)
        conn.commit()
        return
    cur = conn.cursor()
    for statement in [part.strip() for part in sql.split(";") if part.strip()]:
        cur.execute(statement)
    conn.commit()
    cur.close()

