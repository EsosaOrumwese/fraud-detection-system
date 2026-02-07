"""Action Layer storage foundations (Phase 1 lockstep storage kickoff)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Any, Mapping

import psycopg

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.platform_runtime import resolve_run_scoped_path


class ActionLedgerStoreError(RuntimeError):
    """Raised when Action Layer ledger operations fail."""


@dataclass(frozen=True)
class ActionLayerStorageLayout:
    ledger_locator: str
    outcomes_locator: str


@dataclass(frozen=True)
class ActionLedgerRecord:
    platform_run_id: str
    scenario_run_id: str
    idempotency_key: str
    action_id: str
    decision_id: str
    payload_hash: str
    first_seen_at_utc: str


@dataclass(frozen=True)
class ActionLedgerWriteResult:
    status: str
    record: ActionLedgerRecord


@dataclass(frozen=True)
class ActionSemanticLedgerRecord:
    platform_run_id: str
    scenario_run_id: str
    semantic_key: str
    idempotency_key: str
    action_id: str
    decision_id: str
    payload_hash: str
    first_seen_at_utc: str


@dataclass(frozen=True)
class ActionSemanticLedgerWriteResult:
    status: str
    record: ActionSemanticLedgerRecord


def build_storage_layout(config: Mapping[str, Any] | None = None) -> ActionLayerStorageLayout:
    mapped = dict(config or {})
    ledger_locator_raw = str(mapped.get("ledger_locator") or "").strip()
    outcomes_locator_raw = str(mapped.get("outcomes_locator") or "").strip()
    ledger_locator = resolve_run_scoped_path(
        ledger_locator_raw or None,
        suffix="action_layer/al_ledger.sqlite",
        create_if_missing=True,
    )
    outcomes_locator = resolve_run_scoped_path(
        outcomes_locator_raw or None,
        suffix="action_layer/al_outcomes.sqlite",
        create_if_missing=True,
    )
    if not ledger_locator or not outcomes_locator:
        raise ActionLedgerStoreError("failed to resolve action-layer storage layout")
    return ActionLayerStorageLayout(
        ledger_locator=ledger_locator,
        outcomes_locator=outcomes_locator,
    )


class ActionLedgerStore:
    def __init__(self, *, locator: str) -> None:
        self.locator = locator
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def register_intent(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        idempotency_key: str,
        action_id: str,
        decision_id: str,
        payload_hash: str,
        first_seen_at_utc: str,
    ) -> ActionLedgerWriteResult:
        params = (
            platform_run_id,
            scenario_run_id,
            idempotency_key,
            action_id,
            decision_id,
            payload_hash,
            first_seen_at_utc,
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT action_id, decision_id, payload_hash, first_seen_at_utc
                FROM al_intent_ledger
                WHERE platform_run_id = {p1} AND scenario_run_id = {p2} AND idempotency_key = {p3}
                """,
                params[:3],
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO al_intent_ledger (
                        platform_run_id,
                        scenario_run_id,
                        idempotency_key,
                        action_id,
                        decision_id,
                        payload_hash,
                        first_seen_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7})
                    """,
                    params,
                )
                record = ActionLedgerRecord(
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    idempotency_key=idempotency_key,
                    action_id=action_id,
                    decision_id=decision_id,
                    payload_hash=payload_hash,
                    first_seen_at_utc=first_seen_at_utc,
                )
                return ActionLedgerWriteResult(status="NEW", record=record)

            existing = ActionLedgerRecord(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                idempotency_key=idempotency_key,
                action_id=str(row[0]),
                decision_id=str(row[1]),
                payload_hash=str(row[2]),
                first_seen_at_utc=str(row[3]),
            )
            if existing.payload_hash != payload_hash:
                return ActionLedgerWriteResult(status="HASH_MISMATCH", record=existing)
            return ActionLedgerWriteResult(status="DUPLICATE", record=existing)

    def register_semantic_intent(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        semantic_key: str,
        idempotency_key: str,
        action_id: str,
        decision_id: str,
        payload_hash: str,
        first_seen_at_utc: str,
    ) -> ActionSemanticLedgerWriteResult:
        params = (
            platform_run_id,
            scenario_run_id,
            semantic_key,
            idempotency_key,
            action_id,
            decision_id,
            payload_hash,
            first_seen_at_utc,
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT idempotency_key, action_id, decision_id, payload_hash, first_seen_at_utc
                FROM al_semantic_ledger
                WHERE platform_run_id = {p1} AND scenario_run_id = {p2} AND semantic_key = {p3}
                """,
                params[:3],
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO al_semantic_ledger (
                        platform_run_id,
                        scenario_run_id,
                        semantic_key,
                        idempotency_key,
                        action_id,
                        decision_id,
                        payload_hash,
                        first_seen_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8})
                    """,
                    params,
                )
                record = ActionSemanticLedgerRecord(
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    semantic_key=semantic_key,
                    idempotency_key=idempotency_key,
                    action_id=action_id,
                    decision_id=decision_id,
                    payload_hash=payload_hash,
                    first_seen_at_utc=first_seen_at_utc,
                )
                return ActionSemanticLedgerWriteResult(status="NEW", record=record)

            existing = ActionSemanticLedgerRecord(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                semantic_key=semantic_key,
                idempotency_key=str(row[0]),
                action_id=str(row[1]),
                decision_id=str(row[2]),
                payload_hash=str(row[3]),
                first_seen_at_utc=str(row[4]),
            )
            if existing.payload_hash != payload_hash:
                return ActionSemanticLedgerWriteResult(status="HASH_MISMATCH", record=existing)
            return ActionSemanticLedgerWriteResult(status="DUPLICATE", record=existing)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS al_intent_ledger (
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    first_seen_at_utc TEXT NOT NULL,
                    PRIMARY KEY (platform_run_id, scenario_run_id, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_al_intent_ledger_action
                    ON al_intent_ledger (platform_run_id, scenario_run_id, action_id);
                CREATE INDEX IF NOT EXISTS ix_al_intent_ledger_decision
                    ON al_intent_ledger (platform_run_id, scenario_run_id, decision_id);

                CREATE TABLE IF NOT EXISTS al_semantic_ledger (
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    semantic_key TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    first_seen_at_utc TEXT NOT NULL,
                    PRIMARY KEY (platform_run_id, scenario_run_id, semantic_key)
                );
                CREATE INDEX IF NOT EXISTS ix_al_semantic_ledger_idempotency
                    ON al_semantic_ledger (platform_run_id, scenario_run_id, idempotency_key);
                CREATE INDEX IF NOT EXISTS ix_al_semantic_ledger_decision
                    ON al_semantic_ledger (platform_run_id, scenario_run_id, decision_id);
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _render_sql(sql: str, backend: str) -> str:
    if backend == "postgres":
        rendered = sql
        for idx in range(1, 10):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
        return rendered
    rendered = sql
    for idx in range(1, 10):
        rendered = rendered.replace(f"{{p{idx}}}", "?")
    return rendered


def _query_one(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> Any:
    rendered = _render_sql(sql, backend)
    cur = conn.execute(rendered, params) if backend == "sqlite" else conn.cursor().execute(rendered, params)
    return cur.fetchone()


def _execute(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> None:
    rendered = _render_sql(sql, backend)
    if backend == "sqlite":
        conn.execute(rendered, params)
        conn.commit()
        return
    cur = conn.cursor()
    cur.execute(rendered, params)
    conn.commit()
    cur.close()


def _execute_script(conn: Any, backend: str, sql: str) -> None:
    if backend == "sqlite":
        conn.executescript(sql)
        conn.commit()
        return
    cur = conn.cursor()
    for statement in [part.strip() for part in sql.split(";") if part.strip()]:
        cur.execute(statement)
    conn.commit()
    cur.close()
