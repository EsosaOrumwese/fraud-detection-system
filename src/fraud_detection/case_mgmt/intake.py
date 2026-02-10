"""CaseTrigger -> CaseMgmt intake boundary (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
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

TIMELINE_EVENT_NEW = "TIMELINE_EVENT_NEW"
TIMELINE_EVENT_DUPLICATE = "TIMELINE_EVENT_DUPLICATE"
TIMELINE_EVENT_PAYLOAD_MISMATCH = "TIMELINE_EVENT_PAYLOAD_MISMATCH"

SOURCE_TYPE_SYSTEM = "SYSTEM"
SOURCE_TYPE_HUMAN = "HUMAN"
SOURCE_TYPE_EXTERNAL = "EXTERNAL"
SOURCE_TYPE_AUTO = "AUTO"
SOURCE_TYPE_VALUES: frozenset[str] = frozenset(
    {
        SOURCE_TYPE_SYSTEM,
        SOURCE_TYPE_HUMAN,
        SOURCE_TYPE_EXTERNAL,
        SOURCE_TYPE_AUTO,
    }
)


class CaseTriggerIntakeError(RuntimeError):
    """Raised when CM intake operations fail."""


@dataclass(frozen=True)
class CaseRecord:
    case_id: str
    case_subject_key: dict[str, str]
    case_subject_hash: str
    pins: dict[str, Any]
    trigger_count: int
    first_observed_time: str
    last_observed_time: str


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
    observed_time: str
    created_at_utc: str
    actor_id: str
    source_type: str
    event_payload: dict[str, Any]


@dataclass(frozen=True)
class CaseTimelineAppendResult:
    outcome: str
    case_id: str
    case_timeline_event_id: str
    replay_count: int
    mismatch_count: int


@dataclass(frozen=True)
class CaseWorkflowProjection:
    case_id: str
    status: str
    queue_state: str
    is_open: bool
    pending_label_write: bool
    pending_action_outcome: bool
    last_activity_observed_time: str
    event_count: int
    assignee: str | None = None


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
                SELECT case_subject_key_json, case_subject_hash, pins_json, trigger_count,
                       first_observed_time, last_observed_time
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
            first_observed_time=str(row[4]),
            last_observed_time=str(row[5]),
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
                SELECT t.case_timeline_event_id,
                       t.timeline_event_type,
                       t.source_ref_id,
                       t.payload_hash,
                       t.event_json,
                       t.observed_time,
                       t.created_at_utc,
                       COALESCE(s.actor_id, 'SYSTEM::unknown') AS actor_id,
                       COALESCE(s.source_type, 'SYSTEM') AS source_type
                FROM cm_case_timeline t
                LEFT JOIN cm_case_timeline_stats s
                  ON s.case_timeline_event_id = t.case_timeline_event_id
                WHERE t.case_id = {p1}
                ORDER BY t.observed_time ASC, t.case_timeline_event_id ASC
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
                event_payload=_json_to_dict(row[4]),
                observed_time=str(row[5]),
                created_at_utc=str(row[6]),
                actor_id=str(row[7]),
                source_type=str(row[8]),
            )
            for row in rows
        ]

    def append_timeline_event(
        self,
        *,
        payload: Mapping[str, Any],
        actor_id: str,
        source_type: str,
        appended_at_utc: str,
    ) -> CaseTimelineAppendResult:
        appended = _require_non_empty(appended_at_utc, "appended_at_utc")
        actor = _require_non_empty(actor_id, "actor_id")
        source = _normalize_source_type(source_type)
        try:
            event = CaseTimelineEvent.from_payload(payload)
        except CaseMgmtContractError as exc:
            raise CaseTriggerIntakeError(f"case timeline append rejected: {exc}") from exc

        if self.lookup_case(event.case_id) is None:
            raise CaseTriggerIntakeError(f"unknown case_id for timeline append: {event.case_id}")

        event_payload = _with_actor_metadata(event=event, actor_id=actor, source_type=source)
        event_json = _canonical_json(event_payload)
        event_hash = _hash_text(event_json)
        links = _extract_timeline_links(event=event)

        with self._connect() as conn:
            if self.backend == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                return self._append_timeline_tx(
                    conn=conn,
                    event=event,
                    actor_id=actor,
                    source_type=source,
                    event_hash=event_hash,
                    event_json=event_json,
                    links=links,
                    appended_at_utc=appended,
                )
            with conn.transaction():
                return self._append_timeline_tx(
                    conn=conn,
                    event=event,
                    actor_id=actor,
                    source_type=source,
                    event_hash=event_hash,
                    event_json=event_json,
                    links=links,
                    appended_at_utc=appended,
                )

    def project_case(self, case_id: str) -> CaseWorkflowProjection | None:
        case = self.lookup_case(case_id)
        if case is None:
            return None
        timeline = self.list_timeline_events(case_id)
        return _project_case(case=case, timeline=timeline)

    def find_case_ids_by_linked_ref(self, *, ref_type: str, ref_id: str) -> tuple[str, ...]:
        normalized_type = _normalize_ref_type(ref_type)
        normalized_id = _require_non_empty(ref_id, "ref_id")
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT DISTINCT case_id
                FROM cm_case_timeline_links
                WHERE ref_type = {p1} AND ref_id = {p2}
                ORDER BY case_id ASC
                """,
                (normalized_type, normalized_id),
            )
        return tuple(str(row[0]) for row in rows)

    def query_case_projections(
        self,
        *,
        status: str | None = None,
        queue_state: str | None = None,
        ref_type: str | None = None,
        ref_id: str | None = None,
        observed_from_utc: str | None = None,
        observed_to_utc: str | None = None,
    ) -> tuple[CaseWorkflowProjection, ...]:
        status_filter = str(status or "").strip().upper() or None
        queue_filter = str(queue_state or "").strip().lower() or None
        observed_from = str(observed_from_utc or "").strip() or None
        observed_to = str(observed_to_utc or "").strip() or None

        case_ids: tuple[str, ...]
        if ref_type is not None and ref_id is not None:
            case_ids = self.find_case_ids_by_linked_ref(ref_type=ref_type, ref_id=ref_id)
        else:
            with self._connect() as conn:
                rows = _query_all(
                    conn,
                    self.backend,
                    "SELECT case_id FROM cm_cases ORDER BY case_id ASC",
                    tuple(),
                )
            case_ids = tuple(str(row[0]) for row in rows)

        projections: list[CaseWorkflowProjection] = []
        for case_id in case_ids:
            projection = self.project_case(case_id)
            if projection is None:
                continue
            if status_filter is not None and projection.status != status_filter:
                continue
            if queue_filter is not None and projection.queue_state != queue_filter:
                continue
            if observed_from is not None and projection.last_activity_observed_time < observed_from:
                continue
            if observed_to is not None and projection.last_activity_observed_time > observed_to:
                continue
            projections.append(projection)
        projections.sort(
            key=lambda item: (item.last_activity_observed_time, item.case_id),
            reverse=True,
        )
        return tuple(projections)

    def _append_timeline_tx(
        self,
        *,
        conn: Any,
        event: CaseTimelineEvent,
        actor_id: str,
        source_type: str,
        event_hash: str,
        event_json: str,
        links: tuple[tuple[str, str], ...],
        appended_at_utc: str,
    ) -> CaseTimelineAppendResult:
        row = _query_one(
            conn,
            self.backend,
            """
            SELECT payload_hash
            FROM cm_case_timeline
            WHERE case_timeline_event_id = {p1}
            """,
            (event.case_timeline_event_id,),
        )
        if row is None:
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
                    event.case_timeline_event_id,
                    event.case_id,
                    event.timeline_event_type,
                    event.source_ref_id,
                    event_hash,
                    event_json,
                    event.observed_time,
                    appended_at_utc,
                ),
            )
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO cm_case_timeline_stats (
                    case_timeline_event_id, replay_count, mismatch_count, actor_id, source_type, last_seen_at_utc
                ) VALUES ({p1}, 0, 0, {p2}, {p3}, {p4})
                ON CONFLICT (case_timeline_event_id) DO NOTHING
                """,
                (event.case_timeline_event_id, actor_id, source_type, appended_at_utc),
            )
            _insert_timeline_links(
                conn=conn,
                backend=self.backend,
                case_timeline_event_id=event.case_timeline_event_id,
                case_id=event.case_id,
                observed_time=event.observed_time,
                links=links,
            )
            _execute(
                conn,
                self.backend,
                """
                UPDATE cm_cases
                SET updated_at_utc = {p1},
                    last_observed_time = CASE
                        WHEN last_observed_time < {p2} THEN {p4}
                        ELSE last_observed_time
                    END
                WHERE case_id = {p3}
                """,
                (appended_at_utc, event.observed_time, event.case_id, event.observed_time),
            )
            return CaseTimelineAppendResult(
                outcome=TIMELINE_EVENT_NEW,
                case_id=event.case_id,
                case_timeline_event_id=event.case_timeline_event_id,
                replay_count=0,
                mismatch_count=0,
            )

        stored_hash = str(row[0] or "")
        stats = _query_one(
            conn,
            self.backend,
            """
            SELECT replay_count, mismatch_count
            FROM cm_case_timeline_stats
            WHERE case_timeline_event_id = {p1}
            """,
            (event.case_timeline_event_id,),
        )
        if stats is None:
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO cm_case_timeline_stats (
                    case_timeline_event_id, replay_count, mismatch_count, actor_id, source_type, last_seen_at_utc
                ) VALUES ({p1}, 0, 0, {p2}, {p3}, {p4})
                ON CONFLICT (case_timeline_event_id) DO NOTHING
                """,
                (event.case_timeline_event_id, actor_id, source_type, appended_at_utc),
            )
            replay_count = 0
            mismatch_count = 0
        else:
            replay_count = int(stats[0] or 0)
            mismatch_count = int(stats[1] or 0)
        if stored_hash == event_hash:
            replay_count += 1
            _execute(
                conn,
                self.backend,
                """
                UPDATE cm_case_timeline_stats
                SET replay_count = {p1}, last_seen_at_utc = {p2}
                WHERE case_timeline_event_id = {p3}
                """,
                (replay_count, appended_at_utc, event.case_timeline_event_id),
            )
            _execute(
                conn,
                self.backend,
                "UPDATE cm_cases SET updated_at_utc = {p1} WHERE case_id = {p2}",
                (appended_at_utc, event.case_id),
            )
            return CaseTimelineAppendResult(
                outcome=TIMELINE_EVENT_DUPLICATE,
                case_id=event.case_id,
                case_timeline_event_id=event.case_timeline_event_id,
                replay_count=replay_count,
                mismatch_count=mismatch_count,
            )

        mismatch_count += 1
        _execute(
            conn,
            self.backend,
            """
            INSERT INTO cm_case_timeline_mismatches (
                case_timeline_event_id, observed_payload_hash, stored_payload_hash, observed_at_utc, event_json
            ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5})
            """,
            (
                event.case_timeline_event_id,
                event_hash,
                stored_hash,
                appended_at_utc,
                event_json,
            ),
        )
        _execute(
            conn,
            self.backend,
            """
            UPDATE cm_case_timeline_stats
            SET mismatch_count = {p1}, last_seen_at_utc = {p2}
            WHERE case_timeline_event_id = {p3}
            """,
            (mismatch_count, appended_at_utc, event.case_timeline_event_id),
        )
        _execute(
            conn,
            self.backend,
            "UPDATE cm_cases SET updated_at_utc = {p1} WHERE case_id = {p2}",
            (appended_at_utc, event.case_id),
        )
        return CaseTimelineAppendResult(
            outcome=TIMELINE_EVENT_PAYLOAD_MISMATCH,
            case_id=event.case_id,
            case_timeline_event_id=event.case_timeline_event_id,
            replay_count=replay_count,
            mismatch_count=mismatch_count,
        )

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
        timeline_payload = _with_actor_metadata(
            event=timeline,
            actor_id="SYSTEM::case_trigger_intake",
            source_type=SOURCE_TYPE_SYSTEM,
        )
        timeline_json = _canonical_json(timeline_payload)
        timeline_hash = _hash_text(timeline_json)
        timeline_links = _extract_timeline_links(event=timeline)
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
                    timeline_hash,
                    timeline_json,
                    timeline.observed_time,
                    ingested_at_utc,
                ),
            )
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO cm_case_timeline_stats (
                    case_timeline_event_id, replay_count, mismatch_count, actor_id, source_type, last_seen_at_utc
                ) VALUES ({p1}, 0, 0, {p2}, {p3}, {p4})
                ON CONFLICT (case_timeline_event_id) DO NOTHING
                """,
                (
                    timeline.case_timeline_event_id,
                    "SYSTEM::case_trigger_intake",
                    SOURCE_TYPE_SYSTEM,
                    ingested_at_utc,
                ),
            )
            _insert_timeline_links(
                conn=conn,
                backend=self.backend,
                case_timeline_event_id=timeline.case_timeline_event_id,
                case_id=timeline.case_id,
                observed_time=timeline.observed_time,
                links=timeline_links,
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
                CREATE TABLE IF NOT EXISTS cm_case_timeline_stats (
                    case_timeline_event_id TEXT PRIMARY KEY,
                    replay_count INTEGER NOT NULL DEFAULT 0,
                    mismatch_count INTEGER NOT NULL DEFAULT 0,
                    actor_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    last_seen_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cm_case_timeline_mismatches (
                    case_timeline_event_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    event_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cm_case_timeline_links (
                    case_timeline_event_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    ref_type TEXT NOT NULL,
                    ref_id TEXT NOT NULL,
                    observed_time TEXT NOT NULL,
                    UNIQUE(case_timeline_event_id, ref_type, ref_id)
                );
                CREATE INDEX IF NOT EXISTS ix_cm_case_timeline_links_ref
                    ON cm_case_timeline_links (ref_type, ref_id, observed_time);
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


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseTriggerIntakeError(f"{field_name} is required")
    return text


def _normalize_source_type(value: str) -> str:
    normalized = _require_non_empty(value, "source_type").upper()
    if normalized not in SOURCE_TYPE_VALUES:
        allowed = ",".join(sorted(SOURCE_TYPE_VALUES))
        raise CaseTriggerIntakeError(f"unsupported source_type: {normalized!r}; allowed={allowed}")
    return normalized


def _normalize_ref_type(value: str) -> str:
    normalized = _require_non_empty(value, "ref_type").lower()
    allowed = {
        "event_id",
        "decision_id",
        "action_outcome_id",
        "audit_record_id",
        "case_trigger_id",
        "case_event_id",
        "source_ref_id",
    }
    if normalized not in allowed:
        supported = ",".join(sorted(allowed))
        raise CaseTriggerIntakeError(f"unsupported ref_type: {normalized!r}; allowed={supported}")
    return normalized


def _with_actor_metadata(*, event: CaseTimelineEvent, actor_id: str, source_type: str) -> dict[str, Any]:
    payload = event.as_dict()
    timeline_payload_raw = payload.get("timeline_payload")
    timeline_payload = dict(timeline_payload_raw) if isinstance(timeline_payload_raw, Mapping) else {}
    timeline_payload["actor_id"] = actor_id
    timeline_payload["source_type"] = source_type
    payload["timeline_payload"] = timeline_payload
    return payload


def _extract_timeline_links(*, event: CaseTimelineEvent) -> tuple[tuple[str, str], ...]:
    refs: set[tuple[str, str]] = set()
    refs.add(("case_event_id", event.case_timeline_event_id))
    refs.add(("source_ref_id", event.source_ref_id))
    if event.timeline_event_type == "CASE_TRIGGERED":
        refs.add(("case_trigger_id", event.source_ref_id))
    if event.case_subject_key is not None:
        event_id = str(event.case_subject_key.event_id or "").strip()
        if event_id:
            refs.add(("event_id", event_id))
    for evidence in event.evidence_refs:
        if evidence.ref_type == "DECISION":
            refs.add(("decision_id", evidence.ref_id))
        elif evidence.ref_type == "ACTION_OUTCOME":
            refs.add(("action_outcome_id", evidence.ref_id))
        elif evidence.ref_type == "DLA_AUDIT_RECORD":
            refs.add(("audit_record_id", evidence.ref_id))
        elif evidence.ref_type == "CASE_EVENT":
            refs.add(("case_event_id", evidence.ref_id))

    if event.source_ref_id.startswith("decision:"):
        refs.add(("decision_id", event.source_ref_id.split(":", 1)[1]))
    elif event.source_ref_id.startswith("action_outcome:"):
        refs.add(("action_outcome_id", event.source_ref_id.split(":", 1)[1]))
    elif event.source_ref_id.startswith("audit:"):
        refs.add(("audit_record_id", event.source_ref_id.split(":", 1)[1]))

    timeline_payload = event.timeline_payload
    for key, ref_type in (
        ("event_id", "event_id"),
        ("decision_id", "decision_id"),
        ("action_outcome_id", "action_outcome_id"),
        ("audit_record_id", "audit_record_id"),
    ):
        value = str(timeline_payload.get(key) or "").strip()
        if value:
            refs.add((ref_type, value))
    return tuple(sorted(refs))


def _insert_timeline_links(
    *,
    conn: Any,
    backend: str,
    case_timeline_event_id: str,
    case_id: str,
    observed_time: str,
    links: tuple[tuple[str, str], ...],
) -> None:
    for ref_type, ref_id in links:
        _execute(
            conn,
            backend,
            """
            INSERT INTO cm_case_timeline_links (
                case_timeline_event_id, case_id, ref_type, ref_id, observed_time
            ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5})
            ON CONFLICT (case_timeline_event_id, ref_type, ref_id) DO NOTHING
            """,
            (case_timeline_event_id, case_id, ref_type, ref_id, observed_time),
        )


def _project_case(*, case: CaseRecord, timeline: list[CaseTimelineRecord]) -> CaseWorkflowProjection:
    status = "NEW"
    queue_state = "triage"
    is_open = True
    pending_label_write = False
    pending_action_outcome = False
    assignee: str | None = None
    last_activity = case.last_observed_time
    for event in timeline:
        event_type = event.timeline_event_type
        payload = event.event_payload.get("timeline_payload")
        timeline_payload = dict(payload) if isinstance(payload, Mapping) else {}
        if event_type == "INVESTIGATOR_ASSERTION":
            status = "IN_PROGRESS"
            queue_state = "investigation"
            is_open = True
            assignee_value = str(timeline_payload.get("assignee") or "").strip()
            if assignee_value:
                assignee = assignee_value
        elif event_type == "ACTION_INTENT_REQUESTED":
            submit_status = str(timeline_payload.get("submit_status") or "REQUESTED").strip().upper()
            if submit_status in {"PRECHECK_REJECTED", "SUBMIT_FAILED_FATAL"}:
                status = "ACTION_FAILED"
                queue_state = "triage"
                pending_action_outcome = False
            else:
                status = "ACTION_PENDING"
                queue_state = "pending_action"
                pending_action_outcome = True
            is_open = True
        elif event_type == "ACTION_OUTCOME_ATTACHED":
            pending_action_outcome = False
            outcome_status = str(timeline_payload.get("outcome_status") or "").strip().upper()
            if outcome_status in {"FAILED", "DENIED", "TIMED_OUT", "UNKNOWN"}:
                status = "ACTION_FAILED"
                queue_state = "triage"
            else:
                status = "IN_PROGRESS"
                queue_state = "investigation"
            is_open = True
        elif event_type == "LABEL_PENDING":
            pending_label_write = True
            status = "LABEL_PENDING"
            queue_state = "pending_label"
            is_open = True
        elif event_type == "LABEL_ACCEPTED":
            pending_label_write = False
            status = "RESOLVED"
            queue_state = "resolved"
            is_open = False
        elif event_type == "LABEL_REJECTED":
            pending_label_write = False
            status = "LABEL_REJECTED"
            queue_state = "triage"
            is_open = True
        if event.observed_time > last_activity:
            last_activity = event.observed_time

    return CaseWorkflowProjection(
        case_id=case.case_id,
        status=status,
        queue_state=queue_state,
        is_open=is_open,
        pending_label_write=pending_label_write,
        pending_action_outcome=pending_action_outcome,
        last_activity_observed_time=last_activity,
        event_count=len(timeline),
        assignee=assignee,
    )


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _render_sql(sql: str, backend: str) -> str:
    placeholder = "%s" if backend == "postgres" else "?"
    return _SQL_PARAM_PATTERN.sub(placeholder, sql)


_SQL_PARAM_PATTERN = re.compile(r"\{p(?P<index>\d+)\}")


def _render_sql_with_params(sql: str, backend: str, params: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]]:
    ordered_params: list[Any] = []
    placeholder = "%s" if backend == "postgres" else "?"

    def _replace(match: re.Match[str]) -> str:
        index = int(match.group("index"))
        if index <= 0 or index > len(params):
            raise CaseTriggerIntakeError(
                f"SQL placeholder index p{index} out of range for {len(params)} params"
            )
        ordered_params.append(params[index - 1])
        return placeholder

    rendered = _SQL_PARAM_PATTERN.sub(_replace, sql)
    return rendered, tuple(ordered_params)


def _query_one(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> Any:
    rendered, ordered_params = _render_sql_with_params(sql, backend, params)
    if backend == "sqlite":
        cur = conn.execute(rendered, ordered_params)
        return cur.fetchone()
    cur = conn.cursor()
    cur.execute(rendered, ordered_params)
    row = cur.fetchone()
    cur.close()
    return row


def _query_all(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    rendered, ordered_params = _render_sql_with_params(sql, backend, params)
    if backend == "sqlite":
        cur = conn.execute(rendered, ordered_params)
        return list(cur.fetchall())
    cur = conn.cursor()
    cur.execute(rendered, ordered_params)
    rows = list(cur.fetchall())
    cur.close()
    return rows


def _execute(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> None:
    rendered, ordered_params = _render_sql_with_params(sql, backend, params)
    if backend == "sqlite":
        conn.execute(rendered, ordered_params)
        return
    cur = conn.cursor()
    cur.execute(rendered, ordered_params)
    cur.close()


def _execute_script(conn: Any, backend: str, sql: str) -> None:
    if backend == "sqlite":
        conn.executescript(sql)
        return
    statements = [item.strip() for item in sql.split(";") if item.strip()]
    cur = conn.cursor()
    for statement in statements:
        cur.execute(statement)
    cur.close()
