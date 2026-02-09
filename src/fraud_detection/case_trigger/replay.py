"""CaseTrigger replay/idempotency ledger (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .config import CaseTriggerPolicy
from .contracts import CaseTriggerContractError, validate_case_trigger_payload


REPLAY_NEW = "NEW"
REPLAY_MATCH = "REPLAY_MATCH"
REPLAY_PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"


class CaseTriggerReplayError(ValueError):
    """Raised when CaseTrigger replay ledger operations are invalid."""


@dataclass(frozen=True)
class ReplayRegistrationResult:
    outcome: str
    case_trigger_id: str
    payload_hash: str
    stored_payload_hash: str
    replay_count: int
    mismatch_count: int


@dataclass(frozen=True)
class CaseTriggerLedgerEntry:
    case_trigger_id: str
    case_id: str
    trigger_type: str
    source_ref_id: str
    source_class: str
    payload_hash: str
    payload_json: str
    first_seen_at_utc: str
    last_seen_at_utc: str
    replay_count: int
    mismatch_count: int


class CaseTriggerReplayLedger:
    def __init__(self, db_path: str | Path) -> None:
        locator = str(db_path)
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "postgres":
            self._store: _ReplayStore = _PostgresReplayStore(dsn=locator)
        else:
            self._store = _SqliteReplayStore(path=Path(_sqlite_path(locator)))

    def register_case_trigger(
        self,
        *,
        payload: Mapping[str, Any],
        source_class: str,
        observed_at_utc: str,
        policy: CaseTriggerPolicy | None = None,
    ) -> ReplayRegistrationResult:
        try:
            trigger = validate_case_trigger_payload(
                payload,
                source_class=source_class,
                policy=policy,
            )
        except CaseTriggerContractError as exc:
            raise CaseTriggerReplayError(
                f"CaseTrigger payload rejected before replay registration: {exc}"
            ) from exc

        return self._store.register(
            case_trigger_payload=trigger.as_dict(),
            source_class=source_class,
            observed_at_utc=observed_at_utc,
        )

    def lookup(self, case_trigger_id: str) -> CaseTriggerLedgerEntry | None:
        return self._store.lookup(case_trigger_id)

    def mismatch_count(self, case_trigger_id: str) -> int:
        return self._store.mismatch_count(case_trigger_id)

    def identity_chain_hash(self) -> str:
        return self._store.identity_chain_hash()


class _ReplayStore:
    def register(
        self,
        *,
        case_trigger_payload: Mapping[str, Any],
        source_class: str,
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        raise NotImplementedError

    def lookup(self, case_trigger_id: str) -> CaseTriggerLedgerEntry | None:
        raise NotImplementedError

    def mismatch_count(self, case_trigger_id: str) -> int:
        raise NotImplementedError

    def identity_chain_hash(self) -> str:
        raise NotImplementedError


@dataclass
class _SqliteReplayStore(_ReplayStore):
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def register(
        self,
        *,
        case_trigger_payload: Mapping[str, Any],
        source_class: str,
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        normalized = _normalize_payload(case_trigger_payload)
        case_trigger_id = _required_text(
            normalized.get("case_trigger_id"),
            "case_trigger_payload.case_trigger_id",
        )
        case_id = _required_text(normalized.get("case_id"), "case_trigger_payload.case_id")
        trigger_type = _required_text(
            normalized.get("trigger_type"),
            "case_trigger_payload.trigger_type",
        )
        source_ref_id = _required_text(
            normalized.get("source_ref_id"),
            "case_trigger_payload.source_ref_id",
        )
        source_class_text = _required_text(source_class, "source_class")

        payload_json = _canonical_json(normalized)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT payload_hash, replay_count, mismatch_count
                FROM case_trigger_replay_ledger
                WHERE case_trigger_id = ?
                """,
                (case_trigger_id,),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO case_trigger_replay_ledger (
                        case_trigger_id, case_id, trigger_type, source_ref_id, source_class,
                        payload_hash, payload_json, first_seen_at_utc, last_seen_at_utc,
                        replay_count, mismatch_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                    """,
                    (
                        case_trigger_id,
                        case_id,
                        trigger_type,
                        source_ref_id,
                        source_class_text,
                        payload_hash,
                        payload_json,
                        observed_at_utc,
                        observed_at_utc,
                    ),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_NEW,
                    case_trigger_id=case_trigger_id,
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
                    UPDATE case_trigger_replay_ledger
                    SET last_seen_at_utc = ?, replay_count = ?
                    WHERE case_trigger_id = ?
                    """,
                    (observed_at_utc, replay_count, case_trigger_id),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_MATCH,
                    case_trigger_id=case_trigger_id,
                    payload_hash=payload_hash,
                    stored_payload_hash=stored_hash,
                    replay_count=replay_count,
                    mismatch_count=mismatch_count,
                )

            mismatch_count += 1
            conn.execute(
                """
                INSERT OR IGNORE INTO case_trigger_payload_mismatches (
                    case_trigger_id, observed_payload_hash, stored_payload_hash, observed_at_utc, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (case_trigger_id, payload_hash, stored_hash, observed_at_utc, payload_json),
            )
            conn.execute(
                """
                UPDATE case_trigger_replay_ledger
                SET last_seen_at_utc = ?, mismatch_count = ?
                WHERE case_trigger_id = ?
                """,
                (observed_at_utc, mismatch_count, case_trigger_id),
            )
            return ReplayRegistrationResult(
                outcome=REPLAY_PAYLOAD_MISMATCH,
                case_trigger_id=case_trigger_id,
                payload_hash=payload_hash,
                stored_payload_hash=stored_hash,
                replay_count=replay_count,
                mismatch_count=mismatch_count,
            )

    def lookup(self, case_trigger_id: str) -> CaseTriggerLedgerEntry | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT case_trigger_id, case_id, trigger_type, source_ref_id, source_class,
                       payload_hash, payload_json, first_seen_at_utc, last_seen_at_utc,
                       replay_count, mismatch_count
                FROM case_trigger_replay_ledger
                WHERE case_trigger_id = ?
                """,
                (case_trigger_id,),
            ).fetchone()
        if row is None:
            return None
        return CaseTriggerLedgerEntry(
            case_trigger_id=str(row[0]),
            case_id=str(row[1]),
            trigger_type=str(row[2]),
            source_ref_id=str(row[3]),
            source_class=str(row[4]),
            payload_hash=str(row[5]),
            payload_json=str(row[6]),
            first_seen_at_utc=str(row[7]),
            last_seen_at_utc=str(row[8]),
            replay_count=int(row[9] or 0),
            mismatch_count=int(row[10] or 0),
        )

    def mismatch_count(self, case_trigger_id: str) -> int:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM case_trigger_payload_mismatches WHERE case_trigger_id = ?",
                (case_trigger_id,),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def identity_chain_hash(self) -> str:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT case_trigger_id, payload_hash
                FROM case_trigger_replay_ledger
                ORDER BY case_trigger_id ASC
                """
            ).fetchall()
        chain = [
            {"case_trigger_id": str(row[0]), "payload_hash": str(row[1])}
            for row in rows
        ]
        return hashlib.sha256(_canonical_json(chain).encode("utf-8")).hexdigest()

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS case_trigger_replay_ledger (
                    case_trigger_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    source_ref_id TEXT NOT NULL,
                    source_class TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS case_trigger_payload_mismatches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_trigger_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(case_trigger_id, observed_payload_hash)
                )
                """
            )


