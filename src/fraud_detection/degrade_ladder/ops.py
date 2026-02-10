"""DL governance and ops telemetry store (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

import psycopg
from fraud_detection.postgres_runtime import postgres_threadlocal_connection

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .contracts import DegradeDecision, PolicyRev
from .signals import DlSignalSnapshot


class DlOpsError(RuntimeError):
    """Raised when governance/ops telemetry operations fail."""


@dataclass(frozen=True)
class DlGovernanceEvent:
    event_id: str
    event_type: str
    scope_key: str
    ts_utc: str
    policy_id: str | None
    policy_revision: str | None
    policy_content_digest: str | None
    payload: dict[str, Any]


def build_ops_store(dsn: str, *, stream_id: str) -> "DlOpsStore":
    if is_postgres_dsn(dsn):
        return PostgresDlOpsStore(dsn=dsn, stream_id=stream_id)
    return SqliteDlOpsStore(path=Path(_sqlite_path(dsn)), stream_id=stream_id)


class DlOpsStore:
    def record_policy_activation(
        self,
        *,
        scope_key: str,
        policy_rev: PolicyRev,
        actor: str,
        reason: str,
        ts_utc: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    def record_posture_transition(
        self,
        *,
        scope_key: str,
        decision: DegradeDecision,
        previous_mode: str | None,
        source: str,
        forced_fail_closed: bool = False,
        reason_codes: tuple[str, ...] = (),
        ts_utc: str | None = None,
    ) -> str:
        raise NotImplementedError

    def record_evaluator_error(
        self,
        *,
        scope_key: str,
        error_code: str,
        ts_utc: str | None = None,
    ) -> None:
        raise NotImplementedError

    def record_signal_snapshot(
        self,
        *,
        scope_key: str,
        snapshot: DlSignalSnapshot,
        ts_utc: str | None = None,
    ) -> None:
        raise NotImplementedError

    def record_serve_result(
        self,
        *,
        scope_key: str,
        source: str,
        ts_utc: str | None = None,
    ) -> None:
        raise NotImplementedError

    def query_governance_events(
        self,
        *,
        event_type: str | None = None,
        scope_key: str | None = None,
        limit: int = 100,
    ) -> list[DlGovernanceEvent]:
        raise NotImplementedError

    def metrics_snapshot(self, *, scope_key: str | None = None) -> dict[str, int]:
        raise NotImplementedError


@dataclass
class SqliteDlOpsStore(DlOpsStore):
    path: Path
    stream_id: str

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS dl_governance_events (
                    stream_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    ts_utc TEXT NOT NULL,
                    policy_id TEXT,
                    policy_revision TEXT,
                    policy_content_digest TEXT,
                    payload_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS idx_dl_gov_events_type_ts
                    ON dl_governance_events(stream_id, event_type, ts_utc DESC);
                CREATE INDEX IF NOT EXISTS idx_dl_gov_events_scope_ts
                    ON dl_governance_events(stream_id, scope_key, ts_utc DESC);

                CREATE TABLE IF NOT EXISTS dl_ops_metrics (
                    stream_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value INTEGER NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scope_key, metric_name)
                );
                """
            )

    def record_policy_activation(
        self,
        *,
        scope_key: str,
        policy_rev: PolicyRev,
        actor: str,
        reason: str,
        ts_utc: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        ts = _timestamp(ts_utc)
        payload = {
            "actor": str(actor),
            "reason": str(reason),
            "metadata": _sanitize_payload(metadata or {}),
        }
        event = _build_event(
            event_type="dl.policy_activated.v1",
            scope_key=scope_key,
            ts_utc=ts,
            policy_rev=policy_rev,
            payload=payload,
        )
        self._insert_event(event)
        return event.event_id

    def record_posture_transition(
        self,
        *,
        scope_key: str,
        decision: DegradeDecision,
        previous_mode: str | None,
        source: str,
        forced_fail_closed: bool = False,
        reason_codes: tuple[str, ...] = (),
        ts_utc: str | None = None,
    ) -> str:
        ts = _timestamp(ts_utc)
        transition_payload = {
            "previous_mode": None if previous_mode in (None, "") else str(previous_mode),
            "new_mode": decision.mode,
            "source": str(source),
            "reason_codes": [str(code) for code in reason_codes],
            "posture_seq": decision.posture_seq,
            "decided_at_utc": decision.decided_at_utc,
            "evidence_refs": list(decision.evidence_refs),
        }
        event = _build_event(
            event_type="dl.posture_transition.v1",
            scope_key=scope_key,
            ts_utc=ts,
            policy_rev=decision.policy_rev,
            payload=transition_payload,
        )
        self._insert_event(event)
        self._increment_metric(scope_key=scope_key, metric_name="posture_transitions_total", delta=1, ts_utc=ts)

        is_forced = forced_fail_closed or (decision.mode == "FAIL_CLOSED" and "HEALTH_GATE" in str(source).upper())
        if is_forced:
            forced_event = _build_event(
                event_type="dl.fail_closed_forced.v1",
                scope_key=scope_key,
                ts_utc=ts,
                policy_rev=decision.policy_rev,
                payload={
                    "source": str(source),
                    "reason_codes": [str(code) for code in reason_codes],
                    "posture_seq": decision.posture_seq,
                },
            )
            self._insert_event(forced_event)
            self._increment_metric(scope_key=scope_key, metric_name="forced_fail_closed_total", delta=1, ts_utc=ts)
        return event.event_id

    def record_evaluator_error(
        self,
        *,
        scope_key: str,
        error_code: str,
        ts_utc: str | None = None,
    ) -> None:
        self._increment_metric(
            scope_key=scope_key,
            metric_name="evaluator_errors_total",
            delta=1,
            ts_utc=_timestamp(ts_utc),
        )
        _ = error_code

    def record_signal_snapshot(
        self,
        *,
        scope_key: str,
        snapshot: DlSignalSnapshot,
        ts_utc: str | None = None,
    ) -> None:
        ts = _timestamp(ts_utc)
        required_ok = 0
        required_bad = 0
        for state in snapshot.states:
            if not state.required:
                continue
            if state.state == "OK":
                required_ok += 1
            else:
                required_bad += 1
        if required_ok:
            self._increment_metric(
                scope_key=scope_key,
                metric_name="signal_required_ok_total",
                delta=required_ok,
                ts_utc=ts,
            )
        if required_bad:
            self._increment_metric(
                scope_key=scope_key,
                metric_name="signal_required_bad_total",
                delta=required_bad,
                ts_utc=ts,
            )

    def record_serve_result(
        self,
        *,
        scope_key: str,
        source: str,
        ts_utc: str | None = None,
    ) -> None:
        if str(source) != "CURRENT_POSTURE":
            self._increment_metric(
                scope_key=scope_key,
                metric_name="serve_fallback_total",
                delta=1,
                ts_utc=_timestamp(ts_utc),
            )

    def query_governance_events(
        self,
        *,
        event_type: str | None = None,
        scope_key: str | None = None,
        limit: int = 100,
    ) -> list[DlGovernanceEvent]:
        if limit <= 0:
            raise DlOpsError("limit must be >= 1")
        clauses = ["stream_id = ?"]
        params: list[Any] = [self.stream_id]
        if event_type:
            clauses.append("event_type = ?")
            params.append(str(event_type))
        if scope_key:
            clauses.append("scope_key = ?")
            params.append(_normalize_scope(scope_key))
        query = f"""
            SELECT event_id, event_type, scope_key, ts_utc,
                   policy_id, policy_revision, policy_content_digest, payload_json
            FROM dl_governance_events
            WHERE {' AND '.join(clauses)}
            ORDER BY ts_utc DESC
            LIMIT ?
        """
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        events: list[DlGovernanceEvent] = []
        for row in rows:
            payload = json.loads(str(row[7]))
            events.append(
                DlGovernanceEvent(
                    event_id=str(row[0]),
                    event_type=str(row[1]),
                    scope_key=str(row[2]),
                    ts_utc=str(row[3]),
                    policy_id=None if row[4] in (None, "") else str(row[4]),
                    policy_revision=None if row[5] in (None, "") else str(row[5]),
                    policy_content_digest=None if row[6] in (None, "") else str(row[6]),
                    payload=payload if isinstance(payload, dict) else {},
                )
            )
        return events

    def metrics_snapshot(self, *, scope_key: str | None = None) -> dict[str, int]:
        if scope_key:
            query = """
                SELECT metric_name, metric_value
                FROM dl_ops_metrics
                WHERE stream_id = ? AND scope_key = ?
            """
            params = (self.stream_id, _normalize_scope(scope_key))
        else:
            query = """
                SELECT metric_name, SUM(metric_value)
                FROM dl_ops_metrics
                WHERE stream_id = ?
                GROUP BY metric_name
            """
            params = (self.stream_id,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def _insert_event(self, event: DlGovernanceEvent) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO dl_governance_events (
                    stream_id, event_id, event_type, scope_key, ts_utc,
                    policy_id, policy_revision, policy_content_digest, payload_json, created_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.stream_id,
                    event.event_id,
                    event.event_type,
                    event.scope_key,
                    event.ts_utc,
                    event.policy_id,
                    event.policy_revision,
                    event.policy_content_digest,
                    _canonical_json(event.payload),
                    now,
                ),
            )

    def _increment_metric(self, *, scope_key: str, metric_name: str, delta: int, ts_utc: str) -> None:
        normalized_scope = _normalize_scope(scope_key)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dl_ops_metrics (stream_id, scope_key, metric_name, metric_value, updated_at_utc)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(stream_id, scope_key, metric_name) DO UPDATE SET
                    metric_value = metric_value + excluded.metric_value,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (self.stream_id, normalized_scope, str(metric_name), int(delta), ts_utc),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path))


