"""Label Store writer boundary and idempotency corridor (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .contracts import LabelAssertion, LabelStoreContractError


LS_WRITE_ACCEPTED = "ACCEPTED"
LS_WRITE_REJECTED = "REJECTED"

REASON_ASSERTION_COMMITTED_NEW = "ASSERTION_COMMITTED_NEW"
REASON_ASSERTION_REPLAY_MATCH = "ASSERTION_REPLAY_MATCH"
REASON_PAYLOAD_HASH_MISMATCH = "PAYLOAD_HASH_MISMATCH"
REASON_CONTRACT_INVALID = "CONTRACT_INVALID"
REASON_MISSING_EVIDENCE_REFS = "MISSING_EVIDENCE_REFS"
REASON_DEDUPE_TUPLE_COLLISION = "DEDUPE_TUPLE_COLLISION"


class LabelStoreWriterError(RuntimeError):
    """Raised when LS writer operations fail unexpectedly."""


@dataclass(frozen=True)
class LabelStoreWriteResult:
    status: str
    reason_code: str | None = None
    assertion_ref: str | None = None
    label_assertion_id: str | None = None
    replay_count: int = 0
    mismatch_count: int = 0


@dataclass(frozen=True)
class LabelAssertionWriteRecord:
    label_assertion_id: str
    platform_run_id: str
    event_id: str
    label_type: str
    payload_hash: str
    replay_count: int
    mismatch_count: int
    first_committed_at_utc: str
    last_committed_at_utc: str
    assertion_ref: str


class LabelStoreWriterBoundary:
    """Append-safe writer lane that enforces LS idempotency and collision policy."""

    def __init__(self, locator: str | Path) -> None:
        self.locator = str(locator)
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            db_path = Path(_sqlite_path(self.locator))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def write_label_assertion(self, assertion_payload: Mapping[str, Any]) -> LabelStoreWriteResult:
        try:
            assertion = LabelAssertion.from_payload(assertion_payload)
        except LabelStoreContractError as exc:
            return LabelStoreWriteResult(
                status=LS_WRITE_REJECTED,
                reason_code=f"{REASON_CONTRACT_INVALID}:{exc.__class__.__name__}",
            )
        if not assertion.evidence_refs:
            return LabelStoreWriteResult(
                status=LS_WRITE_REJECTED,
                reason_code=REASON_MISSING_EVIDENCE_REFS,
                label_assertion_id=assertion.label_assertion_id,
            )

        assertion_json = _canonical_json(assertion.as_dict())
        committed_at_utc = _utc_now()
        return self._run_write_tx(
            lambda conn: self._write_tx(
                conn=conn,
                assertion=assertion,
                assertion_json=assertion_json,
                committed_at_utc=committed_at_utc,
            )
        )

    def lookup_assertion(self, *, label_assertion_id: str) -> LabelAssertionWriteRecord | None:
        assertion_id = _non_empty(label_assertion_id, "label_assertion_id")
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT platform_run_id, event_id, label_type, payload_hash, replay_count, mismatch_count,
                       first_committed_at_utc, last_committed_at_utc, assertion_ref
                FROM ls_label_assertions
                WHERE label_assertion_id = {p1}
                """,
                (assertion_id,),
            )
        if row is None:
            return None
        return LabelAssertionWriteRecord(
            label_assertion_id=assertion_id,
            platform_run_id=str(row[0]),
            event_id=str(row[1]),
            label_type=str(row[2]),
            payload_hash=str(row[3]),
            replay_count=int(row[4] or 0),
            mismatch_count=int(row[5] or 0),
            first_committed_at_utc=str(row[6]),
            last_committed_at_utc=str(row[7]),
            assertion_ref=str(row[8]),
        )

    def mismatch_count(self, *, label_assertion_id: str) -> int:
        assertion_id = _non_empty(label_assertion_id, "label_assertion_id")
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT COUNT(1)
                FROM ls_label_assertion_mismatches
                WHERE label_assertion_id = {p1}
                """,
                (assertion_id,),
            )
        return int((row[0] if row is not None else 0) or 0)

    def _write_tx(
        self,
        *,
        conn: Any,
        assertion: LabelAssertion,
        assertion_json: str,
        committed_at_utc: str,
    ) -> LabelStoreWriteResult:
        subject = assertion.label_subject_key
        assertion_id = assertion.label_assertion_id
        assertion_ref = _assertion_ref(platform_run_id=subject.platform_run_id, label_assertion_id=assertion_id)
        row = _query_one(
            conn,
            self.backend,
            """
            SELECT platform_run_id, event_id, label_type, payload_hash, replay_count, mismatch_count, assertion_ref
            FROM ls_label_assertions
            WHERE label_assertion_id = {p1}
            """,
            (assertion_id,),
        )
        if row is None:
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO ls_label_assertions (
                    label_assertion_id, platform_run_id, event_id, label_type,
                    payload_hash, assertion_json, replay_count, mismatch_count,
                    first_committed_at_utc, last_committed_at_utc, assertion_ref
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, 0, 0, {p7}, {p8}, {p9})
                """,
                (
                    assertion_id,
                    subject.platform_run_id,
                    subject.event_id,
                    assertion.label_type,
                    assertion.payload_hash,
                    assertion_json,
                    committed_at_utc,
                    committed_at_utc,
                    assertion_ref,
                ),
            )
            return LabelStoreWriteResult(
                status=LS_WRITE_ACCEPTED,
                reason_code=REASON_ASSERTION_COMMITTED_NEW,
                assertion_ref=assertion_ref,
                label_assertion_id=assertion_id,
                replay_count=0,
                mismatch_count=0,
            )

        stored_platform_run_id = str(row[0])
        stored_event_id = str(row[1])
        stored_label_type = str(row[2])
        stored_payload_hash = str(row[3])
        replay_count = int(row[4] or 0)
        mismatch_count = int(row[5] or 0)
        stored_assertion_ref = str(row[6] or assertion_ref)

        if (
            stored_platform_run_id != subject.platform_run_id
            or stored_event_id != subject.event_id
            or stored_label_type != assertion.label_type
        ):
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO ls_label_assertion_mismatches (
                    label_assertion_id, platform_run_id, event_id, label_type,
                    observed_payload_hash, stored_payload_hash, observed_at_utc, assertion_json
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8})
                """,
                (
                    assertion_id,
                    subject.platform_run_id,
                    subject.event_id,
                    assertion.label_type,
                    assertion.payload_hash,
                    stored_payload_hash,
                    committed_at_utc,
                    assertion_json,
                ),
            )
            _execute(
                conn,
                self.backend,
                """
                UPDATE ls_label_assertions
                SET mismatch_count = mismatch_count + 1, last_committed_at_utc = {p1}
                WHERE label_assertion_id = {p2}
                """,
                (committed_at_utc, assertion_id),
            )
            return LabelStoreWriteResult(
                status=LS_WRITE_REJECTED,
                reason_code=REASON_DEDUPE_TUPLE_COLLISION,
                assertion_ref=stored_assertion_ref,
                label_assertion_id=assertion_id,
                replay_count=replay_count,
                mismatch_count=mismatch_count + 1,
            )

        if stored_payload_hash == assertion.payload_hash:
            replay_count += 1
            _execute(
                conn,
                self.backend,
                """
                UPDATE ls_label_assertions
                SET replay_count = {p1}, last_committed_at_utc = {p2}
                WHERE label_assertion_id = {p3}
                """,
                (replay_count, committed_at_utc, assertion_id),
            )
            return LabelStoreWriteResult(
                status=LS_WRITE_ACCEPTED,
                reason_code=REASON_ASSERTION_REPLAY_MATCH,
                assertion_ref=stored_assertion_ref,
                label_assertion_id=assertion_id,
                replay_count=replay_count,
                mismatch_count=mismatch_count,
            )

        mismatch_count += 1
        _execute(
            conn,
            self.backend,
            """
            INSERT INTO ls_label_assertion_mismatches (
                label_assertion_id, platform_run_id, event_id, label_type,
                observed_payload_hash, stored_payload_hash, observed_at_utc, assertion_json
            ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8})
            """,
            (
                assertion_id,
                subject.platform_run_id,
                subject.event_id,
                assertion.label_type,
                assertion.payload_hash,
                stored_payload_hash,
                committed_at_utc,
                assertion_json,
            ),
        )
        _execute(
            conn,
            self.backend,
            """
            UPDATE ls_label_assertions
            SET mismatch_count = {p1}, last_committed_at_utc = {p2}
            WHERE label_assertion_id = {p3}
            """,
            (mismatch_count, committed_at_utc, assertion_id),
        )
        return LabelStoreWriteResult(
            status=LS_WRITE_REJECTED,
            reason_code=REASON_PAYLOAD_HASH_MISMATCH,
            assertion_ref=stored_assertion_ref,
            label_assertion_id=assertion_id,
            replay_count=replay_count,
            mismatch_count=mismatch_count,
        )

    def _run_write_tx(self, func: Any) -> Any:
        with self._connect() as conn:
            if self.backend == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                result = func(conn)
                conn.commit()
                return result
            with conn.transaction():
                return func(conn)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS ls_label_assertions (
                    label_assertion_id TEXT PRIMARY KEY,
                    platform_run_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    label_type TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    assertion_json TEXT NOT NULL,
                    replay_count INTEGER NOT NULL DEFAULT 0,
                    mismatch_count INTEGER NOT NULL DEFAULT 0,
                    first_committed_at_utc TEXT NOT NULL,
                    last_committed_at_utc TEXT NOT NULL,
                    assertion_ref TEXT NOT NULL,
                    UNIQUE(platform_run_id, event_id, label_type, label_assertion_id)
                );
                CREATE INDEX IF NOT EXISTS ix_ls_label_assertions_subject
                    ON ls_label_assertions (platform_run_id, event_id, label_type, first_committed_at_utc);
                CREATE TABLE IF NOT EXISTS ls_label_assertion_mismatches (
                    label_assertion_id TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    label_type TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    assertion_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_ls_label_assertion_mismatches_id
                    ON ls_label_assertion_mismatches (label_assertion_id, observed_at_utc);
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def _assertion_ref(*, platform_run_id: str, label_assertion_id: str) -> str:
    return f"runs/fraud-platform/{platform_run_id}/label_store/assertions/{label_assertion_id}.json"


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LabelStoreWriterError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _render_sql(sql: str, backend: str) -> str:
    rendered = sql
    if backend == "postgres":
        for idx in range(1, 31):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
    else:
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
        return
    statements = [item.strip() for item in sql.split(";") if item.strip()]
    cur = conn.cursor()
    for statement in statements:
        cur.execute(statement)
