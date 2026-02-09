"""CM -> Label Store handshake coordinator (Phase 5)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Protocol

import psycopg
import yaml

from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn
from fraud_detection.label_store import LabelAssertion

from .intake import CaseTriggerIntakeLedger, SOURCE_TYPE_SYSTEM


LS_WRITE_ACCEPTED = "ACCEPTED"
LS_WRITE_REJECTED = "REJECTED"
LS_WRITE_PENDING = "PENDING"

EMISSION_PENDING = "PENDING"
EMISSION_ACCEPTED = "ACCEPTED"
EMISSION_REJECTED = "REJECTED"
TERMINAL_EMISSION_STATUSES: frozenset[str] = frozenset({EMISSION_ACCEPTED, EMISSION_REJECTED})

EMISSION_NEW = "NEW"
EMISSION_DUPLICATE = "DUPLICATE"
EMISSION_PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"


class CaseLabelHandshakeError(RuntimeError):
    """Raised when CM label handshake operations are invalid."""


@dataclass(frozen=True)
class LabelEmissionPolicy:
    version: str
    policy_id: str
    revision: str
    allowed_label_types: tuple[str, ...]
    allowed_actor_prefixes: tuple[str, ...]
    allowed_source_types: tuple[str, ...]
    max_retry_attempts: int
    content_digest: str


@dataclass(frozen=True)
class LabelStoreWriteResult:
    status: str
    reason_code: str | None = None
    assertion_ref: str | None = None


class LabelStoreWriter(Protocol):
    def write_label_assertion(self, assertion_payload: Mapping[str, Any]) -> LabelStoreWriteResult:
        ...


@dataclass(frozen=True)
class LabelEmissionRecord:
    label_assertion_id: str
    case_id: str
    source_case_event_id: str
    status: str
    payload_hash: str
    attempt_count: int
    first_requested_at_utc: str
    last_attempted_at_utc: str
    last_reason_code: str | None
    assertion_ref: str | None


@dataclass(frozen=True)
class LabelEmissionResult:
    disposition: str
    label_assertion_id: str
    status: str
    attempt_count: int
    reason_code: str | None
    assertion_ref: str | None


@dataclass(frozen=True)
class _StoredAssertion:
    case_id: str
    source_case_event_id: str
    assertion: LabelAssertion


class CaseLabelHandshakeCoordinator:
    """Deterministic CM label handshake lane with retry-safe emission state."""

    def __init__(
        self,
        *,
        locator: str,
        intake_ledger: CaseTriggerIntakeLedger,
        policy: LabelEmissionPolicy,
        label_store_writer: LabelStoreWriter,
    ) -> None:
        self.locator = str(locator)
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(self.locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self.intake_ledger = intake_ledger
        self.policy = policy
        self.label_store_writer = label_store_writer

        if _normalize_locator(self.locator) != _normalize_locator(self.intake_ledger.locator):
            raise CaseLabelHandshakeError(
                "label handshake locator must match CaseTriggerIntakeLedger locator"
            )

        self._init_schema()

    def submit_label_assertion(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        label_subject_key: Mapping[str, Any],
        pins: Mapping[str, Any],
        label_type: str,
        label_value: str,
        effective_time: str,
        observed_time: str,
        source_type: str,
        actor_id: str | None,
        evidence_refs: list[Mapping[str, Any]],
        requested_at_utc: str,
        label_payload: Mapping[str, Any] | None = None,
    ) -> LabelEmissionResult:
        normalized_case_id = _require_non_empty(case_id, "case_id")
        normalized_source_event = _require_non_empty(source_case_event_id, "source_case_event_id")
        normalized_requested_at = _require_non_empty(requested_at_utc, "requested_at_utc")
        normalized_label_type = _require_non_empty(label_type, "label_type")
        normalized_source_type = _normalize_source_type(source_type)
        normalized_actor = _normalize_optional(actor_id)

        self._enforce_policy(
            label_type=normalized_label_type,
            actor_id=normalized_actor,
            source_type=normalized_source_type,
        )

        assertion = LabelAssertion.from_payload(
            {
                "case_timeline_event_id": normalized_source_event,
                "label_subject_key": dict(label_subject_key),
                "pins": dict(pins),
                "label_type": normalized_label_type,
                "label_value": str(label_value),
                "effective_time": str(effective_time),
                "observed_time": str(observed_time),
                "source_type": normalized_source_type,
                "actor_id": normalized_actor,
                "evidence_refs": [dict(item) for item in evidence_refs],
                "label_payload": dict(label_payload) if isinstance(label_payload, Mapping) else {},
            }
        )
        assertion_payload = assertion.as_dict()
        assertion_json = _canonical_json(assertion_payload)
        payload_hash = _hash_text(assertion_json)

        case_row = self.intake_ledger.lookup_case(normalized_case_id)
        if case_row is None:
            raise CaseLabelHandshakeError(f"unknown case_id: {normalized_case_id}")

        self._require_source_case_event(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
        )

        upsert = self._upsert_emission(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            assertion=assertion,
            assertion_json=assertion_json,
            payload_hash=payload_hash,
            requested_at_utc=normalized_requested_at,
        )
        if isinstance(upsert, LabelEmissionResult):
            return upsert

        disposition, stored = upsert

        pending_event_id = self._append_label_timeline_event(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            case_subject_key=case_row.case_subject_key,
            assertion=assertion,
            event_type="LABEL_PENDING",
            source_ref_id=f"label_assertion:{assertion.label_assertion_id}:pending",
            actor_id=normalized_actor,
            source_type=normalized_source_type,
            observed_time=assertion.observed_time,
            reason_code=None,
        )
        self._set_timeline_pointer(
            label_assertion_id=assertion.label_assertion_id,
            field_name="pending_timeline_event_id",
            event_id=pending_event_id,
        )

        if stored.status in TERMINAL_EMISSION_STATUSES:
            return LabelEmissionResult(
                disposition=EMISSION_DUPLICATE,
                label_assertion_id=stored.label_assertion_id,
                status=stored.status,
                attempt_count=stored.attempt_count,
                reason_code=stored.last_reason_code,
                assertion_ref=stored.assertion_ref,
            )

        return self._attempt_write(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            case_subject_key=case_row.case_subject_key,
            assertion=assertion,
            attempted_at_utc=normalized_requested_at,
            disposition=disposition,
        )

    def retry_pending(
        self,
        *,
        label_assertion_id: str,
        retried_at_utc: str,
    ) -> LabelEmissionResult:
        normalized_id = _require_non_empty(label_assertion_id, "label_assertion_id")
        normalized_retry_time = _require_non_empty(retried_at_utc, "retried_at_utc")

        current = self.lookup_emission(label_assertion_id=normalized_id)
        if current is None:
            raise CaseLabelHandshakeError(f"unknown label_assertion_id: {normalized_id}")

        if current.status in TERMINAL_EMISSION_STATUSES:
            return LabelEmissionResult(
                disposition=EMISSION_DUPLICATE,
                label_assertion_id=current.label_assertion_id,
                status=current.status,
                attempt_count=current.attempt_count,
                reason_code=current.last_reason_code,
                assertion_ref=current.assertion_ref,
            )

        stored = self._load_stored_assertion(label_assertion_id=normalized_id)
        case_row = self.intake_ledger.lookup_case(stored.case_id)
        if case_row is None:
            raise CaseLabelHandshakeError(f"unknown case_id for retry: {stored.case_id}")

        pending_event_id = self._append_label_timeline_event(
            case_id=stored.case_id,
            source_case_event_id=stored.source_case_event_id,
            case_subject_key=case_row.case_subject_key,
            assertion=stored.assertion,
            event_type="LABEL_PENDING",
            source_ref_id=f"label_assertion:{normalized_id}:pending",
            actor_id="SYSTEM::cm_label_handshake",
            source_type=SOURCE_TYPE_SYSTEM,
            observed_time=normalized_retry_time,
            reason_code="RETRY_PENDING",
        )
        self._set_timeline_pointer(
            label_assertion_id=normalized_id,
            field_name="pending_timeline_event_id",
            event_id=pending_event_id,
        )

        if current.attempt_count >= self.policy.max_retry_attempts:
            rejected_id = self._append_label_timeline_event(
                case_id=stored.case_id,
                source_case_event_id=stored.source_case_event_id,
                case_subject_key=case_row.case_subject_key,
                assertion=stored.assertion,
                event_type="LABEL_REJECTED",
                source_ref_id=f"label_assertion:{normalized_id}:rejected",
                actor_id="SYSTEM::cm_label_handshake",
                source_type=SOURCE_TYPE_SYSTEM,
                observed_time=normalized_retry_time,
                reason_code="RETRY_LIMIT_EXCEEDED",
            )
            self._update_emission_terminal(
                label_assertion_id=normalized_id,
                status=EMISSION_REJECTED,
                attempt_count=current.attempt_count,
                attempted_at_utc=normalized_retry_time,
                reason_code="RETRY_LIMIT_EXCEEDED",
                assertion_ref=current.assertion_ref,
                timeline_field="rejected_timeline_event_id",
                timeline_event_id=rejected_id,
            )
            return LabelEmissionResult(
                disposition=EMISSION_DUPLICATE,
                label_assertion_id=normalized_id,
                status=EMISSION_REJECTED,
                attempt_count=current.attempt_count,
                reason_code="RETRY_LIMIT_EXCEEDED",
                assertion_ref=current.assertion_ref,
            )

        return self._attempt_write(
            case_id=stored.case_id,
            source_case_event_id=stored.source_case_event_id,
            case_subject_key=case_row.case_subject_key,
            assertion=stored.assertion,
            attempted_at_utc=normalized_retry_time,
            disposition=EMISSION_DUPLICATE,
        )

    def lookup_emission(self, *, label_assertion_id: str) -> LabelEmissionRecord | None:
        normalized_id = _require_non_empty(label_assertion_id, "label_assertion_id")
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT case_id, source_case_event_id, status, payload_hash, attempt_count,
                       first_requested_at_utc, last_attempted_at_utc, last_reason_code, assertion_ref
                FROM cm_label_emissions
                WHERE label_assertion_id = {p1}
                """,
                (normalized_id,),
            )
        if row is None:
            return None
        return LabelEmissionRecord(
            label_assertion_id=normalized_id,
            case_id=str(row[0]),
            source_case_event_id=str(row[1]),
            status=str(row[2]),
            payload_hash=str(row[3]),
            attempt_count=int(row[4] or 0),
            first_requested_at_utc=str(row[5]),
            last_attempted_at_utc=str(row[6]),
            last_reason_code=_normalize_optional(row[7]),
            assertion_ref=_normalize_optional(row[8]),
        )

    def _upsert_emission(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        assertion: LabelAssertion,
        assertion_json: str,
        payload_hash: str,
        requested_at_utc: str,
    ) -> tuple[str, LabelEmissionRecord] | LabelEmissionResult:
        label_assertion_id = assertion.label_assertion_id

        def _tx(conn: Any) -> tuple[str, LabelEmissionRecord] | LabelEmissionResult:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT payload_hash, status, attempt_count, last_reason_code, assertion_ref,
                       first_requested_at_utc, last_attempted_at_utc
                FROM cm_label_emissions
                WHERE label_assertion_id = {p1}
                """,
                (label_assertion_id,),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO cm_label_emissions (
                        label_assertion_id, case_id, source_case_event_id, label_type,
                        payload_hash, assertion_json, status, attempt_count,
                        first_requested_at_utc, last_attempted_at_utc,
                        last_reason_code, assertion_ref,
                        pending_timeline_event_id, accepted_timeline_event_id, rejected_timeline_event_id
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5}, {p6}, {p7}, 0, {p8}, {p9}, NULL, NULL, NULL, NULL, NULL)
                    """,
                    (
                        label_assertion_id,
                        case_id,
                        source_case_event_id,
                        assertion.label_type,
                        payload_hash,
                        assertion_json,
                        EMISSION_PENDING,
                        requested_at_utc,
                        requested_at_utc,
                    ),
                )
                return (
                    EMISSION_NEW,
                    LabelEmissionRecord(
                        label_assertion_id=label_assertion_id,
                        case_id=case_id,
                        source_case_event_id=source_case_event_id,
                        status=EMISSION_PENDING,
                        payload_hash=payload_hash,
                        attempt_count=0,
                        first_requested_at_utc=requested_at_utc,
                        last_attempted_at_utc=requested_at_utc,
                        last_reason_code=None,
                        assertion_ref=None,
                    ),
                )

            stored_hash = str(row[0] or "")
            status = str(row[1] or EMISSION_PENDING)
            attempt_count = int(row[2] or 0)
            reason_code = _normalize_optional(row[3])
            assertion_ref = _normalize_optional(row[4])
            first_requested = str(row[5])
            last_attempted = str(row[6])

            if stored_hash != payload_hash:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO cm_label_emission_mismatches (
                        label_assertion_id, observed_payload_hash, stored_payload_hash,
                        observed_at_utc, assertion_json
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5})
                    """,
                    (label_assertion_id, payload_hash, stored_hash, requested_at_utc, assertion_json),
                )
                return LabelEmissionResult(
                    disposition=EMISSION_PAYLOAD_MISMATCH,
                    label_assertion_id=label_assertion_id,
                    status=status,
                    attempt_count=attempt_count,
                    reason_code="PAYLOAD_MISMATCH",
                    assertion_ref=assertion_ref,
                )

            return (
                EMISSION_DUPLICATE,
                LabelEmissionRecord(
                    label_assertion_id=label_assertion_id,
                    case_id=case_id,
                    source_case_event_id=source_case_event_id,
                    status=status,
                    payload_hash=stored_hash,
                    attempt_count=attempt_count,
                    first_requested_at_utc=first_requested,
                    last_attempted_at_utc=last_attempted,
                    last_reason_code=reason_code,
                    assertion_ref=assertion_ref,
                ),
            )

        return self._run_write_tx(_tx)

    def _attempt_write(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        case_subject_key: Mapping[str, Any],
        assertion: LabelAssertion,
        attempted_at_utc: str,
        disposition: str,
    ) -> LabelEmissionResult:
        write_result = self._write_to_label_store(assertion=assertion)
        normalized_status = _normalize_writer_status(write_result.status)
        reason_code = _normalize_optional(write_result.reason_code)
        assertion_ref = _normalize_optional(write_result.assertion_ref)

        current = self.lookup_emission(label_assertion_id=assertion.label_assertion_id)
        if current is None:
            raise CaseLabelHandshakeError("label emission row missing during write attempt")
        attempt_count = current.attempt_count + 1

        if normalized_status == LS_WRITE_ACCEPTED:
            accepted_id = self._append_label_timeline_event(
                case_id=case_id,
                source_case_event_id=source_case_event_id,
                case_subject_key=case_subject_key,
                assertion=assertion,
                event_type="LABEL_ACCEPTED",
                source_ref_id=f"label_assertion:{assertion.label_assertion_id}:accepted",
                actor_id="SYSTEM::cm_label_handshake",
                source_type=SOURCE_TYPE_SYSTEM,
                observed_time=attempted_at_utc,
                reason_code=reason_code or "LS_ACCEPTED",
                assertion_ref=assertion_ref,
            )
            self._update_emission_terminal(
                label_assertion_id=assertion.label_assertion_id,
                status=EMISSION_ACCEPTED,
                attempt_count=attempt_count,
                attempted_at_utc=attempted_at_utc,
                reason_code=reason_code or "LS_ACCEPTED",
                assertion_ref=assertion_ref,
                timeline_field="accepted_timeline_event_id",
                timeline_event_id=accepted_id,
            )
            return LabelEmissionResult(
                disposition=disposition,
                label_assertion_id=assertion.label_assertion_id,
                status=EMISSION_ACCEPTED,
                attempt_count=attempt_count,
                reason_code=reason_code,
                assertion_ref=assertion_ref,
            )

        if normalized_status == LS_WRITE_REJECTED:
            rejected_id = self._append_label_timeline_event(
                case_id=case_id,
                source_case_event_id=source_case_event_id,
                case_subject_key=case_subject_key,
                assertion=assertion,
                event_type="LABEL_REJECTED",
                source_ref_id=f"label_assertion:{assertion.label_assertion_id}:rejected",
                actor_id="SYSTEM::cm_label_handshake",
                source_type=SOURCE_TYPE_SYSTEM,
                observed_time=attempted_at_utc,
                reason_code=reason_code or "LS_REJECTED",
                assertion_ref=assertion_ref,
            )
            self._update_emission_terminal(
                label_assertion_id=assertion.label_assertion_id,
                status=EMISSION_REJECTED,
                attempt_count=attempt_count,
                attempted_at_utc=attempted_at_utc,
                reason_code=reason_code or "LS_REJECTED",
                assertion_ref=assertion_ref,
                timeline_field="rejected_timeline_event_id",
                timeline_event_id=rejected_id,
            )
            return LabelEmissionResult(
                disposition=disposition,
                label_assertion_id=assertion.label_assertion_id,
                status=EMISSION_REJECTED,
                attempt_count=attempt_count,
                reason_code=reason_code,
                assertion_ref=assertion_ref,
            )

        self._run_write_tx(
            lambda conn: _execute(
                conn,
                self.backend,
                """
                UPDATE cm_label_emissions
                SET status = {p1}, attempt_count = {p2}, last_attempted_at_utc = {p3},
                    last_reason_code = {p4}, assertion_ref = {p5}
                WHERE label_assertion_id = {p6}
                """,
                (
                    EMISSION_PENDING,
                    attempt_count,
                    attempted_at_utc,
                    reason_code or "LS_PENDING",
                    assertion_ref,
                    assertion.label_assertion_id,
                ),
            )
        )
        return LabelEmissionResult(
            disposition=disposition,
            label_assertion_id=assertion.label_assertion_id,
            status=EMISSION_PENDING,
            attempt_count=attempt_count,
            reason_code=reason_code,
            assertion_ref=assertion_ref,
        )

    def _update_emission_terminal(
        self,
        *,
        label_assertion_id: str,
        status: str,
        attempt_count: int,
        attempted_at_utc: str,
        reason_code: str | None,
        assertion_ref: str | None,
        timeline_field: str,
        timeline_event_id: str,
    ) -> None:
        if timeline_field not in {"accepted_timeline_event_id", "rejected_timeline_event_id"}:
            raise CaseLabelHandshakeError(f"unsupported timeline field: {timeline_field}")

        sql = (
            "UPDATE cm_label_emissions "
            "SET status = {p1}, attempt_count = {p2}, last_attempted_at_utc = {p3}, "
            "last_reason_code = {p4}, assertion_ref = {p5}, "
            f"{timeline_field} = {{p6}} "
            "WHERE label_assertion_id = {p7}"
        )

        self._run_write_tx(
            lambda conn: _execute(
                conn,
                self.backend,
                sql,
                (
                    status,
                    attempt_count,
                    attempted_at_utc,
                    reason_code,
                    assertion_ref,
                    timeline_event_id,
                    label_assertion_id,
                ),
            )
        )

    def _set_timeline_pointer(self, *, label_assertion_id: str, field_name: str, event_id: str) -> None:
        if field_name not in {
            "pending_timeline_event_id",
            "accepted_timeline_event_id",
            "rejected_timeline_event_id",
        }:
            raise CaseLabelHandshakeError(f"unsupported timeline pointer field: {field_name}")

        sql = (
            "UPDATE cm_label_emissions "
            f"SET {field_name} = COALESCE({field_name}, {{p1}}) "
            "WHERE label_assertion_id = {p2}"
        )

        self._run_write_tx(
            lambda conn: _execute(
                conn,
                self.backend,
                sql,
                (event_id, label_assertion_id),
            )
        )

    def _load_stored_assertion(self, *, label_assertion_id: str) -> _StoredAssertion:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT case_id, source_case_event_id, assertion_json
                FROM cm_label_emissions
                WHERE label_assertion_id = {p1}
                """,
                (label_assertion_id,),
            )
        if row is None:
            raise CaseLabelHandshakeError(f"unknown label_assertion_id: {label_assertion_id}")

        assertion_payload = _json_to_dict(row[2])
        assertion = LabelAssertion.from_payload(assertion_payload)
        return _StoredAssertion(
            case_id=str(row[0]),
            source_case_event_id=str(row[1]),
            assertion=assertion,
        )

    def _require_source_case_event(self, *, case_id: str, source_case_event_id: str) -> None:
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT 1
                FROM cm_case_timeline
                WHERE case_id = {p1} AND case_timeline_event_id = {p2}
                """,
                (case_id, source_case_event_id),
            )
        if row is None:
            raise CaseLabelHandshakeError(
                "source_case_event_id is not present in cm_case_timeline for case_id"
            )

    def _append_label_timeline_event(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        case_subject_key: Mapping[str, Any],
        assertion: LabelAssertion,
        event_type: str,
        source_ref_id: str,
        actor_id: str | None,
        source_type: str,
        observed_time: str,
        reason_code: str | None,
        assertion_ref: str | None = None,
    ) -> str:
        timeline_payload: dict[str, Any] = {
            "label_assertion_id": assertion.label_assertion_id,
            "label_type": assertion.label_type,
            "label_value": assertion.label_value,
            "label_subject_key": assertion.label_subject_key.as_dict(),
            "source_case_event_id": source_case_event_id,
        }
        if reason_code:
            timeline_payload["reason_code"] = reason_code
        if assertion_ref:
            timeline_payload["assertion_ref"] = assertion_ref

        evidence_refs = [item.as_dict() for item in assertion.evidence_refs]
        evidence_refs.append({"ref_type": "CASE_EVENT", "ref_id": source_case_event_id})
        if assertion_ref:
            evidence_refs.append({"ref_type": "EXTERNAL_REF", "ref_id": assertion_ref})

        append = self.intake_ledger.append_timeline_event(
            payload={
                "case_id": case_id,
                "timeline_event_type": event_type,
                "source_ref_id": source_ref_id,
                "pins": assertion.pins,
                "observed_time": observed_time,
                "evidence_refs": evidence_refs,
                "case_subject_key": dict(case_subject_key),
                "timeline_payload": timeline_payload,
            },
            actor_id=actor_id or "SYSTEM::cm_label_handshake",
            source_type=source_type,
            appended_at_utc=observed_time,
        )
        return append.case_timeline_event_id

    def _write_to_label_store(self, *, assertion: LabelAssertion) -> LabelStoreWriteResult:
        try:
            result = self.label_store_writer.write_label_assertion(assertion.as_dict())
        except Exception as exc:
            return LabelStoreWriteResult(
                status=LS_WRITE_PENDING,
                reason_code=f"LS_WRITE_EXCEPTION:{exc.__class__.__name__}",
                assertion_ref=None,
            )
        return result

    def _enforce_policy(self, *, label_type: str, actor_id: str | None, source_type: str) -> None:
        if label_type not in set(self.policy.allowed_label_types):
            raise CaseLabelHandshakeError(f"label_type not allowed by policy: {label_type!r}")
        if source_type not in set(self.policy.allowed_source_types):
            raise CaseLabelHandshakeError(f"source_type not allowed by policy: {source_type!r}")
        actor = _normalize_optional(actor_id)
        if actor is not None and not any(actor.startswith(prefix) for prefix in self.policy.allowed_actor_prefixes):
            raise CaseLabelHandshakeError("actor_id not allowed by policy")

    def _run_write_tx(self, func: Any) -> Any:
        with self._connect() as conn:
            if self.backend == "sqlite":
                conn.execute("BEGIN IMMEDIATE")
                result = func(conn)
                conn.commit()
                return result
            with conn.transaction():
                return func(conn)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            _execute_script(
                conn,
                self.backend,
                """
                CREATE TABLE IF NOT EXISTS cm_label_emissions (
                    label_assertion_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    source_case_event_id TEXT NOT NULL,
                    label_type TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    assertion_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    first_requested_at_utc TEXT NOT NULL,
                    last_attempted_at_utc TEXT NOT NULL,
                    last_reason_code TEXT,
                    assertion_ref TEXT,
                    pending_timeline_event_id TEXT,
                    accepted_timeline_event_id TEXT,
                    rejected_timeline_event_id TEXT
                );
                CREATE TABLE IF NOT EXISTS cm_label_emission_mismatches (
                    label_assertion_id TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    assertion_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_cm_label_emissions_case_status
                    ON cm_label_emissions (case_id, status, last_attempted_at_utc);
                CREATE INDEX IF NOT EXISTS ix_cm_label_emission_mismatch_assertion
                    ON cm_label_emission_mismatches (label_assertion_id, observed_at_utc);
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


def load_label_emission_policy(path: Path) -> LabelEmissionPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CaseLabelHandshakeError("label emission policy must be a mapping")

    version = _require_non_empty(payload.get("version"), "version")
    policy_id = _require_non_empty(payload.get("policy_id"), "policy_id")
    revision = _require_non_empty(payload.get("revision"), "revision")

    emission = payload.get("label_emission")
    if not isinstance(emission, dict):
        raise CaseLabelHandshakeError("label_emission section is required")

    allowed_label_types = tuple(
        sorted(
            {
                _require_non_empty(item, "allowed_label_types.item")
                for item in _require_list(emission.get("allowed_label_types"), "allowed_label_types")
            }
        )
    )
    allowed_actor_prefixes = tuple(
        sorted(
            {
                _require_non_empty(item, "allowed_actor_prefixes.item")
                for item in _require_list(emission.get("allowed_actor_prefixes"), "allowed_actor_prefixes")
            }
        )
    )
    allowed_source_types = tuple(
        sorted(
            {
                _normalize_source_type(item)
                for item in _require_list(emission.get("allowed_source_types"), "allowed_source_types")
            }
        )
    )
    max_retry_attempts = int(emission.get("max_retry_attempts") or 0)
    if max_retry_attempts < 1:
        raise CaseLabelHandshakeError("max_retry_attempts must be >= 1")

    digest_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "allowed_label_types": list(allowed_label_types),
        "allowed_actor_prefixes": list(allowed_actor_prefixes),
        "allowed_source_types": list(allowed_source_types),
        "max_retry_attempts": max_retry_attempts,
    }
    canonical = json.dumps(digest_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return LabelEmissionPolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        allowed_label_types=allowed_label_types,
        allowed_actor_prefixes=allowed_actor_prefixes,
        allowed_source_types=allowed_source_types,
        max_retry_attempts=max_retry_attempts,
        content_digest=content_digest,
    )


