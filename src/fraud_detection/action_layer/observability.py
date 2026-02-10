"""Action Layer observability, health, and security helpers (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.platform_runtime import RUNS_ROOT

from .execution import TERMINAL_UNCERTAIN_COMMIT, ActionExecutionTerminal


class ActionLayerObservabilityError(ValueError):
    """Raised when Action Layer observability inputs are invalid."""


@dataclass(frozen=True)
class ActionLayerHealthThresholds:
    amber_lag_events: int = 10
    red_lag_events: int = 100
    amber_queue_depth: int = 100
    red_queue_depth: int = 1000
    amber_error_rate: float = 0.05
    red_error_rate: float = 0.20


@dataclass(frozen=True)
class ActionLayerHealthStatus:
    state: str
    reason_codes: tuple[str, ...]
    signals: dict[str, float]


@dataclass
class ActionLayerRunMetrics:
    platform_run_id: str
    scenario_run_id: str
    counters: dict[str, int] = field(default_factory=dict)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    max_recent_events: int = 25

    def __post_init__(self) -> None:
        self.platform_run_id = _non_empty(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _non_empty(self.scenario_run_id, "scenario_run_id")
        if self.max_recent_events <= 0:
            raise ActionLayerObservabilityError("max_recent_events must be > 0")
        for key in _REQUIRED_COUNTERS:
            self.counters.setdefault(key, 0)

    def record_intake(self, *, intent_payload: Mapping[str, Any]) -> None:
        self._validate_run_scope(intent_payload)
        self.counters["intake_total"] += 1
        self._append_event("intent_intake", intent_payload)

    def record_execution_terminal(self, *, terminal: ActionExecutionTerminal) -> None:
        attempts = len(terminal.attempts)
        retries = max(0, attempts - 1)
        self.counters["execution_attempts_total"] += attempts
        self.counters["execution_retries_total"] += retries
        if terminal.terminal_state == TERMINAL_UNCERTAIN_COMMIT:
            self.counters["unknown_commit_total"] += 1
        self._append_event(
            "execution_terminal",
            {
                "terminal_state": terminal.terminal_state,
                "reason_code": terminal.reason_code,
                "final_attempt_seq": terminal.final_attempt_seq,
                "attempt_count": attempts,
            },
        )

    def record_outcome(self, *, outcome_payload: Mapping[str, Any]) -> None:
        self._validate_run_scope(outcome_payload)
        status = str(outcome_payload.get("status") or "").strip().upper()
        if status == "EXECUTED":
            self.counters["outcome_executed_total"] += 1
        elif status == "DENIED":
            self.counters["outcome_denied_total"] += 1
        elif status == "FAILED":
            self.counters["outcome_failed_total"] += 1
        else:
            raise ActionLayerObservabilityError(f"unsupported outcome status: {status!r}")
        self._append_event("outcome", outcome_payload)

    def record_publish(self, *, decision: str, reason_code: str | None = None) -> None:
        normalized = str(decision or "").strip().upper()
        if normalized == "ADMIT":
            self.counters["publish_admit_total"] += 1
        elif normalized == "DUPLICATE":
            self.counters["publish_duplicate_total"] += 1
        elif normalized == "QUARANTINE":
            self.counters["publish_quarantine_total"] += 1
        elif normalized == "AMBIGUOUS":
            self.counters["publish_ambiguous_total"] += 1
        else:
            raise ActionLayerObservabilityError(f"unsupported publish decision: {normalized!r}")
        payload: dict[str, Any] = {"decision": normalized}
        if reason_code:
            payload["reason_code"] = str(reason_code)
        self._append_event("publish", payload)

    def snapshot(self, *, generated_at_utc: str | None = None) -> dict[str, Any]:
        return {
            "generated_at_utc": generated_at_utc or _utc_now(),
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "metrics": dict(self.counters),
            "recent_events": list(self.recent_events),
        }

    def evaluate_health(
        self,
        *,
        lag_events: int,
        queue_depth: int,
        thresholds: ActionLayerHealthThresholds | None = None,
    ) -> ActionLayerHealthStatus:
        policy = thresholds or ActionLayerHealthThresholds()
        if lag_events < 0:
            raise ActionLayerObservabilityError("lag_events must be >= 0")
        if queue_depth < 0:
            raise ActionLayerObservabilityError("queue_depth must be >= 0")

        intake_total = int(self.counters.get("intake_total", 0))
        error_total = int(self.counters.get("outcome_failed_total", 0))
        error_total += int(self.counters.get("publish_quarantine_total", 0))
        error_total += int(self.counters.get("publish_ambiguous_total", 0))
        error_rate = float(error_total) / float(max(1, intake_total))

        reasons: set[str] = set()
        state = "GREEN"

        if lag_events >= policy.red_lag_events:
            state = "RED"
            reasons.add("LAG_RED")
        elif lag_events >= policy.amber_lag_events:
            state = "AMBER"
            reasons.add("LAG_AMBER")

        if queue_depth >= policy.red_queue_depth:
            state = "RED"
            reasons.add("QUEUE_RED")
        elif queue_depth >= policy.amber_queue_depth and state != "RED":
            state = "AMBER"
            reasons.add("QUEUE_AMBER")

        if error_rate >= policy.red_error_rate:
            state = "RED"
            reasons.add("ERROR_RATE_RED")
        elif error_rate >= policy.amber_error_rate and state != "RED":
            state = "AMBER"
            reasons.add("ERROR_RATE_AMBER")

        if state == "AMBER":
            self.counters["health_amber_total"] += 1
        elif state == "RED":
            self.counters["health_red_total"] += 1

        return ActionLayerHealthStatus(
            state=state,
            reason_codes=tuple(sorted(reasons)),
            signals={
                "lag_events": float(lag_events),
                "queue_depth": float(queue_depth),
                "error_rate": error_rate,
                "error_total": float(error_total),
                "intake_total": float(intake_total),
            },
        )

    def export(self, *, output_path: str | Path | None = None, generated_at_utc: str | None = None) -> dict[str, Any]:
        payload = self.snapshot(generated_at_utc=generated_at_utc)
        path = Path(output_path) if output_path else _default_metrics_path(self.platform_run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload

    def _validate_run_scope(self, payload: Mapping[str, Any]) -> None:
        pins = payload.get("pins")
        if not isinstance(pins, Mapping):
            raise ActionLayerObservabilityError("payload.pins must be a mapping")
        platform_run_id = str(pins.get("platform_run_id") or "").strip()
        scenario_run_id = str(pins.get("scenario_run_id") or "").strip()
        if platform_run_id != self.platform_run_id:
            raise ActionLayerObservabilityError(
                f"platform_run_id mismatch: expected {self.platform_run_id!r}, got {platform_run_id!r}"
            )
        if scenario_run_id != self.scenario_run_id:
            raise ActionLayerObservabilityError(
                f"scenario_run_id mismatch: expected {self.scenario_run_id!r}, got {scenario_run_id!r}"
            )

    def _append_event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        record = {
            "event_type": str(event_type),
            "ts_utc": _utc_now(),
            "payload": redact_sensitive_fields(payload),
        }
        self.recent_events.append(record)
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events = self.recent_events[-self.max_recent_events :]


def redact_sensitive_fields(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key_raw, item in value.items():
            key = str(key_raw)
            if _looks_sensitive_key(key):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive_fields(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_fields(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive_fields(item) for item in value]
    return value


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    if not lowered:
        return False
    for marker in _SENSITIVE_KEY_MARKERS:
        if marker in lowered:
            return True
    return False


def _default_metrics_path(platform_run_id: str) -> Path:
    return RUNS_ROOT / platform_run_id / "action_layer" / "observability" / "last_metrics.json"


def _non_empty(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ActionLayerObservabilityError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_REQUIRED_COUNTERS: tuple[str, ...] = (
    "intake_total",
    "execution_attempts_total",
    "execution_retries_total",
    "outcome_executed_total",
    "outcome_denied_total",
    "outcome_failed_total",
    "unknown_commit_total",
    "publish_admit_total",
    "publish_duplicate_total",
    "publish_quarantine_total",
    "publish_ambiguous_total",
    "health_amber_total",
    "health_red_total",
)

_SENSITIVE_KEY_MARKERS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "access_key",
    "refresh_key",
    "refresh_token",
    "lease_token",
)
