"""CaseTrigger run-scoped observability and governance helpers (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.case_mgmt.contracts import CaseTrigger
from fraud_detection.platform_governance import emit_platform_governance_event
from fraud_detection.platform_governance.anomaly_taxonomy import classify_anomaly
from fraud_detection.platform_provenance import runtime_provenance
from fraud_detection.platform_runtime import RUNS_ROOT
from fraud_detection.scenario_runner.storage import ObjectStore

from .publish import (
    PUBLISH_ADMIT,
    PUBLISH_AMBIGUOUS,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
)


class CaseTriggerObservabilityError(ValueError):
    """Raised when CaseTrigger observability inputs are invalid."""


@dataclass
class CaseTriggerRunMetrics:
    platform_run_id: str
    scenario_run_id: str
    counters: dict[str, int] = field(default_factory=dict)
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    max_recent_events: int = 50

    def __post_init__(self) -> None:
        self.platform_run_id = _non_empty(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _non_empty(self.scenario_run_id, "scenario_run_id")
        if self.max_recent_events <= 0:
            raise CaseTriggerObservabilityError("max_recent_events must be > 0")
        for key in _REQUIRED_COUNTERS:
            self.counters.setdefault(key, 0)

    def record_trigger_seen(self, *, trigger_payload: Mapping[str, Any] | CaseTrigger) -> None:
        trigger = _normalize_trigger(trigger_payload)
        _validate_trigger_scope(
            trigger,
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
        )
        self.counters["triggers_seen"] += 1
        self._append_event(
            "trigger_seen",
            {
                "case_trigger_id": trigger.case_trigger_id,
                "case_id": trigger.case_id,
                "trigger_type": trigger.trigger_type,
                "source_ref_id": trigger.source_ref_id,
            },
        )

    def record_publish(self, *, decision: str, reason_code: str | None = None) -> None:
        normalized = str(decision or "").strip().upper()
        if normalized == PUBLISH_ADMIT:
            self.counters["published"] += 1
        elif normalized == PUBLISH_DUPLICATE:
            self.counters["duplicates"] += 1
        elif normalized == PUBLISH_QUARANTINE:
            self.counters["quarantine"] += 1
        elif normalized == PUBLISH_AMBIGUOUS:
            self.counters["publish_ambiguous"] += 1
        else:
            raise CaseTriggerObservabilityError(f"unsupported publish decision: {normalized!r}")
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

    def export(self, *, output_path: str | Path | None = None, generated_at_utc: str | None = None) -> dict[str, Any]:
        payload = self.snapshot(generated_at_utc=generated_at_utc)
        path = Path(output_path) if output_path else _default_metrics_path(self.platform_run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload

    def _append_event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        self.recent_events.append(
            {
                "event_type": str(event_type),
                "ts_utc": _utc_now(),
                "payload": dict(payload),
            }
        )
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events = self.recent_events[-self.max_recent_events :]


@dataclass(frozen=True)
class CaseTriggerGovernanceEmitter:
    store: ObjectStore
    platform_run_id: str
    scenario_run_id: str
    run_config_digest: str | None = None
    source_component: str = "case_trigger"
    environment: str | None = None
    config_revision: str | None = None

    def emit_collision_anomaly(
        self,
        *,
        case_trigger_id: str,
        reason_code: str = "CASE_TRIGGER_PAYLOAD_MISMATCH",
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        trigger_id = _non_empty(case_trigger_id, "case_trigger_id")
        code = _non_empty(reason_code, "reason_code").upper()
        merged = {
            "corridor": "case_trigger",
            "anomaly_kind": "TRIGGER_COLLISION",
            "case_trigger_id": trigger_id,
            "reason_code": code,
            "anomaly_category": classify_anomaly(code),
            "run_config_digest": self.run_config_digest,
            "provenance": runtime_provenance(
                component=self.source_component,
                environment=self.environment,
                config_revision=self.config_revision,
                run_config_digest=self.run_config_digest,
            ),
        }
        if details:
            merged["details"] = dict(details)
        return self._emit(
            dedupe_key=f"{trigger_id}:collision:{code}",
            details=merged,
        )

    def emit_publish_anomaly(
        self,
        *,
        case_trigger_id: str,
        publish_decision: str,
        reason_code: str | None = None,
        receipt_ref: str | None = None,
    ) -> dict[str, Any] | None:
        trigger_id = _non_empty(case_trigger_id, "case_trigger_id")
        decision = str(publish_decision or "").strip().upper()
        if decision not in {PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}:
            raise CaseTriggerObservabilityError(
                "publish anomaly can only be emitted for QUARANTINE or AMBIGUOUS decisions"
            )
        code = str(reason_code or decision).strip().upper()
        details: dict[str, Any] = {
            "corridor": "case_trigger",
            "anomaly_kind": "PUBLISH_OUTCOME",
            "case_trigger_id": trigger_id,
            "publish_decision": decision,
            "reason_code": code,
            "anomaly_category": classify_anomaly(code),
            "run_config_digest": self.run_config_digest,
            "provenance": runtime_provenance(
                component=self.source_component,
                environment=self.environment,
                config_revision=self.config_revision,
                run_config_digest=self.run_config_digest,
            ),
        }
        if receipt_ref:
            details["evidence_refs"] = [{"ref_type": "receipt_ref", "ref_id": str(receipt_ref)}]
        return self._emit(
            dedupe_key=f"{trigger_id}:publish:{decision}:{code}",
            details=details,
        )

    def _emit(self, *, dedupe_key: str, details: dict[str, Any]) -> dict[str, Any] | None:
        return emit_platform_governance_event(
            store=self.store,
            event_family="CORRIDOR_ANOMALY",
            actor_id="SYSTEM::case_trigger",
            source_type="SYSTEM",
            source_component=self.source_component,
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
            dedupe_key=dedupe_key,
            details=details,
        )


def _normalize_trigger(value: Mapping[str, Any] | CaseTrigger) -> CaseTrigger:
    if isinstance(value, CaseTrigger):
        return value
    if not isinstance(value, Mapping):
        raise CaseTriggerObservabilityError("trigger_payload must be a mapping")
    try:
        return CaseTrigger.from_payload(value)
    except Exception as exc:
        raise CaseTriggerObservabilityError(f"invalid case trigger payload: {exc}") from exc


def _validate_trigger_scope(trigger: CaseTrigger, *, platform_run_id: str, scenario_run_id: str) -> None:
    pins = trigger.pins
    got_platform = str(pins.get("platform_run_id") or "").strip()
    got_scenario = str(pins.get("scenario_run_id") or "").strip()
    if got_platform != platform_run_id:
        raise CaseTriggerObservabilityError(
            f"platform_run_id mismatch: expected {platform_run_id!r}, got {got_platform!r}"
        )
    if got_scenario != scenario_run_id:
        raise CaseTriggerObservabilityError(
            f"scenario_run_id mismatch: expected {scenario_run_id!r}, got {got_scenario!r}"
        )


def _default_metrics_path(platform_run_id: str) -> Path:
    return RUNS_ROOT / platform_run_id / "case_trigger" / "metrics" / "last_metrics.json"


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseTriggerObservabilityError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_REQUIRED_COUNTERS: tuple[str, ...] = (
    "triggers_seen",
    "published",
    "duplicates",
    "quarantine",
    "publish_ambiguous",
)
