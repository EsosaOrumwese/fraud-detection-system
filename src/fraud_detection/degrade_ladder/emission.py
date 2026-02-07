"""DL posture-change emission lane (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Protocol

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .contracts import DegradeDecision


GLOBAL_MANIFEST_SENTINEL = "0" * 64
OUTBOX_PENDING = "PENDING"
OUTBOX_FAILED = "FAILED"
OUTBOX_SENT = "SENT"
OUTBOX_DEAD = "DEAD"


class DlEmissionError(RuntimeError):
    """Raised when emission outbox operations fail."""


class DlControlPublisher(Protocol):
    def publish(self, event: dict[str, Any]) -> None:
        """Publish a single control event."""


@dataclass(frozen=True)
class DlOutboxRecord:
    scope_key: str
    posture_seq: int
    event_id: str
    event_json: str
    status: str
    attempt_count: int
    next_attempt_at_utc: str
    decided_at_utc: str
    last_error: str | None


@dataclass(frozen=True)
class DlDrainResult:
    considered: int
    published: int
    failed: int
    dead_lettered: int
    pending_backlog: int


@dataclass(frozen=True)
class DlEmissionMetrics:
    pending_count: int
    failed_count: int
    dead_letter_count: int
    sent_count: int
    oldest_pending_age_seconds: int | None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "pending_count": self.pending_count,
            "failed_count": self.failed_count,
            "dead_letter_count": self.dead_letter_count,
            "sent_count": self.sent_count,
            "oldest_pending_age_seconds": self.oldest_pending_age_seconds,
        }


def build_outbox_store(dsn: str, *, stream_id: str) -> "DlOutboxStore":
    if is_postgres_dsn(dsn):
        return PostgresDlOutboxStore(dsn=dsn, stream_id=stream_id)
    return SqliteDlOutboxStore(path=Path(_sqlite_path(dsn)), stream_id=stream_id)


def deterministic_posture_event_id(*, scope_key: str, posture_seq: int) -> str:
    normalized_scope = _normalize_scope(scope_key)
    if not isinstance(posture_seq, int) or posture_seq < 0:
        raise DlEmissionError("posture_seq must be a non-negative integer")
    digest_input = f"{normalized_scope}|{posture_seq}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def build_posture_change_event(
    *,
    scope_key: str,
    decision: DegradeDecision,
    change_kind: str,
    triggers_summary: tuple[str, ...] = (),
) -> dict[str, Any]:
    normalized_scope = _normalize_scope(scope_key)
    normalized_change_kind = _normalize_change_kind(change_kind)
    event_id = deterministic_posture_event_id(scope_key=normalized_scope, posture_seq=decision.posture_seq)
    scope_kind, scope_values = _parse_scope_key(normalized_scope)
    manifest = scope_values.get("manifest_fingerprint", GLOBAL_MANIFEST_SENTINEL)

    payload = {
        "scope_key": normalized_scope,
        "scope_kind": scope_kind,
        "posture_seq": decision.posture_seq,
        "mode": decision.mode,
        "capabilities_mask": decision.capabilities_mask.as_dict(),
        "policy_rev": decision.policy_rev.as_dict(),
        "decided_at_utc": decision.decided_at_utc,
        "change_kind": normalized_change_kind,
        "triggers_summary": list(triggers_summary),
    }
    if decision.reason:
        payload["reason"] = decision.reason
    if decision.evidence_refs:
        payload["evidence_refs"] = list(decision.evidence_refs)

    event = {
        "event_id": event_id,
        "event_type": "dl.posture_changed.v1",
        "ts_utc": decision.decided_at_utc,
        "manifest_fingerprint": manifest,
        "payload": payload,
    }
    if scope_kind == "RUN":
        run_id = scope_values.get("run_id")
        if run_id:
            event["run_id"] = run_id
    return event


class DlOutboxStore:
    def enqueue_posture_change(
        self,
        *,
        scope_key: str,
        decision: DegradeDecision,
        change_kind: str,
        triggers_summary: tuple[str, ...] = (),
    ) -> bool:
        raise NotImplementedError

    def drain_once(
        self,
        *,
        publisher: DlControlPublisher,
        max_events: int = 50,
        max_attempts: int = 5,
        base_backoff_seconds: int = 1,
        now_utc: str | None = None,
    ) -> DlDrainResult:
        raise NotImplementedError

    def metrics(self, *, now_utc: str | None = None) -> DlEmissionMetrics:
        raise NotImplementedError


@dataclass
class SqliteDlOutboxStore(DlOutboxStore):
    path: Path
    stream_id: str

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS dl_posture_outbox (
                    stream_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    posture_seq INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    next_attempt_at_utc TEXT NOT NULL,
                    decided_at_utc TEXT NOT NULL,
                    last_error TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scope_key, posture_seq)
                );
                """
            )

    def enqueue_posture_change(
        self,
        *,
        scope_key: str,
        decision: DegradeDecision,
        change_kind: str,
        triggers_summary: tuple[str, ...] = (),
    ) -> bool:
        event = build_posture_change_event(
            scope_key=scope_key,
            decision=decision,
            change_kind=change_kind,
            triggers_summary=triggers_summary,
        )
        now = _utc_now()
        event_json = _canonical_json(event)
        normalized_scope = _normalize_scope(scope_key)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT OR IGNORE INTO dl_posture_outbox (
                    stream_id, scope_key, posture_seq, event_id, event_json, status, attempt_count,
                    next_attempt_at_utc, decided_at_utc, last_error, created_at_utc, updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.stream_id,
                    normalized_scope,
                    decision.posture_seq,
                    event["event_id"],
                    event_json,
                    OUTBOX_PENDING,
                    0,
                    now,
                    decision.decided_at_utc,
                    None,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT event_id, event_json
                FROM dl_posture_outbox
                WHERE stream_id = ? AND scope_key = ? AND posture_seq = ?
                """,
                (self.stream_id, normalized_scope, decision.posture_seq),
            ).fetchone()
            if row is None:
                raise DlEmissionError("OUTBOX_ENQUEUE_FAILED")
            existing_event_id, existing_json = str(row[0]), str(row[1])
            if existing_event_id != event["event_id"]:
                raise DlEmissionError("OUTBOX_ID_COLLISION")
            if existing_json != event_json:
                raise DlEmissionError("OUTBOX_EVENT_COLLISION")
            return conn.total_changes > 0

    def drain_once(
        self,
        *,
        publisher: DlControlPublisher,
        max_events: int = 50,
        max_attempts: int = 5,
        base_backoff_seconds: int = 1,
        now_utc: str | None = None,
    ) -> DlDrainResult:
        if max_events <= 0:
            raise DlEmissionError("max_events must be >= 1")
        if max_attempts <= 0:
            raise DlEmissionError("max_attempts must be >= 1")
        if base_backoff_seconds <= 0:
            raise DlEmissionError("base_backoff_seconds must be >= 1")

        now = _parse_or_now(now_utc)
        candidates = self._select_due_candidates(now=now, max_events=max_events)

        considered = 0
        published = 0
        failed = 0
        dead = 0
        for item in candidates:
            considered += 1
            try:
                event = json.loads(item.event_json)
                if not isinstance(event, dict):
                    raise ValueError("event_json not object")
            except Exception as exc:
                self._mark_dead(item=item, now=now, error=f"EVENT_JSON_CORRUPT:{exc}")
                dead += 1
                continue

            try:
                publisher.publish(event)
            except Exception as exc:
                attempts = item.attempt_count + 1
                if attempts >= max_attempts:
                    self._mark_dead(item=item, now=now, error=str(exc))
                    dead += 1
                else:
                    backoff_seconds = min(base_backoff_seconds * (2 ** (attempts - 1)), 300)
                    next_attempt = now + timedelta(seconds=backoff_seconds)
                    self._mark_failed(
                        item=item,
                        now=now,
                        attempts=attempts,
                        next_attempt=next_attempt,
                        error=str(exc),
                    )
                    failed += 1
                continue

            self._mark_sent(item=item, now=now)
            published += 1

        pending = self.metrics(now_utc=now.astimezone(timezone.utc).isoformat()).pending_count
        return DlDrainResult(
            considered=considered,
            published=published,
            failed=failed,
            dead_lettered=dead,
            pending_backlog=pending,
        )

    def metrics(self, *, now_utc: str | None = None) -> DlEmissionMetrics:
        now = _parse_or_now(now_utc)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN status = ? THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = ? THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = ? THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = ? THEN 1 ELSE 0 END)
                FROM dl_posture_outbox
                WHERE stream_id = ?
                """,
                (OUTBOX_PENDING, OUTBOX_FAILED, OUTBOX_DEAD, OUTBOX_SENT, self.stream_id),
            ).fetchone()
            oldest = conn.execute(
                """
                SELECT decided_at_utc
                FROM dl_posture_outbox
                WHERE stream_id = ? AND status IN (?, ?)
                ORDER BY decided_at_utc ASC
                LIMIT 1
                """,
                (self.stream_id, OUTBOX_PENDING, OUTBOX_FAILED),
            ).fetchone()
        pending = int(row[0] or 0) if row else 0
        failed = int(row[1] or 0) if row else 0
        dead = int(row[2] or 0) if row else 0
        sent = int(row[3] or 0) if row else 0
        oldest_age = None
        if oldest and oldest[0]:
            oldest_dt = _parse_utc(str(oldest[0]), field_name="oldest.decided_at_utc")
            oldest_age = max(0, int((now - oldest_dt).total_seconds()))
        return DlEmissionMetrics(
            pending_count=pending,
            failed_count=failed,
            dead_letter_count=dead,
            sent_count=sent,
            oldest_pending_age_seconds=oldest_age,
        )

    def _select_due_candidates(self, *, now: datetime, max_events: int) -> list[DlOutboxRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT scope_key, posture_seq, event_id, event_json, status, attempt_count,
                       next_attempt_at_utc, decided_at_utc, last_error
                FROM dl_posture_outbox
                WHERE stream_id = ? AND status IN (?, ?)
                ORDER BY scope_key ASC, posture_seq ASC
                """,
                (self.stream_id, OUTBOX_PENDING, OUTBOX_FAILED),
            ).fetchall()
        selected: list[DlOutboxRecord] = []
        seen_scope: set[str] = set()
        for row in rows:
            scope = str(row[0])
            if scope in seen_scope:
                continue
            seen_scope.add(scope)
            next_attempt = _parse_utc(str(row[6]), field_name="next_attempt_at_utc")
            if next_attempt > now:
                continue
            selected.append(
                DlOutboxRecord(
                    scope_key=scope,
                    posture_seq=int(row[1]),
                    event_id=str(row[2]),
                    event_json=str(row[3]),
                    status=str(row[4]),
                    attempt_count=int(row[5]),
                    next_attempt_at_utc=str(row[6]),
                    decided_at_utc=str(row[7]),
                    last_error=None if row[8] in (None, "") else str(row[8]),
                )
            )
            if len(selected) >= max_events:
                break
        return selected

    def _mark_sent(self, *, item: DlOutboxRecord, now: datetime) -> None:
        now_text = now.astimezone(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dl_posture_outbox
                SET status = ?, updated_at_utc = ?, last_error = NULL
                WHERE stream_id = ? AND scope_key = ? AND posture_seq = ?
                """,
                (OUTBOX_SENT, now_text, self.stream_id, item.scope_key, item.posture_seq),
            )

    def _mark_failed(
        self,
        *,
        item: DlOutboxRecord,
        now: datetime,
        attempts: int,
        next_attempt: datetime,
        error: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dl_posture_outbox
                SET status = ?, attempt_count = ?, next_attempt_at_utc = ?, last_error = ?, updated_at_utc = ?
                WHERE stream_id = ? AND scope_key = ? AND posture_seq = ?
                """,
                (
                    OUTBOX_FAILED,
                    attempts,
                    next_attempt.astimezone(timezone.utc).isoformat(),
                    _truncate_error(error),
                    now.astimezone(timezone.utc).isoformat(),
                    self.stream_id,
                    item.scope_key,
                    item.posture_seq,
                ),
            )

    def _mark_dead(self, *, item: DlOutboxRecord, now: datetime, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dl_posture_outbox
                SET status = ?, attempt_count = ?, last_error = ?, updated_at_utc = ?
                WHERE stream_id = ? AND scope_key = ? AND posture_seq = ?
                """,
                (
                    OUTBOX_DEAD,
                    item.attempt_count + 1,
                    _truncate_error(error),
                    now.astimezone(timezone.utc).isoformat(),
                    self.stream_id,
                    item.scope_key,
                    item.posture_seq,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path))


