"""Decision Fabric run-scoped observability helpers (Phase 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.platform_runtime import RUNS_ROOT

from .context import CONTEXT_MISSING, CONTEXT_UNAVAILABLE, CONTEXT_WAITING, DECISION_DEADLINE_EXCEEDED
from .registry import RESOLUTION_FAIL_CLOSED


class DecisionFabricObservabilityError(ValueError):
    """Raised when DF observability inputs are invalid."""


@dataclass
class DfRunMetrics:
    platform_run_id: str
    scenario_run_id: str
    counters: dict[str, int] = field(default_factory=dict)
    _latency_samples_ms: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.platform_run_id = _non_empty(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _non_empty(self.scenario_run_id, "scenario_run_id")
        for key in _REQUIRED_COUNTERS:
            self.counters.setdefault(key, 0)

    def record_decision(
        self,
        *,
        decision_payload: Mapping[str, Any],
        latency_ms: float,
        publish_decision: str | None = None,
    ) -> None:
        normalized = _normalize_decision_payload(decision_payload)
        _validate_run_scope(normalized, platform_run_id=self.platform_run_id, scenario_run_id=self.scenario_run_id)
        latency_value = float(latency_ms)
        if latency_value < 0:
            raise DecisionFabricObservabilityError("latency_ms must be >= 0")
        self._latency_samples_ms.append(latency_value)
        self.counters["decisions_total"] += 1

        reasons = tuple(str(item) for item in list(normalized.get("reason_codes") or []))
        decision_obj = _mapping_or_empty(normalized.get("decision"))
        degrade_mode = str(_mapping_or_empty(normalized.get("degrade_posture")).get("mode") or "").strip().upper()
        context_status = str(decision_obj.get("context_status") or "").strip().upper()
        registry_outcome = str(decision_obj.get("registry_outcome") or "").strip().upper()

        if _is_degrade(
            degrade_mode=degrade_mode,
            context_status=context_status,
            registry_outcome=registry_outcome,
            reason_codes=reasons,
        ):
            self.counters["degrade_total"] += 1
        if _is_missing_context(context_status=context_status, reason_codes=reasons):
            self.counters["missing_context_total"] += 1
        if _is_resolver_failure(registry_outcome=registry_outcome, reason_codes=reasons):
            self.counters["resolver_failures_total"] += 1
        if _is_fail_closed(degrade_mode=degrade_mode, reason_codes=reasons):
            self.counters["fail_closed_total"] += 1

        if publish_decision:
            normalized_publish = str(publish_decision).strip().upper()
            if normalized_publish == "ADMIT":
                self.counters["publish_admit_total"] += 1
            elif normalized_publish == "DUPLICATE":
                self.counters["publish_duplicate_total"] += 1
            elif normalized_publish == "QUARANTINE":
                self.counters["publish_quarantine_total"] += 1
            else:
                raise DecisionFabricObservabilityError(f"unsupported publish decision: {normalized_publish}")

    def snapshot(self, *, generated_at_utc: str | None = None) -> dict[str, Any]:
        payload = {
            "generated_at_utc": generated_at_utc or _utc_now(),
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "metrics": dict(self.counters),
            "latency_ms": {
                "count": len(self._latency_samples_ms),
                "p50": _percentile(self._latency_samples_ms, 0.50),
                "p95": _percentile(self._latency_samples_ms, 0.95),
                "p99": _percentile(self._latency_samples_ms, 0.99),
                "max": max(self._latency_samples_ms) if self._latency_samples_ms else 0.0,
            },
        }
        return payload

    def export(self, *, output_path: str | Path | None = None, generated_at_utc: str | None = None) -> dict[str, Any]:
        payload = self.snapshot(generated_at_utc=generated_at_utc)
        path = Path(output_path) if output_path else _default_metrics_path(self.platform_run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload


def _default_metrics_path(platform_run_id: str) -> Path:
    return RUNS_ROOT / platform_run_id / "decision_fabric" / "metrics" / "last_metrics.json"


def _normalize_decision_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DecisionFabricObservabilityError("decision_payload must be a mapping")
    normalized = dict(payload)
    decision_id = str(normalized.get("decision_id") or "").strip()
    if not decision_id:
        raise DecisionFabricObservabilityError("decision_payload.decision_id is required")
    return normalized


def _validate_run_scope(payload: Mapping[str, Any], *, platform_run_id: str, scenario_run_id: str) -> None:
    pins = _mapping_or_empty(payload.get("pins"))
    payload_platform_run_id = str(pins.get("platform_run_id") or "").strip()
    payload_scenario_run_id = str(pins.get("scenario_run_id") or "").strip()
    if payload_platform_run_id != platform_run_id:
        raise DecisionFabricObservabilityError(
            f"platform_run_id mismatch: expected {platform_run_id!r}, got {payload_platform_run_id!r}"
        )
    if payload_scenario_run_id != scenario_run_id:
        raise DecisionFabricObservabilityError(
            f"scenario_run_id mismatch: expected {scenario_run_id!r}, got {payload_scenario_run_id!r}"
        )


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _is_degrade(
    *,
    degrade_mode: str,
    context_status: str,
    registry_outcome: str,
    reason_codes: tuple[str, ...],
) -> bool:
    if degrade_mode not in {"", "NORMAL"}:
        return True
    if _is_missing_context(context_status=context_status, reason_codes=reason_codes):
        return True
    if registry_outcome == RESOLUTION_FAIL_CLOSED:
        return True
    return any(item.startswith("DEGRADE_") for item in reason_codes)


def _is_missing_context(*, context_status: str, reason_codes: tuple[str, ...]) -> bool:
    if context_status in {
        CONTEXT_MISSING,
        CONTEXT_WAITING,
        CONTEXT_UNAVAILABLE,
        DECISION_DEADLINE_EXCEEDED,
    }:
        return True
    return any(
        item.startswith("CONTEXT_MISSING:")
        or item.startswith("CONTEXT_WAITING:")
        or item.startswith("JOIN_WAIT_EXCEEDED")
        for item in reason_codes
    )


def _is_resolver_failure(*, registry_outcome: str, reason_codes: tuple[str, ...]) -> bool:
    if registry_outcome == RESOLUTION_FAIL_CLOSED:
        return True
    return any(
        item.startswith("REGISTRY_")
        or item.startswith("BUNDLE_")
        or item.startswith("RESOLUTION_FAIL_CLOSED")
        for item in reason_codes
    )


def _is_fail_closed(*, degrade_mode: str, reason_codes: tuple[str, ...]) -> bool:
    if degrade_mode in {"FAIL_CLOSED", "BLOCKED"}:
        return True
    return any("FAIL_CLOSED" in item for item in reason_codes)


def _percentile(samples: list[float], quantile: float) -> float:
    if not samples:
        return 0.0
    bounded_q = min(max(float(quantile), 0.0), 1.0)
    sorted_values = sorted(samples)
    rank = max(1, int(math.ceil(len(sorted_values) * bounded_q)))
    return float(sorted_values[rank - 1])


def _non_empty(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionFabricObservabilityError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_REQUIRED_COUNTERS = (
    "decisions_total",
    "degrade_total",
    "missing_context_total",
    "resolver_failures_total",
    "fail_closed_total",
    "publish_admit_total",
    "publish_duplicate_total",
    "publish_quarantine_total",
)
