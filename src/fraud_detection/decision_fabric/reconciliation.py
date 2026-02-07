"""Decision Fabric reconciliation artifact helpers (Phase 8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.platform_runtime import RUNS_ROOT

from .registry import RESOLUTION_FAIL_CLOSED


class DecisionFabricReconciliationError(ValueError):
    """Raised when reconciliation inputs are invalid."""


@dataclass(frozen=True)
class DfParityProof:
    expected_events: int
    observed_events: int
    quarantined_events: int
    fail_closed_events: int
    status: str
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "expected_events": self.expected_events,
            "observed_events": self.observed_events,
            "quarantined_events": self.quarantined_events,
            "fail_closed_events": self.fail_closed_events,
            "status": self.status,
            "reasons": list(self.reasons),
        }


@dataclass
class DfReconciliationBuilder:
    platform_run_id: str
    scenario_run_id: str
    _records: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.platform_run_id = _non_empty(self.platform_run_id, "platform_run_id")
        self.scenario_run_id = _non_empty(self.scenario_run_id, "scenario_run_id")

    def add_record(
        self,
        *,
        decision_payload: Mapping[str, Any],
        action_intents: tuple[Mapping[str, Any], ...] = tuple(),
        publish_decision: str | None = None,
        decision_receipt_ref: str | None = None,
        action_receipt_refs: tuple[str, ...] = tuple(),
    ) -> None:
        decision = _normalize_mapping(decision_payload, "decision_payload")
        decision_id = _non_empty(decision.get("decision_id"), "decision_payload.decision_id")
        _validate_run_scope(decision, platform_run_id=self.platform_run_id, scenario_run_id=self.scenario_run_id)

        action_kind = str(_mapping_or_empty(decision.get("decision")).get("action_kind") or "").strip().upper()
        degrade_mode = str(_mapping_or_empty(decision.get("degrade_posture")).get("mode") or "").strip().upper()
        bundle_id = str(_mapping_or_empty(decision.get("bundle_ref")).get("bundle_id") or "").strip().lower()
        source_event = _mapping_or_empty(decision.get("source_event"))
        source_eb_ref = _mapping_or_empty(source_event.get("eb_ref"))
        registry_outcome = str(_mapping_or_empty(decision.get("decision")).get("registry_outcome") or "").strip().upper()
        reason_codes = tuple(str(item) for item in list(decision.get("reason_codes") or []))
        normalized_publish = _normalize_publish_decision(publish_decision)

        for index, intent in enumerate(action_intents):
            mapped_intent = _normalize_mapping(intent, f"action_intents[{index}]")
            intent_decision_id = str(mapped_intent.get("decision_id") or "").strip()
            if intent_decision_id != decision_id:
                raise DecisionFabricReconciliationError(
                    f"action_intents[{index}].decision_id mismatch: expected {decision_id!r}, got {intent_decision_id!r}"
                )

        self._records.append(
            {
                "decision_id": decision_id,
                "run_config_digest": str(decision.get("run_config_digest") or "").strip().lower(),
                "mode": degrade_mode,
                "bundle_id": bundle_id,
                "action_kind": action_kind,
                "registry_outcome": registry_outcome,
                "reason_codes": reason_codes,
                "publish_decision": normalized_publish,
                "evidence": {
                    "source_event_id": str(source_event.get("event_id") or "").strip(),
                    "source_eb_ref": dict(source_eb_ref),
                    "decision_receipt_ref": str(decision_receipt_ref or "").strip() or None,
                    "action_receipt_refs": tuple(
                        str(item).strip() for item in action_receipt_refs if str(item).strip()
                    ),
                },
            }
        )

    def summary(self, *, generated_at_utc: str | None = None) -> dict[str, Any]:
        by_mode = _count_by(self._records, "mode")
        by_bundle = _count_by(self._records, "bundle_id")
        by_action = _count_by(self._records, "action_kind")
        by_publish = _count_by(self._records, "publish_decision")
        reason_code_counts = _count_reason_codes(self._records)
        run_config_digests = sorted({str(item.get("run_config_digest") or "") for item in self._records if item.get("run_config_digest")})

        fail_closed_count = sum(1 for item in self._records if _is_fail_closed_record(item))
        degrade_count = sum(1 for item in self._records if _is_degrade_record(item))
        quarantined_count = sum(1 for item in self._records if str(item.get("publish_decision") or "") == "QUARANTINE")

        evidence_refs = [
            {
                "decision_id": item["decision_id"],
                "source_event_id": item["evidence"]["source_event_id"],
                "source_eb_ref": item["evidence"]["source_eb_ref"],
                "decision_receipt_ref": item["evidence"]["decision_receipt_ref"],
                "action_receipt_refs": list(item["evidence"]["action_receipt_refs"]),
            }
            for item in self._records
        ]

        return {
            "generated_at_utc": generated_at_utc or _utc_now(),
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": self.scenario_run_id,
            "totals": {
                "decisions_total": len(self._records),
                "degrade_total": degrade_count,
                "fail_closed_total": fail_closed_count,
                "quarantined_total": quarantined_count,
            },
            "by_mode": by_mode,
            "by_bundle_id": by_bundle,
            "by_action_kind": by_action,
            "by_publish_decision": by_publish,
            "reason_code_counts": reason_code_counts,
            "run_config_digests": run_config_digests,
            "evidence_refs": evidence_refs,
        }

    def export(self, *, output_path: str | Path | None = None, generated_at_utc: str | None = None) -> dict[str, Any]:
        payload = self.summary(generated_at_utc=generated_at_utc)
        path = Path(output_path) if output_path else _default_reconciliation_path(self.platform_run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return payload

    def parity_proof(self, *, expected_events: int) -> DfParityProof:
        expected = int(expected_events)
        if expected < 0:
            raise DecisionFabricReconciliationError("expected_events must be >= 0")
        observed = len(self._records)
        quarantined = sum(1 for item in self._records if str(item.get("publish_decision") or "") == "QUARANTINE")
        fail_closed = sum(1 for item in self._records if _is_fail_closed_record(item))
        reasons: list[str] = []
        if observed != expected:
            reasons.append(f"OBSERVED_MISMATCH:{observed}:{expected}")
        if quarantined > 0:
            reasons.append(f"QUARANTINED_EVENTS:{quarantined}")
        status = "PASS" if not reasons else "FAIL"
        return DfParityProof(
            expected_events=expected,
            observed_events=observed,
            quarantined_events=quarantined,
            fail_closed_events=fail_closed,
            status=status,
            reasons=tuple(reasons),
        )


def _default_reconciliation_path(platform_run_id: str) -> Path:
    return RUNS_ROOT / platform_run_id / "decision_fabric" / "reconciliation" / "reconciliation.json"


def _normalize_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DecisionFabricReconciliationError(f"{name} must be a mapping")
    return dict(value)


def _validate_run_scope(payload: Mapping[str, Any], *, platform_run_id: str, scenario_run_id: str) -> None:
    pins = _mapping_or_empty(payload.get("pins"))
    payload_platform_run_id = str(pins.get("platform_run_id") or "").strip()
    payload_scenario_run_id = str(pins.get("scenario_run_id") or "").strip()
    if payload_platform_run_id != platform_run_id:
        raise DecisionFabricReconciliationError(
            f"platform_run_id mismatch: expected {platform_run_id!r}, got {payload_platform_run_id!r}"
        )
    if payload_scenario_run_id != scenario_run_id:
        raise DecisionFabricReconciliationError(
            f"scenario_run_id mismatch: expected {scenario_run_id!r}, got {payload_scenario_run_id!r}"
        )


def _normalize_publish_decision(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if text not in {"ADMIT", "DUPLICATE", "QUARANTINE"}:
        raise DecisionFabricReconciliationError(f"unsupported publish decision: {text}")
    return text


def _count_by(records: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = str(record.get(field_name) or "").strip()
        if not key:
            key = "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _count_reason_codes(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for reason in record.get("reason_codes") or tuple():
            reason_text = str(reason).strip()
            if not reason_text:
                continue
            counts[reason_text] = counts.get(reason_text, 0) + 1
    return dict(sorted(counts.items()))


def _is_degrade_record(record: Mapping[str, Any]) -> bool:
    mode = str(record.get("mode") or "").strip().upper()
    if mode not in {"", "NORMAL"}:
        return True
    registry_outcome = str(record.get("registry_outcome") or "").strip().upper()
    if registry_outcome == RESOLUTION_FAIL_CLOSED:
        return True
    reasons = tuple(str(item) for item in list(record.get("reason_codes") or []))
    return any(item.startswith("DEGRADE_") or item.startswith("CONTEXT_") for item in reasons)


def _is_fail_closed_record(record: Mapping[str, Any]) -> bool:
    mode = str(record.get("mode") or "").strip().upper()
    if mode in {"FAIL_CLOSED", "BLOCKED"}:
        return True
    reasons = tuple(str(item) for item in list(record.get("reason_codes") or []))
    return any("FAIL_CLOSED" in item for item in reasons)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _non_empty(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionFabricReconciliationError(f"{field_name} is required")
    return text


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()
