"""Decision Fabric replay/idempotency ledger (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg
from fraud_detection.postgres_runtime import postgres_threadlocal_connection

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn


REPLAY_NEW = "NEW"
REPLAY_MATCH = "REPLAY_MATCH"
REPLAY_PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"


class DecisionReplayError(ValueError):
    """Raised when replay ledger operations are invalid."""


@dataclass(frozen=True)
class ReplayRegistrationResult:
    outcome: str
    decision_id: str
    payload_hash: str
    stored_payload_hash: str
    replay_count: int
    mismatch_count: int


@dataclass(frozen=True)
class DecisionLedgerEntry:
    decision_id: str
    source_event_id: str
    payload_hash: str
    payload_json: str
    first_seen_at_utc: str
    last_seen_at_utc: str
    replay_count: int
    mismatch_count: int


class DecisionReplayLedger:
    def __init__(self, db_path: str | Path) -> None:
        locator = str(db_path)
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "postgres":
            self._store: _ReplayStore = _PostgresReplayStore(dsn=locator)
        else:
            path = Path(_sqlite_path(locator))
            self._store = _SqliteReplayStore(path=path)

    def register_decision(
        self,
        *,
        decision_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        return self._store.register_decision(decision_payload=decision_payload, observed_at_utc=observed_at_utc)

    def lookup(self, decision_id: str) -> DecisionLedgerEntry | None:
        return self._store.lookup(decision_id)

    def mismatch_count(self, decision_id: str) -> int:
        return self._store.mismatch_count(decision_id)


class _ReplayStore:
    def register_decision(
        self,
        *,
        decision_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        raise NotImplementedError

    def lookup(self, decision_id: str) -> DecisionLedgerEntry | None:
        raise NotImplementedError

    def mismatch_count(self, decision_id: str) -> int:
        raise NotImplementedError


@dataclass
class _SqliteReplayStore(_ReplayStore):
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def register_decision(
        self,
        *,
        decision_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        normalized = _normalize_payload(decision_payload)
        decision_id = str(normalized.get("decision_id") or "").strip()
        if not decision_id:
            raise DecisionReplayError("decision_payload.decision_id is required")
        source_event_id = str((normalized.get("source_event") or {}).get("event_id") or "").strip()
        if not source_event_id:
            raise DecisionReplayError("decision_payload.source_event.event_id is required")
        payload_json = _canonical_json(normalized)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT payload_hash, replay_count, mismatch_count
                FROM decision_replay_ledger
                WHERE decision_id = ?
                """,
                (decision_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO decision_replay_ledger (
                        decision_id, source_event_id, payload_hash, payload_json,
                        first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0)
                    """,
                    (decision_id, source_event_id, payload_hash, payload_json, observed_at_utc, observed_at_utc),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_NEW,
                    decision_id=decision_id,
                    payload_hash=payload_hash,
                    stored_payload_hash=payload_hash,
                    replay_count=0,
                    mismatch_count=0,
                )

            stored_hash = str(row[0] or "")
            replay_count = int(row[1] or 0)
            mismatch_count = int(row[2] or 0)

            if stored_hash == payload_hash:
                replay_count += 1
                conn.execute(
                    """
                    UPDATE decision_replay_ledger
                    SET last_seen_at_utc = ?, replay_count = ?
                    WHERE decision_id = ?
                    """,
                    (observed_at_utc, replay_count, decision_id),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_MATCH,
                    decision_id=decision_id,
                    payload_hash=payload_hash,
                    stored_payload_hash=stored_hash,
                    replay_count=replay_count,
                    mismatch_count=mismatch_count,
                )

            mismatch_count += 1
            conn.execute(
                """
                INSERT OR IGNORE INTO decision_payload_mismatches (
                    decision_id, observed_payload_hash, stored_payload_hash, observed_at_utc, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (decision_id, payload_hash, stored_hash, observed_at_utc, payload_json),
            )
            conn.execute(
                """
                UPDATE decision_replay_ledger
                SET last_seen_at_utc = ?, mismatch_count = ?
                WHERE decision_id = ?
                """,
                (observed_at_utc, mismatch_count, decision_id),
            )
            return ReplayRegistrationResult(
                outcome=REPLAY_PAYLOAD_MISMATCH,
                decision_id=decision_id,
                payload_hash=payload_hash,
                stored_payload_hash=stored_hash,
                replay_count=replay_count,
                mismatch_count=mismatch_count,
            )

    def lookup(self, decision_id: str) -> DecisionLedgerEntry | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT decision_id, source_event_id, payload_hash, payload_json,
                       first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                FROM decision_replay_ledger
                WHERE decision_id = ?
                """,
                (decision_id,),
            ).fetchone()
        if row is None:
            return None
        return DecisionLedgerEntry(
            decision_id=str(row[0]),
            source_event_id=str(row[1]),
            payload_hash=str(row[2]),
            payload_json=str(row[3]),
            first_seen_at_utc=str(row[4]),
            last_seen_at_utc=str(row[5]),
            replay_count=int(row[6] or 0),
            mismatch_count=int(row[7] or 0),
        )

    def mismatch_count(self, decision_id: str) -> int:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM decision_payload_mismatches WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_replay_ledger (
                    decision_id TEXT PRIMARY KEY,
                    source_event_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    first_seen_at_utc TEXT NOT NULL,
                    last_seen_at_utc TEXT NOT NULL,
                    replay_count INTEGER NOT NULL DEFAULT 0,
                    mismatch_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_payload_mismatches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(decision_id, observed_payload_hash)
                )
                """
            )


