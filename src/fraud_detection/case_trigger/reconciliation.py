"""CaseTrigger reconciliation artifact helpers (Phase 7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.case_mgmt.contracts import CaseTrigger
from fraud_detection.platform_runtime import RUNS_ROOT

from .publish import (
    PUBLISH_ADMIT,
    PUBLISH_AMBIGUOUS,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
)
from .replay import REPLAY_PAYLOAD_MISMATCH


class CaseTriggerReconciliationError(ValueError):
    """Raised when reconciliation inputs are invalid."""


@dataclass
class CaseTriggerReconciliationBuilder:
    platform_run_id: str
    scenario_run_id: str
    _records: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.platform_run_id = _non_empty(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _non_empty(self.scenario_run_id, "scenario_run_id")

    def add_record(
        self,
        *,
        trigger_payload: Mapping[str, Any] | CaseTrigger,
        publish_record: Mapping[str, Any] | None = None,
        replay_outcome: str | None = None,
    ) -> None:
        trigger = _normalize_trigger(trigger_payload)
        _validate_run_scope(
            trigger,
            platform_run_id=self.platform_run_id,
            scenario_run_id=self.scenario_run_id,
        )
        publish_decision = _normalize_publish_decision(publish_record)
        receipt_ref = _extract_text(publish_record, "receipt_ref") if publish_record else None
        reason_code = _extract_text(publish_record, "reason_code") if publish_record else None
        replay = str(replay_outcome or "").strip().upper() or None
        self._records.append(
            {
                "case_trigger_id": trigger.case_trigger_id,
                "case_id": trigger.case_id,
                "trigger_type": trigger.trigger_type,
                "source_ref_id": trigger.source_ref_id,
                "payload_hash": trigger.payload_hash,
                "publish_decision": publish_decision,
                "publish_reason_code": reason_code,
                "receipt_ref": receipt_ref,
                "replay_outcome": replay,
            }
        )

    def summary(self, *, generated_at_utc: str | None = None) -> dict[str, Any]:
        by_publish = _count_by(self._records, "publish_decision")
        reason_counts = _count_by(self._records, "publish_reason_code")
        replay_counts = _count_by(self._records, "replay_outcome")
        evidence_refs = [
            {
                "case_trigger_id": item["case_trigger_id"],
                "ref_type": "receipt_ref",
                "ref_id": item["receipt_ref"],
            }
            for item in self._records
            if item.get("receipt_ref")
        ]
        return {
            "generated_at_utc": generated_at_utc or _utc_now(),
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "totals": {
                "triggers_seen": len(self._records),
                "published": int(by_publish.get(PUBLISH_ADMIT, 0)),
                "duplicates": int(by_publish.get(PUBLISH_DUPLICATE, 0)),
                "quarantine": int(by_publish.get(PUBLISH_QUARANTINE, 0)),
                "publish_ambiguous": int(by_publish.get(PUBLISH_AMBIGUOUS, 0)),
                "payload_mismatch": int(replay_counts.get(REPLAY_PAYLOAD_MISMATCH, 0)),
            },
            "by_publish_decision": by_publish,
            "publish_reason_code_counts": reason_counts,
            "replay_outcome_counts": replay_counts,
            "evidence_refs": evidence_refs,
        }

    def export(self, *, output_path: str | Path | None = None, generated_at_utc: str | None = None) -> dict[str, Any]:
        payload = self.summary(generated_at_utc=generated_at_utc)
        path = Path(output_path) if output_path else _default_reconciliation_path(self.platform_run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload


def _normalize_trigger(value: Mapping[str, Any] | CaseTrigger) -> CaseTrigger:
    if isinstance(value, CaseTrigger):
        return value
    if not isinstance(value, Mapping):
        raise CaseTriggerReconciliationError("trigger_payload must be a mapping")
    try:
        return CaseTrigger.from_payload(value)
    except Exception as exc:
        raise CaseTriggerReconciliationError(f"invalid case trigger payload: {exc}") from exc


def _validate_run_scope(trigger: CaseTrigger, *, platform_run_id: str, scenario_run_id: str) -> None:
    pins = trigger.pins
    payload_platform = str(pins.get("platform_run_id") or "").strip()
    payload_scenario = str(pins.get("scenario_run_id") or "").strip()
    if payload_platform != platform_run_id:
        raise CaseTriggerReconciliationError(
            f"platform_run_id mismatch: expected {platform_run_id!r}, got {payload_platform!r}"
        )
    if payload_scenario != scenario_run_id:
        raise CaseTriggerReconciliationError(
            f"scenario_run_id mismatch: expected {scenario_run_id!r}, got {payload_scenario!r}"
        )


def _normalize_publish_decision(value: Mapping[str, Any] | None) -> str | None:
    if not value:
        return None
    decision = _extract_text(value, "decision")
    if decision is None:
        return None
    normalized = decision.upper()
    if normalized not in {PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}:
        raise CaseTriggerReconciliationError(f"unsupported publish decision: {normalized}")
    return normalized


def _extract_text(value: Mapping[str, Any] | None, key: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    raw = value.get(key)
    text = str(raw or "").strip()
    return text or None


def _count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in records:
        value = str(item.get(key) or "").strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _default_reconciliation_path(platform_run_id: str) -> Path:
    return RUNS_ROOT / platform_run_id / "case_trigger" / "reconciliation" / "reconciliation.json"


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseTriggerReconciliationError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
