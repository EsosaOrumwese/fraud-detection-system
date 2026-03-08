"""Shared internal canonical-event publish helpers.

Internal platform hops should route canonical envelopes directly onto the
native bus using the same class-map and partitioning contract as IG.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from fraud_detection.event_bus import EbRef, EventBusPublisher, FileEventBusPublisher
from fraud_detection.ingestion_gate.config import ClassMap
from fraud_detection.ingestion_gate.partitioning import PartitioningProfiles
from fraud_detection.ingestion_gate.schemas import SchemaRegistry


@dataclass(frozen=True)
class InternalPublishResult:
    event_id: str
    event_type: str
    event_class: str
    partition_profile_id: str
    partition_key: str
    eb_ref: EbRef


class InternalEventPublishError(ValueError):
    """Raised when an internal canonical-event publish cannot proceed safely."""


@dataclass
class InternalCanonicalEventPublisher:
    event_bus_kind: str
    event_bus_root: str
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    class_map_ref: Path | str
    partitioning_profiles_ref: Path | str
    engine_contracts_root: Path | str = "docs/model_spec/data-engine/interface_pack/contracts"
    default_profile_id: str = "ig.partitioning.v0.traffic"
    client_id: str = "platform-internal-publisher"

    def __post_init__(self) -> None:
        self._class_map = ClassMap.load(Path(self.class_map_ref))
        self._partitioning = PartitioningProfiles(str(self.partitioning_profiles_ref))
        self._schema_registry = SchemaRegistry(Path(self.engine_contracts_root))
        self._bus = _build_bus(
            event_bus_kind=str(self.event_bus_kind or "").strip().lower(),
            event_bus_root=str(self.event_bus_root or "").strip(),
            event_bus_stream=str(self.event_bus_stream or "").strip() or None,
            event_bus_region=str(self.event_bus_region or "").strip() or None,
            event_bus_endpoint_url=str(self.event_bus_endpoint_url or "").strip() or None,
            client_id=self.client_id,
        )

    def publish_envelope(self, envelope: Mapping[str, Any]) -> InternalPublishResult:
        payload = dict(envelope)
        self._validate_envelope(payload)
        event_type = str(payload.get("event_type") or "").strip()
        if event_type not in self._class_map.event_classes:
            raise InternalEventPublishError(f"EVENT_CLASS_UNMAPPED:{event_type or 'empty'}")
        event_class = self._class_map.class_for(event_type)
        profile_id = _profile_id_for_class(event_class, self.default_profile_id)
        partition_key = self._partitioning.derive_key(profile_id, payload)
        profile = self._partitioning.get(profile_id)
        eb_ref = self._bus.publish(profile.stream, partition_key, payload)
        return InternalPublishResult(
            event_id=str(payload.get("event_id") or ""),
            event_type=event_type,
            event_class=event_class,
            partition_profile_id=profile_id,
            partition_key=partition_key,
            eb_ref=eb_ref,
        )

    def _validate_envelope(self, envelope: Mapping[str, Any]) -> None:
        try:
            self._schema_registry.validate("canonical_event_envelope.schema.yaml", dict(envelope))
        except Exception as exc:  # pragma: no cover - defensive
            raise InternalEventPublishError(f"CANONICAL_ENVELOPE_INVALID:{exc}") from exc
        event_type = str(envelope.get("event_type") or "").strip()
        if not event_type:
            raise InternalEventPublishError("EVENT_TYPE_MISSING")
        required_pins = self._class_map.required_pins_for(event_type)
        payload_pins = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else {}
        nested_pins = payload_pins.get("pins") if isinstance(payload_pins.get("pins"), Mapping) else {}
        missing: list[str] = []
        for field in required_pins:
            direct = envelope.get(field)
            nested = nested_pins.get(field)
            value = direct if direct not in (None, "") else nested
            if value in (None, ""):
                missing.append(field)
        if missing:
            raise InternalEventPublishError(f"REQUIRED_PINS_MISSING:{','.join(sorted(missing))}")


def _build_bus(
    *,
    event_bus_kind: str,
    event_bus_root: str,
    event_bus_stream: str | None,
    event_bus_region: str | None,
    event_bus_endpoint_url: str | None,
    client_id: str,
) -> EventBusPublisher:
    if event_bus_kind == "file":
        root = event_bus_root or "runs/fraud-platform/eb"
        return FileEventBusPublisher(Path(root))
    if event_bus_kind == "kafka":
        from fraud_detection.event_bus.kafka import build_kafka_publisher

        return build_kafka_publisher(client_id=client_id)
    if event_bus_kind == "kinesis":
        from fraud_detection.event_bus.kinesis import build_kinesis_publisher

        stream_name = event_bus_stream
        if isinstance(stream_name, str) and stream_name.lower() in {"", "auto", "topic"}:
            stream_name = None
        return build_kinesis_publisher(
            stream_name=stream_name,
            region=event_bus_region,
            endpoint_url=event_bus_endpoint_url,
        )
    raise InternalEventPublishError(f"EB_KIND_UNSUPPORTED:{event_bus_kind}")


def _profile_id_for_class(class_name: str, default_profile_id: str) -> str:
    if class_name == "control":
        return "ig.partitioning.v0.control"
    if class_name == "audit":
        return "ig.partitioning.v0.audit"
    if class_name == "rtdl_decision":
        return "ig.partitioning.v0.rtdl.decision"
    if class_name == "rtdl_action_intent":
        return "ig.partitioning.v0.rtdl.action_intent"
    if class_name == "rtdl_action_outcome":
        return "ig.partitioning.v0.rtdl.action_outcome"
    if class_name == "case_trigger":
        return "ig.partitioning.v0.case.trigger"
    if class_name == "traffic_baseline":
        return "ig.partitioning.v0.traffic.baseline"
    if class_name == "traffic_fraud":
        return "ig.partitioning.v0.traffic.fraud"
    if class_name == "context_arrival":
        return "ig.partitioning.v0.context.arrival_events"
    if class_name == "context_arrival_entities":
        return "ig.partitioning.v0.context.arrival_entities"
    if class_name == "context_flow_baseline":
        return "ig.partitioning.v0.context.flow_anchor.baseline"
    if class_name == "context_flow_fraud":
        return "ig.partitioning.v0.context.flow_anchor.fraud"
    return default_profile_id
