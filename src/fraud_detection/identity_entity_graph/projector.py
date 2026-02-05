"""IEG projector: consume EB events and build projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from fraud_detection.event_bus import EbRecord, EventBusReader
from fraud_detection.ingestion_gate.config import ClassMap
from fraud_detection.ingestion_gate.schemas import SchemaRegistry

from .classification import ClassificationMap, GRAPH_IRRELEVANT, GRAPH_MUTATING, GRAPH_UNUSABLE
from .config import IegProfile
from .hints import IdentityHint, IdentityHintsPolicy, extract_identity_hints
from .ids import dedupe_key, entity_id_from_hint
from .store import ApplyResult, build_store

logger = logging.getLogger("fraud_detection.ieg")


@dataclass(frozen=True)
class BusRecord:
    topic: str
    partition: int
    offset: str
    offset_kind: str
    payload: dict[str, Any]
    published_at_utc: str | None = None


class IdentityGraphProjector:
    def __init__(self, profile: IegProfile) -> None:
        self.profile = profile
        self.class_map = ClassMap.load(Path(profile.policy.class_map_ref))
        self.classification = ClassificationMap.load(Path(profile.policy.classification_ref))
        self.hints_policy = IdentityHintsPolicy.load(Path(profile.policy.identity_hints_ref))
        self.envelope_registry = SchemaRegistry(Path(profile.wiring.engine_contracts_root))
        self.store = build_store(profile.wiring.projection_db_dsn, stream_id=profile.policy.graph_stream_id)
        self._file_reader = None
        self._kinesis_reader = None
        if profile.wiring.event_bus_kind == "file":
            bus_root = profile.wiring.event_bus_root or "runs/fraud-platform/eb"
            self._file_reader = EventBusReader(Path(bus_root))
        elif profile.wiring.event_bus_kind == "kinesis":
            from fraud_detection.event_bus.kinesis import KinesisEventBusReader

            self._kinesis_reader = KinesisEventBusReader(
                stream_name=profile.wiring.event_bus_stream,
                region=profile.wiring.event_bus_region,
                endpoint_url=profile.wiring.event_bus_endpoint_url,
            )
        else:
            raise RuntimeError("IEG_EVENT_BUS_KIND_UNSUPPORTED")

    @classmethod
    def build(cls, profile_path: str) -> "IdentityGraphProjector":
        profile = IegProfile.load(Path(profile_path))
        return cls(profile)

    def run_once(self) -> int:
        processed = 0
        topics = self.profile.wiring.event_bus_topics or []
        if self.profile.wiring.event_bus_kind == "file":
            for topic in topics:
                for partition in self._file_partitions(topic):
                    processed += self._consume_file_topic(topic, partition)
        else:
            fixed_stream = self.profile.wiring.event_bus_stream
            if fixed_stream and str(fixed_stream).lower() not in {"", "auto", "topic"}:
                processed += self._consume_kinesis_topic(str(fixed_stream))
            else:
                for topic in topics:
                    processed += self._consume_kinesis_topic(topic)
        return processed

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.profile.wiring.poll_sleep_seconds)

    def _consume_file_topic(self, topic: str, partition: int) -> int:
        assert self._file_reader is not None
        checkpoint = self.store.get_checkpoint(topic=topic, partition=partition)
        from_offset = int(checkpoint.next_offset) if checkpoint else 0
        records = self._file_reader.read(
            topic,
            partition=partition,
            from_offset=from_offset,
            max_records=self.profile.wiring.poll_max_records,
        )
        return self._process_records(topic, records, offset_kind="file_line")

    def _consume_kinesis_topic(self, topic: str) -> int:
        assert self._kinesis_reader is not None
        stream = self._stream_name(topic)
        shard_ids = self._kinesis_reader.list_shards(stream)
        processed = 0
        for shard_id in shard_ids:
            partition = _partition_id_from_shard(shard_id)
            checkpoint = self.store.get_checkpoint(topic=topic, partition=partition)
            from_offset = checkpoint.next_offset if checkpoint else None
            records = self._kinesis_reader.read(
                stream_name=stream,
                shard_id=shard_id,
                from_sequence=from_offset,
                limit=self.profile.wiring.poll_max_records,
            )
            processed += self._process_kinesis_records(topic, partition, records)
        return processed

    def _process_records(self, topic: str, records: Iterable[EbRecord], *, offset_kind: str) -> int:
        processed = 0
        for record in records:
            envelope = _unwrap_envelope(record.record)
            if not envelope:
                continue
            bus_record = BusRecord(
                topic=topic,
                partition=record.partition,
                offset=str(record.offset),
                offset_kind=offset_kind,
                payload=envelope,
                published_at_utc=record.record.get("published_at_utc"),
            )
            self._process_record(bus_record)
            processed += 1
        return processed

    def _process_kinesis_records(self, topic: str, partition: int, records: Iterable[dict[str, Any]]) -> int:
        processed = 0
        for record in records:
            envelope = record.get("payload")
            if not isinstance(envelope, dict):
                continue
            bus_record = BusRecord(
                topic=topic,
                partition=partition,
                offset=str(record.get("sequence_number") or ""),
                offset_kind="kinesis_sequence",
                payload=envelope,
                published_at_utc=record.get("published_at_utc"),
            )
            self._process_record(bus_record)
            processed += 1
        return processed

    def _process_record(self, record: BusRecord) -> ApplyResult:
        envelope = record.payload
        event_id = str(envelope.get("event_id") or "unknown")
        event_type = str(envelope.get("event_type") or "unknown")
        try:
            self.envelope_registry.validate("canonical_event_envelope.schema.yaml", envelope)
        except Exception:
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                reason_code="ENVELOPE_INVALID",
                details=None,
                event_ts_utc=envelope.get("ts_utc"),
            )

        class_name = self.class_map.class_for(event_type)
        missing = [
            pin for pin in self.class_map.required_pins_for(event_type) if envelope.get(pin) in (None, "")
        ]
        if missing:
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                reason_code="REQUIRED_PINS_MISSING",
                details={"missing": missing},
                event_ts_utc=envelope.get("ts_utc"),
            )

        classification = self.classification.classify(event_type)
        if classification == GRAPH_IRRELEVANT:
            return self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=envelope.get("ts_utc"),
            )

        scenario_run_id = envelope.get("scenario_run_id")
        if not scenario_run_id:
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                scenario_run_id=envelope.get("run_id"),
                reason_code="SCENARIO_RUN_ID_MISSING",
                details=None,
                event_ts_utc=envelope.get("ts_utc"),
            )

        if classification == GRAPH_UNUSABLE:
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                scenario_run_id=scenario_run_id,
                reason_code="CLASSIFICATION_UNSUPPORTED",
                details=None,
                event_ts_utc=envelope.get("ts_utc"),
            )

        identity_hints = extract_identity_hints(envelope, self.hints_policy)
        if not identity_hints:
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                scenario_run_id=scenario_run_id,
                reason_code="IDENTITY_HINTS_MISSING",
                details=None,
                event_ts_utc=envelope.get("ts_utc"),
            )

        pins = _pins_for_envelope(envelope, scenario_run_id)
        dedupe = dedupe_key(scenario_run_id, class_name, event_id)
        payload_hash = _payload_hash(envelope)
        normalized_hints = _assign_entity_ids(identity_hints, pins)
        pins["dedupe_key"] = dedupe
        return self.store.apply_mutation(
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            offset_kind=record.offset_kind,
            event_id=event_id,
            event_type=event_type,
            class_name=class_name,
            scenario_run_id=scenario_run_id,
            pins=pins,
            payload_hash=payload_hash,
            identity_hints=normalized_hints,
            event_ts_utc=envelope.get("ts_utc"),
        )

    def _file_partitions(self, topic: str) -> list[int]:
        assert self._file_reader is not None
        root = self._file_reader.root / topic
        if not root.exists():
            return [0]
        partitions = []
        for path in root.glob("partition=*.jsonl"):
            name = path.stem
            if name.startswith("partition="):
                try:
                    partitions.append(int(name.split("partition=")[1]))
                except ValueError:
                    continue
        return sorted(partitions) or [0]

    def _stream_name(self, topic: str) -> str:
        stream = self.profile.wiring.event_bus_stream
        if not stream or str(stream).lower() in {"", "auto", "topic"}:
            return topic
        return stream


def _unwrap_envelope(record: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    payload = record.get("payload")
    if isinstance(payload, dict):
        return payload
    if "event_type" in record and "event_id" in record:
        return record
    return None


def _payload_hash(envelope: dict[str, Any]) -> str:
    payload = {
        "event_type": envelope.get("event_type"),
        "schema_version": envelope.get("schema_version"),
        "payload": envelope.get("payload"),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _pins_for_envelope(envelope: dict[str, Any], scenario_run_id: str) -> dict[str, Any]:
    return {
        "platform_run_id": envelope.get("platform_run_id"),
        "scenario_run_id": scenario_run_id,
        "scenario_id": envelope.get("scenario_id"),
        "run_id": envelope.get("run_id"),
        "manifest_fingerprint": envelope.get("manifest_fingerprint"),
        "parameter_hash": envelope.get("parameter_hash"),
        "seed": envelope.get("seed"),
    }


def _assign_entity_ids(identity_hints: list[IdentityHint], pins: dict[str, Any]) -> list[IdentityHint]:
    normalized: list[IdentityHint] = []
    for hint in identity_hints:
        entity_id = hint.entity_id or entity_id_from_hint(hint, pins)
        normalized.append(
            IdentityHint(
                identifier_type=hint.identifier_type,
                identifier_value=hint.identifier_value,
                entity_type=hint.entity_type,
                entity_id=entity_id,
                source_event_id=hint.source_event_id,
            )
        )
    return normalized


def _partition_id_from_shard(shard_id: str) -> int:
    try:
        return int(shard_id.split("-")[-1])
    except ValueError:
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="IEG projector (Phase 1)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Process a single batch and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    projector = IdentityGraphProjector.build(args.profile)
    if args.once:
        projector.run_once()
    else:
        projector.run_forever()


if __name__ == "__main__":
    main()
