"""IG admission spine."""

from __future__ import annotations

import logging
import time
import hashlib
import json
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
from .pg_index import PostgresAdmissionIndex, PostgresOpsIndex, is_postgres_dsn
from .partitioning import PartitionProfile, PartitioningProfiles
from .policy_digest import compute_policy_digest
from .rate_limit import RateLimiter
from .receipts import ReceiptWriter
from .security import AuthContext, authorize
from .schema import SchemaEnforcer
from .schemas import SchemaRegistry
from .store import ObjectStore, S3ObjectStore, build_object_store
from ..platform_runtime import platform_run_prefix, resolve_platform_run_id
from ..platform_provenance import runtime_provenance
from ..platform_governance.anomaly_taxonomy import classify_anomaly
from ..platform_governance import emit_platform_governance_event

logger = logging.getLogger(__name__)
narrative_logger = logging.getLogger("fraud_detection.platform_narrative")
eb_logger = logging.getLogger("fraud_detection.event_bus")

_RTDL_EXPECTED_CLASS_BY_EVENT: dict[str, str] = {
    "decision_response": "rtdl_decision",
    "action_intent": "rtdl_action_intent",
    "action_outcome": "rtdl_action_outcome",
}
_RTDL_REQUIRED_PINS: set[str] = {
    "platform_run_id",
    "scenario_run_id",
    "manifest_fingerprint",
    "parameter_hash",
    "seed",
    "scenario_id",
}


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
    auth_service_token_secrets: list[str]
    api_key_header: str
    push_limiter: RateLimiter

    @classmethod
    def build(cls, wiring: WiringProfile) -> "IngestionGate":
        policy = SchemaPolicy.load(Path(wiring.schema_policy_ref))
        class_map = ClassMap.load(Path(wiring.class_map_ref))
        _validate_rtdl_policy_alignment(policy, class_map)
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
        run_prefix = platform_run_prefix(create_if_missing=True)
        if not run_prefix:
            raise RuntimeError("PLATFORM_RUN_ID required to build IG run-scoped artifacts.")
        receipt_writer = ReceiptWriter(store, prefix=f"{run_prefix}/ig")
        admission_index, ops_index = _build_indices(wiring.admission_db_path)
        bus = _build_bus(wiring)
        bus_probe_streams = _bus_probe_streams(wiring, partitioning, class_map)
        health = HealthProbe(
            store,
            bus,
            ops_index,
            wiring.health_probe_interval_seconds,
            wiring.bus_publish_failure_threshold,
            wiring.store_read_failure_threshold,
            health_path=f"{run_prefix}/ig/health/last_probe.json",
            bus_probe_mode=wiring.health_bus_probe_mode,
            bus_probe_streams=bus_probe_streams,
        )
        metrics = MetricsRecorder(flush_interval_seconds=wiring.metrics_flush_seconds)
        governance = GovernanceEmitter(
            store=store,
            bus=bus,
            partitioning=partitioning,
            quarantine_spike_threshold=wiring.quarantine_spike_threshold,
            quarantine_spike_window_seconds=wiring.quarantine_spike_window_seconds,
            policy_id=policy_rev.policy_id,
            prefix=run_prefix,
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
            auth_service_token_secrets=list(wiring.service_token_secrets or []),
            api_key_header=wiring.api_key_header,
            push_limiter=RateLimiter(wiring.push_rate_limit_per_minute),
        )

    def admit_push(self, envelope: dict[str, Any], *, auth_context: AuthContext | None = None) -> Receipt:
        logger.info("IG admit_push start event_id=%s event_type=%s", envelope.get("event_id"), envelope.get("event_type"))
        decision, receipt = self._admit_event(envelope, auth_context=auth_context)
        if decision.decision == "QUARANTINE":
            raise RuntimeError("QUARANTINED")
        return receipt

    def admit_push_with_decision(
        self,
        envelope: dict[str, Any],
        *,
        auth_context: AuthContext | None = None,
    ) -> tuple[AdmissionDecision, Receipt]:
        logger.info(
            "IG admit_push(decision) event_id=%s event_type=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
        )
        decision, receipt = self._admit_event(envelope, auth_context=auth_context)
        return decision, receipt

    def _admit_event(
        self,
        envelope: dict[str, Any],
        *,
        auth_context: AuthContext | None = None,
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
            return self._quarantine(envelope, exc, start, auth_context=auth_context)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("IG admission validation error")
            return self._quarantine(envelope, IngestionError("INTERNAL_ERROR"), start, auth_context=auth_context)
        logger.info(
            "IG validated event_id=%s event_type=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
        )

        event_type = envelope["event_type"]
        event_id = envelope["event_id"]
        event_class = self.class_map.class_for(event_type)
        platform_run_id = envelope.get("platform_run_id")
        scenario_run_id = envelope.get("scenario_run_id") or envelope.get("run_id")
        payload_hash, payload_hash_hex = _payload_hash(envelope)
        dedupe = dedupe_key(platform_run_id or "", event_class, event_id)

        def _handle_existing(existing_row: dict[str, Any]) -> tuple[AdmissionDecision, Receipt]:
            existing_hash = existing_row.get("payload_hash")
            if existing_hash and existing_hash != payload_hash_hex:
                return self._quarantine(envelope, IngestionError("PAYLOAD_HASH_MISMATCH"), start, auth_context=auth_context)
            state = existing_row.get("state") or ("ADMITTED" if existing_row.get("eb_ref") else None)
            if state in {"PUBLISH_IN_FLIGHT", "PUBLISH_AMBIGUOUS"}:
                return self._quarantine(envelope, IngestionError(state), start, auth_context=auth_context)
            if state not in {"ADMITTED", None}:
                return self._quarantine(envelope, IngestionError("ADMISSION_STATE_INVALID", state), start, auth_context=auth_context)
            logger.info("IG duplicate event_id=%s event_type=%s", event_id, event_type)
            eb_ref = _normalize_eb_ref(existing_row.get("eb_ref"))
            admitted_at_utc = existing_row.get("admitted_at_utc") or (
                eb_ref.get("published_at_utc") if eb_ref else None
            ) or datetime.now(tz=timezone.utc).isoformat()
            decision = AdmissionDecision(
                decision="DUPLICATE",
                reason_codes=["DUPLICATE"],
                eb_ref=eb_ref,
                evidence_refs=[{"kind": "receipt_ref", "ref": existing_row.get("receipt_ref")}]
                if existing_row.get("receipt_ref")
                else None,
            )
            receipt_started = time.perf_counter()
            receipt_payload = self._receipt_payload(
                envelope,
                decision,
                dedupe,
                event_class=event_class,
                platform_run_id=platform_run_id,
                scenario_run_id=scenario_run_id,
                payload_hash=payload_hash,
                admitted_at_utc=admitted_at_utc,
                auth_context=auth_context,
            )
            receipt = Receipt(payload=receipt_payload)
            receipt_id = receipt_payload["receipt_id"]
            self.contract_registry.validate("ingestion_receipt.schema.yaml", receipt_payload)
            receipt_ref = self.receipt_writer.write_receipt(
                receipt_id,
                receipt_payload,
                prefix=self._receipt_prefix(envelope),
            )
            if not existing_row.get("receipt_ref") or existing_row.get("receipt_write_failed"):
                self.admission_index.record_receipt(dedupe, receipt_ref)
            self._record_ops_receipt(receipt_payload, receipt_ref)
            self.metrics.record_latency("phase.receipt_seconds", time.perf_counter() - receipt_started)
            self.metrics.record_decision("DUPLICATE")
            self.metrics.record_latency("admission_seconds", time.perf_counter() - start)
            self.metrics.flush_if_due(self._metrics_context(envelope))
            return decision, receipt

        dedupe_started = time.perf_counter()
        existing = self.admission_index.lookup(dedupe)
        self.metrics.record_latency("phase.dedupe_seconds", time.perf_counter() - dedupe_started)
        if existing:
            return _handle_existing(existing)

        try:
            partition_key, profile = self._partitioning(envelope)
        except IngestionError as exc:
            return self._quarantine(envelope, exc, start, auth_context=auth_context)

        inserted = self.admission_index.record_in_flight(
            dedupe,
            platform_run_id=platform_run_id or "",
            event_class=event_class,
            event_id=event_id,
            payload_hash=payload_hash_hex,
        )
        if not inserted:
            existing = self.admission_index.lookup(dedupe)
            if existing:
                return _handle_existing(existing)
        try:
            publish_started = time.perf_counter()
            eb_ref = self.bus.publish(profile.stream, partition_key, envelope)
            self.metrics.record_latency("phase.publish_seconds", time.perf_counter() - publish_started)
        except Exception:
            logger.exception("IG event bus publish error")
            self.health.record_publish_failure()
            self.admission_index.record_ambiguous(dedupe, payload_hash_hex)
            return self._quarantine(envelope, IngestionError("PUBLISH_AMBIGUOUS"), start, auth_context=auth_context)
        self.health.record_publish_success()
        admitted_at_utc = datetime.now(tz=timezone.utc).isoformat()
        self.admission_index.record_admitted(dedupe, eb_ref=_eb_ref_payload(eb_ref), admitted_at_utc=admitted_at_utc, payload_hash=payload_hash_hex)
        logger.info(
            "IG admitted event_id=%s event_type=%s topic=%s partition=%s offset=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
            eb_ref.topic,
            eb_ref.partition,
            eb_ref.offset,
        )
        narrative_logger.info(
            "IG published to EB event_id=%s topic=%s partition=%s offset=%s",
            envelope.get("event_id"),
            eb_ref.topic,
            eb_ref.partition,
            eb_ref.offset,
        )
        eb_logger.info(
            "EB publish event_id=%s topic=%s partition=%s offset=%s",
            envelope.get("event_id"),
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
            event_class=event_class,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            payload_hash=payload_hash,
            admitted_at_utc=admitted_at_utc,
            profile_id=profile.profile_id,
            partition_key=partition_key,
            eb_ref=eb_ref,
            auth_context=auth_context,
        )
        receipt = Receipt(payload=receipt_payload)
        receipt_id = receipt_payload["receipt_id"]
        self.contract_registry.validate("ingestion_receipt.schema.yaml", receipt_payload)
        try:
            receipt_ref = self.receipt_writer.write_receipt(
                receipt_id,
                receipt_payload,
                prefix=self._receipt_prefix(envelope),
            )
        except Exception:
            self.admission_index.mark_receipt_failed(dedupe)
            logger.exception("IG receipt write failed after publish event_id=%s", event_id)
            raise
        self.admission_index.record_receipt(dedupe, receipt_ref)
        self._record_ops_receipt(receipt_payload, receipt_ref)
        logger.info(
            "IG receipt stored receipt_id=%s receipt_ref=%s eb_ref=%s",
            receipt_id,
            receipt_ref,
            decision.eb_ref,
        )
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
        *,
        auth_context: AuthContext | None = None,
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
                "platform_run_id": envelope.get("platform_run_id"),
                "scenario_run_id": envelope.get("scenario_run_id"),
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
        if auth_context:
            quarantine_payload["actor"] = {
                "actor_id": auth_context.actor_id,
                "source_type": auth_context.source_type,
                "auth_mode": auth_context.auth_mode,
                "principal": auth_context.principal,
            }
        provenance = runtime_provenance(
            component="ingestion_gate",
            environment=self.wiring.profile_id,
            config_revision=self.policy_rev.revision,
            run_config_digest=self.policy_rev.content_digest,
        )
        quarantine_payload["service_release_id"] = provenance["service_release_id"]
        quarantine_payload["environment"] = provenance["environment"]
        quarantine_payload["provenance"] = provenance
        quarantine_payload["pins"] = _prune_none(quarantine_payload["pins"])
        if self.policy_rev.content_digest:
            quarantine_payload["policy_rev"]["content_digest"] = self.policy_rev.content_digest
        self.contract_registry.validate("quarantine_record.schema.yaml", quarantine_payload)
        quarantine_ref = self.receipt_writer.write_quarantine(
            quarantine_id,
            quarantine_payload,
            prefix=self._receipt_prefix(envelope),
        )
        decision = AdmissionDecision(
            decision="QUARANTINE",
            reason_codes=[code],
            evidence_refs=[{"kind": "quarantine_record", "ref": quarantine_ref}],
        )
        event_class = self.class_map.class_for(envelope.get("event_type", "unknown"))
        dedupe = dedupe_key(envelope.get("platform_run_id") or "", event_class, event_id)
        receipt_payload = self._receipt_payload(
            envelope,
            decision,
            dedupe,
            event_class=event_class,
            platform_run_id=envelope.get("platform_run_id"),
            scenario_run_id=envelope.get("scenario_run_id") or envelope.get("run_id"),
            auth_context=auth_context,
        )
        receipt_id = receipt_payload["receipt_id"]
        self.contract_registry.validate("ingestion_receipt.schema.yaml", receipt_payload)
        receipt_ref = self.receipt_writer.write_receipt(
            receipt_id,
            receipt_payload,
            prefix=self._receipt_prefix(envelope),
        )
        self._record_ops_quarantine(quarantine_payload, quarantine_ref, event_id)
        self._record_ops_receipt(receipt_payload, receipt_ref)
        self.metrics.record_latency("phase.receipt_seconds", time.perf_counter() - receipt_started)
        self.metrics.record_decision("QUARANTINE", code)
        self.metrics.record_latency("admission_seconds", time.perf_counter() - started_at)
        self._emit_governance_anomaly(
            envelope,
            code,
            quarantine_ref=quarantine_ref,
            receipt_ref=receipt_ref,
            auth_context=auth_context,
        )
        self.governance.emit_quarantine_spike(self.metrics.counters.get("decision.QUARANTINE", 0))
        self.metrics.flush_if_due(self._metrics_context(envelope))
        receipt = Receipt(payload=receipt_payload)
        return decision, receipt

    def _metrics_context(self, envelope: dict[str, Any]) -> dict[str, Any]:
        pins = {
            "manifest_fingerprint": envelope.get("manifest_fingerprint"),
            "platform_run_id": envelope.get("platform_run_id"),
            "scenario_run_id": envelope.get("scenario_run_id"),
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

    def _run_prefix_for(self, platform_run_id: str) -> str:
        if isinstance(self.store, S3ObjectStore):
            return platform_run_id
        root = Path(self.wiring.object_store_root)
        if root.name == "fraud-platform":
            return platform_run_id
        return f"fraud-platform/{platform_run_id}"

    def _receipt_prefix(self, envelope: dict[str, Any]) -> str:
        platform_run_id = envelope.get("platform_run_id")
        if platform_run_id:
            return f"{self._run_prefix_for(platform_run_id)}/ig"
        return self.receipt_writer.prefix

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

    def authorize_request(self, token: str | None) -> AuthContext:
        allowed, reason, context = authorize(
            self.auth_mode,
            token,
            self.auth_allowlist,
            service_token_secrets=self.auth_service_token_secrets,
        )
        if not allowed:
            raise IngestionError(reason or "UNAUTHORIZED")
        if context is None:
            raise IngestionError("UNAUTHORIZED")
        return context

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

    def _emit_governance_anomaly(
        self,
        envelope: dict[str, Any],
        reason_code: str,
        *,
        quarantine_ref: str | None,
        receipt_ref: str | None,
        auth_context: AuthContext | None = None,
    ) -> None:
        platform_run_id = str(envelope.get("platform_run_id") or "").strip()
        if not platform_run_id:
            platform_run_id = str(resolve_platform_run_id(create_if_missing=False) or "").strip()
        if not platform_run_id:
            logger.warning(
                "IG governance anomaly emit skipped (event_id=%s reason=%s platform_run_id missing)",
                envelope.get("event_id"),
                reason_code,
            )
            return
        scenario_run_id = str(envelope.get("scenario_run_id") or envelope.get("run_id") or "").strip() or None
        manifest_fingerprint = str(envelope.get("manifest_fingerprint") or "").strip() or None
        parameter_hash = str(envelope.get("parameter_hash") or "").strip() or None
        seed = envelope.get("seed")
        scenario_id = str(envelope.get("scenario_id") or "").strip() or None
        event_id = str(envelope.get("event_id") or "").strip() or "unknown"
        dedupe_key = f"ig_quarantine:{event_id}:{reason_code}"
        actor_id = auth_context.actor_id if auth_context else "SYSTEM::ingestion_gate"
        source_type = auth_context.source_type if auth_context else "SYSTEM"
        anomaly_category = classify_anomaly(reason_code)
        emit_platform_governance_event(
            store=self.store,
            event_family="CORRIDOR_ANOMALY",
            actor_id=actor_id,
            source_type=source_type,
            source_component="ingestion_gate",
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
            scenario_id=scenario_id,
            dedupe_key=dedupe_key,
            details={
                "boundary": "ingestion_gate",
                "reason_code": reason_code,
                "anomaly_category": anomaly_category,
                "event_id": event_id,
                "event_type": envelope.get("event_type"),
                "quarantine_ref": quarantine_ref,
                "receipt_ref": receipt_ref,
                "policy_rev": {
                    "policy_id": self.policy_rev.policy_id,
                    "revision": self.policy_rev.revision,
                    "content_digest": self.policy_rev.content_digest,
                },
                "run_config_digest": self.policy_rev.content_digest,
            },
        )

    def _partitioning(self, envelope: dict[str, Any]) -> tuple[str, PartitionProfile]:
        class_name = self.class_map.class_for(envelope["event_type"])
        profile_id = _profile_id_for_class(class_name, self.wiring.partitioning_profile_id)
        profile = self.partitioning.get(profile_id)
        partition_key = self.partitioning.derive_key(profile_id, envelope)
        return partition_key, profile

    def _receipt_payload(
        self,
        envelope: dict[str, Any],
        decision: AdmissionDecision,
        dedupe: str,
        event_class: str | None = None,
        platform_run_id: str | None = None,
        scenario_run_id: str | None = None,
        payload_hash: dict[str, Any] | None = None,
        admitted_at_utc: str | None = None,
        profile_id: str | None = None,
        partition_key: str | None = None,
        eb_ref: EbRef | None = None,
        auth_context: AuthContext | None = None,
    ) -> dict[str, Any]:
        receipt_id = receipt_id_from(envelope["event_id"], decision.decision)
        payload: dict[str, Any] = {
            "receipt_id": receipt_id,
            "decision": decision.decision,
            "event_id": envelope["event_id"],
            "event_type": envelope["event_type"],
            "event_class": event_class or self.class_map.class_for(envelope["event_type"]),
            "ts_utc": envelope["ts_utc"],
            "manifest_fingerprint": envelope["manifest_fingerprint"],
            "platform_run_id": platform_run_id or envelope.get("platform_run_id"),
            "run_config_digest": self.policy_rev.content_digest,
            "policy_rev": {
                "policy_id": self.policy_rev.policy_id,
                "revision": self.policy_rev.revision,
            },
            "dedupe_key": dedupe,
            "pins": {
                "manifest_fingerprint": envelope["manifest_fingerprint"],
                "platform_run_id": platform_run_id or envelope.get("platform_run_id"),
                "scenario_run_id": scenario_run_id or envelope.get("scenario_run_id"),
                "parameter_hash": envelope.get("parameter_hash"),
                "seed": envelope.get("seed"),
                "scenario_id": envelope.get("scenario_id"),
                "run_id": envelope.get("run_id"),
            },
        }
        payload["pins"] = _prune_none(payload["pins"])
        if scenario_run_id or envelope.get("scenario_run_id"):
            payload["scenario_run_id"] = scenario_run_id or envelope.get("scenario_run_id")
        if payload_hash:
            payload["payload_hash"] = payload_hash
        if admitted_at_utc:
            payload["admitted_at_utc"] = admitted_at_utc
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
        if auth_context:
            payload["actor"] = {
                "actor_id": auth_context.actor_id,
                "source_type": auth_context.source_type,
                "auth_mode": auth_context.auth_mode,
                "principal": auth_context.principal,
            }
        provenance = runtime_provenance(
            component="ingestion_gate",
            environment=self.wiring.profile_id,
            config_revision=self.policy_rev.revision,
            run_config_digest=self.policy_rev.content_digest,
        )
        payload["service_release_id"] = provenance["service_release_id"]
        payload["environment"] = provenance["environment"]
        payload["provenance"] = provenance
        return payload


def _build_indices(admission_db_path: str) -> tuple[AdmissionIndex | PostgresAdmissionIndex, OpsIndex | PostgresOpsIndex]:
    if is_postgres_dsn(admission_db_path):
        return PostgresAdmissionIndex(admission_db_path), PostgresOpsIndex(admission_db_path)
    path = Path(admission_db_path)
    return AdmissionIndex(path), OpsIndex(path)


def _build_bus(wiring: WiringProfile) -> EventBusPublisher:
    if wiring.event_bus_kind == "file":
        bus_path = wiring.event_bus_path or "runs/fraud-platform/eb"
        return FileEventBusPublisher(Path(bus_path))
    if wiring.event_bus_kind == "kafka":
        from fraud_detection.event_bus.kafka import build_kafka_publisher

        # Auth + bootstrap are supplied via env vars (materialized from SSM by ECS secrets).
        # This keeps the profile transport-agnostic while still being deterministic.
        return build_kafka_publisher(client_id=f"ig-{wiring.profile_id}")
    if wiring.event_bus_kind == "kinesis":
        from fraud_detection.event_bus.kinesis import build_kinesis_publisher

        stream_name = wiring.event_bus_path
        if isinstance(stream_name, str) and stream_name.lower() in {"", "auto", "topic"}:
            stream_name = None
        return build_kinesis_publisher(
            stream_name=stream_name,
            region=wiring.event_bus_region,
            endpoint_url=wiring.event_bus_endpoint_url,
        )
    raise RuntimeError("EB_KIND_UNSUPPORTED")


def _profile_id_for_class(class_name: str, default_profile_id: str) -> str:
    if class_name == "control":
        return "ig.partitioning.v0.control"
    if class_name == "audit":
        return "ig.partitioning.v0.audit"
    if class_name == "rtdl_decision":
        return "ig.partitioning.v0.rtdl.decision"
    if class_name == "rtdl_action_intent":
        return "ig.partitioning.v0.rtdl.action_intent"
    if class_name == "rtdl_action_outcome":
        return "ig.partitioning.v0.rtdl.action_outcome"
    if class_name == "case_trigger":
        return "ig.partitioning.v0.case.trigger"
    if class_name == "traffic_baseline":
        return "ig.partitioning.v0.traffic.baseline"
    if class_name == "traffic_fraud":
        return "ig.partitioning.v0.traffic.fraud"
    if class_name == "context_arrival":
        return "ig.partitioning.v0.context.arrival_events"
    if class_name == "context_arrival_entities":
        return "ig.partitioning.v0.context.arrival_entities"
    if class_name == "context_flow_baseline":
        return "ig.partitioning.v0.context.flow_anchor.baseline"
    if class_name == "context_flow_fraud":
        return "ig.partitioning.v0.context.flow_anchor.fraud"
    return default_profile_id


def _validate_rtdl_policy_alignment(policy: SchemaPolicy, class_map: ClassMap) -> None:
    present_events = {
        event_type
        for event_type in _RTDL_EXPECTED_CLASS_BY_EVENT
        if event_type in class_map.event_classes or policy.for_event(event_type) is not None
    }
    if not present_events:
        return
    mismatches: list[str] = []
    missing_events = sorted(set(_RTDL_EXPECTED_CLASS_BY_EVENT) - present_events)
    if missing_events:
        mismatches.append(f"missing_rtdl_events={','.join(missing_events)}")
    for event_type in sorted(present_events):
        expected_class = _RTDL_EXPECTED_CLASS_BY_EVENT[event_type]
        actual_class = class_map.class_for(event_type)
        if actual_class != expected_class:
            mismatches.append(
                f"{event_type}:class_map={actual_class}:expected={expected_class}"
            )
        policy_entry = policy.for_event(event_type)
        if policy_entry is None:
            mismatches.append(f"{event_type}:schema_policy=missing")
            continue
        if policy_entry.class_name != expected_class:
            mismatches.append(
                f"{event_type}:schema_policy_class={policy_entry.class_name}:expected={expected_class}"
            )
        if not policy_entry.schema_version_required:
            mismatches.append(f"{event_type}:schema_version_required=false")
        allowed = set(policy_entry.allowed_schema_versions or [])
        if "v1" not in allowed:
            mismatches.append(f"{event_type}:allowed_schema_versions_missing_v1")
        required = set(class_map.required_pins_for(event_type))
        if "run_id" in required:
            mismatches.append(f"{event_type}:required_pins_contains_run_id")
        if not _RTDL_REQUIRED_PINS.issubset(required):
            missing = sorted(_RTDL_REQUIRED_PINS - required)
            mismatches.append(f"{event_type}:required_pins_missing={','.join(missing)}")
    if mismatches:
        joined = ";".join(mismatches)
        raise RuntimeError(f"IG_RTLD_POLICY_ALIGNMENT_FAILED:{joined}")


def _bus_probe_streams(
    wiring: WiringProfile,
    partitioning: PartitioningProfiles,
    class_map: ClassMap,
) -> list[str]:
    if wiring.event_bus_kind not in {"kinesis", "kafka"}:
        return []
    stream_name = wiring.event_bus_path
    if isinstance(stream_name, str) and stream_name.lower() not in {"", "auto", "topic"}:
        return [stream_name]
    class_names = set(class_map.event_classes.values())
    profile_ids = {_profile_id_for_class(name, wiring.partitioning_profile_id) for name in class_names}
    streams = {partitioning.get(profile_id).stream for profile_id in profile_ids if profile_id}
    return sorted(stream for stream in streams if stream)


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


def _payload_hash(envelope: dict[str, Any]) -> tuple[dict[str, Any], str]:
    payload = {
        "event_type": envelope.get("event_type"),
        "schema_version": envelope.get("schema_version"),
        "payload": envelope.get("payload"),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {"algo": "sha256", "hex": digest}, digest
