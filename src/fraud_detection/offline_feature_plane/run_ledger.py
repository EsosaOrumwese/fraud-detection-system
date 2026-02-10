"""OFS Phase 2 durable run ledger and state machine."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import sqlite3
from typing import Any, Mapping

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.postgres_runtime import postgres_threadlocal_connection

from .contracts import OfsBuildIntent


OFS_RUN_QUEUED = "QUEUED"
OFS_RUN_RUNNING = "RUNNING"
OFS_RUN_DONE = "DONE"
OFS_RUN_FAILED = "FAILED"
OFS_RUN_PUBLISH_PENDING = "PUBLISH_PENDING"

OFS_EXECUTION_NONE = "NONE"
OFS_EXECUTION_FULL = "FULL"
OFS_EXECUTION_PUBLISH_ONLY = "PUBLISH_ONLY"

OFS_SUBMIT_NEW = "NEW"
OFS_SUBMIT_DUPLICATE = "DUPLICATE"

OFS_RETRY_ALLOWED = "ALLOWED"
OFS_RETRY_NOT_PENDING = "NOT_PENDING"
OFS_RETRY_EXHAUSTED = "EXHAUSTED"


class OfsRunLedgerError(RuntimeError):
    """Raised when OFS run-ledger operations are invalid."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code or "").strip() or "UNKNOWN"
        self.message = str(message or "").strip() or self.code
        super().__init__(f"{self.code}:{self.message}")


@dataclass(frozen=True)
class OfsRunReceipt:
    run_key: str
    request_id: str
    intent_kind: str
    status: str
    execution_mode: str
    full_run_attempts: int
    publish_retry_attempts: int
    last_error_code: str | None
    result_ref: str | None
    input_summary: dict[str, Any]
    provenance: dict[str, Any]
    created_at_utc: str
    updated_at_utc: str
    last_transition_at_utc: str
    last_started_at_utc: str | None
    last_completed_at_utc: str | None


@dataclass(frozen=True)
class OfsRunSubmission:
    outcome: str
    run_key: str
    receipt: OfsRunReceipt


@dataclass(frozen=True)
class OfsPublishRetryDecision:
    decision: str
    run_key: str
    attempts_used: int
    max_attempts: int


@dataclass(frozen=True)
class OfsRunEvent:
    run_key: str
    seq: int
    event_type: str
    status: str
    event_at_utc: str
    reason_code: str | None
    detail: dict[str, Any]


