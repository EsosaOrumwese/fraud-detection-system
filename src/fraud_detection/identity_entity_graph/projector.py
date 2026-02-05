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
from collections import deque

from fraud_detection.event_bus import EbRecord, EventBusReader
from fraud_detection.ingestion_gate.config import ClassMap
from fraud_detection.ingestion_gate.schemas import SchemaRegistry

from .classification import ClassificationMap, GRAPH_IRRELEVANT, GRAPH_MUTATING, GRAPH_UNUSABLE
from .config import IegProfile
from .hints import IdentityHint, IdentityHintsPolicy, extract_identity_hints
from .ids import dedupe_key, entity_id_from_hint
from .replay import ReplayManifest, ReplayPartitionRange, ReplayTopicRange
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
        self._graph_stream_base = profile.policy.graph_stream_base
        self._required_platform_run_id = profile.wiring.required_platform_run_id
        self._lock_run_scope_on_first_event = profile.wiring.lock_run_scope_on_first_event
        self._locked_platform_run_id = self._required_platform_run_id
        self._replay_manifest: ReplayManifest | None = None
        self._file_reader = None
        self._kinesis_reader = None
        self._buffers: dict[tuple[str, int], deque[BusRecord]] = {}
        self._file_next_offsets: dict[tuple[str, int], int] = {}
        self._kinesis_next_offsets: dict[tuple[str, int], str | None] = {}
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

    def run_once(self, *, manifest: ReplayManifest | None = None) -> int:
        if manifest:
            return self._run_manifest(manifest)
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

    def _run_manifest(self, manifest: ReplayManifest) -> int:
        processed = 0
        self._replay_manifest = manifest
        try:
            if self.profile.wiring.event_bus_kind == "file":
                for topic_range in manifest.topics:
                    for partition_range in topic_range.partitions:
                        processed += self._consume_file_topic_range(topic_range, partition_range)
            else:
                for topic_range in manifest.topics:
                    stream_name = self._stream_name(topic_range.topic, override=manifest.stream_id)
                    processed += self._consume_kinesis_topic_range(stream_name, topic_range)
        finally:
            self._replay_manifest = None
        return processed

    def _consume_file_topic(self, topic: str, partition: int) -> int:
        assert self._file_reader is not None
        key = (topic, partition)
        buffer = self._buffer_for(key)
        self._fill_file_buffer(topic, partition, buffer)
        return self._drain_buffer(buffer, batch_size=self.profile.wiring.batch_size)

    def _consume_file_topic_range(self, topic_range: ReplayTopicRange, partition_range: ReplayPartitionRange) -> int:
        assert self._file_reader is not None
        topic = topic_range.topic
        partition = partition_range.partition
        start_offset = _coerce_file_offset(partition_range.from_offset, default=0)
        end_offset = _coerce_file_offset(partition_range.to_offset, default=None)
        if end_offset is not None and start_offset > end_offset:
            return 0
        processed = 0
        cursor = start_offset
        while True:
            records = self._file_reader.read(
                topic,
                partition=partition,
                from_offset=cursor,
                max_records=self.profile.wiring.poll_max_records,
            )
            if not records:
                break
            for record in records:
                if end_offset is not None and record.offset > end_offset:
                    return processed
                envelope = _unwrap_envelope(record.record)
                if not envelope:
                    cursor = record.offset + 1
                    continue
                bus_record = BusRecord(
                    topic=topic,
                    partition=partition,
                    offset=str(record.offset),
                    offset_kind="file_line",
                    payload=envelope,
                    published_at_utc=record.record.get("published_at_utc"),
                )
                self._process_record(bus_record)
                processed += 1
                cursor = record.offset + 1
            if len(records) < self.profile.wiring.poll_max_records:
                break
            if end_offset is not None and cursor > end_offset:
                break
        return processed

    def _consume_kinesis_topic(self, topic: str) -> int:
        assert self._kinesis_reader is not None
        stream = self._stream_name(topic)
        shard_ids = self._kinesis_reader.list_shards(stream)
        processed = 0
        for shard_id in shard_ids:
            partition = _partition_id_from_shard(shard_id)
            key = (topic, partition)
            buffer = self._buffer_for(key)
            self._fill_kinesis_buffer(stream, topic, shard_id, partition, buffer)
            processed += self._drain_buffer(buffer, batch_size=self.profile.wiring.batch_size)
        return processed

    def _consume_kinesis_topic_range(self, stream: str, topic_range: ReplayTopicRange) -> int:
        assert self._kinesis_reader is not None
        shard_ids = self._kinesis_reader.list_shards(stream)
        shard_map = {_partition_id_from_shard(shard_id): shard_id for shard_id in shard_ids}
        processed = 0
        for partition_range in topic_range.partitions:
            shard_id = shard_map.get(partition_range.partition)
            if not shard_id:
                raise RuntimeError(f"KINESIS_SHARD_MISSING partition={partition_range.partition}")
            processed += self._consume_kinesis_partition_range(
                stream=stream,
                topic=topic_range.topic,
                shard_id=shard_id,
                partition_range=partition_range,
            )
        return processed

    def _consume_kinesis_partition_range(
        self,
        *,
        stream: str,
        topic: str,
        shard_id: str,
        partition_range: ReplayPartitionRange,
    ) -> int:
        assert self._kinesis_reader is not None
        processed = 0
        cursor = partition_range.from_offset
        end_offset = partition_range.to_offset
        while True:
            records = self._kinesis_reader.read(
                stream_name=stream,
                shard_id=shard_id,
                from_sequence=cursor,
                limit=self.profile.wiring.poll_max_records,
            )
            if not records:
                break
            for record in records:
                sequence = str(record.get("sequence_number") or "")
                if end_offset is not None and _sequence_after(sequence, end_offset):
                    return processed
                envelope = record.get("payload")
                if not isinstance(envelope, dict):
                    cursor = sequence
                    continue
                bus_record = BusRecord(
                    topic=topic,
                    partition=partition_range.partition,
                    offset=sequence,
                    offset_kind="kinesis_sequence",
                    payload=envelope,
                    published_at_utc=record.get("published_at_utc"),
                )
                self._process_record(bus_record)
                processed += 1
                cursor = sequence
                if end_offset is not None and _sequence_equal_or_after(sequence, end_offset):
                    return processed
            if len(records) < self.profile.wiring.poll_max_records:
                break
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

    def _buffer_for(self, key: tuple[str, int]) -> deque[BusRecord]:
        buffer = self._buffers.get(key)
        if buffer is None:
            buffer = deque()
            self._buffers[key] = buffer
        return buffer

    def _fill_file_buffer(self, topic: str, partition: int, buffer: deque[BusRecord]) -> None:
        assert self._file_reader is not None
        max_inflight = self.profile.wiring.max_inflight
        if len(buffer) >= max_inflight:
            return
        key = (topic, partition)
        from_offset = self._file_next_offsets.get(key)
        if from_offset is None:
            checkpoint = self.store.get_checkpoint(topic=topic, partition=partition)
            from_offset = int(checkpoint.next_offset) if checkpoint else 0
        read_max = min(self.profile.wiring.poll_max_records, max_inflight - len(buffer))
        if read_max <= 0:
            return
        records = self._file_reader.read(
            topic,
            partition=partition,
            from_offset=from_offset,
            max_records=read_max,
        )
        if not records:
            return
        last_offset = from_offset
        for record in records:
            last_offset = record.offset
            envelope = _unwrap_envelope(record.record)
            if not envelope:
                continue
            buffer.append(
                BusRecord(
                    topic=topic,
                    partition=record.partition,
                    offset=str(record.offset),
                    offset_kind="file_line",
                    payload=envelope,
                    published_at_utc=record.record.get("published_at_utc"),
                )
            )
        self._file_next_offsets[key] = int(last_offset) + 1

    def _fill_kinesis_buffer(
        self,
        stream: str,
        topic: str,
        shard_id: str,
        partition: int,
        buffer: deque[BusRecord],
    ) -> None:
        assert self._kinesis_reader is not None
        max_inflight = self.profile.wiring.max_inflight
        if len(buffer) >= max_inflight:
            return
        key = (topic, partition)
        from_sequence = self._kinesis_next_offsets.get(key)
        if from_sequence is None:
            checkpoint = self.store.get_checkpoint(topic=topic, partition=partition)
            from_sequence = checkpoint.next_offset if checkpoint else None
        read_max = min(self.profile.wiring.poll_max_records, max_inflight - len(buffer))
        if read_max <= 0:
            return
        records = self._kinesis_reader.read(
            stream_name=stream,
            shard_id=shard_id,
            from_sequence=from_sequence,
            limit=read_max,
        )
        if not records:
            return
        last_sequence = from_sequence
        for record in records:
            sequence = str(record.get("sequence_number") or "")
            last_sequence = sequence
            envelope = record.get("payload")
            if not isinstance(envelope, dict):
                continue
            buffer.append(
                BusRecord(
                    topic=topic,
                    partition=partition,
                    offset=sequence,
                    offset_kind="kinesis_sequence",
                    payload=envelope,
                    published_at_utc=record.get("published_at_utc"),
                )
            )
        if last_sequence:
            self._kinesis_next_offsets[key] = last_sequence

    def _drain_buffer(self, buffer: deque[BusRecord], *, batch_size: int) -> int:
        processed = 0
        count = min(len(buffer), max(1, batch_size))
        for _ in range(count):
            record = buffer.popleft()
            self._process_record(record)
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
                platform_run_id=envelope.get("platform_run_id"),
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
                platform_run_id=envelope.get("platform_run_id"),
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                reason_code="REQUIRED_PINS_MISSING",
                details={"missing": missing},
                event_ts_utc=envelope.get("ts_utc"),
            )

        platform_run_id = envelope.get("platform_run_id")
        if not platform_run_id:
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                platform_run_id=None,
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                reason_code="PLATFORM_RUN_ID_MISSING",
                details=None,
                event_ts_utc=envelope.get("ts_utc"),
            )

        if self._required_platform_run_id and str(platform_run_id) != str(self._required_platform_run_id):
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                reason_code="RUN_SCOPE_MISMATCH",
                details={"expected": self._required_platform_run_id, "actual": platform_run_id},
                event_ts_utc=envelope.get("ts_utc"),
            )

        if self._lock_run_scope_on_first_event and self._locked_platform_run_id is None:
            self._locked_platform_run_id = str(platform_run_id)
            new_stream_id = f"{self._graph_stream_base}::{self._locked_platform_run_id}"
            self.store.rebind_stream_id(new_stream_id)

        if self._locked_platform_run_id and str(platform_run_id) != str(self._locked_platform_run_id):
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                reason_code="RUN_SCOPE_MISMATCH",
                details={"expected": self._locked_platform_run_id, "actual": platform_run_id},
                event_ts_utc=envelope.get("ts_utc"),
            )

        replay_mismatch = _replay_pins_mismatch(self._replay_manifest, envelope)
        if replay_mismatch:
            return self.store.record_failure(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                reason_code="REPLAY_PINS_MISMATCH",
                details={"mismatches": replay_mismatch},
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
                platform_run_id=platform_run_id,
                scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
                count_as="irrelevant",
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
                platform_run_id=platform_run_id,
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
                platform_run_id=platform_run_id,
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
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                reason_code="IDENTITY_HINTS_MISSING",
                details=None,
                event_ts_utc=envelope.get("ts_utc"),
            )

        pins = _pins_for_envelope(envelope, scenario_run_id)
        dedupe = dedupe_key(str(platform_run_id), scenario_run_id, class_name, event_id)
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
            platform_run_id=str(platform_run_id),
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

    def _stream_name(self, topic: str, *, override: str | None = None) -> str:
        if override:
            return override
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


