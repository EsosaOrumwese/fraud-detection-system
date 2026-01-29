"""IG admission spine."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ClassMap, PolicyRev, SchemaPolicy, WiringProfile
from fraud_detection.event_bus import EbRef, EventBusPublisher, FileEventBusPublisher
from .errors import IngestionError, reason_code
from .governance import GovernanceEmitter
from .health import HealthProbe, HealthState
from .ids import dedupe_key, quarantine_id_from, receipt_id_from
from .index import AdmissionIndex
from .metrics import MetricsRecorder
from .models import AdmissionDecision, Receipt, QuarantineRecord
from .ops_index import OpsIndex
from .partitioning import PartitionProfile, PartitioningProfiles
from .policy_digest import compute_policy_digest
from .rate_limit import RateLimiter
from .receipts import ReceiptWriter
from .security import authorize
from .schema import SchemaEnforcer
from .schemas import SchemaRegistry
from .store import ObjectStore, build_object_store

logger = logging.getLogger(__name__)


@dataclass
class IngestionGate:
    wiring: WiringProfile
    policy: SchemaPolicy
    class_map: ClassMap
    policy_rev: PolicyRev
    partitioning: PartitioningProfiles
    schema_enforcer: SchemaEnforcer
    contract_registry: SchemaRegistry
    receipt_writer: ReceiptWriter
    admission_index: AdmissionIndex
    ops_index: OpsIndex
    bus: EventBusPublisher
    store: ObjectStore
    health: HealthProbe
    metrics: MetricsRecorder
    governance: GovernanceEmitter
    auth_mode: str
    auth_allowlist: list[str]
    api_key_header: str
    push_limiter: RateLimiter

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
        auth_allowlist = list(wiring.auth_allowlist or [])
        return cls(
            wiring=wiring,
            policy=policy,
            class_map=class_map,
            policy_rev=policy_rev,
            partitioning=partitioning,
            schema_enforcer=schema_enforcer,
            contract_registry=contract_registry,
            receipt_writer=receipt_writer,
            admission_index=admission_index,
            ops_index=ops_index,
            bus=bus,
            store=store,
            health=health,
            metrics=metrics,
            governance=governance,
            auth_mode=wiring.auth_mode,
            auth_allowlist=auth_allowlist,
            api_key_header=wiring.api_key_header,
            push_limiter=RateLimiter(wiring.push_rate_limit_per_minute),
        )

    def admit_push(self, envelope: dict[str, Any]) -> Receipt:
        logger.info("IG admit_push start event_id=%s event_type=%s", envelope.get("event_id"), envelope.get("event_type"))
        decision, receipt = self._admit_event(envelope)
        if decision.decision == "QUARANTINE":
            raise RuntimeError("QUARANTINED")
        return receipt

    def admit_push_with_decision(self, envelope: dict[str, Any]) -> tuple[AdmissionDecision, Receipt]:
        logger.info("IG admit_push(decision) event_id=%s event_type=%s", envelope.get("event_id"), envelope.get("event_type"))
        decision, receipt = self._admit_event(envelope)
        return decision, receipt

    def _admit_event(
        self,
        envelope: dict[str, Any],
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
            eb_ref = _normalize_eb_ref(existing.get("eb_ref"))
            decision = AdmissionDecision(
                decision="DUPLICATE",
                reason_codes=["DUPLICATE"],
                eb_ref=eb_ref,
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
            self.health.record_publish_failure()
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
            eb_ref=_eb_ref_payload(eb_ref),
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


def _eb_ref_payload(eb_ref: EbRef) -> dict[str, Any]:
    payload = {
        "topic": eb_ref.topic,
        "partition": eb_ref.partition,
        "offset": eb_ref.offset,
        "offset_kind": eb_ref.offset_kind,
    }
    if eb_ref.published_at_utc:
        payload["published_at_utc"] = eb_ref.published_at_utc
    return payload


def _normalize_eb_ref(eb_ref: dict[str, Any] | None) -> dict[str, Any] | None:
    if not eb_ref:
        return None
    if "offset_kind" not in eb_ref:
        eb_ref = dict(eb_ref)
        eb_ref["offset_kind"] = "file_line"
    if "offset" in eb_ref and eb_ref["offset"] is not None:
        eb_ref = dict(eb_ref)
        eb_ref["offset"] = str(eb_ref["offset"])
    return eb_ref