@dataclass
class _PostgresReplayStore(_ReplayStore):
    dsn: str

    def __post_init__(self) -> None:
        self._init_db()

    def register(
        self,
        *,
        case_trigger_payload: Mapping[str, Any],
        source_class: str,
        observed_at_utc: str,
    ) -> ReplayRegistrationResult:
        normalized = _normalize_payload(case_trigger_payload)
        case_trigger_id = _required_text(
            normalized.get("case_trigger_id"),
            "case_trigger_payload.case_trigger_id",
        )
        case_id = _required_text(normalized.get("case_id"), "case_trigger_payload.case_id")
        trigger_type = _required_text(
            normalized.get("trigger_type"),
            "case_trigger_payload.trigger_type",
        )
        source_ref_id = _required_text(
            normalized.get("source_ref_id"),
            "case_trigger_payload.source_ref_id",
        )
        source_class_text = _required_text(source_class, "source_class")

        payload_json = _canonical_json(normalized)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT payload_hash, replay_count, mismatch_count
                    FROM case_trigger_replay_ledger
                    WHERE case_trigger_id = %s
                    FOR UPDATE
                    """,
                    (case_trigger_id,),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO case_trigger_replay_ledger (
                            case_trigger_id, case_id, trigger_type, source_ref_id, source_class,
                            payload_hash, payload_json, first_seen_at_utc, last_seen_at_utc,
                            replay_count, mismatch_count
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
                        """,
                        (
                            case_trigger_id,
                            case_id,
                            trigger_type,
                            source_ref_id,
                            source_class_text,
                            payload_hash,
                            payload_json,
                            observed_at_utc,
                            observed_at_utc,
                        ),
                    )
                    return ReplayRegistrationResult(
                        outcome=REPLAY_NEW,
                        case_trigger_id=case_trigger_id,
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
                        UPDATE case_trigger_replay_ledger
                        SET last_seen_at_utc = %s, replay_count = %s
                        WHERE case_trigger_id = %s
                        """,
                        (observed_at_utc, replay_count, case_trigger_id),
                    )
                    return ReplayRegistrationResult(
                        outcome=REPLAY_MATCH,
                        case_trigger_id=case_trigger_id,
                        payload_hash=payload_hash,
                        stored_payload_hash=stored_hash,
                        replay_count=replay_count,
                        mismatch_count=mismatch_count,
                    )

                mismatch_count += 1
                conn.execute(
                    """
                    INSERT INTO case_trigger_payload_mismatches (
                        case_trigger_id, observed_payload_hash, stored_payload_hash, observed_at_utc, payload_json
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (case_trigger_id, observed_payload_hash) DO NOTHING
                    """,
                    (case_trigger_id, payload_hash, stored_hash, observed_at_utc, payload_json),
                )
                conn.execute(
                    """
                    UPDATE case_trigger_replay_ledger
                    SET last_seen_at_utc = %s, mismatch_count = %s
                    WHERE case_trigger_id = %s
                    """,
                    (observed_at_utc, mismatch_count, case_trigger_id),
                )
                return ReplayRegistrationResult(
                    outcome=REPLAY_PAYLOAD_MISMATCH,
                    case_trigger_id=case_trigger_id,
                    payload_hash=payload_hash,
                    stored_payload_hash=stored_hash,
                    replay_count=replay_count,
                    mismatch_count=mismatch_count,
                )

    def lookup(self, case_trigger_id: str) -> CaseTriggerLedgerEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT case_trigger_id, case_id, trigger_type, source_ref_id, source_class,
                       payload_hash, payload_json, first_seen_at_utc, last_seen_at_utc,
                       replay_count, mismatch_count
                FROM case_trigger_replay_ledger
                WHERE case_trigger_id = %s
                """,
                (case_trigger_id,),
            ).fetchone()
        if row is None:
            return None
        return CaseTriggerLedgerEntry(
            case_trigger_id=str(row[0]),
            case_id=str(row[1]),
            trigger_type=str(row[2]),
            source_ref_id=str(row[3]),
            source_class=str(row[4]),
            payload_hash=str(row[5]),
            payload_json=str(row[6]),
            first_seen_at_utc=str(row[7]),
            last_seen_at_utc=str(row[8]),
            replay_count=int(row[9] or 0),
            mismatch_count=int(row[10] or 0),
        )

    def mismatch_count(self, case_trigger_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(1) FROM case_trigger_payload_mismatches WHERE case_trigger_id = %s",
                (case_trigger_id,),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def identity_chain_hash(self) -> str:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT case_trigger_id, payload_hash
                FROM case_trigger_replay_ledger
                ORDER BY case_trigger_id ASC
                """
            ).fetchall()
        chain = [
            {"case_trigger_id": str(row[0]), "payload_hash": str(row[1])}
            for row in rows
        ]
        return hashlib.sha256(_canonical_json(chain).encode("utf-8")).hexdigest()

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.dsn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS case_trigger_replay_ledger (
                    case_trigger_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    source_ref_id TEXT NOT NULL,
                    source_class TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS case_trigger_payload_mismatches (
                    id BIGSERIAL PRIMARY KEY,
                    case_trigger_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(case_trigger_id, observed_payload_hash)
                )
                """
            )


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise CaseTriggerReplayError("case trigger payload must be a mapping")
    return dict(payload)


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseTriggerReplayError(f"{field_name} is required")
    return text


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator
