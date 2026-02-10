"""Archive writer observability helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.platform_governance import emit_platform_governance_event
from fraud_detection.platform_governance.anomaly_taxonomy import classify_anomaly
from fraud_detection.platform_provenance import runtime_provenance
from fraud_detection.platform_runtime import RUNS_ROOT
from fraud_detection.scenario_runner.storage import ObjectStore


@dataclass
class ArchiveWriterRunMetrics:
    platform_run_id: str
    counters: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.platform_run_id = _required(self.platform_run_id, "platform_run_id")
        for key in _REQUIRED_COUNTERS:
            self.counters.setdefault(key, 0)

    def bump(self, key: str, delta: int = 1) -> None:
        if key not in self.counters:
            raise ValueError(f"unsupported metric counter: {key}")
        self.counters[key] = int(self.counters.get(key, 0)) + int(delta)

    def snapshot(self) -> dict[str, Any]:
        return {
            "generated_at_utc": _utc_now(),
            "platform_run_id": self.platform_run_id,
            "metrics": dict(self.counters),
        }

    def export(self) -> dict[str, Any]:
        payload = self.snapshot()
        path = RUNS_ROOT / self.platform_run_id / "archive_writer" / "metrics" / "last_metrics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload


@dataclass(frozen=True)
class ArchiveWriterGovernanceEmitter:
    store: ObjectStore
    platform_run_id: str
    source_component: str = "archive_writer"
    environment: str | None = None
    config_revision: str | None = None

    def emit_replay_basis_mismatch(
        self,
        *,
        scenario_run_id: str | None,
        topic: str,
        partition: int,
        offset_kind: str,
        offset: str,
        expected_payload_hash: str,
        observed_payload_hash: str,
        archive_ref: str | None,
    ) -> dict[str, Any] | None:
        key = f"{topic}:{partition}:{offset_kind}:{offset}"
        details: dict[str, Any] = {
            "corridor": "archive_writer",
            "anomaly_kind": "REPLAY_BASIS_MISMATCH",
            "reason_code": "REPLAY_BASIS_MISMATCH",
            "anomaly_category": classify_anomaly("REPLAY_BASIS_MISMATCH"),
            "origin_offset": {
                "topic": str(topic),
                "partition": int(partition),
                "offset_kind": str(offset_kind),
                "offset": str(offset),
            },
            "expected_payload_hash": str(expected_payload_hash),
            "observed_payload_hash": str(observed_payload_hash),
            "provenance": runtime_provenance(
                component=self.source_component,
                environment=self.environment,
                config_revision=self.config_revision,
            ),
        }
        if archive_ref:
            details["evidence_refs"] = [{"ref_type": "archive_ref", "ref_id": str(archive_ref)}]
        return emit_platform_governance_event(
            store=self.store,
            event_family="CORRIDOR_ANOMALY",
            actor_id="SYSTEM::archive_writer",
            source_type="SYSTEM",
            source_component=self.source_component,
            platform_run_id=self.platform_run_id,
            scenario_run_id=scenario_run_id,
            dedupe_key=f"archive-replay-basis-mismatch:{key}",
            details=details,
        )


def build_health_payload(
    *,
    platform_run_id: str,
    counters: Mapping[str, Any],
    reconciliation_totals: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    mismatch = int(counters.get("payload_mismatch_total", 0))
    write_error = int(counters.get("write_error_total", 0))
    health_state = "GREEN"
    reasons: list[str] = []
    if mismatch > 0:
        health_state = "RED"
        reasons.append("REPLAY_BASIS_MISMATCH_NONZERO")
    if write_error > 0:
        health_state = "RED"
        reasons.append("ARCHIVE_WRITE_ERROR_NONZERO")
    return {
        "generated_at_utc": _utc_now(),
        "platform_run_id": _required(platform_run_id, "platform_run_id"),
        "health_state": health_state,
        "health_reasons": sorted(set(reasons)),
        "metrics": dict(counters),
        "reconciliation_totals": dict(reconciliation_totals or {}),
    }


def export_health(*, platform_run_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    path = RUNS_ROOT / platform_run_id / "archive_writer" / "health" / "last_health.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return body


def _required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


_REQUIRED_COUNTERS: tuple[str, ...] = (
    "seen_total",
    "archived_total",
    "duplicate_total",
    "payload_mismatch_total",
    "write_error_total",
)
