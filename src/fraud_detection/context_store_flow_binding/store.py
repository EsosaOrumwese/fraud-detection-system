"""Context Store + FlowBinding durable store (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable, Mapping, TypeVar

import psycopg
import yaml

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .contracts import FlowBindingRecord, JoinFrameKey
from .migrations import apply_postgres_migrations, apply_sqlite_migrations


HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
T = TypeVar("T")


class ContextStoreFlowBindingStoreError(RuntimeError):
    """Raised when CSFB storage operations fail."""


class ContextStoreFlowBindingConflictError(ContextStoreFlowBindingStoreError):
    """Raised when idempotent keys collide with mismatched hashes."""


@dataclass(frozen=True)
class CsfbCheckpoint:
    topic: str
    partition_id: int
    next_offset: str
    offset_kind: str
    watermark_ts_utc: str | None
    updated_at_utc: str


@dataclass(frozen=True)
class CsfbApplyResult:
    status: str
    checkpoint_status: str


@dataclass(frozen=True)
class CsfbIntakeApplyResult:
    dedupe_status: str
    join_frame_status: str
    flow_binding_status: str
    checkpoint_status: str


@dataclass(frozen=True)
class CsfbRetentionProfile:
    profile: str
    join_frame_days: int | None
    flow_binding_days: int | None
    apply_failure_days: int | None
    checkpoint_days: int | None


@dataclass(frozen=True)
class CsfbJoinFrameRecord:
    join_frame_key: JoinFrameKey
    payload_hash: str
    frame_payload: dict[str, Any]
    source_event: dict[str, Any]


class ContextStoreFlowBindingStore:
    def __init__(self, *, locator: str | Path, stream_id: str) -> None:
        self.locator = str(locator)
        self.stream_id = _non_empty(stream_id, "stream_id")
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(self.locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if self.backend == "sqlite":
                apply_sqlite_migrations(conn)
            else:
                apply_postgres_migrations(conn)

    def upsert_join_frame(
        self,
        *,
        join_frame_key: JoinFrameKey,
        payload_hash: str,
        frame_payload: Mapping[str, Any],
        source_event: Mapping[str, Any],
    ) -> str:
        _validate_hash(payload_hash, "payload_hash")
        source = _normalize_source_event(source_event)

        def work(conn: Any) -> str:
            row = self._execute(
                conn,
                """
                SELECT payload_hash FROM csfb_join_frames
                WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ?
                  AND merchant_id = ? AND arrival_seq = ?
                """,
                (
                    self.stream_id,
                    join_frame_key.platform_run_id,
                    join_frame_key.scenario_run_id,
                    join_frame_key.merchant_id,
                    join_frame_key.arrival_seq,
                ),
            ).fetchone()
            if row is not None:
                if str(row[0]) == payload_hash:
                    return "noop"
                raise ContextStoreFlowBindingConflictError("JOIN_FRAME_PAYLOAD_HASH_MISMATCH")

            self._execute(
                conn,
                """
                INSERT INTO csfb_join_frames (
                    stream_id, platform_run_id, scenario_run_id, merchant_id, arrival_seq, run_id,
                    payload_hash, frame_payload_json, source_event_json,
                    source_event_id, source_event_type, source_topic, source_partition,
                    source_offset, source_offset_kind, source_ts_utc, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    self.stream_id,
                    join_frame_key.platform_run_id,
                    join_frame_key.scenario_run_id,
                    join_frame_key.merchant_id,
                    join_frame_key.arrival_seq,
                    join_frame_key.run_id,
                    payload_hash,
                    _canonical_json(frame_payload),
                    _canonical_json(source),
                    source["event_id"],
                    source["event_type"],
                    source["eb_ref"]["topic"],
                    source["eb_ref"]["partition"],
                    source["eb_ref"]["offset"],
                    source["eb_ref"]["offset_kind"],
                    source["ts_utc"],
                ),
            )
            return "inserted"

        return self._run_in_tx(work)

    def upsert_flow_binding(self, *, record: FlowBindingRecord) -> str:
        _validate_hash(record.payload_hash, "flow_binding.payload_hash")
        _ensure_record_matches_join_key(record)
        key = record.join_frame_key

        def work(conn: Any) -> str:
            row = self._execute(
                conn,
                """
                SELECT payload_hash FROM csfb_flow_bindings
                WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ? AND flow_id = ?
                """,
                (self.stream_id, key.platform_run_id, key.scenario_run_id, record.flow_id),
            ).fetchone()
            if row is not None:
                if str(row[0]) == record.payload_hash:
                    return "noop"
                raise ContextStoreFlowBindingConflictError("FLOW_BINDING_PAYLOAD_HASH_MISMATCH")

            try:
                self._execute(
                    conn,
                    """
                    INSERT INTO csfb_flow_bindings (
                        stream_id, platform_run_id, scenario_run_id, flow_id,
                        merchant_id, arrival_seq, run_id, authoritative_source_event_type,
                        payload_hash, binding_payload_json, source_event_json,
                        source_event_id, source_event_type, source_topic, source_partition,
                        source_offset, source_offset_kind, source_ts_utc, bound_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        self.stream_id,
                        key.platform_run_id,
                        key.scenario_run_id,
                        record.flow_id,
                        key.merchant_id,
                        key.arrival_seq,
                        key.run_id,
                        record.authoritative_source_event_type,
                        record.payload_hash,
                        _canonical_json(record.as_dict()),
                        _canonical_json(record.source_event),
                        record.source_event["event_id"],
                        record.source_event["event_type"],
                        record.source_event["eb_ref"]["topic"],
                        int(record.source_event["eb_ref"]["partition"]),
                        str(record.source_event["eb_ref"]["offset"]),
                        str(record.source_event["eb_ref"]["offset_kind"]),
                        record.source_event["ts_utc"],
                        record.bound_at_utc,
                    ),
                )
            except Exception as exc:
                if self.backend == "sqlite" and isinstance(exc, sqlite3.IntegrityError):
                    raise ContextStoreFlowBindingConflictError("FLOW_BINDING_JOIN_KEY_CONFLICT") from exc
                if self.backend == "postgres" and getattr(exc, "sqlstate", "") == "23505":
                    raise ContextStoreFlowBindingConflictError("FLOW_BINDING_JOIN_KEY_CONFLICT") from exc
                raise
            return "inserted"

        return self._run_in_tx(work)

    def apply_flow_binding_and_checkpoint(
        self,
        *,
        record: FlowBindingRecord,
        topic: str,
        partition_id: int,
        next_offset: str,
        offset_kind: str,
        watermark_ts_utc: str | None,
    ) -> CsfbApplyResult:
        # Keep apply + checkpoint in one transaction to prevent checkpoint drift on failure.
        def work_single_tx(conn: Any) -> CsfbApplyResult:
            status = self._upsert_flow_binding_in_tx(conn=conn, record=record)
            checkpoint_status = self._advance_checkpoint_conn(
                conn,
                topic=topic,
                partition_id=partition_id,
                next_offset=next_offset,
                offset_kind=offset_kind,
                watermark_ts_utc=watermark_ts_utc,
            )
            return CsfbApplyResult(status=status, checkpoint_status=checkpoint_status)

        return self._run_in_tx(work_single_tx)

    def apply_join_frame_and_checkpoint(
        self,
        *,
        join_frame_key: JoinFrameKey,
        frame_state: Mapping[str, Any],
        source_event: Mapping[str, Any],
        topic: str,
        partition_id: int,
        next_offset: str,
        offset_kind: str,
        watermark_ts_utc: str | None,
    ) -> CsfbApplyResult:
        frame_hash = hashlib.sha256(_canonical_json(frame_state).encode("utf-8")).hexdigest()

        def work_single_tx(conn: Any) -> CsfbApplyResult:
            status = self._upsert_join_frame_state_in_tx(
                conn=conn,
                join_frame_key=join_frame_key,
                frame_state=frame_state,
                frame_hash=frame_hash,
                source_event=source_event,
            )
            checkpoint_status = self._advance_checkpoint_conn(
                conn,
                topic=topic,
                partition_id=partition_id,
                next_offset=next_offset,
                offset_kind=offset_kind,
                watermark_ts_utc=watermark_ts_utc,
            )
            return CsfbApplyResult(status=status, checkpoint_status=checkpoint_status)

        return self._run_in_tx(work_single_tx)

    def apply_context_event_and_checkpoint(
        self,
        *,
        platform_run_id: str,
        event_class: str,
        event_id: str,
        payload_hash: str,
        join_frame_key: JoinFrameKey,
        frame_state: Mapping[str, Any],
        source_event: Mapping[str, Any],
        topic: str,
        partition_id: int,
        event_offset: str,
        next_offset: str,
        offset_kind: str,
        watermark_ts_utc: str | None,
        flow_binding_record: FlowBindingRecord | None = None,
    ) -> CsfbIntakeApplyResult:
        frame_hash = hashlib.sha256(_canonical_json(frame_state).encode("utf-8")).hexdigest()

        def work_single_tx(conn: Any) -> CsfbIntakeApplyResult:
            dedupe_status = self._register_intake_event_in_tx(
                conn=conn,
                platform_run_id=platform_run_id,
                event_class=event_class,
                event_id=event_id,
                payload_hash=payload_hash,
                topic=topic,
                partition_id=partition_id,
                offset=event_offset,
                offset_kind=offset_kind,
                event_ts_utc=watermark_ts_utc,
            )
            if dedupe_status == "duplicate":
                checkpoint_status = self._advance_checkpoint_conn(
                    conn,
                    topic=topic,
                    partition_id=partition_id,
                    next_offset=next_offset,
                    offset_kind=offset_kind,
                    watermark_ts_utc=watermark_ts_utc,
                )
                return CsfbIntakeApplyResult(
                    dedupe_status=dedupe_status,
                    join_frame_status="noop",
                    flow_binding_status="noop",
                    checkpoint_status=checkpoint_status,
                )

            join_frame_status = self._upsert_join_frame_state_in_tx(
                conn=conn,
                join_frame_key=join_frame_key,
                frame_state=frame_state,
                frame_hash=frame_hash,
                source_event=source_event,
            )
            flow_binding_status = "noop"
            if flow_binding_record is not None:
                flow_binding_status = self._upsert_flow_binding_in_tx(conn=conn, record=flow_binding_record)
            checkpoint_status = self._advance_checkpoint_conn(
                conn,
                topic=topic,
                partition_id=partition_id,
                next_offset=next_offset,
                offset_kind=offset_kind,
                watermark_ts_utc=watermark_ts_utc,
            )
            return CsfbIntakeApplyResult(
                dedupe_status=dedupe_status,
                join_frame_status=join_frame_status,
                flow_binding_status=flow_binding_status,
                checkpoint_status=checkpoint_status,
            )

        return self._run_in_tx(work_single_tx)

    def advance_checkpoint(
        self,
        *,
        topic: str,
        partition_id: int,
        next_offset: str,
        offset_kind: str,
        watermark_ts_utc: str | None,
    ) -> str:
        def work(conn: Any) -> str:
            return self._advance_checkpoint_conn(
                conn,
                topic=topic,
                partition_id=partition_id,
                next_offset=next_offset,
                offset_kind=offset_kind,
                watermark_ts_utc=watermark_ts_utc,
            )

        return self._run_in_tx(work)

    def register_intake_event(
        self,
        *,
        platform_run_id: str,
        event_class: str,
        event_id: str,
        payload_hash: str,
        topic: str,
        partition_id: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> str:
        def work(conn: Any) -> str:
            return self._register_intake_event_in_tx(
                conn=conn,
                platform_run_id=platform_run_id,
                event_class=event_class,
                event_id=event_id,
                payload_hash=payload_hash,
                topic=topic,
                partition_id=partition_id,
                offset=offset,
                offset_kind=offset_kind,
                event_ts_utc=event_ts_utc,
            )

        return self._run_in_tx(work)

    def read_join_frame_state(self, *, join_frame_key: JoinFrameKey) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = self._execute(
                conn,
                """
                SELECT frame_payload_json
                FROM csfb_join_frames
                WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ?
                  AND merchant_id = ? AND arrival_seq = ?
                """,
                (
                    self.stream_id,
                    join_frame_key.platform_run_id,
                    join_frame_key.scenario_run_id,
                    join_frame_key.merchant_id,
                    join_frame_key.arrival_seq,
                ),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row[0]))
        except json.JSONDecodeError as exc:
            raise ContextStoreFlowBindingStoreError("join frame state row is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ContextStoreFlowBindingStoreError("join frame state row must decode to object")
        return payload

    def read_join_frame_record(self, *, join_frame_key: JoinFrameKey) -> CsfbJoinFrameRecord | None:
        with self._connect() as conn:
            row = self._execute(
                conn,
                """
                SELECT payload_hash, frame_payload_json, source_event_json
                FROM csfb_join_frames
                WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ?
                  AND merchant_id = ? AND arrival_seq = ?
                """,
                (
                    self.stream_id,
                    join_frame_key.platform_run_id,
                    join_frame_key.scenario_run_id,
                    join_frame_key.merchant_id,
                    join_frame_key.arrival_seq,
                ),
            ).fetchone()
        if row is None:
            return None
        payload_hash = str(row[0])
        frame_payload = _load_json_object(row[1], "join frame payload")
        source_event = _load_json_object(row[2], "join frame source_event")
        return CsfbJoinFrameRecord(
            join_frame_key=join_frame_key,
            payload_hash=payload_hash,
            frame_payload=frame_payload,
            source_event=source_event,
        )

    def read_flow_binding(
        self,
        *,
        platform_run_id: str,
        scenario_run_id: str,
        flow_id: str,
    ) -> FlowBindingRecord | None:
        with self._connect() as conn:
            row = self._execute(
                conn,
                """
                SELECT binding_payload_json
                FROM csfb_flow_bindings
                WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ? AND flow_id = ?
                """,
                (
                    self.stream_id,
                    _non_empty(platform_run_id, "platform_run_id"),
                    _non_empty(scenario_run_id, "scenario_run_id"),
                    _non_empty(flow_id, "flow_id"),
                ),
            ).fetchone()
        if row is None:
            return None
        payload = _load_json_object(row[0], "flow binding payload")
        return FlowBindingRecord.from_mapping(payload)

    def read_flow_binding_for_join_frame(self, *, join_frame_key: JoinFrameKey) -> FlowBindingRecord | None:
        with self._connect() as conn:
            row = self._execute(
                conn,
                """
                SELECT binding_payload_json
                FROM csfb_flow_bindings
                WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ?
                  AND merchant_id = ? AND arrival_seq = ?
                """,
                (
                    self.stream_id,
                    join_frame_key.platform_run_id,
                    join_frame_key.scenario_run_id,
                    join_frame_key.merchant_id,
                    join_frame_key.arrival_seq,
                ),
            ).fetchone()
        if row is None:
            return None
        payload = _load_json_object(row[0], "flow binding payload")
        return FlowBindingRecord.from_mapping(payload)

    def get_checkpoint(self, *, topic: str, partition_id: int) -> CsfbCheckpoint | None:
        with self._connect() as conn:
            row = self._execute(
                conn,
                """
                SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc
                FROM csfb_join_checkpoints
                WHERE stream_id = ? AND topic = ? AND partition_id = ?
                """,
                (self.stream_id, topic, int(partition_id)),
            ).fetchone()
        if row is None:
            return None
        return CsfbCheckpoint(
            topic=str(row[0]),
            partition_id=int(row[1]),
            next_offset=str(row[2]),
            offset_kind=str(row[3]),
            watermark_ts_utc=None if row[4] in (None, "") else str(row[4]),
            updated_at_utc=str(row[5]),
        )

    def checkpoints(self) -> list[CsfbCheckpoint]:
        with self._connect() as conn:
            rows = self._execute(
                conn,
                """
                SELECT topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc
                FROM csfb_join_checkpoints
                WHERE stream_id = ?
                ORDER BY topic ASC, partition_id ASC
                """,
                (self.stream_id,),
            ).fetchall()
        checkpoints: list[CsfbCheckpoint] = []
        for row in rows:
            checkpoints.append(
                CsfbCheckpoint(
                    topic=str(row[0]),
                    partition_id=int(row[1]),
                    next_offset=str(row[2]),
                    offset_kind=str(row[3]),
                    watermark_ts_utc=None if row[4] in (None, "") else str(row[4]),
                    updated_at_utc=str(row[5]),
                )
            )
        return checkpoints

    def checkpoint_summary(self) -> dict[str, Any]:
        checkpoints = self.checkpoints()
        if not checkpoints:
            return {
                "stream_id": self.stream_id,
                "partitions": [],
                "watermark_ts_utc": None,
                "updated_at_utc": None,
            }
        watermark = max((item.watermark_ts_utc for item in checkpoints if item.watermark_ts_utc), default=None)
        updated = max((item.updated_at_utc for item in checkpoints if item.updated_at_utc), default=None)
        return {
            "stream_id": self.stream_id,
            "partitions": [
                {
                    "topic": item.topic,
                    "partition": item.partition_id,
                    "next_offset": item.next_offset,
                    "offset_kind": item.offset_kind,
                    "watermark_ts_utc": item.watermark_ts_utc,
                    "updated_at_utc": item.updated_at_utc,
                }
                for item in checkpoints
            ],
            "watermark_ts_utc": watermark,
            "updated_at_utc": updated,
        }

    def input_basis(self) -> dict[str, Any] | None:
        checkpoints = self.checkpoints()
        if not checkpoints:
            return None
        topics: dict[str, Any] = {}
        watermark = None
        for item in checkpoints:
            topic_entry = topics.setdefault(item.topic, {"partitions": {}})
            topic_entry["partitions"][str(item.partition_id)] = {
                "next_offset": item.next_offset,
                "offset_kind": item.offset_kind,
            }
            if item.watermark_ts_utc and (watermark is None or item.watermark_ts_utc > watermark):
                watermark = item.watermark_ts_utc
        basis = {"stream_id": self.stream_id, "topics": topics}
        digest = hashlib.sha256(_canonical_json(basis).encode("utf-8")).hexdigest()
        payload: dict[str, Any] = {
            "stream_id": self.stream_id,
            "topics": topics,
            "basis_digest": digest,
        }
        if watermark:
            payload["window_end_utc"] = watermark
        return payload

    def metrics_snapshot(
        self,
        *,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
    ) -> dict[str, int]:
        join_hits_sql = """
            SELECT COUNT(*)
            FROM csfb_flow_bindings fb
            JOIN csfb_join_frames jf
              ON jf.stream_id = fb.stream_id
             AND jf.platform_run_id = fb.platform_run_id
             AND jf.scenario_run_id = fb.scenario_run_id
             AND jf.merchant_id = fb.merchant_id
             AND jf.arrival_seq = fb.arrival_seq
            WHERE fb.stream_id = ?
        """
        join_miss_sql = """
            SELECT COUNT(*)
            FROM csfb_flow_bindings fb
            LEFT JOIN csfb_join_frames jf
              ON jf.stream_id = fb.stream_id
             AND jf.platform_run_id = fb.platform_run_id
             AND jf.scenario_run_id = fb.scenario_run_id
             AND jf.merchant_id = fb.merchant_id
             AND jf.arrival_seq = fb.arrival_seq
            WHERE fb.stream_id = ? AND jf.stream_id IS NULL
        """
        failure_sql = """
            SELECT COUNT(*)
            FROM csfb_join_apply_failures
            WHERE stream_id = ?
        """
        conflict_sql = """
            SELECT COUNT(*)
            FROM csfb_join_apply_failures
            WHERE stream_id = ? AND reason_code LIKE 'FLOW_BINDING_%'
        """
        fb_scope, fb_params = _scope_suffix(
            table_alias="fb",
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
        )
        failure_scope, failure_params = _scope_suffix(
            table_alias="",
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
        )
        with self._connect() as conn:
            join_hits = int(
                self._execute(conn, join_hits_sql + fb_scope, (self.stream_id, *fb_params)).fetchone()[0]
            )
            join_misses = int(
                self._execute(conn, join_miss_sql + fb_scope, (self.stream_id, *fb_params)).fetchone()[0]
            )
            apply_failures = int(
                self._execute(conn, failure_sql + failure_scope, (self.stream_id, *failure_params)).fetchone()[0]
            )
            binding_conflicts = int(
                self._execute(conn, conflict_sql + failure_scope, (self.stream_id, *failure_params)).fetchone()[0]
            )
        return {
            "join_hits": join_hits,
            "join_misses": join_misses,
            "binding_conflicts": binding_conflicts,
            "apply_failures": apply_failures,
        }

    def unresolved_anomalies(
        self,
        *,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        scope_suffix, scope_params = _scope_suffix(
            table_alias="",
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
        )
        query = (
            """
            SELECT failure_id, platform_run_id, scenario_run_id, topic, partition_id,
                   offset, offset_kind, event_id, event_type, reason_code, details_json, recorded_at_utc
            FROM csfb_join_apply_failures
            WHERE stream_id = ?
            """
            + scope_suffix
            + " ORDER BY recorded_at_utc DESC LIMIT ?"
        )
        with self._connect() as conn:
            rows = self._execute(conn, query, (self.stream_id, *scope_params, int(max(1, limit)))).fetchall()
        payload: list[dict[str, Any]] = []
        for row in rows:
            details = _load_json_object(row[10], "apply_failure.details_json") if row[10] not in (None, "") else {}
            payload.append(
                {
                    "failure_id": str(row[0]),
                    "platform_run_id": None if row[1] in (None, "") else str(row[1]),
                    "scenario_run_id": None if row[2] in (None, "") else str(row[2]),
                    "topic": None if row[3] in (None, "") else str(row[3]),
                    "partition_id": None if row[4] is None else int(row[4]),
                    "offset": None if row[5] in (None, "") else str(row[5]),
                    "offset_kind": None if row[6] in (None, "") else str(row[6]),
                    "event_id": None if row[7] in (None, "") else str(row[7]),
                    "event_type": None if row[8] in (None, "") else str(row[8]),
                    "reason_code": str(row[9]),
                    "details": details,
                    "recorded_at_utc": str(row[11]),
                }
            )
        return payload

    def record_apply_failure(
        self,
        *,
        reason_code: str,
        details: Mapping[str, Any],
        platform_run_id: str | None,
        scenario_run_id: str | None,
        topic: str | None,
        partition_id: int | None,
        offset: str | None,
        offset_kind: str | None,
        event_id: str | None,
        event_type: str | None,
    ) -> str:
        failure_id = hashlib.sha256(
            f"{self.stream_id}:{platform_run_id}:{scenario_run_id}:{topic}:{partition_id}:{offset}:{event_id}:{reason_code}:{_canonical_json(details)}".encode(
                "utf-8"
            )
        ).hexdigest()[:32]

        def work(conn: Any) -> str:
            self._execute(
                conn,
                """
                INSERT INTO csfb_join_apply_failures (
                    failure_id, stream_id, platform_run_id, scenario_run_id,
                    topic, partition_id, offset, offset_kind, event_id, event_type,
                    reason_code, details_json, recorded_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    failure_id,
                    self.stream_id,
                    platform_run_id,
                    scenario_run_id,
                    topic,
                    partition_id,
                    offset,
                    offset_kind,
                    event_id,
                    event_type,
                    _non_empty(reason_code, "reason_code"),
                    _canonical_json(details),
                ),
            )
            return failure_id

        return self._run_in_tx(work)

    def _upsert_flow_binding_in_tx(self, *, conn: Any, record: FlowBindingRecord) -> str:
        _validate_hash(record.payload_hash, "flow_binding.payload_hash")
        _ensure_record_matches_join_key(record)
        key = record.join_frame_key
        row = self._execute(
            conn,
            """
            SELECT payload_hash FROM csfb_flow_bindings
            WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ? AND flow_id = ?
            """,
            (self.stream_id, key.platform_run_id, key.scenario_run_id, record.flow_id),
        ).fetchone()
        if row is not None:
            if str(row[0]) == record.payload_hash:
                return "noop"
            raise ContextStoreFlowBindingConflictError("FLOW_BINDING_PAYLOAD_HASH_MISMATCH")

        self._execute(
            conn,
            """
            INSERT INTO csfb_flow_bindings (
                stream_id, platform_run_id, scenario_run_id, flow_id,
                merchant_id, arrival_seq, run_id, authoritative_source_event_type,
                payload_hash, binding_payload_json, source_event_json,
                source_event_id, source_event_type, source_topic, source_partition,
                source_offset, source_offset_kind, source_ts_utc, bound_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                self.stream_id,
                key.platform_run_id,
                key.scenario_run_id,
                record.flow_id,
                key.merchant_id,
                key.arrival_seq,
                key.run_id,
                record.authoritative_source_event_type,
                record.payload_hash,
                _canonical_json(record.as_dict()),
                _canonical_json(record.source_event),
                record.source_event["event_id"],
                record.source_event["event_type"],
                record.source_event["eb_ref"]["topic"],
                int(record.source_event["eb_ref"]["partition"]),
                str(record.source_event["eb_ref"]["offset"]),
                str(record.source_event["eb_ref"]["offset_kind"]),
                record.source_event["ts_utc"],
                record.bound_at_utc,
            ),
        )
        return "inserted"

    def _upsert_join_frame_state_in_tx(
        self,
        *,
        conn: Any,
        join_frame_key: JoinFrameKey,
        frame_state: Mapping[str, Any],
        frame_hash: str,
        source_event: Mapping[str, Any],
    ) -> str:
        source = _normalize_source_event(source_event)
        row = self._execute(
            conn,
            """
            SELECT payload_hash
            FROM csfb_join_frames
            WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ?
              AND merchant_id = ? AND arrival_seq = ?
            """,
            (
                self.stream_id,
                join_frame_key.platform_run_id,
                join_frame_key.scenario_run_id,
                join_frame_key.merchant_id,
                join_frame_key.arrival_seq,
            ),
        ).fetchone()
        if row is None:
            self._execute(
                conn,
                """
                INSERT INTO csfb_join_frames (
                    stream_id, platform_run_id, scenario_run_id, merchant_id, arrival_seq, run_id,
                    payload_hash, frame_payload_json, source_event_json,
                    source_event_id, source_event_type, source_topic, source_partition,
                    source_offset, source_offset_kind, source_ts_utc, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    self.stream_id,
                    join_frame_key.platform_run_id,
                    join_frame_key.scenario_run_id,
                    join_frame_key.merchant_id,
                    join_frame_key.arrival_seq,
                    join_frame_key.run_id,
                    frame_hash,
                    _canonical_json(frame_state),
                    _canonical_json(source),
                    source["event_id"],
                    source["event_type"],
                    source["eb_ref"]["topic"],
                    source["eb_ref"]["partition"],
                    source["eb_ref"]["offset"],
                    source["eb_ref"]["offset_kind"],
                    source["ts_utc"],
                ),
            )
            return "inserted"
        if str(row[0]) == frame_hash:
            return "noop"
        self._execute(
            conn,
            """
            UPDATE csfb_join_frames
            SET payload_hash = ?, frame_payload_json = ?, source_event_json = ?,
                source_event_id = ?, source_event_type = ?, source_topic = ?, source_partition = ?,
                source_offset = ?, source_offset_kind = ?, source_ts_utc = ?, updated_at_utc = CURRENT_TIMESTAMP
            WHERE stream_id = ? AND platform_run_id = ? AND scenario_run_id = ?
              AND merchant_id = ? AND arrival_seq = ?
            """,
            (
                frame_hash,
                _canonical_json(frame_state),
                _canonical_json(source),
                source["event_id"],
                source["event_type"],
                source["eb_ref"]["topic"],
                source["eb_ref"]["partition"],
                source["eb_ref"]["offset"],
                source["eb_ref"]["offset_kind"],
                source["ts_utc"],
                self.stream_id,
                join_frame_key.platform_run_id,
                join_frame_key.scenario_run_id,
                join_frame_key.merchant_id,
                join_frame_key.arrival_seq,
            ),
        )
        return "updated"

    def _register_intake_event_in_tx(
        self,
        *,
        conn: Any,
        platform_run_id: str,
        event_class: str,
        event_id: str,
        payload_hash: str,
        topic: str,
        partition_id: int,
        offset: str,
        offset_kind: str,
        event_ts_utc: str | None,
    ) -> str:
        _validate_hash(payload_hash, "payload_hash")
        row = self._execute(
            conn,
            """
            SELECT payload_hash
            FROM csfb_intake_dedupe
            WHERE stream_id = ? AND platform_run_id = ? AND event_class = ? AND event_id = ?
            """,
            (
                self.stream_id,
                _non_empty(platform_run_id, "platform_run_id"),
                _non_empty(event_class, "event_class"),
                _non_empty(event_id, "event_id"),
            ),
        ).fetchone()
        if row is None:
            self._execute(
                conn,
                """
                INSERT INTO csfb_intake_dedupe (
                    stream_id, platform_run_id, event_class, event_id, payload_hash,
                    first_topic, first_partition, first_offset, offset_kind, first_seen_ts_utc, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    self.stream_id,
                    platform_run_id,
                    event_class,
                    event_id,
                    payload_hash,
                    _non_empty(topic, "topic"),
                    int(partition_id),
                    _non_empty(offset, "offset"),
                    _non_empty(offset_kind, "offset_kind"),
                    event_ts_utc,
                ),
            )
            return "inserted"
        if str(row[0]) == payload_hash:
            return "duplicate"
        raise ContextStoreFlowBindingConflictError("INTAKE_PAYLOAD_HASH_MISMATCH")

    def _advance_checkpoint_conn(
        self,
        conn: Any,
        *,
        topic: str,
        partition_id: int,
        next_offset: str,
        offset_kind: str,
        watermark_ts_utc: str | None,
    ) -> str:
        normalized_topic = _non_empty(topic, "topic")
        normalized_offset = _non_empty(next_offset, "next_offset")
        normalized_kind = _non_empty(offset_kind, "offset_kind")
        partition = int(partition_id)
        if partition < 0:
            raise ContextStoreFlowBindingStoreError("partition_id must be >= 0")

        row = self._execute(
            conn,
            """
            SELECT next_offset, offset_kind, watermark_ts_utc
            FROM csfb_join_checkpoints
            WHERE stream_id = ? AND topic = ? AND partition_id = ?
            """,
            (self.stream_id, normalized_topic, partition),
        ).fetchone()

        if row is None:
            self._execute(
                conn,
                """
                INSERT INTO csfb_join_checkpoints (
                    stream_id, topic, partition_id, next_offset, offset_kind, watermark_ts_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (self.stream_id, normalized_topic, partition, normalized_offset, normalized_kind, watermark_ts_utc),
            )
            return "inserted"

        current_offset = str(row[0])
        current_kind = str(row[1])
        current_watermark = None if row[2] in (None, "") else str(row[2])
        if current_kind != normalized_kind:
            raise ContextStoreFlowBindingStoreError(
                f"offset_kind mismatch for checkpoint: {current_kind!r} vs {normalized_kind!r}"
            )

        advanced = _offset_after(normalized_offset, current_offset, normalized_kind)
        final_offset = normalized_offset if advanced else current_offset
        final_watermark = _max_ts(current_watermark, watermark_ts_utc)
        self._execute(
            conn,
            """
            UPDATE csfb_join_checkpoints
            SET next_offset = ?, watermark_ts_utc = ?, updated_at_utc = CURRENT_TIMESTAMP
            WHERE stream_id = ? AND topic = ? AND partition_id = ?
            """,
            (final_offset, final_watermark, self.stream_id, normalized_topic, partition),
        )
        return "advanced" if advanced else "noop"

    def _run_in_tx(self, work: Callable[[Any], T]) -> T:
        with self._connect() as conn:
            if self.backend == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                return work(conn)
            with conn.transaction():
                return work(conn)

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            return sqlite3.connect(_sqlite_path(self.locator))
        return psycopg.connect(self.locator)

    def _execute(self, conn: Any, query: str, params: tuple[Any, ...]) -> Any:
        if self.backend == "postgres":
            query = query.replace("?", "%s")
        return conn.execute(query, params)


def build_store(locator: str | Path, *, stream_id: str) -> ContextStoreFlowBindingStore:
    return ContextStoreFlowBindingStore(locator=locator, stream_id=stream_id)


def load_retention_profile(path: Path, *, profile: str) -> CsfbRetentionProfile:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("retention"), dict):
        raise ContextStoreFlowBindingStoreError("retention policy must have mapping root 'retention'")
    profile_payload = payload["retention"].get(profile)
    if not isinstance(profile_payload, dict):
        raise ContextStoreFlowBindingStoreError(f"retention profile not found: {profile}")
    return CsfbRetentionProfile(
        profile=profile,
        join_frame_days=_parse_days(profile_payload.get("join_frame_days"), "join_frame_days"),
        flow_binding_days=_parse_days(profile_payload.get("flow_binding_days"), "flow_binding_days"),
        apply_failure_days=_parse_days(profile_payload.get("apply_failure_days"), "apply_failure_days"),
        checkpoint_days=_parse_days(profile_payload.get("checkpoint_days"), "checkpoint_days"),
    )


