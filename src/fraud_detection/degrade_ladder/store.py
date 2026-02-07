"""DL current posture store (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .contracts import DegradeContractError, DegradeDecision


class DlPostureStoreError(RuntimeError):
    """Raised when posture store operations fail."""


class DlPostureTrustError(DlPostureStoreError):
    """Raised when stored posture rows are unreadable or internally inconsistent."""


@dataclass(frozen=True)
class DlCommitResult:
    status: str
    posture_seq: int
    updated_at_utc: str


@dataclass(frozen=True)
class DlCurrentPosture:
    scope_key: str
    decision: DegradeDecision
    updated_at_utc: str
    policy_id: str
    policy_revision: str
    policy_content_digest: str | None


def build_store(dsn: str, *, stream_id: str) -> "DlPostureStore":
    if is_postgres_dsn(dsn):
        return PostgresDlPostureStore(dsn=dsn, stream_id=stream_id)
    return SqliteDlPostureStore(path=Path(_sqlite_path(dsn)), stream_id=stream_id)


class DlPostureStore:
    def commit_current(self, *, scope_key: str, decision: DegradeDecision) -> DlCommitResult:
        raise NotImplementedError

    def read_current(self, *, scope_key: str) -> DlCurrentPosture | None:
        raise NotImplementedError


@dataclass
class SqliteDlPostureStore(DlPostureStore):
    path: Path
    stream_id: str

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS dl_current_posture (
                    stream_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    posture_seq INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    policy_revision TEXT NOT NULL,
                    policy_content_digest TEXT,
                    decided_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scope_key)
                );
                """
            )

    def commit_current(self, *, scope_key: str, decision: DegradeDecision) -> DlCommitResult:
        normalized_scope = _normalize_scope(scope_key)
        decision_json = decision.canonical_json()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT posture_seq, decision_json
                FROM dl_current_posture
                WHERE stream_id = ? AND scope_key = ?
                """,
                (self.stream_id, normalized_scope),
            ).fetchone()
            if existing:
                existing_seq = int(existing[0])
                existing_json = str(existing[1])
                if decision.posture_seq < existing_seq:
                    raise DlPostureStoreError(
                        f"POSTURE_SEQ_REGRESSION:{decision.posture_seq}<{existing_seq}"
                    )
                if decision.posture_seq == existing_seq:
                    if decision_json == existing_json:
                        return DlCommitResult(status="noop", posture_seq=decision.posture_seq, updated_at_utc=now)
                    raise DlPostureStoreError(
                        "POSTURE_SEQ_COLLISION:existing seq reused with different decision payload"
                    )
                status = "updated"
            else:
                status = "inserted"

            conn.execute(
                """
                INSERT INTO dl_current_posture (
                    stream_id,
                    scope_key,
                    decision_json,
                    posture_seq,
                    mode,
                    policy_id,
                    policy_revision,
                    policy_content_digest,
                    decided_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(stream_id, scope_key) DO UPDATE SET
                    decision_json=excluded.decision_json,
                    posture_seq=excluded.posture_seq,
                    mode=excluded.mode,
                    policy_id=excluded.policy_id,
                    policy_revision=excluded.policy_revision,
                    policy_content_digest=excluded.policy_content_digest,
                    decided_at_utc=excluded.decided_at_utc,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    self.stream_id,
                    normalized_scope,
                    decision_json,
                    decision.posture_seq,
                    decision.mode,
                    decision.policy_rev.policy_id,
                    decision.policy_rev.revision,
                    decision.policy_rev.content_digest,
                    decision.decided_at_utc,
                    now,
                ),
            )
            return DlCommitResult(status=status, posture_seq=decision.posture_seq, updated_at_utc=now)

    def read_current(self, *, scope_key: str) -> DlCurrentPosture | None:
        normalized_scope = _normalize_scope(scope_key)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT decision_json, posture_seq, mode, policy_id, policy_revision,
                       policy_content_digest, decided_at_utc, updated_at_utc
                FROM dl_current_posture
                WHERE stream_id = ? AND scope_key = ?
                """,
                (self.stream_id, normalized_scope),
            ).fetchone()
        if row is None:
            return None
        return _parse_row(
            scope_key=normalized_scope,
            decision_json=row[0],
            posture_seq=row[1],
            mode=row[2],
            policy_id=row[3],
            policy_revision=row[4],
            policy_content_digest=row[5],
            decided_at_utc=row[6],
            updated_at_utc=row[7],
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path))


@dataclass
class PostgresDlPostureStore(DlPostureStore):
    dsn: str
    stream_id: str

    def __post_init__(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dl_current_posture (
                    stream_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    posture_seq BIGINT NOT NULL,
                    mode TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    policy_revision TEXT NOT NULL,
                    policy_content_digest TEXT,
                    decided_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scope_key)
                )
                """
            )

    def commit_current(self, *, scope_key: str, decision: DegradeDecision) -> DlCommitResult:
        normalized_scope = _normalize_scope(scope_key)
        decision_json = decision.canonical_json()
        now = _utc_now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT posture_seq, decision_json
                    FROM dl_current_posture
                    WHERE stream_id = %s AND scope_key = %s
                    FOR UPDATE
                    """,
                    (self.stream_id, normalized_scope),
                )
                existing = cur.fetchone()
                if existing:
                    existing_seq = int(existing[0])
                    existing_json = str(existing[1])
                    if decision.posture_seq < existing_seq:
                        raise DlPostureStoreError(
                            f"POSTURE_SEQ_REGRESSION:{decision.posture_seq}<{existing_seq}"
                        )
                    if decision.posture_seq == existing_seq:
                        if decision_json == existing_json:
                            return DlCommitResult(
                                status="noop",
                                posture_seq=decision.posture_seq,
                                updated_at_utc=now,
                            )
                        raise DlPostureStoreError(
                            "POSTURE_SEQ_COLLISION:existing seq reused with different decision payload"
                        )
                    status = "updated"
                else:
                    status = "inserted"

                cur.execute(
                    """
                    INSERT INTO dl_current_posture (
                        stream_id,
                        scope_key,
                        decision_json,
                        posture_seq,
                        mode,
                        policy_id,
                        policy_revision,
                        policy_content_digest,
                        decided_at_utc,
                        updated_at_utc
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (stream_id, scope_key) DO UPDATE SET
                        decision_json = excluded.decision_json,
                        posture_seq = excluded.posture_seq,
                        mode = excluded.mode,
                        policy_id = excluded.policy_id,
                        policy_revision = excluded.policy_revision,
                        policy_content_digest = excluded.policy_content_digest,
                        decided_at_utc = excluded.decided_at_utc,
                        updated_at_utc = excluded.updated_at_utc
                    """,
                    (
                        self.stream_id,
                        normalized_scope,
                        decision_json,
                        decision.posture_seq,
                        decision.mode,
                        decision.policy_rev.policy_id,
                        decision.policy_rev.revision,
                        decision.policy_rev.content_digest,
                        decision.decided_at_utc,
                        now,
                    ),
                )
        return DlCommitResult(status=status, posture_seq=decision.posture_seq, updated_at_utc=now)

    def read_current(self, *, scope_key: str) -> DlCurrentPosture | None:
        normalized_scope = _normalize_scope(scope_key)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT decision_json, posture_seq, mode, policy_id, policy_revision,
                       policy_content_digest, decided_at_utc, updated_at_utc
                FROM dl_current_posture
                WHERE stream_id = %s AND scope_key = %s
                """,
                (self.stream_id, normalized_scope),
            ).fetchone()
        if row is None:
            return None
        return _parse_row(
            scope_key=normalized_scope,
            decision_json=row[0],
            posture_seq=row[1],
            mode=row[2],
            policy_id=row[3],
            policy_revision=row[4],
            policy_content_digest=row[5],
            decided_at_utc=row[6],
            updated_at_utc=row[7],
        )

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn)