def _coerce_file_offset(value: str | None, *, default: int | None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sequence_compare(left: str, right: str) -> int:
    try:
        left_val = int(left)
        right_val = int(right)
        if left_val < right_val:
            return -1
        if left_val > right_val:
            return 1
        return 0
    except (TypeError, ValueError):
        if left < right:
            return -1
        if left > right:
            return 1
        return 0


def _sequence_after(left: str, right: str) -> bool:
    return _sequence_compare(left, right) > 0


def _sequence_equal_or_after(left: str, right: str) -> bool:
    return _sequence_compare(left, right) >= 0


def _replay_pins_mismatch(
    manifest: ReplayManifest | None, envelope: dict[str, Any]
) -> dict[str, dict[str, Any]] | None:
    if not manifest or not manifest.pins:
        return None
    mismatches: dict[str, dict[str, Any]] = {}
    for key, expected in manifest.pins.items():
        if expected is None:
            continue
        actual = envelope.get(key)
        if actual is None or str(actual) != str(expected):
            mismatches[key] = {"expected": expected, "actual": actual}
    if not mismatches:
        return None
    return mismatches


def _manifest_stream_override(profile: IegProfile, manifest: ReplayManifest) -> str | None:
    if manifest.stream_id:
        return manifest.stream_id
    stream = profile.wiring.event_bus_stream
    if not stream or str(stream).lower() in {"", "auto", "topic"}:
        return None
    return str(stream)


def main() -> None:
    parser = argparse.ArgumentParser(description="IEG projector (Phase 2)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Process a single batch and exit")
    parser.add_argument("--replay-manifest", help="Path to replay manifest YAML/JSON")
    parser.add_argument("--reset", action="store_true", help="Reset projection store before processing")
    parser.add_argument("--prune", action="store_true", help="Apply retention policy before processing")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    projector = IdentityGraphProjector.build(args.profile)
    if args.reset:
        logger.info("IEG reset requested")
        projector.store.reset()
    if args.prune:
        if projector.profile.retention.is_enabled():
            summary = projector.store.prune(projector.profile.retention)
            logger.info("IEG retention prune summary=%s", summary)
        else:
            logger.info("IEG retention prune skipped: no retention policy enabled")

    manifest = None
    if args.replay_manifest:
        manifest = ReplayManifest.load(Path(args.replay_manifest))
    if manifest:
        processed = projector.run_once(manifest=manifest)
        graph_version = projector.store.current_graph_version()
        stream_override = _manifest_stream_override(projector.profile, manifest)
        basis = manifest.basis(
            event_bus_kind=projector.profile.wiring.event_bus_kind,
            stream_override=stream_override,
        )
        projector.store.record_replay_basis(
            replay_id=manifest.replay_id(),
            manifest_json=manifest.canonical_json(),
            basis_json=json.dumps(basis, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
            graph_version=graph_version,
        )
        logger.info("IEG replay processed=%s graph_version=%s", processed, graph_version)
        return
    if args.once:
        projector.run_once()
    else:
        projector.run_forever()


if __name__ == "__main__":
    main()
