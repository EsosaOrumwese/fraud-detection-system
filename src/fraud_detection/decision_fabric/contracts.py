"""Decision Fabric contract helpers (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import re


HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

DECISION_RESPONSE_REQUIRED_FIELDS: tuple[str, ...] = (
    "decision_id",
    "decision_kind",
    "bundle_ref",
    "snapshot_hash",
    "graph_version",
    "eb_offset_basis",
    "degrade_posture",
    "pins",
    "decided_at_utc",
    "policy_rev",
    "run_config_digest",
    "source_event",
    "decision",
)

ACTION_INTENT_REQUIRED_FIELDS: tuple[str, ...] = (
    "action_id",
    "decision_id",
    "action_kind",
    "idempotency_key",
    "pins",
    "requested_at_utc",
    "actor_principal",
    "origin",
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
DEGRADE_POSTURE_REQUIRED_FIELDS: tuple[str, ...] = (
    "mode",
    "capabilities_mask",
    "policy_rev",
    "posture_seq",
    "decided_at_utc",
)
CAPABILITY_MASK_REQUIRED_FIELDS: tuple[str, ...] = (
    "allow_ieg",
    "allowed_feature_groups",
    "allow_model_primary",
    "allow_model_stage2",
    "allow_fallback_heuristics",
    "action_posture",
)
ACTION_INTENT_ORIGINS: set[str] = {"DF", "CASE", "HUMAN", "OPS"}


class DecisionFabricContractError(ValueError):
    """Raised when DecisionResponse/ActionIntent payloads violate DF contracts."""


@dataclass(frozen=True)
class DecisionResponse:
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DecisionResponse":
        normalized = _as_mapping(payload, "DecisionResponse")
        _require_fields(normalized, DECISION_RESPONSE_REQUIRED_FIELDS, "DecisionResponse")

        decision_id = _as_non_empty_string(normalized.get("decision_id"), "decision_id")
        if not HEX32_RE.fullmatch(decision_id):
            raise DecisionFabricContractError("decision_id must be 32-char lowercase hex")

        _require_hex64(normalized.get("snapshot_hash"), "snapshot_hash")
        _require_hex64(normalized.get("run_config_digest"), "run_config_digest")

        bundle_ref = _as_mapping(normalized.get("bundle_ref"), "bundle_ref")
        _require_fields(bundle_ref, BUNDLE_REF_REQUIRED_FIELDS, "bundle_ref")
        _require_hex64(bundle_ref.get("bundle_id"), "bundle_ref.bundle_id")

        pins = _as_mapping(normalized.get("pins"), "pins")
        _require_fields(pins, PIN_REQUIRED_FIELDS, "pins")
        _require_hex64(pins.get("manifest_fingerprint"), "pins.manifest_fingerprint")
        _require_hex64(pins.get("parameter_hash"), "pins.parameter_hash")

        policy_rev = _as_mapping(normalized.get("policy_rev"), "policy_rev")
        _require_fields(policy_rev, POLICY_REV_REQUIRED_FIELDS, "policy_rev")

        degrade_posture = _as_mapping(normalized.get("degrade_posture"), "degrade_posture")
        _require_fields(degrade_posture, DEGRADE_POSTURE_REQUIRED_FIELDS, "degrade_posture")
        posture_policy_rev = _as_mapping(degrade_posture.get("policy_rev"), "degrade_posture.policy_rev")
        _require_fields(posture_policy_rev, POLICY_REV_REQUIRED_FIELDS, "degrade_posture.policy_rev")
        capability_mask = _as_mapping(degrade_posture.get("capabilities_mask"), "degrade_posture.capabilities_mask")
        _require_fields(
            capability_mask,
            CAPABILITY_MASK_REQUIRED_FIELDS,
            "degrade_posture.capabilities_mask",
        )

        graph_version = _as_mapping(normalized.get("graph_version"), "graph_version")
        _require_fields(graph_version, ("version_id", "watermark_ts_utc"), "graph_version")

        eb_offset_basis = _as_mapping(normalized.get("eb_offset_basis"), "eb_offset_basis")
        _require_fields(eb_offset_basis, ("stream", "offset_kind", "offsets"), "eb_offset_basis")
        offsets = eb_offset_basis.get("offsets")
        if not isinstance(offsets, list) or not offsets:
            raise DecisionFabricContractError("eb_offset_basis.offsets must be a non-empty list")

        source_event = _as_mapping(normalized.get("source_event"), "source_event")
        _require_fields(source_event, ("event_id", "event_type", "ts_utc", "eb_ref"), "source_event")
        _as_mapping(source_event.get("eb_ref"), "source_event.eb_ref")

        decision_obj = normalized.get("decision")
        if not isinstance(decision_obj, dict):
            raise DecisionFabricContractError("decision must be an object")

        return cls(payload=dict(normalized))

    @property
    def decision_id(self) -> str:
        return str(self.payload["decision_id"])

    def as_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(frozen=True)
class ActionIntent:
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ActionIntent":
        normalized = _as_mapping(payload, "ActionIntent")
        _require_fields(normalized, ACTION_INTENT_REQUIRED_FIELDS, "ActionIntent")

        action_id = _as_non_empty_string(normalized.get("action_id"), "action_id")
        if not HEX32_RE.fullmatch(action_id):
            raise DecisionFabricContractError("action_id must be 32-char lowercase hex")
        decision_id = _as_non_empty_string(normalized.get("decision_id"), "decision_id")
        if not HEX32_RE.fullmatch(decision_id):
            raise DecisionFabricContractError("decision_id must be 32-char lowercase hex")
        _as_non_empty_string(normalized.get("idempotency_key"), "idempotency_key")
        _as_non_empty_string(normalized.get("action_kind"), "action_kind")
        _as_non_empty_string(normalized.get("actor_principal"), "actor_principal")
        _require_hex64(normalized.get("run_config_digest"), "run_config_digest")

        origin = _as_non_empty_string(normalized.get("origin"), "origin")
        if origin not in ACTION_INTENT_ORIGINS:
            raise DecisionFabricContractError(
                f"origin must be one of {sorted(ACTION_INTENT_ORIGINS)}"
            )

        pins = _as_mapping(normalized.get("pins"), "pins")
        _require_fields(pins, PIN_REQUIRED_FIELDS, "pins")
        _require_hex64(pins.get("manifest_fingerprint"), "pins.manifest_fingerprint")
        _require_hex64(pins.get("parameter_hash"), "pins.parameter_hash")

        policy_rev = _as_mapping(normalized.get("policy_rev"), "policy_rev")
        _require_fields(policy_rev, POLICY_REV_REQUIRED_FIELDS, "policy_rev")

        return cls(payload=dict(normalized))

    @property
    def action_id(self) -> str:
        return str(self.payload["action_id"])

    @property
    def decision_id(self) -> str:
        return str(self.payload["decision_id"])

    def as_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def validate_action_intent_lineage(
    decision: DecisionResponse,
    intents: list[ActionIntent],
) -> None:
    for index, intent in enumerate(intents):
        if intent.decision_id != decision.decision_id:
            raise DecisionFabricContractError(
                f"action intent at index {index} has decision_id mismatch"
            )


def _as_mapping(payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise DecisionFabricContractError(f"{name} must be a mapping")
    return dict(payload)


def _require_fields(payload: Mapping[str, Any], required: tuple[str, ...], name: str) -> None:
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise DecisionFabricContractError(f"{name} missing required fields: {','.join(missing)}")


def _as_non_empty_string(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DecisionFabricContractError(f"{name} must be a non-empty string")
    return text


def _require_hex64(value: Any, name: str) -> str:
    text = _as_non_empty_string(value, name)
    if not HEX64_RE.fullmatch(text):
        raise DecisionFabricContractError(f"{name} must be 64-char lowercase hex")
    return text
