"""Case Management contract validators for Phase 5.1."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .ids import (
    canonical_case_timeline_payload_hash,
    canonical_case_trigger_payload_hash,
    deterministic_case_id,
    deterministic_case_timeline_event_id,
    deterministic_case_trigger_id,
)


HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PLATFORM_RUN_ID_RE = re.compile(r"^platform_[0-9]{8}T[0-9]{6}Z$")

REQUIRED_PINS: tuple[str, ...] = (
    "platform_run_id",
    "scenario_run_id",
    "manifest_fingerprint",
    "parameter_hash",
    "scenario_id",
    "seed",
)

CASE_TRIGGER_TYPES: set[str] = {
    "DECISION_ESCALATION",
    "ACTION_FAILURE",
    "ANOMALY",
    "EXTERNAL_SIGNAL",
    "MANUAL_ASSERTION",
}

CASE_TIMELINE_EVENT_TYPES: set[str] = {
    "CASE_TRIGGERED",
    "EVIDENCE_ATTACHED",
    "ACTION_INTENT_REQUESTED",
    "ACTION_OUTCOME_ATTACHED",
    "LABEL_PENDING",
    "LABEL_ACCEPTED",
    "LABEL_REJECTED",
    "INVESTIGATOR_ASSERTION",
}

EVIDENCE_REF_TYPES: set[str] = {
    "DLA_AUDIT_RECORD",
    "DECISION",
    "ACTION_OUTCOME",
    "EB_ORIGIN_OFFSET",
    "CASE_EVENT",
    "EXTERNAL_REF",
}


class CaseMgmtContractError(ValueError):
    """Raised when CM contracts fail validation."""


@dataclass(frozen=True)
class CaseSubjectKey:
    platform_run_id: str
    event_class: str
    event_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CaseSubjectKey":
        mapped = _as_mapping(payload, "case_subject_key")
        platform_run_id = _require_platform_run_id(
            mapped.get("platform_run_id"), "case_subject_key.platform_run_id"
        )
        event_class = _require_non_empty_string(mapped.get("event_class"), "case_subject_key.event_class")
        event_id = _require_non_empty_string(mapped.get("event_id"), "case_subject_key.event_id")
        return cls(
            platform_run_id=platform_run_id,
            event_class=event_class,
            event_id=event_id,
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "platform_run_id": self.platform_run_id,
            "event_class": self.event_class,
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class EvidenceRef:
    ref_type: str
    ref_id: str
    ref_scope: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "EvidenceRef":
        mapped = _as_mapping(payload, "evidence_ref")
        ref_type = _require_non_empty_string(mapped.get("ref_type"), "evidence_ref.ref_type")
        if ref_type not in EVIDENCE_REF_TYPES:
            raise CaseMgmtContractError(
                f"evidence_ref.ref_type must be one of {sorted(EVIDENCE_REF_TYPES)}"
            )
        ref_id = _require_non_empty_string(mapped.get("ref_id"), "evidence_ref.ref_id")
        ref_scope_raw = mapped.get("ref_scope")
        ref_scope = _require_non_empty_string(ref_scope_raw, "evidence_ref.ref_scope") if ref_scope_raw not in (None, "") else None
        return cls(ref_type=ref_type, ref_id=ref_id, ref_scope=ref_scope)

    def as_dict(self) -> dict[str, str]:
        payload = {"ref_type": self.ref_type, "ref_id": self.ref_id}
        if self.ref_scope is not None:
            payload["ref_scope"] = self.ref_scope
        return payload


@dataclass(frozen=True)
class CaseTrigger:
    case_id: str
    case_trigger_id: str
    trigger_type: str
    source_ref_id: str
    pins: dict[str, Any]
    case_subject_key: CaseSubjectKey
    evidence_refs: tuple[EvidenceRef, ...]
    observed_time: str
    payload_hash: str
    trigger_payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CaseTrigger":
        mapped = _as_mapping(payload, "case_trigger")
        trigger_type = _require_non_empty_string(mapped.get("trigger_type"), "case_trigger.trigger_type")
        if trigger_type not in CASE_TRIGGER_TYPES:
            raise CaseMgmtContractError(
                f"case_trigger.trigger_type must be one of {sorted(CASE_TRIGGER_TYPES)}"
            )
        source_ref_id = _require_non_empty_string(mapped.get("source_ref_id"), "case_trigger.source_ref_id")
        observed_time = _require_non_empty_string(mapped.get("observed_time"), "case_trigger.observed_time")
        pins = _normalize_pins(mapped.get("pins"), "case_trigger.pins")
        case_subject_key = CaseSubjectKey.from_payload(mapped.get("case_subject_key") or {})
        _require_subject_pins_alignment(case_subject_key, pins)
        evidence_refs = _normalize_evidence_refs(mapped.get("evidence_refs"), "case_trigger.evidence_refs")
        trigger_payload_raw = mapped.get("trigger_payload")
        trigger_payload = dict(trigger_payload_raw) if isinstance(trigger_payload_raw, Mapping) else {}

        expected_case_id = deterministic_case_id(case_subject_key=case_subject_key.as_dict())
        provided_case_id = mapped.get("case_id")
        if provided_case_id not in (None, ""):
            case_id = _require_hex32(provided_case_id, "case_trigger.case_id")
            if case_id != expected_case_id:
                raise CaseMgmtContractError("case_trigger.case_id does not match deterministic case subject identity")
        else:
            case_id = expected_case_id

        expected_trigger_id = deterministic_case_trigger_id(
            case_id=case_id,
            trigger_type=trigger_type,
            source_ref_id=source_ref_id,
        )
        provided_trigger_id = mapped.get("case_trigger_id")
        if provided_trigger_id not in (None, ""):
            case_trigger_id = _require_hex32(provided_trigger_id, "case_trigger.case_trigger_id")
            if case_trigger_id != expected_trigger_id:
                raise CaseMgmtContractError("case_trigger.case_trigger_id does not match deterministic identity")
        else:
            case_trigger_id = expected_trigger_id

        expected_payload_hash = canonical_case_trigger_payload_hash(
            {
                "case_subject_key": case_subject_key.as_dict(),
                "trigger_type": trigger_type,
                "source_ref_id": source_ref_id,
                "pins": pins,
                "observed_time": observed_time,
                "evidence_refs": [item.as_dict() for item in evidence_refs],
                "trigger_payload": trigger_payload,
            }
        )
        provided_payload_hash = mapped.get("payload_hash")
        if provided_payload_hash not in (None, ""):
            payload_hash = _require_hex64(provided_payload_hash, "case_trigger.payload_hash")
            if payload_hash != expected_payload_hash:
                raise CaseMgmtContractError("case_trigger.payload_hash mismatch for canonical trigger payload")
        else:
            payload_hash = expected_payload_hash

        return cls(
            case_id=case_id,
            case_trigger_id=case_trigger_id,
            trigger_type=trigger_type,
            source_ref_id=source_ref_id,
            pins=pins,
            case_subject_key=case_subject_key,
            evidence_refs=evidence_refs,
            observed_time=observed_time,
            payload_hash=payload_hash,
            trigger_payload=trigger_payload,
        )

    def dedupe_tuple(self) -> tuple[str, str, str]:
        return (self.case_id, self.trigger_type, self.source_ref_id)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case_id": self.case_id,
            "case_trigger_id": self.case_trigger_id,
            "trigger_type": self.trigger_type,
            "source_ref_id": self.source_ref_id,
            "pins": dict(self.pins),
            "case_subject_key": self.case_subject_key.as_dict(),
            "evidence_refs": [item.as_dict() for item in self.evidence_refs],
            "observed_time": self.observed_time,
            "payload_hash": self.payload_hash,
        }
        if self.trigger_payload:
            payload["trigger_payload"] = dict(self.trigger_payload)
        return payload


@dataclass(frozen=True)
class CaseTimelineEvent:
    case_id: str
    case_timeline_event_id: str
    timeline_event_type: str
    source_ref_id: str
    pins: dict[str, Any]
    observed_time: str
    payload_hash: str
    evidence_refs: tuple[EvidenceRef, ...]
    case_subject_key: CaseSubjectKey | None
    timeline_payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CaseTimelineEvent":
        mapped = _as_mapping(payload, "case_timeline_event")
        case_id = _require_hex32(mapped.get("case_id"), "case_timeline_event.case_id")
        timeline_event_type = _require_non_empty_string(
            mapped.get("timeline_event_type"),
            "case_timeline_event.timeline_event_type",
        )
        if timeline_event_type not in CASE_TIMELINE_EVENT_TYPES:
            raise CaseMgmtContractError(
                "case_timeline_event.timeline_event_type must be one of "
                f"{sorted(CASE_TIMELINE_EVENT_TYPES)}"
            )
        source_ref_id = _require_non_empty_string(
            mapped.get("source_ref_id"),
            "case_timeline_event.source_ref_id",
        )
        pins = _normalize_pins(mapped.get("pins"), "case_timeline_event.pins")
        observed_time = _require_non_empty_string(mapped.get("observed_time"), "case_timeline_event.observed_time")
        evidence_refs = _normalize_evidence_refs(mapped.get("evidence_refs"), "case_timeline_event.evidence_refs")
        timeline_payload_raw = mapped.get("timeline_payload")
        timeline_payload = dict(timeline_payload_raw) if isinstance(timeline_payload_raw, Mapping) else {}

        subject_raw = mapped.get("case_subject_key")
        case_subject_key = None
        if subject_raw not in (None, ""):
            case_subject_key = CaseSubjectKey.from_payload(subject_raw)
            _require_subject_pins_alignment(case_subject_key, pins)
            expected_case_id = deterministic_case_id(case_subject_key=case_subject_key.as_dict())
            if case_id != expected_case_id:
                raise CaseMgmtContractError(
                    "case_timeline_event.case_id does not match deterministic case subject identity"
                )

        expected_event_id = deterministic_case_timeline_event_id(
            case_id=case_id,
            timeline_event_type=timeline_event_type,
            source_ref_id=source_ref_id,
        )
        provided_event_id = mapped.get("case_timeline_event_id")
        if provided_event_id not in (None, ""):
            case_timeline_event_id = _require_hex32(
                provided_event_id, "case_timeline_event.case_timeline_event_id"
            )
            if case_timeline_event_id != expected_event_id:
                raise CaseMgmtContractError(
                    "case_timeline_event.case_timeline_event_id does not match deterministic identity"
                )
        else:
            case_timeline_event_id = expected_event_id

        expected_payload_hash = canonical_case_timeline_payload_hash(
            {
                "case_id": case_id,
                "timeline_event_type": timeline_event_type,
                "source_ref_id": source_ref_id,
                "pins": pins,
                "observed_time": observed_time,
                "evidence_refs": [item.as_dict() for item in evidence_refs],
                "timeline_payload": timeline_payload,
                "case_subject_key": case_subject_key.as_dict() if case_subject_key else None,
            }
        )
        provided_payload_hash = mapped.get("payload_hash")
        if provided_payload_hash not in (None, ""):
            payload_hash = _require_hex64(provided_payload_hash, "case_timeline_event.payload_hash")
            if payload_hash != expected_payload_hash:
                raise CaseMgmtContractError("case_timeline_event.payload_hash mismatch for canonical payload")
        else:
            payload_hash = expected_payload_hash

        return cls(
            case_id=case_id,
            case_timeline_event_id=case_timeline_event_id,
            timeline_event_type=timeline_event_type,
            source_ref_id=source_ref_id,
            pins=pins,
            observed_time=observed_time,
            payload_hash=payload_hash,
            evidence_refs=evidence_refs,
            case_subject_key=case_subject_key,
            timeline_payload=timeline_payload,
        )

    def dedupe_tuple(self) -> tuple[str, str, str]:
        return (self.case_id, self.timeline_event_type, self.source_ref_id)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case_id": self.case_id,
            "case_timeline_event_id": self.case_timeline_event_id,
            "timeline_event_type": self.timeline_event_type,
            "source_ref_id": self.source_ref_id,
            "pins": dict(self.pins),
            "observed_time": self.observed_time,
            "payload_hash": self.payload_hash,
            "evidence_refs": [item.as_dict() for item in self.evidence_refs],
        }
        if self.case_subject_key is not None:
            payload["case_subject_key"] = self.case_subject_key.as_dict()
        if self.timeline_payload:
            payload["timeline_payload"] = dict(self.timeline_payload)
        return payload


def _as_mapping(payload: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise CaseMgmtContractError(f"{field_name} must be a mapping")
    return dict(payload)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CaseMgmtContractError(f"{field_name} must be a non-empty string")
    return text


def _require_hex32(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    if not HEX32_RE.fullmatch(text):
        raise CaseMgmtContractError(f"{field_name} must be 32-char lowercase hex")
    return text


def _require_hex64(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    if not HEX64_RE.fullmatch(text):
        raise CaseMgmtContractError(f"{field_name} must be 64-char lowercase hex")
    return text


def _require_platform_run_id(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    if not PLATFORM_RUN_ID_RE.fullmatch(text):
        raise CaseMgmtContractError(
            f"{field_name} must match platform_YYYYMMDDTHHMMSSZ"
        )
    return text


def _normalize_pins(payload: Any, field_name: str) -> dict[str, Any]:
    pins = _as_mapping(payload, field_name)
    missing = [field for field in REQUIRED_PINS if pins.get(field) in (None, "")]
    if missing:
        raise CaseMgmtContractError(f"{field_name} missing required pins: {','.join(missing)}")
    pins["platform_run_id"] = _require_platform_run_id(
        pins.get("platform_run_id"), f"{field_name}.platform_run_id"
    )
    pins["scenario_run_id"] = _require_hex32(
        pins.get("scenario_run_id"), f"{field_name}.scenario_run_id"
    )
    pins["manifest_fingerprint"] = _require_hex64(
        pins.get("manifest_fingerprint"), f"{field_name}.manifest_fingerprint"
    )
    pins["parameter_hash"] = _require_hex64(
        pins.get("parameter_hash"), f"{field_name}.parameter_hash"
    )
    pins["scenario_id"] = _require_non_empty_string(
        pins.get("scenario_id"), f"{field_name}.scenario_id"
    )
    pins["seed"] = _as_non_negative_int(pins.get("seed"), f"{field_name}.seed")
    run_id_raw = pins.get("run_id")
    if run_id_raw not in (None, ""):
        pins["run_id"] = _require_hex32(run_id_raw, f"{field_name}.run_id")
    return pins


def _as_non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise CaseMgmtContractError(f"{field_name} must be an integer >= 0")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CaseMgmtContractError(f"{field_name} must be an integer >= 0") from exc
    if parsed < 0:
        raise CaseMgmtContractError(f"{field_name} must be an integer >= 0")
    return parsed


def _normalize_evidence_refs(payload: Any, field_name: str) -> tuple[EvidenceRef, ...]:
    if payload in (None, ""):
        return tuple()
    if not isinstance(payload, list):
        raise CaseMgmtContractError(f"{field_name} must be a list")
    refs = [EvidenceRef.from_payload(item) for item in payload]
    refs.sort(key=lambda item: (item.ref_type, item.ref_id, item.ref_scope or ""))
    return tuple(refs)


def _require_subject_pins_alignment(subject: CaseSubjectKey, pins: Mapping[str, Any]) -> None:
    if subject.platform_run_id != str(pins.get("platform_run_id")):
        raise CaseMgmtContractError(
            "case subject platform_run_id must match pins.platform_run_id"
        )
