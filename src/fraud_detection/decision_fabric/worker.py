"""Decision Fabric runtime worker CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Mapping

import yaml

from fraud_detection.context_store_flow_binding.query import ContextStoreFlowBindingQueryService
from fraud_detection.degrade_ladder.config import load_policy_bundle as load_dl_policy_bundle
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev
from fraud_detection.degrade_ladder.evaluator import resolve_scope
from fraud_detection.degrade_ladder.health import DlHealthGateController, DlHealthPolicy
from fraud_detection.degrade_ladder.serve import DlCurrentPostureService, DlGuardedPostureService
from fraud_detection.degrade_ladder.store import build_store as build_dl_store
from fraud_detection.event_bus import EventBusReader
from fraud_detection.event_bus.kafka import build_kafka_reader
from fraud_detection.event_bus.kinesis import KinesisEventBusReader
from fraud_detection.identity_entity_graph.query import IdentityGraphQuery
from fraud_detection.online_feature_plane.serve import OfpGetFeaturesService
from fraud_detection.platform_runtime import RUNS_ROOT, resolve_platform_run_id, resolve_run_scoped_path

from .checkpoints import CHECKPOINT_COMMITTED, DecisionCheckpointGate
from .config import load_trigger_policy
from .context import DecisionContextAcquirer, DecisionContextPolicy
from .inlet import DfBusInput, DecisionFabricInlet, DecisionTriggerCandidate
from .observability import DfRunMetrics
from .posture import DfPostureResolver, DfPostureStamp
from .publish import DecisionFabricIgPublisher, DecisionFabricPublishError
from .reconciliation import DfReconciliationBuilder
from .registry import RegistryResolutionPolicy, RegistryResolver, RegistryScopeKey, RegistrySnapshot
from .replay import REPLAY_NEW, DecisionReplayLedger
from .synthesis import DecisionSynthesizer


logger = logging.getLogger("fraud_detection.df.worker")
_ENV_PATTERN = re.compile(r"^\$\{([^}:]+)(?::-([^}]*))?\}$")


@dataclass(frozen=True)
class DfWorkerConfig:
    profile_path: Path
    trigger_policy_ref: Path
    context_policy_ref: Path
    registry_policy_ref: Path
    registry_snapshot_ref: Path
    engine_contracts_root: Path
    class_map_ref: Path
    event_bus_kind: str
    event_bus_root: str
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    event_bus_start_position: str
    poll_max_records: int
    poll_sleep_seconds: float
    stream_id: str
    platform_run_id: str | None
    required_platform_run_id: str | None
    ig_ingest_url: str
    ig_api_key: str | None
    ig_api_key_header: str
    replay_dsn: str
    checkpoint_dsn: str
    consumer_checkpoint_path: Path
    dl_policy_ref: Path
    dl_policy_profile_id: str
    dl_store_dsn: str
    dl_stream_id: str
    dl_scope_key: str
    dl_max_age_seconds: int
    environment: str
    bundle_slot: str
    tenant_id: str | None


class _ConsumerCheckpointStore:
    def __init__(self, path: Path, stream_id: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream_id = stream_id
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS df_worker_consumer_checkpoints (
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
                FROM df_worker_consumer_checkpoints
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
                INSERT INTO df_worker_consumer_checkpoints (
                    stream_id, topic, partition_id, next_offset, offset_kind, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(stream_id, topic, partition_id) DO UPDATE SET
                    next_offset = excluded.next_offset,
                    offset_kind = excluded.offset_kind,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (self.stream_id, topic, int(partition), next_offset, offset_kind, _utc_now()),
            )


class DecisionFabricWorker:
    def __init__(self, config: DfWorkerConfig) -> None:
        self.config = config
        self.trigger_policy = load_trigger_policy(config.trigger_policy_ref)
        self.context_policy = DecisionContextPolicy.load(config.context_policy_ref)
        self.registry_policy = RegistryResolutionPolicy.load(config.registry_policy_ref)
        self.registry_snapshot = RegistrySnapshot.load(config.registry_snapshot_ref)
        self.registry_resolver = RegistryResolver(policy=self.registry_policy, snapshot=self.registry_snapshot)
        self.inlet = DecisionFabricInlet(
            self.trigger_policy,
            engine_contracts_root=config.engine_contracts_root,
            class_map_ref=config.class_map_ref,
        )
        self.replay = DecisionReplayLedger(config.replay_dsn)
        self.checkpoint_gate = DecisionCheckpointGate(config.checkpoint_dsn)
        self.consumer_checkpoints = _ConsumerCheckpointStore(config.consumer_checkpoint_path, config.stream_id)
        self.csfb_query = ContextStoreFlowBindingQueryService.build_from_policy(config.profile_path)
        self.ieg_query = IdentityGraphQuery.from_profile(str(config.profile_path))
        self.ofp_service = OfpGetFeaturesService.build(
            str(config.profile_path),
            graph_version_resolver=self._resolve_graph_version,
        )
        self.acquirer = DecisionContextAcquirer(
            policy=self.context_policy,
            ofp_client=self.ofp_service,
            ieg_query=self.ieg_query,
        )
        dl_bundle = load_dl_policy_bundle(config.dl_policy_ref)
        dl_profile = dl_bundle.profile(config.dl_policy_profile_id)
        dl_store = build_dl_store(config.dl_store_dsn, stream_id=config.dl_stream_id)
        dl_base = DlCurrentPostureService(store=dl_store, fallback_profile=dl_profile, fallback_policy_rev=dl_bundle.policy_rev)
        self.posture_resolver = DfPostureResolver(
            guarded_service=DlGuardedPostureService(base_service=dl_base, health_gate=DlHealthGateController(DlHealthPolicy())),
            max_age_seconds=config.dl_max_age_seconds,
        )
        self.publisher = DecisionFabricIgPublisher(
            ig_ingest_url=config.ig_ingest_url,
            api_key=config.ig_api_key,
            api_key_header=config.ig_api_key_header,
            engine_contracts_root=config.engine_contracts_root,
        )
        self.synthesizer = DecisionSynthesizer()
        self.run_config_digest = _sha256(
            {
                "trigger": self.trigger_policy.content_digest,
                "context": self.context_policy.content_digest,
                "registry_policy": self.registry_policy.content_digest,
                "registry_snapshot": self.registry_snapshot.snapshot_digest,
            }
        )
        self._scenario_run_id: str | None = None
        self._metrics: DfRunMetrics | None = None
        self._reconciliation: DfReconciliationBuilder | None = None
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
        self._kafka_reader = build_kafka_reader(client_id=f"df-worker-{config.stream_id}") if config.event_bus_kind == "kafka" else None

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
        bus = DfBusInput(
            topic=topic,
            partition=partition,
            offset=offset,
            offset_kind=offset_kind,
            payload=envelope,
            published_at_utc=_none_if_blank(row.get("published_at_utc")),
        )
        inlet = self.inlet.evaluate(bus)
        if not inlet.accepted or inlet.candidate is None:
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return
        candidate = inlet.candidate
        if self.config.required_platform_run_id and str(candidate.pins.get("platform_run_id") or "") != self.config.required_platform_run_id:
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return
        if not self._ensure_scenario(candidate):
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)
            return

        started = _utc_now()
        posture = self._resolve_posture(candidate)
        context = self.acquirer.acquire(
            candidate=candidate,
            posture=posture,
            decision_started_at_utc=started,
            now_utc=_utc_now(),
            context_refs=self._context_refs(candidate, envelope),
            feature_keys=_feature_keys(candidate, envelope),
            compatibility=None,
        )
        registry = self.registry_resolver.resolve(
            scope_key=self._registry_scope(candidate, envelope),
            posture=posture,
            feature_group_versions=context.feature_group_versions,
        )
        artifacts = self.synthesizer.synthesize(
            candidate=candidate,
            posture=posture,
            registry_result=registry,
            context_result=context,
            run_config_digest=self.run_config_digest,
            decided_at_utc=_utc_now(),
            requested_at_utc=_utc_now(),
            decision_scope="fraud.primary",
        )
        replay = self.replay.register_decision(decision_payload=artifacts.decision_payload, observed_at_utc=_utc_now())
        token = self.checkpoint_gate.issue_token(
            source_event_id=candidate.source_event_id,
            decision_id=artifacts.decision_payload["decision_id"],
            issued_at_utc=_utc_now(),
        )
        self.checkpoint_gate.mark_ledger_committed(token_id=token.token_id)

        publish_decision = "DUPLICATE"
        action_decisions: tuple[str, ...] = tuple()
        halted = False
        halt_reason = None
        decision_receipt_ref = None
        action_receipt_refs: tuple[str, ...] = tuple()

        if replay.outcome == REPLAY_NEW:
            try:
                result = self.publisher.publish_decision_and_intents(
                    decision_envelope=artifacts.decision_envelope,
                    action_envelopes=artifacts.action_envelopes,
                )
                publish_decision = result.decision_record.decision
                action_decisions = tuple(item.decision for item in result.action_records)
                decision_receipt_ref = result.decision_record.receipt_ref
                action_receipt_refs = tuple(item.receipt_ref for item in result.action_records if item.receipt_ref)
                halted = bool(result.halted)
                halt_reason = result.halt_reason
            except DecisionFabricPublishError as exc:
                publish_decision = "QUARANTINE"
                halted = True
                halt_reason = str(exc)[:256]

        self.checkpoint_gate.mark_publish_result(
            token_id=token.token_id,
            decision_publish=publish_decision,
            action_publishes=action_decisions,
            halted=halted,
            halt_reason=halt_reason,
        )
        commit = self.checkpoint_gate.commit_checkpoint(
            token_id=token.token_id,
            checkpoint_ref={
                "topic": candidate.source_eb_ref.topic,
                "partition": int(candidate.source_eb_ref.partition),
                "offset": str(candidate.source_eb_ref.offset),
                "offset_kind": str(candidate.source_eb_ref.offset_kind),
            },
            committed_at_utc=_utc_now(),
        )
        if commit.status == CHECKPOINT_COMMITTED:
            self.consumer_checkpoints.advance(topic=topic, partition=partition, offset=offset, offset_kind=offset_kind)

        if self._metrics is not None:
            self._metrics.record_decision(
                decision_payload=artifacts.decision_payload,
                latency_ms=_latency_ms(started, _utc_now()),
                publish_decision=publish_decision,
            )
        if self._reconciliation is not None:
            self._reconciliation.add_record(
                decision_payload=artifacts.decision_payload,
                action_intents=artifacts.action_intents,
                publish_decision=publish_decision,
                decision_receipt_ref=decision_receipt_ref,
                action_receipt_refs=action_receipt_refs,
            )

    def _resolve_graph_version(self, request: dict[str, Any]) -> dict[str, Any] | None:
        scenario_run_id = str(((request.get("pins") or {}).get("scenario_run_id") or "")).strip()
        if not scenario_run_id:
            return None
        try:
            status = self.ieg_query.status(scenario_run_id=scenario_run_id)
        except Exception:
            return None
        graph = status.get("graph_version")
        return dict(graph) if isinstance(graph, Mapping) else None

    def _resolve_posture(self, candidate: DecisionTriggerCandidate) -> DfPostureStamp:
        try:
            return self.posture_resolver.resolve(
                scope_key=self.config.dl_scope_key,
                decision_time_utc=str(candidate.source_ts_utc or _utc_now()),
                policy_ok=True,
                required_signals_ok=True,
            )
        except Exception:
            return DfPostureStamp(
                scope_key=self.config.dl_scope_key,
                mode="FAIL_CLOSED",
                capabilities_mask=CapabilitiesMask(
                    allow_ieg=False,
                    allowed_feature_groups=tuple(),
                    allow_model_primary=False,
                    allow_model_stage2=False,
                    allow_fallback_heuristics=True,
                    action_posture="STEP_UP_ONLY",
                ),
                policy_rev=PolicyRev(policy_id="dl.policy.fail_closed", revision="df.worker", content_digest="0" * 64),
                posture_seq=0,
                decided_at_utc=_utc_now(),
                source="DF_WORKER_FAILSAFE",
                trust_state="UNTRUSTED",
                served_at_utc=_utc_now(),
                reasons=("DL_RESOLVE_FAILED",),
            )

    def _context_refs(self, candidate: DecisionTriggerCandidate, envelope: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        flow_id = _flow_id(envelope)
        if not flow_id:
            return {}
        response = self.csfb_query.query(
            {
                "request_id": f"df_ctx_{candidate.source_event_id}",
                "query_kind": "resolve_flow_binding",
                "flow_id": flow_id,
                "pins": dict(candidate.pins),
            }
        )
        if str(response.get("status") or "") != "READY":
            return {}
        refs: dict[str, dict[str, Any]] = {}
        flow_binding = response.get("flow_binding") if isinstance(response.get("flow_binding"), Mapping) else {}
        source_event = flow_binding.get("source_event") if isinstance(flow_binding.get("source_event"), Mapping) else {}
        eb_ref = source_event.get("eb_ref") if isinstance(source_event.get("eb_ref"), Mapping) else {}
        if eb_ref:
            refs["arrival_events"] = dict(eb_ref)
            refs["arrival_entities"] = dict(eb_ref)
        join_key = response.get("join_frame_key") if isinstance(response.get("join_frame_key"), Mapping) else {}
        if join_key:
            refs["flow_anchor"] = dict(join_key)
        return refs

    def _registry_scope(self, candidate: DecisionTriggerCandidate, envelope: Mapping[str, Any]) -> RegistryScopeKey:
        mode = "baseline" if "baseline" in f"{candidate.event_class}|{candidate.source_event_type}".lower() else "fraud"
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else {}
        explicit_mode = str((payload or {}).get("mode") or (payload or {}).get("traffic_mode") or "").strip().lower()
        if explicit_mode in {"fraud", "baseline"}:
            mode = explicit_mode
        tenant = str((payload or {}).get("tenant_id") or "").strip() or self.config.tenant_id
        return RegistryScopeKey(
            environment=self.config.environment,
            mode=mode,
            bundle_slot=self.config.bundle_slot,
            tenant_id=tenant or None,
        )

    def _ensure_scenario(self, candidate: DecisionTriggerCandidate) -> bool:
        scenario_run_id = str(candidate.pins.get("scenario_run_id") or "").strip()
        platform_run_id = str(candidate.pins.get("platform_run_id") or "").strip()
        if not scenario_run_id or not platform_run_id:
            return False
        if self._scenario_run_id is None:
            self._scenario_run_id = scenario_run_id
            self._metrics = DfRunMetrics(platform_run_id=platform_run_id, scenario_run_id=scenario_run_id)
            self._reconciliation = DfReconciliationBuilder(platform_run_id=platform_run_id, scenario_run_id=scenario_run_id)
            return True
        return self._scenario_run_id == scenario_run_id

    def _iter_records(self) -> list[dict[str, Any]]:
        if self.config.event_bus_kind == "kinesis":
            return self._read_kinesis()
        if self.config.event_bus_kind == "kafka":
            return self._read_kafka()
        if self.config.event_bus_kind == "file":
            return self._read_file()
        raise RuntimeError(f"DF_EVENT_BUS_KIND_UNSUPPORTED:{self.config.event_bus_kind}")

    def _read_file(self) -> list[dict[str, Any]]:
        assert self._file_reader is not None
        rows: list[dict[str, Any]] = []
        for topic in self.trigger_policy.admitted_traffic_topics:
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
                            "published_at_utc": _none_if_blank((record.record or {}).get("published_at_utc") if isinstance(record.record, Mapping) else None),
                        }
                    )
        return rows

    def _read_kinesis(self) -> list[dict[str, Any]]:
        assert self._kinesis_reader is not None
        rows: list[dict[str, Any]] = []
        for topic in self.trigger_policy.admitted_traffic_topics:
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
                            "published_at_utc": _none_if_blank(row.get("published_at_utc")),
                        }
                    )
        return rows

    def _read_kafka(self) -> list[dict[str, Any]]:
        assert self._kafka_reader is not None
        rows: list[dict[str, Any]] = []
        for topic in self.trigger_policy.admitted_traffic_topics:
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
                    rows.append(
                        {
                            "topic": topic,
                            "partition": int(partition),
                            "offset": str(record.get("offset")) if record.get("offset") is not None else "",
                            "offset_kind": "kafka_offset",
                            "payload": record.get("payload") if isinstance(record.get("payload"), Mapping) else {},
                            "published_at_utc": _none_if_blank(record.get("published_at_utc")),
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
        self._reconciliation.export()
        health = {
            "generated_at_utc": _utc_now(),
            "platform_run_id": self._metrics.platform_run_id,
            "scenario_run_id": self._metrics.scenario_run_id,
            "health_state": "RED" if int(metrics["metrics"].get("publish_quarantine_total", 0)) > 0 else "GREEN",
            "metrics": dict(metrics["metrics"]),
        }
        path = self._run_root() / "decision_fabric" / "health" / "last_health.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(health, sort_keys=True, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def _run_root(self) -> Path:
        if self.config.platform_run_id:
            return RUNS_ROOT / self.config.platform_run_id
        return RUNS_ROOT / "_unknown"


def load_worker_config(profile_path: Path) -> DfWorkerConfig:
    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("DF_PROFILE_INVALID")
    profile_id = str(payload.get("profile_id") or "local")
    wiring = payload.get("wiring") if isinstance(payload.get("wiring"), Mapping) else {}
    event_bus = wiring.get("event_bus") if isinstance(wiring.get("event_bus"), Mapping) else {}
    security = wiring.get("security") if isinstance(wiring.get("security"), Mapping) else {}
    df = payload.get("df") if isinstance(payload.get("df"), Mapping) else {}
    df_policy = df.get("policy") if isinstance(df.get("policy"), Mapping) else {}
    df_wiring = df.get("wiring") if isinstance(df.get("wiring"), Mapping) else {}
    dl = payload.get("dl") if isinstance(payload.get("dl"), Mapping) else {}
    dl_policy = dl.get("policy") if isinstance(dl.get("policy"), Mapping) else {}
    dl_wiring = dl.get("wiring") if isinstance(dl.get("wiring"), Mapping) else {}
    platform_run_id = _platform_run_id()
    stream_id = _with_scope(str(_env(df_wiring.get("stream_id") or "df.v0")).strip(), platform_run_id)
    dl_stream_id = _with_scope(str(_env(dl_wiring.get("stream_id") or "dl.v0")).strip(), platform_run_id)
    dl_scope = resolve_scope(
        scope_kind=str(_env(dl_wiring.get("scope_kind") or "GLOBAL")).strip().upper(),
        manifest_fingerprint=_none_if_blank(_env(dl_wiring.get("manifest_fingerprint"))),
        run_id=_none_if_blank(_env(dl_wiring.get("run_id"))),
        scenario_id=_none_if_blank(_env(dl_wiring.get("scenario_id"))),
        parameter_hash=_none_if_blank(_env(dl_wiring.get("parameter_hash"))),
        seed=_none_if_blank(_env(dl_wiring.get("seed"))),
    )
    checkpoint_path = Path(
        resolve_run_scoped_path(
            str(_env(df_wiring.get("consumer_checkpoint_path") or "")).strip() or None,
            suffix="decision_fabric/consumer_checkpoints.sqlite",
            create_if_missing=True,
        )
    )
    return DfWorkerConfig(
        profile_path=profile_path,
        trigger_policy_ref=Path(str(_env(df_policy.get("trigger_policy_ref") or "config/platform/df/trigger_policy_v0.yaml"))),
        context_policy_ref=Path(str(_env(df_policy.get("context_policy_ref") or "config/platform/df/context_policy_v0.yaml"))),
        registry_policy_ref=Path(str(_env(df_policy.get("registry_resolution_policy_ref") or "config/platform/df/registry_resolution_policy_v0.yaml"))),
        registry_snapshot_ref=Path(str(_env(df_policy.get("registry_snapshot_ref") or "config/platform/df/registry_snapshot_local_parity_v0.yaml"))),
        engine_contracts_root=Path(str(_env(df_wiring.get("engine_contracts_root") or "docs/model_spec/data-engine/interface_pack/contracts"))),
        class_map_ref=Path(str(_env(df_wiring.get("class_map_ref") or "config/platform/ig/class_map_v0.yaml"))),
        event_bus_kind=str(_env(df_wiring.get("event_bus_kind") or wiring.get("event_bus_kind") or "kinesis")).strip().lower(),
        event_bus_root=str(_env(df_wiring.get("event_bus_root") or "runs/fraud-platform/eb")).strip(),
        event_bus_stream=_none_if_blank(_env(df_wiring.get("event_bus_stream") or event_bus.get("stream") or "auto")),
        event_bus_region=_none_if_blank(_env(df_wiring.get("event_bus_region") or event_bus.get("region"))),
        event_bus_endpoint_url=_none_if_blank(_env(df_wiring.get("event_bus_endpoint_url") or event_bus.get("endpoint_url"))),
        event_bus_start_position=str(_env(df_wiring.get("event_bus_start_position") or "trim_horizon")).strip().lower(),
        poll_max_records=max(1, int(_env(df_wiring.get("poll_max_records") or 200))),
        poll_sleep_seconds=max(0.05, float(_env(df_wiring.get("poll_sleep_seconds") or 0.5))),
        stream_id=stream_id,
        platform_run_id=platform_run_id,
        required_platform_run_id=_none_if_blank(_env(df_wiring.get("required_platform_run_id") or os.getenv("DF_REQUIRED_PLATFORM_RUN_ID") or platform_run_id)),
        ig_ingest_url=str(_env(df_wiring.get("ig_ingest_url") or wiring.get("ig_ingest_url") or os.getenv("IG_INGEST_URL") or "http://127.0.0.1:8081")).strip(),
        ig_api_key=_none_if_blank(_env(df_wiring.get("ig_api_key") or os.getenv("DF_IG_API_KEY") or security.get("df_auth_token") or security.get("wsp_auth_token"))),
        ig_api_key_header=str(_env(df_wiring.get("ig_api_key_header") or security.get("api_key_header") or "X-IG-Api-Key")).strip(),
        replay_dsn=_locator(df_wiring.get("replay_dsn"), "decision_fabric/replay.sqlite"),
        checkpoint_dsn=_locator(df_wiring.get("checkpoint_dsn"), "decision_fabric/checkpoints.sqlite"),
        consumer_checkpoint_path=checkpoint_path,
        dl_policy_ref=Path(str(_env(dl_policy.get("profiles_ref") or "config/platform/dl/policy_profiles_v0.yaml"))),
        dl_policy_profile_id=str(_env(dl_policy.get("profile_id") or profile_id)).strip(),
        dl_store_dsn=_locator(dl_wiring.get("store_dsn"), "degrade_ladder/posture.sqlite"),
        dl_stream_id=dl_stream_id,
        dl_scope_key=dl_scope.scope_key,
        dl_max_age_seconds=max(1, int(_env(dl_wiring.get("max_age_seconds") or 120))),
        environment=str(_env(df_wiring.get("environment") or profile_id)).strip(),
        bundle_slot=str(_env(df_wiring.get("bundle_slot") or "primary")).strip(),
        tenant_id=_none_if_blank(_env(df_wiring.get("tenant_id"))),
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
        raise RuntimeError(f"DF_LOCATOR_MISSING:{suffix}")
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


def _flow_id(envelope: Mapping[str, Any]) -> str | None:
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else {}
    for token in (payload.get("flow_id"), envelope.get("flow_id")):
        text = str(token or "").strip()
        if text:
            return text
    return None


def _feature_keys(candidate: DecisionTriggerCandidate, envelope: Mapping[str, Any]) -> list[dict[str, str]]:
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), Mapping) else {}
    values: list[tuple[str, str]] = [("event_id", candidate.source_event_id)]
    flow = _flow_id(envelope)
    if flow:
        values.append(("flow_id", flow))
    for key in ("account_id", "customer_id", "card_id", "device_id", "merchant_id"):
        token = str(payload.get(key) or "").strip()
        if token:
            values.append((key, token))
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, str]] = []
    for key_type, key_id in values:
        pair = (key_type, key_id)
        if pair in seen:
            continue
        seen.add(pair)
        rows.append({"key_type": key_type, "key_id": key_id})
    return rows


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


def _latency_ms(started_at_utc: str, ended_at_utc: str) -> float:
    try:
        start = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
        end = datetime.fromisoformat(ended_at_utc.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max(0.0, (end - start).total_seconds() * 1000.0)


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _utc_now() -> str:
    # Canonical envelope contract expects UTC RFC3339 with microseconds and trailing Z.
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Decision Fabric runtime worker")
    parser.add_argument("--profile", required=True, help="Path to platform profile YAML")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    worker = DecisionFabricWorker(load_worker_config(Path(args.profile)))
    if args.once:
        processed = worker.run_once()
        logger.info("DF worker processed=%s", processed)
        return
    worker.run_forever()


if __name__ == "__main__":
    main()
