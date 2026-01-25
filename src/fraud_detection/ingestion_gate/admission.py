"""IG admission spine."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .catalogue import OutputCatalogue
from .config import ClassMap, PolicyRev, SchemaPolicy, WiringProfile
from .engine_pull import EnginePuller
from .event_bus import EbRef, EventBusPublisher, FileEventBusPublisher
from .errors import IngestionError, reason_code
from .gates import GateMap
from .governance import GovernanceEmitter
from .health import HealthProbe, HealthState
from .ids import dedupe_key, quarantine_id_from, receipt_id_from
from .index import AdmissionIndex
from .metrics import MetricsRecorder
from .models import AdmissionDecision, Receipt, QuarantineRecord
from .ops_index import OpsIndex
from .partitioning import PartitionProfile, PartitioningProfiles
from .policy_digest import compute_policy_digest
from .pull_state import PullRunStore
from .rate_limit import RateLimiter
from .retry import with_retry
from .receipts import ReceiptWriter
from .scopes import is_instance_scope
from .security import authorize
from .schema import SchemaEnforcer
from .schemas import SchemaRegistry
from .store import ObjectStore, build_object_store

try:  # optional import for local gate re-hash verification
    from fraud_detection.scenario_runner.evidence import GateMap as SrGateMap
    from fraud_detection.scenario_runner.evidence import GateVerifier
except Exception:  # pragma: no cover - optional dependency
    GateVerifier = None  # type: ignore[assignment]
    SrGateMap = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class IngestionGate:
    wiring: WiringProfile
    policy: SchemaPolicy
    class_map: ClassMap
    policy_rev: PolicyRev
    catalogue: OutputCatalogue
    gate_map: GateMap
    partitioning: PartitioningProfiles
    schema_enforcer: SchemaEnforcer
    contract_registry: SchemaRegistry
    receipt_writer: ReceiptWriter
    admission_index: AdmissionIndex
    ops_index: OpsIndex
    bus: EventBusPublisher
    store: ObjectStore
    gate_verifier: GateVerifier | None
    health: HealthProbe
    metrics: MetricsRecorder
    governance: GovernanceEmitter
    pull_store: PullRunStore
    auth_mode: str
    auth_allowlist: list[str]
    api_key_header: str
    ready_allowlist_run_ids: list[str]
    push_limiter: RateLimiter
    ready_limiter: RateLimiter

    @classmethod
    def build(cls, wiring: WiringProfile) -> "IngestionGate":
        policy = SchemaPolicy.load(Path(wiring.schema_policy_ref))
        class_map = ClassMap.load(Path(wiring.class_map_ref))
        digest = compute_policy_digest(
            [
                Path(wiring.schema_policy_ref),
                Path(wiring.class_map_ref),
                Path(wiring.partitioning_profiles_ref),
            ]
        )
        policy_rev = PolicyRev(policy_id="ig_policy", revision=wiring.policy_rev, content_digest=digest)
        catalogue = OutputCatalogue(Path(wiring.engine_catalogue_path))
        gate_map = GateMap(Path(wiring.gate_map_path))
        partitioning = PartitioningProfiles(wiring.partitioning_profiles_ref)
        schema_enforcer = SchemaEnforcer(
            envelope_registry=SchemaRegistry(Path(wiring.engine_contracts_root)),
            payload_registry_root=Path("."),
            policy=policy,
        )
        contract_registry = SchemaRegistry(Path(wiring.schema_root) / "ingestion_gate")
        store = build_object_store(
            wiring.object_store_root,
            s3_endpoint_url=wiring.object_store_endpoint,
            s3_region=wiring.object_store_region,
            s3_path_style=wiring.object_store_path_style,
        )
        gate_verifier = None
        if wiring.engine_root_path:
            if not GateVerifier or not SrGateMap:
                raise RuntimeError("GATE_VERIFIER_UNAVAILABLE")
            gate_verifier = GateVerifier(Path(wiring.engine_root_path), SrGateMap(Path(wiring.gate_map_path)))
        receipt_writer = ReceiptWriter(store)
        admission_index = AdmissionIndex(Path(wiring.admission_db_path))
        ops_index = OpsIndex(Path(wiring.admission_db_path))
        bus = _build_bus(wiring)
        health = HealthProbe(
            store,
            bus,
            ops_index,
            wiring.health_probe_interval_seconds,
            wiring.bus_publish_failure_threshold,
            wiring.store_read_failure_threshold,
        )
        metrics = MetricsRecorder(flush_interval_seconds=wiring.metrics_flush_seconds)
        governance = GovernanceEmitter(
            store=store,
            bus=bus,
            partitioning=partitioning,
            quarantine_spike_threshold=wiring.quarantine_spike_threshold,
            quarantine_spike_window_seconds=wiring.quarantine_spike_window_seconds,
            policy_id=policy_rev.policy_id,
        )
        governance.emit_policy_activation(
            {"policy_id": policy_rev.policy_id, "revision": policy_rev.revision, "content_digest": policy_rev.content_digest}
        )
        pull_store = PullRunStore(store)
        auth_allowlist = list(wiring.auth_allowlist or [])
        ready_allowlist = list(wiring.ready_allowlist_run_ids or [])
        return cls(
            wiring=wiring,
            policy=policy,
            class_map=class_map,
            policy_rev=policy_rev,
            catalogue=catalogue,
            gate_map=gate_map,
            partitioning=partitioning,
            schema_enforcer=schema_enforcer,
            contract_registry=contract_registry,
            receipt_writer=receipt_writer,
            admission_index=admission_index,
            ops_index=ops_index,
            bus=bus,
            store=store,
            gate_verifier=gate_verifier,
            health=health,
            metrics=metrics,
            governance=governance,
            pull_store=pull_store,
            auth_mode=wiring.auth_mode,
            auth_allowlist=auth_allowlist,
            api_key_header=wiring.api_key_header,
            ready_allowlist_run_ids=ready_allowlist,
            push_limiter=RateLimiter(wiring.push_rate_limit_per_minute),
            ready_limiter=RateLimiter(wiring.ready_rate_limit_per_minute),
        )

    def admit_push(self, envelope: dict[str, Any]) -> Receipt:
        logger.info("IG admit_push start event_id=%s event_type=%s", envelope.get("event_id"), envelope.get("event_type"))
        decision, receipt = self._admit_event(envelope, output_id=None, run_facts=None)
        if decision.decision == "QUARANTINE":
            raise RuntimeError("QUARANTINED")
        return receipt

    def admit_push_with_decision(self, envelope: dict[str, Any]) -> tuple[AdmissionDecision, Receipt]:
        logger.info("IG admit_push(decision) event_id=%s event_type=%s", envelope.get("event_id"), envelope.get("event_type"))
        decision, receipt = self._admit_event(envelope, output_id=None, run_facts=None)
        return decision, receipt

    def admit_pull(self, run_facts_view_path: Path) -> list[Receipt]:
        logger.info("IG admit_pull start run_facts_view=%s", run_facts_view_path)
        receipts: list[Receipt] = []
        run_facts = _load_json(run_facts_view_path)
        puller = EnginePuller(run_facts_view_path, self.catalogue, run_facts)
        for envelope in puller.iter_events():
            decision, receipt = self._admit_event(
                envelope,
                output_id=envelope["event_type"],
                run_facts=run_facts,
            )
            if decision.decision != "QUARANTINE":
                receipts.append(receipt)
        return receipts

    def admit_pull_with_state(
        self,
        run_facts_ref: str,
        *,
        run_id: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        self._enforce_health()
        run_facts = self._load_run_facts_by_ref(run_facts_ref)
        run_facts_path = None
        if not run_facts_ref.startswith("s3://"):
            run_facts_path = self._resolve_run_facts_path(run_facts_ref)
        run_id = run_id or run_facts.get("pins", {}).get("run_id") or run_facts.get("run_id")
        if not run_id:
            raise IngestionError("RUN_ID_MISSING")

        started_at = datetime.now(tz=timezone.utc)
        budget_seconds = self.wiring.pull_time_budget_seconds
        budget_start = time.monotonic()
        budget_deadline = None
        if budget_seconds and budget_seconds > 0:
            budget_deadline = budget_start + budget_seconds

        def budget_exceeded() -> bool:
            return budget_deadline is not None and time.monotonic() >= budget_deadline

        def mark_budget_exceeded(output_id: str, shard_id: int | None = None) -> None:
            elapsed = time.monotonic() - budget_start
            entry: dict[str, Any] = {"output_id": output_id, "reason_code": "TIME_BUDGET_EXCEEDED"}
            event_payload: dict[str, Any] = {
                "event_kind": "OUTPUT_FAILED",
                "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                "run_id": run_id,
                "message_id": message_id,
                "output_id": output_id,
                "reason_code": "TIME_BUDGET_EXCEEDED",
                "elapsed_seconds": round(elapsed, 3),
            }
            if shard_id is not None:
                entry["shard_id"] = shard_id
                event_payload["shard_id"] = shard_id
            status["outputs_failed"].append(entry)
            self.pull_store.append_event(run_id, event_payload)
            logger.warning(
                "IG pull time budget exceeded run_id=%s output_id=%s elapsed=%.2fs",
                run_id,
                output_id,
                elapsed,
            )
        output_ids = EnginePuller(
            run_facts_path,
            self.catalogue,
            run_facts,
            retry_attempts=self.wiring.store_read_retry_attempts,
            retry_backoff_seconds=self.wiring.store_read_retry_backoff_seconds,
            retry_max_seconds=self.wiring.store_read_retry_max_seconds,
        ).list_outputs()
        status = {
            "run_id": run_id,
            "message_id": message_id,
            "status": "IN_PROGRESS",
            "started_at_utc": started_at.isoformat(),
            "output_ids": output_ids,
            "counts": {"ADMIT": 0, "DUPLICATE": 0, "QUARANTINE": 0},
            "outputs_completed": [],
            "outputs_failed": [],
            "facts_view_ref": run_facts_ref,
        }
        self.pull_store.append_event(
            run_id,
            {
                "event_kind": "PULL_STARTED",
                "ts_utc": started_at.isoformat(),
                "run_id": run_id,
                "message_id": message_id,
            },
        )
        puller = EnginePuller(
            run_facts_path,
            self.catalogue,
            run_facts,
            retry_attempts=self.wiring.store_read_retry_attempts,
            retry_backoff_seconds=self.wiring.store_read_retry_backoff_seconds,
            retry_max_seconds=self.wiring.store_read_retry_max_seconds,
        )
        shard_mode = self.wiring.pull_shard_mode or "output_id"
        if shard_mode not in {"output_id", "locator_range"}:
            raise IngestionError("SHARD_MODE_UNSUPPORTED", shard_mode)
        shard_size = self.wiring.pull_shard_size
        stop_due_to_budget = False

        for output_id in output_ids:
            if budget_exceeded():
                mark_budget_exceeded(output_id)
                stop_due_to_budget = True
                break
            if shard_mode == "locator_range":
                if shard_size <= 0:
                    raise IngestionError("SHARD_SIZE_INVALID", str(shard_size))
                locator_paths = puller.list_locator_paths(output_id)
                if not locator_paths:
                    status["outputs_failed"].append({"output_id": output_id, "reason_code": "OUTPUT_LOCATOR_MISSING"})
                    self.pull_store.append_event(
                        run_id,
                        {
                            "event_kind": "OUTPUT_FAILED",
                            "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                            "run_id": run_id,
                            "message_id": message_id,
                            "output_id": output_id,
                            "reason_code": "OUTPUT_LOCATOR_MISSING",
                        },
                    )
                    continue
                shards = _chunk_list(locator_paths, shard_size)
                all_shards_done = True
                for shard_id in range(len(shards)):
                    if not self.pull_store.checkpoint_exists(run_id, output_id, shard_id=shard_id):
                        all_shards_done = False
                        break
                if all_shards_done:
                    logger.info("IG pull checkpoint skip run_id=%s output_id=%s shards=%s", run_id, output_id, len(shards))
                    status["outputs_completed"].append(output_id)
                    continue
                output_counts = {"ADMIT": 0, "DUPLICATE": 0, "QUARANTINE": 0}
                output_failed = False
                for shard_id, shard_paths in enumerate(shards):
                    if budget_exceeded():
                        mark_budget_exceeded(output_id, shard_id=shard_id)
                        stop_due_to_budget = True
                        output_failed = True
                        break
                    if self.pull_store.checkpoint_exists(run_id, output_id, shard_id=shard_id):
                        logger.info(
                            "IG pull shard checkpoint skip run_id=%s output_id=%s shard_id=%s",
                            run_id,
                            output_id,
                            shard_id,
                        )
                        continue
                    shard_counts = {"ADMIT": 0, "DUPLICATE": 0, "QUARANTINE": 0}
                    try:
                        for envelope in puller.iter_events_for_paths(output_id, shard_paths):
                            if budget_exceeded():
                                mark_budget_exceeded(output_id, shard_id=shard_id)
                                stop_due_to_budget = True
                                output_failed = True
                                break
                            decision, _receipt = self._admit_event(
                                envelope,
                                output_id=output_id,
                                run_facts=run_facts,
                            )
                            shard_counts[decision.decision] += 1
                            output_counts[decision.decision] += 1
                            status["counts"][decision.decision] += 1
                        if stop_due_to_budget:
                            break
                        checkpoint_payload = {
                            "run_id": run_id,
                            "output_id": output_id,
                            "shard_id": shard_id,
                            "shard_total": len(shards),
                            "path_count": len(shard_paths),
                            "status": "COMPLETED",
                            "counts": shard_counts,
                            "completed_at_utc": datetime.now(tz=timezone.utc).isoformat(),
                        }
                        self.pull_store.write_checkpoint(run_id, output_id, checkpoint_payload, shard_id=shard_id)
                        self.pull_store.append_event(
                            run_id,
                            {
                                "event_kind": "SHARD_COMPLETED",
                                "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                                "run_id": run_id,
                                "message_id": message_id,
                                "output_id": output_id,
                                "shard_id": shard_id,
                                "shard_total": len(shards),
                                "counts": shard_counts,
                            },
                        )
                    except Exception as exc:
                        code = reason_code(exc)
                        output_failed = True
                        status["outputs_failed"].append({"output_id": output_id, "shard_id": shard_id, "reason_code": code})
                        self.pull_store.append_event(
                            run_id,
                            {
                                "event_kind": "SHARD_FAILED",
                                "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                                "run_id": run_id,
                                "message_id": message_id,
                                "output_id": output_id,
                                "shard_id": shard_id,
                                "reason_code": code,
                            },
                        )
                if output_failed:
                    if stop_due_to_budget:
                        break
                    continue
                self.pull_store.append_event(
                    run_id,
                    {
                        "event_kind": "OUTPUT_COMPLETED",
                        "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                        "run_id": run_id,
                        "message_id": message_id,
                        "output_id": output_id,
                        "counts": output_counts,
                        "shard_total": len(shards),
                    },
                )
                status["outputs_completed"].append(output_id)
                continue

            if self.pull_store.checkpoint_exists(run_id, output_id):
                logger.info("IG pull checkpoint skip run_id=%s output_id=%s", run_id, output_id)
                status["outputs_completed"].append(output_id)
                continue
            output_counts = {"ADMIT": 0, "DUPLICATE": 0, "QUARANTINE": 0}
            try:
                for envelope in puller.iter_events(output_ids=[output_id]):
                    if budget_exceeded():
                        mark_budget_exceeded(output_id)
                        stop_due_to_budget = True
                        break
                    decision, _receipt = self._admit_event(
                        envelope,
                        output_id=output_id,
                        run_facts=run_facts,
                    )
                    output_counts[decision.decision] += 1
                    status["counts"][decision.decision] += 1
                if stop_due_to_budget:
                    break
                checkpoint_payload = {
                    "run_id": run_id,
                    "output_id": output_id,
                    "status": "COMPLETED",
                    "counts": output_counts,
                    "completed_at_utc": datetime.now(tz=timezone.utc).isoformat(),
                }
                self.pull_store.write_checkpoint(run_id, output_id, checkpoint_payload)
                self.pull_store.append_event(
                    run_id,
                    {
                        "event_kind": "OUTPUT_COMPLETED",
                        "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                        "run_id": run_id,
                        "message_id": message_id,
                        "output_id": output_id,
                        "counts": output_counts,
                    },
                )
                status["outputs_completed"].append(output_id)
            except Exception as exc:
                code = reason_code(exc)
                status["outputs_failed"].append({"output_id": output_id, "reason_code": code})
                self.pull_store.append_event(
                    run_id,
                    {
                        "event_kind": "OUTPUT_FAILED",
                        "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
                        "run_id": run_id,
                        "message_id": message_id,
                        "output_id": output_id,
                        "reason_code": code,
                    },
                )
            if stop_due_to_budget:
                break

        completed_at = datetime.now(tz=timezone.utc)
        status["completed_at_utc"] = completed_at.isoformat()
        if status["outputs_failed"]:
            status["status"] = "PARTIAL"
        else:
            status["status"] = "COMPLETED"
        status_ref = self.pull_store.write_status(run_id, status)
        status["status_ref"] = status_ref
        self.ops_index.record_pull_run(status, status_ref)
        self.governance.emit_pull_run_summary(
            {
                "run_id": run_id,
                "message_id": message_id,
                "status": status["status"],
                "counts": status["counts"],
                "output_ids": output_ids,
                "facts_view_ref": run_facts_ref,
                "started_at_utc": status["started_at_utc"],
                "completed_at_utc": status.get("completed_at_utc"),
            }
        )
        self.pull_store.append_event(
            run_id,
            {
                "event_kind": "PULL_COMPLETED",
                "ts_utc": completed_at.isoformat(),
                "run_id": run_id,
                "message_id": message_id,
                "status": status["status"],
            },
        )
        return status

    def _admit_event(
        self,
        envelope: dict[str, Any],
        output_id: str | None,
        run_facts: dict[str, Any] | None,
    ) -> tuple[AdmissionDecision, Receipt]:
        start = time.perf_counter()
        validate_started = time.perf_counter()
        try:
            self._enforce_health()
            self._validate_envelope(envelope)
            self._validate_class_pins(envelope)
            self.schema_enforcer.validate_payload(envelope["event_type"], envelope)
            self.metrics.record_latency("phase.validate_seconds", time.perf_counter() - validate_started)
            verify_started = time.perf_counter()
            if run_facts is None and self._requires_run_ready(envelope["event_type"]):
                self._ensure_run_ready(envelope)
            if output_id and run_facts:
                self._verify_required_gates(output_id, run_facts)
            self.metrics.record_latency("phase.verify_seconds", time.perf_counter() - verify_started)
        except IngestionError as exc:
            if exc.code == "IG_UNHEALTHY":
                raise
            return self._quarantine(envelope, exc, start)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("IG admission validation error")
            return self._quarantine(envelope, IngestionError("INTERNAL_ERROR"), start)
        logger.info(
            "IG validated event_id=%s event_type=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
        )

        dedupe = dedupe_key(envelope["event_id"], envelope["event_type"])
        dedupe_started = time.perf_counter()
        existing = self.admission_index.lookup(dedupe)
        self.metrics.record_latency("phase.dedupe_seconds", time.perf_counter() - dedupe_started)
        if existing:
            logger.info("IG duplicate event_id=%s event_type=%s", envelope["event_id"], envelope["event_type"])
            decision = AdmissionDecision(
                decision="DUPLICATE",
                reason_codes=["DUPLICATE"],
                eb_ref=existing.get("eb_ref"),
                evidence_refs=[{"kind": "receipt_ref", "ref": existing.get("receipt_ref")}]
                if existing.get("receipt_ref")
                else None,
            )
            receipt_started = time.perf_counter()
            receipt_payload = self._receipt_payload(envelope, decision, dedupe)
            receipt = Receipt(payload=receipt_payload)
            receipt_id = receipt_payload["receipt_id"]
            self.contract_registry.validate("ingestion_receipt.schema.yaml", receipt_payload)
            receipt_ref = self.receipt_writer.write_receipt(receipt_id, receipt_payload)
            self._record_ops_receipt(receipt_payload, receipt_ref)
            self.metrics.record_latency("phase.receipt_seconds", time.perf_counter() - receipt_started)
            self.metrics.record_decision("DUPLICATE")
            self.metrics.record_latency("admission_seconds", time.perf_counter() - start)
            self.metrics.flush_if_due(self._metrics_context(envelope))
            return decision, receipt

        try:
            partition_key, profile = self._partitioning(envelope)
            publish_started = time.perf_counter()
            eb_ref = self.bus.publish(profile.stream, partition_key, envelope)
            self.metrics.record_latency("phase.publish_seconds", time.perf_counter() - publish_started)
        except IngestionError as exc:
            return self._quarantine(envelope, exc, start)
        except Exception as exc:
            logger.exception("IG event bus publish error")
            self.health.record_publish_failure()
            return self._quarantine(envelope, IngestionError("EB_PUBLISH_FAILED"), start)
        self.health.record_publish_success()
        logger.info(
            "IG admitted event_id=%s event_type=%s topic=%s partition=%s offset=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
            eb_ref.topic,
            eb_ref.partition,
            eb_ref.offset,
        )
        decision = AdmissionDecision(
            decision="ADMIT",
            reason_codes=[],
            eb_ref={"topic": eb_ref.topic, "partition": eb_ref.partition, "offset": eb_ref.offset},
        )
        receipt_started = time.perf_counter()
        receipt_payload = self._receipt_payload(
            envelope,
            decision,
            dedupe,
            profile.profile_id,
            partition_key,
            eb_ref,
        )
        receipt = Receipt(payload=receipt_payload)
        receipt_id = receipt_payload["receipt_id"]
        self.contract_registry.validate("ingestion_receipt.schema.yaml", receipt_payload)
        receipt_ref = self.receipt_writer.write_receipt(receipt_id, receipt_payload)
        self.admission_index.record(dedupe, receipt_ref, decision.eb_ref)
        self._record_ops_receipt(receipt_payload, receipt_ref)
        self.metrics.record_latency("phase.receipt_seconds", time.perf_counter() - receipt_started)
        self.metrics.record_decision("ADMIT")
        self.metrics.record_latency("admission_seconds", time.perf_counter() - start)
        self.metrics.flush_if_due(self._metrics_context(envelope))
        return decision, receipt

    def _quarantine(
        self,
        envelope: dict[str, Any],
        exc: Exception,
        started_at: float,
    ) -> tuple[AdmissionDecision, Receipt]:
        code = reason_code(exc)
        logger.warning(
            "IG quarantine event_id=%s event_type=%s reason=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
            code,
        )
        event_id = envelope.get("event_id") or "unknown"
        quarantine_id = quarantine_id_from(event_id)
        receipt_started = time.perf_counter()
        quarantine_payload = {
            "quarantine_id": quarantine_id,
            "received_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "decision": "QUARANTINE",
            "reason_codes": [code],
            "manifest_fingerprint": envelope.get("manifest_fingerprint", "0" * 64),
            "pins": {
                "manifest_fingerprint": envelope.get("manifest_fingerprint", "0" * 64),
                "parameter_hash": envelope.get("parameter_hash"),
                "seed": envelope.get("seed"),
                "scenario_id": envelope.get("scenario_id"),
                "run_id": envelope.get("run_id"),
            },
            "policy_rev": {
                "policy_id": self.policy_rev.policy_id,
                "revision": self.policy_rev.revision,
            },
            "envelope": {k: envelope.get(k) for k in envelope if k != "payload"},
        }
        quarantine_payload["pins"] = _prune_none(quarantine_payload["pins"])
        if self.policy_rev.content_digest:
            quarantine_payload["policy_rev"]["content_digest"] = self.policy_rev.content_digest
        self.contract_registry.validate("quarantine_record.schema.yaml", quarantine_payload)
        quarantine_ref = self.receipt_writer.write_quarantine(quarantine_id, quarantine_payload)
        decision = AdmissionDecision(
            decision="QUARANTINE",
            reason_codes=[code],
            evidence_refs=[{"kind": "quarantine_record", "ref": quarantine_ref}],
        )
        dedupe = dedupe_key(event_id, envelope.get("event_type", "unknown"))
        receipt_payload = self._receipt_payload(envelope, decision, dedupe)
        receipt_id = receipt_payload["receipt_id"]
        self.contract_registry.validate("ingestion_receipt.schema.yaml", receipt_payload)
        receipt_ref = self.receipt_writer.write_receipt(receipt_id, receipt_payload)
        self._record_ops_quarantine(quarantine_payload, quarantine_ref, event_id)
        self._record_ops_receipt(receipt_payload, receipt_ref)
        self.metrics.record_latency("phase.receipt_seconds", time.perf_counter() - receipt_started)
        self.metrics.record_decision("QUARANTINE", code)
        self.metrics.record_latency("admission_seconds", time.perf_counter() - started_at)
        self.governance.emit_quarantine_spike(self.metrics.counters.get("decision.QUARANTINE", 0))
        self.metrics.flush_if_due(self._metrics_context(envelope))
        receipt = Receipt(payload=receipt_payload)
        return decision, receipt

    def _metrics_context(self, envelope: dict[str, Any]) -> dict[str, Any]:
        pins = {
            "manifest_fingerprint": envelope.get("manifest_fingerprint"),
            "parameter_hash": envelope.get("parameter_hash"),
            "seed": envelope.get("seed"),
            "scenario_id": envelope.get("scenario_id"),
            "run_id": envelope.get("run_id"),
        }
        return {
            "policy_rev": {
                "policy_id": self.policy_rev.policy_id,
                "revision": self.policy_rev.revision,
                "content_digest": self.policy_rev.content_digest,
            },
            "event_type": envelope.get("event_type"),
            "pins": _prune_none(pins),
        }

    def _validate_envelope(self, envelope: dict[str, Any]) -> None:
        self.schema_enforcer.validate_envelope(envelope)

    def _validate_class_pins(self, envelope: dict[str, Any]) -> None:
        required = self.class_map.required_pins_for(envelope["event_type"])
        missing = [pin for pin in required if envelope.get(pin) in (None, "")]
        if missing:
            raise IngestionError("PINS_MISSING", ",".join(missing))

    def _requires_run_ready(self, event_type: str) -> bool:
        required = set(self.class_map.required_pins_for(event_type))
        run_scoped = {"run_id", "scenario_id", "parameter_hash", "seed"}
        return bool(required & run_scoped)

    def _ensure_run_ready(self, envelope: dict[str, Any]) -> None:
        run_id = envelope.get("run_id")
        if not run_id:
            raise IngestionError("RUN_ID_MISSING")
        status_path = f"{self.wiring.sr_ledger_prefix}/run_status/{run_id}.json"
        if not self.store.exists(status_path):
            raise IngestionError("RUN_STATUS_MISSING", run_id)
        status = self.store.read_json(status_path)
        if status.get("state") != "READY":
            raise IngestionError("RUN_NOT_READY", status.get("state"))
        facts_ref = status.get("facts_view_ref") or f"{self.wiring.sr_ledger_prefix}/run_facts_view/{run_id}.json"
        if not self.store.exists(facts_ref):
            raise IngestionError("RUN_FACTS_MISSING", run_id)
        run_facts = self._load_run_facts_by_ref(facts_ref)
        self._verify_run_pins(envelope, run_facts)
        logger.info("IG run joinability ok run_id=%s facts_ref=%s", run_id, facts_ref)

    def resolve_run_facts_ref(self, run_id: str) -> str:
        status_path = f"{self.wiring.sr_ledger_prefix}/run_status/{run_id}.json"
        if not self.store.exists(status_path):
            raise IngestionError("RUN_STATUS_MISSING", run_id)
        status = self.store.read_json(status_path)
        if status.get("state") != "READY":
            raise IngestionError("RUN_NOT_READY", status.get("state"))
        facts_ref = status.get("facts_view_ref") or f"{self.wiring.sr_ledger_prefix}/run_facts_view/{run_id}.json"
        if not self.store.exists(facts_ref):
            raise IngestionError("RUN_FACTS_MISSING", run_id)
        return facts_ref

    def _resolve_run_facts_path(self, run_facts_ref: str) -> Path:
        if run_facts_ref.startswith("s3://"):
            raise IngestionError("RUN_FACTS_REMOTE")
        candidate = Path(run_facts_ref)
        if candidate.is_absolute():
            return candidate
        store_root = getattr(self.store, "root", None)
        if store_root is None:
            raise IngestionError("RUN_FACTS_UNSUPPORTED")
        return Path(store_root) / run_facts_ref

    def _load_run_facts_by_ref(self, run_facts_ref: str) -> dict[str, Any]:
        def _read() -> dict[str, Any]:
            if run_facts_ref.startswith("s3://"):
                return _load_json_from_s3(
                    run_facts_ref,
                    endpoint_url=self.wiring.object_store_endpoint,
                    region=self.wiring.object_store_region,
                    path_style=self.wiring.object_store_path_style,
                )
            return self.store.read_json(run_facts_ref)

        def _on_retry(attempt: int, delay: float, exc: Exception) -> None:
            logger.warning(
                "IG run_facts read retry attempt=%s delay=%.2fs reason=%s",
                attempt,
                delay,
                str(exc)[:160],
            )

        try:
            payload = with_retry(
                _read,
                attempts=self.wiring.store_read_retry_attempts,
                base_delay_seconds=self.wiring.store_read_retry_backoff_seconds,
                max_delay_seconds=self.wiring.store_read_retry_max_seconds,
                on_retry=_on_retry,
            )
            self.health.record_read_success()
            return payload
        except Exception as exc:
            self.health.record_read_failure()
            raise IngestionError("RUN_FACTS_UNREADABLE", str(exc)[:256]) from exc

    def _enforce_health(self) -> None:
        result = self.health.check()
        if result.state == HealthState.RED:
            raise IngestionError("IG_UNHEALTHY", ",".join(result.reasons))
        if result.state == HealthState.AMBER:
            logger.warning("IG health amber reasons=%s", ",".join(result.reasons))
            if self.wiring.health_deny_on_amber:
                raise IngestionError("IG_UNHEALTHY", "AMBER")
            if self.wiring.health_amber_sleep_seconds > 0:
                time.sleep(self.wiring.health_amber_sleep_seconds)

    def authorize_request(self, token: str | None) -> None:
        allowed, reason = authorize(self.auth_mode, token, self.auth_allowlist)
        if not allowed:
            raise IngestionError(reason or "UNAUTHORIZED")

    def enforce_push_rate_limit(self) -> None:
        if not self.push_limiter.allow():
            raise IngestionError("RATE_LIMITED")

    def enforce_ready_rate_limit(self) -> None:
        if not self.ready_limiter.allow():
            raise IngestionError("RATE_LIMITED")

    def enforce_ready_allowlist(self, run_id: str) -> None:
        if self.ready_allowlist_run_ids and run_id not in self.ready_allowlist_run_ids:
            raise IngestionError("RUN_NOT_ALLOWED", run_id)

    def _record_ops_receipt(self, payload: dict[str, Any], receipt_ref: str) -> None:
        try:
            self.ops_index.record_receipt(payload, receipt_ref)
        except Exception:
            logger.exception("IG ops index receipt write failed")

    def _record_ops_quarantine(self, payload: dict[str, Any], quarantine_ref: str, event_id: str) -> None:
        try:
            self.ops_index.record_quarantine(payload, quarantine_ref, event_id)
        except Exception:
            logger.exception("IG ops index quarantine write failed")

    def _verify_run_pins(self, envelope: dict[str, Any], run_facts: dict[str, Any]) -> None:
        pins = run_facts.get("pins", {})
        for key in ("manifest_fingerprint", "parameter_hash", "seed", "scenario_id", "run_id"):
            value = envelope.get(key)
            if value is None:
                continue
            if pins.get(key) != value:
                raise IngestionError("RUN_PINS_MISMATCH", key)

    def _verify_required_gates(self, output_id: str, run_facts: dict[str, Any]) -> None:
        try:
            entry = self.catalogue.get(output_id)
        except KeyError as exc:
            raise IngestionError("OUTPUT_UNKNOWN", output_id) from exc
        required_gates = entry.read_requires_gates or self.gate_map.required_gate_set([output_id])
        gate_receipts = run_facts.get("gate_receipts", [])
        gate_status = {receipt["gate_id"]: receipt["status"] for receipt in gate_receipts}
        missing = [gate_id for gate_id in required_gates if gate_status.get(gate_id) != "PASS"]
        if missing:
            raise IngestionError("GATE_MISSING", ",".join(missing))
        if self.gate_verifier:
            pins = run_facts.get("pins", {})
            for gate_id in required_gates:
                result = self.gate_verifier.verify(gate_id, pins)
                if result.receipt is None or result.missing:
                    raise IngestionError("GATE_VERIFY_MISSING", gate_id)
                if result.conflict or result.receipt.status.value != "PASS":
                    raise IngestionError("GATE_VERIFY_CONFLICT", gate_id)
        logger.info("IG gate verification ok output_id=%s gates=%s", output_id, ",".join(required_gates))
        if is_instance_scope(entry.scope):
            locator = _locator_for(output_id, run_facts.get("locators", []))
            if not _has_instance_receipt(output_id, run_facts.get("instance_receipts", []), locator):
                raise IngestionError("INSTANCE_PROOF_MISSING", output_id)
            logger.info("IG instance proof ok output_id=%s", output_id)

    def _partitioning(self, envelope: dict[str, Any]) -> tuple[str, PartitionProfile]:
        class_name = self.class_map.class_for(envelope["event_type"])
        if class_name == "control":
            profile_id = "ig.partitioning.v0.control"
        elif class_name == "audit":
            profile_id = "ig.partitioning.v0.audit"
        else:
            profile_id = self.wiring.partitioning_profile_id
        profile = self.partitioning.get(profile_id)
        partition_key = self.partitioning.derive_key(profile_id, envelope)
        return partition_key, profile

    def _receipt_payload(
        self,
        envelope: dict[str, Any],
        decision: AdmissionDecision,
        dedupe: str,
        profile_id: str | None = None,
        partition_key: str | None = None,
        eb_ref: EbRef | None = None,
    ) -> dict[str, Any]:
        receipt_id = receipt_id_from(envelope["event_id"], decision.decision)
        payload: dict[str, Any] = {
            "receipt_id": receipt_id,
            "decision": decision.decision,
            "event_id": envelope["event_id"],
            "event_type": envelope["event_type"],
            "ts_utc": envelope["ts_utc"],
            "manifest_fingerprint": envelope["manifest_fingerprint"],
            "policy_rev": {
                "policy_id": self.policy_rev.policy_id,
                "revision": self.policy_rev.revision,
            },
            "dedupe_key": dedupe,
            "pins": {
                "manifest_fingerprint": envelope["manifest_fingerprint"],
                "parameter_hash": envelope.get("parameter_hash"),
                "seed": envelope.get("seed"),
                "scenario_id": envelope.get("scenario_id"),
                "run_id": envelope.get("run_id"),
            },
        }
        payload["pins"] = _prune_none(payload["pins"])
        if envelope.get("schema_version"):
            payload["schema_version"] = envelope["schema_version"]
        if envelope.get("producer"):
            payload["producer"] = envelope["producer"]
        if self.policy_rev.content_digest:
            payload["policy_rev"]["content_digest"] = self.policy_rev.content_digest
        if profile_id:
            payload["partitioning_profile_id"] = profile_id
        if partition_key:
            payload["partition_key"] = partition_key
        if decision.eb_ref:
            payload["eb_ref"] = decision.eb_ref
        if decision.reason_codes:
            payload["reason_codes"] = decision.reason_codes
        if decision.evidence_refs:
            payload["evidence_refs"] = decision.evidence_refs
        return payload


def _build_bus(wiring: WiringProfile) -> EventBusPublisher:
    if wiring.event_bus_kind == "file":
        bus_path = wiring.event_bus_path or "runs/local_bus"
        return FileEventBusPublisher(Path(bus_path))
    raise RuntimeError("EB_KIND_UNSUPPORTED")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_from_s3(
    ref: str,
    *,
    endpoint_url: str | None,
    region: str | None,
    path_style: bool | None,
) -> dict[str, Any]:
    from urllib.parse import urlparse

    import boto3
    from botocore.config import Config

    parsed = urlparse(ref)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError("S3_REF_INVALID")
    config = None
    if path_style:
        config = Config(s3={"addressing_style": "path"})
    client = boto3.client("s3", region_name=region, endpoint_url=endpoint_url, config=config)
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def _locator_for(output_id: str, locators: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for locator in locators:
        if locator.get("output_id") == output_id:
            return locator
    return None


def _has_instance_receipt(
    output_id: str,
    receipts: Iterable[dict[str, Any]],
    locator: dict[str, Any] | None,
) -> bool:
    for receipt in receipts:
        if receipt.get("output_id") != output_id:
            continue
        if receipt.get("status") != "PASS":
            continue
        target_ref = receipt.get("target_ref", {})
        if locator and target_ref.get("path") and locator.get("path") != target_ref.get("path"):
            continue
        if receipt.get("target_digest"):
            return True
    return False


def _prune_none(payload: dict[str, Any]) -> dict[str, Any]:
    pruned: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, dict):
            pruned[key] = _prune_none(value)
        else:
            pruned[key] = value
    return pruned


def _chunk_list(items: list[str], size: int) -> list[list[str]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]
