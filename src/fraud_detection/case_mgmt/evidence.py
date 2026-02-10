"""Case Management evidence-by-ref resolution corridor (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

import psycopg
import yaml

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn


EVIDENCE_PENDING = "PENDING"
EVIDENCE_RESOLVED = "RESOLVED"
EVIDENCE_UNAVAILABLE = "UNAVAILABLE"
EVIDENCE_QUARANTINED = "QUARANTINED"
EVIDENCE_FORBIDDEN = "FORBIDDEN"

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        EVIDENCE_RESOLVED,
        EVIDENCE_UNAVAILABLE,
        EVIDENCE_QUARANTINED,
        EVIDENCE_FORBIDDEN,
    }
)

REQUEST_NEW = "NEW"
REQUEST_DUPLICATE = "DUPLICATE"
REQUEST_FORBIDDEN = "FORBIDDEN"

RESOLUTION_ALLOWED_STATUSES: frozenset[str] = frozenset(
    {
        EVIDENCE_RESOLVED,
        EVIDENCE_UNAVAILABLE,
        EVIDENCE_QUARANTINED,
    }
)

SOURCE_TYPE_SYSTEM = "SYSTEM"
SOURCE_TYPE_HUMAN = "HUMAN"
SOURCE_TYPE_EXTERNAL = "EXTERNAL"
SOURCE_TYPE_AUTO = "AUTO"
SOURCE_TYPE_VALUES: frozenset[str] = frozenset(
    {
        SOURCE_TYPE_SYSTEM,
        SOURCE_TYPE_HUMAN,
        SOURCE_TYPE_EXTERNAL,
        SOURCE_TYPE_AUTO,
    }
)


class CaseEvidenceResolutionError(RuntimeError):
    """Raised when CM evidence-resolution corridor operations fail."""


@dataclass(frozen=True)
class EvidenceResolutionPolicy:
    version: str
    policy_id: str
    revision: str
    allowed_ref_types: tuple[str, ...]
    allowed_actor_prefixes: tuple[str, ...]
    allowed_source_types: tuple[str, ...]
    content_digest: str


@dataclass(frozen=True)
class EvidenceResolutionSnapshot:
    request_id: str
    case_id: str
    case_timeline_event_id: str
    ref_type: str
    ref_id: str
    requested_by: str
    requested_source_type: str
    created_at_utc: str
    updated_at_utc: str
    status: str
    reason_code: str | None
    status_observed_at_utc: str
    status_actor_id: str
    status_source_type: str
    locator_ref: str | None


@dataclass(frozen=True)
class EvidenceResolutionRequestResult:
    disposition: str
    snapshot: EvidenceResolutionSnapshot


class CaseEvidenceResolutionCorridor:
    """Policy-gated, append-only evidence resolution status ledger."""

    def __init__(
        self,
        *,
        locator: str,
        policy: EvidenceResolutionPolicy,
    ) -> None:
        self.locator = str(locator)
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(self.locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self.policy = policy
        self._init_schema()

    def request_resolution(
        self,
        *,
        case_id: str,
        case_timeline_event_id: str,
        ref_type: str,
        ref_id: str,
        actor_id: str,
        source_type: str,
        requested_at_utc: str,
        locator_ref: str | None = None,
    ) -> EvidenceResolutionRequestResult:
        normalized_case_id = _require_non_empty(case_id, "case_id")
        normalized_event_id = _require_non_empty(case_timeline_event_id, "case_timeline_event_id")
        normalized_ref_type = _normalize_ref_type(ref_type)
        normalized_ref_id = _require_non_empty(ref_id, "ref_id")
        normalized_actor = _require_non_empty(actor_id, "actor_id")
        normalized_source = _normalize_source_type(source_type)
        normalized_requested_at = _require_non_empty(requested_at_utc, "requested_at_utc")
        normalized_locator = _normalize_optional(locator_ref)

        request_id = _request_id(
            case_id=normalized_case_id,
            case_timeline_event_id=normalized_event_id,
            ref_type=normalized_ref_type,
            ref_id=normalized_ref_id,
        )

        gate_reason = self._gate_reason(
            ref_type=normalized_ref_type,
            actor_id=normalized_actor,
            source_type=normalized_source,
        )

        with self._connect() as conn:
            if self.backend == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                return self._request_tx(
                    conn=conn,
                    request_id=request_id,
                    case_id=normalized_case_id,
                    case_timeline_event_id=normalized_event_id,
                    ref_type=normalized_ref_type,
                    ref_id=normalized_ref_id,
                    actor_id=normalized_actor,
                    source_type=normalized_source,
                    requested_at_utc=normalized_requested_at,
                    locator_ref=normalized_locator,
                    gate_reason=gate_reason,
                )
            with conn.transaction():
                return self._request_tx(
                    conn=conn,
                    request_id=request_id,
                    case_id=normalized_case_id,
                    case_timeline_event_id=normalized_event_id,
                    ref_type=normalized_ref_type,
                    ref_id=normalized_ref_id,
                    actor_id=normalized_actor,
                    source_type=normalized_source,
                    requested_at_utc=normalized_requested_at,
                    locator_ref=normalized_locator,
                    gate_reason=gate_reason,
                )

    def record_resolution(
        self,
        *,
        request_id: str,
        status: str,
        reason_code: str,
        actor_id: str,
        source_type: str,
        observed_at_utc: str,
        locator_ref: str | None = None,
    ) -> EvidenceResolutionSnapshot:
        normalized_request_id = _require_non_empty(request_id, "request_id")
        normalized_status = _normalize_status(status)
        normalized_reason = _require_non_empty(reason_code, "reason_code")
        normalized_actor = _require_non_empty(actor_id, "actor_id")
        normalized_source = _normalize_source_type(source_type)
        normalized_observed = _require_non_empty(observed_at_utc, "observed_at_utc")
        normalized_locator = _normalize_optional(locator_ref)

        if normalized_status not in RESOLUTION_ALLOWED_STATUSES:
            allowed = ",".join(sorted(RESOLUTION_ALLOWED_STATUSES))
            raise CaseEvidenceResolutionError(
                f"unsupported resolution status: {normalized_status!r}; allowed={allowed}"
            )

        with self._connect() as conn:
            if self.backend == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                return self._resolve_tx(
                    conn=conn,
                    request_id=normalized_request_id,
                    status=normalized_status,
                    reason_code=normalized_reason,
                    actor_id=normalized_actor,
                    source_type=normalized_source,
                    observed_at_utc=normalized_observed,
                    locator_ref=normalized_locator,
                )
            with conn.transaction():
                return self._resolve_tx(
                    conn=conn,
                    request_id=normalized_request_id,
                    status=normalized_status,
                    reason_code=normalized_reason,
                    actor_id=normalized_actor,
                    source_type=normalized_source,
                    observed_at_utc=normalized_observed,
                    locator_ref=normalized_locator,
                )

    def snapshot(self, *, request_id: str) -> EvidenceResolutionSnapshot | None:
        normalized_request_id = _require_non_empty(request_id, "request_id")
        with self._connect() as conn:
            return _snapshot_by_request_id(conn=conn, backend=self.backend, request_id=normalized_request_id)

    def list_case_snapshots(self, *, case_id: str) -> tuple[EvidenceResolutionSnapshot, ...]:
        normalized_case_id = _require_non_empty(case_id, "case_id")
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT request_id
                FROM cm_evidence_resolution_requests
                WHERE case_id = {p1}
                ORDER BY created_at_utc ASC, request_id ASC
                """,
                (normalized_case_id,),
            )
            snapshots: list[EvidenceResolutionSnapshot] = []
            for row in rows:
                snapshot = _snapshot_by_request_id(conn=conn, backend=self.backend, request_id=str(row[0]))
                if snapshot is not None:
                    snapshots.append(snapshot)
            return tuple(snapshots)

    def event_count(self, *, request_id: str) -> int:
        normalized_request_id = _require_non_empty(request_id, "request_id")
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                "SELECT COUNT(1) FROM cm_evidence_resolution_events WHERE request_id = {p1}",
                (normalized_request_id,),
            )
        return int(row[0] or 0) if row is not None else 0

    def _request_tx(
        self,
        *,
        conn: Any,
        request_id: str,
        case_id: str,
        case_timeline_event_id: str,
        ref_type: str,
        ref_id: str,
        actor_id: str,
        source_type: str,
        requested_at_utc: str,
        locator_ref: str | None,
        gate_reason: str | None,
    ) -> EvidenceResolutionRequestResult:
        _execute(
            conn,
            self.backend,
            """
            INSERT INTO cm_evidence_resolution_requests (
                request_id, case_id, case_timeline_event_id, ref_type, ref_id,
                requested_by, requested_source_type, locator_ref, created_at_utc, updated_at_utc
            ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10})
            ON CONFLICT (request_id) DO NOTHING
            """,
            (
                request_id,
                case_id,
                case_timeline_event_id,
                ref_type,
                ref_id,
                actor_id,
                source_type,
                locator_ref,
                requested_at_utc,
                requested_at_utc,
            ),
        )

        current = _snapshot_by_request_id(conn=conn, backend=self.backend, request_id=request_id)
        if current is None:
            raise CaseEvidenceResolutionError(f"failed to create evidence resolution request: {request_id}")

        if current.status in TERMINAL_STATUSES:
            return EvidenceResolutionRequestResult(disposition=REQUEST_DUPLICATE, snapshot=current)

        if current.status == EVIDENCE_PENDING and self._event_count_tx(conn=conn, request_id=request_id) > 0:
            return EvidenceResolutionRequestResult(disposition=REQUEST_DUPLICATE, snapshot=current)

        if gate_reason is not None:
            self._append_event(
                conn=conn,
                request_id=request_id,
                status=EVIDENCE_FORBIDDEN,
                reason_code=gate_reason,
                actor_id=actor_id,
                source_type=source_type,
                observed_at_utc=requested_at_utc,
                locator_ref=locator_ref,
            )
            snapshot = _snapshot_by_request_id(conn=conn, backend=self.backend, request_id=request_id)
            if snapshot is None:
                raise CaseEvidenceResolutionError("failed to read forbidden evidence resolution snapshot")
            return EvidenceResolutionRequestResult(disposition=REQUEST_FORBIDDEN, snapshot=snapshot)

        if self._event_count_tx(conn=conn, request_id=request_id) == 0:
            self._append_event(
                conn=conn,
                request_id=request_id,
                status=EVIDENCE_PENDING,
                reason_code="REQUEST_ACCEPTED",
                actor_id=actor_id,
                source_type=source_type,
                observed_at_utc=requested_at_utc,
                locator_ref=locator_ref,
            )
            snapshot = _snapshot_by_request_id(conn=conn, backend=self.backend, request_id=request_id)
            if snapshot is None:
                raise CaseEvidenceResolutionError("failed to read pending evidence resolution snapshot")
            return EvidenceResolutionRequestResult(disposition=REQUEST_NEW, snapshot=snapshot)

        return EvidenceResolutionRequestResult(disposition=REQUEST_DUPLICATE, snapshot=current)

    def _event_count_tx(self, *, conn: Any, request_id: str) -> int:
        row = _query_one(
            conn,
            self.backend,
            "SELECT COUNT(1) FROM cm_evidence_resolution_events WHERE request_id = {p1}",
            (request_id,),
        )
        return int(row[0] or 0) if row is not None else 0

    def _resolve_tx(
        self,
        *,
        conn: Any,
        request_id: str,
        status: str,
        reason_code: str,
        actor_id: str,
        source_type: str,
        observed_at_utc: str,
        locator_ref: str | None,
    ) -> EvidenceResolutionSnapshot:
        existing = _query_one(
            conn,
            self.backend,
            "SELECT request_id FROM cm_evidence_resolution_requests WHERE request_id = {p1}",
            (request_id,),
        )
        if existing is None:
            raise CaseEvidenceResolutionError(f"unknown evidence resolution request: {request_id}")

        current = _snapshot_by_request_id(conn=conn, backend=self.backend, request_id=request_id)
        if current is None:
            raise CaseEvidenceResolutionError(f"missing snapshot for evidence resolution request: {request_id}")

        if current.status in TERMINAL_STATUSES:
            return current

        self._append_event(
            conn=conn,
            request_id=request_id,
            status=status,
            reason_code=reason_code,
            actor_id=actor_id,
            source_type=source_type,
            observed_at_utc=observed_at_utc,
            locator_ref=locator_ref,
        )
        snapshot = _snapshot_by_request_id(conn=conn, backend=self.backend, request_id=request_id)
        if snapshot is None:
            raise CaseEvidenceResolutionError(f"failed to resolve evidence resolution request: {request_id}")
        return snapshot

    def _append_event(
        self,
        *,
        conn: Any,
        request_id: str,
        status: str,
        reason_code: str,
        actor_id: str,
        source_type: str,
        observed_at_utc: str,
        locator_ref: str | None,
    ) -> None:
        _execute(
            conn,
            self.backend,
            """
            INSERT INTO cm_evidence_resolution_events (
                request_id, status, reason_code, actor_id, source_type, observed_at_utc, locator_ref
            ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7})
            """,
            (request_id, status, reason_code, actor_id, source_type, observed_at_utc, locator_ref),
        )
        _execute(
            conn,
            self.backend,
            "UPDATE cm_evidence_resolution_requests SET updated_at_utc = {p1} WHERE request_id = {p2}",
            (observed_at_utc, request_id),
        )

    def _gate_reason(self, *, ref_type: str, actor_id: str, source_type: str) -> str | None:
        if ref_type not in set(self.policy.allowed_ref_types):
            return "UNSUPPORTED_REF_TYPE"
        if source_type not in set(self.policy.allowed_source_types):
            return "UNSUPPORTED_SOURCE_TYPE"
        if not any(actor_id.startswith(prefix) for prefix in self.policy.allowed_actor_prefixes):
            return "ACTOR_FORBIDDEN"
        return None

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS cm_evidence_resolution_requests (
                    request_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    case_timeline_event_id TEXT NOT NULL,
                    ref_type TEXT NOT NULL,
                    ref_id TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    requested_source_type TEXT NOT NULL,
                    locator_ref TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    UNIQUE(case_id, case_timeline_event_id, ref_type, ref_id)
                );
                CREATE TABLE IF NOT EXISTS cm_evidence_resolution_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    locator_ref TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_cm_evidence_resolution_events_request
                    ON cm_evidence_resolution_events (request_id, seq);
                CREATE INDEX IF NOT EXISTS ix_cm_evidence_resolution_requests_case
                    ON cm_evidence_resolution_requests (case_id, created_at_utc);
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def load_evidence_resolution_policy(path: Path) -> EvidenceResolutionPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CaseEvidenceResolutionError("evidence resolution policy must be a mapping")

    version = _require_non_empty(payload.get("version"), "version")
    policy_id = _require_non_empty(payload.get("policy_id"), "policy_id")
    revision = _require_non_empty(payload.get("revision"), "revision")

    corridor = payload.get("evidence_resolution")
    if not isinstance(corridor, dict):
        raise CaseEvidenceResolutionError("evidence_resolution section is required")

    allowed_ref_types = tuple(
        sorted(
            {
                _normalize_ref_type_value(item)
                for item in _require_list(corridor.get("allowed_ref_types"), "allowed_ref_types")
            }
        )
    )
    allowed_actor_prefixes = tuple(
        sorted(
            {
                _require_non_empty(item, "allowed_actor_prefixes.item")
                for item in _require_list(corridor.get("allowed_actor_prefixes"), "allowed_actor_prefixes")
            }
        )
    )
    allowed_source_types = tuple(
        sorted(
            {
                _normalize_source_type(item)
                for item in _require_list(corridor.get("allowed_source_types"), "allowed_source_types")
            }
        )
    )

    digest_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "allowed_ref_types": list(allowed_ref_types),
        "allowed_actor_prefixes": list(allowed_actor_prefixes),
        "allowed_source_types": list(allowed_source_types),
    }
    canonical = json.dumps(digest_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return EvidenceResolutionPolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        allowed_ref_types=allowed_ref_types,
        allowed_actor_prefixes=allowed_actor_prefixes,
        allowed_source_types=allowed_source_types,
        content_digest=content_digest,
    )


