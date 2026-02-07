"""Decision Log & Audit storage substrate (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass(frozen=True)
class DecisionLogAuditIntakeCheckpoint:
    topic: str
    partition: int
    next_offset: str
    offset_kind: str
    watermark_ts_utc: str | None
    updated_at_utc: str


@dataclass(frozen=True)
class DecisionLogAuditIntakeWriteResult:
    status: str
    record_id: str


@dataclass(frozen=True)
class DecisionLogAuditReplayObservationResult:
    status: str
    detail: str | None = None


@dataclass(frozen=True)
class DecisionLogAuditIntakeAttemptResult:
    status: str
    attempt_id: str


@dataclass(frozen=True)
class DecisionLogAuditLineageApplyResult:
    status: str
    decision_id: str
    chain_status: str
    unresolved_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DecisionLogAuditLineageChain:
    decision_id: str
    platform_run_id: str
    scenario_run_id: str
    decision_event_id: str | None
    decision_payload_hash: str | None
    decision_ref: dict[str, Any] | None
    intent_count: int
    outcome_count: int
    unresolved_reasons: tuple[str, ...]
    chain_status: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True)
class DecisionLogAuditLineageIntent:
    decision_id: str
    action_id: str
    intent_event_id: str
    payload_hash: str
    source_ref: dict[str, Any]
    requested_at_utc: str | None
    created_at_utc: str


@dataclass(frozen=True)
class DecisionLogAuditLineageOutcome:
    decision_id: str
    outcome_id: str
    action_id: str
    outcome_event_id: str
    payload_hash: str
    source_ref: dict[str, Any]
    status: str | None
    completed_at_utc: str | None
    created_at_utc: str


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


class DecisionLogAuditIntakeStore:
    """Durable intake substrate for Phase 3 gating."""

    def __init__(self, *, locator: str, stream_id: str = "dla.intake.v0") -> None:
        self.locator = str(locator or "").strip()
        self.stream_id = str(stream_id or "").strip()
        if not self.locator:
            raise DecisionLogAuditIndexStoreError("intake locator must be non-empty")
        if not self.stream_id:
            raise DecisionLogAuditIndexStoreError("intake stream_id must be non-empty")
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(self.locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def append_candidate(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        event_type: str,
        event_id: str,
        schema_version: str,
        payload_hash: str,
        source_topic: str,
        source_partition: int,
        source_offset: str,
        source_offset_kind: str,
        source_ts_utc: str | None,
        published_at_utc: str | None,
        envelope: Mapping[str, Any],
    ) -> DecisionLogAuditIntakeWriteResult:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT payload_hash
                FROM dla_intake_candidates
                WHERE platform_run_id = {p1} AND event_type = {p2} AND event_id = {p3}
                """,
                (platform_run_id, event_type, event_id),
            )
            if row is not None:
                existing_hash = str(row[0])
                if existing_hash == payload_hash:
                    return DecisionLogAuditIntakeWriteResult(status="DUPLICATE", record_id=event_id)
                return DecisionLogAuditIntakeWriteResult(status="HASH_MISMATCH", record_id=event_id)
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO dla_intake_candidates (
                    platform_run_id,
                    scenario_run_id,
                    event_type,
                    event_id,
                    schema_version,
                    payload_hash,
                    source_topic,
                    source_partition,
                    source_offset,
                    source_offset_kind,
                    source_ts_utc,
                    published_at_utc,
                    envelope_json,
                    created_at_utc
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10}, {p11}, {p12}, {p13}, {p14})
                """,
                (
                    platform_run_id,
                    scenario_run_id,
                    event_type,
                    event_id,
                    schema_version,
                    payload_hash,
                    source_topic,
                    int(source_partition),
                    source_offset,
                    source_offset_kind,
                    source_ts_utc,
                    published_at_utc,
                    _canonical_json(envelope),
                    _utc_now(),
                ),
            )
        return DecisionLogAuditIntakeWriteResult(status="NEW", record_id=event_id)

    def append_quarantine(
        self,
        *,
        reason_code: str,
        detail: str | None,
        source_topic: str,
        source_partition: int,
        source_offset: str,
        source_offset_kind: str,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        event_type: str | None = None,
        event_id: str | None = None,
        schema_version: str | None = None,
        payload_hash: str | None = None,
        source_ts_utc: str | None = None,
        published_at_utc: str | None = None,
        envelope: Mapping[str, Any] | None = None,
    ) -> DecisionLogAuditIntakeWriteResult:
        quarantine_id = _quarantine_record_id(
            source_topic=source_topic,
            source_partition=source_partition,
            source_offset=source_offset,
            source_offset_kind=source_offset_kind,
            reason_code=reason_code,
            event_id=event_id or "",
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                "SELECT quarantine_id FROM dla_intake_quarantine WHERE quarantine_id = {p1}",
                (quarantine_id,),
            )
            if row is not None:
                return DecisionLogAuditIntakeWriteResult(status="DUPLICATE", record_id=quarantine_id)
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO dla_intake_quarantine (
                    quarantine_id,
                    reason_code,
                    detail,
                    platform_run_id,
                    scenario_run_id,
                    event_type,
                    event_id,
                    schema_version,
                    payload_hash,
                    source_topic,
                    source_partition,
                    source_offset,
                    source_offset_kind,
                    source_ts_utc,
                    published_at_utc,
                    envelope_json,
                    created_at_utc
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10}, {p11}, {p12}, {p13}, {p14}, {p15}, {p16}, {p17})
                """,
                (
                    quarantine_id,
                    reason_code,
                    detail,
                    platform_run_id,
                    scenario_run_id,
                    event_type,
                    event_id,
                    schema_version,
                    payload_hash,
                    source_topic,
                    int(source_partition),
                    source_offset,
                    source_offset_kind,
                    source_ts_utc,
                    published_at_utc,
                    _canonical_json(envelope or {}),
                    _utc_now(),
                ),
            )
        return DecisionLogAuditIntakeWriteResult(status="NEW", record_id=quarantine_id)

    def record_replay_observation(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        platform_run_id: str,
        scenario_run_id: str,
        event_type: str,
        event_id: str,
        payload_hash: str,
    ) -> DecisionLogAuditReplayObservationResult:
        now_utc = _utc_now()
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT platform_run_id, scenario_run_id, event_type, event_id, payload_hash
                FROM dla_intake_replay_observations
                WHERE stream_id = {p1}
                  AND topic = {p2}
                  AND partition_id = {p3}
                  AND source_offset_kind = {p4}
                  AND source_offset = {p5}
                """,
                (self.stream_id, topic, int(partition), offset_kind, offset),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO dla_intake_replay_observations (
                        stream_id,
                        topic,
                        partition_id,
                        source_offset,
                        source_offset_kind,
                        platform_run_id,
                        scenario_run_id,
                        event_type,
                        event_id,
                        payload_hash,
                        first_seen_at_utc,
                        updated_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10}, {p11}, {p12})
                    """,
                    (
                        self.stream_id,
                        topic,
                        int(partition),
                        offset,
                        offset_kind,
                        platform_run_id,
                        scenario_run_id,
                        event_type,
                        event_id,
                        payload_hash,
                        now_utc,
                        now_utc,
                    ),
                )
                return DecisionLogAuditReplayObservationResult(status="NEW")

            observed = (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
            )
            incoming = (
                platform_run_id,
                scenario_run_id,
                event_type,
                event_id,
                payload_hash,
            )
            if observed == incoming:
                return DecisionLogAuditReplayObservationResult(status="DUPLICATE")
            return DecisionLogAuditReplayObservationResult(
                status="DIVERGENCE",
                detail=(
                    "observed="
                    f"{observed[0]}|{observed[1]}|{observed[2]}|{observed[3]}|{observed[4]}"
                    ";incoming="
                    f"{incoming[0]}|{incoming[1]}|{incoming[2]}|{incoming[3]}|{incoming[4]}"
                ),
            )

    def record_intake_attempt(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        platform_run_id: str | None,
        scenario_run_id: str | None,
        event_type: str | None,
        event_id: str | None,
        accepted: bool,
        reason_code: str,
        write_status: str | None,
        checkpoint_advanced: bool,
        detail: str | None,
    ) -> DecisionLogAuditIntakeAttemptResult:
        attempt_id = _intake_attempt_id(
            stream_id=self.stream_id,
            topic=topic,
            partition=partition,
            offset=offset,
            offset_kind=offset_kind,
            reason_code=reason_code,
            event_id=event_id or "",
            created_at_utc=_utc_now(),
        )
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                "SELECT attempt_id FROM dla_intake_attempts WHERE attempt_id = {p1}",
                (attempt_id,),
            )
            if row is not None:
                return DecisionLogAuditIntakeAttemptResult(status="DUPLICATE", attempt_id=attempt_id)
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO dla_intake_attempts (
                    attempt_id, stream_id, topic, partition_id, source_offset, source_offset_kind,
                    platform_run_id, scenario_run_id, event_type, event_id, accepted, reason_code,
                    write_status, checkpoint_advanced, detail, created_at_utc
                ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10}, {p11}, {p12}, {p13}, {p14}, {p15}, {p16})
                """,
                (
                    attempt_id,
                    self.stream_id,
                    topic,
                    int(partition),
                    offset,
                    offset_kind,
                    platform_run_id,
                    scenario_run_id,
                    event_type,
                    event_id,
                    1 if accepted else 0,
                    reason_code,
                    write_status,
                    1 if checkpoint_advanced else 0,
                    detail,
                    _utc_now(),
                ),
            )
        return DecisionLogAuditIntakeAttemptResult(status="NEW", attempt_id=attempt_id)

    def intake_metrics_snapshot(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
    ) -> dict[str, int]:
        with self._connect() as conn:
            counts = _query_one(
                conn,
                self.backend,
                """
                SELECT
                    SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) AS accepted_total,
                    SUM(CASE WHEN accepted = 0 THEN 1 ELSE 0 END) AS rejected_total,
                    SUM(CASE WHEN checkpoint_advanced = 1 THEN 1 ELSE 0 END) AS checkpoint_advanced_total,
                    SUM(CASE WHEN reason_code = {p3} THEN 1 ELSE 0 END) AS replay_divergence_total,
                    SUM(CASE WHEN reason_code = {p4} THEN 1 ELSE 0 END) AS write_failed_total
                FROM dla_intake_attempts
                WHERE stream_id = {p1}
                  AND platform_run_id = {p2}
                  AND scenario_run_id = {p5}
                """,
                (
                    self.stream_id,
                    platform_run_id,
                    "REPLAY_DIVERGENCE",
                    "WRITE_FAILED",
                    scenario_run_id,
                ),
            )
            candidate_count_row = _query_one(
                conn,
                self.backend,
                """
                SELECT COUNT(*)
                FROM dla_intake_candidates
                WHERE platform_run_id = {p1} AND scenario_run_id = {p2}
                """,
                (platform_run_id, scenario_run_id),
            )
            quarantine_count_row = _query_one(
                conn,
                self.backend,
                """
                SELECT COUNT(*)
                FROM dla_intake_quarantine
                WHERE platform_run_id = {p1} AND scenario_run_id = {p2}
                """,
                (platform_run_id, scenario_run_id),
            )
            replay_quarantine_row = _query_one(
                conn,
                self.backend,
                """
                SELECT COUNT(*)
                FROM dla_intake_quarantine
                WHERE platform_run_id = {p1}
                  AND scenario_run_id = {p2}
                  AND reason_code = {p3}
                """,
                (platform_run_id, scenario_run_id, "REPLAY_DIVERGENCE"),
            )
            unresolved_row = _query_one(
                conn,
                self.backend,
                """
                SELECT
                    SUM(CASE WHEN chain_status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved_total,
                    SUM(CASE WHEN chain_status = 'UNRESOLVED' THEN 1 ELSE 0 END) AS unresolved_total
                FROM dla_lineage_chains
                WHERE platform_run_id = {p1} AND scenario_run_id = {p2}
                """,
                (platform_run_id, scenario_run_id),
            )
        accepted_total = int((counts[0] or 0) if counts is not None else 0)
        rejected_total = int((counts[1] or 0) if counts is not None else 0)
        checkpoint_advanced_total = int((counts[2] or 0) if counts is not None else 0)
        replay_divergence_total = int((counts[3] or 0) if counts is not None else 0)
        write_failed_total = int((counts[4] or 0) if counts is not None else 0)
        candidate_total = int(candidate_count_row[0] if candidate_count_row else 0)
        quarantine_total = int(quarantine_count_row[0] if quarantine_count_row else 0)
        replay_quarantine_total = int(replay_quarantine_row[0] if replay_quarantine_row else 0)
        resolved_total = int((unresolved_row[0] or 0) if unresolved_row is not None else 0)
        unresolved_total = int((unresolved_row[1] or 0) if unresolved_row is not None else 0)
        return {
            "append_success_total": candidate_total + quarantine_total,
            "append_failure_total": write_failed_total,
            "accepted_total": accepted_total,
            "rejected_total": rejected_total,
            "checkpoint_advanced_total": checkpoint_advanced_total,
            "candidate_total": candidate_total,
            "quarantine_total": quarantine_total,
            "lineage_resolved_total": resolved_total,
            "lineage_unresolved_total": unresolved_total,
            "replay_divergence_total": max(replay_divergence_total, replay_quarantine_total),
        }

    def checkpoint_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT
                    COUNT(*) AS checkpoint_count,
                    MIN(updated_at_utc) AS oldest_checkpoint_updated_at_utc,
                    MAX(updated_at_utc) AS latest_checkpoint_updated_at_utc,
                    MAX(watermark_ts_utc) AS watermark_ts_utc
                FROM dla_intake_checkpoints
                WHERE stream_id = {p1}
                """,
                (self.stream_id,),
            )
        return {
            "checkpoint_count": int((row[0] or 0) if row is not None else 0),
            "oldest_checkpoint_updated_at_utc": str(row[1]) if row and row[1] not in (None, "") else None,
            "latest_checkpoint_updated_at_utc": str(row[2]) if row and row[2] not in (None, "") else None,
            "watermark_ts_utc": str(row[3]) if row and row[3] not in (None, "") else None,
        }

    def quarantine_reason_counts(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        limit: int = 50,
    ) -> dict[str, int]:
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT reason_code, COUNT(*)
                FROM dla_intake_quarantine
                WHERE platform_run_id = {p1} AND scenario_run_id = {p2}
                GROUP BY reason_code
                ORDER BY COUNT(*) DESC, reason_code
                LIMIT {p3}
                """,
                (platform_run_id, scenario_run_id, max(1, int(limit))),
            )
        return {str(item[0]): int(item[1]) for item in rows}

    def governance_stamp_summary(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        limit: int = 5000,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT envelope_json
                FROM dla_intake_candidates
                WHERE platform_run_id = {p1}
                  AND scenario_run_id = {p2}
                  AND event_type = 'decision_response'
                ORDER BY created_at_utc, event_id
                LIMIT {p3}
                """,
                (platform_run_id, scenario_run_id, max(1, int(limit))),
            )
        policy_refs: set[str] = set()
        bundle_refs: set[str] = set()
        execution_profile_refs: set[str] = set()
        run_config_digests: set[str] = set()
        for row in rows:
            try:
                envelope = json.loads(str(row[0]))
            except (TypeError, ValueError):
                continue
            if not isinstance(envelope, Mapping):
                continue
            payload = envelope.get("payload")
            if not isinstance(payload, Mapping):
                continue
            policy = payload.get("policy_rev")
            if isinstance(policy, Mapping):
                policy_id = str(policy.get("policy_id") or "").strip()
                revision = str(policy.get("revision") or "").strip()
                if policy_id and revision:
                    policy_refs.add(f"policy://{policy_id}@{revision}")
            bundle = payload.get("bundle_ref")
            if isinstance(bundle, Mapping):
                bundle_id = str(bundle.get("bundle_id") or "").strip()
                bundle_version = str(bundle.get("bundle_version") or "").strip()
                if bundle_id and bundle_version:
                    bundle_refs.add(f"bundle://{bundle_id}@{bundle_version}")
            degrade = payload.get("degrade_posture")
            if isinstance(degrade, Mapping):
                mode = str(degrade.get("mode") or "").strip()
                policy_rev = degrade.get("policy_rev")
                if isinstance(policy_rev, Mapping):
                    policy_id = str(policy_rev.get("policy_id") or "").strip()
                    revision = str(policy_rev.get("revision") or "").strip()
                    if policy_id and revision and mode:
                        execution_profile_refs.add(f"policy://{policy_id}@{revision}#mode={mode}")
            run_config_digest = str(payload.get("run_config_digest") or "").strip()
            if run_config_digest:
                run_config_digests.add(run_config_digest)
        return {
            "policy_refs": sorted(policy_refs),
            "bundle_refs": sorted(bundle_refs),
            "execution_profile_refs": sorted(execution_profile_refs),
            "run_config_digests": sorted(run_config_digests),
        }

    def recent_attempts(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT topic, partition_id, source_offset, source_offset_kind, event_type, event_id,
                       accepted, reason_code, write_status, checkpoint_advanced, detail, created_at_utc
                FROM dla_intake_attempts
                WHERE stream_id = {p1}
                  AND platform_run_id = {p2}
                  AND scenario_run_id = {p3}
                ORDER BY created_at_utc DESC
                LIMIT {p4}
                """,
                (self.stream_id, platform_run_id, scenario_run_id, max(1, int(limit))),
            )
        records: list[dict[str, Any]] = []
        for row in rows:
            records.append(
                {
                    "topic": str(row[0]),
                    "partition": int(row[1]),
                    "source_offset": str(row[2]),
                    "source_offset_kind": str(row[3]),
                    "event_type": str(row[4]) if row[4] not in (None, "") else None,
                    "event_id": str(row[5]) if row[5] not in (None, "") else None,
                    "accepted": bool(int(row[6])),
                    "reason_code": str(row[7]),
                    "write_status": str(row[8]) if row[8] not in (None, "") else None,
                    "checkpoint_advanced": bool(int(row[9])),
                    "detail": str(row[10]) if row[10] not in (None, "") else None,
                    "created_at_utc": str(row[11]),
                }
            )
        return records

    def lineage_fingerprint(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        limit: int = 200000,
    ) -> str:
        chains = self.list_lineage_chains_by_run_scope(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            limit=max(1, int(limit)),
        )
        lineage_payload: dict[str, Any] = {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "chains": [],
        }
        for chain in chains:
            intents = self.list_lineage_intents(decision_id=chain.decision_id)
            outcomes = self.list_lineage_outcomes(decision_id=chain.decision_id)
            lineage_payload["chains"].append(
                {
                    "decision_id": chain.decision_id,
                    "decision_event_id": chain.decision_event_id,
                    "decision_payload_hash": chain.decision_payload_hash,
                    "decision_ref": dict(chain.decision_ref) if isinstance(chain.decision_ref, Mapping) else chain.decision_ref,
                    "intent_count": chain.intent_count,
                    "outcome_count": chain.outcome_count,
                    "unresolved_reasons": list(chain.unresolved_reasons),
                    "chain_status": chain.chain_status,
                    "intents": [
                        {
                            "action_id": item.action_id,
                            "intent_event_id": item.intent_event_id,
                            "payload_hash": item.payload_hash,
                            "source_ref": dict(item.source_ref),
                            "requested_at_utc": item.requested_at_utc,
                        }
                        for item in intents
                    ],
                    "outcomes": [
                        {
                            "outcome_id": item.outcome_id,
                            "action_id": item.action_id,
                            "outcome_event_id": item.outcome_event_id,
                            "payload_hash": item.payload_hash,
                            "source_ref": dict(item.source_ref),
                            "status": item.status,
                            "completed_at_utc": item.completed_at_utc,
                        }
                        for item in outcomes
                    ],
                }
            )
        digest = hashlib.sha256(_canonical_json(lineage_payload).encode("utf-8")).hexdigest()
        return digest

    def get_checkpoint(self, *, topic: str, partition: int) -> DecisionLogAuditIntakeCheckpoint | None:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc
                FROM dla_intake_checkpoints
                WHERE stream_id = {p1} AND topic = {p2} AND partition_id = {p3}
                """,
                (self.stream_id, topic, int(partition)),
            )
        if row is None:
            return None
        return DecisionLogAuditIntakeCheckpoint(
            topic=str(row[0]),
            partition=int(row[1]),
            next_offset=str(row[2]),
            offset_kind=str(row[3]),
            watermark_ts_utc=str(row[4]) if row[4] not in (None, "") else None,
            updated_at_utc=str(row[5]),
        )

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> str:
        next_offset = _next_offset_value(offset=offset, offset_kind=offset_kind)
        now_utc = _utc_now()
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT next_offset, offset_kind, watermark_ts_utc
                FROM dla_intake_checkpoints
                WHERE stream_id = {p1} AND topic = {p2} AND partition_id = {p3}
                """,
                (self.stream_id, topic, int(partition)),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO dla_intake_checkpoints (
                        stream_id, topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7})
                    """,
                    (
                        self.stream_id,
                        topic,
                        int(partition),
                        next_offset,
                        offset_kind,
                        event_ts_utc,
                        now_utc,
                    ),
                )
                return "NEW"
            current_next_offset = str(row[0])
            current_offset_kind = str(row[1])
            current_watermark = str(row[2]) if row[2] not in (None, "") else None
            if current_offset_kind != offset_kind:
                raise DecisionLogAuditIndexStoreError(
                    f"offset_kind mismatch for checkpoint: {current_offset_kind!r} vs {offset_kind!r}"
                )
            if not _offset_after(new_offset=next_offset, current_offset=current_next_offset, offset_kind=offset_kind):
                return "IGNORED"
            watermark = _max_timestamp(current_watermark, event_ts_utc)
            _execute(
                conn,
                self.backend,
                """
                UPDATE dla_intake_checkpoints
                SET next_offset = {p1}, watermark_ts_utc = {p2}, updated_at_utc = {p3}
                WHERE stream_id = {p4} AND topic = {p5} AND partition_id = {p6}
                """,
                (
                    next_offset,
                    watermark,
                    now_utc,
                    self.stream_id,
                    topic,
                    int(partition),
                ),
            )
        return "ADVANCED"

    def apply_lineage_candidate(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        event_type: str,
        event_id: str,
        schema_version: str,
        payload_hash: str,
        payload: Mapping[str, Any],
        source_ref: Mapping[str, Any],
    ) -> DecisionLogAuditLineageApplyResult:
        event_type_norm = str(event_type or "").strip()
        if event_type_norm == "decision_response":
            return self._apply_decision_response(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_id=event_id,
                schema_version=schema_version,
                payload_hash=payload_hash,
                payload=payload,
                source_ref=source_ref,
            )
        if event_type_norm == "action_intent":
            return self._apply_action_intent(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_id=event_id,
                schema_version=schema_version,
                payload_hash=payload_hash,
                payload=payload,
                source_ref=source_ref,
            )
        if event_type_norm == "action_outcome":
            return self._apply_action_outcome(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_id=event_id,
                schema_version=schema_version,
                payload_hash=payload_hash,
                payload=payload,
                source_ref=source_ref,
            )
        raise DecisionLogAuditIndexStoreError(f"unsupported lineage event_type: {event_type_norm!r}")

    def get_lineage_chain(self, *, decision_id: str) -> DecisionLogAuditLineageChain | None:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT decision_id, platform_run_id, scenario_run_id, decision_event_id, decision_payload_hash,
                       decision_ref_json, intent_count, outcome_count, unresolved_reasons_json, chain_status,
                       created_at_utc, updated_at_utc
                FROM dla_lineage_chains
                WHERE decision_id = {p1}
                """,
                (decision_id,),
            )
        if row is None:
            return None
        return _row_to_lineage_chain(row)

    def list_lineage_chains_by_run_scope(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        start_ts_utc: str | None = None,
        end_ts_utc: str | None = None,
        limit: int = 100,
    ) -> list[DecisionLogAuditLineageChain]:
        bounded_limit = max(1, int(limit))
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT decision_id, platform_run_id, scenario_run_id, decision_event_id, decision_payload_hash,
                       decision_ref_json, intent_count, outcome_count, unresolved_reasons_json, chain_status,
                       created_at_utc, updated_at_utc
                FROM dla_lineage_chains
                WHERE platform_run_id = {p1}
                  AND scenario_run_id = {p2}
                  AND ({p3} IS NULL OR COALESCE(decision_ts_utc, updated_at_utc) >= {p4})
                  AND ({p5} IS NULL OR COALESCE(decision_ts_utc, updated_at_utc) <= {p6})
                ORDER BY COALESCE(decision_ts_utc, updated_at_utc), decision_id
                LIMIT {p7}
                """,
                (platform_run_id, scenario_run_id, start_ts_utc, start_ts_utc, end_ts_utc, end_ts_utc, bounded_limit),
            )
        return [_row_to_lineage_chain(row) for row in rows]

    def list_lineage_chains_by_action_id(
        self,
        *,
        action_id: str,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        limit: int = 100,
    ) -> list[DecisionLogAuditLineageChain]:
        bounded_limit = max(1, int(limit))
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT c.decision_id, c.platform_run_id, c.scenario_run_id, c.decision_event_id, c.decision_payload_hash,
                       c.decision_ref_json, c.intent_count, c.outcome_count, c.unresolved_reasons_json, c.chain_status,
                       c.created_at_utc, c.updated_at_utc
                FROM dla_lineage_chains c
                JOIN dla_lineage_intents i ON i.decision_id = c.decision_id
                WHERE i.action_id = {p1}
                  AND ({p2} IS NULL OR c.platform_run_id = {p3})
                  AND ({p4} IS NULL OR c.scenario_run_id = {p5})
                ORDER BY COALESCE(c.decision_ts_utc, c.updated_at_utc), c.decision_id
                LIMIT {p6}
                """,
                (action_id, platform_run_id, platform_run_id, scenario_run_id, scenario_run_id, bounded_limit),
            )
        return [_row_to_lineage_chain(row) for row in rows]

    def list_lineage_chains_by_outcome_id(
        self,
        *,
        outcome_id: str,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        limit: int = 100,
    ) -> list[DecisionLogAuditLineageChain]:
        bounded_limit = max(1, int(limit))
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT c.decision_id, c.platform_run_id, c.scenario_run_id, c.decision_event_id, c.decision_payload_hash,
                       c.decision_ref_json, c.intent_count, c.outcome_count, c.unresolved_reasons_json, c.chain_status,
                       c.created_at_utc, c.updated_at_utc
                FROM dla_lineage_chains c
                JOIN dla_lineage_outcomes o ON o.decision_id = c.decision_id
                WHERE o.outcome_id = {p1}
                  AND ({p2} IS NULL OR c.platform_run_id = {p3})
                  AND ({p4} IS NULL OR c.scenario_run_id = {p5})
                ORDER BY COALESCE(c.decision_ts_utc, c.updated_at_utc), c.decision_id
                LIMIT {p6}
                """,
                (outcome_id, platform_run_id, platform_run_id, scenario_run_id, scenario_run_id, bounded_limit),
            )
        return [_row_to_lineage_chain(row) for row in rows]

    def list_lineage_intents(self, *, decision_id: str) -> list[DecisionLogAuditLineageIntent]:
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT decision_id, action_id, intent_event_id, payload_hash, source_ref_json, requested_at_utc, created_at_utc
                FROM dla_lineage_intents
                WHERE decision_id = {p1}
                ORDER BY created_at_utc, action_id
                """,
                (decision_id,),
            )
        items: list[DecisionLogAuditLineageIntent] = []
        for row in rows:
            items.append(
                DecisionLogAuditLineageIntent(
                    decision_id=str(row[0]),
                    action_id=str(row[1]),
                    intent_event_id=str(row[2]),
                    payload_hash=str(row[3]),
                    source_ref=json.loads(str(row[4])),
                    requested_at_utc=str(row[5]) if row[5] not in (None, "") else None,
                    created_at_utc=str(row[6]),
                )
            )
        return items

    def list_lineage_outcomes(self, *, decision_id: str) -> list[DecisionLogAuditLineageOutcome]:
        with self._connect() as conn:
            rows = _query_all(
                conn,
                self.backend,
                """
                SELECT decision_id, outcome_id, action_id, outcome_event_id, payload_hash, source_ref_json, status, completed_at_utc, created_at_utc
                FROM dla_lineage_outcomes
                WHERE decision_id = {p1}
                ORDER BY created_at_utc, outcome_id
                """,
                (decision_id,),
            )
        items: list[DecisionLogAuditLineageOutcome] = []
        for row in rows:
            items.append(
                DecisionLogAuditLineageOutcome(
                    decision_id=str(row[0]),
                    outcome_id=str(row[1]),
                    action_id=str(row[2]),
                    outcome_event_id=str(row[3]),
                    payload_hash=str(row[4]),
                    source_ref=json.loads(str(row[5])),
                    status=str(row[6]) if row[6] not in (None, "") else None,
                    completed_at_utc=str(row[7]) if row[7] not in (None, "") else None,
                    created_at_utc=str(row[8]),
                )
            )
        return items

    def _apply_decision_response(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        event_id: str,
        schema_version: str,
        payload_hash: str,
        payload: Mapping[str, Any],
        source_ref: Mapping[str, Any],
    ) -> DecisionLogAuditLineageApplyResult:
        decision_id = _require_non_empty_str(payload.get("decision_id"), "decision_response.payload.decision_id")
        decision_ts_utc = str(payload.get("decided_at_utc") or "") or None
        source_ref_json = _canonical_json(
            {
                **dict(source_ref),
                "event_id": event_id,
                "event_type": "decision_response",
                "schema_version": schema_version,
                "payload_hash": payload_hash,
            }
        )
        now_utc = _utc_now()
        with self._connect() as conn:
            chain = _query_one(
                conn,
                self.backend,
                """
                SELECT platform_run_id, scenario_run_id, decision_event_id, decision_payload_hash
                FROM dla_lineage_chains
                WHERE decision_id = {p1}
                """,
                (decision_id,),
            )
            if chain is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO dla_lineage_chains (
                        decision_id, platform_run_id, scenario_run_id, decision_event_id, decision_payload_hash,
                        decision_ref_json, decision_ts_utc, intent_count, outcome_count, unresolved_reasons_json,
                        chain_status, created_at_utc, updated_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, 0, 0, {p8}, 'UNRESOLVED', {p9}, {p10})
                    """,
                    (
                        decision_id,
                        platform_run_id,
                        scenario_run_id,
                        event_id,
                        payload_hash,
                        source_ref_json,
                        decision_ts_utc,
                        "[]",
                        now_utc,
                        now_utc,
                    ),
                )
                event_status = "NEW"
            else:
                if str(chain[0]) != platform_run_id or str(chain[1]) != scenario_run_id:
                    return DecisionLogAuditLineageApplyResult(
                        status="CONFLICT",
                        decision_id=decision_id,
                        chain_status="UNRESOLVED",
                        unresolved_reasons=("RUN_SCOPE_MISMATCH",),
                    )
                existing_event = str(chain[2]) if chain[2] not in (None, "") else None
                existing_hash = str(chain[3]) if chain[3] not in (None, "") else None
                if existing_event in (None, ""):
                    _execute(
                        conn,
                        self.backend,
                        """
                        UPDATE dla_lineage_chains
                        SET decision_event_id = {p1},
                            decision_payload_hash = {p2},
                            decision_ref_json = {p3},
                            decision_ts_utc = {p4},
                            updated_at_utc = {p5}
                        WHERE decision_id = {p6}
                        """,
                        (event_id, payload_hash, source_ref_json, decision_ts_utc, now_utc, decision_id),
                    )
                    event_status = "NEW"
                elif existing_event == event_id and existing_hash == payload_hash:
                    event_status = "DUPLICATE"
                else:
                    return DecisionLogAuditLineageApplyResult(
                        status="CONFLICT",
                        decision_id=decision_id,
                        chain_status="UNRESOLVED",
                        unresolved_reasons=("DECISION_LINK_CONFLICT",),
                    )
            chain_status, unresolved = self._refresh_lineage_chain(conn, decision_id=decision_id)
        return DecisionLogAuditLineageApplyResult(
            status=event_status,
            decision_id=decision_id,
            chain_status=chain_status,
            unresolved_reasons=tuple(unresolved),
        )

    def _apply_action_intent(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        event_id: str,
        schema_version: str,
        payload_hash: str,
        payload: Mapping[str, Any],
        source_ref: Mapping[str, Any],
    ) -> DecisionLogAuditLineageApplyResult:
        decision_id = _require_non_empty_str(payload.get("decision_id"), "action_intent.payload.decision_id")
        action_id = _require_non_empty_str(payload.get("action_id"), "action_intent.payload.action_id")
        requested_at_utc = str(payload.get("requested_at_utc") or "") or None
        source_ref_json = _canonical_json(
            {
                **dict(source_ref),
                "event_id": event_id,
                "event_type": "action_intent",
                "schema_version": schema_version,
                "payload_hash": payload_hash,
            }
        )
        now_utc = _utc_now()
        with self._connect() as conn:
            if not self._ensure_chain_scope(
                conn,
                decision_id=decision_id,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                created_at_utc=now_utc,
            ):
                return DecisionLogAuditLineageApplyResult(
                    status="CONFLICT",
                    decision_id=decision_id,
                    chain_status="UNRESOLVED",
                    unresolved_reasons=("RUN_SCOPE_MISMATCH",),
                )
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT intent_event_id, payload_hash
                FROM dla_lineage_intents
                WHERE decision_id = {p1} AND action_id = {p2}
                """,
                (decision_id, action_id),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO dla_lineage_intents (
                        decision_id, action_id, platform_run_id, scenario_run_id, intent_event_id, payload_hash,
                        source_ref_json, requested_at_utc, created_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9})
                    """,
                    (
                        decision_id,
                        action_id,
                        platform_run_id,
                        scenario_run_id,
                        event_id,
                        payload_hash,
                        source_ref_json,
                        requested_at_utc,
                        now_utc,
                    ),
                )
                event_status = "NEW"
            elif str(row[0]) == event_id and str(row[1]) == payload_hash:
                event_status = "DUPLICATE"
            else:
                return DecisionLogAuditLineageApplyResult(
                    status="CONFLICT",
                    decision_id=decision_id,
                    chain_status="UNRESOLVED",
                    unresolved_reasons=("INTENT_LINK_CONFLICT",),
                )
            chain_status, unresolved = self._refresh_lineage_chain(conn, decision_id=decision_id)
        return DecisionLogAuditLineageApplyResult(
            status=event_status,
            decision_id=decision_id,
            chain_status=chain_status,
            unresolved_reasons=tuple(unresolved),
        )

    def _apply_action_outcome(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        event_id: str,
        schema_version: str,
        payload_hash: str,
        payload: Mapping[str, Any],
        source_ref: Mapping[str, Any],
    ) -> DecisionLogAuditLineageApplyResult:
        decision_id = _require_non_empty_str(payload.get("decision_id"), "action_outcome.payload.decision_id")
        action_id = _require_non_empty_str(payload.get("action_id"), "action_outcome.payload.action_id")
        outcome_id = _require_non_empty_str(payload.get("outcome_id"), "action_outcome.payload.outcome_id")
        status_value = str(payload.get("status") or "") or None
        completed_at_utc = str(payload.get("completed_at_utc") or "") or None
        source_ref_json = _canonical_json(
            {
                **dict(source_ref),
                "event_id": event_id,
                "event_type": "action_outcome",
                "schema_version": schema_version,
                "payload_hash": payload_hash,
            }
        )
        now_utc = _utc_now()
        with self._connect() as conn:
            if not self._ensure_chain_scope(
                conn,
                decision_id=decision_id,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                created_at_utc=now_utc,
            ):
                return DecisionLogAuditLineageApplyResult(
                    status="CONFLICT",
                    decision_id=decision_id,
                    chain_status="UNRESOLVED",
                    unresolved_reasons=("RUN_SCOPE_MISMATCH",),
                )
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT outcome_event_id, payload_hash
                FROM dla_lineage_outcomes
                WHERE decision_id = {p1} AND outcome_id = {p2}
                """,
                (decision_id, outcome_id),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO dla_lineage_outcomes (
                        decision_id, outcome_id, action_id, platform_run_id, scenario_run_id, outcome_event_id,
                        payload_hash, source_ref_json, status, completed_at_utc, created_at_utc
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, {p8}, {p9}, {p10}, {p11})
                    """,
                    (
                        decision_id,
                        outcome_id,
                        action_id,
                        platform_run_id,
                        scenario_run_id,
                        event_id,
                        payload_hash,
                        source_ref_json,
                        status_value,
                        completed_at_utc,
                        now_utc,
                    ),
                )
                event_status = "NEW"
            elif str(row[0]) == event_id and str(row[1]) == payload_hash:
                event_status = "DUPLICATE"
            else:
                return DecisionLogAuditLineageApplyResult(
                    status="CONFLICT",
                    decision_id=decision_id,
                    chain_status="UNRESOLVED",
                    unresolved_reasons=("OUTCOME_LINK_CONFLICT",),
                )
            chain_status, unresolved = self._refresh_lineage_chain(conn, decision_id=decision_id)
        return DecisionLogAuditLineageApplyResult(
            status=event_status,
            decision_id=decision_id,
            chain_status=chain_status,
            unresolved_reasons=tuple(unresolved),
        )

    def _ensure_chain_scope(
        self,
        conn: Any,
        *,
        decision_id: str,
        platform_run_id: str,
        scenario_run_id: str,
        created_at_utc: str,
    ) -> bool:
        row = _query_one(
            conn,
            self.backend,
            """
            SELECT platform_run_id, scenario_run_id
            FROM dla_lineage_chains
            WHERE decision_id = {p1}
            """,
            (decision_id,),
        )
        if row is None:
            _execute(
                conn,
                self.backend,
                """
                INSERT INTO dla_lineage_chains (
                    decision_id, platform_run_id, scenario_run_id, decision_event_id, decision_payload_hash,
                    decision_ref_json, decision_ts_utc, intent_count, outcome_count, unresolved_reasons_json,
                    chain_status, created_at_utc, updated_at_utc
                ) VALUES ({p1}, {p2}, {p3}, NULL, NULL, NULL, NULL, 0, 0, {p4}, 'UNRESOLVED', {p5}, {p6})
                """,
                (decision_id, platform_run_id, scenario_run_id, "[]", created_at_utc, created_at_utc),
            )
            return True
        return str(row[0]) == platform_run_id and str(row[1]) == scenario_run_id

    def _refresh_lineage_chain(self, conn: Any, *, decision_id: str) -> tuple[str, list[str]]:
        chain_row = _query_one(
            conn,
            self.backend,
            """
            SELECT decision_event_id
            FROM dla_lineage_chains
            WHERE decision_id = {p1}
            """,
            (decision_id,),
        )
        if chain_row is None:
            raise DecisionLogAuditIndexStoreError(f"lineage chain missing for decision_id={decision_id!r}")
        has_decision = chain_row[0] not in (None, "")
        intent_count_row = _query_one(
            conn,
            self.backend,
            "SELECT COUNT(*) FROM dla_lineage_intents WHERE decision_id = {p1}",
            (decision_id,),
        )
        outcome_count_row = _query_one(
            conn,
            self.backend,
            "SELECT COUNT(*) FROM dla_lineage_outcomes WHERE decision_id = {p1}",
            (decision_id,),
        )
        missing_intent_row = _query_one(
            conn,
            self.backend,
            """
            SELECT COUNT(*)
            FROM dla_lineage_outcomes o
            LEFT JOIN dla_lineage_intents i
              ON i.decision_id = o.decision_id AND i.action_id = o.action_id
            WHERE o.decision_id = {p1} AND i.action_id IS NULL
            """,
            (decision_id,),
        )
        missing_outcome_row = _query_one(
            conn,
            self.backend,
            """
            SELECT COUNT(*)
            FROM dla_lineage_intents i
            LEFT JOIN dla_lineage_outcomes o
              ON o.decision_id = i.decision_id AND o.action_id = i.action_id
            WHERE i.decision_id = {p1} AND o.outcome_id IS NULL
            """,
            (decision_id,),
        )
        intent_count = int(intent_count_row[0] if intent_count_row else 0)
        outcome_count = int(outcome_count_row[0] if outcome_count_row else 0)
        missing_intent_count = int(missing_intent_row[0] if missing_intent_row else 0)
        missing_outcome_count = int(missing_outcome_row[0] if missing_outcome_row else 0)

        unresolved: list[str] = []
        if not has_decision:
            unresolved.append("MISSING_DECISION")
        if missing_intent_count > 0:
            unresolved.append("MISSING_INTENT_LINK")
        if missing_outcome_count > 0:
            unresolved.append("MISSING_OUTCOME_LINK")
        chain_status = "RESOLVED" if not unresolved else "UNRESOLVED"
        _execute(
            conn,
            self.backend,
            """
            UPDATE dla_lineage_chains
            SET intent_count = {p1},
                outcome_count = {p2},
                unresolved_reasons_json = {p3},
                chain_status = {p4},
                updated_at_utc = {p5}
            WHERE decision_id = {p6}
            """,
            (
                intent_count,
                outcome_count,
                json.dumps(sorted(unresolved), ensure_ascii=True, separators=(",", ":")),
                chain_status,
                _utc_now(),
                decision_id,
            ),
        )
        return chain_status, sorted(unresolved)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS dla_intake_candidates (
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    source_topic TEXT NOT NULL,
                    source_partition INTEGER NOT NULL,
                    source_offset TEXT NOT NULL,
                    source_offset_kind TEXT NOT NULL,
                    source_ts_utc TEXT,
                    published_at_utc TEXT,
                    envelope_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (platform_run_id, event_type, event_id)
                );
                CREATE INDEX IF NOT EXISTS ix_dla_intake_candidates_source
                    ON dla_intake_candidates (source_topic, source_partition, source_offset);

                CREATE TABLE IF NOT EXISTS dla_intake_quarantine (
                    quarantine_id TEXT PRIMARY KEY,
                    reason_code TEXT NOT NULL,
                    detail TEXT,
                    platform_run_id TEXT,
                    scenario_run_id TEXT,
                    event_type TEXT,
                    event_id TEXT,
                    schema_version TEXT,
                    payload_hash TEXT,
                    source_topic TEXT NOT NULL,
                    source_partition INTEGER NOT NULL,
                    source_offset TEXT NOT NULL,
                    source_offset_kind TEXT NOT NULL,
                    source_ts_utc TEXT,
                    published_at_utc TEXT,
                    envelope_json TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS ux_dla_intake_quarantine_source_reason
                    ON dla_intake_quarantine (source_topic, source_partition, source_offset, source_offset_kind, reason_code);

                CREATE TABLE IF NOT EXISTS dla_intake_checkpoints (
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    partition_id INTEGER NOT NULL,
                    next_offset TEXT NOT NULL,
                    offset_kind TEXT NOT NULL,
                    watermark_ts_utc TEXT,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, topic, partition_id)
                );

                CREATE TABLE IF NOT EXISTS dla_intake_replay_observations (
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    partition_id INTEGER NOT NULL,
                    source_offset TEXT NOT NULL,
                    source_offset_kind TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    first_seen_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, topic, partition_id, source_offset_kind, source_offset)
                );
                CREATE INDEX IF NOT EXISTS ix_dla_intake_replay_observations_run_scope
                    ON dla_intake_replay_observations (platform_run_id, scenario_run_id, topic, partition_id);

                CREATE TABLE IF NOT EXISTS dla_intake_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    partition_id INTEGER NOT NULL,
                    source_offset TEXT NOT NULL,
                    source_offset_kind TEXT NOT NULL,
                    platform_run_id TEXT,
                    scenario_run_id TEXT,
                    event_type TEXT,
                    event_id TEXT,
                    accepted INTEGER NOT NULL,
                    reason_code TEXT NOT NULL,
                    write_status TEXT,
                    checkpoint_advanced INTEGER NOT NULL,
                    detail TEXT,
                    created_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_dla_intake_attempts_run_scope
                    ON dla_intake_attempts (stream_id, platform_run_id, scenario_run_id, created_at_utc);
                CREATE INDEX IF NOT EXISTS ix_dla_intake_attempts_reason
                    ON dla_intake_attempts (stream_id, reason_code, created_at_utc);

                CREATE TABLE IF NOT EXISTS dla_lineage_chains (
                    decision_id TEXT PRIMARY KEY,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    decision_event_id TEXT,
                    decision_payload_hash TEXT,
                    decision_ref_json TEXT,
                    decision_ts_utc TEXT,
                    intent_count INTEGER NOT NULL DEFAULT 0,
                    outcome_count INTEGER NOT NULL DEFAULT 0,
                    unresolved_reasons_json TEXT NOT NULL,
                    chain_status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_dla_lineage_chains_status
                    ON dla_lineage_chains (chain_status, updated_at_utc);

                CREATE TABLE IF NOT EXISTS dla_lineage_intents (
                    decision_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    intent_event_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    source_ref_json TEXT NOT NULL,
                    requested_at_utc TEXT,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (decision_id, action_id)
                );
                CREATE INDEX IF NOT EXISTS ix_dla_lineage_intents_decision
                    ON dla_lineage_intents (decision_id, created_at_utc);

                CREATE TABLE IF NOT EXISTS dla_lineage_outcomes (
                    decision_id TEXT NOT NULL,
                    outcome_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    platform_run_id TEXT NOT NULL,
                    scenario_run_id TEXT NOT NULL,
                    outcome_event_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    source_ref_json TEXT NOT NULL,
                    status TEXT,
                    completed_at_utc TEXT,
                    created_at_utc TEXT NOT NULL,
                    PRIMARY KEY (decision_id, outcome_id)
                );
                CREATE INDEX IF NOT EXISTS ix_dla_lineage_outcomes_decision
                    ON dla_lineage_outcomes (decision_id, created_at_utc);
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


def _row_to_lineage_chain(row: Any) -> DecisionLogAuditLineageChain:
    decision_ref_raw = str(row[5]) if row[5] not in (None, "") else None
    decision_ref = json.loads(decision_ref_raw) if decision_ref_raw else None
    unresolved = tuple(json.loads(str(row[8]) or "[]"))
    return DecisionLogAuditLineageChain(
        decision_id=str(row[0]),
        platform_run_id=str(row[1]),
        scenario_run_id=str(row[2]),
        decision_event_id=str(row[3]) if row[3] not in (None, "") else None,
        decision_payload_hash=str(row[4]) if row[4] not in (None, "") else None,
        decision_ref=decision_ref,
        intent_count=int(row[6]),
        outcome_count=int(row[7]),
        unresolved_reasons=unresolved,
        chain_status=str(row[9]),
        created_at_utc=str(row[10]),
        updated_at_utc=str(row[11]),
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


def _quarantine_record_id(
    *,
    source_topic: str,
    source_partition: int,
    source_offset: str,
    source_offset_kind: str,
    reason_code: str,
    event_id: str,
) -> str:
    digest = hashlib.sha256(
        f"{source_topic}|{source_partition}|{source_offset}|{source_offset_kind}|{reason_code}|{event_id}".encode("utf-8")
    ).hexdigest()
    return digest[:32]


def _intake_attempt_id(
    *,
    stream_id: str,
    topic: str,
    partition: int,
    offset: str,
    offset_kind: str,
    reason_code: str,
    event_id: str,
    created_at_utc: str,
) -> str:
    digest = hashlib.sha256(
        f"{stream_id}|{topic}|{partition}|{offset}|{offset_kind}|{reason_code}|{event_id}|{created_at_utc}".encode("utf-8")
    ).hexdigest()
    return digest[:32]


def _next_offset_value(*, offset: str, offset_kind: str) -> str:
    if offset_kind in {"file_line", "kafka_offset"}:
        return str(int(offset) + 1)
    if offset_kind == "kinesis_sequence":
        return str(offset)
    raise DecisionLogAuditIndexStoreError(f"unsupported offset_kind: {offset_kind!r}")


def _offset_after(*, new_offset: str, current_offset: str, offset_kind: str) -> bool:
    if offset_kind in {"file_line", "kafka_offset"}:
        return int(new_offset) > int(current_offset)
    if offset_kind == "kinesis_sequence":
        try:
            return int(new_offset) > int(current_offset)
        except ValueError:
            return str(new_offset) > str(current_offset)
    return str(new_offset) > str(current_offset)


def _max_timestamp(left: str | None, right: str | None) -> str | None:
    if left in (None, ""):
        return right
    if right in (None, ""):
        return left
    return right if str(right) > str(left) else left


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


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
