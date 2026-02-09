"""CaseTrigger checkpoint commit gate (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .publish import (
    PUBLISH_ADMIT,
    PUBLISH_AMBIGUOUS,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
)


CHECKPOINT_ISSUED = "ISSUED"
CHECKPOINT_COMMITTED = "COMMITTED"
CHECKPOINT_BLOCKED = "BLOCKED"


class CaseTriggerCheckpointError(ValueError):
    """Raised when CaseTrigger checkpoint transitions are invalid."""


@dataclass(frozen=True)
class CheckpointToken:
    token_id: str
    source_ref_id: str
    case_trigger_id: str
    issued_at_utc: str


@dataclass(frozen=True)
class CheckpointCommitResult:
    status: str
    token_id: str
    reason: str | None = None
    checkpoint_ref: dict[str, Any] | None = None


class CaseTriggerCheckpointGate:
    def __init__(self, db_path: str | Path) -> None:
        locator = str(db_path)
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "postgres":
            self._store: _CheckpointStore = _PostgresCheckpointStore(dsn=locator)
        else:
            self._store = _SqliteCheckpointStore(path=Path(_sqlite_path(locator)))

    def issue_token(
        self,
        *,
        source_ref_id: str,
        case_trigger_id: str,
        issued_at_utc: str,
    ) -> CheckpointToken:
        return self._store.issue_token(
            source_ref_id=source_ref_id,
            case_trigger_id=case_trigger_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_ledger_committed(self, *, token_id: str) -> None:
        self._store.mark_ledger_committed(token_id=token_id)

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        halted: bool,
        halt_reason: str | None,
    ) -> None:
        self._store.mark_publish_result(
            token_id=token_id,
            publish_decision=publish_decision,
            halted=halted,
            halt_reason=halt_reason,
        )

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> CheckpointCommitResult:
        return self._store.commit_checkpoint(
            token_id=token_id,
            checkpoint_ref=checkpoint_ref,
            committed_at_utc=committed_at_utc,
        )


class _CheckpointStore:
    def issue_token(
        self,
        *,
        source_ref_id: str,
        case_trigger_id: str,
        issued_at_utc: str,
    ) -> CheckpointToken:
        raise NotImplementedError

    def mark_ledger_committed(self, *, token_id: str) -> None:
        raise NotImplementedError

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        halted: bool,
        halt_reason: str | None,
    ) -> None:
        raise NotImplementedError

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> CheckpointCommitResult:
        raise NotImplementedError


@dataclass
class _SqliteCheckpointStore(_CheckpointStore):
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def issue_token(
        self,
        *,
        source_ref_id: str,
        case_trigger_id: str,
        issued_at_utc: str,
    ) -> CheckpointToken:
        if not source_ref_id or not case_trigger_id:
            raise CaseTriggerCheckpointError("source_ref_id and case_trigger_id are required")
        token_id = hashlib.sha256(f"{source_ref_id}:{case_trigger_id}".encode("utf-8")).hexdigest()[:32]
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO checkpoint_tokens (
                    token_id, source_ref_id, case_trigger_id, issued_at_utc,
                    ledger_committed, publish_decision, halted, halt_reason,
                    checkpoint_committed, checkpoint_ref_json, committed_at_utc
                ) VALUES (?, ?, ?, ?, 0, NULL, 0, NULL, 0, NULL, NULL)
                """,
                (token_id, source_ref_id, case_trigger_id, issued_at_utc),
            )
        return CheckpointToken(
            token_id=token_id,
            source_ref_id=source_ref_id,
            case_trigger_id=case_trigger_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_ledger_committed(self, *, token_id: str) -> None:
        with sqlite3.connect(self.path) as conn:
            updated = conn.execute(
                "UPDATE checkpoint_tokens SET ledger_committed = 1 WHERE token_id = ?",
                (token_id,),
            ).rowcount
        if updated == 0:
            raise CaseTriggerCheckpointError(f"unknown checkpoint token: {token_id}")

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        halted: bool,
        halt_reason: str | None,
    ) -> None:
        normalized = str(publish_decision or "").upper()
        if normalized not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}:
            raise CaseTriggerCheckpointError(f"unsupported publish decision: {normalized}")
        with sqlite3.connect(self.path) as conn:
            updated = conn.execute(
                """
                UPDATE checkpoint_tokens
                SET publish_decision = ?, halted = ?, halt_reason = ?
                WHERE token_id = ?
                """,
                (normalized, 1 if halted else 0, halt_reason, token_id),
            ).rowcount
        if updated == 0:
            raise CaseTriggerCheckpointError(f"unknown checkpoint token: {token_id}")

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> CheckpointCommitResult:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT ledger_committed, publish_decision, halted, checkpoint_committed
                FROM checkpoint_tokens
                WHERE token_id = ?
                """,
                (token_id,),
            ).fetchone()
            if row is None:
                raise CaseTriggerCheckpointError(f"unknown checkpoint token: {token_id}")
            ledger_committed = bool(row[0])
            publish_decision = str(row[1] or "")
            halted = bool(row[2])
            checkpoint_committed = bool(row[3])

            if checkpoint_committed:
                return CheckpointCommitResult(
                    status=CHECKPOINT_COMMITTED,
                    token_id=token_id,
                    reason=None,
                    checkpoint_ref=checkpoint_ref,
                )

            block_reason = _block_reason(
                ledger_committed=ledger_committed,
                publish_decision=publish_decision,
                halted=halted,
            )
            if block_reason is not None:
                return CheckpointCommitResult(
                    status=CHECKPOINT_BLOCKED,
                    token_id=token_id,
                    reason=block_reason,
                    checkpoint_ref=None,
                )

            conn.execute(
                """
                UPDATE checkpoint_tokens
                SET checkpoint_committed = 1, checkpoint_ref_json = ?, committed_at_utc = ?
                WHERE token_id = ?
                """,
                (
                    json.dumps(checkpoint_ref, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
                    committed_at_utc,
                    token_id,
                ),
            )
        return CheckpointCommitResult(
            status=CHECKPOINT_COMMITTED,
            token_id=token_id,
            reason=None,
            checkpoint_ref=checkpoint_ref,
        )

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_tokens (
                    token_id TEXT PRIMARY KEY,
                    source_ref_id TEXT NOT NULL,
                    case_trigger_id TEXT NOT NULL,
                    issued_at_utc TEXT NOT NULL,
                    ledger_committed INTEGER NOT NULL DEFAULT 0,
                    publish_decision TEXT,
                    halted INTEGER NOT NULL DEFAULT 0,
                    halt_reason TEXT,
                    checkpoint_committed INTEGER NOT NULL DEFAULT 0,
                    checkpoint_ref_json TEXT,
                    committed_at_utc TEXT
                )
                """
            )


