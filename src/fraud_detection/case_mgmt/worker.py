"""Case Management runtime worker CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Mapping

import yaml

from fraud_detection.event_bus import EventBusReader
from fraud_detection.event_bus.kafka import build_kafka_reader
from fraud_detection.event_bus.kinesis import KinesisEventBusReader
from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id, resolve_run_scoped_path

from .contracts import CaseTrigger
from .intake import INTAKE_NEW_TRIGGER, CaseTriggerIntakeLedger
from .label_handshake import CaseLabelHandshakeCoordinator, load_label_emission_policy
from .observability import CaseMgmtRunReporter
from fraud_detection.label_store import LabelStoreWriterBoundary


logger = logging.getLogger("fraud_detection.case_mgmt.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class CaseMgmtWorkerConfig:
    profile_path: Path
    label_policy_ref: Path
    event_bus_kind: str
    event_bus_root: str
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    event_bus_start_position: str
    admitted_topics: tuple[str, ...]
    poll_max_records: int
    poll_sleep_seconds: float
    stream_id: str
    platform_run_id: str | None
    required_platform_run_id: str | None
    locator: str
    label_store_locator: str
    consumer_checkpoint_path: Path
    default_label_type: str
    default_label_value: str
    default_source_type: str
    default_actor_id: str


class _ConsumerCheckpointStore:
    def __init__(self, path: Path, stream_id: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream_id = stream_id
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS case_mgmt_worker_consumer_checkpoints (
                    stream_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    partition_id INTEGER NOT NULL,
                    next_offset TEXT NOT NULL,
                    offset_kind TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (stream_id, topic, partition_id)
                )
                """
            )

    def next_offset(self, *, topic: str, partition: int) -> tuple[str, str] | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT next_offset, offset_kind
                FROM case_mgmt_worker_consumer_checkpoints
                WHERE stream_id = ? AND topic = ? AND partition_id = ?
                """,
                (self.stream_id, topic, int(partition)),
            ).fetchone()
        if row is None:
            return None
        return str(row[0]), str(row[1])

    def advance(self, *, topic: str, partition: int, offset: str, offset_kind: str) -> None:
        next_offset = str(offset)
        if offset_kind in {"file_line", "kafka_offset"}:
            next_offset = str(int(offset) + 1)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                INSERT INTO case_mgmt_worker_consumer_checkpoints (
                    stream_id, topic, partition_id, next_offset, offset_kind, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(stream_id, topic, partition_id) DO UPDATE SET
                    next_offset = excluded.next_offset,
                    offset_kind = excluded.offset_kind,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (self.stream_id, topic, int(partition), next_offset, offset_kind, _utc_now()),
            )


class CaseMgmtWorker:
    def __init__(self, config: CaseMgmtWorkerConfig) -> None:
        self.config = config
        self.intake = CaseTriggerIntakeLedger(config.locator)
        self.label_writer = LabelStoreWriterBoundary(config.label_store_locator)
        self.labels = CaseLabelHandshakeCoordinator(
            locator=config.locator,
            intake_ledger=self.intake,
            policy=load_label_emission_policy(config.label_policy_ref),
            label_store_writer=self.label_writer,
        )
        self.consumer_checkpoints = _ConsumerCheckpointStore(config.consumer_checkpoint_path, config.stream_id)
        self._scenario_run_id: str | None = None
        self._file_reader = EventBusReader(Path(config.event_bus_root)) if config.event_bus_kind == "file" else None
        self._kinesis_reader = (
            KinesisEventBusReader(
                stream_name=config.event_bus_stream,
                region=config.event_bus_region,
                endpoint_url=config.event_bus_endpoint_url,
            )
            if config.event_bus_kind == "kinesis"
            else None
        )
        self._kafka_reader = build_kafka_reader(client_id=f"case-mgmt-worker-{config.stream_id}") if config.event_bus_kind == "kafka" else None

    def run_once(self) -> int:
        processed = 0
        for row in self._iter_records():
            topic = str(row["topic"])
            partition = int(row["partition"])
            offset = str(row["offset"])
            offset_kind = str(row["offset_kind"])
            committed = self._process_record(row)
            if committed:
                self.consumer_checkpoints.advance(
                    topic=topic,
                    partition=partition,
                    offset=offset,
                    offset_kind=offset_kind,
                )
                processed += 1
        self._export()
        return processed

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.config.poll_sleep_seconds)

    def _process_record(self, row: dict[str, Any]) -> bool:
        envelope = _unwrap_envelope(row.get("payload"))
        if str(envelope.get("event_type") or "").strip() != "case_trigger":
            return True
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else {}
        if not isinstance(payload, Mapping):
            return True

        try:
            trigger = CaseTrigger.from_payload(payload)
        except Exception as exc:
            logger.warning("CaseMgmt intake dropped invalid case_trigger payload: %s", str(exc)[:256])
            return True

        if self.config.required_platform_run_id and trigger.case_subject_key.platform_run_id != self.config.required_platform_run_id:
            return True
        if not self._ensure_scenario(trigger):
            return True

        try:
            intake = self.intake.ingest_case_trigger(
                payload=trigger.as_dict(),
                ingested_at_utc=_utc_now(),
            )
        except Exception:
            logger.exception("CaseMgmt intake failed")
            return False

        if intake.outcome != INTAKE_NEW_TRIGGER:
            return True

        evidence_refs = [item.as_dict() for item in trigger.evidence_refs]
        evidence_refs.append(
            {
                "ref_type": "CASE_EVENT",
                "ref_id": intake.timeline_event_id,
            }
        )
        try:
            self.labels.submit_label_assertion(
                case_id=intake.case_id,
                source_case_event_id=intake.timeline_event_id,
                label_subject_key={
                    "platform_run_id": trigger.case_subject_key.platform_run_id,
                    "event_id": trigger.case_subject_key.event_id,
                },
                pins=dict(trigger.pins),
                label_type=self.config.default_label_type,
                label_value=self.config.default_label_value,
                effective_time=trigger.observed_time,
                observed_time=trigger.observed_time,
                source_type=self.config.default_source_type,
                actor_id=self.config.default_actor_id,
                evidence_refs=evidence_refs,
                requested_at_utc=_utc_now(),
                label_payload={
                    "trigger_type": trigger.trigger_type,
                    "source_ref_id": trigger.source_ref_id,
                },
            )
        except Exception:
            logger.exception("CaseMgmt label handshake failed for case_id=%s", intake.case_id)
            return False
        return True

    def _ensure_scenario(self, trigger: CaseTrigger) -> bool:
        scenario_run_id = str(trigger.pins.get("scenario_run_id") or "").strip()
        platform_run_id = str(trigger.pins.get("platform_run_id") or "").strip()
        if not scenario_run_id or not platform_run_id:
            return False
        if self._scenario_run_id is None:
            self._scenario_run_id = scenario_run_id
            return True
        return self._scenario_run_id == scenario_run_id

    def _iter_records(self) -> list[dict[str, Any]]:
        if self.config.event_bus_kind == "kinesis":
            return self._read_kinesis()
        if self.config.event_bus_kind == "kafka":
            return self._read_kafka()
        if self.config.event_bus_kind == "file":
            return self._read_file()
        raise RuntimeError(f"CASE_MGMT_EVENT_BUS_KIND_UNSUPPORTED:{self.config.event_bus_kind}")

    def _read_file(self) -> list[dict[str, Any]]:
        assert self._file_reader is not None
        rows: list[dict[str, Any]] = []
        for topic in self.config.admitted_topics:
            for partition in self._file_partitions(topic):
                checkpoint = self.consumer_checkpoints.next_offset(topic=topic, partition=partition)
                from_offset = int(checkpoint[0]) if checkpoint and checkpoint[1] == "file_line" else 0
                for record in self._file_reader.read(topic, partition=partition, from_offset=from_offset, max_records=self.config.poll_max_records):
                    payload = record.record if isinstance(record.record, Mapping) else {}
                    if isinstance(payload.get("payload"), Mapping):
                        payload = dict(payload.get("payload") or {})
                    rows.append(
                        {
                            "topic": topic,
                            "partition": int(partition),
                            "offset": str(record.offset),
                            "offset_kind": "file_line",
                            "payload": payload,
                        }
                    )
        return rows

    def _read_kinesis(self) -> list[dict[str, Any]]:
        assert self._kinesis_reader is not None
        rows: list[dict[str, Any]] = []
        for topic in self.config.admitted_topics:
            stream = self.config.event_bus_stream if self.config.event_bus_stream and self.config.event_bus_stream not in {"auto", "topic"} else topic
            for shard_id in self._kinesis_reader.list_shards(stream):
                partition = _partition_from_shard(shard_id)
                checkpoint = self.consumer_checkpoints.next_offset(topic=topic, partition=partition)
                from_sequence = checkpoint[0] if checkpoint else None
                for row in self._kinesis_reader.read(
                    stream_name=stream,
                    shard_id=shard_id,
                    from_sequence=from_sequence,
                    limit=self.config.poll_max_records,
                    start_position=self.config.event_bus_start_position,
                ):
                    rows.append(
                        {
                            "topic": topic,
                            "partition": int(partition),
                            "offset": str(row.get("sequence_number") or ""),
                            "offset_kind": "kinesis_sequence",
                            "payload": row.get("payload") if isinstance(row.get("payload"), Mapping) else {},
                        }
                    )
        return rows

    def _read_kafka(self) -> list[dict[str, Any]]:
        assert self._kafka_reader is not None
        rows: list[dict[str, Any]] = []
        for topic in self.config.admitted_topics:
            for partition in self._kafka_partitions(topic):
                checkpoint = self.consumer_checkpoints.next_offset(topic=topic, partition=partition)
                from_offset: int | None = None
                if checkpoint and checkpoint[1] == "kafka_offset":
                    try:
                        from_offset = int(checkpoint[0])
                    except ValueError:
                        from_offset = None
                start_position = "earliest"
                if checkpoint is None and self.config.event_bus_start_position == "latest":
                    start_position = "latest"
                for record in self._kafka_reader.read(
                    topic=topic,
                    partition=partition,
                    from_offset=from_offset,
                    limit=self.config.poll_max_records,
                    start_position=start_position,
                ):
                    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
                    # Keep the full Kafka envelope so _process_record can validate event_type/run scope.
                    if isinstance(payload.get("envelope"), Mapping):
                        payload = dict(payload.get("envelope") or {})
                    rows.append(
                        {
                            "topic": topic,
                            "partition": int(partition),
                            "offset": str(record.get("offset")) if record.get("offset") is not None else "",
                            "offset_kind": "kafka_offset",
                            "payload": payload,
                        }
                    )
        return rows

    def _file_partitions(self, topic: str) -> list[int]:
        root = Path(self.config.event_bus_root) / topic
        if not root.exists():
            return [0]
        parts: list[int] = []
        for path in root.glob("partition=*.jsonl"):
            try:
                parts.append(int(path.stem.replace("partition=", "")))
            except ValueError:
                continue
        return sorted(set(parts)) if parts else [0]

    def _kafka_partitions(self, topic: str) -> list[int]:
        assert self._kafka_reader is not None
        partitions = self._kafka_reader.list_partitions(topic)
        return partitions if partitions else [0]

    def _export(self) -> None:
        if not self.config.platform_run_id or not self._scenario_run_id:
            return
        reporter = CaseMgmtRunReporter(
            locator=self.config.locator,
            platform_run_id=self.config.platform_run_id,
            scenario_run_id=self._scenario_run_id,
        )
        reporter.export()


def load_worker_config(profile_path: Path) -> CaseMgmtWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("CASE_MGMT_PROFILE_INVALID")

    wiring = payload.get("wiring") if isinstance(payload.get("wiring"), Mapping) else {}
    event_bus = wiring.get("event_bus") if isinstance(wiring.get("event_bus"), Mapping) else {}
    cm = payload.get("case_mgmt") if isinstance(payload.get("case_mgmt"), Mapping) else {}
    cm_policy = cm.get("policy") if isinstance(cm.get("policy"), Mapping) else {}
    cm_wiring = cm.get("wiring") if isinstance(cm.get("wiring"), Mapping) else {}
    platform_run_id = _platform_run_id()
    stream_id = _with_scope(str(_env(cm_wiring.get("stream_id") or "case_mgmt.v0")).strip(), platform_run_id)
    admitted = cm_wiring.get("admitted_topics")
    admitted_topics: tuple[str, ...]
    if isinstance(admitted, list) and admitted:
        admitted_topics = tuple(str(item).strip() for item in admitted if str(item).strip())
    else:
        admitted_topics = ("fp.bus.case.triggers.v1",)
    checkpoint_path = Path(
        resolve_run_scoped_path(
            str(_env(cm_wiring.get("consumer_checkpoint_path") or "")).strip() or None,
            suffix="case_mgmt/consumer_checkpoints.sqlite",
            create_if_missing=True,
        )
    )
    return CaseMgmtWorkerConfig(
        profile_path=profile_path,
        label_policy_ref=Path(
            str(_env(cm_policy.get("label_emission_policy_ref") or "config/platform/case_mgmt/label_emission_policy_v0.yaml"))
        ),
        event_bus_kind=str(_env(cm_wiring.get("event_bus_kind") or wiring.get("event_bus_kind") or "kinesis")).strip().lower(),
        event_bus_root=str(_env(cm_wiring.get("event_bus_root") or "runs/fraud-platform/eb")).strip(),
        event_bus_stream=_none_if_blank(_env(cm_wiring.get("event_bus_stream") or event_bus.get("stream") or "auto")),
        event_bus_region=_none_if_blank(_env(cm_wiring.get("event_bus_region") or event_bus.get("region"))),
        event_bus_endpoint_url=_none_if_blank(_env(cm_wiring.get("event_bus_endpoint_url") or event_bus.get("endpoint_url"))),
        event_bus_start_position=str(_env(cm_wiring.get("event_bus_start_position") or "trim_horizon")).strip().lower(),
        admitted_topics=admitted_topics,
        poll_max_records=max(1, int(_env(cm_wiring.get("poll_max_records") or 200))),
        poll_sleep_seconds=max(0.05, float(_env(cm_wiring.get("poll_sleep_seconds") or 0.5))),
        stream_id=stream_id,
        platform_run_id=platform_run_id,
        required_platform_run_id=_none_if_blank(
            _env(
                cm_wiring.get("required_platform_run_id")
                or os.getenv("CASE_MGMT_REQUIRED_PLATFORM_RUN_ID")
                or platform_run_id
            )
        ),
        locator=_locator(cm_wiring.get("locator"), "case_mgmt/case_mgmt.sqlite"),
        label_store_locator=_locator(cm_wiring.get("label_store_locator"), "label_store/writer.sqlite"),
        consumer_checkpoint_path=checkpoint_path,
        default_label_type=str(_env(cm_wiring.get("default_label_type") or "fraud_disposition")).strip(),
        default_label_value=str(_env(cm_wiring.get("default_label_value") or "FRAUD_SUSPECTED")).strip(),
        default_source_type=str(_env(cm_wiring.get("default_source_type") or "AUTO")).strip().upper(),
        default_actor_id=str(_env(cm_wiring.get("default_actor_id") or "SYSTEM::case_mgmt_worker")).strip(),
    )


def _env(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    token = value.strip()
    match = _ENV_PATTERN.fullmatch(token)
    if not match:
        return value
    return os.getenv(match.group(1), match.group(2) or "")


def _locator(value: Any, suffix: str) -> str:
    raw = str(_env(value) or "").strip()
    path = resolve_run_scoped_path(raw or None, suffix=suffix, create_if_missing=True)
    if not path:
        raise RuntimeError(f"CASE_MGMT_LOCATOR_MISSING:{suffix}")
    if not (path.startswith("postgres://") or path.startswith("postgresql://") or path.startswith("s3://")):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def _platform_run_id() -> str | None:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    if explicit:
        return explicit
    return resolve_platform_run_id(create_if_missing=False)


def _with_scope(base_stream: str, run_id: str | None) -> str:
    if run_id and "::" not in base_stream:
        return f"{base_stream}::{run_id}"
    return base_stream


def _unwrap_envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    if isinstance(value.get("envelope"), Mapping):
        return dict(value.get("envelope") or {})
    if isinstance(value.get("payload"), Mapping) and _looks_like_envelope(value.get("payload") or {}):
        return dict(value.get("payload") or {})
    return dict(value)


def _looks_like_envelope(value: Mapping[str, Any]) -> bool:
    return all(value.get(key) not in (None, "") for key in ("event_id", "event_type", "schema_version"))


def _partition_from_shard(shard_id: str) -> int:
    token = str(shard_id).rsplit("-", 1)[-1]
    try:
        return int(token)
    except ValueError:
        return 0


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Case Management runtime worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    worker = CaseMgmtWorker(load_worker_config(Path(args.profile)))
    if args.once:
        processed = worker.run_once()
        logger.info("CaseMgmt worker processed=%s", processed)
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
