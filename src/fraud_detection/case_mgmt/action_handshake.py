"""CM -> Action Layer manual-action handshake coordinator (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Protocol

import psycopg
import yaml

from fraud_detection.action_layer import ActionIntent
from fraud_detection.ingestion_gate.pg_index import is_postgres_dsn

from .intake import CaseTriggerIntakeLedger, SOURCE_TYPE_SYSTEM


AL_SUBMIT_ACCEPTED = "ACCEPTED"
AL_SUBMIT_REJECTED = "REJECTED"
AL_SUBMIT_PENDING = "PENDING"

SUBMIT_REQUESTED = "REQUESTED"
SUBMIT_SUBMITTED = "SUBMITTED"
SUBMIT_PRECHECK_REJECTED = "PRECHECK_REJECTED"
SUBMIT_FAILED_RETRYABLE = "SUBMIT_FAILED_RETRYABLE"
SUBMIT_FAILED_FATAL = "SUBMIT_FAILED_FATAL"

OUTCOME_EXECUTED = "EXECUTED"
OUTCOME_DENIED = "DENIED"
OUTCOME_FAILED = "FAILED"
OUTCOME_TIMED_OUT = "TIMED_OUT"
OUTCOME_UNKNOWN = "UNKNOWN"

SUBMIT_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        SUBMIT_SUBMITTED,
        SUBMIT_PRECHECK_REJECTED,
        SUBMIT_FAILED_FATAL,
    }
)
OUTCOME_ALLOWED_CLASSES: frozenset[str] = frozenset(
    {
        OUTCOME_EXECUTED,
        OUTCOME_DENIED,
        OUTCOME_FAILED,
        OUTCOME_TIMED_OUT,
        OUTCOME_UNKNOWN,
    }
)

ACTION_NEW = "NEW"
ACTION_DUPLICATE = "DUPLICATE"
ACTION_PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"


class CaseActionHandshakeError(RuntimeError):
    """Raised when CM manual-action handshake operations are invalid."""


@dataclass(frozen=True)
class ActionEmissionPolicy:
    version: str
    policy_id: str
    revision: str
    allowed_action_kinds: tuple[str, ...]
    allowed_actor_prefixes: tuple[str, ...]
    allowed_source_types: tuple[str, ...]
    origin: str
    al_policy_id: str
    al_policy_revision: str
    max_submit_attempts: int
    content_digest: str


@dataclass(frozen=True)
class ActionSubmitWriteResult:
    status: str
    reason_code: str | None = None
    intent_ref: str | None = None


class ActionIntentWriter(Protocol):
    def write_action_intent(self, intent_payload: Mapping[str, Any]) -> ActionSubmitWriteResult:
        ...


@dataclass(frozen=True)
class ActionIntentRecord:
    action_idempotency_key: str
    action_id: str
    case_id: str
    source_case_event_id: str
    status: str
    submit_attempt_count: int
    payload_hash: str
    last_reason_code: str | None
    intent_ref: str | None
    action_outcome_id: str | None
    outcome_status: str | None
    outcome_observed_at_utc: str | None


@dataclass(frozen=True)
class ActionIntentSubmissionResult:
    disposition: str
    action_idempotency_key: str
    action_id: str
    submission_status: str
    submit_attempt_count: int
    reason_code: str | None
    intent_ref: str | None


@dataclass(frozen=True)
class ActionOutcomeAttachResult:
    action_idempotency_key: str
    action_outcome_id: str
    outcome_status: str
    timeline_event_id: str


class CaseActionHandshakeCoordinator:
    """Deterministic CM manual-action lane with AL-boundary submission + by-ref outcome attach."""

    def __init__(
        self,
        *,
        locator: str,
        intake_ledger: CaseTriggerIntakeLedger,
        policy: ActionEmissionPolicy,
        action_intent_writer: ActionIntentWriter,
    ) -> None:
        self.locator = str(locator)
        self.backend = "postgres" if is_postgres_dsn(self.locator) else "sqlite"
        if self.backend == "sqlite":
            path = Path(_sqlite_path(self.locator))
            path.parent.mkdir(parents=True, exist_ok=True)
        self.intake_ledger = intake_ledger
        self.policy = policy
        self.action_intent_writer = action_intent_writer

        if _normalize_locator(self.locator) != _normalize_locator(self.intake_ledger.locator):
            raise CaseActionHandshakeError(
                "action handshake locator must match CaseTriggerIntakeLedger locator"
            )

        self._init_schema()

    def submit_manual_action(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        action_kind: str,
        target_ref: Mapping[str, Any],
        pins: Mapping[str, Any],
        actor_principal: str,
        source_type: str,
        requested_at_utc: str,
        reason_code: str,
        evidence_refs: list[Mapping[str, Any]],
        decision_id: str | None = None,
        run_config_digest: str | None = None,
        constraints: Mapping[str, Any] | None = None,
    ) -> ActionIntentSubmissionResult:
        normalized_case_id = _require_non_empty(case_id, "case_id")
        normalized_source_event = _require_non_empty(source_case_event_id, "source_case_event_id")
        normalized_action_kind = _require_non_empty(action_kind, "action_kind")
        normalized_actor = _require_non_empty(actor_principal, "actor_principal")
        normalized_source_type = _normalize_source_type(source_type)
        normalized_requested_at = _require_non_empty(requested_at_utc, "requested_at_utc")
        normalized_reason_code = _require_non_empty(reason_code, "reason_code")

        normalized_target_ref = _normalize_target_ref(target_ref)
        normalized_evidence_refs = _normalize_evidence_refs(evidence_refs)
        self._enforce_policy(
            action_kind=normalized_action_kind,
            actor_principal=normalized_actor,
            source_type=normalized_source_type,
        )

        case_row = self.intake_ledger.lookup_case(normalized_case_id)
        if case_row is None:
            raise CaseActionHandshakeError(f"unknown case_id: {normalized_case_id}")
        self._require_source_case_event(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
        )

        action_idempotency_key = _deterministic_action_idempotency_key(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            action_kind=normalized_action_kind,
            target_ref=normalized_target_ref,
        )
        action_id = _deterministic_action_id(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            action_idempotency_key=action_idempotency_key,
        )
        normalized_decision_id = _normalize_decision_id(
            decision_id,
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            action_kind=normalized_action_kind,
        )
        normalized_run_config_digest = _normalize_run_config_digest(
            run_config_digest,
            pins=dict(pins),
        )

        action_payload = {
            "case_id": normalized_case_id,
            "source_case_event_id": normalized_source_event,
            "reason_code": normalized_reason_code,
            "target_ref": dict(normalized_target_ref),
            "evidence_refs": [dict(item) for item in normalized_evidence_refs],
            "constraints": dict(constraints) if isinstance(constraints, Mapping) else {},
            "origin_marker": "case_workbench",
        }

        intent = ActionIntent.from_payload(
            {
                "action_id": action_id,
                "decision_id": normalized_decision_id,
                "action_kind": normalized_action_kind,
                "idempotency_key": action_idempotency_key,
                "pins": dict(pins),
                "requested_at_utc": normalized_requested_at,
                "actor_principal": normalized_actor,
                "origin": self.policy.origin,
                "policy_rev": {
                    "policy_id": self.policy.al_policy_id,
                    "revision": self.policy.al_policy_revision,
                },
                "run_config_digest": normalized_run_config_digest,
                "reason_ref": f"case://{normalized_case_id}/event/{normalized_source_event}",
                "action_payload": action_payload,
            }
        )
        intent_payload = intent.as_dict()
        intent_json = _canonical_json(intent_payload)
        payload_hash = _hash_text(intent_json)

        upsert = self._upsert_action_intent(
            action_idempotency_key=action_idempotency_key,
            action_id=action_id,
            decision_id=normalized_decision_id,
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            action_kind=normalized_action_kind,
            target_ref=normalized_target_ref,
            payload_hash=payload_hash,
            intent_json=intent_json,
            requested_at_utc=normalized_requested_at,
        )
        if isinstance(upsert, ActionIntentSubmissionResult):
            return upsert

        disposition, current = upsert

        requested_timeline_event_id = self._append_action_intent_timeline_event(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            case_subject_key=case_row.case_subject_key,
            pins=dict(pins),
            action_id=action_id,
            action_idempotency_key=action_idempotency_key,
            action_kind=normalized_action_kind,
            target_ref=normalized_target_ref,
            actor_id=normalized_actor,
            source_type=normalized_source_type,
            observed_time=normalized_requested_at,
            submit_status=SUBMIT_REQUESTED,
            reason_code=normalized_reason_code,
            evidence_refs=normalized_evidence_refs,
            intent_ref=None,
        )
        self._set_timeline_pointer(
            action_idempotency_key=action_idempotency_key,
            field_name="requested_timeline_event_id",
            event_id=requested_timeline_event_id,
        )

        if current.status in SUBMIT_TERMINAL_STATUSES:
            return ActionIntentSubmissionResult(
                disposition=ACTION_DUPLICATE,
                action_idempotency_key=action_idempotency_key,
                action_id=action_id,
                submission_status=current.status,
                submit_attempt_count=current.submit_attempt_count,
                reason_code=current.last_reason_code,
                intent_ref=current.intent_ref,
            )

        if current.status == SUBMIT_FAILED_RETRYABLE and disposition == ACTION_DUPLICATE:
            return ActionIntentSubmissionResult(
                disposition=ACTION_DUPLICATE,
                action_idempotency_key=action_idempotency_key,
                action_id=action_id,
                submission_status=current.status,
                submit_attempt_count=current.submit_attempt_count,
                reason_code=current.last_reason_code,
                intent_ref=current.intent_ref,
            )

        return self._attempt_submit(
            case_id=normalized_case_id,
            source_case_event_id=normalized_source_event,
            case_subject_key=case_row.case_subject_key,
            pins=dict(pins),
            action_id=action_id,
            action_idempotency_key=action_idempotency_key,
            action_kind=normalized_action_kind,
            target_ref=normalized_target_ref,
            actor_id=normalized_actor,
            source_type=normalized_source_type,
            observed_time=normalized_requested_at,
            reason_code=normalized_reason_code,
            intent=intent,
            evidence_refs=normalized_evidence_refs,
            disposition=disposition,
        )

    def retry_pending(
        self,
        *,
        action_idempotency_key: str,
        retried_at_utc: str,
    ) -> ActionIntentSubmissionResult:
        normalized_key = _require_non_empty(action_idempotency_key, "action_idempotency_key")
        normalized_retried_at = _require_non_empty(retried_at_utc, "retried_at_utc")

        current = self.lookup_action_intent(action_idempotency_key=normalized_key)
        if current is None:
            raise CaseActionHandshakeError(f"unknown action_idempotency_key: {normalized_key}")
        if current.status in SUBMIT_TERMINAL_STATUSES:
            return ActionIntentSubmissionResult(
                disposition=ACTION_DUPLICATE,
                action_idempotency_key=normalized_key,
                action_id=current.action_id,
                submission_status=current.status,
                submit_attempt_count=current.submit_attempt_count,
                reason_code=current.last_reason_code,
                intent_ref=current.intent_ref,
            )

        stored = self._load_stored_intent(action_idempotency_key=normalized_key)
        case_row = self.intake_ledger.lookup_case(stored.case_id)
        if case_row is None:
            raise CaseActionHandshakeError(f"unknown case_id for retry: {stored.case_id}")

        if current.submit_attempt_count >= self.policy.max_submit_attempts:
            status_event_id = self._append_action_intent_timeline_event(
                case_id=stored.case_id,
                source_case_event_id=stored.source_case_event_id,
                case_subject_key=case_row.case_subject_key,
                pins=stored.pins,
                action_id=stored.action_id,
                action_idempotency_key=normalized_key,
                action_kind=stored.action_kind,
                target_ref=stored.target_ref,
                actor_id="SYSTEM::cm_action_handshake",
                source_type=SOURCE_TYPE_SYSTEM,
                observed_time=normalized_retried_at,
                submit_status=SUBMIT_FAILED_FATAL,
                reason_code="RETRY_LIMIT_EXCEEDED",
                evidence_refs=stored.evidence_refs,
                intent_ref=current.intent_ref,
            )
            self._set_timeline_pointer(
                action_idempotency_key=normalized_key,
                field_name="status_timeline_event_id",
                event_id=status_event_id,
            )
            self._update_submission_result(
                action_idempotency_key=normalized_key,
                status=SUBMIT_FAILED_FATAL,
                submit_attempt_count=current.submit_attempt_count,
                attempted_at_utc=normalized_retried_at,
                reason_code="RETRY_LIMIT_EXCEEDED",
                intent_ref=current.intent_ref,
            )
            return ActionIntentSubmissionResult(
                disposition=ACTION_DUPLICATE,
                action_idempotency_key=normalized_key,
                action_id=current.action_id,
                submission_status=SUBMIT_FAILED_FATAL,
                submit_attempt_count=current.submit_attempt_count,
                reason_code="RETRY_LIMIT_EXCEEDED",
                intent_ref=current.intent_ref,
            )

        return self._attempt_submit(
            case_id=stored.case_id,
            source_case_event_id=stored.source_case_event_id,
            case_subject_key=case_row.case_subject_key,
            pins=stored.pins,
            action_id=stored.action_id,
            action_idempotency_key=normalized_key,
            action_kind=stored.action_kind,
            target_ref=stored.target_ref,
            actor_id="SYSTEM::cm_action_handshake",
            source_type=SOURCE_TYPE_SYSTEM,
            observed_time=normalized_retried_at,
            reason_code=stored.reason_code,
            intent=stored.intent,
            evidence_refs=stored.evidence_refs,
            disposition=ACTION_DUPLICATE,
        )

    def lookup_action_intent(self, *, action_idempotency_key: str) -> ActionIntentRecord | None:
        normalized_key = _require_non_empty(action_idempotency_key, "action_idempotency_key")
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT action_id, case_id, source_case_event_id, status, submit_attempt_count, payload_hash,
                       last_reason_code, intent_ref, action_outcome_id, outcome_status, outcome_observed_at_utc
                FROM cm_action_intents
                WHERE action_idempotency_key = {p1}
                """,
                (normalized_key,),
            )
        if row is None:
            return None
        return ActionIntentRecord(
            action_idempotency_key=normalized_key,
            action_id=str(row[0]),
            case_id=str(row[1]),
            source_case_event_id=str(row[2]),
            status=str(row[3]),
            submit_attempt_count=int(row[4] or 0),
            payload_hash=str(row[5]),
            last_reason_code=_normalize_optional(row[6]),
            intent_ref=_normalize_optional(row[7]),
            action_outcome_id=_normalize_optional(row[8]),
            outcome_status=_normalize_optional(row[9]),
            outcome_observed_at_utc=_normalize_optional(row[10]),
        )

    def attach_action_outcome(
        self,
        *,
        case_id: str,
        action_idempotency_key: str,
        action_outcome_id: str,
        outcome_status: str,
        observed_at_utc: str,
        actor_id: str | None,
        source_type: str,
        evidence_refs: list[Mapping[str, Any]],
        outcome_ref: str | None = None,
    ) -> ActionOutcomeAttachResult:
        normalized_case_id = _require_non_empty(case_id, "case_id")
        normalized_key = _require_non_empty(action_idempotency_key, "action_idempotency_key")
        normalized_outcome_id = _require_non_empty(action_outcome_id, "action_outcome_id")
        normalized_outcome_status = _normalize_outcome_class(outcome_status)
        normalized_observed_at = _require_non_empty(observed_at_utc, "observed_at_utc")
        normalized_source_type = _normalize_source_type(source_type)
        normalized_actor = _normalize_optional(actor_id) or "SYSTEM::cm_action_handshake"

        current = self.lookup_action_intent(action_idempotency_key=normalized_key)
        if current is None:
            raise CaseActionHandshakeError(f"unknown action_idempotency_key: {normalized_key}")
        if current.case_id != normalized_case_id:
            raise CaseActionHandshakeError("case_id does not match action_idempotency_key binding")
        stored = self._load_stored_intent(action_idempotency_key=normalized_key)
        case_row = self.intake_ledger.lookup_case(normalized_case_id)
        if case_row is None:
            raise CaseActionHandshakeError(f"unknown case_id: {normalized_case_id}")

        normalized_refs = _normalize_evidence_refs(evidence_refs)
        normalized_refs.append({"ref_type": "ACTION_OUTCOME", "ref_id": normalized_outcome_id})
        normalized_refs.append({"ref_type": "CASE_EVENT", "ref_id": stored.source_case_event_id})
        if outcome_ref:
            normalized_refs.append({"ref_type": "EXTERNAL_REF", "ref_id": str(outcome_ref)})

        timeline_event_id = self._append_action_outcome_timeline_event(
            case_id=normalized_case_id,
            source_case_event_id=stored.source_case_event_id,
            case_subject_key=case_row.case_subject_key,
            pins=stored.pins,
            action_id=stored.action_id,
            action_idempotency_key=normalized_key,
            action_outcome_id=normalized_outcome_id,
            outcome_status=normalized_outcome_status,
            observed_time=normalized_observed_at,
            actor_id=normalized_actor,
            source_type=normalized_source_type,
            evidence_refs=normalized_refs,
            outcome_ref=_normalize_optional(outcome_ref),
        )
        self._set_timeline_pointer(
            action_idempotency_key=normalized_key,
            field_name="outcome_timeline_event_id",
            event_id=timeline_event_id,
        )
        self._update_outcome_binding(
            action_idempotency_key=normalized_key,
            action_outcome_id=normalized_outcome_id,
            outcome_status=normalized_outcome_status,
            outcome_observed_at_utc=normalized_observed_at,
        )
        return ActionOutcomeAttachResult(
            action_idempotency_key=normalized_key,
            action_outcome_id=normalized_outcome_id,
            outcome_status=normalized_outcome_status,
            timeline_event_id=timeline_event_id,
        )

    def _upsert_action_intent(
        self,
        *,
        action_idempotency_key: str,
        action_id: str,
        decision_id: str,
        case_id: str,
        source_case_event_id: str,
        action_kind: str,
        target_ref: Mapping[str, str],
        payload_hash: str,
        intent_json: str,
        requested_at_utc: str,
    ) -> tuple[str, ActionIntentRecord] | ActionIntentSubmissionResult:
        def _tx(conn: Any) -> tuple[str, ActionIntentRecord] | ActionIntentSubmissionResult:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT action_id, status, submit_attempt_count, payload_hash,
                       last_reason_code, intent_ref, action_outcome_id, outcome_status, outcome_observed_at_utc
                FROM cm_action_intents
                WHERE action_idempotency_key = {p1}
                """,
                (action_idempotency_key,),
            )
            if row is None:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO cm_action_intents (
                        action_idempotency_key, action_id, decision_id, case_id, source_case_event_id,
                        action_kind, target_ref_type, target_ref_id,
                        payload_hash, intent_json, status, submit_attempt_count,
                        first_requested_at_utc, last_attempted_at_utc,
                        last_reason_code, intent_ref,
                        requested_timeline_event_id, status_timeline_event_id, outcome_timeline_event_id,
                        action_outcome_id, outcome_status, outcome_observed_at_utc
                    ) VALUES (
                        {p1}, {p2}, {p3}, {p4}, {p5},
                        {p6}, {p7}, {p8},
                        {p9}, {p10}, {p11}, 0,
                        {p12}, {p13},
                        NULL, NULL,
                        NULL, NULL, NULL,
                        NULL, NULL, NULL
                    )
                    """,
                    (
                        action_idempotency_key,
                        action_id,
                        decision_id,
                        case_id,
                        source_case_event_id,
                        action_kind,
                        target_ref["ref_type"],
                        target_ref["ref_id"],
                        payload_hash,
                        intent_json,
                        SUBMIT_REQUESTED,
                        requested_at_utc,
                        requested_at_utc,
                    ),
                )
                return (
                    ACTION_NEW,
                    ActionIntentRecord(
                        action_idempotency_key=action_idempotency_key,
                        action_id=action_id,
                        case_id=case_id,
                        source_case_event_id=source_case_event_id,
                        status=SUBMIT_REQUESTED,
                        submit_attempt_count=0,
                        payload_hash=payload_hash,
                        last_reason_code=None,
                        intent_ref=None,
                        action_outcome_id=None,
                        outcome_status=None,
                        outcome_observed_at_utc=None,
                    ),
                )

            stored_action_id = str(row[0] or "")
            status = str(row[1] or SUBMIT_REQUESTED)
            attempts = int(row[2] or 0)
            stored_hash = str(row[3] or "")
            reason_code = _normalize_optional(row[4])
            intent_ref = _normalize_optional(row[5])
            action_outcome_id = _normalize_optional(row[6])
            outcome_status = _normalize_optional(row[7])
            outcome_observed = _normalize_optional(row[8])

            if stored_hash != payload_hash:
                _execute(
                    conn,
                    self.backend,
                    """
                    INSERT INTO cm_action_intent_mismatches (
                        action_idempotency_key, observed_payload_hash, stored_payload_hash, observed_at_utc, intent_json
                    ) VALUES ({p1}, {p2}, {p3}, {p4}, {p5})
                    """,
                    (action_idempotency_key, payload_hash, stored_hash, requested_at_utc, intent_json),
                )
                return ActionIntentSubmissionResult(
                    disposition=ACTION_PAYLOAD_MISMATCH,
                    action_idempotency_key=action_idempotency_key,
                    action_id=stored_action_id,
                    submission_status=status,
                    submit_attempt_count=attempts,
                    reason_code="PAYLOAD_MISMATCH",
                    intent_ref=intent_ref,
                )

            return (
                ACTION_DUPLICATE,
                ActionIntentRecord(
                    action_idempotency_key=action_idempotency_key,
                    action_id=stored_action_id,
                    case_id=case_id,
                    source_case_event_id=source_case_event_id,
                    status=status,
                    submit_attempt_count=attempts,
                    payload_hash=stored_hash,
                    last_reason_code=reason_code,
                    intent_ref=intent_ref,
                    action_outcome_id=action_outcome_id,
                    outcome_status=outcome_status,
                    outcome_observed_at_utc=outcome_observed,
                ),
            )

        return self._run_write_tx(_tx)

    def _attempt_submit(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        case_subject_key: Mapping[str, Any],
        pins: Mapping[str, Any],
        action_id: str,
        action_idempotency_key: str,
        action_kind: str,
        target_ref: Mapping[str, str],
        actor_id: str,
        source_type: str,
        observed_time: str,
        reason_code: str,
        intent: ActionIntent,
        evidence_refs: list[dict[str, str]],
        disposition: str,
    ) -> ActionIntentSubmissionResult:
        write_result = self._submit_to_action_layer(intent=intent)
        submit_status, normalized_reason = _map_submit_status(
            write_status=write_result.status,
            reason_code=write_result.reason_code,
        )
        intent_ref = _normalize_optional(write_result.intent_ref)

        current = self.lookup_action_intent(action_idempotency_key=action_idempotency_key)
        if current is None:
            raise CaseActionHandshakeError("action intent row missing during submit attempt")
        next_attempt = current.submit_attempt_count + 1

        if submit_status == SUBMIT_FAILED_RETRYABLE and next_attempt >= self.policy.max_submit_attempts:
            submit_status = SUBMIT_FAILED_FATAL
            normalized_reason = "RETRY_LIMIT_EXCEEDED"

        status_timeline_event_id = self._append_action_intent_timeline_event(
            case_id=case_id,
            source_case_event_id=source_case_event_id,
            case_subject_key=case_subject_key,
            pins=pins,
            action_id=action_id,
            action_idempotency_key=action_idempotency_key,
            action_kind=action_kind,
            target_ref=target_ref,
            actor_id=actor_id,
            source_type=source_type,
            observed_time=observed_time,
            submit_status=submit_status,
            reason_code=normalized_reason or reason_code,
            evidence_refs=evidence_refs,
            intent_ref=intent_ref,
        )
        self._set_timeline_pointer(
            action_idempotency_key=action_idempotency_key,
            field_name="status_timeline_event_id",
            event_id=status_timeline_event_id,
        )
        self._update_submission_result(
            action_idempotency_key=action_idempotency_key,
            status=submit_status,
            submit_attempt_count=next_attempt,
            attempted_at_utc=observed_time,
            reason_code=normalized_reason,
            intent_ref=intent_ref,
        )
        return ActionIntentSubmissionResult(
            disposition=disposition,
            action_idempotency_key=action_idempotency_key,
            action_id=action_id,
            submission_status=submit_status,
            submit_attempt_count=next_attempt,
            reason_code=normalized_reason,
            intent_ref=intent_ref,
        )

    def _submit_to_action_layer(self, *, intent: ActionIntent) -> ActionSubmitWriteResult:
        try:
            result = self.action_intent_writer.write_action_intent(intent.as_dict())
        except Exception as exc:
            return ActionSubmitWriteResult(
                status=AL_SUBMIT_PENDING,
                reason_code=f"AL_SUBMIT_EXCEPTION:{exc.__class__.__name__}",
                intent_ref=None,
            )
        return result

    def _load_stored_intent(self, *, action_idempotency_key: str) -> "_StoredActionIntent":
        with self._connect() as conn:
            row = _query_one(
                conn,
                self.backend,
                """
                SELECT action_id, case_id, source_case_event_id, action_kind, target_ref_type, target_ref_id,
                       intent_json
                FROM cm_action_intents
                WHERE action_idempotency_key = {p1}
                """,
                (action_idempotency_key,),
            )
        if row is None:
            raise CaseActionHandshakeError(f"unknown action_idempotency_key: {action_idempotency_key}")
        intent_payload = _json_to_dict(row[6])
        intent = ActionIntent.from_payload(intent_payload)
        action_payload = intent_payload.get("action_payload")
        payload_map = dict(action_payload) if isinstance(action_payload, Mapping) else {}
        raw_refs = payload_map.get("evidence_refs")
        evidence_refs = _normalize_evidence_refs(raw_refs if isinstance(raw_refs, list) else [])
        target_ref = {
            "ref_type": str(row[4]),
            "ref_id": str(row[5]),
        }
        return _StoredActionIntent(
            action_id=str(row[0]),
            case_id=str(row[1]),
            source_case_event_id=str(row[2]),
            action_kind=str(row[3]),
            target_ref=target_ref,
            reason_code=str(payload_map.get("reason_code") or "ACTION_REQUESTED"),
            evidence_refs=evidence_refs,
            pins=dict(intent.payload.get("pins") or {}),
            intent=intent,
        )

    def _update_submission_result(
        self,
        *,
        action_idempotency_key: str,
        status: str,
        submit_attempt_count: int,
        attempted_at_utc: str,
        reason_code: str | None,
        intent_ref: str | None,
    ) -> None:
        self._run_write_tx(
            lambda conn: _execute(
                conn,
                self.backend,
                """
                UPDATE cm_action_intents
                SET status = {p1},
                    submit_attempt_count = {p2},
                    last_attempted_at_utc = {p3},
                    last_reason_code = {p4},
                    intent_ref = {p5}
                WHERE action_idempotency_key = {p6}
                """,
                (
                    status,
                    submit_attempt_count,
                    attempted_at_utc,
                    reason_code,
                    intent_ref,
                    action_idempotency_key,
                ),
            )
        )

    def _update_outcome_binding(
        self,
        *,
        action_idempotency_key: str,
        action_outcome_id: str,
        outcome_status: str,
        outcome_observed_at_utc: str,
    ) -> None:
        self._run_write_tx(
            lambda conn: _execute(
                conn,
                self.backend,
                """
                UPDATE cm_action_intents
                SET action_outcome_id = {p1},
                    outcome_status = {p2},
                    outcome_observed_at_utc = {p3}
                WHERE action_idempotency_key = {p4}
                """,
                (
                    action_outcome_id,
                    outcome_status,
                    outcome_observed_at_utc,
                    action_idempotency_key,
                ),
            )
        )

    def _set_timeline_pointer(self, *, action_idempotency_key: str, field_name: str, event_id: str) -> None:
        if field_name not in {
            "requested_timeline_event_id",
            "status_timeline_event_id",
            "outcome_timeline_event_id",
        }:
            raise CaseActionHandshakeError(f"unsupported timeline pointer field: {field_name}")
        sql = (
            "UPDATE cm_action_intents "
            f"SET {field_name} = COALESCE({field_name}, {{p1}}) "
            "WHERE action_idempotency_key = {p2}"
        )
        self._run_write_tx(
            lambda conn: _execute(
                conn,
                self.backend,
                sql,
                (event_id, action_idempotency_key),
            )
        )

    def _append_action_intent_timeline_event(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        case_subject_key: Mapping[str, Any],
        pins: Mapping[str, Any],
        action_id: str,
        action_idempotency_key: str,
        action_kind: str,
        target_ref: Mapping[str, str],
        actor_id: str,
        source_type: str,
        observed_time: str,
        submit_status: str,
        reason_code: str,
        evidence_refs: list[dict[str, str]],
        intent_ref: str | None,
    ) -> str:
        source_ref_id = f"action_intent:{action_id}:submit:{submit_status.lower()}"
        timeline_payload: dict[str, Any] = {
            "action_id": action_id,
            "action_kind": action_kind,
            "action_idempotency_key": action_idempotency_key,
            "source_case_event_id": source_case_event_id,
            "target_ref": dict(target_ref),
            "submit_status": submit_status,
            "reason_code": reason_code,
        }
        if intent_ref:
            timeline_payload["intent_ref"] = intent_ref

        refs = [dict(item) for item in evidence_refs]
        refs.append({"ref_type": "CASE_EVENT", "ref_id": source_case_event_id})
        if intent_ref:
            refs.append({"ref_type": "EXTERNAL_REF", "ref_id": intent_ref})
        append = self.intake_ledger.append_timeline_event(
            payload={
                "case_id": case_id,
                "timeline_event_type": "ACTION_INTENT_REQUESTED",
                "source_ref_id": source_ref_id,
                "pins": dict(pins),
                "observed_time": observed_time,
                "evidence_refs": refs,
                "case_subject_key": dict(case_subject_key),
                "timeline_payload": timeline_payload,
            },
            actor_id=actor_id,
            source_type=source_type,
            appended_at_utc=observed_time,
        )
        return append.case_timeline_event_id

    def _append_action_outcome_timeline_event(
        self,
        *,
        case_id: str,
        source_case_event_id: str,
        case_subject_key: Mapping[str, Any],
        pins: Mapping[str, Any],
        action_id: str,
        action_idempotency_key: str,
        action_outcome_id: str,
        outcome_status: str,
        observed_time: str,
        actor_id: str,
        source_type: str,
        evidence_refs: list[dict[str, str]],
        outcome_ref: str | None,
    ) -> str:
        timeline_payload: dict[str, Any] = {
            "action_id": action_id,
            "action_idempotency_key": action_idempotency_key,
            "action_outcome_id": action_outcome_id,
            "outcome_status": outcome_status,
            "source_case_event_id": source_case_event_id,
        }
        if outcome_ref:
            timeline_payload["outcome_ref"] = outcome_ref
        append = self.intake_ledger.append_timeline_event(
            payload={
                "case_id": case_id,
                "timeline_event_type": "ACTION_OUTCOME_ATTACHED",
                "source_ref_id": f"action_outcome:{action_outcome_id}",
                "pins": dict(pins),
                "observed_time": observed_time,
                "evidence_refs": [dict(item) for item in evidence_refs],
                "case_subject_key": dict(case_subject_key),
                "timeline_payload": timeline_payload,
            },
            actor_id=actor_id,
            source_type=source_type,
            appended_at_utc=observed_time,
        )
        return append.case_timeline_event_id

    def _enforce_policy(self, *, action_kind: str, actor_principal: str, source_type: str) -> None:
        if action_kind not in set(self.policy.allowed_action_kinds):
            raise CaseActionHandshakeError(f"action_kind not allowed by policy: {action_kind!r}")
        if source_type not in set(self.policy.allowed_source_types):
            raise CaseActionHandshakeError(f"source_type not allowed by policy: {source_type!r}")
        if not any(actor_principal.startswith(prefix) for prefix in self.policy.allowed_actor_prefixes):
            raise CaseActionHandshakeError("actor_principal not allowed by policy")

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
            raise CaseActionHandshakeError(
                "source_case_event_id is not present in cm_case_timeline for case_id"
            )

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
                CREATE TABLE IF NOT EXISTS cm_action_intents (
                    action_idempotency_key TEXT PRIMARY KEY,
                    action_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    source_case_event_id TEXT NOT NULL,
                    action_kind TEXT NOT NULL,
                    target_ref_type TEXT NOT NULL,
                    target_ref_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    intent_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    submit_attempt_count INTEGER NOT NULL DEFAULT 0,
                    first_requested_at_utc TEXT NOT NULL,
                    last_attempted_at_utc TEXT NOT NULL,
                    last_reason_code TEXT,
                    intent_ref TEXT,
                    requested_timeline_event_id TEXT,
                    status_timeline_event_id TEXT,
                    outcome_timeline_event_id TEXT,
                    action_outcome_id TEXT,
                    outcome_status TEXT,
                    outcome_observed_at_utc TEXT
                );
                CREATE TABLE IF NOT EXISTS cm_action_intent_mismatches (
                    action_idempotency_key TEXT NOT NULL,
                    observed_payload_hash TEXT NOT NULL,
                    stored_payload_hash TEXT NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    intent_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_cm_action_intents_case_status
                    ON cm_action_intents (case_id, status, last_attempted_at_utc);
                CREATE INDEX IF NOT EXISTS ix_cm_action_intents_outcome
                    ON cm_action_intents (action_outcome_id, outcome_status, outcome_observed_at_utc);
                CREATE INDEX IF NOT EXISTS ix_cm_action_intent_mismatch_key
                    ON cm_action_intent_mismatches (action_idempotency_key, observed_at_utc);
                """,
            )

    def _connect(self) -> Any:
        if self.backend == "sqlite":
            conn = sqlite3.connect(_sqlite_path(self.locator))
            conn.row_factory = sqlite3.Row
            return conn
        return psycopg.connect(self.locator)


@dataclass(frozen=True)
class _StoredActionIntent:
    action_id: str
    case_id: str
    source_case_event_id: str
    action_kind: str
    target_ref: dict[str, str]
    reason_code: str
    evidence_refs: list[dict[str, str]]
    pins: dict[str, Any]
    intent: ActionIntent


def load_action_emission_policy(path: Path) -> ActionEmissionPolicy:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CaseActionHandshakeError("action emission policy must be a mapping")

    version = _require_non_empty(payload.get("version"), "version")
    policy_id = _require_non_empty(payload.get("policy_id"), "policy_id")
    revision = _require_non_empty(payload.get("revision"), "revision")

    action_emission = payload.get("action_emission")
    if not isinstance(action_emission, Mapping):
        raise CaseActionHandshakeError("action_emission section is required")

    allowed_action_kinds = tuple(
        sorted(
            {
                _require_non_empty(item, "allowed_action_kinds.item")
                for item in _require_list(action_emission.get("allowed_action_kinds"), "allowed_action_kinds")
            }
        )
    )
    allowed_actor_prefixes = tuple(
        sorted(
            {
                _require_non_empty(item, "allowed_actor_prefixes.item")
                for item in _require_list(action_emission.get("allowed_actor_prefixes"), "allowed_actor_prefixes")
            }
        )
    )
    allowed_source_types = tuple(
        sorted(
            {
                _normalize_source_type(item)
                for item in _require_list(action_emission.get("allowed_source_types"), "allowed_source_types")
            }
        )
    )
    origin = _require_non_empty(action_emission.get("origin"), "origin").upper()
    if origin != "CASE":
        raise CaseActionHandshakeError("origin must be CASE for CM manual action lane")

    al_policy_rev = action_emission.get("al_policy_rev")
    al_policy = dict(al_policy_rev) if isinstance(al_policy_rev, Mapping) else {}
    al_policy_id = _require_non_empty(al_policy.get("policy_id"), "al_policy_rev.policy_id")
    al_policy_revision = _require_non_empty(al_policy.get("revision"), "al_policy_rev.revision")

    max_submit_attempts = int(action_emission.get("max_submit_attempts") or 0)
    if max_submit_attempts < 1:
        raise CaseActionHandshakeError("max_submit_attempts must be >= 1")

    digest_payload = {
        "version": version,
        "policy_id": policy_id,
        "revision": revision,
        "allowed_action_kinds": list(allowed_action_kinds),
        "allowed_actor_prefixes": list(allowed_actor_prefixes),
        "allowed_source_types": list(allowed_source_types),
        "origin": origin,
        "al_policy_rev": {"policy_id": al_policy_id, "revision": al_policy_revision},
        "max_submit_attempts": max_submit_attempts,
    }
    canonical = _canonical_json(digest_payload)
    content_digest = _hash_text(canonical)

    return ActionEmissionPolicy(
        version=version,
        policy_id=policy_id,
        revision=revision,
        allowed_action_kinds=allowed_action_kinds,
        allowed_actor_prefixes=allowed_actor_prefixes,
        allowed_source_types=allowed_source_types,
        origin=origin,
        al_policy_id=al_policy_id,
        al_policy_revision=al_policy_revision,
        max_submit_attempts=max_submit_attempts,
        content_digest=content_digest,
    )


def _map_submit_status(*, write_status: str, reason_code: str | None) -> tuple[str, str | None]:
    normalized_status = _normalize_submit_writer_status(write_status)
    normalized_reason = _normalize_optional(reason_code)
    if normalized_status == AL_SUBMIT_ACCEPTED:
        return SUBMIT_SUBMITTED, normalized_reason or "AL_SUBMIT_ACCEPTED"
    if normalized_status == AL_SUBMIT_REJECTED:
        return SUBMIT_PRECHECK_REJECTED, normalized_reason or "AL_SUBMIT_REJECTED"
    return SUBMIT_FAILED_RETRYABLE, normalized_reason or "AL_SUBMIT_PENDING"


def _normalize_target_ref(value: Mapping[str, Any]) -> dict[str, str]:
    mapped = dict(value) if isinstance(value, Mapping) else {}
    ref_type = _require_non_empty(mapped.get("ref_type"), "target_ref.ref_type")
    ref_id = _require_non_empty(mapped.get("ref_id"), "target_ref.ref_id")
    return {"ref_type": ref_type, "ref_id": ref_id}


def _normalize_evidence_refs(values: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for item in values:
        mapped = dict(item) if isinstance(item, Mapping) else {}
        ref_type = _require_non_empty(mapped.get("ref_type"), "evidence_ref.ref_type")
        ref_id = _require_non_empty(mapped.get("ref_id"), "evidence_ref.ref_id")
        refs.append({"ref_type": ref_type, "ref_id": ref_id})
    refs.sort(key=lambda item: (item["ref_type"], item["ref_id"]))
    return refs


def _normalize_decision_id(
    value: str | None,
    *,
    case_id: str,
    source_case_event_id: str,
    action_kind: str,
) -> str:
    if value is not None and str(value).strip():
        candidate = _require_non_empty(value, "decision_id")
        if not _is_hex32(candidate):
            raise CaseActionHandshakeError("decision_id must be 32-char lowercase hex")
        return candidate
    seed = f"{case_id}:{source_case_event_id}:{action_kind}"
    return _hash_with_recipe("cm.action_intent.decision_id.v1", {"seed": seed})[:32]


def _normalize_run_config_digest(value: str | None, *, pins: Mapping[str, Any]) -> str:
    if value is not None and str(value).strip():
        digest = _require_non_empty(value, "run_config_digest")
        if not _is_hex64(digest):
            raise CaseActionHandshakeError("run_config_digest must be 64-char lowercase hex")
        return digest
    seed = {
        "platform_run_id": str(pins.get("platform_run_id") or ""),
        "scenario_run_id": str(pins.get("scenario_run_id") or ""),
        "manifest_fingerprint": str(pins.get("manifest_fingerprint") or ""),
        "parameter_hash": str(pins.get("parameter_hash") or ""),
        "scenario_id": str(pins.get("scenario_id") or ""),
        "seed": int(pins.get("seed") or 0),
    }
    return _hash_with_recipe("cm.action_intent.run_config_digest.v1", seed)


def _deterministic_action_idempotency_key(
    *,
    case_id: str,
    source_case_event_id: str,
    action_kind: str,
    target_ref: Mapping[str, str],
) -> str:
    payload = {
        "case_id": case_id,
        "source_case_event_id": source_case_event_id,
        "action_kind": action_kind,
        "target_ref": {
            "ref_type": str(target_ref.get("ref_type") or ""),
            "ref_id": str(target_ref.get("ref_id") or ""),
        },
    }
    return _hash_with_recipe("cm.action_intent.idempotency_key.v1", payload)


def _deterministic_action_id(
    *,
    case_id: str,
    source_case_event_id: str,
    action_idempotency_key: str,
) -> str:
    payload = {
        "case_id": case_id,
        "source_case_event_id": source_case_event_id,
        "action_idempotency_key": action_idempotency_key,
    }
    return _hash_with_recipe("cm.action_intent.action_id.v1", payload)[:32]


def _normalize_submit_writer_status(value: str) -> str:
    normalized = _require_non_empty(value, "writer.status").upper()
    allowed = {AL_SUBMIT_ACCEPTED, AL_SUBMIT_REJECTED, AL_SUBMIT_PENDING}
    if normalized not in allowed:
        raise CaseActionHandshakeError(
            f"writer status unsupported: {normalized!r}; allowed={','.join(sorted(allowed))}"
        )
    return normalized


def _normalize_source_type(value: str) -> str:
    normalized = _require_non_empty(value, "source_type").upper()
    allowed = {"SYSTEM", "HUMAN", "EXTERNAL", "AUTO"}
    if normalized not in allowed:
        raise CaseActionHandshakeError(
            f"unsupported source_type: {normalized!r}; allowed={','.join(sorted(allowed))}"
        )
    return normalized


def _normalize_outcome_class(value: str) -> str:
    normalized = _require_non_empty(value, "outcome_status").upper()
    if normalized not in OUTCOME_ALLOWED_CLASSES:
        raise CaseActionHandshakeError(
            f"unsupported outcome_status: {normalized!r}; allowed={','.join(sorted(OUTCOME_ALLOWED_CLASSES))}"
        )
    return normalized


def _is_hex32(value: str) -> bool:
    return len(value) == 32 and all(ch in "0123456789abcdef" for ch in value)


def _is_hex64(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _hash_with_recipe(recipe: str, payload: Mapping[str, Any]) -> str:
    canonical = _canonical_json({"recipe": recipe, "payload": _normalize_generic(dict(payload))})
    return _hash_text(canonical)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _json_to_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CaseActionHandshakeError("invalid stored intent_json") from exc
    if not isinstance(parsed, Mapping):
        raise CaseActionHandshakeError("stored intent_json must decode to mapping")
    return dict(parsed)


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


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise CaseActionHandshakeError(f"{field_name} must be a non-empty list")
    return value


def _require_non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseActionHandshakeError(f"{field_name} is required")
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
