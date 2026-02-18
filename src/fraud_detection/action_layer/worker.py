"""Action Layer runtime worker CLI."""

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

from .authz import authorize_intent, build_denied_outcome_payload
from .checkpoints import CHECKPOINT_COMMITTED, ActionCheckpointGate
from .contracts import ActionIntent, ActionOutcome
from .execution import (
    EXECUTION_COMMITTED,
    ActionEffectExecutor,
    ActionExecutionEngine,
    ActionExecutionRequest,
    ActionExecutionResult,
    build_execution_outcome_payload,
)
from .idempotency import AL_DROP_DUPLICATE, AL_EXECUTE, ActionIdempotencyGate
from .observability import ActionLayerRunMetrics
from .policy import AlPolicyBundle, load_policy_bundle
from .publish import ActionLayerIgPublisher, ActionLayerPublishError, PublishedOutcomeRecord, PUBLISH_AMBIGUOUS, build_action_outcome_envelope
from .replay import ActionOutcomeReplayLedger
from .storage import ActionLedgerStore, ActionOutcomeStore


logger = logging.getLogger("fraud_detection.al.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class AlWorkerConfig:
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
    ig_ingest_url: str
    ig_api_key: str | None
    ig_api_key_header: str
    ledger_dsn: str
    outcomes_dsn: str
    replay_dsn: str
    checkpoint_dsn: str
    consumer_checkpoint_path: Path


class _ConsumerCheckpointStore:
    def __init__(self, path: Path, stream_id: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream_id = stream_id
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS al_worker_consumer_checkpoints (
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
                FROM al_worker_consumer_checkpoints
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
                INSERT INTO al_worker_consumer_checkpoints (
                    stream_id, topic, partition_id, next_offset, offset_kind, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(stream_id, topic, partition_id) DO UPDATE SET
                    next_offset = excluded.next_offset,
                    offset_kind = excluded.offset_kind,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (self.stream_id, topic, int(partition), next_offset, offset_kind, _utc_now()),
            )


class _NoOpEffectExecutor(ActionEffectExecutor):
    def execute(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        return ActionExecutionResult(
            state=EXECUTION_COMMITTED,
            provider_code="NOOP_COMMITTED",
            provider_ref=f"noop:{request.idempotency_token}",
            message="noop committed",
        )


class ActionLayerWorker:
    def __init__(self, config: AlWorkerConfig) -> None:
        self.config = config
        self.bundle: AlPolicyBundle = load_policy_bundle(config.policy_ref)
        self.ledger_store = ActionLedgerStore(locator=config.ledger_dsn)
        self.outcome_store = ActionOutcomeStore(locator=config.outcomes_dsn)
        self.replay = ActionOutcomeReplayLedger(config.replay_dsn)
        self.checkpoints = ActionCheckpointGate(config.checkpoint_dsn)
        self.idempotency = ActionIdempotencyGate(store=self.ledger_store)
        self.publisher = ActionLayerIgPublisher(
            ig_ingest_url=config.ig_ingest_url,
            api_key=config.ig_api_key,
            api_key_header=config.ig_api_key_header,
        )
        self.executor = _NoOpEffectExecutor()
        self.consumer_checkpoints = _ConsumerCheckpointStore(config.consumer_checkpoint_path, config.stream_id)
        self._scenario_run_id: str | None = None
        self._metrics: ActionLayerRunMetrics | None = None
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
        self._kafka_reader = build_kafka_reader(client_id=f"al-worker-{config.stream_id}") if config.event_bus_kind == "kafka" else None

    def run_once(self) -> int:
        processed = 0
        for row in self._iter_records():
            self._process_record(row)
            processed += 1
        self._export()
        return processed

    def run_forever(self) -> None:
        while True:
            processed = self.run_once()
            if processed == 0:
                time.sleep(self.config.poll_sleep_seconds)

    def _process_record(self, row: dict[str, Any]) -> None:
        topic = str(row["topic"])
        partition = int(row["partition"])
        offset = str(row["offset"])
        offset_kind = str(row["offset_kind"])
        envelope = _unwrap_envelope(row.get("payload"))
        event_type = str(envelope.get("event_type") or "").strip()
        if event_type != "action_intent":
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return

        payload = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else {}
        try:
            intent = ActionIntent.from_payload(payload)
        except Exception as exc:
            logger.warning("AL intent dropped: %s", exc)
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return

        if self.config.required_platform_run_id and str((intent.payload.get("pins") or {}).get("platform_run_id") or "") != self.config.required_platform_run_id:
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return
        if not self._ensure_scenario(intent):
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return
        assert self._metrics is not None
        self._metrics.record_intake(intent_payload=intent.payload)

        idem = self.idempotency.evaluate(intent=intent, first_seen_at_utc=_utc_now())
        if idem.disposition == AL_DROP_DUPLICATE:
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return
        if idem.disposition != AL_EXECUTE:
            self._metrics.record_publish(decision="QUARANTINE", reason_code=idem.reason_code)
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return

        authz = authorize_intent(intent, bundle=self.bundle)
        if authz.allowed:
            engine = ActionExecutionEngine(executor=self.executor, retry_policy=self.bundle.retry_policy)
            terminal = engine.execute(intent=intent, semantic_key=idem.semantic_key)
            self._metrics.record_execution_terminal(terminal=terminal)
            outcome_payload = build_execution_outcome_payload(
                intent=intent,
                authz_policy_rev=self.bundle.policy_rev.as_dict(),
                terminal=terminal,
                posture_mode=self.bundle.execution_posture.mode,
                completed_at_utc=_utc_now(),
            )
        else:
            outcome_payload = build_denied_outcome_payload(
                intent=intent,
                decision=authz,
                completed_at_utc=_utc_now(),
            )

        outcome = ActionOutcome.from_payload(outcome_payload)
        self._metrics.record_outcome(outcome_payload=outcome.payload)
        append_result = self.outcome_store.register_outcome(
            outcome_payload=outcome.payload,
            recorded_at_utc=_utc_now(),
        )
        if append_result.status == "HASH_MISMATCH":
            self._metrics.record_publish(decision="QUARANTINE", reason_code="OUTCOME_HASH_MISMATCH")
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return

        token = self.checkpoints.issue_token(
            outcome_id=outcome.outcome_id,
            action_id=str(outcome.payload["action_id"]),
            decision_id=str(outcome.payload["decision_id"]),
            issued_at_utc=_utc_now(),
        )
        self.checkpoints.mark_outcome_appended(token_id=token.token_id, outcome_hash=append_result.record.payload_hash)

        published = self._publish_outcome(outcome)
        self._metrics.record_publish(decision=published.decision, reason_code=published.reason_code)
        self.outcome_store.register_publish_result(
            outcome_id=outcome.outcome_id,
            event_id=published.event_id,
            event_type=published.event_type,
            publish_decision=published.decision,
            receipt=published.receipt,
            receipt_ref=published.receipt_ref,
            reason_code=published.reason_code,
            published_at_utc=_utc_now(),
        )
        self.checkpoints.mark_publish_result(
            token_id=token.token_id,
            publish_decision=published.decision,
            receipt_ref=published.receipt_ref,
            reason_code=published.reason_code,
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
        self.replay.register_outcome(outcome_payload=outcome.payload, observed_at_utc=_utc_now())
        if commit.status == CHECKPOINT_COMMITTED:
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)

    def _publish_outcome(self, outcome: ActionOutcome) -> PublishedOutcomeRecord:
        try:
            return self.publisher.publish_envelope(build_action_outcome_envelope(outcome))
        except ActionLayerPublishError as exc:
            return PublishedOutcomeRecord(
                outcome_id=outcome.outcome_id,
                event_id=outcome.outcome_id,
                event_type="action_outcome",
                decision=PUBLISH_AMBIGUOUS,
                receipt={},
                receipt_ref=None,
                reason_code=str(exc)[:256],
            )

    def _ensure_scenario(self, intent: ActionIntent) -> bool:
        pins = intent.payload.get("pins") if isinstance(intent.payload.get("pins"), Mapping) else {}
        scenario_run_id = str((pins or {}).get("scenario_run_id") or "").strip()
        platform_run_id = str((pins or {}).get("platform_run_id") or "").strip()
        if not scenario_run_id or not platform_run_id:
            return False
        if self._scenario_run_id is None:
            self._scenario_run_id = scenario_run_id
            self._metrics = ActionLayerRunMetrics(platform_run_id=platform_run_id, scenario_run_id=scenario_run_id)
            return True
        return self._scenario_run_id == scenario_run_id

    def _iter_records(self) -> list[dict[str, Any]]:
        if self.config.event_bus_kind == "kinesis":
            return self._read_kinesis()
        if self.config.event_bus_kind == "kafka":
            return self._read_kafka()
        if self.config.event_bus_kind == "file":
            return self._read_file()
        raise RuntimeError(f"AL_EVENT_BUS_KIND_UNSUPPORTED:{self.config.event_bus_kind}")

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
                start_position = self.config.event_bus_start_position
                if checkpoint is None and self.config.required_platform_run_id:
                    start_position = "trim_horizon"
                for row in self._kinesis_reader.read(
                    stream_name=stream,
                    shard_id=shard_id,
                    from_sequence=from_sequence,
                    limit=self.config.poll_max_records,
                    start_position=start_position,
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
                if checkpoint is None and self.config.required_platform_run_id:
                    start_position = "earliest"
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
        if self._metrics is None:
            return
        metrics = self._metrics.export()
        health = self._metrics.evaluate_health(lag_events=0, queue_depth=0)
        path = self._run_root() / "action_layer" / "health" / "last_health.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "generated_at_utc": _utc_now(),
                    "platform_run_id": self._metrics.platform_run_id,
                    "scenario_run_id": self._metrics.scenario_run_id,
                    "health_state": health.state,
                    "health_reasons": list(health.reason_codes),
                    "metrics": dict(metrics.get("metrics") or {}),
                },
                sort_keys=True,
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _run_root(self) -> Path:
        if self.config.platform_run_id:
            return RUNS_ROOT / self.config.platform_run_id
        return RUNS_ROOT / "_unknown"


def load_worker_config(profile_path: Path) -> AlWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("AL_PROFILE_INVALID")
    wiring = payload.get("wiring") if isinstance(payload.get("wiring"), Mapping) else {}
    event_bus = wiring.get("event_bus") if isinstance(wiring.get("event_bus"), Mapping) else {}
    security = wiring.get("security") if isinstance(wiring.get("security"), Mapping) else {}
    al = payload.get("al") if isinstance(payload.get("al"), Mapping) else {}
    al_policy = al.get("policy") if isinstance(al.get("policy"), Mapping) else {}
    al_wiring = al.get("wiring") if isinstance(al.get("wiring"), Mapping) else {}
    platform_run_id = _platform_run_id()
    stream_id = _with_scope(str(_env(al_wiring.get("stream_id") or "al.v0")).strip(), platform_run_id)
    admitted = al_wiring.get("admitted_topics")
    admitted_topics: tuple[str, ...]
    if isinstance(admitted, list) and admitted:
        admitted_topics = tuple(str(item).strip() for item in admitted if str(item).strip())
    else:
        admitted_topics = ("fp.bus.traffic.fraud.v1",)
    checkpoint_path = Path(
        resolve_run_scoped_path(
            str(_env(al_wiring.get("consumer_checkpoint_path") or "")).strip() or None,
            suffix="action_layer/consumer_checkpoints.sqlite",
            create_if_missing=True,
        )
    )
    return AlWorkerConfig(
        profile_path=profile_path,
        policy_ref=Path(str(_env(al_policy.get("authz_policy_ref") or "config/platform/al/policy_v0.yaml"))),
        event_bus_kind=str(_env(al_wiring.get("event_bus_kind") or wiring.get("event_bus_kind") or "kinesis")).strip().lower(),
        event_bus_root=str(_env(al_wiring.get("event_bus_root") or "runs/fraud-platform/eb")).strip(),
        event_bus_stream=_none_if_blank(_env(al_wiring.get("event_bus_stream") or event_bus.get("stream") or "auto")),
        event_bus_region=_none_if_blank(_env(al_wiring.get("event_bus_region") or event_bus.get("region"))),
        event_bus_endpoint_url=_none_if_blank(_env(al_wiring.get("event_bus_endpoint_url") or event_bus.get("endpoint_url"))),
        event_bus_start_position=str(_env(al_wiring.get("event_bus_start_position") or "trim_horizon")).strip().lower(),
        admitted_topics=admitted_topics,
        poll_max_records=max(1, int(_env(al_wiring.get("poll_max_records") or 200))),
        poll_sleep_seconds=max(0.05, float(_env(al_wiring.get("poll_sleep_seconds") or 0.5))),
        stream_id=stream_id,
        platform_run_id=platform_run_id,
        required_platform_run_id=_none_if_blank(_env(al_wiring.get("required_platform_run_id") or os.getenv("AL_REQUIRED_PLATFORM_RUN_ID") or platform_run_id)),
        ig_ingest_url=str(_env(al_wiring.get("ig_ingest_url") or wiring.get("ig_ingest_url") or os.getenv("IG_INGEST_URL") or "http://127.0.0.1:8081")).strip(),
        ig_api_key=_none_if_blank(_env(al_wiring.get("ig_api_key") or os.getenv("AL_IG_API_KEY") or security.get("al_auth_token") or security.get("wsp_auth_token"))),
        ig_api_key_header=str(_env(al_wiring.get("ig_api_key_header") or security.get("api_key_header") or "X-IG-Api-Key")).strip(),
        ledger_dsn=_locator(al_wiring.get("ledger_dsn"), "action_layer/al_ledger.sqlite"),
        outcomes_dsn=_locator(al_wiring.get("outcomes_dsn"), "action_layer/al_outcomes.sqlite"),
        replay_dsn=_locator(al_wiring.get("replay_dsn"), "action_layer/al_replay.sqlite"),
        checkpoint_dsn=_locator(al_wiring.get("checkpoint_dsn"), "action_layer/al_checkpoints.sqlite"),
        consumer_checkpoint_path=checkpoint_path,
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
        raise RuntimeError(f"AL_LOCATOR_MISSING:{suffix}")
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
    parser = argparse.ArgumentParser(description="Action Layer runtime worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    worker = ActionLayerWorker(load_worker_config(Path(args.profile)))
    if args.once:
        processed = worker.run_once()
        logger.info("AL worker processed=%s", processed)
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
