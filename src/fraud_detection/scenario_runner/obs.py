"""Structured observability events for SR (best-effort, non-blocking)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any


class ObsPhase(str, Enum):
    INGRESS = "INGRESS"
    AUTHORITY = "AUTHORITY"
    PLAN = "PLAN"
    ENGINE = "ENGINE"
    EVIDENCE = "EVIDENCE"
    COMMIT = "COMMIT"
    REEMIT = "REEMIT"


class ObsOutcome(str, Enum):
    OK = "OK"
    WAITING = "WAITING"
    FAIL = "FAIL"
    CONFLICT = "CONFLICT"
    SKIP = "SKIP"
    RETRY = "RETRY"


class ObsSeverity(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ObsEvent:
    event_kind: str
    phase: ObsPhase
    outcome: ObsOutcome
    severity: ObsSeverity
    pins: dict[str, Any]
    ts_utc: str
    policy_rev: dict[str, Any] | None = None
    attempt_id: str | None = None
    details: dict[str, Any] | None = None

    @classmethod
    def now(
        cls,
        *,
        event_kind: str,
        phase: ObsPhase,
        outcome: ObsOutcome,
        severity: ObsSeverity,
        pins: dict[str, Any],
        policy_rev: dict[str, Any] | None = None,
        attempt_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "ObsEvent":
        return cls(
            event_kind=event_kind,
            phase=phase,
            outcome=outcome,
            severity=severity,
            pins=pins,
            ts_utc=datetime.now(tz=timezone.utc).isoformat(),
            policy_rev=policy_rev,
            attempt_id=attempt_id,
            details=details,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "event_kind": self.event_kind,
            "phase": self.phase.value,
            "outcome": self.outcome.value,
            "severity": self.severity.value,
            "pins": self.pins,
            "ts_utc": self.ts_utc,
        }
        if self.policy_rev:
            payload["policy_rev"] = self.policy_rev
        if self.attempt_id:
            payload["attempt_id"] = self.attempt_id
        if self.details:
            payload["details"] = self.details
        return payload


class ObsSink:
    def emit(self, event: ObsEvent) -> None:
        raise NotImplementedError


class NullObsSink(ObsSink):
    def emit(self, event: ObsEvent) -> None:
        return


class CompositeObsSink(ObsSink):
    def __init__(self, sinks: list[ObsSink]) -> None:
        self.sinks = sinks

    def emit(self, event: ObsEvent) -> None:
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception:
                continue


class ConsoleObsSink(ObsSink):
    def emit(self, event: ObsEvent) -> None:
        payload = json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=True)
        print(payload)


class MetricsObsSink(ObsSink):
    def __init__(self) -> None:
        self.counters: Counter[str] = Counter()
        self.outcome_counters: Counter[str] = Counter()
        self.duration_ms: dict[str, list[int]] = defaultdict(list)

    def emit(self, event: ObsEvent) -> None:
        self.counters[event.event_kind] += 1
        self.outcome_counters[event.outcome.value] += 1
        if event.details:
            duration = event.details.get("duration_ms")
            if isinstance(duration, int):
                self.duration_ms[event.event_kind].append(duration)

    def snapshot(self) -> dict[str, Any]:
        durations = {
            key: {
                "count": len(values),
                "min_ms": min(values) if values else None,
                "max_ms": max(values) if values else None,
                "avg_ms": int(sum(values) / len(values)) if values else None,
            }
            for key, values in self.duration_ms.items()
        }
        return {
            "counters": dict(self.counters),
            "outcomes": dict(self.outcome_counters),
            "durations": durations,
        }


class OtlpObsSink(ObsSink):
    """Feature-flagged scaffold; does nothing until OTLP is wired."""

    def emit(self, event: ObsEvent) -> None:
        return
