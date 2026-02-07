"""Action Layer contract helpers (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping


HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
PLATFORM_RUN_ID_RE = re.compile(r"^platform_[0-9]{8}T[0-9]{6}Z$")

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

ACTION_OUTCOME_REQUIRED_FIELDS: tuple[str, ...] = (
    "outcome_id",
    "decision_id",
    "action_id",
    "action_kind",
    "status",
    "idempotency_key",
    "actor_principal",
    "origin",
    "authz_policy_rev",
    "run_config_digest",
    "pins",
    "completed_at_utc",
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
ACTION_INTENT_ORIGINS: set[str] = {"DF", "CASE", "HUMAN", "OPS"}
ACTION_OUTCOME_STATUSES: set[str] = {"EXECUTED", "DENIED", "FAILED"}


class ActionLayerContractError(ValueError):
    """Raised when ActionIntent/ActionOutcome payloads violate AL contracts."""


@dataclass(frozen=True)
class ActionIntent:
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ActionIntent":
        normalized = _as_mapping(payload, "ActionIntent")
        _require_fields(normalized, ACTION_INTENT_REQUIRED_FIELDS, "ActionIntent")

        action_id = _as_non_empty_string(normalized.get("action_id"), "action_id")
        if not HEX32_RE.fullmatch(action_id):
            raise ActionLayerContractError("action_id must be 32-char lowercase hex")

        decision_id = _as_non_empty_string(normalized.get("decision_id"), "decision_id")
        if not HEX32_RE.fullmatch(decision_id):
            raise ActionLayerContractError("decision_id must be 32-char lowercase hex")

        _as_non_empty_string(normalized.get("action_kind"), "action_kind")
        _as_non_empty_string(normalized.get("idempotency_key"), "idempotency_key")
        _as_non_empty_string(normalized.get("actor_principal"), "actor_principal")
        _require_hex64(normalized.get("run_config_digest"), "run_config_digest")

        origin = _as_non_empty_string(normalized.get("origin"), "origin")
        if origin not in ACTION_INTENT_ORIGINS:
            raise ActionLayerContractError(
                f"origin must be one of {sorted(ACTION_INTENT_ORIGINS)}"
            )

        pins = _as_mapping(normalized.get("pins"), "pins")
        _validate_pins(pins, field_name="pins")

        policy_rev = _as_mapping(normalized.get("policy_rev"), "policy_rev")
        _require_fields(policy_rev, POLICY_REV_REQUIRED_FIELDS, "policy_rev")

        return cls(payload=dict(normalized))

    @property
    def action_id(self) -> str:
        return str(self.payload["action_id"])

    @property
    def decision_id(self) -> str:
        return str(self.payload["decision_id"])

    @property
    def idempotency_key(self) -> str:
        return str(self.payload["idempotency_key"])

    def semantic_identity(self) -> str:
        return build_semantic_idempotency_key(self.payload)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(frozen=True)
class ActionOutcome:
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ActionOutcome":
        normalized = _as_mapping(payload, "ActionOutcome")
        _require_fields(normalized, ACTION_OUTCOME_REQUIRED_FIELDS, "ActionOutcome")

        outcome_id = _as_non_empty_string(normalized.get("outcome_id"), "outcome_id")
        if not HEX32_RE.fullmatch(outcome_id):
            raise ActionLayerContractError("outcome_id must be 32-char lowercase hex")

        action_id = _as_non_empty_string(normalized.get("action_id"), "action_id")
        if not HEX32_RE.fullmatch(action_id):
            raise ActionLayerContractError("action_id must be 32-char lowercase hex")

        decision_id = _as_non_empty_string(normalized.get("decision_id"), "decision_id")
        if not HEX32_RE.fullmatch(decision_id):
            raise ActionLayerContractError("decision_id must be 32-char lowercase hex")

        _as_non_empty_string(normalized.get("action_kind"), "action_kind")
        _as_non_empty_string(normalized.get("idempotency_key"), "idempotency_key")
        _as_non_empty_string(normalized.get("actor_principal"), "actor_principal")
        _require_hex64(normalized.get("run_config_digest"), "run_config_digest")

        origin = _as_non_empty_string(normalized.get("origin"), "origin")
        if origin not in ACTION_INTENT_ORIGINS:
            raise ActionLayerContractError(
                f"origin must be one of {sorted(ACTION_INTENT_ORIGINS)}"
            )

        status = _as_non_empty_string(normalized.get("status"), "status")
        if status not in ACTION_OUTCOME_STATUSES:
            raise ActionLayerContractError(
                f"status must be one of {sorted(ACTION_OUTCOME_STATUSES)}"
            )

        pins = _as_mapping(normalized.get("pins"), "pins")
        _validate_pins(pins, field_name="pins")

        policy_rev = _as_mapping(normalized.get("authz_policy_rev"), "authz_policy_rev")
        _require_fields(policy_rev, POLICY_REV_REQUIRED_FIELDS, "authz_policy_rev")

        attempt_seq = normalized.get("attempt_seq")
        if attempt_seq is not None:
            parsed = _as_positive_int(attempt_seq, "attempt_seq")
            if parsed < 1:
                raise ActionLayerContractError("attempt_seq must be >= 1 when provided")

        return cls(payload=dict(normalized))

    @property
    def outcome_id(self) -> str:
        return str(self.payload["outcome_id"])

    @property
    def action_id(self) -> str:
        return str(self.payload["action_id"])

    @property
    def decision_id(self) -> str:
        return str(self.payload["decision_id"])

    def as_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def validate_outcome_lineage(intent: ActionIntent, outcome: ActionOutcome) -> None:
    if outcome.decision_id != intent.decision_id:
        raise ActionLayerContractError("ActionOutcome decision_id mismatch for ActionIntent")
    if outcome.action_id != intent.action_id:
        raise ActionLayerContractError("ActionOutcome action_id mismatch for ActionIntent")
    if str(outcome.payload.get("idempotency_key")) != intent.idempotency_key:
        raise ActionLayerContractError("ActionOutcome idempotency_key mismatch for ActionIntent")


def build_semantic_idempotency_key(payload: Mapping[str, Any]) -> str:
    normalized = _as_mapping(payload, "payload")
    pins = _as_mapping(normalized.get("pins"), "pins")
    _validate_pins(pins, field_name="pins")
    idempotency_key = _as_non_empty_string(normalized.get("idempotency_key"), "idempotency_key")
    identity = {
        "platform_run_id": pins["platform_run_id"],
        "scenario_run_id": pins["scenario_run_id"],
        "idempotency_key": idempotency_key,
    }
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _as_mapping(payload: Any, name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ActionLayerContractError(f"{name} must be a mapping")
    return dict(payload)


def _require_fields(payload: Mapping[str, Any], required: tuple[str, ...], name: str) -> None:
    missing = [field for field in required if payload.get(field) in (None, "")]
    if missing:
        raise ActionLayerContractError(f"{name} missing required fields: {','.join(missing)}")


def _as_non_empty_string(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ActionLayerContractError(f"{name} must be a non-empty string")
    return text


def _require_hex64(value: Any, name: str) -> str:
    text = _as_non_empty_string(value, name)
    if not HEX64_RE.fullmatch(text):
        raise ActionLayerContractError(f"{name} must be 64-char lowercase hex")
    return text


def _validate_pins(pins: Mapping[str, Any], *, field_name: str) -> None:
    _require_fields(pins, PIN_REQUIRED_FIELDS, field_name)
    platform_run_id = _as_non_empty_string(pins.get("platform_run_id"), f"{field_name}.platform_run_id")
    if not PLATFORM_RUN_ID_RE.fullmatch(platform_run_id):
        raise ActionLayerContractError(
            f"{field_name}.platform_run_id must match platform_YYYYMMDDTHHMMSSZ"
        )
    scenario_run_id = _as_non_empty_string(pins.get("scenario_run_id"), f"{field_name}.scenario_run_id")
    if not HEX32_RE.fullmatch(scenario_run_id):
        raise ActionLayerContractError(f"{field_name}.scenario_run_id must be 32-char lowercase hex")
    _require_hex64(pins.get("manifest_fingerprint"), f"{field_name}.manifest_fingerprint")
    _require_hex64(pins.get("parameter_hash"), f"{field_name}.parameter_hash")
    _as_non_empty_string(pins.get("scenario_id"), f"{field_name}.scenario_id")
    _as_positive_int(pins.get("seed"), f"{field_name}.seed")
    run_id_raw = pins.get("run_id")
    if run_id_raw not in (None, ""):
        run_id = _as_non_empty_string(run_id_raw, f"{field_name}.run_id")
        if not HEX32_RE.fullmatch(run_id):
            raise ActionLayerContractError(f"{field_name}.run_id must be 32-char lowercase hex")


def _as_positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise ActionLayerContractError(f"{name} must be an integer >= 0")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ActionLayerContractError(f"{name} must be an integer >= 0") from exc
    if parsed < 0:
        raise ActionLayerContractError(f"{name} must be an integer >= 0")
    return parsed


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

