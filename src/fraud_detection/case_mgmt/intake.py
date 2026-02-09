"""CaseTrigger -> CaseMgmt intake boundary (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .contracts import CaseMgmtContractError, CaseTimelineEvent, CaseTrigger


INTAKE_NEW_TRIGGER = "NEW_TRIGGER"
INTAKE_DUPLICATE_TRIGGER = "DUPLICATE_TRIGGER"
INTAKE_TRIGGER_PAYLOAD_MISMATCH = "TRIGGER_PAYLOAD_MISMATCH"

CASE_CREATED = "CASE_CREATED"
CASE_EXISTING = "CASE_EXISTING"

TIMELINE_APPENDED = "TIMELINE_APPENDED"
TIMELINE_NOOP = "TIMELINE_NOOP"


class CaseTriggerIntakeError(RuntimeError):
    """Raised when CM intake operations fail."""


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    case_subject_key: dict[str, str]
    case_subject_hash: str
    pins: dict[str, Any]
    trigger_count: int


@dataclass(frozen=True)
class CaseTriggerIntakeEntry:
    case_trigger_id: str
    case_id: str
    payload_hash: str
    replay_count: int
    mismatch_count: int


@dataclass(frozen=True)
class CaseTimelineRecord:
    case_timeline_event_id: str
    case_id: str
    timeline_event_type: str
    source_ref_id: str
    payload_hash: str


@dataclass(frozen=True)
class CaseTriggerIntakeResult:
    outcome: str
    case_status: str
    timeline_status: str
    case_id: str
    case_trigger_id: str
    timeline_event_id: str
    replay_count: int
    mismatch_count: int


class CaseTriggerIntakeLedger:
    """Idempotent CM intake ledger for CaseTrigger events."""

    def __init__(self, db_path: str | Path) -> None:
        self.locator = str(db_path)
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(self.locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def ingest_case_trigger(
        self,
        *,
        payload: Mapping[str, Any],
        ingested_at_utc: str,
    ) -> CaseTriggerIntakeResult:
        ingested = str(ingested_at_utc or "").strip()
        if not ingested:
            raise CaseTriggerIntakeError("ingested_at_utc is required")
        try:
            trigger = CaseTrigger.from_payload(payload)
        except CaseMgmtContractError as exc:
            raise CaseTriggerIntakeError(f"case trigger intake rejected: {exc}") from exc

        subject_key_json = _canonical_json(trigger.case_subject_key.as_dict())
        subject_hash = _hash_text(subject_key_json)
        trigger_json = _canonical_json(trigger.as_dict())
        trigger_hash = _hash_text(trigger_json)
        timeline = _build_trigger_timeline_event(trigger)

        with self._connect() as conn:
            if self.backend == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                return self._ingest_tx(
                    conn=conn,
                    trigger=trigger,
                    ingested_at_utc=ingested,
                    subject_key_json=subject_key_json,
                    subject_hash=subject_hash,
                    trigger_json=trigger_json,
                    trigger_hash=trigger_hash,
                    timeline=timeline,
                )
            with conn.transaction():
                return self._ingest_tx(
                    conn=conn,
                    trigger=trigger,
                    ingested_at_utc=ingested,
                    subject_key_json=subject_key_json,
                    subject_hash=subject_hash,
                    trigger_json=trigger_json,
                    trigger_hash=trigger_hash,
                    timeline=timeline,
                )

    def lookup_case(self, case_id: str) -> CaseRecord | None:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT case_subject_key_json, case_subject_hash, pins_json, trigger_count
                FROM cm_cases
                WHERE case_id = {p1}
                """,
                (case_id,),
            )
        if row is None:
            return None
        return CaseRecord(
            case_id=case_id,
            case_subject_key=_json_to_dict(row[0]),
            case_subject_hash=str(row[1]),
            pins=_json_to_dict(row[2]),
            trigger_count=int(row[3] or 0),
        )

    def lookup_trigger(self, case_trigger_id: str) -> CaseTriggerIntakeEntry | None:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT case_id, payload_hash, replay_count, mismatch_count
                FROM cm_case_trigger_intake
                WHERE case_trigger_id = {p1}
                """,
                (case_trigger_id,),
            )
        if row is None:
            return None
        return CaseTriggerIntakeEntry(
            case_trigger_id=case_trigger_id,
            case_id=str(row[0]),
            payload_hash=str(row[1]),
            replay_count=int(row[2] or 0),
            mismatch_count=int(row[3] or 0),
        )

    def list_timeline_events(self, case_id: str) -> list[CaseTimelineRecord]:
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT case_timeline_event_id, timeline_event_type, source_ref_id, payload_hash
                FROM cm_case_timeline
                WHERE case_id = {p1}
                ORDER BY created_at_utc ASC, case_timeline_event_id ASC
                """,
                (case_id,),
            )
        return [
            CaseTimelineRecord(
                case_timeline_event_id=str(row[0]),
                case_id=case_id,
                timeline_event_type=str(row[1]),
                source_ref_id=str(row[2]),
                payload_hash=str(row[3]),
            )
            for row in rows
        ]

    def _ingest_tx(
        self,
        *,
        conn: Any,
        trigger: CaseTrigger,
        ingested_at_utc: str,
        subject_key_json: str,
        subject_hash: str,
        trigger_json: str,
        trigger_hash: str,
        timeline: CaseTimelineEvent,
    ) -> CaseTriggerIntakeResult:
        case_row = _query_one(
            conn,
            self.backend,
            "SELECT case_subject_hash FROM cm_cases WHERE case_id = {p1}",
            (trigger.case_id,),
        )
        if case_row is None:
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO cm_cases (
                    case_id, case_subject_hash, case_subject_key_json, pins_json,
                    first_observed_time, last_observed_time, trigger_count,
                    created_at_utc, updated_at_utc
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, 0, {p7}, {p8})
                """,
                (
                    trigger.case_id,
                    subject_hash,
                    subject_key_json,
                    _canonical_json(trigger.pins),
                    trigger.observed_time,
                    trigger.observed_time,
                    ingested_at_utc,
                    ingested_at_utc,
                ),
            )
            case_status = CASE_CREATED
        else:
            if str(case_row[0] or "") != subject_hash:
                raise CaseTriggerIntakeError("no-merge violation: case_id maps to different subject")
            case_status = CASE_EXISTING

        row = _query_one(
            conn,
            self.backend,
            """
            SELECT payload_hash, replay_count, mismatch_count
            FROM cm_case_trigger_intake
            WHERE case_trigger_id = {p1}
            """,
            (trigger.case_trigger_id,),
        )
        if row is None:
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO cm_case_trigger_intake (
                    case_trigger_id, case_id, trigger_type, source_ref_id, payload_hash, trigger_json,
                    observed_time, first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, 0, 0)
                """,
                (
                    trigger.case_trigger_id,
                    trigger.case_id,
                    trigger.trigger_type,
                    trigger.source_ref_id,
                    trigger_hash,
                    trigger_json,
                    trigger.observed_time,
                    ingested_at_utc,
                    ingested_at_utc,
                ),
            )
            outcome = INTAKE_NEW_TRIGGER
            replay_count = 0
            mismatch_count = 0
        else:
            stored_hash = str(row[0] or "")
            replay_count = int(row[1] or 0)
            mismatch_count = int(row[2] or 0)
            if stored_hash == trigger_hash:
                replay_count += 1
                _execute(
                    conn,
                    self.backend,
                    """
                    UPDATE cm_case_trigger_intake
                    SET replay_count = {p1}, last_seen_at_utc = {p2}
                    WHERE case_trigger_id = {p3}
                    """,
                    (replay_count, ingested_at_utc, trigger.case_trigger_id),
                )
                outcome = INTAKE_DUPLICATE_TRIGGER
            else:
                mismatch_count += 1
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO cm_case_trigger_mismatches (
                        case_trigger_id, observed_payload_hash, stored_payload_hash, observed_at_utc, trigger_json
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5})
                    """,
                    (
                        trigger.case_trigger_id,
                        trigger_hash,
                        stored_hash,
                        ingested_at_utc,
                        trigger_json,
                    ),
                )
                _execute(
                    conn,
                    self.backend,
                    """
                    UPDATE cm_case_trigger_intake
                    SET mismatch_count = {p1}, last_seen_at_utc = {p2}
                    WHERE case_trigger_id = {p3}
                    """,
                    (mismatch_count, ingested_at_utc, trigger.case_trigger_id),
                )
                outcome = INTAKE_TRIGGER_PAYLOAD_MISMATCH

        timeline_status = TIMELINE_NOOP
        if outcome == INTAKE_NEW_TRIGGER:
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO cm_case_timeline (
                    case_timeline_event_id, case_id, timeline_event_type, source_ref_id,
                    payload_hash, event_json, observed_time, created_at_utc
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8})
                """,
                (
                    timeline.case_timeline_event_id,
                    timeline.case_id,
                    timeline.timeline_event_type,
                    timeline.source_ref_id,
                    timeline.payload_hash,
                    _canonical_json(timeline.as_dict()),
                    timeline.observed_time,
                    ingested_at_utc,
                ),
            )
            _execute(
                conn,
                self.backend,
                """
                UPDATE cm_cases
                SET trigger_count = trigger_count + 1, last_observed_time = {p1}, updated_at_utc = {p2}
                WHERE case_id = {p3}
                """,
                (trigger.observed_time, ingested_at_utc, trigger.case_id),
            )
            timeline_status = TIMELINE_APPENDED
        else:
            _execute(
                conn,
                self.backend,
                "UPDATE cm_cases SET updated_at_utc = {p1} WHERE case_id = {p2}",
                (ingested_at_utc, trigger.case_id),
            )

        return CaseTriggerIntakeResult(
            outcome=outcome,
            case_status=case_status,
            timeline_status=timeline_status,
            case_id=trigger.case_id,
            case_trigger_id=trigger.case_trigger_id,
            timeline_event_id=timeline.case_timeline_event_id,
            replay_count=replay_count,
            mismatch_count=mismatch_count,
        )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS cm_cases (
                    case_id TEXT PRIMARY KEY,
                    case_subject_hash TEXT NOT NULL UNIQUE,
                    case_subject_key_json TEXT NOT NULL,
                    pins_json TEXT NOT NULL,
                    first_observed_time TEXT NOT NULL,
                    last_observed_time TEXT NOT NULL,
                    trigger_count INTEGER NOT NULL DEFAULT 0,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cm_case_trigger_intake (
                    case_trigger_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    source_ref_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    trigger_json TEXT NOT NULL,
                    observed_time TEXT NOT NULL,
                    first_seen_at_utc TEXT NOT NULL,
                    last_seen_at_utc TEXT NOT NULL,
                    replay_count INTEGER NOT NULL DEFAULT 0,
                    mismatch_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS cm_case_trigger_mismatches (
                    case_trigger_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    trigger_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cm_case_timeline (
                    case_timeline_event_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    timeline_event_type TEXT NOT NULL,
                    source_ref_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    observed_time TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    UNIQUE(case_id, timeline_event_type, source_ref_id)
                );
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def _build_trigger_timeline_event(trigger: CaseTrigger) -> CaseTimelineEvent:
    return CaseTimelineEvent.from_payload(
        {
            "case_id": trigger.case_id,
            "timeline_event_type": "CASE_TRIGGERED",
            "source_ref_id": trigger.case_trigger_id,
            "pins": trigger.pins,
            "observed_time": trigger.observed_time,
            "evidence_refs": [item.as_dict() for item in trigger.evidence_refs],
            "case_subject_key": trigger.case_subject_key.as_dict(),
            "timeline_payload": {
                "case_trigger_id": trigger.case_trigger_id,
                "trigger_type": trigger.trigger_type,
                "source_ref_id": trigger.source_ref_id,
            },
        }
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_to_dict(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


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


def _query_all(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    rendered = _render_sql(sql, backend)
    cur = conn.execute(rendered, params) if backend == "sqlite" else conn.cursor().execute(rendered, params)
    return list(cur.fetchall())


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
