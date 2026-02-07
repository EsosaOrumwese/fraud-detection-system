"""Decision Fabric inlet gating (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from fraud_detection.ingestion_gate.config import ClassMap
from fraud_detection.ingestion_gate.schemas import SchemaRegistry

from .config import DecisionTriggerPolicy


INLET_ACCEPT = "ACCEPT"
INLET_INVALID_ENVELOPE = "INVALID_ENVELOPE"
INLET_NON_TRAFFIC_TOPIC = "NON_TRAFFIC_TOPIC"
INLET_LOOP_PREVENTION = "LOOP_PREVENTION"
INLET_EVENT_TYPE_NOT_ALLOWED = "EVENT_TYPE_NOT_ALLOWED"
INLET_SCHEMA_VERSION_REQUIRED = "SCHEMA_VERSION_REQUIRED"
INLET_SCHEMA_VERSION_NOT_ALLOWED = "SCHEMA_VERSION_NOT_ALLOWED"
INLET_MISSING_REQUIRED_PINS = "MISSING_REQUIRED_PINS"
INLET_MISSING_EVENT_ID = "MISSING_EVENT_ID"
INLET_DUPLICATE = "DUPLICATE"
INLET_PAYLOAD_HASH_MISMATCH = "PAYLOAD_HASH_MISMATCH"


@dataclass(frozen=True)
class DfBusInput:
    topic: str
    partition: int
    offset: str
    offset_kind: str
    payload: dict[str, Any]
    published_at_utc: str | None = None


@dataclass(frozen=True)
class SourceEbRef:
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
class DecisionTriggerCandidate:
    source_event_id: str
    event_class: str
    payload_hash: str
    source_event_type: str
    schema_version: str
    source_ts_utc: str
    pins: dict[str, Any]
    source_eb_ref: SourceEbRef

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_event_id": self.source_event_id,
            "event_class": self.event_class,
            "payload_hash": self.payload_hash,
            "source_event_type": self.source_event_type,
            "schema_version": self.schema_version,
            "source_ts_utc": self.source_ts_utc,
            "pins": dict(self.pins),
            "source_eb_ref": self.source_eb_ref.as_dict(),
        }


@dataclass(frozen=True)
class DfInletResult:
    accepted: bool
    reason_code: str
    candidate: DecisionTriggerCandidate | None = None
    detail: str | None = None


class DecisionFabricInlet:
    def __init__(
        self,
        policy: DecisionTriggerPolicy,
        *,
        engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts",
        class_map_ref: Path | str = "config/platform/ig/class_map_v0.yaml",
    ) -> None:
        self.policy = policy
        self.envelope_registry = SchemaRegistry(Path(engine_contracts_root))
        self.class_map = ClassMap.load(Path(class_map_ref))
        self._collision_guard = _InMemoryCollisionGuard()

    def evaluate(self, record: DfBusInput) -> DfInletResult:
        envelope = _unwrap_envelope(record.payload)
        if envelope is None:
            return DfInletResult(accepted=False, reason_code=INLET_INVALID_ENVELOPE)
        if not self._is_valid_envelope(envelope):
            return DfInletResult(accepted=False, reason_code=INLET_INVALID_ENVELOPE)

        if record.topic not in self.policy.admitted_traffic_topics:
            return DfInletResult(
                accepted=False,
                reason_code=INLET_NON_TRAFFIC_TOPIC,
                detail=f"topic={record.topic}",
            )

        event_type = str(envelope.get("event_type") or "").strip()
        if self.policy.is_blocked_event_type(event_type):
            return DfInletResult(
                accepted=False,
                reason_code=INLET_LOOP_PREVENTION,
                detail=f"event_type={event_type}",
            )

        allowed_schema_versions = self.policy.allowed_schema_versions(event_type)
        if allowed_schema_versions is None:
            return DfInletResult(
                accepted=False,
                reason_code=INLET_EVENT_TYPE_NOT_ALLOWED,
                detail=f"event_type={event_type}",
            )

        schema_version = str(envelope.get("schema_version") or "").strip()
        if not schema_version:
            return DfInletResult(accepted=False, reason_code=INLET_SCHEMA_VERSION_REQUIRED)
        if schema_version not in allowed_schema_versions:
            return DfInletResult(
                accepted=False,
                reason_code=INLET_SCHEMA_VERSION_NOT_ALLOWED,
                detail=f"event_type={event_type} schema_version={schema_version}",
            )

        missing_pins = self.policy.missing_required_pins(envelope)
        if missing_pins:
            return DfInletResult(
                accepted=False,
                reason_code=INLET_MISSING_REQUIRED_PINS,
                detail=",".join(missing_pins),
            )

        source_event_id = str(envelope.get("event_id") or "").strip()
        if not source_event_id:
            return DfInletResult(accepted=False, reason_code=INLET_MISSING_EVENT_ID)
        platform_run_id = str(envelope.get("platform_run_id") or "").strip()
        event_class = str(envelope.get("event_class") or "").strip()
        if not event_class:
            event_class = self.class_map.class_for(event_type)
        payload_hash = _payload_hash(envelope)
        collision = self._collision_guard.observe(
            platform_run_id=platform_run_id,
            event_class=event_class,
            event_id=source_event_id,
            payload_hash=payload_hash,
        )
        if collision == "DUPLICATE":
            return DfInletResult(
                accepted=False,
                reason_code=INLET_DUPLICATE,
                detail=f"event_class={event_class} event_id={source_event_id}",
            )
        if collision == "PAYLOAD_HASH_MISMATCH":
            return DfInletResult(
                accepted=False,
                reason_code=INLET_PAYLOAD_HASH_MISMATCH,
                detail=f"event_class={event_class} event_id={source_event_id}",
            )

        candidate = DecisionTriggerCandidate(
            source_event_id=source_event_id,
            event_class=event_class,
            payload_hash=payload_hash,
            source_event_type=event_type,
            schema_version=schema_version,
            source_ts_utc=str(envelope.get("ts_utc") or ""),
            pins={pin: envelope.get(pin) for pin in self.policy.required_pins},
            source_eb_ref=SourceEbRef(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                published_at_utc=record.published_at_utc,
            ),
        )
        return DfInletResult(accepted=True, reason_code=INLET_ACCEPT, candidate=candidate)

    def _is_valid_envelope(self, envelope: dict[str, Any]) -> bool:
        try:
            self.envelope_registry.validate("canonical_event_envelope.schema.yaml", envelope)
        except Exception:
            return False
        return True


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


class _InMemoryCollisionGuard:
    def __init__(self) -> None:
        self._hash_by_tuple: dict[tuple[str, str, str], str] = {}

    def observe(
        self,
        *,
        platform_run_id: str,
        event_class: str,
        event_id: str,
        payload_hash: str,
    ) -> str:
        key = (platform_run_id, event_class, event_id)
        previous = self._hash_by_tuple.get(key)
        if previous is None:
            self._hash_by_tuple[key] = payload_hash
            return "NEW"
        if previous == payload_hash:
            return "DUPLICATE"
        return "PAYLOAD_HASH_MISMATCH"
