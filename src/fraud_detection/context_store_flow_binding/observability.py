"""CSFB observability reporter (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml

from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id

from .store import ContextStoreFlowBindingStore, build_store


@dataclass(frozen=True)
class CsfbHealthThresholds:
    amber_watermark_age_seconds: float = 120.0
    red_watermark_age_seconds: float = 300.0
    amber_checkpoint_age_seconds: float = 120.0
    red_checkpoint_age_seconds: float = 300.0
    amber_join_misses: int = 1
    red_join_misses: int = 10
    amber_binding_conflicts: int = 1
    red_binding_conflicts: int = 5
    amber_apply_failures: int = 1
    red_apply_failures: int = 10


@dataclass(frozen=True)
class CsfbObservabilityPolicy:
    threshold_policy_ref: str
    thresholds: CsfbHealthThresholds
    max_unresolved_anomalies: int

    @classmethod
    def load(cls, path: Path) -> "CsfbObservabilityPolicy":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CSFB observability policy must be a mapping")
        root = payload.get("context_store_flow_binding")
        if isinstance(root, dict):
            payload = root
        obs = payload.get("observability")
        if not isinstance(obs, dict):
            raise ValueError("CSFB observability policy missing 'observability'")
        thresholds_raw = obs.get("thresholds")
        if not isinstance(thresholds_raw, dict):
            raise ValueError("CSFB observability policy missing 'thresholds'")
        rec_raw = obs.get("reconciliation")
        if rec_raw is not None and not isinstance(rec_raw, dict):
            raise ValueError("CSFB observability reconciliation policy must be mapping")

        thresholds = CsfbHealthThresholds(
            amber_watermark_age_seconds=float(thresholds_raw.get("amber_watermark_age_seconds", 120.0)),
            red_watermark_age_seconds=float(thresholds_raw.get("red_watermark_age_seconds", 300.0)),
            amber_checkpoint_age_seconds=float(thresholds_raw.get("amber_checkpoint_age_seconds", 120.0)),
            red_checkpoint_age_seconds=float(thresholds_raw.get("red_checkpoint_age_seconds", 300.0)),
            amber_join_misses=int(thresholds_raw.get("amber_join_misses", 1)),
            red_join_misses=int(thresholds_raw.get("red_join_misses", 10)),
            amber_binding_conflicts=int(thresholds_raw.get("amber_binding_conflicts", 1)),
            red_binding_conflicts=int(thresholds_raw.get("red_binding_conflicts", 5)),
            amber_apply_failures=int(thresholds_raw.get("amber_apply_failures", 1)),
            red_apply_failures=int(thresholds_raw.get("red_apply_failures", 10)),
        )
        max_unresolved_anomalies = int((rec_raw or {}).get("max_unresolved_anomalies", 200))
        if max_unresolved_anomalies <= 0:
            raise ValueError("max_unresolved_anomalies must be > 0")
        return cls(
            threshold_policy_ref=str(obs.get("threshold_policy_ref") or "csfb.observability.v0"),
            thresholds=thresholds,
            max_unresolved_anomalies=max_unresolved_anomalies,
        )


@dataclass
class CsfbObservabilityReporter:
    store: ContextStoreFlowBindingStore
    stream_id: str
    policy: CsfbObservabilityPolicy

    @classmethod
    def build(
        cls,
        *,
        locator: str | Path,
        stream_id: str,
        policy_path: str | Path = "config/platform/context_store_flow_binding/observability_v0.yaml",
    ) -> "CsfbObservabilityReporter":
        store = build_store(locator=locator, stream_id=stream_id)
        policy = CsfbObservabilityPolicy.load(Path(policy_path))
        return cls(store=store, stream_id=stream_id, policy=policy)

    def collect(
        self,
        *,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
    ) -> dict[str, Any]:
        generated_at_utc = _utc_now()
        metrics = self.store.metrics_snapshot(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
        )
        checkpoints = self.store.checkpoint_summary()
        basis = self.store.input_basis()
        unresolved = self.store.unresolved_anomalies(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            limit=self.policy.max_unresolved_anomalies,
        )
        watermark_age_seconds = _age_seconds(checkpoints.get("watermark_ts_utc"))
        checkpoint_age_seconds = _age_seconds(checkpoints.get("updated_at_utc"))
        lag_seconds = checkpoint_age_seconds

        health = _derive_health(
            metrics=metrics,
            watermark_age_seconds=watermark_age_seconds,
            checkpoint_age_seconds=checkpoint_age_seconds,
            thresholds=self.policy.thresholds,
        )
        payload = {
            "generated_at_utc": generated_at_utc,
            "stream_id": self.stream_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "threshold_policy_ref": self.policy.threshold_policy_ref,
            "metrics": metrics,
            "checkpoints": checkpoints,
            "applied_offset_basis": basis,
            "unresolved_anomalies": unresolved,
            "watermark_age_seconds": watermark_age_seconds,
            "checkpoint_age_seconds": checkpoint_age_seconds,
            "lag_seconds": lag_seconds,
            "health_state": health["state"],
            "health_reasons": health["reasons"],
        }
        return payload

    def export(
        self,
        *,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        output_root: Path | None = None,
    ) -> dict[str, Any]:
        payload = self.collect(platform_run_id=platform_run_id, scenario_run_id=scenario_run_id)
        run_root = output_root or _default_output_root(platform_run_id)
        if run_root is None:
            return payload
        run_root = Path(run_root)
        metrics_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "stream_id": payload["stream_id"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "threshold_policy_ref": payload["threshold_policy_ref"],
            "metrics": payload["metrics"],
            "checkpoints": payload["checkpoints"],
            "watermark_age_seconds": payload["watermark_age_seconds"],
            "checkpoint_age_seconds": payload["checkpoint_age_seconds"],
            "lag_seconds": payload["lag_seconds"],
        }
        health_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "stream_id": payload["stream_id"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "threshold_policy_ref": payload["threshold_policy_ref"],
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
            "checkpoints": payload["checkpoints"],
            "watermark_age_seconds": payload["watermark_age_seconds"],
            "checkpoint_age_seconds": payload["checkpoint_age_seconds"],
        }
        reconciliation_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "stream_id": payload["stream_id"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "threshold_policy_ref": payload["threshold_policy_ref"],
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
            "metrics": payload["metrics"],
            "applied_offset_basis": payload["applied_offset_basis"],
            "unresolved_anomalies": payload["unresolved_anomalies"],
        }
        _write_json(run_root / "context_store_flow_binding" / "metrics" / "last_metrics.json", metrics_payload)
        _write_json(run_root / "context_store_flow_binding" / "health" / "last_health.json", health_payload)
        _write_json(
            run_root / "context_store_flow_binding" / "reconciliation" / "last_reconciliation.json",
            reconciliation_payload,
        )
        return payload


def _default_output_root(platform_run_id: str | None) -> Path | None:
    run_id = str(platform_run_id or "").strip()
    if not run_id:
        run_id = str(resolve_platform_run_id(create_if_missing=False) or "").strip()
    if not run_id:
        return None
    return RUNS_ROOT / run_id


def _derive_health(
    *,
    metrics: dict[str, int],
    watermark_age_seconds: float | None,
    checkpoint_age_seconds: float | None,
    thresholds: CsfbHealthThresholds,
) -> dict[str, Any]:
    state = "GREEN"
    reasons: list[str] = []

    if watermark_age_seconds is None:
        reasons.append("WATERMARK_MISSING")
        state = "AMBER"
    elif watermark_age_seconds >= thresholds.red_watermark_age_seconds:
        reasons.append("WATERMARK_TOO_OLD")
        state = "RED"
    elif watermark_age_seconds >= thresholds.amber_watermark_age_seconds:
        reasons.append("WATERMARK_OLD")
        if state != "RED":
            state = "AMBER"

    if checkpoint_age_seconds is None:
        reasons.append("CHECKPOINT_MISSING")
        if state != "RED":
            state = "AMBER"
    elif checkpoint_age_seconds >= thresholds.red_checkpoint_age_seconds:
        reasons.append("CHECKPOINT_TOO_OLD")
        state = "RED"
    elif checkpoint_age_seconds >= thresholds.amber_checkpoint_age_seconds:
        reasons.append("CHECKPOINT_OLD")
        if state != "RED":
            state = "AMBER"

    join_misses = int(metrics.get("join_misses", 0))
    binding_conflicts = int(metrics.get("binding_conflicts", 0))
    apply_failures = int(metrics.get("apply_failures", 0))

    if join_misses >= thresholds.red_join_misses:
        reasons.append("JOIN_MISSES_RED")
        state = "RED"
    elif join_misses >= thresholds.amber_join_misses:
        reasons.append("JOIN_MISSES_AMBER")
        if state != "RED":
            state = "AMBER"

    if binding_conflicts >= thresholds.red_binding_conflicts:
        reasons.append("BINDING_CONFLICTS_RED")
        state = "RED"
    elif binding_conflicts >= thresholds.amber_binding_conflicts:
        reasons.append("BINDING_CONFLICTS_AMBER")
        if state != "RED":
            state = "AMBER"

    if apply_failures >= thresholds.red_apply_failures:
        reasons.append("APPLY_FAILURES_RED")
        state = "RED"
    elif apply_failures >= thresholds.amber_apply_failures:
        reasons.append("APPLY_FAILURES_AMBER")
        if state != "RED":
            state = "AMBER"

    return {"state": state, "reasons": reasons}


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