@dataclass
class PostgresDlOpsStore(DlOpsStore):
    dsn: str
    stream_id: str

    def __post_init__(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dl_governance_events (
                    stream_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    ts_utc TEXT NOT NULL,
                    policy_id TEXT,
                    policy_revision TEXT,
                    policy_content_digest TEXT,
                    payload_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, event_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_dl_gov_events_type_ts
                ON dl_governance_events(stream_id, event_type, ts_utc DESC)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_dl_gov_events_scope_ts
                ON dl_governance_events(stream_id, scope_key, ts_utc DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dl_ops_metrics (
                    stream_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value BIGINT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, scope_key, metric_name)
                )
                """
            )

    def record_policy_activation(
        self,
        *,
        scope_key: str,
        policy_rev: PolicyRev,
        actor: str,
        reason: str,
        ts_utc: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        ts = _timestamp(ts_utc)
        payload = {
            "actor": str(actor),
            "reason": str(reason),
            "metadata": _sanitize_payload(metadata or {}),
        }
        event = _build_event(
            event_type="dl.policy_activated.v1",
            scope_key=scope_key,
            ts_utc=ts,
            policy_rev=policy_rev,
            payload=payload,
        )
        self._insert_event(event)
        return event.event_id

    def record_posture_transition(
        self,
        *,
        scope_key: str,
        decision: DegradeDecision,
        previous_mode: str | None,
        source: str,
        forced_fail_closed: bool = False,
        reason_codes: tuple[str, ...] = (),
        ts_utc: str | None = None,
    ) -> str:
        ts = _timestamp(ts_utc)
        transition_payload = {
            "previous_mode": None if previous_mode in (None, "") else str(previous_mode),
            "new_mode": decision.mode,
            "source": str(source),
            "reason_codes": [str(code) for code in reason_codes],
            "posture_seq": decision.posture_seq,
            "decided_at_utc": decision.decided_at_utc,
            "evidence_refs": list(decision.evidence_refs),
        }
        event = _build_event(
            event_type="dl.posture_transition.v1",
            scope_key=scope_key,
            ts_utc=ts,
            policy_rev=decision.policy_rev,
            payload=transition_payload,
        )
        self._insert_event(event)
        self._increment_metric(scope_key=scope_key, metric_name="posture_transitions_total", delta=1, ts_utc=ts)

        is_forced = forced_fail_closed or (decision.mode == "FAIL_CLOSED" and "HEALTH_GATE" in str(source).upper())
        if is_forced:
            forced_event = _build_event(
                event_type="dl.fail_closed_forced.v1",
                scope_key=scope_key,
                ts_utc=ts,
                policy_rev=decision.policy_rev,
                payload={
                    "source": str(source),
                    "reason_codes": [str(code) for code in reason_codes],
                    "posture_seq": decision.posture_seq,
                },
            )
            self._insert_event(forced_event)
            self._increment_metric(scope_key=scope_key, metric_name="forced_fail_closed_total", delta=1, ts_utc=ts)
        return event.event_id

    def record_evaluator_error(
        self,
        *,
        scope_key: str,
        error_code: str,
        ts_utc: str | None = None,
    ) -> None:
        self._increment_metric(
            scope_key=scope_key,
            metric_name="evaluator_errors_total",
            delta=1,
            ts_utc=_timestamp(ts_utc),
        )
        _ = error_code

    def record_signal_snapshot(
        self,
        *,
        scope_key: str,
        snapshot: DlSignalSnapshot,
        ts_utc: str | None = None,
    ) -> None:
        ts = _timestamp(ts_utc)
        required_ok = 0
        required_bad = 0
        for state in snapshot.states:
            if not state.required:
                continue
            if state.state == "OK":
                required_ok += 1
            else:
                required_bad += 1
        if required_ok:
            self._increment_metric(
                scope_key=scope_key,
                metric_name="signal_required_ok_total",
                delta=required_ok,
                ts_utc=ts,
            )
        if required_bad:
            self._increment_metric(
                scope_key=scope_key,
                metric_name="signal_required_bad_total",
                delta=required_bad,
                ts_utc=ts,
            )

    def record_serve_result(
        self,
        *,
        scope_key: str,
        source: str,
        ts_utc: str | None = None,
    ) -> None:
        if str(source) != "CURRENT_POSTURE":
            self._increment_metric(
                scope_key=scope_key,
                metric_name="serve_fallback_total",
                delta=1,
                ts_utc=_timestamp(ts_utc),
            )

    def query_governance_events(
        self,
        *,
        event_type: str | None = None,
        scope_key: str | None = None,
        limit: int = 100,
    ) -> list[DlGovernanceEvent]:
        if limit <= 0:
            raise DlOpsError("limit must be >= 1")
        clauses = ["stream_id = %s"]
        params: list[Any] = [self.stream_id]
        if event_type:
            clauses.append("event_type = %s")
            params.append(str(event_type))
        if scope_key:
            clauses.append("scope_key = %s")
            params.append(_normalize_scope(scope_key))
        query = f"""
            SELECT event_id, event_type, scope_key, ts_utc,
                   policy_id, policy_revision, policy_content_digest, payload_json
            FROM dl_governance_events
            WHERE {' AND '.join(clauses)}
            ORDER BY ts_utc DESC
            LIMIT %s
        """
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        events: list[DlGovernanceEvent] = []
        for row in rows:
            payload = json.loads(str(row[7]))
            events.append(
                DlGovernanceEvent(
                    event_id=str(row[0]),
                    event_type=str(row[1]),
                    scope_key=str(row[2]),
                    ts_utc=str(row[3]),
                    policy_id=None if row[4] in (None, "") else str(row[4]),
                    policy_revision=None if row[5] in (None, "") else str(row[5]),
                    policy_content_digest=None if row[6] in (None, "") else str(row[6]),
                    payload=payload if isinstance(payload, dict) else {},
                )
            )
        return events

    def metrics_snapshot(self, *, scope_key: str | None = None) -> dict[str, int]:
        if scope_key:
            query = """
                SELECT metric_name, metric_value
                FROM dl_ops_metrics
                WHERE stream_id = %s AND scope_key = %s
            """
            params = (self.stream_id, _normalize_scope(scope_key))
        else:
            query = """
                SELECT metric_name, SUM(metric_value)
                FROM dl_ops_metrics
                WHERE stream_id = %s
                GROUP BY metric_name
            """
            params = (self.stream_id,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def _insert_event(self, event: DlGovernanceEvent) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dl_governance_events (
                    stream_id, event_id, event_type, scope_key, ts_utc,
                    policy_id, policy_revision, policy_content_digest, payload_json, created_at_utc
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (stream_id, event_id) DO NOTHING
                """,
                (
                    self.stream_id,
                    event.event_id,
                    event.event_type,
                    event.scope_key,
                    event.ts_utc,
                    event.policy_id,
                    event.policy_revision,
                    event.policy_content_digest,
                    _canonical_json(event.payload),
                    now,
                ),
            )

    def _increment_metric(self, *, scope_key: str, metric_name: str, delta: int, ts_utc: str) -> None:
        normalized_scope = _normalize_scope(scope_key)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dl_ops_metrics (stream_id, scope_key, metric_name, metric_value, updated_at_utc)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(stream_id, scope_key, metric_name) DO UPDATE SET
                    metric_value = dl_ops_metrics.metric_value + excluded.metric_value,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (self.stream_id, normalized_scope, str(metric_name), int(delta), ts_utc),
            )

    def _connect(self) -> psycopg.Connection:
        return postgres_threadlocal_connection(self.dsn)


