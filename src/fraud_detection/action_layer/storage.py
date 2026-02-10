"""Action Layer storage foundations (Phase 1 lockstep storage kickoff)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import json
import re
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


@dataclass(frozen=True)
class ActionOutcomeAppendRecord:
    outcome_id: str
    platform_run_id: str
    scenario_run_id: str
    decision_id: str
    action_id: str
    status: str
    idempotency_key: str
    payload_hash: str
    completed_at_utc: str
    recorded_at_utc: str


@dataclass(frozen=True)
class ActionOutcomeAppendWriteResult:
    status: str
    record: ActionOutcomeAppendRecord


@dataclass(frozen=True)
class ActionOutcomePublishRecord:
    outcome_id: str
    event_id: str
    event_type: str
    publish_decision: str
    receipt_id: str | None
    receipt_ref: str | None
    reason_code: str | None
    published_at_utc: str
    publish_hash: str


@dataclass(frozen=True)
class ActionOutcomePublishWriteResult:
    status: str
    record: ActionOutcomePublishRecord


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


class ActionOutcomeStore:
    _PUBLISH_DECISIONS = {"ADMIT", "DUPLICATE", "QUARANTINE", "AMBIGUOUS"}

    def __init__(self, *, locator: str) -> None:
        self.locator = locator
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def register_outcome(
        self,
        *,
        outcome_payload: Mapping[str, Any],
        recorded_at_utc: str,
    ) -> ActionOutcomeAppendWriteResult:
        payload = dict(outcome_payload)
        pins = payload.get("pins")
        if not isinstance(pins, Mapping):
            raise ActionLedgerStoreError("outcome payload pins must be a mapping")

        outcome_id = str(payload.get("outcome_id") or "").strip()
        platform_run_id = str(pins.get("platform_run_id") or "").strip()
        scenario_run_id = str(pins.get("scenario_run_id") or "").strip()
        decision_id = str(payload.get("decision_id") or "").strip()
        action_id = str(payload.get("action_id") or "").strip()
        status = str(payload.get("status") or "").strip()
        idempotency_key = str(payload.get("idempotency_key") or "").strip()
        completed_at_utc = str(payload.get("completed_at_utc") or "").strip()
        if not all(
            (
                outcome_id,
                platform_run_id,
                scenario_run_id,
                decision_id,
                action_id,
                status,
                idempotency_key,
                completed_at_utc,
            )
        ):
            raise ActionLedgerStoreError("outcome payload missing required append fields")

        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        params = (
            outcome_id,
            platform_run_id,
            scenario_run_id,
            decision_id,
            action_id,
            status,
            idempotency_key,
            payload_hash,
            json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
            completed_at_utc,
            recorded_at_utc,
        )

        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT platform_run_id, scenario_run_id, decision_id, action_id, status,
                       idempotency_key, payload_hash, completed_at_utc, recorded_at_utc
                FROM al_outcomes_append
                WHERE outcome_id = {p1}
                """,
                (outcome_id,),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO al_outcomes_append (
                        outcome_id, platform_run_id, scenario_run_id, decision_id, action_id,
                        status, idempotency_key, payload_hash, payload_json, completed_at_utc, recorded_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10}, {p11})
                    """,
                    params,
                )
                record = ActionOutcomeAppendRecord(
                    outcome_id=outcome_id,
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    decision_id=decision_id,
                    action_id=action_id,
                    status=status,
                    idempotency_key=idempotency_key,
                    payload_hash=payload_hash,
                    completed_at_utc=completed_at_utc,
                    recorded_at_utc=recorded_at_utc,
                )
                return ActionOutcomeAppendWriteResult(status="NEW", record=record)

            existing = ActionOutcomeAppendRecord(
                outcome_id=outcome_id,
                platform_run_id=str(row[0]),
                scenario_run_id=str(row[1]),
                decision_id=str(row[2]),
                action_id=str(row[3]),
                status=str(row[4]),
                idempotency_key=str(row[5]),
                payload_hash=str(row[6]),
                completed_at_utc=str(row[7]),
                recorded_at_utc=str(row[8]),
            )
            if existing.payload_hash == payload_hash:
                return ActionOutcomeAppendWriteResult(status="DUPLICATE", record=existing)
            return ActionOutcomeAppendWriteResult(status="HASH_MISMATCH", record=existing)

    def register_publish_result(
        self,
        *,
        outcome_id: str,
        event_id: str,
        event_type: str,
        publish_decision: str,
        receipt: Mapping[str, Any] | None,
        receipt_ref: str | None,
        reason_code: str | None,
        published_at_utc: str,
    ) -> ActionOutcomePublishWriteResult:
        decision = str(publish_decision or "").strip().upper()
        if decision not in self._PUBLISH_DECISIONS:
            raise ActionLedgerStoreError(f"unsupported publish decision: {decision}")
        receipt_id = None
        if isinstance(receipt, Mapping):
            receipt_id_raw = receipt.get("receipt_id")
            receipt_id = str(receipt_id_raw).strip() if receipt_id_raw not in (None, "") else None
        receipt_ref_value = str(receipt_ref).strip() if receipt_ref not in (None, "") else None
        reason = str(reason_code).strip() if reason_code not in (None, "") else None
        publish_identity = {
            "outcome_id": outcome_id,
            "event_id": event_id,
            "event_type": event_type,
            "publish_decision": decision,
            "receipt_id": receipt_id,
            "receipt_ref": receipt_ref_value,
            "reason_code": reason,
        }
        publish_hash = hashlib.sha256(
            json.dumps(publish_identity, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        receipt_json = (
            json.dumps(dict(receipt), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            if isinstance(receipt, Mapping)
            else None
        )
        params = (
            outcome_id,
            event_id,
            event_type,
            decision,
            receipt_id,
            receipt_ref_value,
            reason,
            published_at_utc,
            publish_hash,
            receipt_json,
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT event_id, event_type, publish_decision, receipt_id, receipt_ref,
                       reason_code, published_at_utc, publish_hash
                FROM al_outcome_publish
                WHERE outcome_id = {p1}
                """,
                (outcome_id,),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO al_outcome_publish (
                        outcome_id, event_id, event_type, publish_decision, receipt_id,
                        receipt_ref, reason_code, published_at_utc, publish_hash, receipt_json
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10})
                    """,
                    params,
                )
                record = ActionOutcomePublishRecord(
                    outcome_id=outcome_id,
                    event_id=event_id,
                    event_type=event_type,
                    publish_decision=decision,
                    receipt_id=receipt_id,
                    receipt_ref=receipt_ref_value,
                    reason_code=reason,
                    published_at_utc=published_at_utc,
                    publish_hash=publish_hash,
                )
                return ActionOutcomePublishWriteResult(status="NEW", record=record)

            existing = ActionOutcomePublishRecord(
                outcome_id=outcome_id,
                event_id=str(row[0]),
                event_type=str(row[1]),
                publish_decision=str(row[2]),
                receipt_id=None if row[3] in (None, "") else str(row[3]),
                receipt_ref=None if row[4] in (None, "") else str(row[4]),
                reason_code=None if row[5] in (None, "") else str(row[5]),
                published_at_utc=str(row[6]),
                publish_hash=str(row[7]),
            )
            if existing.publish_hash == publish_hash:
                return ActionOutcomePublishWriteResult(status="DUPLICATE", record=existing)
            return ActionOutcomePublishWriteResult(status="HASH_MISMATCH", record=existing)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS al_outcomes_append (
                    outcome_id TEXT PRIMARY KEY,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    completed_at_utc TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_al_outcomes_append_run_scope
                    ON al_outcomes_append (platform_run_id, scenario_run_id, recorded_at_utc);
                CREATE INDEX IF NOT EXISTS ix_al_outcomes_append_decision
                    ON al_outcomes_append (decision_id);

                CREATE TABLE IF NOT EXISTS al_outcome_publish (
                    outcome_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    publish_decision TEXT NOT NULL,
                    receipt_id TEXT,
                    receipt_ref TEXT,
                    reason_code TEXT,
                    published_at_utc TEXT NOT NULL,
                    publish_hash TEXT NOT NULL,
                    receipt_json TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_al_outcome_publish_decision
                    ON al_outcome_publish (publish_decision, published_at_utc);
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
    placeholder = "%s" if backend == "postgres" else "?"
    return _SQL_PARAM_PATTERN.sub(placeholder, sql)


_SQL_PARAM_PATTERN = re.compile(r"\{p(?P<index>\d+)\}")


def _render_sql_with_params(sql: str, backend: str, params: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]]:
    ordered_params: list[Any] = []
    placeholder = "%s" if backend == "postgres" else "?"

    def _replace(match: re.Match[str]) -> str:
        index = int(match.group("index"))
        if index <= 0 or index > len(params):
            raise ActionLedgerStoreError(
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


def _execute(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> None:
    rendered, ordered_params = _render_sql_with_params(sql, backend, params)
    if backend == "sqlite":
        conn.execute(rendered, ordered_params)
        conn.commit()
        return
    cur = conn.cursor()
    cur.execute(rendered, ordered_params)
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