@dataclass
class _PostgresReplayStore(_ReplayStore):
    dsn: str

    def __post_init__(self) -> None:
        self._init_db()

    def register_decision(
        self,
        *,
        decision_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        normalized = _normalize_payload(decision_payload)
        decision_id = str(normalized.get("decision_id") or "").strip()
        if not decision_id:
            raise DecisionReplayError("decision_payload.decision_id is required")
        source_event_id = str((normalized.get("source_event") or {}).get("event_id") or "").strip()
        if not source_event_id:
            raise DecisionReplayError("decision_payload.source_event.event_id is required")
        payload_json = _canonical_json(normalized)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT payload_hash, replay_count, mismatch_count
                    FROM decision_replay_ledger
                    WHERE decision_id = %s
                    FOR UPDATE
                    """,
                    (decision_id,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO decision_replay_ledger (
                            decision_id, source_event_id, payload_hash, payload_json,
                            first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, 0, 0)
                        """,
                        (decision_id, source_event_id, payload_hash, payload_json, observed_at_utc, observed_at_utc),
                    )
                    return ReplayRegistrationResult(
                        outcome=REPLAY_NEW,
                        decision_id=decision_id,
                        payload_hash=payload_hash,
                        stored_payload_hash=payload_hash,
                        replay_count=0,
                        mismatch_count=0,
                    )

                stored_hash = str(row[0] or "")
                replay_count = int(row[1] or 0)
                mismatch_count = int(row[2] or 0)

                if stored_hash == payload_hash:
                    replay_count += 1
                    conn.execute(
                        """
                        UPDATE decision_replay_ledger
                        SET last_seen_at_utc = %s, replay_count = %s
                        WHERE decision_id = %s
                        """,
                        (observed_at_utc, replay_count, decision_id),
                    )
                    return ReplayRegistrationResult(
                        outcome=REPLAY_MATCH,
                        decision_id=decision_id,
                        payload_hash=payload_hash,
                        stored_payload_hash=stored_hash,
                        replay_count=replay_count,
                        mismatch_count=mismatch_count,
                    )

                mismatch_count += 1
                conn.execute(
                    """
                    INSERT INTO decision_payload_mismatches (
                        decision_id, observed_payload_hash, stored_payload_hash, observed_at_utc, payload_json
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (decision_id, observed_payload_hash) DO NOTHING
                    """,
                    (decision_id, payload_hash, stored_hash, observed_at_utc, payload_json),
                )
                conn.execute(
                    """
                    UPDATE decision_replay_ledger
                    SET last_seen_at_utc = %s, mismatch_count = %s
                    WHERE decision_id = %s
                    """,
                    (observed_at_utc, mismatch_count, decision_id),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_PAYLOAD_MISMATCH,
                    decision_id=decision_id,
                    payload_hash=payload_hash,
                    stored_payload_hash=stored_hash,
                    replay_count=replay_count,
                    mismatch_count=mismatch_count,
                )

    def lookup(self, decision_id: str) -> DecisionLedgerEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT decision_id, source_event_id, payload_hash, payload_json,
                       first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                FROM decision_replay_ledger
                WHERE decision_id = %s
                """,
                (decision_id,),
            ).fetchone()
        if row is None:
            return None
        return DecisionLedgerEntry(
            decision_id=str(row[0]),
            source_event_id=str(row[1]),
            payload_hash=str(row[2]),
            payload_json=str(row[3]),
            first_seen_at_utc=str(row[4]),
            last_seen_at_utc=str(row[5]),
            replay_count=int(row[6] or 0),
            mismatch_count=int(row[7] or 0),
        )

    def mismatch_count(self, decision_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM decision_payload_mismatches WHERE decision_id = %s",
                (decision_id,),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_replay_ledger (
                    decision_id TEXT PRIMARY KEY,
                    source_event_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    first_seen_at_utc TEXT NOT NULL,
                    last_seen_at_utc TEXT NOT NULL,
                    replay_count INTEGER NOT NULL DEFAULT 0,
                    mismatch_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decision_payload_mismatches (
                    id BIGSERIAL PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(decision_id, observed_payload_hash)
                )
                """
            )

    def _connect(self) -> psycopg.Connection:
        return postgres_threadlocal_connection(self.dsn)


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DecisionReplayError("decision_payload must be a mapping")
    return json.loads(_canonical_json(payload))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator.replace("sqlite:///", "", 1)
    if locator.startswith("sqlite://"):
        return locator.replace("sqlite://", "", 1)
    return locator