class OfsRunLedger:
    """Durable ledger for OFS run-control state."""

    def __init__(self, *, locator: str) -> None:
        self.locator = str(locator or "").strip()
        if not self.locator:
            raise ValueError("ofs run ledger locator is required")
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            sqlite3.connect(_sqlite_path(self.locator)).close()
        self._ensure_schema()

    def submit_intent(self, *, intent: OfsBuildIntent, queued_at_utc: str) -> OfsRunSubmission:
        request_id = str(intent.request_id)
        run_key = deterministic_run_key(request_id)
        payload_hash = canonical_intent_payload_hash(intent.as_dict())
        input_summary = _input_summary(intent)
        provenance = _provenance_summary(intent)
        with self._connect() as conn:
            existing = conn.execute(
                *self._sql_with_params(
                    """
                    SELECT run_key, request_payload_hash
                      FROM ofs_run_ledger
                     WHERE request_id = {p1}
                    """,
                    (request_id,),
                )
            ).fetchone()
            if existing is not None:
                existing_run_key = str(existing[0])
                existing_payload_hash = str(existing[1])
                if existing_payload_hash != payload_hash:
                    raise OfsRunLedgerError(
                        "REQUEST_ID_PAYLOAD_MISMATCH",
                        "request_id already exists with a different intent payload hash",
                    )
                receipt = self._receipt_tx(conn=conn, run_key=existing_run_key)
                return OfsRunSubmission(outcome=OFS_SUBMIT_DUPLICATE, run_key=existing_run_key, receipt=receipt)

            conn.execute(
                *self._sql_with_params(
                    """
                    INSERT INTO ofs_run_ledger (
                        run_key, request_id, request_payload_hash, intent_kind, status, execution_mode,
                        full_run_attempts, publish_retry_attempts, last_error_code, result_ref,
                        input_summary_json, provenance_json,
                        created_at_utc, updated_at_utc, last_transition_at_utc,
                        last_started_at_utc, last_completed_at_utc
                    ) VALUES (
                        {p1}, {p2}, {p3}, {p4}, {p5}, {p6},
                        0, 0, NULL, NULL,
                        {p7}, {p8},
                        {p9}, {p9}, {p9},
                        NULL, NULL
                    )
                    """,
                    (
                        run_key,
                        request_id,
                        payload_hash,
                        str(intent.intent_kind),
                        OFS_RUN_QUEUED,
                        OFS_EXECUTION_NONE,
                        _json_dump(input_summary),
                        _json_dump(provenance),
                        str(queued_at_utc),
                    ),
                )
            )
            self._append_event_tx(
                conn=conn,
                run_key=run_key,
                event_type="INTENT_QUEUED",
                status=OFS_RUN_QUEUED,
                event_at_utc=str(queued_at_utc),
                reason_code=None,
                detail={
                    "request_id": request_id,
                    "intent_kind": str(intent.intent_kind),
                    "payload_hash": payload_hash,
                },
            )
            receipt = self._receipt_tx(conn=conn, run_key=run_key)
            return OfsRunSubmission(outcome=OFS_SUBMIT_NEW, run_key=run_key, receipt=receipt)

    def start_run(self, *, run_key: str, started_at_utc: str, mode: str = OFS_EXECUTION_FULL) -> OfsRunReceipt:
        normalized_mode = str(mode or "").strip().upper()
        if normalized_mode not in {OFS_EXECUTION_FULL, OFS_EXECUTION_PUBLISH_ONLY}:
            raise OfsRunLedgerError("INVALID_MODE", f"unsupported run mode: {mode}")
        with self._connect() as conn:
            row = self._require_row(conn=conn, run_key=run_key)
            current_status = str(row["status"])
            current_mode = str(row["execution_mode"])
            full_attempts = int(row["full_run_attempts"])
            if normalized_mode == OFS_EXECUTION_FULL:
                if current_status == OFS_RUN_RUNNING and current_mode == OFS_EXECUTION_FULL:
                    return self._receipt_tx(conn=conn, run_key=run_key)
                if current_status != OFS_RUN_QUEUED:
                    raise OfsRunLedgerError(
                        "INVALID_TRANSITION",
                        f"cannot start full run from status {current_status}",
                    )
                full_attempts = full_attempts + 1
            else:
                if current_status == OFS_RUN_RUNNING and current_mode == OFS_EXECUTION_PUBLISH_ONLY:
                    return self._receipt_tx(conn=conn, run_key=run_key)
                if current_status != OFS_RUN_PUBLISH_PENDING:
                    raise OfsRunLedgerError(
                        "INVALID_TRANSITION",
                        f"cannot start publish-only retry from status {current_status}",
                    )

            conn.execute(
                *self._sql_with_params(
                    """
                    UPDATE ofs_run_ledger
                       SET status = {p2},
                           execution_mode = {p3},
                           full_run_attempts = {p4},
                           last_error_code = NULL,
                           updated_at_utc = {p5},
                           last_transition_at_utc = {p5},
                           last_started_at_utc = {p5}
                     WHERE run_key = {p1}
                    """,
                    (run_key, OFS_RUN_RUNNING, normalized_mode, full_attempts, str(started_at_utc)),
                )
            )
            self._append_event_tx(
                conn=conn,
                run_key=run_key,
                event_type="RUN_STARTED",
                status=OFS_RUN_RUNNING,
                event_at_utc=str(started_at_utc),
                reason_code=None,
                detail={"execution_mode": normalized_mode},
            )
            return self._receipt_tx(conn=conn, run_key=run_key)

    def mark_publish_pending(self, *, run_key: str, pending_at_utc: str, reason_code: str) -> OfsRunReceipt:
        reason = str(reason_code or "").strip() or "PUBLISH_PENDING"
        with self._connect() as conn:
            row = self._require_row(conn=conn, run_key=run_key)
            current_status = str(row["status"])
            if current_status == OFS_RUN_PUBLISH_PENDING and str(row["last_error_code"] or "") == reason:
                return self._receipt_tx(conn=conn, run_key=run_key)
            if current_status != OFS_RUN_RUNNING:
                raise OfsRunLedgerError(
                    "INVALID_TRANSITION",
                    f"cannot mark publish pending from status {current_status}",
                )
            conn.execute(
                *self._sql_with_params(
                    """
                    UPDATE ofs_run_ledger
                       SET status = {p2},
                           last_error_code = {p3},
                           updated_at_utc = {p4},
                           last_transition_at_utc = {p4}
                     WHERE run_key = {p1}
                    """,
                    (run_key, OFS_RUN_PUBLISH_PENDING, reason, str(pending_at_utc)),
                )
            )
            self._append_event_tx(
                conn=conn,
                run_key=run_key,
                event_type="PUBLISH_PENDING",
                status=OFS_RUN_PUBLISH_PENDING,
                event_at_utc=str(pending_at_utc),
                reason_code=reason,
                detail={},
            )
            return self._receipt_tx(conn=conn, run_key=run_key)

    def request_publish_retry(
        self,
        *,
        run_key: str,
        requested_at_utc: str,
        max_attempts: int,
    ) -> OfsPublishRetryDecision:
        if int(max_attempts) < 1:
            raise OfsRunLedgerError("INVALID_RETRY_POLICY", "max_attempts must be >= 1")
        with self._connect() as conn:
            row = self._require_row(conn=conn, run_key=run_key)
            status = str(row["status"])
            attempts = int(row["publish_retry_attempts"])
            if status != OFS_RUN_PUBLISH_PENDING:
                self._append_event_tx(
                    conn=conn,
                    run_key=run_key,
                    event_type="PUBLISH_RETRY_SKIPPED",
                    status=status,
                    event_at_utc=str(requested_at_utc),
                    reason_code="RETRY_NOT_PENDING",
                    detail={"publish_retry_attempts": attempts, "max_attempts": int(max_attempts)},
                )
                return OfsPublishRetryDecision(
                    decision=OFS_RETRY_NOT_PENDING,
                    run_key=run_key,
                    attempts_used=attempts,
                    max_attempts=int(max_attempts),
                )
            if attempts >= int(max_attempts):
                self._append_event_tx(
                    conn=conn,
                    run_key=run_key,
                    event_type="PUBLISH_RETRY_EXHAUSTED",
                    status=OFS_RUN_PUBLISH_PENDING,
                    event_at_utc=str(requested_at_utc),
                    reason_code="PUBLISH_RETRY_EXHAUSTED",
                    detail={"publish_retry_attempts": attempts, "max_attempts": int(max_attempts)},
                )
                return OfsPublishRetryDecision(
                    decision=OFS_RETRY_EXHAUSTED,
                    run_key=run_key,
                    attempts_used=attempts,
                    max_attempts=int(max_attempts),
                )

            attempts = attempts + 1
            conn.execute(
                *self._sql_with_params(
                    """
                    UPDATE ofs_run_ledger
                       SET publish_retry_attempts = {p2},
                           updated_at_utc = {p3}
                     WHERE run_key = {p1}
                    """,
                    (run_key, attempts, str(requested_at_utc)),
                )
            )
            self._append_event_tx(
                conn=conn,
                run_key=run_key,
                event_type="PUBLISH_RETRY_REQUESTED",
                status=OFS_RUN_PUBLISH_PENDING,
                event_at_utc=str(requested_at_utc),
                reason_code="PUBLISH_RETRY_ALLOWED",
                detail={"publish_retry_attempts": attempts, "max_attempts": int(max_attempts)},
            )
            return OfsPublishRetryDecision(
                decision=OFS_RETRY_ALLOWED,
                run_key=run_key,
                attempts_used=attempts,
                max_attempts=int(max_attempts),
            )

    def mark_done(self, *, run_key: str, completed_at_utc: str, result_ref: str | None = None) -> OfsRunReceipt:
        with self._connect() as conn:
            row = self._require_row(conn=conn, run_key=run_key)
            current_status = str(row["status"])
            if current_status == OFS_RUN_DONE:
                return self._receipt_tx(conn=conn, run_key=run_key)
            if current_status != OFS_RUN_RUNNING:
                raise OfsRunLedgerError("INVALID_TRANSITION", f"cannot mark done from status {current_status}")
            conn.execute(
                *self._sql_with_params(
                    """
                    UPDATE ofs_run_ledger
                       SET status = {p2},
                           result_ref = {p3},
                           last_error_code = NULL,
                           updated_at_utc = {p4},
                           last_transition_at_utc = {p4},
                           last_completed_at_utc = {p4}
                     WHERE run_key = {p1}
                    """,
                    (run_key, OFS_RUN_DONE, _none_if_blank(result_ref), str(completed_at_utc)),
                )
            )
            self._append_event_tx(
                conn=conn,
                run_key=run_key,
                event_type="RUN_DONE",
                status=OFS_RUN_DONE,
                event_at_utc=str(completed_at_utc),
                reason_code=None,
                detail={"result_ref": _none_if_blank(result_ref)},
            )
            return self._receipt_tx(conn=conn, run_key=run_key)

    def mark_failed(self, *, run_key: str, failed_at_utc: str, reason_code: str) -> OfsRunReceipt:
        reason = str(reason_code or "").strip() or "FAILED"
        with self._connect() as conn:
            row = self._require_row(conn=conn, run_key=run_key)
            current_status = str(row["status"])
            if current_status == OFS_RUN_FAILED and str(row["last_error_code"] or "") == reason:
                return self._receipt_tx(conn=conn, run_key=run_key)
            if current_status not in {OFS_RUN_QUEUED, OFS_RUN_RUNNING, OFS_RUN_PUBLISH_PENDING, OFS_RUN_FAILED}:
                raise OfsRunLedgerError("INVALID_TRANSITION", f"cannot mark failed from status {current_status}")
            conn.execute(
                *self._sql_with_params(
                    """
                    UPDATE ofs_run_ledger
                       SET status = {p2},
                           last_error_code = {p3},
                           updated_at_utc = {p4},
                           last_transition_at_utc = {p4},
                           last_completed_at_utc = {p4}
                     WHERE run_key = {p1}
                    """,
                    (run_key, OFS_RUN_FAILED, reason, str(failed_at_utc)),
                )
            )
            self._append_event_tx(
                conn=conn,
                run_key=run_key,
                event_type="RUN_FAILED",
                status=OFS_RUN_FAILED,
                event_at_utc=str(failed_at_utc),
                reason_code=reason,
                detail={},
            )
            return self._receipt_tx(conn=conn, run_key=run_key)

    def receipt(self, *, run_key: str) -> OfsRunReceipt:
        with self._connect() as conn:
            return self._receipt_tx(conn=conn, run_key=run_key)

    def list_events(self, *, run_key: str) -> list[OfsRunEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                *self._sql_with_params(
                    """
                    SELECT run_key, seq, event_type, status, event_at_utc, reason_code, detail_json
                      FROM ofs_run_events
                     WHERE run_key = {p1}
                     ORDER BY seq ASC
                    """,
                    (str(run_key),),
                )
            ).fetchall()
        events: list[OfsRunEvent] = []
        for row in rows:
            detail = _json_load(str(row[6] or "{}"))
            events.append(
                OfsRunEvent(
                    run_key=str(row[0]),
                    seq=int(row[1]),
                    event_type=str(row[2]),
                    status=str(row[3]),
                    event_at_utc=str(row[4]),
                    reason_code=str(row[5]) if row[5] not in (None, "") else None,
                    detail=detail if isinstance(detail, Mapping) else {},
                )
            )
        return events

    def _connect(self) -> Any:
        if self.backend == "postgres":
            return postgres_threadlocal_connection(self.locator)
        return sqlite3.connect(_sqlite_path(self.locator))

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                _sql(
                    """
                    CREATE TABLE IF NOT EXISTS ofs_run_ledger (
                        run_key TEXT PRIMARY KEY,
                        request_id TEXT NOT NULL UNIQUE,
                        request_payload_hash TEXT NOT NULL,
                        intent_kind TEXT NOT NULL,
                        status TEXT NOT NULL,
                        execution_mode TEXT NOT NULL,
                        full_run_attempts INTEGER NOT NULL DEFAULT 0,
                        publish_retry_attempts INTEGER NOT NULL DEFAULT 0,
                        last_error_code TEXT,
                        result_ref TEXT,
                        input_summary_json TEXT NOT NULL,
                        provenance_json TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        last_transition_at_utc TEXT NOT NULL,
                        last_started_at_utc TEXT,
                        last_completed_at_utc TEXT
                    )
                    """,
                    self.backend,
                )
            )
            conn.execute(
                _sql(
                    """
                    CREATE TABLE IF NOT EXISTS ofs_run_events (
                        run_key TEXT NOT NULL,
                        seq INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        event_at_utc TEXT NOT NULL,
                        reason_code TEXT,
                        detail_json TEXT NOT NULL,
                        PRIMARY KEY (run_key, seq)
                    )
                    """,
                    self.backend,
                )
            )

    def _require_row(self, *, conn: Any, run_key: str) -> dict[str, Any]:
        row = conn.execute(
            *self._sql_with_params(
                """
                SELECT run_key, request_id, intent_kind, status, execution_mode,
                       full_run_attempts, publish_retry_attempts, last_error_code, result_ref,
                       input_summary_json, provenance_json, created_at_utc, updated_at_utc,
                       last_transition_at_utc, last_started_at_utc, last_completed_at_utc
                  FROM ofs_run_ledger
                 WHERE run_key = {p1}
                """,
                (str(run_key),),
            )
        ).fetchone()
        if row is None:
            raise OfsRunLedgerError("RUN_NOT_FOUND", f"unknown run_key: {run_key}")
        return {
            "run_key": str(row[0]),
            "request_id": str(row[1]),
            "intent_kind": str(row[2]),
            "status": str(row[3]),
            "execution_mode": str(row[4]),
            "full_run_attempts": int(row[5]),
            "publish_retry_attempts": int(row[6]),
            "last_error_code": str(row[7]) if row[7] not in (None, "") else None,
            "result_ref": str(row[8]) if row[8] not in (None, "") else None,
            "input_summary_json": str(row[9]),
            "provenance_json": str(row[10]),
            "created_at_utc": str(row[11]),
            "updated_at_utc": str(row[12]),
            "last_transition_at_utc": str(row[13]),
            "last_started_at_utc": str(row[14]) if row[14] not in (None, "") else None,
            "last_completed_at_utc": str(row[15]) if row[15] not in (None, "") else None,
        }

    def _receipt_tx(self, *, conn: Any, run_key: str) -> OfsRunReceipt:
        row = self._require_row(conn=conn, run_key=run_key)
        input_summary = _json_load(row["input_summary_json"])
        provenance = _json_load(row["provenance_json"])
        return OfsRunReceipt(
            run_key=row["run_key"],
            request_id=row["request_id"],
            intent_kind=row["intent_kind"],
            status=row["status"],
            execution_mode=row["execution_mode"],
            full_run_attempts=row["full_run_attempts"],
            publish_retry_attempts=row["publish_retry_attempts"],
            last_error_code=row["last_error_code"],
            result_ref=row["result_ref"],
            input_summary=input_summary if isinstance(input_summary, Mapping) else {},
            provenance=provenance if isinstance(provenance, Mapping) else {},
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
            last_transition_at_utc=row["last_transition_at_utc"],
            last_started_at_utc=row["last_started_at_utc"],
            last_completed_at_utc=row["last_completed_at_utc"],
        )

    def _append_event_tx(
        self,
        *,
        conn: Any,
        run_key: str,
        event_type: str,
        status: str,
        event_at_utc: str,
        reason_code: str | None,
        detail: Mapping[str, Any],
    ) -> None:
        next_seq_row = conn.execute(
            *self._sql_with_params(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM ofs_run_events WHERE run_key = {p1}",
                (str(run_key),),
            )
        ).fetchone()
        next_seq = int(next_seq_row[0]) if next_seq_row is not None else 1
        conn.execute(
            *self._sql_with_params(
                """
                INSERT INTO ofs_run_events (
                    run_key, seq, event_type, status, event_at_utc, reason_code, detail_json
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7})
                """,
                (
                    str(run_key),
                    int(next_seq),
                    str(event_type),
                    str(status),
                    str(event_at_utc),
                    _none_if_blank(reason_code),
                    _json_dump(detail),
                ),
            )
        )

    def _sql_with_params(self, sql: str, params: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]]:
        rendered = _sql(sql, self.backend)
        ordered = _ordered_params(sql, params)
        return rendered, ordered