def _parse_row(
    *,
    scope_key: str,
    decision_json: Any,
    posture_seq: Any,
    mode: Any,
    policy_id: Any,
    policy_revision: Any,
    policy_content_digest: Any,
    decided_at_utc: Any,
    updated_at_utc: Any,
) -> DlCurrentPosture:
    try:
        payload = json.loads(str(decision_json))
    except json.JSONDecodeError as exc:
        raise DlPostureTrustError("POSTURE_ROW_CORRUPT:decision_json is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DlPostureTrustError("POSTURE_ROW_CORRUPT:decision_json must decode to object")

    try:
        decision = DegradeDecision.from_payload(payload)
    except DegradeContractError as exc:
        raise DlPostureTrustError("POSTURE_ROW_CORRUPT:decision payload violates contract") from exc

    expected_seq = int(posture_seq)
    if decision.posture_seq != expected_seq:
        raise DlPostureTrustError(
            "POSTURE_ROW_MISMATCH:posture_seq column differs from decision payload posture_seq"
        )
    if decision.mode != str(mode):
        raise DlPostureTrustError("POSTURE_ROW_MISMATCH:mode column differs from decision payload mode")
    if decision.policy_rev.policy_id != str(policy_id):
        raise DlPostureTrustError("POSTURE_ROW_MISMATCH:policy_id column differs from decision payload policy_id")
    if decision.policy_rev.revision != str(policy_revision):
        raise DlPostureTrustError(
            "POSTURE_ROW_MISMATCH:policy_revision column differs from decision payload revision"
        )
    if decision.decided_at_utc != str(decided_at_utc):
        raise DlPostureTrustError(
            "POSTURE_ROW_MISMATCH:decided_at_utc column differs from decision payload decided_at_utc"
        )

    digest_value = None if policy_content_digest in (None, "") else str(policy_content_digest)
    if decision.policy_rev.content_digest != digest_value:
        raise DlPostureTrustError(
            "POSTURE_ROW_MISMATCH:policy_content_digest column differs from decision payload content_digest"
        )

    return DlCurrentPosture(
        scope_key=scope_key,
        decision=decision,
        updated_at_utc=str(updated_at_utc),
        policy_id=str(policy_id),
        policy_revision=str(policy_revision),
        policy_content_digest=digest_value,
    )


def _normalize_scope(scope_key: str) -> str:
    normalized = str(scope_key).strip()
    if not normalized:
        raise DlPostureStoreError("scope_key must be non-empty")
    return normalized


def _sqlite_path(dsn: str) -> str:
    value = str(dsn or "").strip()
    if not value:
        raise DlPostureStoreError("sqlite store path/DSN must be non-empty")
    if value.startswith("sqlite:///"):
        return value[len("sqlite:///") :]
    if value.startswith("sqlite://"):
        return value[len("sqlite://") :]
    return value


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
