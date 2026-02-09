"""Decision Log & Audit inlet gating (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from fraud_detection.action_layer.contracts import ActionLayerContractError, ActionOutcome
from fraud_detection.decision_fabric.contracts import (
    ActionIntent,
    DecisionFabricContractError,
    DecisionResponse,
)
from fraud_detection.ingestion_gate.schemas import SchemaRegistry

from .config import DecisionLogAuditIntakePolicy


DLA_INLET_ACCEPT = "ACCEPT"
DLA_INLET_INVALID_ENVELOPE = "INVALID_ENVELOPE"
DLA_INLET_NON_AUDIT_TOPIC = "NON_AUDIT_TOPIC"
DLA_INLET_UNKNOWN_EVENT_FAMILY = "UNKNOWN_EVENT_FAMILY"
DLA_INLET_SCHEMA_VERSION_REQUIRED = "SCHEMA_VERSION_REQUIRED"
DLA_INLET_SCHEMA_VERSION_NOT_ALLOWED = "SCHEMA_VERSION_NOT_ALLOWED"
DLA_INLET_MISSING_REQUIRED_PINS = "MISSING_REQUIRED_PINS"
DLA_INLET_RUN_SCOPE_MISMATCH = "RUN_SCOPE_MISMATCH"
DLA_INLET_MISSING_EVENT_ID = "MISSING_EVENT_ID"
DLA_INLET_PAYLOAD_CONTRACT_INVALID = "PAYLOAD_CONTRACT_INVALID"


@dataclass(frozen=True)
class DlaBusInput:
    topic: str
    partition: int
    offset: str
    offset_kind: str
    payload: dict[str, Any]
    published_at_utc: str | None = None


@dataclass(frozen=True)
class DlaSourceEbRef:
    topic: str
    partition: int
    offset: str
    offset_kind: str
    published_at_utc: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topic": self.topic,
            "partition": self.partition,
            "offset": self.offset,
            "offset_kind": self.offset_kind,
        }
        if self.published_at_utc:
            payload["published_at_utc"] = self.published_at_utc
        return payload


@dataclass(frozen=True)
class DlaInletCandidate:
    event_id: str
    event_type: str
    schema_version: str
    payload_hash: str
    source_ts_utc: str
    pins: dict[str, Any]
    envelope: dict[str, Any]
    source_eb_ref: DlaSourceEbRef


@dataclass(frozen=True)
class DlaInletResult:
    accepted: bool
    reason_code: str
    candidate: DlaInletCandidate | None = None
    detail: str | None = None


class DecisionLogAuditInlet:
    def __init__(
        self,
        policy: DecisionLogAuditIntakePolicy,
        *,
        engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts",
    ) -> None:
        self.policy = policy
        self.envelope_registry = SchemaRegistry(Path(engine_contracts_root))

    def evaluate(self, record: DlaBusInput) -> DlaInletResult:
        envelope = _unwrap_envelope(record.payload)
        if envelope is None:
            return DlaInletResult(accepted=False, reason_code=DLA_INLET_INVALID_ENVELOPE)
        if not self._is_valid_envelope(envelope):
            return DlaInletResult(accepted=False, reason_code=DLA_INLET_INVALID_ENVELOPE)

        if record.topic not in self.policy.admitted_topics:
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_NON_AUDIT_TOPIC,
                detail=f"topic={record.topic}",
            )

        event_type = str(envelope.get("event_type") or "").strip()

        missing_pins = self.policy.missing_required_pins(envelope)
        if missing_pins:
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_MISSING_REQUIRED_PINS,
                detail=",".join(missing_pins),
            )

        required_platform_run_id = self.policy.required_platform_run_id
        platform_run_id = str(envelope.get("platform_run_id") or "").strip()
        if required_platform_run_id and platform_run_id != required_platform_run_id:
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_RUN_SCOPE_MISMATCH,
                detail=f"platform_run_id={platform_run_id}",
            )

        allowed_schema_versions = self.policy.allowed_schema_versions(event_type)
        if allowed_schema_versions is None:
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_UNKNOWN_EVENT_FAMILY,
                detail=f"event_type={event_type}",
            )

        schema_version = str(envelope.get("schema_version") or "").strip()
        if not schema_version:
            return DlaInletResult(accepted=False, reason_code=DLA_INLET_SCHEMA_VERSION_REQUIRED)
        if schema_version not in allowed_schema_versions:
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_SCHEMA_VERSION_NOT_ALLOWED,
                detail=f"event_type={event_type} schema_version={schema_version}",
            )

        event_id = str(envelope.get("event_id") or "").strip()
        if not event_id:
            return DlaInletResult(accepted=False, reason_code=DLA_INLET_MISSING_EVENT_ID)

        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_PAYLOAD_CONTRACT_INVALID,
                detail="payload must be a mapping",
            )
        payload_contract = self.policy.payload_contract(event_type)
        if payload_contract is None:
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_UNKNOWN_EVENT_FAMILY,
                detail=f"event_type={event_type}",
            )
        contract_error = _validate_payload_contract(payload_contract=payload_contract, payload=payload)
        if contract_error is not None:
            return DlaInletResult(
                accepted=False,
                reason_code=DLA_INLET_PAYLOAD_CONTRACT_INVALID,
                detail=contract_error,
            )

        pins = {pin: envelope.get(pin) for pin in self.policy.required_pins}
        run_id = envelope.get("run_id")
        if run_id not in (None, ""):
            pins["run_id"] = run_id
        candidate = DlaInletCandidate(
            event_id=event_id,
            event_type=event_type,
            schema_version=schema_version,
            payload_hash=_payload_hash(envelope),
            source_ts_utc=str(envelope.get("ts_utc") or ""),
            pins=pins,
            envelope=dict(envelope),
            source_eb_ref=DlaSourceEbRef(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                published_at_utc=record.published_at_utc,
            ),
        )
        return DlaInletResult(accepted=True, reason_code=DLA_INLET_ACCEPT, candidate=candidate)

    def _is_valid_envelope(self, envelope: dict[str, Any]) -> bool:
        try:
            self.envelope_registry.validate("canonical_event_envelope.schema.yaml", envelope)
        except Exception:
            return False
        return True


def _validate_payload_contract(*, payload_contract: str, payload: dict[str, Any]) -> str | None:
    try:
        if payload_contract == "decision_response":
            DecisionResponse.from_payload(payload)
        elif payload_contract == "action_intent":
            ActionIntent.from_payload(payload)
        elif payload_contract == "action_outcome":
            ActionOutcome.from_payload(payload)
        else:
            return f"unsupported payload_contract: {payload_contract}"
    except (DecisionFabricContractError, ActionLayerContractError, ValueError) as exc:
        return str(exc)[:256]
    return None


def _unwrap_envelope(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    nested = value.get("envelope")
    if isinstance(nested, dict):
        return dict(nested)
    return dict(value)


def _payload_hash(envelope: dict[str, Any]) -> str:
    payload = {
        "event_type": envelope.get("event_type"),
        "schema_version": envelope.get("schema_version"),
        "payload": envelope.get("payload"),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