def _snapshot_by_request_id(
    *,
    conn: Any,
    backend: str,
    request_id: str,
) -> EvidenceResolutionSnapshot | None:
    row = _query_one(
        conn,
        backend,
        """
        SELECT r.request_id,
               r.case_id,
               r.case_timeline_event_id,
               r.ref_type,
               r.ref_id,
               r.requested_by,
               r.requested_source_type,
               r.created_at_utc,
               r.updated_at_utc,
               e.status,
               e.reason_code,
               e.observed_at_utc,
               e.actor_id,
               e.source_type,
               COALESCE(e.locator_ref, r.locator_ref) AS locator_ref
        FROM cm_evidence_resolution_requests r
        LEFT JOIN cm_evidence_resolution_events e
               ON e.request_id = r.request_id
              AND e.seq = (
                   SELECT MAX(seq)
                   FROM cm_evidence_resolution_events
                   WHERE request_id = r.request_id
              )
        WHERE r.request_id = {p1}
        """,
        (request_id,),
    )
    if row is None:
        return None
    status = str(row[9] or EVIDENCE_PENDING)
    reason_code = _normalize_optional(row[10])
    observed_at = str(row[11] or row[8] or "")
    actor = str(row[12] or row[5] or "")
    source = str(row[13] or row[6] or "")
    return EvidenceResolutionSnapshot(
        request_id=str(row[0]),
        case_id=str(row[1]),
        case_timeline_event_id=str(row[2]),
        ref_type=str(row[3]),
        ref_id=str(row[4]),
        requested_by=str(row[5]),
        requested_source_type=str(row[6]),
        created_at_utc=str(row[7]),
        updated_at_utc=str(row[8]),
        status=status,
        reason_code=reason_code,
        status_observed_at_utc=observed_at,
        status_actor_id=actor,
        status_source_type=source,
        locator_ref=_normalize_optional(row[14]),
    )