def deterministic_run_key(request_id: str) -> str:
    normalized = str(request_id or "").strip()
    if not normalized:
        raise ValueError("request_id is required")
    payload = {"recipe": "ofs.run_key.v1", "request_id": normalized}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:32]


def canonical_intent_payload_hash(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    canonical = json.dumps(_normalize_generic(dict(payload)), sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    encoded = json.dumps({"recipe": "ofs.intent_payload.v1", "payload": canonical}, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _input_summary(intent: OfsBuildIntent) -> dict[str, Any]:
    feature = intent.feature_definition_set
    label = intent.label_basis
    return {
        "request_id": intent.request_id,
        "intent_kind": intent.intent_kind,
        "platform_run_id": intent.platform_run_id,
        "scenario_run_count": len(intent.scenario_run_ids),
        "replay_slice_count": len(intent.replay_basis),
        "label_asof_utc": label.label_asof_utc,
        "label_resolution_rule": label.resolution_rule,
        "feature_set_id": feature.feature_set_id,
        "feature_set_version": feature.feature_set_version,
        "policy_revision": intent.policy_revision,
        "config_revision": intent.config_revision,
    }


def _provenance_summary(intent: OfsBuildIntent) -> dict[str, Any]:
    return {
        "ofs_code_release_id": intent.ofs_code_release_id,
        "policy_revision": intent.policy_revision,
        "config_revision": intent.config_revision,
        "run_facts_ref": intent.run_facts_ref,
        "non_training_allowed": bool(intent.non_training_allowed),
        "parity_anchor_ref": intent.parity_anchor_ref,
    }


_PLACEHOLDER_PATTERN = re.compile(r"\{p(\d+)\}")


def _sql(sql: str, backend: str) -> str:
    if backend == "sqlite":
        return _PLACEHOLDER_PATTERN.sub("?", sql)
    if backend == "postgres":
        return _PLACEHOLDER_PATTERN.sub("%s", sql)
    raise ValueError(f"unsupported backend: {backend}")


def _ordered_params(sql: str, params: tuple[Any, ...]) -> tuple[Any, ...]:
    ordered: list[Any] = []
    for token in _PLACEHOLDER_PATTERN.findall(sql):
        idx = int(token) - 1
        if idx < 0 or idx >= len(params):
            raise ValueError(f"placeholder index out of range: p{token}")
        ordered.append(params[idx])
    return tuple(ordered)


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _sqlite_path(locator: str) -> str:
    text = str(locator or "").strip()
    if text.startswith("sqlite:///"):
        return text[len("sqlite:///") :]
    if text.startswith("sqlite://"):
        return text[len("sqlite://") :]
    return text


def _json_dump(value: Any) -> str:
    return json.dumps(_normalize_generic(value), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _json_load(value: str) -> Any:
    text = str(value or "").strip()
    if not text:
        return {}
    return json.loads(text)


def _normalize_generic(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_generic(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_normalize_generic(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
