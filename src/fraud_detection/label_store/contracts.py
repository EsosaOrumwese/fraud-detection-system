"""Label Store contract validators for Phase 5.1."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .ids import (
    canonical_label_assertion_payload_hash,
    deterministic_label_assertion_id,
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

SOURCE_TYPES: set[str] = {"HUMAN", "EXTERNAL", "AUTO", "SYSTEM"}
LABEL_TYPES: set[str] = {
    "fraud_disposition",
    "chargeback_status",
    "account_takeover",
}
LABEL_VALUES_BY_TYPE: dict[str, set[str]] = {
    "fraud_disposition": {"FRAUD_CONFIRMED", "FRAUD_SUSPECTED", "LEGIT_CONFIRMED"},
    "chargeback_status": {"CHARGEBACK", "NO_CHARGEBACK", "PENDING"},
    "account_takeover": {"ATO_CONFIRMED", "ATO_SUSPECTED", "ATO_NOT_CONFIRMED"},
}
EVIDENCE_REF_TYPES: set[str] = {
    "DLA_AUDIT_RECORD",
    "DECISION",
    "ACTION_OUTCOME",
    "EB_ORIGIN_OFFSET",
    "CASE_EVENT",
    "EXTERNAL_REF",
}


class LabelStoreContractError(ValueError):
    """Raised when LS LabelAssertion contracts fail validation."""


@dataclass(frozen=True)
class LabelSubjectKey:
    platform_run_id: str
    event_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LabelSubjectKey":
        mapped = _as_mapping(payload, "label_subject_key")
        platform_run_id = _require_platform_run_id(
            mapped.get("platform_run_id"), "label_subject_key.platform_run_id"
        )
        event_id = _require_non_empty_string(mapped.get("event_id"), "label_subject_key.event_id")
        return cls(platform_run_id=platform_run_id, event_id=event_id)

    def as_dict(self) -> dict[str, str]:
        return {
            "platform_run_id": self.platform_run_id,
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
            raise LabelStoreContractError(
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
class LabelAssertion:
    label_assertion_id: str
    case_timeline_event_id: str
    label_subject_key: LabelSubjectKey
    pins: dict[str, Any]
    label_type: str
    label_value: str
    effective_time: str
    observed_time: str
    source_type: str
    actor_id: str | None
    evidence_refs: tuple[EvidenceRef, ...]
    payload_hash: str
    label_payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LabelAssertion":
        mapped = _as_mapping(payload, "label_assertion")
        case_timeline_event_id = _require_hex32(
            mapped.get("case_timeline_event_id"),
            "label_assertion.case_timeline_event_id",
        )
        label_subject_key = LabelSubjectKey.from_payload(mapped.get("label_subject_key") or {})
        pins = _normalize_pins(mapped.get("pins"), "label_assertion.pins")
        if label_subject_key.platform_run_id != str(pins.get("platform_run_id")):
            raise LabelStoreContractError(
                "label_subject_key.platform_run_id must match pins.platform_run_id"
            )
        label_type = _require_non_empty_string(mapped.get("label_type"), "label_assertion.label_type")
        if label_type not in LABEL_TYPES:
            raise LabelStoreContractError(
                f"label_assertion.label_type must be one of {sorted(LABEL_TYPES)}"
            )
        label_value = _require_non_empty_string(mapped.get("label_value"), "label_assertion.label_value")
        if label_value not in LABEL_VALUES_BY_TYPE[label_type]:
            raise LabelStoreContractError(
                "label_assertion.label_value invalid for label_type="
                f"{label_type}; expected one of {sorted(LABEL_VALUES_BY_TYPE[label_type])}"
            )
        effective_time = _require_non_empty_string(
            mapped.get("effective_time"), "label_assertion.effective_time"
        )
        observed_time = _require_non_empty_string(
            mapped.get("observed_time"), "label_assertion.observed_time"
        )
        source_type = _require_non_empty_string(mapped.get("source_type"), "label_assertion.source_type")
        if source_type not in SOURCE_TYPES:
            raise LabelStoreContractError(
                f"label_assertion.source_type must be one of {sorted(SOURCE_TYPES)}"
            )
        actor_id_raw = mapped.get("actor_id")
        if source_type == "HUMAN":
            actor_id = _require_non_empty_string(actor_id_raw, "label_assertion.actor_id")
        else:
            actor_id = _require_non_empty_string(actor_id_raw, "label_assertion.actor_id") if actor_id_raw not in (None, "") else None
        evidence_refs = _normalize_evidence_refs(
            mapped.get("evidence_refs"), "label_assertion.evidence_refs"
        )

        expected_label_assertion_id = deterministic_label_assertion_id(
            case_timeline_event_id=case_timeline_event_id,
            label_subject_key=label_subject_key.as_dict(),
            label_type=label_type,
        )
        provided_label_assertion_id = mapped.get("label_assertion_id")
        if provided_label_assertion_id not in (None, ""):
            label_assertion_id = _require_hex32(
                provided_label_assertion_id, "label_assertion.label_assertion_id"
            )
            if label_assertion_id != expected_label_assertion_id:
                raise LabelStoreContractError(
                    "label_assertion.label_assertion_id does not match deterministic identity"
                )
        else:
            label_assertion_id = expected_label_assertion_id

        expected_payload_hash = canonical_label_assertion_payload_hash(
            label_subject_key=label_subject_key.as_dict(),
            label_type=label_type,
            label_value=label_value,
            effective_time=effective_time,
            observed_time=observed_time,
            source_type=source_type,
            actor_id=actor_id,
            evidence_refs=[item.as_dict() for item in evidence_refs],
        )
        provided_payload_hash = mapped.get("payload_hash")
        if provided_payload_hash not in (None, ""):
            payload_hash = _require_hex64(provided_payload_hash, "label_assertion.payload_hash")
            if payload_hash != expected_payload_hash:
                raise LabelStoreContractError(
                    "label_assertion.payload_hash mismatch for canonical assertion payload"
                )
        else:
            payload_hash = expected_payload_hash

        label_payload_raw = mapped.get("label_payload")
        label_payload = dict(label_payload_raw) if isinstance(label_payload_raw, Mapping) else {}

        return cls(
            label_assertion_id=label_assertion_id,
            case_timeline_event_id=case_timeline_event_id,
            label_subject_key=label_subject_key,
            pins=pins,
            label_type=label_type,
            label_value=label_value,
            effective_time=effective_time,
            observed_time=observed_time,
            source_type=source_type,
            actor_id=actor_id,
            evidence_refs=evidence_refs,
            payload_hash=payload_hash,
            label_payload=label_payload,
        )

    def dedupe_tuple(self) -> tuple[str, str, str, str]:
        subject = self.label_subject_key
        return (
            subject.platform_run_id,
            subject.event_id,
            self.label_type,
            self.label_assertion_id,
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "label_assertion_id": self.label_assertion_id,
            "case_timeline_event_id": self.case_timeline_event_id,
            "label_subject_key": self.label_subject_key.as_dict(),
            "pins": dict(self.pins),
            "label_type": self.label_type,
            "label_value": self.label_value,
            "effective_time": self.effective_time,
            "observed_time": self.observed_time,
            "source_type": self.source_type,
            "evidence_refs": [item.as_dict() for item in self.evidence_refs],
            "payload_hash": self.payload_hash,
        }
        if self.actor_id is not None:
            payload["actor_id"] = self.actor_id
        if self.label_payload:
            payload["label_payload"] = dict(self.label_payload)
        return payload


def _as_mapping(payload: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise LabelStoreContractError(f"{field_name} must be a mapping")
    return dict(payload)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LabelStoreContractError(f"{field_name} must be a non-empty string")
    return text


def _require_hex32(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    if not HEX32_RE.fullmatch(text):
        raise LabelStoreContractError(f"{field_name} must be 32-char lowercase hex")
    return text


def _require_hex64(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    if not HEX64_RE.fullmatch(text):
        raise LabelStoreContractError(f"{field_name} must be 64-char lowercase hex")
    return text


def _require_platform_run_id(value: Any, field_name: str) -> str:
    text = _require_non_empty_string(value, field_name)
    if not PLATFORM_RUN_ID_RE.fullmatch(text):
        raise LabelStoreContractError(
            f"{field_name} must match platform_YYYYMMDDTHHMMSSZ"
        )
    return text


def _normalize_pins(payload: Any, field_name: str) -> dict[str, Any]:
    pins = _as_mapping(payload, field_name)
    missing = [field for field in REQUIRED_PINS if pins.get(field) in (None, "")]
    if missing:
        raise LabelStoreContractError(f"{field_name} missing required pins: {','.join(missing)}")
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
        raise LabelStoreContractError(f"{field_name} must be an integer >= 0")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise LabelStoreContractError(f"{field_name} must be an integer >= 0") from exc
    if parsed < 0:
        raise LabelStoreContractError(f"{field_name} must be an integer >= 0")
    return parsed


def _normalize_evidence_refs(payload: Any, field_name: str) -> tuple[EvidenceRef, ...]:
    if payload in (None, ""):
        return tuple()
    if not isinstance(payload, list):
        raise LabelStoreContractError(f"{field_name} must be a list")
    refs = [EvidenceRef.from_payload(item) for item in payload]
    refs.sort(key=lambda item: (item.ref_type, item.ref_id, item.ref_scope or ""))
    return tuple(refs)
