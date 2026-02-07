"""Context Store + FlowBinding intake worker (Phase 3)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Mapping

import yaml

from fraud_detection.event_bus import EventBusReader
from fraud_detection.event_bus.kinesis import KinesisEventBusReader
from fraud_detection.ingestion_gate.config import ClassMap
from fraud_detection.ingestion_gate.schemas import SchemaRegistry
from fraud_detection.platform_runtime import resolve_run_scoped_path

from .contracts import FlowBindingRecord, JoinFrameKey
from .replay import CsfbReplayManifest, CsfbReplayPartitionRange
from .store import ContextStoreFlowBindingConflictError, build_store
from .taxonomy import ContextStoreFlowBindingTaxonomyError, ensure_authoritative_flow_binding_event_type

logger = logging.getLogger("fraud_detection.csfb")


@dataclass(frozen=True)
class BusRecord:
    topic: str
    partition: int
    offset: str
    offset_kind: str
    payload: dict[str, Any]
    published_at_utc: str | None = None


@dataclass(frozen=True)
class CsfbInletPolicy:
    stream_id: str
    class_map_ref: str
    context_event_classes: tuple[str, ...]
    context_topics: tuple[str, ...]
    projection_db_dsn: str
    event_bus_kind: str
    event_bus_root: str | None
    event_bus_stream: str | None
    event_bus_start_position: str
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    engine_contracts_root: str
    required_platform_run_id: str | None
    poll_max_records: int
    poll_sleep_seconds: float

    @classmethod
    def load(cls, path: Path) -> "CsfbInletPolicy":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CSFB intake policy must be a mapping")
        root = payload.get("context_store_flow_binding")
        if isinstance(root, dict):
            payload = root
        policy = payload.get("policy", {})
        wiring = payload.get("wiring", {})

        projection_db_dsn = resolve_run_scoped_path(
            str(wiring.get("projection_db_dsn") or "runs/fraud-platform/context_store_flow_binding/csfb.sqlite"),
            suffix="context_store_flow_binding/csfb.sqlite",
            create_if_missing=True,
        )
        if not projection_db_dsn:
            raise ValueError("PLATFORM_RUN_ID required to resolve projection_db_dsn")
        event_bus_root = resolve_run_scoped_path(
            str(wiring.get("event_bus_root") or "runs/fraud-platform/eb"),
            suffix="eb",
            create_if_missing=True,
        )

        return cls(
            stream_id=str(policy.get("stream_id") or "csfb.v0"),
            class_map_ref=str(policy.get("class_map_ref") or "config/platform/ig/class_map_v0.yaml"),
            context_event_classes=tuple(
                policy.get("context_event_classes")
                or [
                    "context_arrival",
                    "context_arrival_entities",
                    "context_flow_baseline",
                    "context_flow_fraud",
                ]
            ),
            context_topics=tuple(
                policy.get("context_topics")
                or [
                    "fp.bus.context.arrival_events.v1",
                    "fp.bus.context.arrival_entities.v1",
                    "fp.bus.context.flow_anchor.baseline.v1",
                    "fp.bus.context.flow_anchor.fraud.v1",
                ]
            ),
            projection_db_dsn=str(projection_db_dsn),
            event_bus_kind=str(wiring.get("event_bus_kind") or "file"),
            event_bus_root=event_bus_root,
            event_bus_stream=str(wiring.get("event_bus_stream") or "auto"),
            event_bus_start_position=str(wiring.get("event_bus_start_position") or "trim_horizon"),
            event_bus_region=_none_if_blank(wiring.get("event_bus_region")),
            event_bus_endpoint_url=_none_if_blank(wiring.get("event_bus_endpoint_url")),
            engine_contracts_root=str(
                wiring.get("engine_contracts_root")
                or "docs/model_spec/data-engine/interface_pack/contracts"
            ),
            required_platform_run_id=_none_if_blank(wiring.get("required_platform_run_id")),
            poll_max_records=max(1, int(wiring.get("poll_max_records") or 200)),
            poll_sleep_seconds=float(wiring.get("poll_sleep_seconds") or 0.5),
        )


class ContextStoreFlowBindingInlet:
    def __init__(self, policy: CsfbInletPolicy) -> None:
        self.policy = policy
        self.class_map = ClassMap.load(Path(policy.class_map_ref))
        self.schema_registry = SchemaRegistry(Path(policy.engine_contracts_root))
        self.store = build_store(policy.projection_db_dsn, stream_id=policy.stream_id)
        self._file_reader: EventBusReader | None = None
        self._kinesis_reader: KinesisEventBusReader | None = None
        if policy.event_bus_kind == "file":
            self._file_reader = EventBusReader(Path(policy.event_bus_root or "runs/fraud-platform/eb"))
        elif policy.event_bus_kind == "kinesis":
            self._kinesis_reader = KinesisEventBusReader(
                stream_name=policy.event_bus_stream,
                region=policy.event_bus_region,
                endpoint_url=policy.event_bus_endpoint_url,
            )
        else:
            raise RuntimeError("CSFB_EVENT_BUS_KIND_UNSUPPORTED")

    @classmethod
    def build(cls, policy_path: str) -> "ContextStoreFlowBindingInlet":
        return cls(CsfbInletPolicy.load(Path(policy_path)))

    def run_once(self, manifest: CsfbReplayManifest | None = None) -> int:
        if manifest is not None:
            return self.run_replay_once(manifest)
        processed = 0
        for topic in self.policy.context_topics:
            if self.policy.event_bus_kind == "file":
                for partition in self._file_partitions(topic):
                    processed += self._consume_file_partition(topic, partition)
            else:
                processed += self._consume_kinesis_topic(topic)
        return processed

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.policy.poll_sleep_seconds)

    def run_replay_once(self, manifest: CsfbReplayManifest) -> int:
        processed = 0
        replay_pins = manifest.pins
        for topic_range in manifest.topics:
            if topic_range.topic not in self.policy.context_topics:
                raise RuntimeError(f"CSFB_REPLAY_TOPIC_NOT_ALLOWED:{topic_range.topic}")
            for partition_range in topic_range.partitions:
                if self.policy.event_bus_kind == "file":
                    processed += self._consume_file_partition_range(
                        topic=topic_range.topic,
                        partition_range=partition_range,
                        replay_pins=replay_pins,
                    )
                else:
                    processed += self._consume_kinesis_partition_range(
                        topic=topic_range.topic,
                        partition_range=partition_range,
                        replay_pins=replay_pins,
                    )
        return processed

    def _consume_file_partition(self, topic: str, partition: int) -> int:
        assert self._file_reader is not None
        checkpoint = self.store.get_checkpoint(topic=topic, partition_id=partition)
        from_offset = int(checkpoint.next_offset) if checkpoint and checkpoint.offset_kind == "file_line" else 0
        records = self._file_reader.read(
            topic,
            partition=partition,
            from_offset=from_offset,
            max_records=self.policy.poll_max_records,
        )
        processed = 0
        for record in records:
            bus_record = BusRecord(
                topic=topic,
                partition=partition,
                offset=str(record.offset),
                offset_kind="file_line",
                payload=record.record,
                published_at_utc=record.record.get("published_at_utc") if isinstance(record.record, dict) else None,
            )
            self._process_record(bus_record)
            processed += 1
        return processed

    def _consume_file_partition_range(
        self,
        *,
        topic: str,
        partition_range: CsfbReplayPartitionRange,
        replay_pins: Mapping[str, Any] | None,
    ) -> int:
        assert self._file_reader is not None
        from_offset = _coerce_file_offset(partition_range.from_offset, default=0)
        to_offset = _coerce_file_offset(partition_range.to_offset, default=None)
        if from_offset is None:
            from_offset = 0
        if to_offset is not None and to_offset < from_offset:
            return 0

        processed = 0
        cursor = from_offset
        while True:
            records = self._file_reader.read(
                topic,
                partition=partition_range.partition,
                from_offset=cursor,
                max_records=self.policy.poll_max_records,
            )
            if not records:
                break
            for record in records:
                if to_offset is not None and record.offset > to_offset:
                    return processed
                bus_record = BusRecord(
                    topic=topic,
                    partition=partition_range.partition,
                    offset=str(record.offset),
                    offset_kind=partition_range.offset_kind or "file_line",
                    payload=record.record,
                    published_at_utc=record.record.get("published_at_utc") if isinstance(record.record, dict) else None,
                )
                self._process_record(bus_record, replay_pins=replay_pins)
                processed += 1
                cursor = record.offset + 1
            if to_offset is not None and cursor > to_offset:
                break
            if len(records) < self.policy.poll_max_records:
                break
        return processed

    def _consume_kinesis_topic(self, topic: str) -> int:
        assert self._kinesis_reader is not None
        stream_name = self._stream_name(topic)
        processed = 0
        for shard_id in self._kinesis_reader.list_shards(stream_name):
            partition = _partition_id_from_shard(shard_id)
            checkpoint = self.store.get_checkpoint(topic=topic, partition_id=partition)
            from_sequence = checkpoint.next_offset if checkpoint else None
            records = self._kinesis_reader.read(
                stream_name=stream_name,
                shard_id=shard_id,
                from_sequence=from_sequence,
                limit=self.policy.poll_max_records,
                start_position=self.policy.event_bus_start_position,
            )
            for record in records:
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue
                self._process_record(
                    BusRecord(
                        topic=topic,
                        partition=partition,
                        offset=str(record.get("sequence_number") or ""),
                        offset_kind="kinesis_sequence",
                        payload=payload,
                        published_at_utc=record.get("published_at_utc"),
                    )
                )
                processed += 1
        return processed

    def _consume_kinesis_partition_range(
        self,
        *,
        topic: str,
        partition_range: CsfbReplayPartitionRange,
        replay_pins: Mapping[str, Any] | None,
    ) -> int:
        assert self._kinesis_reader is not None
        stream_name = self._stream_name(topic)
        shard_id = f"shardId-{int(partition_range.partition):012d}"
        from_sequence = partition_range.from_offset
        to_sequence = partition_range.to_offset
        processed = 0
        current_from = from_sequence
        while True:
            records = self._kinesis_reader.read(
                stream_name=stream_name,
                shard_id=shard_id,
                from_sequence=current_from,
                limit=self.policy.poll_max_records,
                start_position=self.policy.event_bus_start_position,
            )
            if not records:
                break
            for record in records:
                sequence = str(record.get("sequence_number") or "")
                if to_sequence and sequence and _sequence_compare(sequence, to_sequence) > 0:
                    return processed
                payload = record.get("payload")
                if not isinstance(payload, dict):
                    continue
                self._process_record(
                    BusRecord(
                        topic=topic,
                        partition=partition_range.partition,
                        offset=sequence,
                        offset_kind=partition_range.offset_kind or "kinesis_sequence",
                        payload=payload,
                        published_at_utc=record.get("published_at_utc"),
                    ),
                    replay_pins=replay_pins,
                )
                processed += 1
                if sequence:
                    current_from = sequence
            if len(records) < self.policy.poll_max_records:
                break
        return processed

    def _process_record(self, record: BusRecord, *, replay_pins: Mapping[str, Any] | None = None) -> None:
        envelope = _unwrap_envelope(record.payload)
        if envelope is None:
            self._record_failure_and_advance(
                record=record,
                reason_code="ENVELOPE_MISSING",
                details={},
                event_id=None,
                event_type=None,
                platform_run_id=None,
                scenario_run_id=None,
                event_ts_utc=None,
            )
            return

        event_id = str(envelope.get("event_id") or "")
        event_type = str(envelope.get("event_type") or "")
        event_ts_utc = _none_if_blank(envelope.get("ts_utc"))
        platform_run_id = _none_if_blank(envelope.get("platform_run_id"))
        scenario_run_id = _none_if_blank(envelope.get("scenario_run_id") or envelope.get("run_id"))

        try:
            self.schema_registry.validate("canonical_event_envelope.schema.yaml", envelope)
        except Exception:
            self._record_failure_and_advance(
                record=record,
                reason_code="ENVELOPE_INVALID",
                details={"event_type": event_type},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        replay_mismatch = _replay_pins_mismatch(replay_pins, envelope)
        if replay_mismatch:
            self._record_failure_and_advance(
                record=record,
                reason_code="REPLAY_PINS_MISMATCH",
                details={"mismatches": replay_mismatch},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        if record.topic not in self.policy.context_topics:
            self._record_failure_and_advance(
                record=record,
                reason_code="TOPIC_NOT_ALLOWED",
                details={"topic": record.topic},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        event_class = self.class_map.class_for(event_type)
        if event_class not in self.policy.context_event_classes:
            self._record_failure_and_advance(
                record=record,
                reason_code="EVENT_CLASS_UNSUPPORTED",
                details={"event_class": event_class, "event_type": event_type},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        missing_pins = [
            pin
            for pin in self.class_map.required_pins_for(event_type)
            if envelope.get(pin) in (None, "")
        ]
        if missing_pins:
            self._record_failure_and_advance(
                record=record,
                reason_code="REQUIRED_PINS_MISSING",
                details={"missing": missing_pins},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        if not platform_run_id:
            self._record_failure_and_advance(
                record=record,
                reason_code="PLATFORM_RUN_ID_MISSING",
                details={},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=None,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        if self.policy.required_platform_run_id and platform_run_id != self.policy.required_platform_run_id:
            self._record_failure_and_advance(
                record=record,
                reason_code="RUN_SCOPE_MISMATCH",
                details={
                    "expected": self.policy.required_platform_run_id,
                    "actual": platform_run_id,
                },
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        payload = envelope.get("payload")
        if not isinstance(payload, Mapping):
            self._record_failure_and_advance(
                record=record,
                reason_code="PAYLOAD_INVALID",
                details={"type": str(type(payload))},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        join_key = _extract_join_key(
            payload=payload,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
        )
        if join_key is None:
            self._record_failure_and_advance(
                record=record,
                reason_code="JOIN_KEY_MISSING",
                details={"event_type": event_type},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )
            return

        existing_state = self.store.read_join_frame_state(join_frame_key=join_key)
        frame_state = _merge_join_frame_state(
            existing_state=existing_state,
            join_key=join_key,
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            event_ts_utc=event_ts_utc,
        )

        flow_binding_record = None
        if event_type in {"s2_flow_anchor_baseline_6B", "s3_flow_anchor_with_fraud_6B"}:
            flow_binding_record = _build_flow_binding(
                event_type=event_type,
                event_id=event_id,
                event_ts_utc=event_ts_utc,
                join_key=join_key,
                payload=payload,
                record=record,
                envelope=envelope,
            )
            if flow_binding_record is None:
                self._record_failure_and_advance(
                    record=record,
                    reason_code="FLOW_ID_MISSING",
                    details={"event_type": event_type},
                    event_id=event_id,
                    event_type=event_type,
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    event_ts_utc=event_ts_utc,
                )
                return

        payload_hash = _payload_hash(envelope)
        next_offset = _next_offset(record.offset, record.offset_kind)
        checkpoint_before = self.store.get_checkpoint(topic=record.topic, partition_id=record.partition)
        late = bool(
            checkpoint_before
            and checkpoint_before.watermark_ts_utc
            and event_ts_utc
            and event_ts_utc < checkpoint_before.watermark_ts_utc
        )

        try:
            outcome = self.store.apply_context_event_and_checkpoint(
                platform_run_id=platform_run_id,
                event_class=event_class,
                event_id=event_id,
                payload_hash=payload_hash,
                join_frame_key=join_key,
                frame_state=frame_state,
                source_event=_source_event(record=record, event_type=event_type, event_id=event_id, event_ts_utc=event_ts_utc),
                flow_binding_record=flow_binding_record,
                topic=record.topic,
                partition_id=record.partition,
                event_offset=record.offset,
                next_offset=next_offset,
                offset_kind=record.offset_kind,
                watermark_ts_utc=event_ts_utc,
            )
            if late and outcome.dedupe_status != "duplicate":
                self.store.record_apply_failure(
                    reason_code="LATE_CONTEXT_EVENT",
                    details={
                        "event_type": event_type,
                        "event_ts_utc": event_ts_utc,
                        "watermark_ts_utc": checkpoint_before.watermark_ts_utc if checkpoint_before else None,
                        "applied": True,
                    },
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    topic=record.topic,
                    partition_id=record.partition,
                    offset=record.offset,
                    offset_kind=record.offset_kind,
                    event_id=event_id,
                    event_type=event_type,
                )
        except ContextStoreFlowBindingConflictError as exc:
            self._record_failure_and_advance(
                record=record,
                reason_code=str(exc),
                details={"event_class": event_class, "event_type": event_type},
                event_id=event_id,
                event_type=event_type,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                event_ts_utc=event_ts_utc,
            )

    def _record_failure_and_advance(
        self,
        *,
        record: BusRecord,
        reason_code: str,
        details: Mapping[str, Any],
        event_id: str | None,
        event_type: str | None,
        platform_run_id: str | None,
        scenario_run_id: str | None,
        event_ts_utc: str | None,
    ) -> None:
        self.store.record_apply_failure(
            reason_code=reason_code,
            details=dict(details),
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            topic=record.topic,
            partition_id=record.partition,
            offset=record.offset,
            offset_kind=record.offset_kind,
            event_id=event_id,
            event_type=event_type,
        )
        self.store.advance_checkpoint(
            topic=record.topic,
            partition_id=record.partition,
            next_offset=_next_offset(record.offset, record.offset_kind),
            offset_kind=record.offset_kind,
            watermark_ts_utc=event_ts_utc,
        )

    def _file_partitions(self, topic: str) -> list[int]:
        assert self._file_reader is not None
        root = Path(self._file_reader.root) / topic
        if not root.exists():
            return [0]
        partitions: list[int] = []
        for path in root.glob("partition=*.jsonl"):
            token = path.stem.replace("partition=", "")
            try:
                partitions.append(int(token))
            except ValueError:
                continue
        return sorted(set(partitions)) or [0]

    def _stream_name(self, topic: str) -> str:
        stream = self.policy.event_bus_stream
        if stream and str(stream).lower() not in {"", "auto", "topic"}:
            return str(stream)
        return topic


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _unwrap_envelope(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    payload = value.get("payload")
    if isinstance(payload, dict) and "event_type" in payload and "event_id" in payload:
        return payload
    if "event_type" in value and "event_id" in value:
        return value
    return None


def _extract_join_key(*, payload: Mapping[str, Any], platform_run_id: str, scenario_run_id: str | None) -> JoinFrameKey | None:
    merchant_id = payload.get("merchant_id")
    arrival_seq = payload.get("arrival_seq")
    if merchant_id in (None, "") or arrival_seq in (None, "") or not scenario_run_id:
        return None
    return JoinFrameKey.from_mapping(
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "merchant_id": str(merchant_id),
            "arrival_seq": int(arrival_seq),
        }
    )


def _merge_join_frame_state(
    *,
    existing_state: dict[str, Any] | None,
    join_key: JoinFrameKey,
    event_type: str,
    event_id: str,
    payload: Mapping[str, Any],
    topic: str,
    partition: int,
    offset: str,
    event_ts_utc: str | None,
) -> dict[str, Any]:
    state = dict(existing_state or {})
    state["join_frame_key"] = join_key.as_dict()
    if event_type == "arrival_events_5B":
        state["arrival_event"] = dict(payload)
    elif event_type == "s1_arrival_entities_6B":
        state["arrival_entities"] = dict(payload)
    elif event_type in {"s2_flow_anchor_baseline_6B", "s3_flow_anchor_with_fraud_6B"}:
        state["flow_anchor"] = dict(payload)
        flow_id = payload.get("flow_id")
        if flow_id not in (None, ""):
            state["flow_id"] = str(flow_id)

    state["context_complete"] = bool(state.get("arrival_event") and state.get("flow_anchor"))
    state["last_event_type"] = event_type
    state["last_event_id"] = event_id
    state["event_ts_utc"] = event_ts_utc
    state["source"] = {
        "topic": topic,
        "partition": partition,
        "offset": offset,
    }
    return state


def _build_flow_binding(
    *,
    event_type: str,
    event_id: str,
    event_ts_utc: str | None,
    join_key: JoinFrameKey,
    payload: Mapping[str, Any],
    record: BusRecord,
    envelope: Mapping[str, Any],
) -> FlowBindingRecord | None:
    flow_id = payload.get("flow_id")
    if flow_id in (None, ""):
        return None
    try:
        authoritative = ensure_authoritative_flow_binding_event_type(event_type)
    except ContextStoreFlowBindingTaxonomyError:
        return None
    binding_hash = hashlib.sha256(
        json.dumps(
            {
                "flow_id": str(flow_id),
                "join_frame_key": join_key.as_dict(),
                "source_event_id": event_id,
            },
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return FlowBindingRecord.from_mapping(
        {
            "flow_id": str(flow_id),
            "join_frame_key": join_key.as_dict(),
            "source_event": _source_event(record=record, event_type=event_type, event_id=event_id, event_ts_utc=event_ts_utc),
            "authoritative_source_event_type": authoritative,
            "payload_hash": binding_hash,
            "pins": {
                "platform_run_id": envelope.get("platform_run_id"),
                "scenario_run_id": envelope.get("scenario_run_id") or envelope.get("run_id"),
                "manifest_fingerprint": envelope.get("manifest_fingerprint"),
                "parameter_hash": envelope.get("parameter_hash"),
                "scenario_id": envelope.get("scenario_id"),
                "seed": envelope.get("seed"),
                "run_id": envelope.get("run_id"),
            },
            "bound_at_utc": event_ts_utc or "",
        }
    )


def _source_event(*, record: BusRecord, event_type: str, event_id: str, event_ts_utc: str | None) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ts_utc": event_ts_utc or "",
        "eb_ref": {
            "topic": record.topic,
            "partition": record.partition,
            "offset": record.offset,
            "offset_kind": record.offset_kind,
        },
    }


def _payload_hash(envelope: Mapping[str, Any]) -> str:
    payload = {
        "event_type": envelope.get("event_type"),
        "schema_version": envelope.get("schema_version"),
        "payload": envelope.get("payload"),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _next_offset(offset: str, offset_kind: str) -> str:
    if offset_kind == "file_line":
        try:
            return str(int(offset) + 1)
        except ValueError:
            return offset
    return offset


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


def _replay_pins_mismatch(replay_pins: Mapping[str, Any] | None, envelope: Mapping[str, Any]) -> dict[str, Any] | None:
    if not replay_pins:
        return None
    mismatches: dict[str, Any] = {}
    for key, expected in replay_pins.items():
        if expected is None:
            continue
        actual = envelope.get(key)
        if actual is None or str(actual) != str(expected):
            mismatches[key] = {"expected": expected, "actual": actual}
    if not mismatches:
        return None
    return mismatches


def main() -> None:
    parser = argparse.ArgumentParser(description="CSFB intake worker (Phase 3)")
    parser.add_argument("--policy", required=True, help="Path to CSFB intake policy YAML")
    parser.add_argument("--once", action="store_true", help="Process one poll cycle and exit")
    parser.add_argument("--replay-manifest", help="Path to CSFB replay basis manifest (explicit offsets required)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    inlet = ContextStoreFlowBindingInlet.build(args.policy)
    if args.replay_manifest:
        manifest = CsfbReplayManifest.load(Path(args.replay_manifest))
        processed = inlet.run_replay_once(manifest)
        logger.info("CSFB replay processed=%s replay_id=%s", processed, manifest.replay_id())
        return
    if args.once:
        processed = inlet.run_once()
        logger.info("CSFB intake processed=%s", processed)
        return
    inlet.run_forever()


if __name__ == "__main__":
    main()
