"""Decision Log & Audit observability, reconciliation, and security helpers (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.platform_runtime import RUNS_ROOT

from .storage import DecisionLogAuditIntakeStore


class DecisionLogAuditObservabilityError(ValueError):
    """Raised when DLA observability/reconciliation inputs are invalid."""


@dataclass(frozen=True)
class DecisionLogAuditHealthThresholds:
    amber_checkpoint_age_seconds: float = 120.0
    red_checkpoint_age_seconds: float = 300.0
    amber_quarantine_total: int = 1
    red_quarantine_total: int = 25
    amber_unresolved_total: int = 1
    red_unresolved_total: int = 20
    amber_append_failure_total: int = 1
    red_append_failure_total: int = 5
    amber_replay_divergence_total: int = 1
    red_replay_divergence_total: int = 1


@dataclass(frozen=True)
class DecisionLogAuditSecurityPolicy:
    allow_custom_output_root: bool = False
    allowed_root: Path = RUNS_ROOT

    def resolve_output_root(self, *, platform_run_id: str, output_root: Path | None = None) -> Path:
        default_root = RUNS_ROOT / platform_run_id
        if output_root is None:
            return default_root
        candidate = Path(output_root).resolve()
        if not self.allow_custom_output_root:
            raise DecisionLogAuditObservabilityError("custom output root is not allowed by security policy")
        allowed_root = Path(self.allowed_root).resolve()
        try:
            candidate.relative_to(allowed_root)
        except ValueError as exc:
            raise DecisionLogAuditObservabilityError("output root outside allowed root") from exc
        return candidate


@dataclass
class DecisionLogAuditObservabilityReporter:
    store: DecisionLogAuditIntakeStore
    platform_run_id: str
    scenario_run_id: str
    thresholds: DecisionLogAuditHealthThresholds = DecisionLogAuditHealthThresholds()
    security_policy: DecisionLogAuditSecurityPolicy = DecisionLogAuditSecurityPolicy()

    def __post_init__(self) -> None:
        self.platform_run_id = _non_empty(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _non_empty(self.scenario_run_id, "scenario_run_id")

    def collect(self) -> dict[str, Any]:
        generated_at_utc = _utc_now()
        metrics = self.store.intake_metrics_snapshot(
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
        )
        checkpoints = self.store.checkpoint_summary()
        quarantine_reasons = self.store.quarantine_reason_counts(
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
        )
        governance = self.store.governance_stamp_summary(
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
        )
        recent_attempts = self.store.recent_attempts(
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
            limit=25,
        )
        checkpoint_age_seconds = _age_seconds(checkpoints.get("latest_checkpoint_updated_at_utc"))
        watermark_age_seconds = _age_seconds(checkpoints.get("watermark_ts_utc"))

        health = _derive_health(
            metrics=metrics,
            checkpoint_age_seconds=checkpoint_age_seconds,
            thresholds=self.thresholds,
        )
        return {
            "generated_at_utc": generated_at_utc,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "metrics": metrics,
            "checkpoints": checkpoints,
            "checkpoint_age_seconds": checkpoint_age_seconds,
            "watermark_age_seconds": watermark_age_seconds,
            "health_state": health["state"],
            "health_reasons": health["reasons"],
            "reconciliation": {
                "lineage": {
                    "resolved_total": int(metrics.get("lineage_resolved_total", 0)),
                    "unresolved_total": int(metrics.get("lineage_unresolved_total", 0)),
                },
                "anomaly_lanes": quarantine_reasons,
                "recent_attempts": recent_attempts,
            },
            "governance_stamps": governance,
        }

    def export(self, *, output_root: Path | None = None) -> dict[str, Any]:
        payload = self.collect()
        run_root = self.security_policy.resolve_output_root(
            platform_run_id=self.platform_run_id,
            output_root=output_root,
        )
        base = run_root / "decision_log_audit"
        metrics_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "metrics": payload["metrics"],
            "checkpoints": payload["checkpoints"],
            "checkpoint_age_seconds": payload["checkpoint_age_seconds"],
            "watermark_age_seconds": payload["watermark_age_seconds"],
        }
        health_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
            "metrics": payload["metrics"],
            "checkpoints": payload["checkpoints"],
        }
        reconciliation_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "reconciliation": payload["reconciliation"],
            "governance_stamps": payload["governance_stamps"],
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
        }
        _write_json(base / "metrics" / "last_metrics.json", metrics_payload)
        _write_json(base / "health" / "last_health.json", health_payload)
        _write_json(base / "reconciliation" / "last_reconciliation.json", redact_sensitive_fields(reconciliation_payload))
        return payload


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
    if isinstance(value, str):
        lowered = value.lower()
        for marker in _SENSITIVE_KEY_MARKERS:
            token = f"{marker}="
            if token in lowered:
                return "[REDACTED]"
    return value


def _derive_health(
    *,
    metrics: Mapping[str, int],
    checkpoint_age_seconds: float | None,
    thresholds: DecisionLogAuditHealthThresholds,
) -> dict[str, Any]:
    state = "GREEN"
    reasons: list[str] = []

    if checkpoint_age_seconds is None:
        reasons.append("CHECKPOINT_MISSING")
        state = "AMBER"
    elif checkpoint_age_seconds >= thresholds.red_checkpoint_age_seconds:
        reasons.append("CHECKPOINT_TOO_OLD")
        state = "RED"
    elif checkpoint_age_seconds >= thresholds.amber_checkpoint_age_seconds:
        reasons.append("CHECKPOINT_OLD")
        if state != "RED":
            state = "AMBER"

    quarantine_total = int(metrics.get("quarantine_total", 0))
    unresolved_total = int(metrics.get("lineage_unresolved_total", 0))
    append_failure_total = int(metrics.get("append_failure_total", 0))
    replay_divergence_total = int(metrics.get("replay_divergence_total", 0))

    if quarantine_total >= thresholds.red_quarantine_total:
        reasons.append("QUARANTINE_RED")
        state = "RED"
    elif quarantine_total >= thresholds.amber_quarantine_total:
        reasons.append("QUARANTINE_AMBER")
        if state != "RED":
            state = "AMBER"

    if unresolved_total >= thresholds.red_unresolved_total:
        reasons.append("UNRESOLVED_RED")
        state = "RED"
    elif unresolved_total >= thresholds.amber_unresolved_total:
        reasons.append("UNRESOLVED_AMBER")
        if state != "RED":
            state = "AMBER"

    if append_failure_total >= thresholds.red_append_failure_total:
        reasons.append("APPEND_FAILURE_RED")
        state = "RED"
    elif append_failure_total >= thresholds.amber_append_failure_total:
        reasons.append("APPEND_FAILURE_AMBER")
        if state != "RED":
            state = "AMBER"

    if replay_divergence_total >= thresholds.red_replay_divergence_total:
        reasons.append("REPLAY_DIVERGENCE_RED")
        state = "RED"
    elif replay_divergence_total >= thresholds.amber_replay_divergence_total:
        reasons.append("REPLAY_DIVERGENCE_AMBER")
        if state != "RED":
            state = "AMBER"

    return {"state": state, "reasons": reasons}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _non_empty(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionLogAuditObservabilityError(f"{field_name} is required")
    return text


def _parse_ts(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _age_seconds(value: str | None) -> float | None:
    ts = _parse_ts(value)
    if ts is None:
        return None
    return max(0.0, (datetime.now(tz=timezone.utc) - ts).total_seconds())


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    if not lowered:
        return False
    for marker in _SENSITIVE_KEY_MARKERS:
        if marker in lowered:
            return True
    return False


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

