"""CaseTrigger runtime worker CLI."""

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
from fraud_detection.scenario_runner.storage import build_object_store

from .adapters import CaseTriggerAdapterError, adapt_case_trigger_from_source
from .checkpoints import CHECKPOINT_COMMITTED, CaseTriggerCheckpointGate
from .config import CaseTriggerPolicy, load_trigger_policy
from .observability import CaseTriggerGovernanceEmitter, CaseTriggerRunMetrics
from .publish import (
    PUBLISH_AMBIGUOUS,
    PUBLISH_QUARANTINE,
    CaseTriggerIgPublisher,
    PublishedCaseTriggerRecord,
)
from .reconciliation import CaseTriggerReconciliationBuilder
from .replay import REPLAY_PAYLOAD_MISMATCH, CaseTriggerReplayLedger
from .storage import CaseTriggerPublishStore


logger = logging.getLogger("fraud_detection.case_trigger.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class CaseTriggerWorkerConfig:
    profile_path: Path
    policy_ref: Path
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
    event_class: str
    ig_ingest_url: str
    ig_api_key: str | None
    ig_api_key_header: str
    replay_dsn: str
    checkpoint_dsn: str
    publish_store_dsn: str
    consumer_checkpoint_path: Path
    platform_store_root: str
    object_store_endpoint: str | None
    object_store_region: str | None
    object_store_path_style: bool
    environment: str
    config_revision: str


class _ConsumerCheckpointStore:
    def __init__(self, path: Path, stream_id: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream_id = stream_id
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS case_trigger_worker_consumer_checkpoints (
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
                FROM case_trigger_worker_consumer_checkpoints
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
                INSERT INTO case_trigger_worker_consumer_checkpoints (
                    stream_id, topic, partition_id, next_offset, offset_kind, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(stream_id, topic, partition_id) DO UPDATE SET
                    next_offset = excluded.next_offset,
                    offset_kind = excluded.offset_kind,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (self.stream_id, topic, int(partition), next_offset, offset_kind, _utc_now()),
            )


class CaseTriggerWorker:
    def __init__(self, config: CaseTriggerWorkerConfig) -> None:
        self.config = config
        self.policy: CaseTriggerPolicy = load_trigger_policy(config.policy_ref)
        self.replay = CaseTriggerReplayLedger(config.replay_dsn)
        self.checkpoints = CaseTriggerCheckpointGate(config.checkpoint_dsn)
        self.publish_store = CaseTriggerPublishStore(locator=config.publish_store_dsn)
        self.publisher = CaseTriggerIgPublisher(
            ig_ingest_url=config.ig_ingest_url,
            api_key=config.ig_api_key,
            api_key_header=config.ig_api_key_header,
            publish_store=self.publish_store,
        )
        self.consumer_checkpoints = _ConsumerCheckpointStore(config.consumer_checkpoint_path, config.stream_id)
        self._scenario_run_id: str | None = None
        self._metrics: CaseTriggerRunMetrics | None = None
        self._reconciliation: CaseTriggerReconciliationBuilder | None = None
        self._governance: CaseTriggerGovernanceEmitter | None = None
        self._decision_source_event_ids: dict[str, str] = {}
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
        self._kafka_reader = build_kafka_reader(client_id=f"case-trigger-worker-{config.stream_id}") if config.event_bus_kind == "kafka" else None
        self._governance_store = None
        try:
            self._governance_store = build_object_store(
                root=config.platform_store_root,
                s3_endpoint_url=config.object_store_endpoint,
                s3_region=config.object_store_region,
                s3_path_style=config.object_store_path_style,
            )
        except Exception as exc:
            logger.warning("CaseTrigger governance store disabled: %s", str(exc)[:256])

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
        topic = str(row["topic"])
        partition = int(row["partition"])
        offset = str(row["offset"])
        offset_kind = str(row["offset_kind"])
        envelope = _unwrap_envelope(row.get("payload"))
        event_type = str(envelope.get("event_type") or "").strip()
        if event_type not in {"decision_response", "action_outcome"}:
            return True

        platform_run_id = str(envelope.get("platform_run_id") or "").strip()
        if self.config.required_platform_run_id and platform_run_id != self.config.required_platform_run_id:
            return True
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else {}
        if not isinstance(payload, Mapping):
            return True

        try:
            trigger = self._adapt_trigger(
                event_type=event_type,
                payload=payload,
                envelope=envelope,
            )
        except CaseTriggerAdapterError as exc:
            logger.info("CaseTrigger source skipped: %s", str(exc)[:256])
            return True
        except Exception:
            logger.exception("CaseTrigger adaptation failed")
            return False

        if not self._ensure_scenario(trigger):
            return True
        assert self._metrics is not None
        assert self._reconciliation is not None

        self._metrics.record_trigger_seen(trigger_payload=trigger.as_dict())
        replay_result = self.replay.register_case_trigger(
            payload=trigger.as_dict(),
            source_class=_source_class_for_event_type(event_type),
            observed_at_utc=_utc_now(),
            policy=self.policy,
        )
        published = self._publish_trigger(trigger=trigger, replay_outcome=replay_result.outcome)
        self._metrics.record_publish(decision=published.decision, reason_code=published.reason_code)

        token = self.checkpoints.issue_token(
            source_ref_id=trigger.source_ref_id,
            case_trigger_id=trigger.case_trigger_id,
            issued_at_utc=_utc_now(),
        )
        self.checkpoints.mark_ledger_committed(token_id=token.token_id)
        halted = published.decision in {PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}
        self.checkpoints.mark_publish_result(
            token_id=token.token_id,
            publish_decision=published.decision,
            halted=halted,
            halt_reason=published.reason_code if halted else None,
        )
        commit = self.checkpoints.commit_checkpoint(
            token_id=token.token_id,
            checkpoint_ref={
                "topic": topic,
                "partition": int(partition),
                "offset": str(offset),
                "offset_kind": offset_kind,
            },
            committed_at_utc=_utc_now(),
        )
        self._reconciliation.add_record(
            trigger_payload=trigger.as_dict(),
            publish_record={
                "decision": published.decision,
                "reason_code": published.reason_code,
                "receipt_ref": published.receipt_ref,
            },
            replay_outcome=replay_result.outcome,
        )
        return commit.status == CHECKPOINT_COMMITTED

    def _adapt_trigger(
        self,
        *,
        event_type: str,
        payload: Mapping[str, Any],
        envelope: Mapping[str, Any],
    ) -> Any:
        observed_time = str(envelope.get("ts_utc") or "").strip() or _utc_now()
        if event_type == "decision_response":
            decision_id = str(payload.get("decision_id") or "").strip()
            source_event = payload.get("source_event") if isinstance(payload.get("source_event"), Mapping) else {}
            source_event_id = str((source_event or {}).get("event_id") or "").strip()
            if decision_id and source_event_id:
                self._decision_source_event_ids[decision_id] = source_event_id
            return adapt_case_trigger_from_source(
                source_class="DF_DECISION",
                source_payload=payload,
                policy=self.policy,
                event_class=self.config.event_class,
                observed_time=observed_time,
                audit_record_id=_audit_ref(payload=payload, event_type=event_type),
            )

        decision_id = str(payload.get("decision_id") or "").strip()
        source_event_id = self._decision_source_event_ids.get(decision_id)
        if not source_event_id:
            raise CaseTriggerAdapterError(
                f"ACTION_OUTCOME source_event_id missing for decision_id={decision_id!r}"
            )
        return adapt_case_trigger_from_source(
            source_class="AL_OUTCOME",
            source_payload=payload,
            policy=self.policy,
            event_class=self.config.event_class,
            observed_time=observed_time,
            audit_record_id=_audit_ref(payload=payload, event_type=event_type),
            source_event_id=source_event_id,
        )

    def _publish_trigger(self, *, trigger: Any, replay_outcome: str) -> PublishedCaseTriggerRecord:
        if replay_outcome == REPLAY_PAYLOAD_MISMATCH:
            if self._governance is not None:
                self._governance.emit_collision_anomaly(
                    case_trigger_id=trigger.case_trigger_id,
                    reason_code="CASE_TRIGGER_PAYLOAD_MISMATCH",
                )
            return PublishedCaseTriggerRecord(
                case_trigger_id=trigger.case_trigger_id,
                event_id=trigger.case_trigger_id,
                event_type="case_trigger",
                decision=PUBLISH_QUARANTINE,
                receipt={},
                receipt_ref=None,
                reason_code="REPLAY_PAYLOAD_MISMATCH",
                actor_principal=None,
                actor_source_type=None,
            )

        published = self.publisher.publish_case_trigger(trigger)
        if self._governance is not None and published.decision in {PUBLISH_QUARANTINE, PUBLISH_AMBIGUOUS}:
            self._governance.emit_publish_anomaly(
                case_trigger_id=trigger.case_trigger_id,
                publish_decision=published.decision,
                reason_code=published.reason_code,
                receipt_ref=published.receipt_ref,
            )
        return published

    def _ensure_scenario(self, trigger: Any) -> bool:
        pins = trigger.pins if isinstance(trigger.pins, Mapping) else {}
        scenario_run_id = str(pins.get("scenario_run_id") or "").strip()
        platform_run_id = str(pins.get("platform_run_id") or "").strip()
        if not scenario_run_id or not platform_run_id:
            return False
        if self._scenario_run_id is None:
            self._scenario_run_id = scenario_run_id
            self._metrics = CaseTriggerRunMetrics(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
            )
            self._reconciliation = CaseTriggerReconciliationBuilder(
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
            )
            if self._governance_store is not None:
                self._governance = CaseTriggerGovernanceEmitter(
                    store=self._governance_store,
                    platform_run_id=platform_run_id,
                    scenario_run_id=scenario_run_id,
                    source_component="case_trigger",
                    environment=self.config.environment,
                    config_revision=self.config.config_revision,
                )
            return True
        return self._scenario_run_id == scenario_run_id

    def _iter_records(self) -> list[dict[str, Any]]:
        if self.config.event_bus_kind == "kinesis":
            return self._read_kinesis()
        if self.config.event_bus_kind == "kafka":
            return self._read_kafka()
        if self.config.event_bus_kind == "file":
            return self._read_file()
        raise RuntimeError(f"CASE_TRIGGER_EVENT_BUS_KIND_UNSUPPORTED:{self.config.event_bus_kind}")

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
                    if isinstance(payload.get("payload"), Mapping):
                        payload = dict(payload.get("payload") or {})
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
        if self._metrics is None or self._reconciliation is None:
            return
        metrics = self._metrics.export()
        reconciliation = self._reconciliation.export()
        counters = metrics.get("metrics") if isinstance(metrics.get("metrics"), Mapping) else {}
        reasons: list[str] = []
        health_state = "GREEN"
        if int(counters.get("quarantine", 0)) > 0:
            health_state = "RED"
            reasons.append("QUARANTINE_NONZERO")
        if int(counters.get("publish_ambiguous", 0)) > 0:
            health_state = "RED"
            reasons.append("PUBLISH_AMBIGUOUS_NONZERO")
        health_payload = {
            "generated_at_utc": _utc_now(),
            "platform_run_id": self._metrics.platform_run_id,
            "scenario_run_id": self._metrics.scenario_run_id,
            "health_state": health_state,
            "health_reasons": sorted(set(reasons)),
            "metrics": dict(counters),
            "reconciliation_totals": reconciliation.get("totals"),
        }
        path = self._run_root() / "case_trigger" / "health" / "last_health.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(health_payload, sort_keys=True, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _run_root(self) -> Path:
        if self.config.platform_run_id:
            return RUNS_ROOT / self.config.platform_run_id
        return RUNS_ROOT / "_unknown"


def load_worker_config(profile_path: Path) -> CaseTriggerWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise RuntimeError("CASE_TRIGGER_PROFILE_INVALID")

    profile_id = str(payload.get("profile_id") or "local")
    wiring = payload.get("wiring") if isinstance(payload.get("wiring"), Mapping) else {}
    event_bus = wiring.get("event_bus") if isinstance(wiring.get("event_bus"), Mapping) else {}
    security = wiring.get("security") if isinstance(wiring.get("security"), Mapping) else {}
    object_store = wiring.get("object_store") if isinstance(wiring.get("object_store"), Mapping) else {}

    ct = payload.get("case_trigger") if isinstance(payload.get("case_trigger"), Mapping) else {}
    ct_policy = ct.get("policy") if isinstance(ct.get("policy"), Mapping) else {}
    ct_wiring = ct.get("wiring") if isinstance(ct.get("wiring"), Mapping) else {}

    platform_run_id = _platform_run_id()
    stream_id = _with_scope(str(_env(ct_wiring.get("stream_id") or "case_trigger.v0")).strip(), platform_run_id)
    admitted = ct_wiring.get("admitted_topics")
    admitted_topics: tuple[str, ...]
    if isinstance(admitted, list) and admitted:
        admitted_topics = tuple(str(item).strip() for item in admitted if str(item).strip())
    else:
        admitted_topics = ("fp.bus.rtdl.v1",)
    checkpoint_path = Path(
        resolve_run_scoped_path(
            str(_env(ct_wiring.get("consumer_checkpoint_path") or "")).strip() or None,
            suffix="case_trigger/consumer_checkpoints.sqlite",
            create_if_missing=True,
        )
    )
    object_path_style_value = str(_env(object_store.get("path_style") or os.getenv("SR_S3_PATH_STYLE") or "true")).strip().lower()
    return CaseTriggerWorkerConfig(
        profile_path=profile_path,
        policy_ref=Path(str(_env(ct_policy.get("trigger_policy_ref") or "config/platform/case_trigger/trigger_policy_v0.yaml"))),
        event_bus_kind=str(_env(ct_wiring.get("event_bus_kind") or wiring.get("event_bus_kind") or "kinesis")).strip().lower(),
        event_bus_root=str(_env(ct_wiring.get("event_bus_root") or "runs/fraud-platform/eb")).strip(),
        event_bus_stream=_none_if_blank(_env(ct_wiring.get("event_bus_stream") or event_bus.get("stream") or "auto")),
        event_bus_region=_none_if_blank(_env(ct_wiring.get("event_bus_region") or event_bus.get("region"))),
        event_bus_endpoint_url=_none_if_blank(_env(ct_wiring.get("event_bus_endpoint_url") or event_bus.get("endpoint_url"))),
        event_bus_start_position=str(_env(ct_wiring.get("event_bus_start_position") or "trim_horizon")).strip().lower(),
        admitted_topics=admitted_topics,
        poll_max_records=max(1, int(_env(ct_wiring.get("poll_max_records") or 200))),
        poll_sleep_seconds=max(0.05, float(_env(ct_wiring.get("poll_sleep_seconds") or 0.5))),
        stream_id=stream_id,
        platform_run_id=platform_run_id,
        required_platform_run_id=_none_if_blank(
            _env(
                ct_wiring.get("required_platform_run_id")
                or os.getenv("CASE_TRIGGER_REQUIRED_PLATFORM_RUN_ID")
                or platform_run_id
            )
        ),
        event_class=str(_env(ct_wiring.get("event_class") or "traffic_fraud")).strip(),
        ig_ingest_url=str(
            _env(
                ct_wiring.get("ig_ingest_url")
                or wiring.get("ig_ingest_url")
                or os.getenv("IG_INGEST_URL")
                or "http://127.0.0.1:8081"
            )
        ).strip(),
        ig_api_key=_none_if_blank(
            _env(
                ct_wiring.get("ig_api_key")
                or os.getenv("CASE_TRIGGER_IG_API_KEY")
                or security.get("case_trigger_auth_token")
                or security.get("wsp_auth_token")
            )
        ),
        ig_api_key_header=str(_env(ct_wiring.get("ig_api_key_header") or security.get("api_key_header") or "X-IG-Api-Key")).strip(),
        replay_dsn=_locator(ct_wiring.get("replay_dsn"), "case_trigger/replay.sqlite"),
        checkpoint_dsn=_locator(ct_wiring.get("checkpoint_dsn"), "case_trigger/checkpoints.sqlite"),
        publish_store_dsn=_locator(ct_wiring.get("publish_store_dsn"), "case_trigger/publish.sqlite"),
        consumer_checkpoint_path=checkpoint_path,
        platform_store_root=str(_env(ct_wiring.get("platform_store_root") or os.getenv("PLATFORM_STORE_ROOT") or object_store.get("root") or "s3://fraud-platform")).strip(),
        object_store_endpoint=_none_if_blank(
            _env(ct_wiring.get("object_store_endpoint") or object_store.get("endpoint") or os.getenv("OBJECT_STORE_ENDPOINT"))
        ),
        object_store_region=_none_if_blank(
            _env(ct_wiring.get("object_store_region") or object_store.get("region") or os.getenv("OBJECT_STORE_REGION"))
        ),
        object_store_path_style=object_path_style_value in {"1", "true", "yes"},
        environment=str(_env(ct_wiring.get("environment") or profile_id)).strip(),
        config_revision=str(_env(payload.get("policy", {}).get("policy_rev") if isinstance(payload.get("policy"), Mapping) else "local-parity-v0")).strip() or "local-parity-v0",
    )


def _source_class_for_event_type(event_type: str) -> str:
    if event_type == "decision_response":
        return "DF_DECISION"
    return "AL_OUTCOME"


def _audit_ref(*, payload: Mapping[str, Any], event_type: str) -> str:
    if event_type == "decision_response":
        decision_id = str(payload.get("decision_id") or "").strip()
        if decision_id:
            return f"audit_{decision_id}"
    outcome_id = str(payload.get("outcome_id") or "").strip()
    if outcome_id:
        return f"audit_{outcome_id}"
    return f"audit_{event_type}_missing_id"


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
        raise RuntimeError(f"CASE_TRIGGER_LOCATOR_MISSING:{suffix}")
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
    parser = argparse.ArgumentParser(description="CaseTrigger runtime worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    worker = CaseTriggerWorker(load_worker_config(Path(args.profile)))
    if args.once:
        processed = worker.run_once()
        logger.info("CaseTrigger worker processed=%s", processed)
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