def _parse_days(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    parsed = int(value)
    if parsed < 0:
        raise ContextStoreFlowBindingStoreError(f"{field_name} must be >= 0")
    return parsed


def _normalize_source_event(source_event: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(source_event, Mapping):
        raise ContextStoreFlowBindingStoreError("source_event must be mapping")
    eb_ref = source_event.get("eb_ref")
    if not isinstance(eb_ref, Mapping):
        raise ContextStoreFlowBindingStoreError("source_event.eb_ref must be mapping")
    return {
        "event_id": _non_empty(source_event.get("event_id"), "source_event.event_id"),
        "event_type": _non_empty(source_event.get("event_type"), "source_event.event_type"),
        "ts_utc": _non_empty(source_event.get("ts_utc"), "source_event.ts_utc"),
        "eb_ref": {
            "topic": _non_empty(eb_ref.get("topic"), "source_event.eb_ref.topic"),
            "partition": int(eb_ref.get("partition")),
            "offset": _non_empty(eb_ref.get("offset"), "source_event.eb_ref.offset"),
            "offset_kind": _non_empty(eb_ref.get("offset_kind"), "source_event.eb_ref.offset_kind"),
        },
    }


def _ensure_record_matches_join_key(record: FlowBindingRecord) -> None:
    if record.pins.get("platform_run_id") != record.join_frame_key.platform_run_id:
        raise ContextStoreFlowBindingStoreError("platform_run_id mismatch between pins and join_frame_key")
    if record.pins.get("scenario_run_id") != record.join_frame_key.scenario_run_id:
        raise ContextStoreFlowBindingStoreError("scenario_run_id mismatch between pins and join_frame_key")


def _validate_hash(value: str, field_name: str) -> None:
    if not HEX64_RE.fullmatch(str(value or "")):
        raise ContextStoreFlowBindingStoreError(f"{field_name} must be 64-char lowercase hex")


def _offset_after(left: str, right: str, offset_kind: str) -> bool:
    if offset_kind in {"file_line", "kafka_offset"}:
        try:
            return int(left) > int(right)
        except ValueError:
            return left > right
    return left > right


def _max_ts(current: str | None, incoming: str | None) -> str | None:
    if not incoming:
        return current
    if not current:
        return incoming
    return incoming if incoming > current else current


def _canonical_json(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise ContextStoreFlowBindingStoreError("payload must be a mapping")
    return json.dumps(dict(payload), sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _load_json_object(value: Any, field_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ContextStoreFlowBindingStoreError(f"{field_name} row is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ContextStoreFlowBindingStoreError(f"{field_name} row must decode to object")
    return payload


def _scope_suffix(
    *,
    table_alias: str,
    platform_run_id: str | None,
    scenario_run_id: str | None,
) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    params: list[Any] = []
    prefix = f"{table_alias}." if table_alias else ""
    if platform_run_id not in (None, ""):
        clauses.append(f"{prefix}platform_run_id = ?")
        params.append(str(platform_run_id))
    if scenario_run_id not in (None, ""):
        clauses.append(f"{prefix}scenario_run_id = ?")
        params.append(str(scenario_run_id))
    if not clauses:
        return "", ()
    return " AND " + " AND ".join(clauses), tuple(params)


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ContextStoreFlowBindingStoreError(f"{field_name} must be non-empty")
    return text


def _sqlite_path(locator: str) -> str:
    value = str(locator or "").strip()
    if not value:
        raise ContextStoreFlowBindingStoreError("sqlite store locator must be non-empty")
    if value.startswith("sqlite:///"):
        return value[len("sqlite:///") :]
    if value.startswith("sqlite://"):
        return value[len("sqlite://") :]
    return value
