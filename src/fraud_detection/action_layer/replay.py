"""Action Layer replay/idempotency ledger (Phase 6)."""

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


class ActionReplayError(ValueError):
    """Raised when AL replay ledger operations are invalid."""


@dataclass(frozen=True)
class ReplayRegistrationResult:
    outcome: str
    outcome_id: str
    payload_hash: str
    stored_payload_hash: str
    replay_count: int
    mismatch_count: int


@dataclass(frozen=True)
class ActionOutcomeLedgerEntry:
    outcome_id: str
    decision_id: str
    action_id: str
    payload_hash: str
    payload_json: str
    first_seen_at_utc: str
    last_seen_at_utc: str
    replay_count: int
    mismatch_count: int


class ActionOutcomeReplayLedger:
    def __init__(self, db_path: str | Path) -> None:
        locator = str(db_path)
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "postgres":
            self._store: _ReplayStore = _PostgresReplayStore(dsn=locator)
        else:
            self._store = _SqliteReplayStore(path=Path(_sqlite_path(locator)))

    def register_outcome(
        self,
        *,
        outcome_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        return self._store.register_outcome(outcome_payload=outcome_payload, observed_at_utc=observed_at_utc)

    def lookup(self, outcome_id: str) -> ActionOutcomeLedgerEntry | None:
        return self._store.lookup(outcome_id)

    def mismatch_count(self, outcome_id: str) -> int:
        return self._store.mismatch_count(outcome_id)

    def identity_chain_hash(self) -> str:
        return self._store.identity_chain_hash()


class _ReplayStore:
    def register_outcome(
        self,
        *,
        outcome_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        raise NotImplementedError

    def lookup(self, outcome_id: str) -> ActionOutcomeLedgerEntry | None:
        raise NotImplementedError

    def mismatch_count(self, outcome_id: str) -> int:
        raise NotImplementedError

    def identity_chain_hash(self) -> str:
        raise NotImplementedError


@dataclass
class _SqliteReplayStore(_ReplayStore):
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def register_outcome(
        self,
        *,
        outcome_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        normalized = _normalize_payload(outcome_payload)
        outcome_id = str(normalized.get("outcome_id") or "").strip()
        if not outcome_id:
            raise ActionReplayError("outcome_payload.outcome_id is required")
        decision_id = str(normalized.get("decision_id") or "").strip()
        if not decision_id:
            raise ActionReplayError("outcome_payload.decision_id is required")
        action_id = str(normalized.get("action_id") or "").strip()
        if not action_id:
            raise ActionReplayError("outcome_payload.action_id is required")

        payload_json = _canonical_json(normalized)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT payload_hash, replay_count, mismatch_count
                FROM al_outcome_replay_ledger
                WHERE outcome_id = ?
                """,
                (outcome_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO al_outcome_replay_ledger (
                        outcome_id, decision_id, action_id, payload_hash, payload_json,
                        first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                    """,
                    (outcome_id, decision_id, action_id, payload_hash, payload_json, observed_at_utc, observed_at_utc),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_NEW,
                    outcome_id=outcome_id,
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
                    UPDATE al_outcome_replay_ledger
                    SET last_seen_at_utc = ?, replay_count = ?
                    WHERE outcome_id = ?
                    """,
                    (observed_at_utc, replay_count, outcome_id),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_MATCH,
                    outcome_id=outcome_id,
                    payload_hash=payload_hash,
                    stored_payload_hash=stored_hash,
                    replay_count=replay_count,
                    mismatch_count=mismatch_count,
                )

            mismatch_count += 1
            conn.execute(
                """
                INSERT OR IGNORE INTO al_outcome_payload_mismatches (
                    outcome_id, observed_payload_hash, stored_payload_hash, observed_at_utc, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (outcome_id, payload_hash, stored_hash, observed_at_utc, payload_json),
            )
            conn.execute(
                """
                UPDATE al_outcome_replay_ledger
                SET last_seen_at_utc = ?, mismatch_count = ?
                WHERE outcome_id = ?
                """,
                (observed_at_utc, mismatch_count, outcome_id),
            )
            return ReplayRegistrationResult(
                outcome=REPLAY_PAYLOAD_MISMATCH,
                outcome_id=outcome_id,
                payload_hash=payload_hash,
                stored_payload_hash=stored_hash,
                replay_count=replay_count,
                mismatch_count=mismatch_count,
            )

    def lookup(self, outcome_id: str) -> ActionOutcomeLedgerEntry | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT outcome_id, decision_id, action_id, payload_hash, payload_json,
                       first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                FROM al_outcome_replay_ledger
                WHERE outcome_id = ?
                """,
                (outcome_id,),
            ).fetchone()
        if row is None:
            return None
        return ActionOutcomeLedgerEntry(
            outcome_id=str(row[0]),
            decision_id=str(row[1]),
            action_id=str(row[2]),
            payload_hash=str(row[3]),
            payload_json=str(row[4]),
            first_seen_at_utc=str(row[5]),
            last_seen_at_utc=str(row[6]),
            replay_count=int(row[7] or 0),
            mismatch_count=int(row[8] or 0),
        )

    def mismatch_count(self, outcome_id: str) -> int:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM al_outcome_payload_mismatches WHERE outcome_id = ?",
                (outcome_id,),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def identity_chain_hash(self) -> str:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT outcome_id, payload_hash
                FROM al_outcome_replay_ledger
                ORDER BY outcome_id ASC
                """
            ).fetchall()
        chain = [{"outcome_id": str(row[0]), "payload_hash": str(row[1])} for row in rows]
        return hashlib.sha256(_canonical_json(chain).encode("utf-8")).hexdigest()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS al_outcome_replay_ledger (
                    outcome_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS al_outcome_payload_mismatches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outcome_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(outcome_id, observed_payload_hash)
                )
                """
            )


@dataclass
class _PostgresReplayStore(_ReplayStore):
    dsn: str

    def __post_init__(self) -> None:
        self._init_db()

    def register_outcome(
        self,
        *,
        outcome_payload: Mapping[str, Any],
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        normalized = _normalize_payload(outcome_payload)
        outcome_id = str(normalized.get("outcome_id") or "").strip()
        if not outcome_id:
            raise ActionReplayError("outcome_payload.outcome_id is required")
        decision_id = str(normalized.get("decision_id") or "").strip()
        if not decision_id:
            raise ActionReplayError("outcome_payload.decision_id is required")
        action_id = str(normalized.get("action_id") or "").strip()
        if not action_id:
            raise ActionReplayError("outcome_payload.action_id is required")

        payload_json = _canonical_json(normalized)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT payload_hash, replay_count, mismatch_count
                    FROM al_outcome_replay_ledger
                    WHERE outcome_id = %s
                    FOR UPDATE
                    """,
                    (outcome_id,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO al_outcome_replay_ledger (
                            outcome_id, decision_id, action_id, payload_hash, payload_json,
                            first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0)
                        """,
                        (outcome_id, decision_id, action_id, payload_hash, payload_json, observed_at_utc, observed_at_utc),
                    )
                    return ReplayRegistrationResult(
                        outcome=REPLAY_NEW,
                        outcome_id=outcome_id,
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
                        UPDATE al_outcome_replay_ledger
                        SET last_seen_at_utc = %s, replay_count = %s
                        WHERE outcome_id = %s
                        """,
                        (observed_at_utc, replay_count, outcome_id),
                    )
                    return ReplayRegistrationResult(
                        outcome=REPLAY_MATCH,
                        outcome_id=outcome_id,
                        payload_hash=payload_hash,
                        stored_payload_hash=stored_hash,
                        replay_count=replay_count,
                        mismatch_count=mismatch_count,
                    )

                mismatch_count += 1
                conn.execute(
                    """
                    INSERT INTO al_outcome_payload_mismatches (
                        outcome_id, observed_payload_hash, stored_payload_hash, observed_at_utc, payload_json
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (outcome_id, observed_payload_hash) DO NOTHING
                    """,
                    (outcome_id, payload_hash, stored_hash, observed_at_utc, payload_json),
                )
                conn.execute(
                    """
                    UPDATE al_outcome_replay_ledger
                    SET last_seen_at_utc = %s, mismatch_count = %s
                    WHERE outcome_id = %s
                    """,
                    (observed_at_utc, mismatch_count, outcome_id),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_PAYLOAD_MISMATCH,
                    outcome_id=outcome_id,
                    payload_hash=payload_hash,
                    stored_payload_hash=stored_hash,
                    replay_count=replay_count,
                    mismatch_count=mismatch_count,
                )

    def lookup(self, outcome_id: str) -> ActionOutcomeLedgerEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT outcome_id, decision_id, action_id, payload_hash, payload_json,
                       first_seen_at_utc, last_seen_at_utc, replay_count, mismatch_count
                FROM al_outcome_replay_ledger
                WHERE outcome_id = %s
                """,
                (outcome_id,),
            ).fetchone()
        if row is None:
            return None
        return ActionOutcomeLedgerEntry(
            outcome_id=str(row[0]),
            decision_id=str(row[1]),
            action_id=str(row[2]),
            payload_hash=str(row[3]),
            payload_json=str(row[4]),
            first_seen_at_utc=str(row[5]),
            last_seen_at_utc=str(row[6]),
            replay_count=int(row[7] or 0),
            mismatch_count=int(row[8] or 0),
        )

    def mismatch_count(self, outcome_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM al_outcome_payload_mismatches WHERE outcome_id = %s",
                (outcome_id,),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def identity_chain_hash(self) -> str:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT outcome_id, payload_hash
                FROM al_outcome_replay_ledger
                ORDER BY outcome_id ASC
                """
            ).fetchall()
        chain = [{"outcome_id": str(row[0]), "payload_hash": str(row[1])} for row in rows]
        return hashlib.sha256(_canonical_json(chain).encode("utf-8")).hexdigest()

    def _connect(self) -> psycopg.Connection[Any]:
        return postgres_threadlocal_connection(self.dsn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS al_outcome_replay_ledger (
                    outcome_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS al_outcome_payload_mismatches (
                    id BIGSERIAL PRIMARY KEY,
                    outcome_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(outcome_id, observed_payload_hash)
                )
                """
            )


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ActionReplayError("outcome payload must be a mapping")
    return dict(payload)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


