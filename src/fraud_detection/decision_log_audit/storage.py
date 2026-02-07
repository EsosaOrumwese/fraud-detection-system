"""Decision Log & Audit storage substrate (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping
from urllib.parse import urlparse

import psycopg
import yaml

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.platform_runtime import resolve_run_scoped_path

from .contracts import AuditRecord


class DecisionLogAuditIndexStoreError(RuntimeError):
    """Raised when DLA storage/index operations fail."""


@dataclass(frozen=True)
class DecisionLogAuditRetentionWindow:
    audit_record_ttl_days: int
    index_ttl_days: int
    reconciliation_ttl_days: int


@dataclass(frozen=True)
class DecisionLogAuditStorageProfile:
    profile_id: str
    object_store_prefix: str
    retention: DecisionLogAuditRetentionWindow


@dataclass(frozen=True)
class DecisionLogAuditStoragePolicy:
    version: str
    policy_id: str
    revision: str
    profiles: dict[str, DecisionLogAuditStorageProfile]

    def profile(self, profile_id: str) -> DecisionLogAuditStorageProfile:
        key = str(profile_id or "").strip()
        if key not in self.profiles:
            raise DecisionLogAuditIndexStoreError(f"unknown DLA storage profile: {profile_id!r}")
        return self.profiles[key]


@dataclass(frozen=True)
class DecisionLogAuditStorageLayout:
    object_store_prefix: str
    index_locator: str
    profile_id: str | None = None
    retention_window: DecisionLogAuditRetentionWindow | None = None

    def object_key_for(self, *, platform_run_id: str, audit_id: str) -> str:
        root = self.object_store_prefix.rstrip("/")
        return f"{root}/{platform_run_id}/decision_log_audit/records/{audit_id}.json"


@dataclass(frozen=True)
class DecisionLogAuditObjectWriteResult:
    status: str
    audit_id: str
    record_digest: str
    object_ref: str


@dataclass(frozen=True)
class DecisionLogAuditIndexWriteResult:
    status: str
    audit_id: str
    record_digest: str


@dataclass(frozen=True)
class DecisionLogAuditIndexRecord:
    audit_id: str
    platform_run_id: str
    scenario_run_id: str
    decision_event_id: str
    recorded_at_utc: str
    record_digest: str
    object_ref: str


DEFAULT_STORAGE_POLICY_PATH = "config/platform/dla/storage_policy_v0.yaml"
_REQUIRED_PROFILES: tuple[str, ...] = ("local", "local_parity", "dev", "prod")


def load_storage_policy(path: Path | str) -> DecisionLogAuditStoragePolicy:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise DecisionLogAuditIndexStoreError("DLA storage policy payload must be a mapping")

    version = _require_non_empty_str(payload.get("version"), "version")
    policy_id = _require_non_empty_str(payload.get("policy_id"), "policy_id")
    revision = _require_non_empty_str(payload.get("revision"), "revision")
    profiles_raw = payload.get("profiles")
    if not isinstance(profiles_raw, Mapping):
        raise DecisionLogAuditIndexStoreError("profiles must be a mapping")

    profiles: dict[str, DecisionLogAuditStorageProfile] = {}
    for profile_id in _REQUIRED_PROFILES:
        if profile_id not in profiles_raw:
            raise DecisionLogAuditIndexStoreError(f"missing required profile: {profile_id}")
        value = profiles_raw[profile_id]
        if not isinstance(value, Mapping):
            raise DecisionLogAuditIndexStoreError(f"profile {profile_id!r} must be a mapping")
        object_prefix = _require_non_empty_str(value.get("object_store_prefix"), f"{profile_id}.object_store_prefix")
        retention_raw = value.get("retention")
        if not isinstance(retention_raw, Mapping):
            raise DecisionLogAuditIndexStoreError(f"{profile_id}.retention must be a mapping")
        retention = DecisionLogAuditRetentionWindow(
            audit_record_ttl_days=_positive_int(retention_raw.get("audit_record_ttl_days"), f"{profile_id}.retention.audit_record_ttl_days"),
            index_ttl_days=_positive_int(retention_raw.get("index_ttl_days"), f"{profile_id}.retention.index_ttl_days"),
            reconciliation_ttl_days=_positive_int(
                retention_raw.get("reconciliation_ttl_days"),
                f"{profile_id}.retention.reconciliation_ttl_days",
            ),
        )
        profiles[profile_id] = DecisionLogAuditStorageProfile(
            profile_id=profile_id,
            object_store_prefix=object_prefix,
            retention=retention,
        )

    return DecisionLogAuditStoragePolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        profiles=profiles,
    )


def build_storage_layout(config: Mapping[str, Any] | None = None) -> DecisionLogAuditStorageLayout:
    mapped = dict(config or {})
    object_prefix = str(mapped.get("object_store_prefix") or "").strip()
    profile_id = str(mapped.get("profile_id") or "").strip() or None
    retention_window: DecisionLogAuditRetentionWindow | None = None

    if not object_prefix and profile_id:
        policy_path = str(mapped.get("storage_policy_path") or DEFAULT_STORAGE_POLICY_PATH).strip()
        policy = load_storage_policy(Path(policy_path))
        profile = policy.profile(profile_id)
        object_prefix = profile.object_store_prefix
        retention_window = profile.retention

    if not object_prefix:
        object_prefix = "fraud-platform"

    index_locator_raw = str(mapped.get("index_locator") or "").strip()
    index_locator = resolve_run_scoped_path(
        index_locator_raw or None,
        suffix="decision_log_audit/dla_index.sqlite",
        create_if_missing=True,
    )
    if not index_locator:
        raise DecisionLogAuditIndexStoreError("failed to resolve DLA index locator")

    return DecisionLogAuditStorageLayout(
        object_store_prefix=object_prefix,
        index_locator=index_locator,
        profile_id=profile_id,
        retention_window=retention_window,
    )


class DecisionLogAuditObjectStore:
    """Append-only object writer for audit records."""

    def __init__(self, *, root_locator: str) -> None:
        locator = str(root_locator or "").strip()
        if not locator:
            raise DecisionLogAuditIndexStoreError("root_locator must be non-empty")
        self.root = Path(locator)
        self.root.mkdir(parents=True, exist_ok=True)

    def append_audit_record(
        self,
        *,
        record: AuditRecord,
        layout: DecisionLogAuditStorageLayout,
    ) -> DecisionLogAuditObjectWriteResult:
        object_ref = layout.object_key_for(platform_run_id=record.platform_run_id, audit_id=record.audit_id)
        rel_path = _object_ref_to_relative_path(object_ref)
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)

        payload_json = _canonical_json(record.as_dict())
        digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        if path.exists():
            existing_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if existing_digest == digest:
                return DecisionLogAuditObjectWriteResult(
                    status="DUPLICATE",
                    audit_id=record.audit_id,
                    record_digest=existing_digest,
                    object_ref=object_ref,
                )
            return DecisionLogAuditObjectWriteResult(
                status="HASH_MISMATCH",
                audit_id=record.audit_id,
                record_digest=existing_digest,
                object_ref=object_ref,
            )

        path.write_bytes(payload_json.encode("utf-8"))
        return DecisionLogAuditObjectWriteResult(
            status="NEW",
            audit_id=record.audit_id,
            record_digest=digest,
            object_ref=object_ref,
        )


class DecisionLogAuditIndexStore:
    def __init__(self, *, locator: str) -> None:
        self.locator = locator
        self.backend = "postgres" if is_postgres_dsn(locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def register_audit_record(
        self,
        record: AuditRecord,
        *,
        object_ref: str,
    ) -> DecisionLogAuditIndexWriteResult:
        payload = record.as_dict()
        digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        params = (
            record.audit_id,
            record.platform_run_id,
            record.scenario_run_id,
            str(payload["decision_event"]["event_id"]),
            str(payload["recorded_at_utc"]),
            digest,
            object_ref,
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                "SELECT record_digest FROM dla_audit_index WHERE audit_id = {p1}",
                (record.audit_id,),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO dla_audit_index (
                        audit_id,
                        platform_run_id,
                        scenario_run_id,
                        decision_event_id,
                        recorded_at_utc,
                        record_digest,
                        object_ref
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7})
                    """,
                    params,
                )
                return DecisionLogAuditIndexWriteResult(status="NEW", audit_id=record.audit_id, record_digest=digest)
            existing_digest = str(row[0])
            if existing_digest == digest:
                return DecisionLogAuditIndexWriteResult(
                    status="DUPLICATE",
                    audit_id=record.audit_id,
                    record_digest=existing_digest,
                )
            return DecisionLogAuditIndexWriteResult(
                status="HASH_MISMATCH",
                audit_id=record.audit_id,
                record_digest=existing_digest,
            )

    def get_by_audit_id(self, audit_id: str) -> DecisionLogAuditIndexRecord | None:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT audit_id, platform_run_id, scenario_run_id, decision_event_id,
                       recorded_at_utc, record_digest, object_ref
                FROM dla_audit_index
                WHERE audit_id = {p1}
                """,
                (audit_id,),
            )
        if row is None:
            return None
        return _row_to_index_record(row)

    def list_by_run_scope(self, *, platform_run_id: str, scenario_run_id: str, limit: int = 100) -> list[DecisionLogAuditIndexRecord]:
        bounded_limit = max(1, int(limit))
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT audit_id, platform_run_id, scenario_run_id, decision_event_id,
                       recorded_at_utc, record_digest, object_ref
                FROM dla_audit_index
                WHERE platform_run_id = {p1} AND scenario_run_id = {p2}
                ORDER BY recorded_at_utc, audit_id
                LIMIT {p3}
                """,
                (platform_run_id, scenario_run_id, bounded_limit),
            )
        return [_row_to_index_record(item) for item in rows]

    def list_by_decision_event(self, *, decision_event_id: str, limit: int = 100) -> list[DecisionLogAuditIndexRecord]:
        bounded_limit = max(1, int(limit))
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT audit_id, platform_run_id, scenario_run_id, decision_event_id,
                       recorded_at_utc, record_digest, object_ref
                FROM dla_audit_index
                WHERE decision_event_id = {p1}
                ORDER BY recorded_at_utc, audit_id
                LIMIT {p2}
                """,
                (decision_event_id, bounded_limit),
            )
        return [_row_to_index_record(item) for item in rows]

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS dla_audit_index (
                    audit_id TEXT PRIMARY KEY,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    decision_event_id TEXT NOT NULL,
                    recorded_at_utc TEXT NOT NULL,
                    record_digest TEXT NOT NULL,
                    object_ref TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_dla_audit_index_run_scope
                    ON dla_audit_index (platform_run_id, scenario_run_id, recorded_at_utc);
                CREATE INDEX IF NOT EXISTS ix_dla_audit_index_decision_event
                    ON dla_audit_index (decision_event_id, recorded_at_utc);
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def _row_to_index_record(row: Any) -> DecisionLogAuditIndexRecord:
    return DecisionLogAuditIndexRecord(
        audit_id=str(row[0]),
        platform_run_id=str(row[1]),
        scenario_run_id=str(row[2]),
        decision_event_id=str(row[3]),
        recorded_at_utc=str(row[4]),
        record_digest=str(row[5]),
        object_ref=str(row[6]),
    )


def _object_ref_to_relative_path(object_ref: str) -> Path:
    ref = str(object_ref or "").strip()
    if not ref:
        raise DecisionLogAuditIndexStoreError("object_ref must be non-empty")
    if "://" in ref:
        parsed = urlparse(ref)
        raw = "/".join(part for part in (parsed.netloc, parsed.path.lstrip("/")) if part)
    else:
        raw = ref.replace("\\", "/")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise DecisionLogAuditIndexStoreError(f"object_ref must be relative: {object_ref!r}")
    parts = [part for part in raw.split("/") if part and part != "."]
    if not parts or any(part == ".." for part in parts):
        raise DecisionLogAuditIndexStoreError(f"unsafe object_ref path: {object_ref!r}")
    return Path(*parts)


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _render_sql(sql: str, backend: str) -> str:
    if backend == "postgres":
        rendered = sql
        for idx in range(1, 21):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
        return rendered
    rendered = sql
    for idx in range(1, 21):
        rendered = rendered.replace(f"{{p{idx}}}", "?")
    return rendered


def _query_one(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> Any:
    rendered = _render_sql(sql, backend)
    if backend == "sqlite":
        cur = conn.execute(rendered, params)
        return cur.fetchone()
    cur = conn.cursor()
    cur.execute(rendered, params)
    row = cur.fetchone()
    cur.close()
    return row


def _query_all(conn: Any, backend: str, sql: str, params: tuple[Any, ...]) -> list[Any]:
    rendered = _render_sql(sql, backend)
    if backend == "sqlite":
        cur = conn.execute(rendered, params)
        return list(cur.fetchall())
    cur = conn.cursor()
    cur.execute(rendered, params)
    rows = list(cur.fetchall())
    cur.close()
    return rows


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


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require_non_empty_str(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionLogAuditIndexStoreError(f"{field_name} must be non-empty")
    return text


def _positive_int(value: Any, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DecisionLogAuditIndexStoreError(f"{field_name} must be a positive integer") from exc
    if parsed <= 0:
        raise DecisionLogAuditIndexStoreError(f"{field_name} must be a positive integer")
    return parsed
