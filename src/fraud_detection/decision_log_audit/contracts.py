"""Decision Log & Audit contract helpers (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PLATFORM_RUN_ID_RE = re.compile(r"^platform_[0-9]{8}T[0-9]{6}Z$")

AUDIT_RECORD_REQUIRED_FIELDS: tuple[str, ...] = (
    "audit_id",
    "decision_event",
    "bundle_ref",
    "snapshot_hash",
    "graph_version",
    "eb_offset_basis",
    "degrade_posture",
    "pins",
    "recorded_at_utc",
    "policy_rev",
    "run_config_digest",
)

PIN_REQUIRED_FIELDS: tuple[str, ...] = (
    "platform_run_id",
    "scenario_run_id",
    "manifest_fingerprint",
    "parameter_hash",
    "scenario_id",
    "seed",
)

POLICY_REV_REQUIRED_FIELDS: tuple[str, ...] = ("policy_id", "revision")
BUNDLE_REF_REQUIRED_FIELDS: tuple[str, ...] = ("bundle_id",)
EB_REF_REQUIRED_FIELDS: tuple[str, ...] = ("topic", "partition", "offset", "offset_kind")
EVENT_REF_REQUIRED_FIELDS: tuple[str, ...] = ("event_id", "event_type", "ts_utc", "eb_ref")

AUDIT_CONTEXT_ROLES: set[str] = {"arrival_events", "arrival_entities", "flow_anchor"}
OFFSET_KINDS: set[str] = {"file_line", "kinesis_sequence", "kafka_offset"}


class DecisionLogAuditContractError(ValueError):
    """Raised when DLA AuditRecord payloads violate contract rules."""


@dataclass(frozen=True)
class AuditRecord:
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AuditRecord":
        normalized = _as_mapping(payload, "AuditRecord")
        _require_fields(normalized, AUDIT_RECORD_REQUIRED_FIELDS, "AuditRecord")

        audit_id = _as_non_empty_string(normalized.get("audit_id"), "audit_id")
        if not HEX32_RE.fullmatch(audit_id):
            raise DecisionLogAuditContractError("audit_id must be 32-char lowercase hex")

        _require_hex64(normalized.get("snapshot_hash"), "snapshot_hash")
        _require_hex64(normalized.get("run_config_digest"), "run_config_digest")

        decision_event = _normalize_event_ref(normalized.get("decision_event"), "decision_event")
        if not decision_event["event_id"]:
            raise DecisionLogAuditContractError("decision_event.event_id must be present")

        action_intents_raw = normalized.get("action_intents")
        if action_intents_raw is not None:
            _normalize_event_ref_list(action_intents_raw, "action_intents")

        action_outcomes_raw = normalized.get("action_outcomes")
        if action_outcomes_raw is not None:
            _normalize_event_ref_list(action_outcomes_raw, "action_outcomes")

        bundle_ref = _as_mapping(normalized.get("bundle_ref"), "bundle_ref")
        _require_fields(bundle_ref, BUNDLE_REF_REQUIRED_FIELDS, "bundle_ref")
        _require_hex64(bundle_ref.get("bundle_id"), "bundle_ref.bundle_id")

        graph_version = _as_mapping(normalized.get("graph_version"), "graph_version")
        _require_fields(graph_version, ("version_id", "watermark_ts_utc"), "graph_version")
        version_id = _as_non_empty_string(graph_version.get("version_id"), "graph_version.version_id")
        if not HEX32_RE.fullmatch(version_id):
            raise DecisionLogAuditContractError("graph_version.version_id must be 32-char lowercase hex")

        eb_offset_basis = _as_mapping(normalized.get("eb_offset_basis"), "eb_offset_basis")
        _require_fields(eb_offset_basis, ("stream", "offset_kind", "offsets"), "eb_offset_basis")
        _as_non_empty_string(eb_offset_basis.get("stream"), "eb_offset_basis.stream")
        offset_kind = _as_non_empty_string(eb_offset_basis.get("offset_kind"), "eb_offset_basis.offset_kind")
        if offset_kind not in OFFSET_KINDS:
            raise DecisionLogAuditContractError(
                f"eb_offset_basis.offset_kind must be one of {sorted(OFFSET_KINDS)}"
            )
        offsets = eb_offset_basis.get("offsets")
        if not isinstance(offsets, list) or not offsets:
            raise DecisionLogAuditContractError("eb_offset_basis.offsets must be a non-empty list")
        for idx, item in enumerate(offsets):
            mapped = _as_mapping(item, f"eb_offset_basis.offsets[{idx}]")
            _require_fields(mapped, ("partition", "offset"), f"eb_offset_basis.offsets[{idx}]")
            _as_non_negative_int(mapped.get("partition"), f"eb_offset_basis.offsets[{idx}].partition")
            _as_non_empty_string(mapped.get("offset"), f"eb_offset_basis.offsets[{idx}].offset")

        policy_rev = _as_mapping(normalized.get("policy_rev"), "policy_rev")
        _require_fields(policy_rev, POLICY_REV_REQUIRED_FIELDS, "policy_rev")

        degrade_posture = _as_mapping(normalized.get("degrade_posture"), "degrade_posture")
        _require_fields(
            degrade_posture,
            ("mode", "capabilities_mask", "policy_rev", "posture_seq", "decided_at_utc"),
            "degrade_posture",
        )
        posture_policy_rev = _as_mapping(degrade_posture.get("policy_rev"), "degrade_posture.policy_rev")
        _require_fields(posture_policy_rev, POLICY_REV_REQUIRED_FIELDS, "degrade_posture.policy_rev")

        pins = _as_mapping(normalized.get("pins"), "pins")
        _validate_pins(pins, field_name="pins")

        context_refs = normalized.get("context_refs")
        if context_refs is not None:
            if not isinstance(context_refs, list):
                raise DecisionLogAuditContractError("context_refs must be a list when provided")
            for idx, item in enumerate(context_refs):
                mapped = _as_mapping(item, f"context_refs[{idx}]")
                _require_fields(mapped, ("event_id", "event_type", "eb_ref", "role"), f"context_refs[{idx}]")
                _as_non_empty_string(mapped.get("event_id"), f"context_refs[{idx}].event_id")
                _as_non_empty_string(mapped.get("event_type"), f"context_refs[{idx}].event_type")
                role = _as_non_empty_string(mapped.get("role"), f"context_refs[{idx}].role")
                if role not in AUDIT_CONTEXT_ROLES:
                    raise DecisionLogAuditContractError(
                        f"context_refs[{idx}].role must be one of {sorted(AUDIT_CONTEXT_ROLES)}"
                    )
                _normalize_eb_ref(mapped.get("eb_ref"), f"context_refs[{idx}].eb_ref")

        return cls(payload=dict(normalized))

    @property
    def audit_id(self) -> str:
        return str(self.payload["audit_id"])

    @property
    def platform_run_id(self) -> str:
        return str(self.payload["pins"]["platform_run_id"])

    @property
    def scenario_run_id(self) -> str:
        return str(self.payload["pins"]["scenario_run_id"])

    def as_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def _normalize_event_ref_list(value: Any, field_name: str) -> None:
    if not isinstance(value, list):
        raise DecisionLogAuditContractError(f"{field_name} must be a list")
    for idx, item in enumerate(value):
        _normalize_event_ref(item, f"{field_name}[{idx}]")


def _normalize_event_ref(value: Any, field_name: str) -> dict[str, Any]:
    mapped = _as_mapping(value, field_name)
    _require_fields(mapped, EVENT_REF_REQUIRED_FIELDS, field_name)
    _as_non_empty_string(mapped.get("event_id"), f"{field_name}.event_id")
    _as_non_empty_string(mapped.get("event_type"), f"{field_name}.event_type")
    _as_non_empty_string(mapped.get("ts_utc"), f"{field_name}.ts_utc")
    _normalize_eb_ref(mapped.get("eb_ref"), f"{field_name}.eb_ref")
    return mapped


def _normalize_eb_ref(value: Any, field_name: str) -> dict[str, Any]:
    mapped = _as_mapping(value, field_name)
    _require_fields(mapped, EB_REF_REQUIRED_FIELDS, field_name)
    _as_non_empty_string(mapped.get("topic"), f"{field_name}.topic")
    _as_non_negative_int(mapped.get("partition"), f"{field_name}.partition")
    _as_non_empty_string(mapped.get("offset"), f"{field_name}.offset")
    offset_kind = _as_non_empty_string(mapped.get("offset_kind"), f"{field_name}.offset_kind")
    if offset_kind not in OFFSET_KINDS:
        raise DecisionLogAuditContractError(
            f"{field_name}.offset_kind must be one of {sorted(OFFSET_KINDS)}"
        )
    return mapped


def _validate_pins(pins: Mapping[str, Any], *, field_name: str) -> None:
    _require_fields(pins, PIN_REQUIRED_FIELDS, field_name)
    platform_run_id = _as_non_empty_string(pins.get("platform_run_id"), f"{field_name}.platform_run_id")
    if not PLATFORM_RUN_ID_RE.fullmatch(platform_run_id):
        raise DecisionLogAuditContractError(
            f"{field_name}.platform_run_id must match platform_YYYYMMDDTHHMMSSZ"
        )
    scenario_run_id = _as_non_empty_string(pins.get("scenario_run_id"), f"{field_name}.scenario_run_id")
    if not HEX32_RE.fullmatch(scenario_run_id):
        raise DecisionLogAuditContractError(f"{field_name}.scenario_run_id must be 32-char lowercase hex")
    _require_hex64(pins.get("manifest_fingerprint"), f"{field_name}.manifest_fingerprint")
    _require_hex64(pins.get("parameter_hash"), f"{field_name}.parameter_hash")
    _as_non_empty_string(pins.get("scenario_id"), f"{field_name}.scenario_id")
    _as_non_negative_int(pins.get("seed"), f"{field_name}.seed")
    run_id_raw = pins.get("run_id")
    if run_id_raw not in (None, ""):
        run_id = _as_non_empty_string(run_id_raw, f"{field_name}.run_id")
        if not HEX32_RE.fullmatch(run_id):
            raise DecisionLogAuditContractError(f"{field_name}.run_id must be 32-char lowercase hex")


def _as_mapping(payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DecisionLogAuditContractError(f"{name} must be a mapping")
    return dict(payload)


def _require_fields(payload: Mapping[str, Any], required: tuple[str, ...], name: str) -> None:
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise DecisionLogAuditContractError(f"{name} missing required fields: {','.join(missing)}")


def _as_non_empty_string(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionLogAuditContractError(f"{name} must be a non-empty string")
    return text


def _as_non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise DecisionLogAuditContractError(f"{name} must be an integer >= 0")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DecisionLogAuditContractError(f"{name} must be an integer >= 0") from exc
    if parsed < 0:
        raise DecisionLogAuditContractError(f"{name} must be an integer >= 0")
    return parsed


def _require_hex64(value: Any, name: str) -> str:
    text = _as_non_empty_string(value, name)
    if not HEX64_RE.fullmatch(text):
        raise DecisionLogAuditContractError(f"{name} must be 64-char lowercase hex")
    return text

