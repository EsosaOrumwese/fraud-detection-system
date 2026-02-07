"""Action Layer executor adapters and retry semantics (Phase 4)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any, Protocol

from .contracts import ActionIntent
from .policy import AlRetryPolicy


EXECUTION_COMMITTED = "COMMITTED"
EXECUTION_RETRYABLE_ERROR = "RETRYABLE_ERROR"
EXECUTION_PERMANENT_ERROR = "PERMANENT_ERROR"
EXECUTION_UNKNOWN_COMMIT = "UNKNOWN_COMMIT"

TERMINAL_EXECUTED = "EXECUTED"
TERMINAL_FAILED = "FAILED"
TERMINAL_UNCERTAIN_COMMIT = "UNCERTAIN_COMMIT"


class ActionExecutionError(ValueError):
    """Raised when AL execution inputs/results are invalid."""


@dataclass(frozen=True)
class ActionExecutionRequest:
    action_kind: str
    action_payload: dict[str, Any]
    idempotency_token: str
    attempt_seq: int


@dataclass(frozen=True)
class ActionExecutionResult:
    state: str
    provider_code: str
    provider_ref: str | None = None
    message: str = ""


class ActionEffectExecutor(Protocol):
    def execute(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        ...


@dataclass(frozen=True)
class ActionExecutionAttempt:
    attempt_seq: int
    state: str
    provider_code: str
    provider_ref: str | None
    message: str

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "attempt_seq": self.attempt_seq,
            "state": self.state,
            "provider_code": self.provider_code,
            "message": self.message,
        }
        if self.provider_ref:
            payload["provider_ref"] = self.provider_ref
        return payload


@dataclass(frozen=True)
class ActionExecutionTerminal:
    terminal_state: str
    reason_code: str
    final_attempt_seq: int
    attempts: tuple[ActionExecutionAttempt, ...]
    final_provider_code: str
    final_provider_ref: str | None


@dataclass
class ActionExecutionEngine:
    executor: ActionEffectExecutor
    retry_policy: AlRetryPolicy
    sleeper: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if self.retry_policy.max_attempts <= 0:
            raise ActionExecutionError("retry_policy.max_attempts must be > 0")
        if self.retry_policy.base_backoff_ms <= 0:
            raise ActionExecutionError("retry_policy.base_backoff_ms must be > 0")
        if self.retry_policy.max_backoff_ms < self.retry_policy.base_backoff_ms:
            raise ActionExecutionError("retry_policy.max_backoff_ms must be >= base_backoff_ms")

    def execute(self, *, intent: ActionIntent, semantic_key: str) -> ActionExecutionTerminal:
        attempts: list[ActionExecutionAttempt] = []
        for attempt_seq in range(1, self.retry_policy.max_attempts + 1):
            request = ActionExecutionRequest(
                action_kind=str(intent.payload["action_kind"]),
                action_payload=dict(intent.payload.get("action_payload") or {}),
                idempotency_token=semantic_key,
                attempt_seq=attempt_seq,
            )
            result = self.executor.execute(request)
            _validate_execution_result(result)
            attempt = ActionExecutionAttempt(
                attempt_seq=attempt_seq,
                state=result.state,
                provider_code=result.provider_code,
                provider_ref=result.provider_ref,
                message=result.message,
            )
            attempts.append(attempt)

            if result.state == EXECUTION_COMMITTED:
                return ActionExecutionTerminal(
                    terminal_state=TERMINAL_EXECUTED,
                    reason_code="EXECUTED",
                    final_attempt_seq=attempt_seq,
                    attempts=tuple(attempts),
                    final_provider_code=result.provider_code,
                    final_provider_ref=result.provider_ref,
                )
            if result.state == EXECUTION_PERMANENT_ERROR:
                return ActionExecutionTerminal(
                    terminal_state=TERMINAL_FAILED,
                    reason_code=f"PERMANENT_ERROR:{result.provider_code}",
                    final_attempt_seq=attempt_seq,
                    attempts=tuple(attempts),
                    final_provider_code=result.provider_code,
                    final_provider_ref=result.provider_ref,
                )
            if result.state == EXECUTION_UNKNOWN_COMMIT:
                return ActionExecutionTerminal(
                    terminal_state=TERMINAL_UNCERTAIN_COMMIT,
                    reason_code=f"UNCERTAIN_COMMIT:{result.provider_code}",
                    final_attempt_seq=attempt_seq,
                    attempts=tuple(attempts),
                    final_provider_code=result.provider_code,
                    final_provider_ref=result.provider_ref,
                )
            if result.state == EXECUTION_RETRYABLE_ERROR:
                if attempt_seq < self.retry_policy.max_attempts:
                    delay_ms = self.backoff_for_attempt_ms(attempt_seq)
                    self.sleeper(delay_ms / 1000.0)
                    continue
                return ActionExecutionTerminal(
                    terminal_state=TERMINAL_FAILED,
                    reason_code=f"RETRY_EXHAUSTED:{result.provider_code}",
                    final_attempt_seq=attempt_seq,
                    attempts=tuple(attempts),
                    final_provider_code=result.provider_code,
                    final_provider_ref=result.provider_ref,
                )
            raise ActionExecutionError(f"unsupported execution state: {result.state!r}")

        # Defensive fallback; the loop always returns.
        raise ActionExecutionError("execution terminated without terminal state")

    def backoff_schedule_ms(self) -> tuple[int, ...]:
        values: list[int] = []
        for attempt_seq in range(1, self.retry_policy.max_attempts + 1):
            values.append(self.backoff_for_attempt_ms(attempt_seq))
        return tuple(values)

    def backoff_for_attempt_ms(self, attempt_seq: int) -> int:
        if attempt_seq <= 0:
            raise ActionExecutionError("attempt_seq must be >= 1")
        delay = self.retry_policy.base_backoff_ms * (2 ** (attempt_seq - 1))
        return min(delay, self.retry_policy.max_backoff_ms)


def build_execution_outcome_payload(
    *,
    intent: ActionIntent,
    authz_policy_rev: dict[str, Any],
    terminal: ActionExecutionTerminal,
    completed_at_utc: str | None = None,
) -> dict[str, Any]:
    payload = intent.as_dict()
    ts = completed_at_utc or datetime.now(tz=timezone.utc).isoformat()
    status = TERMINAL_EXECUTED if terminal.terminal_state == TERMINAL_EXECUTED else TERMINAL_FAILED
    identity = {
        "decision_id": payload["decision_id"],
        "action_id": payload["action_id"],
        "idempotency_key": payload["idempotency_key"],
        "terminal_state": terminal.terminal_state,
        "reason_code": terminal.reason_code,
        "final_attempt_seq": terminal.final_attempt_seq,
    }
    outcome_id = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:32]
    outcome_payload = {
        "terminal_state": terminal.terminal_state,
        "reason_code": terminal.reason_code,
        "final_provider_code": terminal.final_provider_code,
        "final_provider_ref": terminal.final_provider_ref,
        "attempts": [item.as_dict() for item in terminal.attempts],
    }
    return {
        "outcome_id": outcome_id,
        "decision_id": payload["decision_id"],
        "action_id": payload["action_id"],
        "action_kind": payload["action_kind"],
        "status": status,
        "idempotency_key": payload["idempotency_key"],
        "actor_principal": payload["actor_principal"],
        "origin": payload["origin"],
        "authz_policy_rev": dict(authz_policy_rev),
        "run_config_digest": payload["run_config_digest"],
        "pins": payload["pins"],
        "completed_at_utc": ts,
        "attempt_seq": terminal.final_attempt_seq,
        "reason": terminal.reason_code,
        "outcome_payload": outcome_payload,
    }


def _validate_execution_result(result: ActionExecutionResult) -> None:
    if result.state not in {
        EXECUTION_COMMITTED,
        EXECUTION_RETRYABLE_ERROR,
        EXECUTION_PERMANENT_ERROR,
        EXECUTION_UNKNOWN_COMMIT,
    }:
        raise ActionExecutionError(f"invalid execution state: {result.state!r}")
    if not str(result.provider_code or "").strip():
        raise ActionExecutionError("provider_code must be non-empty")