def _request_id(
    *,
    case_id: str,
    case_timeline_event_id: str,
    ref_type: str,
    ref_id: str,
) -> str:
    basis = f"{case_id}:{case_timeline_event_id}:{ref_type}:{ref_id}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def _normalize_ref_type(value: str) -> str:
    return _require_non_empty(value, "ref_type").upper()


def _normalize_ref_type_value(value: Any) -> str:
    normalized = _require_non_empty(value, "ref_type").upper()
    allowed = {
        "DLA_AUDIT_RECORD",
        "DECISION",
        "ACTION_OUTCOME",
        "EB_ORIGIN_OFFSET",
        "CASE_EVENT",
    }
    if normalized not in allowed:
        supported = ",".join(sorted(allowed))
        raise CaseEvidenceResolutionError(f"unsupported ref_type: {normalized!r}; allowed={supported}")
    return normalized


def _normalize_status(value: str) -> str:
    normalized = _require_non_empty(value, "status").upper()
    allowed = {EVIDENCE_PENDING, EVIDENCE_RESOLVED, EVIDENCE_UNAVAILABLE, EVIDENCE_QUARANTINED, EVIDENCE_FORBIDDEN}
    if normalized not in allowed:
        supported = ",".join(sorted(allowed))
        raise CaseEvidenceResolutionError(f"unsupported status: {normalized!r}; allowed={supported}")
    return normalized


def _normalize_source_type(value: str) -> str:
    normalized = _require_non_empty(value, "source_type").upper()
    if normalized not in SOURCE_TYPE_VALUES:
        supported = ",".join(sorted(SOURCE_TYPE_VALUES))
        raise CaseEvidenceResolutionError(f"unsupported source_type: {normalized!r}; allowed={supported}")
    return normalized


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise CaseEvidenceResolutionError(f"{field_name} must be a non-empty list")
    return value


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseEvidenceResolutionError(f"{field_name} is required")
    return text


def _normalize_optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


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
            raise CaseEvidenceResolutionError(
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


def _query_all(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    rendered, ordered_params = _render_sql_with_params(sql, backend, params)
    if backend == "sqlite":
        cur = conn.execute(rendered, ordered_params)
        return list(cur.fetchall())
    cur = conn.cursor()
    cur.execute(rendered, ordered_params)
    rows = list(cur.fetchall())
    cur.close()
    return rows


def _execute(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> None:
    rendered, ordered_params = _render_sql_with_params(sql, backend, params)
    if backend == "sqlite":
        conn.execute(rendered, ordered_params)
        return
    cur = conn.cursor()
    cur.execute(rendered, ordered_params)
    cur.close()


def _execute_script(conn: Any, backend: str, sql: str) -> None:
    if backend == "sqlite":
        conn.executescript(sql)
        return
    statements = [item.strip() for item in sql.split(";") if item.strip()]
    cur = conn.cursor()
    for statement in statements:
        cur.execute(statement)
    cur.close()
