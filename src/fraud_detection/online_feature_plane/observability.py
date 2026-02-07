"""OFP observability reporter (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id

from .config import OfpProfile
from .store import OfpStore, build_store

_REQUIRED_COUNTERS = [
    "snapshots_built",
    "snapshot_failures",
    "events_applied",
    "duplicates",
    "stale_graph_version",
    "missing_features",
]


@dataclass(frozen=True)
class OfpHealthThresholds:
    amber_watermark_age_seconds: float = 120.0
    red_watermark_age_seconds: float = 300.0
    amber_checkpoint_age_seconds: float = 120.0
    red_checkpoint_age_seconds: float = 300.0
    amber_missing_features: int = 1
    red_missing_features: int = 10
    amber_stale_graph_version: int = 1
    red_stale_graph_version: int = 10
    amber_snapshot_failures: int = 1
    red_snapshot_failures: int = 5


@dataclass
class OfpObservabilityReporter:
    profile: OfpProfile
    store: OfpStore
    thresholds: OfpHealthThresholds = OfpHealthThresholds()

    @classmethod
    def build(cls, profile_path: str) -> "OfpObservabilityReporter":
        profile = OfpProfile.load(Path(profile_path))
        store = build_store(
            profile.wiring.projection_db_dsn,
            stream_id=profile.policy.stream_id,
            basis_stream=profile.wiring.event_bus_basis_stream,
            run_config_digest=profile.policy.run_config_digest,
            feature_def_policy_id=profile.policy.feature_def_policy_rev.policy_id,
            feature_def_revision=profile.policy.feature_def_policy_rev.revision,
            feature_def_content_digest=profile.policy.feature_def_policy_rev.content_digest,
        )
        return cls(profile=profile, store=store)

    def collect(self, *, scenario_run_id: str) -> dict[str, Any]:
        generated_at_utc = _utc_now()
        counters = dict(self.store.metrics_summary(scenario_run_id=scenario_run_id))
        for metric_name in _REQUIRED_COUNTERS:
            counters.setdefault(metric_name, 0)

        checkpoints = self.store.checkpoints_summary()
        watermark_age_seconds = _age_seconds(checkpoints.get("watermark_ts_utc"))
        checkpoint_age_seconds = _age_seconds(checkpoints.get("updated_at_utc"))
        lag_seconds = checkpoint_age_seconds

        health = _derive_health(
            counters=counters,
            watermark_age_seconds=watermark_age_seconds,
            checkpoint_age_seconds=checkpoint_age_seconds,
            thresholds=self.thresholds,
        )
        payload = {
            "generated_at_utc": generated_at_utc,
            "stream_id": self.profile.policy.stream_id,
            "platform_run_id": self.profile.wiring.required_platform_run_id,
            "scenario_run_id": scenario_run_id,
            "run_config_digest": self.profile.policy.run_config_digest,
            "metrics": counters,
            "checkpoints": checkpoints,
            "watermark_age_seconds": watermark_age_seconds,
            "checkpoint_age_seconds": checkpoint_age_seconds,
            "lag_seconds": lag_seconds,
            "health_state": health["state"],
            "health_reasons": health["reasons"],
        }
        return payload

    def export(self, *, scenario_run_id: str, output_root: Path | None = None) -> dict[str, Any]:
        payload = self.collect(scenario_run_id=scenario_run_id)
        run_root = output_root or _default_output_root(self.profile.wiring.required_platform_run_id)
        if run_root is None:
            return payload
        run_root = Path(run_root)
        metrics_payload = {
            "generated_at_utc": payload["generated_at_utc"],
            "stream_id": payload["stream_id"],
            "platform_run_id": payload["platform_run_id"],
            "scenario_run_id": payload["scenario_run_id"],
            "run_config_digest": payload["run_config_digest"],
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
            "run_config_digest": payload["run_config_digest"],
            "checkpoints": payload["checkpoints"],
            "watermark_age_seconds": payload["watermark_age_seconds"],
            "checkpoint_age_seconds": payload["checkpoint_age_seconds"],
            "health_state": payload["health_state"],
            "health_reasons": payload["health_reasons"],
        }
        _write_json(run_root / "online_feature_plane" / "metrics" / "last_metrics.json", metrics_payload)
        _write_json(run_root / "online_feature_plane" / "health" / "last_health.json", health_payload)
        return payload


def _default_output_root(required_platform_run_id: str | None) -> Path | None:
    run_id = str(required_platform_run_id or "").strip()
    if not run_id:
        run_id = str(resolve_platform_run_id(create_if_missing=False) or "").strip()
    if not run_id:
        return None
    return RUNS_ROOT / run_id


def _derive_health(
    *,
    counters: dict[str, int],
    watermark_age_seconds: float | None,
    checkpoint_age_seconds: float | None,
    thresholds: OfpHealthThresholds,
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
        state = "AMBER"

    if checkpoint_age_seconds is None:
        reasons.append("CHECKPOINT_MISSING")
        if state != "RED":
            state = "AMBER"
    elif checkpoint_age_seconds >= thresholds.red_checkpoint_age_seconds:
        reasons.append("CHECKPOINT_TOO_OLD")
        state = "RED"
    elif checkpoint_age_seconds >= thresholds.amber_checkpoint_age_seconds and state != "RED":
        reasons.append("CHECKPOINT_OLD")
        state = "AMBER"

    missing_features = int(counters.get("missing_features", 0))
    stale_graph_version = int(counters.get("stale_graph_version", 0))
    snapshot_failures = int(counters.get("snapshot_failures", 0))

    if missing_features >= thresholds.red_missing_features:
        reasons.append("MISSING_FEATURES_RED")
        state = "RED"
    elif missing_features >= thresholds.amber_missing_features and state != "RED":
        reasons.append("MISSING_FEATURES_AMBER")
        state = "AMBER"

    if stale_graph_version >= thresholds.red_stale_graph_version:
        reasons.append("STALE_GRAPH_VERSION_RED")
        state = "RED"
    elif stale_graph_version >= thresholds.amber_stale_graph_version and state != "RED":
        reasons.append("STALE_GRAPH_VERSION_AMBER")
        state = "AMBER"

    if snapshot_failures >= thresholds.red_snapshot_failures:
        reasons.append("SNAPSHOT_FAILURES_RED")
        state = "RED"
    elif snapshot_failures >= thresholds.amber_snapshot_failures and state != "RED":
        reasons.append("SNAPSHOT_FAILURES_AMBER")
        state = "AMBER"

    return {"state": state, "reasons": reasons}


def _parse_ts(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


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