def _normalize_writer_status(value: str) -> str:
    normalized = _require_non_empty(value, "writer.status").upper()
    allowed = {LS_WRITE_ACCEPTED, LS_WRITE_REJECTED, LS_WRITE_PENDING}
    if normalized not in allowed:
        supported = ",".join(sorted(allowed))
        raise CaseLabelHandshakeError(f"writer status unsupported: {normalized!r}; allowed={supported}")
    return normalized


def _normalize_source_type(value: str) -> str:
    normalized = _require_non_empty(value, "source_type").upper()
    allowed = {"SYSTEM", "HUMAN", "EXTERNAL", "AUTO"}
    if normalized not in allowed:
        supported = ",".join(sorted(allowed))
        raise CaseLabelHandshakeError(f"unsupported source_type: {normalized!r}; allowed={supported}")
    return normalized


def _json_to_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CaseLabelHandshakeError("invalid stored assertion_json") from exc
    if not isinstance(parsed, Mapping):
        raise CaseLabelHandshakeError("stored assertion_json must decode to mapping")
    return dict(parsed)


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise CaseLabelHandshakeError(f"{field_name} must be a non-empty list")
    return value


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseLabelHandshakeError(f"{field_name} is required")
    return text


def _normalize_optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sqlite_path(locator: str) -> str:
    if locator.startswith("sqlite:///"):
        return locator[len("sqlite:///") :]
    if locator.startswith("sqlite://"):
        return locator[len("sqlite://") :]
    return locator


def _normalize_locator(locator: str) -> str:
    if is_postgres_dsn(locator):
        return str(locator).strip()
    return str(Path(_sqlite_path(locator)).resolve())


def _render_sql(sql: str, backend: str) -> str:
    rendered = sql
    if backend == "postgres":
        for idx in range(1, 51):
            rendered = rendered.replace(f"{{p{idx}}}", f"${idx}")
    else:
        for idx in range(1, 51):
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
    else:
        conn.cursor().execute(rendered, params)


def _execute_script(conn: Any, backend: str, sql: str) -> None:
    if backend == "sqlite":
        conn.executescript(sql)
        return
    statements = [item.strip() for item in sql.split(";") if item.strip()]
    cur = conn.cursor()
    for statement in statements:
        cur.execute(statement)
