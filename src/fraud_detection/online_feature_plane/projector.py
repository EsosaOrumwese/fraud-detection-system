"""OFP projector: consume admitted EB events and build feature state."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from fraud_detection.event_bus import EventBusReader
from fraud_detection.ingestion_gate.schemas import SchemaRegistry

from .config import OfpProfile
from .store import build_store

logger = logging.getLogger("fraud_detection.ofp")

_REQUIRED_PINS = [
    "platform_run_id",
    "scenario_run_id",
    "manifest_fingerprint",
    "parameter_hash",
    "scenario_id",
    "seed",
]
_IGNORED_EVENT_TYPES = {
    "decision_response",
    "action_intent",
}


@dataclass(frozen=True)
class BusRecord:
    topic: str
    partition: int
    offset: str
    offset_kind: str
    payload: dict[str, Any]
    published_at_utc: str | None = None


class OnlineFeatureProjector:
    def __init__(self, profile: OfpProfile) -> None:
        self.profile = profile
        self.store = build_store(
            profile.wiring.projection_db_dsn,
            stream_id=profile.policy.stream_id,
            basis_stream=profile.wiring.event_bus_basis_stream,
            run_config_digest=profile.policy.run_config_digest,
            feature_def_policy_id=profile.policy.feature_def_policy_rev.policy_id,
            feature_def_revision=profile.policy.feature_def_policy_rev.revision,
            feature_def_content_digest=profile.policy.feature_def_policy_rev.content_digest,
        )
        logger.info(
            "OFP feature policy active: policy_id=%s revision=%s digest=%s",
            profile.policy.feature_def_policy_rev.policy_id,
            profile.policy.feature_def_policy_rev.revision,
            profile.policy.feature_def_policy_rev.content_digest,
        )
        self.envelope_registry = SchemaRegistry(Path(profile.wiring.engine_contracts_root))
        self._file_reader = None
        self._kinesis_reader = None
        if profile.wiring.event_bus_kind == "file":
            root = profile.wiring.event_bus_root or "runs/fraud-platform/eb"
            self._file_reader = EventBusReader(Path(root))
        elif profile.wiring.event_bus_kind == "kinesis":
            from fraud_detection.event_bus.kinesis import KinesisEventBusReader

            self._kinesis_reader = KinesisEventBusReader(
                stream_name=profile.wiring.event_bus_stream,
                region=profile.wiring.event_bus_region,
                endpoint_url=profile.wiring.event_bus_endpoint_url,
            )
        else:
            raise RuntimeError("OFP_EVENT_BUS_KIND_UNSUPPORTED")

    @classmethod
    def build(cls, profile_path: str) -> "OnlineFeatureProjector":
        return cls(OfpProfile.load(Path(profile_path)))

    def run_once(self) -> int:
        topics = self.profile.wiring.event_bus_topics
        if self.profile.wiring.event_bus_kind == "file":
            processed = 0
            for topic in topics:
                partitions = self._file_partitions(topic)
                for partition in partitions:
                    processed += self._consume_file_topic(topic, partition)
            return processed
        processed = 0
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
        from_offset = int(checkpoint.next_offset) if checkpoint and checkpoint.offset_kind == "file_line" else 0
        records = self._file_reader.read(
            topic,
            partition=partition,
            from_offset=from_offset,
            max_records=self.profile.wiring.poll_max_records,
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

    def _consume_kinesis_topic(self, topic: str) -> int:
        assert self._kinesis_reader is not None
        stream_name = self._stream_name(topic)
        shard_ids = self._kinesis_reader.list_shards(stream_name)
        processed = 0
        for shard_id in shard_ids:
            partition = _partition_id_from_shard(shard_id)
            checkpoint = self.store.get_checkpoint(topic=topic, partition=partition)
            from_sequence = checkpoint.next_offset if checkpoint else None
            records = self._kinesis_reader.read(
                stream_name=stream_name,
                shard_id=shard_id,
                from_sequence=from_sequence,
                limit=self.profile.wiring.poll_max_records,
                start_position=self.profile.wiring.event_bus_start_position,
            )
            for record in records:
                bus_record = BusRecord(
                    topic=topic,
                    partition=partition,
                    offset=str(record.get("sequence_number") or ""),
                    offset_kind="kinesis_sequence",
                    payload=record.get("payload") if isinstance(record.get("payload"), dict) else {},
                    published_at_utc=record.get("published_at_utc"),
                )
                self._process_record(bus_record)
                processed += 1
        return processed

    def _process_record(self, record: BusRecord) -> None:
        envelope = _unwrap_envelope(record.payload)
        if envelope is None:
            self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=None,
                scenario_run_id=None,
                count_as="invalid_envelope",
            )
            return
        event_id = str(envelope.get("event_id") or "")
        event_ts_utc = str(envelope.get("ts_utc") or "") or None
        scenario_run_id = str(envelope.get("scenario_run_id") or "")
        try:
            self.envelope_registry.validate("canonical_event_envelope.schema.yaml", envelope)
        except Exception:
            self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=event_ts_utc,
                scenario_run_id=scenario_run_id or None,
                count_as="invalid_envelope",
            )
            return

        platform_run_id = str(envelope.get("platform_run_id") or "")
        if not platform_run_id:
            self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=event_ts_utc,
                scenario_run_id=scenario_run_id or None,
                count_as="invalid_pins",
            )
            return
        required_platform_run_id = self.profile.wiring.required_platform_run_id
        if required_platform_run_id and platform_run_id != required_platform_run_id:
            self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=event_ts_utc,
                scenario_run_id=scenario_run_id or None,
                count_as="run_scope_mismatch",
            )
            return
        missing = [pin for pin in _REQUIRED_PINS if envelope.get(pin) in (None, "")]
        if missing:
            self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=event_ts_utc,
                scenario_run_id=scenario_run_id or None,
                count_as="invalid_pins",
            )
            return

        event_type = str(envelope.get("event_type") or "").strip()
        if event_type in _IGNORED_EVENT_TYPES:
            self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=event_ts_utc,
                scenario_run_id=scenario_run_id or None,
                count_as="ignored_event_type",
            )
            return

        key_type, key_id = _resolve_key(
            envelope=envelope,
            key_precedence=self.profile.policy.key_precedence,
            fallback_event_id=event_id,
        )
        event_class = _resolve_event_class(envelope=envelope, topic=record.topic)
        if not event_class:
            self.store.advance_checkpoint(
                topic=record.topic,
                partition=record.partition,
                offset=record.offset,
                offset_kind=record.offset_kind,
                event_ts_utc=event_ts_utc,
                scenario_run_id=scenario_run_id or None,
                count_as="invalid_event_class",
            )
            return
        amount = _resolve_amount(envelope=envelope, amount_fields=self.profile.policy.amount_fields)
        self.store.apply_event(
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            offset_kind=record.offset_kind,
            event_class=event_class,
            event_id=event_id,
            payload_hash=_payload_hash(envelope),
            event_ts_utc=event_ts_utc,
            pins={
                "platform_run_id": platform_run_id,
                "scenario_run_id": str(envelope.get("scenario_run_id") or ""),
                "scenario_id": str(envelope.get("scenario_id") or ""),
                "run_id": str(envelope.get("run_id") or ""),
                "manifest_fingerprint": str(envelope.get("manifest_fingerprint") or ""),
                "parameter_hash": str(envelope.get("parameter_hash") or ""),
                "seed": str(envelope.get("seed") or ""),
            },
            key_type=key_type,
            key_id=key_id,
            group_name=self.profile.policy.feature_group_name,
            group_version=self.profile.policy.feature_group_version,
            amount=amount,
        )

    def _stream_name(self, topic: str) -> str:
        stream = self.profile.wiring.event_bus_stream
        if stream and str(stream).lower() not in {"", "auto", "topic"}:
            return str(stream)
        return topic

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
        if not partitions:
            return [0]
        return sorted(set(partitions))


def _resolve_key(
    *,
    envelope: dict[str, Any],
    key_precedence: list[str],
    fallback_event_id: str,
) -> tuple[str, str]:
    payload = envelope.get("payload")
    if isinstance(payload, dict):
        for key_name in key_precedence:
            value = payload.get(key_name)
            if value not in (None, ""):
                return key_name, str(value)
    if fallback_event_id:
        return "event_id", fallback_event_id
    return "unknown", "unknown"


def _resolve_amount(*, envelope: dict[str, Any], amount_fields: list[str]) -> float:
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        return 0.0
    for field in amount_fields:
        value = payload.get(field)
        if value in (None, ""):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return 0.0


def _resolve_event_class(*, envelope: dict[str, Any], topic: str) -> str:
    explicit = str(envelope.get("event_class") or "").strip()
    if explicit:
        return explicit
    topic_map = {
        "fp.bus.traffic.fraud.v1": "traffic_fraud",
        "fp.bus.traffic.baseline.v1": "traffic_baseline",
        "fp.bus.context.arrival_events.v1": "context_arrival",
        "fp.bus.context.arrival_entities.v1": "context_arrival_entities",
        "fp.bus.context.flow_anchor.fraud.v1": "context_flow_fraud",
        "fp.bus.context.flow_anchor.baseline.v1": "context_flow_baseline",
    }
    resolved = topic_map.get(topic)
    if resolved:
        return resolved
    event_type = str(envelope.get("event_type") or "").strip().lower()
    if "arrival_entities" in event_type:
        return "context_arrival_entities"
    if "arrival_events" in event_type or "arrival_count" in event_type:
        return "context_arrival"
    if "flow_anchor" in event_type and "fraud" in event_type:
        return "context_flow_fraud"
    if "flow_anchor" in event_type and "baseline" in event_type:
        return "context_flow_baseline"
    if "event_stream" in event_type and "fraud" in event_type:
        return "traffic_fraud"
    if "event_stream" in event_type and "baseline" in event_type:
        return "traffic_baseline"
    return ""


def _payload_hash(envelope: dict[str, Any]) -> str:
    payload = {
        "event_type": envelope.get("event_type"),
        "schema_version": envelope.get("schema_version"),
        "payload": envelope.get("payload"),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _unwrap_envelope(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("envelope"), dict):
        return value.get("envelope")
    return value


def _partition_id_from_shard(shard_id: str) -> int:
    try:
        return int(shard_id.split("-")[-1])
    except ValueError:
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="OFP projector (Phase 2)")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Process a single batch and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    projector = OnlineFeatureProjector.build(args.profile)
    if args.once:
        processed = projector.run_once()
        logger.info("OFP projector processed=%s", processed)
        return
    projector.run_forever()


if __name__ == "__main__":
    main()