def _build_event(
    *,
    event_type: str,
    scope_key: str,
    ts_utc: str,
    policy_rev: PolicyRev | None,
    payload: dict[str, Any],
) -> DlGovernanceEvent:
    normalized_scope = _normalize_scope(scope_key)
    sanitized_payload = _sanitize_payload(payload)
    event_id = _event_id(
        event_type=event_type,
        scope_key=normalized_scope,
        ts_utc=ts_utc,
        policy_rev=policy_rev,
        payload=sanitized_payload,
    )
    return DlGovernanceEvent(
        event_id=event_id,
        event_type=str(event_type),
        scope_key=normalized_scope,
        ts_utc=ts_utc,
        policy_id=None if policy_rev is None else policy_rev.policy_id,
        policy_revision=None if policy_rev is None else policy_rev.revision,
        policy_content_digest=None if policy_rev is None else policy_rev.content_digest,
        payload=sanitized_payload,
    )


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, raw in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                sanitized[key_text] = "[REDACTED]"
            else:
                sanitized[key_text] = _sanitize_payload(raw)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    token = key.strip().lower()
    sensitive_markers = (
        "token",
        "secret",
        "password",
        "credential",
        "lease_token",
        "api_key",
        "access_key",
        "private_key",
    )
    return any(marker in token for marker in sensitive_markers)


