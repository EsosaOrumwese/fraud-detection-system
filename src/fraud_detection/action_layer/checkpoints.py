"""Action Layer checkpoint commit gate (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .publish import PUBLISH_ADMIT, PUBLISH_AMBIGUOUS, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE, PUBLISH_TERMINALS


CHECKPOINT_ISSUED = "ISSUED"
CHECKPOINT_COMMITTED = "COMMITTED"
CHECKPOINT_BLOCKED = "BLOCKED"


class ActionCheckpointError(ValueError):
    """Raised when AL checkpoint transitions are invalid."""


@dataclass(frozen=True)
class ActionCheckpointToken:
    token_id: str
    outcome_id: str
    action_id: str
    decision_id: str
    issued_at_utc: str


@dataclass(frozen=True)
class ActionCheckpointCommitResult:
    status: str
    token_id: str
    reason: str | None = None
    checkpoint_ref: dict[str, Any] | None = None


class ActionCheckpointGate:
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
        outcome_id: str,
        action_id: str,
        decision_id: str,
        issued_at_utc: str,
    ) -> ActionCheckpointToken:
        return self._store.issue_token(
            outcome_id=outcome_id,
            action_id=action_id,
            decision_id=decision_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_outcome_appended(self, *, token_id: str, outcome_hash: str) -> None:
        self._store.mark_outcome_appended(token_id=token_id, outcome_hash=outcome_hash)

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        receipt_ref: str | None,
        reason_code: str | None,
    ) -> None:
        self._store.mark_publish_result(
            token_id=token_id,
            publish_decision=publish_decision,
            receipt_ref=receipt_ref,
            reason_code=reason_code,
        )

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> ActionCheckpointCommitResult:
        return self._store.commit_checkpoint(
            token_id=token_id,
            checkpoint_ref=checkpoint_ref,
            committed_at_utc=committed_at_utc,
        )


class _CheckpointStore:
    def issue_token(
        self,
        *,
        outcome_id: str,
        action_id: str,
        decision_id: str,
        issued_at_utc: str,
    ) -> ActionCheckpointToken:
        raise NotImplementedError

    def mark_outcome_appended(self, *, token_id: str, outcome_hash: str) -> None:
        raise NotImplementedError

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        receipt_ref: str | None,
        reason_code: str | None,
    ) -> None:
        raise NotImplementedError

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> ActionCheckpointCommitResult:
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
        outcome_id: str,
        action_id: str,
        decision_id: str,
        issued_at_utc: str,
    ) -> ActionCheckpointToken:
        if not outcome_id or not action_id or not decision_id:
            raise ActionCheckpointError("outcome_id, action_id, decision_id are required")
        token_id = hashlib.sha256(f"{outcome_id}:{action_id}:{decision_id}".encode("utf-8")).hexdigest()[:32]
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO al_checkpoint_tokens (
                    token_id, outcome_id, action_id, decision_id, issued_at_utc,
                    outcome_appended, outcome_hash,
                    publish_decision, receipt_ref, publish_reason_code,
                    checkpoint_committed, checkpoint_ref_json, committed_at_utc
                ) VALUES (?, ?, ?, ?, ?, 0, NULL, NULL, NULL, NULL, 0, NULL, NULL)
                """,
                (token_id, outcome_id, action_id, decision_id, issued_at_utc),
            )
        return ActionCheckpointToken(
            token_id=token_id,
            outcome_id=outcome_id,
            action_id=action_id,
            decision_id=decision_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_outcome_appended(self, *, token_id: str, outcome_hash: str) -> None:
        if not outcome_hash:
            raise ActionCheckpointError("outcome_hash is required")
        with sqlite3.connect(self.path) as conn:
            updated = conn.execute(
                """
                UPDATE al_checkpoint_tokens
                SET outcome_appended = 1, outcome_hash = ?
                WHERE token_id = ?
                """,
                (outcome_hash, token_id),
            ).rowcount
        if updated == 0:
            raise ActionCheckpointError(f"unknown checkpoint token: {token_id}")

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        receipt_ref: str | None,
        reason_code: str | None,
    ) -> None:
        decision = str(publish_decision or "").upper()
        if decision not in PUBLISH_TERMINALS:
            raise ActionCheckpointError(f"unsupported publish decision: {decision}")
        with sqlite3.connect(self.path) as conn:
            updated = conn.execute(
                """
                UPDATE al_checkpoint_tokens
                SET publish_decision = ?, receipt_ref = ?, publish_reason_code = ?
                WHERE token_id = ?
                """,
                (decision, receipt_ref, reason_code, token_id),
            ).rowcount
        if updated == 0:
            raise ActionCheckpointError(f"unknown checkpoint token: {token_id}")

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> ActionCheckpointCommitResult:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT outcome_appended, publish_decision, checkpoint_committed
                FROM al_checkpoint_tokens
                WHERE token_id = ?
                """,
                (token_id,),
            ).fetchone()
            if row is None:
                raise ActionCheckpointError(f"unknown checkpoint token: {token_id}")
            outcome_appended = bool(row[0])
            publish_decision = str(row[1] or "")
            checkpoint_committed = bool(row[2])

            if checkpoint_committed:
                return ActionCheckpointCommitResult(
                    status=CHECKPOINT_COMMITTED,
                    token_id=token_id,
                    reason=None,
                    checkpoint_ref=checkpoint_ref,
                )
            block_reason = _block_reason(outcome_appended=outcome_appended, publish_decision=publish_decision)
            if block_reason is not None:
                return ActionCheckpointCommitResult(
                    status=CHECKPOINT_BLOCKED,
                    token_id=token_id,
                    reason=block_reason,
                    checkpoint_ref=None,
                )
            conn.execute(
                """
                UPDATE al_checkpoint_tokens
                SET checkpoint_committed = 1, checkpoint_ref_json = ?, committed_at_utc = ?
                WHERE token_id = ?
                """,
                (
                    json.dumps(checkpoint_ref, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
                    committed_at_utc,
                    token_id,
                ),
            )
        return ActionCheckpointCommitResult(
            status=CHECKPOINT_COMMITTED,
            token_id=token_id,
            reason=None,
            checkpoint_ref=checkpoint_ref,
        )

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS al_checkpoint_tokens (
                    token_id TEXT PRIMARY KEY,
                    outcome_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    issued_at_utc TEXT NOT NULL,
                    outcome_appended INTEGER NOT NULL DEFAULT 0,
                    outcome_hash TEXT,
                    publish_decision TEXT,
                    receipt_ref TEXT,
                    publish_reason_code TEXT,
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
        outcome_id: str,
        action_id: str,
        decision_id: str,
        issued_at_utc: str,
    ) -> ActionCheckpointToken:
        if not outcome_id or not action_id or not decision_id:
            raise ActionCheckpointError("outcome_id, action_id, decision_id are required")
        token_id = hashlib.sha256(f"{outcome_id}:{action_id}:{decision_id}".encode("utf-8")).hexdigest()[:32]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO al_checkpoint_tokens (
                    token_id, outcome_id, action_id, decision_id, issued_at_utc,
                    outcome_appended, outcome_hash,
                    publish_decision, receipt_ref, publish_reason_code,
                    checkpoint_committed, checkpoint_ref_json, committed_at_utc
                ) VALUES (%s, %s, %s, %s, %s, 0, NULL, NULL, NULL, NULL, 0, NULL, NULL)
                ON CONFLICT (token_id) DO NOTHING
                """,
                (token_id, outcome_id, action_id, decision_id, issued_at_utc),
            )
        return ActionCheckpointToken(
            token_id=token_id,
            outcome_id=outcome_id,
            action_id=action_id,
            decision_id=decision_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_outcome_appended(self, *, token_id: str, outcome_hash: str) -> None:
        if not outcome_hash:
            raise ActionCheckpointError("outcome_hash is required")
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE al_checkpoint_tokens
                SET outcome_appended = 1, outcome_hash = %s
                WHERE token_id = %s
                """,
                (outcome_hash, token_id),
            ).rowcount
        if updated == 0:
            raise ActionCheckpointError(f"unknown checkpoint token: {token_id}")

    def mark_publish_result(
        self,
        *,
        token_id: str,
        publish_decision: str,
        receipt_ref: str | None,
        reason_code: str | None,
    ) -> None:
        decision = str(publish_decision or "").upper()
        if decision not in PUBLISH_TERMINALS:
            raise ActionCheckpointError(f"unsupported publish decision: {decision}")
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE al_checkpoint_tokens
                SET publish_decision = %s, receipt_ref = %s, publish_reason_code = %s
                WHERE token_id = %s
                """,
                (decision, receipt_ref, reason_code, token_id),
            ).rowcount
        if updated == 0:
            raise ActionCheckpointError(f"unknown checkpoint token: {token_id}")

    def commit_checkpoint(
        self,
        *,
        token_id: str,
        checkpoint_ref: dict[str, Any],
        committed_at_utc: str,
    ) -> ActionCheckpointCommitResult:
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    """
                    SELECT outcome_appended, publish_decision, checkpoint_committed
                    FROM al_checkpoint_tokens
                    WHERE token_id = %s
                    FOR UPDATE
                    """,
                    (token_id,),
                ).fetchone()
                if row is None:
                    raise ActionCheckpointError(f"unknown checkpoint token: {token_id}")
                outcome_appended = bool(row[0])
                publish_decision = str(row[1] or "")
                checkpoint_committed = bool(row[2])

                if checkpoint_committed:
                    return ActionCheckpointCommitResult(
                        status=CHECKPOINT_COMMITTED,
                        token_id=token_id,
                        reason=None,
                        checkpoint_ref=checkpoint_ref,
                    )
                block_reason = _block_reason(outcome_appended=outcome_appended, publish_decision=publish_decision)
                if block_reason is not None:
                    return ActionCheckpointCommitResult(
                        status=CHECKPOINT_BLOCKED,
                        token_id=token_id,
                        reason=block_reason,
                        checkpoint_ref=None,
                    )
                conn.execute(
                    """
                    UPDATE al_checkpoint_tokens
                    SET checkpoint_committed = 1, checkpoint_ref_json = %s, committed_at_utc = %s
                    WHERE token_id = %s
                    """,
                    (
                        json.dumps(checkpoint_ref, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
                        committed_at_utc,
                        token_id,
                    ),
                )
        return ActionCheckpointCommitResult(
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
                CREATE TABLE IF NOT EXISTS al_checkpoint_tokens (
                    token_id TEXT PRIMARY KEY,
                    outcome_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    issued_at_utc TEXT NOT NULL,
                    outcome_appended INTEGER NOT NULL DEFAULT 0,
                    outcome_hash TEXT,
                    publish_decision TEXT,
                    receipt_ref TEXT,
                    publish_reason_code TEXT,
                    checkpoint_committed INTEGER NOT NULL DEFAULT 0,
                    checkpoint_ref_json TEXT,
                    committed_at_utc TEXT
                )
                """
            )


def _block_reason(*, outcome_appended: bool, publish_decision: str) -> str | None:
    if not outcome_appended:
        return "OUTCOME_NOT_COMMITTED"
    if not publish_decision:
        return "PUBLISH_NOT_RECORDED"
    if publish_decision == PUBLISH_AMBIGUOUS:
        return "PUBLISH_AMBIGUOUS"
    if publish_decision not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}:
        return "PUBLISH_DECISION_INVALID"
    return None


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator

