"""Decision Fabric checkpoint commit gate (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .publish import PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE


CHECKPOINT_ISSUED = "ISSUED"
CHECKPOINT_COMMITTED = "COMMITTED"
CHECKPOINT_BLOCKED = "BLOCKED"


class DecisionCheckpointError(ValueError):
    """Raised when checkpoint gating transitions are invalid."""


@dataclass(frozen=True)
class CheckpointToken:
    token_id: str
    source_event_id: str
    decision_id: str
    issued_at_utc: str


@dataclass(frozen=True)
class CheckpointCommitResult:
    status: str
    token_id: str
    reason: str | None = None
    checkpoint_ref: dict[str, Any] | None = None


class DecisionCheckpointGate:
    def __init__(self, db_path: str | Path) -> None:
        locator = str(db_path)
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "postgres":
            self._store: _CheckpointStore = _PostgresCheckpointStore(dsn=locator)
        else:
            self._store = _SqliteCheckpointStore(path=Path(_sqlite_path(locator)))

    def issue_token(self, *, source_event_id: str, decision_id: str, issued_at_utc: str) -> CheckpointToken:
        return self._store.issue_token(source_event_id=source_event_id, decision_id=decision_id, issued_at_utc=issued_at_utc)

    def mark_ledger_committed(self, *, token_id: str) -> None:
        self._store.mark_ledger_committed(token_id=token_id)

    def mark_publish_result(
        self,
        *,
        token_id: str,
        decision_publish: str,
        action_publishes: tuple[str, ...],
        halted: bool,
        halt_reason: str | None,
    ) -> None:
        self._store.mark_publish_result(
            token_id=token_id,
            decision_publish=decision_publish,
            action_publishes=action_publishes,
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
    def issue_token(self, *, source_event_id: str, decision_id: str, issued_at_utc: str) -> CheckpointToken:
        raise NotImplementedError

    def mark_ledger_committed(self, *, token_id: str) -> None:
        raise NotImplementedError

    def mark_publish_result(
        self,
        *,
        token_id: str,
        decision_publish: str,
        action_publishes: tuple[str, ...],
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

    def issue_token(self, *, source_event_id: str, decision_id: str, issued_at_utc: str) -> CheckpointToken:
        if not source_event_id or not decision_id:
            raise DecisionCheckpointError("source_event_id and decision_id are required")
        token_id = hashlib.sha256(f"{source_event_id}:{decision_id}".encode("utf-8")).hexdigest()[:32]
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO df_checkpoint_tokens (
                    token_id, source_event_id, decision_id, issued_at_utc, ledger_committed,
                    publish_decision, action_decisions_json, halted, halt_reason,
                    checkpoint_committed, checkpoint_ref_json, committed_at_utc
                ) VALUES (?, ?, ?, ?, 0, NULL, NULL, 0, NULL, 0, NULL, NULL)
                """,
                (token_id, source_event_id, decision_id, issued_at_utc),
            )
        return CheckpointToken(
            token_id=token_id,
            source_event_id=source_event_id,
            decision_id=decision_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_ledger_committed(self, *, token_id: str) -> None:
        with sqlite3.connect(self.path) as conn:
            updated = conn.execute(
                "UPDATE df_checkpoint_tokens SET ledger_committed = 1 WHERE token_id = ?",
                (token_id,),
            ).rowcount
        if updated == 0:
            raise DecisionCheckpointError(f"unknown checkpoint token: {token_id}")

    def mark_publish_result(
        self,
        *,
        token_id: str,
        decision_publish: str,
        action_publishes: tuple[str, ...],
        halted: bool,
        halt_reason: str | None,
    ) -> None:
        normalized_decision = str(decision_publish or "").upper()
        if normalized_decision not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}:
            raise DecisionCheckpointError(f"unsupported decision publish result: {normalized_decision}")
        normalized_actions = tuple(str(item or "").upper() for item in action_publishes)
        for item in normalized_actions:
            if item not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}:
                raise DecisionCheckpointError(f"unsupported action publish result: {item}")
        with sqlite3.connect(self.path) as conn:
            updated = conn.execute(
                """
                UPDATE df_checkpoint_tokens
                SET publish_decision = ?, action_decisions_json = ?, halted = ?, halt_reason = ?
                WHERE token_id = ?
                """,
                (
                    normalized_decision,
                    json.dumps(list(normalized_actions), sort_keys=True, ensure_ascii=True, separators=(",", ":")),
                    1 if halted else 0,
                    halt_reason,
                    token_id,
                ),
            ).rowcount
        if updated == 0:
            raise DecisionCheckpointError(f"unknown checkpoint token: {token_id}")

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
                SELECT ledger_committed, publish_decision, action_decisions_json, halted, checkpoint_committed
                FROM df_checkpoint_tokens
                WHERE token_id = ?
                """,
                (token_id,),
            ).fetchone()
            if row is None:
                raise DecisionCheckpointError(f"unknown checkpoint token: {token_id}")
            ledger_committed = bool(row[0])
            publish_decision = str(row[1] or "")
            action_decisions = _parse_action_decisions(row[2])
            halted = bool(row[3])
            checkpoint_committed = bool(row[4])

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
                action_decisions=action_decisions,
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
                UPDATE df_checkpoint_tokens
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
                CREATE TABLE IF NOT EXISTS df_checkpoint_tokens (
                    token_id TEXT PRIMARY KEY,
                    source_event_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    issued_at_utc TEXT NOT NULL,
                    ledger_committed INTEGER NOT NULL DEFAULT 0,
                    publish_decision TEXT,
                    action_decisions_json TEXT,
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

    def issue_token(self, *, source_event_id: str, decision_id: str, issued_at_utc: str) -> CheckpointToken:
        if not source_event_id or not decision_id:
            raise DecisionCheckpointError("source_event_id and decision_id are required")
        token_id = hashlib.sha256(f"{source_event_id}:{decision_id}".encode("utf-8")).hexdigest()[:32]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO df_checkpoint_tokens (
                    token_id, source_event_id, decision_id, issued_at_utc, ledger_committed,
                    publish_decision, action_decisions_json, halted, halt_reason,
                    checkpoint_committed, checkpoint_ref_json, committed_at_utc
                ) VALUES (%s, %s, %s, %s, 0, NULL, NULL, 0, NULL, 0, NULL, NULL)
                ON CONFLICT (token_id) DO NOTHING
                """,
                (token_id, source_event_id, decision_id, issued_at_utc),
            )
        return CheckpointToken(
            token_id=token_id,
            source_event_id=source_event_id,
            decision_id=decision_id,
            issued_at_utc=issued_at_utc,
        )

    def mark_ledger_committed(self, *, token_id: str) -> None:
        with self._connect() as conn:
            updated = conn.execute(
                "UPDATE df_checkpoint_tokens SET ledger_committed = 1 WHERE token_id = %s",
                (token_id,),
            ).rowcount
        if updated == 0:
            raise DecisionCheckpointError(f"unknown checkpoint token: {token_id}")

    def mark_publish_result(
        self,
        *,
        token_id: str,
        decision_publish: str,
        action_publishes: tuple[str, ...],
        halted: bool,
        halt_reason: str | None,
    ) -> None:
        normalized_decision = str(decision_publish or "").upper()
        if normalized_decision not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}:
            raise DecisionCheckpointError(f"unsupported decision publish result: {normalized_decision}")
        normalized_actions = tuple(str(item or "").upper() for item in action_publishes)
        for item in normalized_actions:
            if item not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE}:
                raise DecisionCheckpointError(f"unsupported action publish result: {item}")
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE df_checkpoint_tokens
                SET publish_decision = %s, action_decisions_json = %s, halted = %s, halt_reason = %s
                WHERE token_id = %s
                """,
                (
                    normalized_decision,
                    json.dumps(list(normalized_actions), sort_keys=True, ensure_ascii=True, separators=(",", ":")),
                    1 if halted else 0,
                    halt_reason,
                    token_id,
                ),
            ).rowcount
        if updated == 0:
            raise DecisionCheckpointError(f"unknown checkpoint token: {token_id}")

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
                    SELECT ledger_committed, publish_decision, action_decisions_json, halted, checkpoint_committed
                    FROM df_checkpoint_tokens
                    WHERE token_id = %s
                    FOR UPDATE
                    """,
                    (token_id,),
                ).fetchone()
                if row is None:
                    raise DecisionCheckpointError(f"unknown checkpoint token: {token_id}")
                ledger_committed = bool(row[0])
                publish_decision = str(row[1] or "")
                action_decisions = _parse_action_decisions(row[2])
                halted = bool(row[3])
                checkpoint_committed = bool(row[4])

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
                    action_decisions=action_decisions,
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
                    UPDATE df_checkpoint_tokens
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

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS df_checkpoint_tokens (
                    token_id TEXT PRIMARY KEY,
                    source_event_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    issued_at_utc TEXT NOT NULL,
                    ledger_committed INTEGER NOT NULL DEFAULT 0,
                    publish_decision TEXT,
                    action_decisions_json TEXT,
                    halted INTEGER NOT NULL DEFAULT 0,
                    halt_reason TEXT,
                    checkpoint_committed INTEGER NOT NULL DEFAULT 0,
                    checkpoint_ref_json TEXT,
                    committed_at_utc TEXT
                )
                """
            )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


def _parse_action_decisions(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return tuple()
    try:
        payload = json.loads(str(value))
    except Exception:
        return tuple()
    if not isinstance(payload, list):
        return tuple()
    return tuple(str(item or "").upper() for item in payload)


def _block_reason(
    *,
    ledger_committed: bool,
    publish_decision: str,
    action_decisions: tuple[str, ...],
    halted: bool,
) -> str | None:
    if not ledger_committed:
        return "LEDGER_NOT_COMMITTED"
    if not publish_decision:
        return "PUBLISH_NOT_RECORDED"
    if halted:
        return "PUBLISH_HALTED"
    if publish_decision == PUBLISH_QUARANTINE:
        return "DECISION_QUARANTINED"
    if any(item == PUBLISH_QUARANTINE for item in action_decisions):
        return "ACTION_QUARANTINED"
    if publish_decision not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE}:
        return "PUBLISH_DECISION_UNSAFE"
    return None


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator.replace("sqlite:///", "", 1)
    if locator.startswith("sqlite://"):
        return locator.replace("sqlite://", "", 1)
    return locator