@dataclass
class _PostgresCheckpointStore(_CheckpointStore):
    dsn: str

    def __post_init__(self) -> None:
        self._init_db()

    def issue_token(
        self,
        *,
        source_ref_id: str,
        case_trigger_id: str,
        issued_at_utc: str,
    ) -> CheckpointToken:
        if not source_ref_id or not case_trigger_id:
            raise CaseTriggerCheckpointError("source_ref_id and case_trigger_id are required")
        token_id = hashlib.sha256(f"{source_ref_id}:{case_trigger_id}".encode("utf-8")).hexdigest()[:32]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO checkpoint_tokens (
                    token_id, source_ref_id, case_trigger_id, issued_at_utc,
                    ledger_committed, publish_decision, halted, halt_reason,
                    checkpoint_committed, checkpoint_ref_json, committed_at_utc
                ) VALUES (%s, %s, %s, %s, 0, NULL, 0, NULL, 0, NULL, NULL)
                ON CONFLICT (token_id) DO NOTHING
                """,
                (token_id, source_ref_id, case_trigger_id, issued_at_utc),
            )
        return CheckpointToken(
            token_id=token_id,
            source_ref_id=source_ref_id,
            case_trigger_id=case_trigger_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_ledger_committed(self, *, token_id: str) -> None:
        with self._connect() as conn:
            updated = conn.execute(
                "UPDATE checkpoint_tokens SET ledger_committed = 1 WHERE token_id = %s",
                (token_id,),
            ).rowcount
        if updated == 0:
            raise CaseTriggerCheckpointError(f"unknown checkpoint token: {token_id}")

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        halted: bool,
        halt_reason: str | None,
    ) -> None:
        normalized = str(publish_decision or "").upper()
        if normalized not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}:
            raise CaseTriggerCheckpointError(f"unsupported publish decision: {normalized}")
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE checkpoint_tokens
                SET publish_decision = %s, halted = %s, halt_reason = %s
                WHERE token_id = %s
                """,
                (normalized, 1 if halted else 0, halt_reason, token_id),
            ).rowcount
        if updated == 0:
            raise CaseTriggerCheckpointError(f"unknown checkpoint token: {token_id}")

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> CheckpointCommitResult:
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT ledger_committed, publish_decision, halted, checkpoint_committed
                    FROM checkpoint_tokens
                    WHERE token_id = %s
                    FOR UPDATE
                    """,
                    (token_id,),
                ).fetchone()
                if row is None:
                    raise CaseTriggerCheckpointError(f"unknown checkpoint token: {token_id}")
                ledger_committed = bool(row[0])
                publish_decision = str(row[1] or "")
                halted = bool(row[2])
                checkpoint_committed = bool(row[3])

                if checkpoint_committed:
                    return CheckpointCommitResult(
                        status=CHECKPOINT_COMMITTED,
                        token_id=token_id,
                        reason=None,
                        checkpoint_ref=checkpoint_ref,
                    )

                block_reason = _block_reason(
                    ledger_committed=ledger_committed,
                    publish_decision=publish_decision,
                    halted=halted,
                )
                if block_reason is not None:
                    return CheckpointCommitResult(
                        status=CHECKPOINT_BLOCKED,
                        token_id=token_id,
                        reason=block_reason,
                        checkpoint_ref=None,
                    )

                conn.execute(
                    """
                    UPDATE checkpoint_tokens
                    SET checkpoint_committed = 1, checkpoint_ref_json = %s, committed_at_utc = %s
                    WHERE token_id = %s
                    """,
                    (
                        json.dumps(checkpoint_ref, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
                        committed_at_utc,
                        token_id,
                    ),
                )
        return CheckpointCommitResult(
            status=CHECKPOINT_COMMITTED,
            token_id=token_id,
            reason=None,
            checkpoint_ref=checkpoint_ref,
        )

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.dsn)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_tokens (
                    token_id TEXT PRIMARY KEY,
                    source_ref_id TEXT NOT NULL,
                    case_trigger_id TEXT NOT NULL,
                    issued_at_utc TEXT NOT NULL,
                    ledger_committed INTEGER NOT NULL DEFAULT 0,
                    publish_decision TEXT,
                    halted INTEGER NOT NULL DEFAULT 0,
                    halt_reason TEXT,
                    checkpoint_committed INTEGER NOT NULL DEFAULT 0,
                    checkpoint_ref_json TEXT,
                    committed_at_utc TEXT
                )
                """
            )


def _block_reason(
    *,
    ledger_committed: bool,
    publish_decision: str,
    halted: bool,
) -> str | None:
    if not ledger_committed:
        return "LEDGER_NOT_COMMITTED"
    if not publish_decision:
        return "PUBLISH_NOT_RECORDED"
    if halted:
        return "PUBLISH_HALTED"
    if publish_decision == PUBLISH_QUARANTINE:
        return "PUBLISH_QUARANTINED"
    if publish_decision == PUBLISH_AMBIGUOUS:
        return "PUBLISH_AMBIGUOUS"
    if publish_decision not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE}:
        return "PUBLISH_DECISION_UNSAFE"
    return None


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator.replace("sqlite:///", "", 1)
    if locator.startswith("sqlite://"):
        return locator.replace("sqlite://", "", 1)
    return locator
