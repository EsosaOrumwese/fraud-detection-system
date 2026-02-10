"""Archive writer runtime worker (Phase 6.0)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping

import yaml

from fraud_detection.event_bus import EventBusReader
from fraud_detection.event_bus.kinesis import KinesisEventBusReader
from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id, resolve_run_scoped_path
from fraud_detection.scenario_runner.storage import LocalObjectStore, ObjectStore, S3ObjectStore, build_object_store

from .contracts import ArchiveEventRecord
from .observability import (
    ArchiveWriterGovernanceEmitter,
    ArchiveWriterRunMetrics,
    build_health_payload,
    export_health,
)
from .reconciliation import ArchiveWriterReconciliation
from .store import (
    ARCHIVE_OBS_DUPLICATE,
    ARCHIVE_OBS_NEW,
    ARCHIVE_OBS_PAYLOAD_MISMATCH,
    ArchiveWriterLedger,
)


logger = logging.getLogger("fraud_detection.archive_writer.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class ArchiveWriterConfig:
    profile_path: Path
    policy_ref: Path
    platform_run_id: str | None
    required_platform_run_id: str | None
    stream_id: str
    event_bus_kind: str
    event_bus_root: str
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    event_bus_start_position: str
    admitted_topics: tuple[str, ...]
    poll_max_records: int
    poll_sleep_seconds: float
    ledger_locator: str
    platform_store_root: str
    object_store_endpoint: str | None
    object_store_region: str | None
    object_store_path_style: bool
    environment: str
    config_revision: str


class ArchiveWriterWorker:
    def __init__(self, config: ArchiveWriterConfig) -> None:
        self.config = config
        self.ledger = ArchiveWriterLedger(locator=config.ledger_locator, stream_id=config.stream_id)
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
        self._store = build_object_store(
            root=config.platform_store_root,
            s3_endpoint_url=config.object_store_endpoint,
            s3_region=config.object_store_region,
            s3_path_style=config.object_store_path_style,
        )
        run_id = self._effective_platform_run_id()
        self._metrics = ArchiveWriterRunMetrics(platform_run_id=run_id)
        self._reconciliation = ArchiveWriterReconciliation(platform_run_id=run_id)
        self._governance = ArchiveWriterGovernanceEmitter(
            store=self._store,
            platform_run_id=run_id,
            source_component="archive_writer",
            environment=config.environment,
            config_revision=config.config_revision,
        )

    def run_once(self) -> int:
        processed = 0
        for row in self._iter_records():
            self._metrics.bump("seen_total")
            committed = self._process_record(row)
            if committed:
                self.ledger.advance(
                    topic=str(row["topic"]),
                    partition=int(row["partition"]),
                    offset=str(row["offset"]),
                    offset_kind=str(row["offset_kind"]),
                )
                processed += 1
        self._export()
        return processed

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.config.poll_sleep_seconds)

    def _process_record(self, row: Mapping[str, Any]) -> bool:
        topic = str(row.get("topic") or "")
        partition = int(row.get("partition") or 0)
        offset = str(row.get("offset") or "")
        offset_kind = str(row.get("offset_kind") or "")
        envelope = _unwrap_envelope(row.get("payload"))
        try:
            record = ArchiveEventRecord.from_bus_record(
                envelope=envelope,
                topic=topic,
                partition=partition,
                offset=offset,
                offset_kind=offset_kind,
            )
        except Exception as exc:
            logger.info("Archive writer skipped non-canonical payload: %s", str(exc)[:256])
            return True

        if self.config.required_platform_run_id and record.platform_run_id != self.config.required_platform_run_id:
            return True

        run_prefix = _run_prefix_for_store(self._store, record.platform_run_id)
        relative_path = record.archive_relative_path(run_prefix=run_prefix)

        obs = self.ledger.observe(
            topic=topic,
            partition=partition,
            offset=offset,
            offset_kind=offset_kind,
            payload_hash=record.payload_hash,
            archive_ref=self._absolute_ref(relative_path),
            observed_at_utc=_utc_now(),
        )

        archive_ref = obs.archive_ref
        if obs.outcome == ARCHIVE_OBS_NEW:
            try:
                ref = self._store.write_json_if_absent(relative_path, record.as_dict())
                archive_ref = str(ref.path)
                self._metrics.bump("archived_total")
            except FileExistsError:
                self._metrics.bump("duplicate_total")
            except Exception:
                self._metrics.bump("write_error_total")
                self.ledger.clear_observation(
                    topic=topic,
                    partition=partition,
                    offset=offset,
                    offset_kind=offset_kind,
                    payload_hash=record.payload_hash,
                )
                logger.exception(
                    "Archive write failed topic=%s partition=%s offset=%s kind=%s",
                    topic,
                    partition,
                    offset,
                    offset_kind,
                )
                return False
        elif obs.outcome == ARCHIVE_OBS_DUPLICATE:
            self._metrics.bump("duplicate_total")
        elif obs.outcome == ARCHIVE_OBS_PAYLOAD_MISMATCH:
            self._metrics.bump("payload_mismatch_total")
            self._governance.emit_replay_basis_mismatch(
                scenario_run_id=record.scenario_run_id,
                topic=topic,
                partition=partition,
                offset_kind=offset_kind,
                offset=offset,
                expected_payload_hash=obs.payload_hash,
                observed_payload_hash=record.payload_hash,
                archive_ref=archive_ref,
            )

        self._reconciliation.add(
            topic=topic,
            partition=partition,
            offset_kind=offset_kind,
            offset=offset,
            outcome=obs.outcome,
            payload_hash=record.payload_hash,
            archive_ref=archive_ref,
            scenario_run_id=record.scenario_run_id,
        )
        return True

    def _iter_records(self) -> list[dict[str, Any]]:
        if self.config.event_bus_kind == "kinesis":
            return self._read_kinesis()
        return self._read_file()

    def _read_file(self) -> list[dict[str, Any]]:
        assert self._file_reader is not None
        rows: list[dict[str, Any]] = []
        for topic in self.config.admitted_topics:
            for partition in self._file_partitions(topic):
                checkpoint = self.ledger.next_offset(topic=topic, partition=partition)
                from_offset = int(checkpoint[0]) if checkpoint and checkpoint[1] == "file_line" else 0
                for record in self._file_reader.read(
                    topic,
                    partition=partition,
                    from_offset=from_offset,
                    max_records=self.config.poll_max_records,
                ):
                    payload = record.record if isinstance(record.record, Mapping) else {}
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
            stream = self.config.event_bus_stream if self.config.event_bus_stream not in (None, "", "auto", "topic") else topic
            for shard_id in self._kinesis_reader.list_shards(stream):
                partition = _partition_from_shard(shard_id)
                checkpoint = self.ledger.next_offset(topic=topic, partition=partition)
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

    def _export(self) -> None:
        metrics = self._metrics.export()
        reconciliation = self._reconciliation.export()
        counters = metrics.get("metrics") if isinstance(metrics.get("metrics"), Mapping) else {}
        health = build_health_payload(
            platform_run_id=self._effective_platform_run_id(),
            counters=counters,
            reconciliation_totals=reconciliation.get("totals") if isinstance(reconciliation.get("totals"), Mapping) else {},
        )
        export_health(platform_run_id=self._effective_platform_run_id(), payload=health)

    def _absolute_ref(self, relative_path: str) -> str:
        if isinstance(self._store, S3ObjectStore):
            key = relative_path
            if self._store.prefix:
                key = f"{self._store.prefix.rstrip('/')}/{relative_path.lstrip('/')}"
            return f"s3://{self._store.bucket}/{key}"
        if isinstance(self._store, LocalObjectStore):
            return str(self._store.root / relative_path)
        return relative_path

    def _effective_platform_run_id(self) -> str:
        run_id = str(self.config.platform_run_id or resolve_platform_run_id(create_if_missing=False) or "").strip()
        if run_id:
            return run_id
        return "_unknown"


def load_worker_config(profile_path: Path) -> ArchiveWriterConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("ARCHIVE_WRITER_PROFILE_INVALID")
    profile_id = str(payload.get("profile_id") or "local").strip() or "local"

    top_wiring = payload.get("wiring") if isinstance(payload.get("wiring"), Mapping) else {}
    event_bus = top_wiring.get("event_bus") if isinstance(top_wiring.get("event_bus"), Mapping) else {}
    object_store = top_wiring.get("object_store") if isinstance(top_wiring.get("object_store"), Mapping) else {}

    archive_payload = payload.get("archive_writer") if isinstance(payload.get("archive_writer"), Mapping) else {}
    archive_policy = archive_payload.get("policy") if isinstance(archive_payload.get("policy"), Mapping) else {}
    archive_wiring = archive_payload.get("wiring") if isinstance(archive_payload.get("wiring"), Mapping) else {}

    platform_run_id = _platform_run_id()
    stream_id = str(_env(archive_wiring.get("stream_id") or "archive_writer.v0")).strip()
    if platform_run_id:
        stream_id = f"{stream_id}::{platform_run_id}"

    topics = _load_topics_ref(archive_wiring.get("topics_ref"))
    if not topics:
        topics = (
            "fp.bus.traffic.fraud.v1",
            "fp.bus.context.arrival_events.v1",
            "fp.bus.context.arrival_entities.v1",
            "fp.bus.context.flow_anchor.fraud.v1",
            "fp.bus.rtdl.v1",
            "fp.bus.case.v1",
        )

    object_path_style_value = str(_env(object_store.get("path_style") or "true")).strip().lower()
    return ArchiveWriterConfig(
        profile_path=profile_path,
        policy_ref=Path(str(_env(archive_policy.get("policy_ref") or "config/platform/archive_writer/policy_v0.yaml"))),
        platform_run_id=platform_run_id,
        required_platform_run_id=_none_if_blank(
            _env(archive_wiring.get("required_platform_run_id") or os.getenv("ARCHIVE_WRITER_REQUIRED_PLATFORM_RUN_ID") or platform_run_id)
        ),
        stream_id=stream_id,
        event_bus_kind=str(_env(archive_wiring.get("event_bus_kind") or top_wiring.get("event_bus_kind") or "kinesis")).strip().lower(),
        event_bus_root=str(_env(archive_wiring.get("event_bus_root") or "runs/fraud-platform/eb")).strip(),
        event_bus_stream=_none_if_blank(_env(archive_wiring.get("event_bus_stream") or event_bus.get("stream") or "auto")),
        event_bus_region=_none_if_blank(_env(archive_wiring.get("event_bus_region") or event_bus.get("region"))),
        event_bus_endpoint_url=_none_if_blank(_env(archive_wiring.get("event_bus_endpoint_url") or event_bus.get("endpoint_url"))),
        event_bus_start_position=str(_env(archive_wiring.get("event_bus_start_position") or "latest")).strip().lower(),
        admitted_topics=tuple(topics),
        poll_max_records=max(1, int(_env(archive_wiring.get("poll_max_records") or 200))),
        poll_sleep_seconds=max(0.05, float(_env(archive_wiring.get("poll_sleep_seconds") or 0.5))),
        ledger_locator=_locator(archive_wiring.get("ledger_dsn"), "archive_writer/ledger.sqlite"),
        platform_store_root=str(_env(archive_wiring.get("platform_store_root") or os.getenv("PLATFORM_STORE_ROOT") or object_store.get("root") or "s3://fraud-platform")).strip(),
        object_store_endpoint=_none_if_blank(_env(archive_wiring.get("object_store_endpoint") or object_store.get("endpoint") or os.getenv("OBJECT_STORE_ENDPOINT"))),
        object_store_region=_none_if_blank(_env(archive_wiring.get("object_store_region") or object_store.get("region") or os.getenv("OBJECT_STORE_REGION"))),
        object_store_path_style=object_path_style_value in {"1", "true", "yes"},
        environment=str(_env(archive_wiring.get("environment") or profile_id)).strip(),
        config_revision=str(_env(payload.get("policy", {}).get("policy_rev") if isinstance(payload.get("policy"), Mapping) else "local-parity-v0")).strip() or "local-parity-v0",
    )


def _load_topics_ref(value: Any) -> tuple[str, ...]:
    raw = str(_env(value) or "").strip()
    if not raw:
        return tuple()
    path = Path(raw)
    if not path.exists():
        raise RuntimeError(f"ARCHIVE_WRITER_TOPICS_REF_MISSING:{path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("ARCHIVE_WRITER_TOPICS_REF_INVALID")
    rows = payload.get("topics")
    if not isinstance(rows, list):
        raise RuntimeError("ARCHIVE_WRITER_TOPICS_MISSING")
    topics = tuple(str(item).strip() for item in rows if str(item).strip())
    if not topics:
        raise RuntimeError("ARCHIVE_WRITER_TOPICS_EMPTY")
    return topics


def _platform_run_id() -> str | None:
    explicit = (os.getenv("ACTIVE_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID") or "").strip()
    if explicit:
        return explicit
    return resolve_platform_run_id(create_if_missing=False)


def _unwrap_envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    payload = dict(value)
    nested = payload.get("payload")
    if isinstance(nested, Mapping):
        return dict(nested)
    return payload


def _locator(value: Any, suffix: str) -> str:
    raw = str(_env(value) or "").strip()
    path = resolve_run_scoped_path(raw or None, suffix=suffix, create_if_missing=True)
    if not path:
        raise RuntimeError(f"ARCHIVE_WRITER_LOCATOR_MISSING:{suffix}")
    if not (path.startswith("postgres://") or path.startswith("postgresql://") or path.startswith("s3://")):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def _env(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    token = value.strip()
    match = _ENV_PATTERN.fullmatch(token)
    if not match:
        return value
    return os.getenv(match.group(1), match.group(2) or "")


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _partition_from_shard(shard_id: str) -> int:
    token = str(shard_id or "").strip().split("-")[-1]
    try:
        return int(token)
    except ValueError:
        return 0


def _run_prefix_for_store(store: ObjectStore, platform_run_id: str) -> str:
    if isinstance(store, S3ObjectStore):
        return platform_run_id
    if isinstance(store, LocalObjectStore) and store.root.name == "fraud-platform":
        return platform_run_id
    return f"fraud-platform/{platform_run_id}"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive writer worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile")
    parser.add_argument("--once", action="store_true", help="Process one polling cycle and exit")
    parser.add_argument("--poll-seconds", type=float, default=None, help="Override poll sleep seconds")
    args = parser.parse_args()

    config = load_worker_config(Path(args.profile))
    if args.poll_seconds is not None and args.poll_seconds > 0:
        config = replace(config, poll_sleep_seconds=float(args.poll_seconds))
    worker = ArchiveWriterWorker(config)
    if args.once:
        worker.run_once()
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