@dataclass
class PostgresDlOutboxStore(DlOutboxStore):
    dsn: str
    stream_id: str

    def __post_init__(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dl_posture_outbox (
                    stream_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    posture_seq BIGINT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    next_attempt_at_utc TEXT NOT NULL,
                    decided_at_utc TEXT NOT NULL,
                    last_error TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scope_key, posture_seq)
                )
                """
            )

    def enqueue_posture_change(
        self,
        *,
        scope_key: str,
        decision: DegradeDecision,
        change_kind: str,
        triggers_summary: tuple[str, ...] = (),
    ) -> bool:
        event = build_posture_change_event(
            scope_key=scope_key,
            decision=decision,
            change_kind=change_kind,
            triggers_summary=triggers_summary,
        )
        now = _utc_now()
        event_json = _canonical_json(event)
        normalized_scope = _normalize_scope(scope_key)
        inserted = False
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dl_posture_outbox (
                        stream_id, scope_key, posture_seq, event_id, event_json, status, attempt_count,
                        next_attempt_at_utc, decided_at_utc, last_error, created_at_utc, updated_at_utc
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stream_id, scope_key, posture_seq) DO NOTHING
                    """,
                    (
                        self.stream_id,
                        normalized_scope,
                        decision.posture_seq,
                        event["event_id"],
                        event_json,
                        OUTBOX_PENDING,
                        0,
                        now,
                        decision.decided_at_utc,
                        None,
                        now,
                        now,
                    ),
                )
                inserted = cur.rowcount > 0
                cur.execute(
                    """
                    SELECT event_id, event_json
                    FROM dl_posture_outbox
                    WHERE stream_id = %s AND scope_key = %s AND posture_seq = %s
                    """,
                    (self.stream_id, normalized_scope, decision.posture_seq),
                )
                row = cur.fetchone()
                if row is None:
                    raise DlEmissionError("OUTBOX_ENQUEUE_FAILED")
                existing_event_id, existing_json = str(row[0]), str(row[1])
                if existing_event_id != event["event_id"]:
                    raise DlEmissionError("OUTBOX_ID_COLLISION")
                if existing_json != event_json:
                    raise DlEmissionError("OUTBOX_EVENT_COLLISION")
        return inserted

    def drain_once(
        self,
        *,
        publisher: DlControlPublisher,
        max_events: int = 50,
        max_attempts: int = 5,
        base_backoff_seconds: int = 1,
        now_utc: str | None = None,
    ) -> DlDrainResult:
        if max_events <= 0:
            raise DlEmissionError("max_events must be >= 1")
        if max_attempts <= 0:
            raise DlEmissionError("max_attempts must be >= 1")
        if base_backoff_seconds <= 0:
            raise DlEmissionError("base_backoff_seconds must be >= 1")

        now = _parse_or_now(now_utc)
        candidates = self._select_due_candidates(now=now, max_events=max_events)

        considered = 0
        published = 0
        failed = 0
        dead = 0
        for item in candidates:
            considered += 1
            try:
                event = json.loads(item.event_json)
                if not isinstance(event, dict):
                    raise ValueError("event_json not object")
            except Exception as exc:
                self._mark_dead(item=item, now=now, error=f"EVENT_JSON_CORRUPT:{exc}")
                dead += 1
                continue

            try:
                publisher.publish(event)
            except Exception as exc:
                attempts = item.attempt_count + 1
                if attempts >= max_attempts:
                    self._mark_dead(item=item, now=now, error=str(exc))
                    dead += 1
                else:
                    backoff_seconds = min(base_backoff_seconds * (2 ** (attempts - 1)), 300)
                    next_attempt = now + timedelta(seconds=backoff_seconds)
                    self._mark_failed(
                        item=item,
                        now=now,
                        attempts=attempts,
                        next_attempt=next_attempt,
                        error=str(exc),
                    )
                    failed += 1
                continue

            self._mark_sent(item=item, now=now)
            published += 1

        pending = self.metrics(now_utc=now.astimezone(timezone.utc).isoformat()).pending_count
        return DlDrainResult(
            considered=considered,
            published=published,
            failed=failed,
            dead_lettered=dead,
            pending_backlog=pending,
        )

    def metrics(self, *, now_utc: str | None = None) -> DlEmissionMetrics:
        now = _parse_or_now(now_utc)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN status = %s THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = %s THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = %s THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = %s THEN 1 ELSE 0 END)
                FROM dl_posture_outbox
                WHERE stream_id = %s
                """,
                (OUTBOX_PENDING, OUTBOX_FAILED, OUTBOX_DEAD, OUTBOX_SENT, self.stream_id),
            ).fetchone()
            oldest = conn.execute(
                """
                SELECT decided_at_utc
                FROM dl_posture_outbox
                WHERE stream_id = %s AND status IN (%s, %s)
                ORDER BY decided_at_utc ASC
                LIMIT 1
                """,
                (self.stream_id, OUTBOX_PENDING, OUTBOX_FAILED),
            ).fetchone()
        pending = int(row[0] or 0) if row else 0
        failed = int(row[1] or 0) if row else 0
        dead = int(row[2] or 0) if row else 0
        sent = int(row[3] or 0) if row else 0
        oldest_age = None
        if oldest and oldest[0]:
            oldest_dt = _parse_utc(str(oldest[0]), field_name="oldest.decided_at_utc")
            oldest_age = max(0, int((now - oldest_dt).total_seconds()))
        return DlEmissionMetrics(
            pending_count=pending,
            failed_count=failed,
            dead_letter_count=dead,
            sent_count=sent,
            oldest_pending_age_seconds=oldest_age,
        )

    def _select_due_candidates(self, *, now: datetime, max_events: int) -> list[DlOutboxRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT scope_key, posture_seq, event_id, event_json, status, attempt_count,
                       next_attempt_at_utc, decided_at_utc, last_error
                FROM dl_posture_outbox
                WHERE stream_id = %s AND status IN (%s, %s)
                ORDER BY scope_key ASC, posture_seq ASC
                """,
                (self.stream_id, OUTBOX_PENDING, OUTBOX_FAILED),
            ).fetchall()
        selected: list[DlOutboxRecord] = []
        seen_scope: set[str] = set()
        for row in rows:
            scope = str(row[0])
            if scope in seen_scope:
                continue
            seen_scope.add(scope)
            next_attempt = _parse_utc(str(row[6]), field_name="next_attempt_at_utc")
            if next_attempt > now:
                continue
            selected.append(
                DlOutboxRecord(
                    scope_key=scope,
                    posture_seq=int(row[1]),
                    event_id=str(row[2]),
                    event_json=str(row[3]),
                    status=str(row[4]),
                    attempt_count=int(row[5]),
                    next_attempt_at_utc=str(row[6]),
                    decided_at_utc=str(row[7]),
                    last_error=None if row[8] in (None, "") else str(row[8]),
                )
            )
            if len(selected) >= max_events:
                break
        return selected

    def _mark_sent(self, *, item: DlOutboxRecord, now: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dl_posture_outbox
                SET status = %s, updated_at_utc = %s, last_error = NULL
                WHERE stream_id = %s AND scope_key = %s AND posture_seq = %s
                """,
                (
                    OUTBOX_SENT,
                    now.astimezone(timezone.utc).isoformat(),
                    self.stream_id,
                    item.scope_key,
                    item.posture_seq,
                ),
            )

    def _mark_failed(
        self,
        *,
        item: DlOutboxRecord,
        now: datetime,
        attempts: int,
        next_attempt: datetime,
        error: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dl_posture_outbox
                SET status = %s, attempt_count = %s, next_attempt_at_utc = %s, last_error = %s, updated_at_utc = %s
                WHERE stream_id = %s AND scope_key = %s AND posture_seq = %s
                """,
                (
                    OUTBOX_FAILED,
                    attempts,
                    next_attempt.astimezone(timezone.utc).isoformat(),
                    _truncate_error(error),
                    now.astimezone(timezone.utc).isoformat(),
                    self.stream_id,
                    item.scope_key,
                    item.posture_seq,
                ),
            )

    def _mark_dead(self, *, item: DlOutboxRecord, now: datetime, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE dl_posture_outbox
                SET status = %s, attempt_count = %s, last_error = %s, updated_at_utc = %s
                WHERE stream_id = %s AND scope_key = %s AND posture_seq = %s
                """,
                (
                    OUTBOX_DEAD,
                    item.attempt_count + 1,
                    _truncate_error(error),
                    now.astimezone(timezone.utc).isoformat(),
                    self.stream_id,
                    item.scope_key,
                    item.posture_seq,
                ),
            )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


def _normalize_scope(scope_key: str) -> str:
    normalized = str(scope_key).strip()
    if not normalized:
        raise DlEmissionError("scope_key must be non-empty")
    return normalized


def _normalize_change_kind(change_kind: str) -> str:
    normalized = str(change_kind).strip().upper()
    if not normalized:
        raise DlEmissionError("change_kind must be non-empty")
    return normalized


def _parse_scope_key(scope_key: str) -> tuple[str, dict[str, str]]:
    token = _normalize_scope(scope_key)
    parts = token.split("|")
    head = parts[0]
    if not head.startswith("scope="):
        raise DlEmissionError(f"invalid scope_key format: {scope_key!r}")
    scope_kind = head.split("=", 1)[1].strip().upper()
    values: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            values[key] = value
    if scope_kind == "GLOBAL":
        values.setdefault("manifest_fingerprint", GLOBAL_MANIFEST_SENTINEL)
    return scope_kind, values


def _parse_utc(value: str, *, field_name: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise DlEmissionError(f"{field_name} must be non-empty")
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DlEmissionError(f"{field_name} must be RFC3339-ish UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise DlEmissionError(f"{field_name} must include timezone information")
    return dt.astimezone(timezone.utc)


def _parse_or_now(now_utc: str | None) -> datetime:
    if now_utc in (None, ""):
        return datetime.now(tz=timezone.utc)
    return _parse_utc(str(now_utc), field_name="now_utc")


def _truncate_error(value: str, limit: int = 2048) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sqlite_path(dsn: str) -> str:
    value = str(dsn or "").strip()
    if not value:
        raise DlEmissionError("sqlite store path/DSN must be non-empty")
    if value.startswith("sqlite:///"):
        return value[len("sqlite:///") :]
    if value.startswith("sqlite://"):
        return value[len("sqlite://") :]
    return value


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