def _event_id(
    *,
    event_type: str,
    scope_key: str,
    ts_utc: str,
    policy_rev: PolicyRev | None,
    payload: dict[str, Any],
) -> str:
    source = {
        "event_type": event_type,
        "scope_key": scope_key,
        "ts_utc": ts_utc,
        "policy_rev": None if policy_rev is None else policy_rev.as_dict(),
        "payload": payload,
    }
    digest = hashlib.sha256(_canonical_json(source).encode("utf-8")).hexdigest()
    return digest


def _normalize_scope(scope_key: str) -> str:
    normalized = str(scope_key).strip()
    if not normalized:
        raise DlOpsError("scope_key must be non-empty")
    return normalized


def _timestamp(ts_utc: str | None) -> str:
    return _utc_now() if ts_utc in (None, "") else _parse_utc(str(ts_utc), field_name="ts_utc").isoformat()


def _parse_utc(value: str, *, field_name: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise DlOpsError(f"{field_name} must be non-empty")
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DlOpsError(f"{field_name} must be RFC3339-ish UTC timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise DlOpsError(f"{field_name} must include timezone information")
    return dt.astimezone(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _sqlite_path(dsn: str) -> str:
    value = str(dsn or "").strip()
    if not value:
        raise DlOpsError("sqlite store path/DSN must be non-empty")
    if value.startswith("sqlite:///"):
        return value[len("sqlite:///") :]
    if value.startswith("sqlite://"):
        return value[len("sqlite://") :]
    return value


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

