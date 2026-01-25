"""IG admission spine."""

from __future__ import annotations

import json
import logging
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
from .ids import dedupe_key, quarantine_id_from, receipt_id_from
from .index import AdmissionIndex
from .models import AdmissionDecision, Receipt, QuarantineRecord
from .partitioning import PartitionProfile, PartitioningProfiles
from .receipts import ReceiptWriter
from .scopes import is_instance_scope
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
    bus: EventBusPublisher
    store: ObjectStore
    gate_verifier: GateVerifier | None

    @classmethod
    def build(cls, wiring: WiringProfile) -> "IngestionGate":
        policy = SchemaPolicy.load(Path(wiring.schema_policy_ref))
        class_map = ClassMap.load(Path(wiring.class_map_ref))
        policy_rev = PolicyRev(policy_id="ig_policy", revision=wiring.policy_rev)
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
        bus = _build_bus(wiring)
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
            bus=bus,
            store=store,
            gate_verifier=gate_verifier,
        )

    def admit_push(self, envelope: dict[str, Any]) -> Receipt:
        logger.info("IG admit_push start event_id=%s event_type=%s", envelope.get("event_id"), envelope.get("event_type"))
        decision, receipt = self._admit_event(envelope, output_id=None, run_facts=None)
        if decision.decision == "QUARANTINE":
            raise RuntimeError("QUARANTINED")
        return receipt

    def admit_pull(self, run_facts_view_path: Path) -> list[Receipt]:
        logger.info("IG admit_pull start run_facts_view=%s", run_facts_view_path)
        puller = EnginePuller(run_facts_view_path, self.catalogue)
        receipts: list[Receipt] = []
        run_facts = _load_json(run_facts_view_path)
        for envelope in puller.iter_events():
            decision, receipt = self._admit_event(
                envelope,
                output_id=envelope["event_type"],
                run_facts=run_facts,
            )
            if decision.decision != "QUARANTINE":
                receipts.append(receipt)
        return receipts

    def _admit_event(
        self,
        envelope: dict[str, Any],
        output_id: str | None,
        run_facts: dict[str, Any] | None,
    ) -> tuple[AdmissionDecision, Receipt]:
        try:
            self._validate_envelope(envelope)
            self._validate_class_pins(envelope)
            self.schema_enforcer.validate_payload(envelope["event_type"], envelope)
            if run_facts is None and self._requires_run_ready(envelope["event_type"]):
                self._ensure_run_ready(envelope)
            if output_id and run_facts:
                self._verify_required_gates(output_id, run_facts)
        except IngestionError as exc:
            return self._quarantine(envelope, exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("IG admission validation error")
            return self._quarantine(envelope, IngestionError("INTERNAL_ERROR"))
        logger.info(
            "IG validated event_id=%s event_type=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
        )

        dedupe = dedupe_key(envelope["event_id"], envelope["event_type"])
        existing = self.admission_index.lookup(dedupe)
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
            receipt_payload = self._receipt_payload(envelope, decision, dedupe)
            receipt = Receipt(payload=receipt_payload)
            receipt_id = receipt_payload["receipt_id"]
            self.contract_registry.validate("ingestion_receipt.schema.yaml", receipt_payload)
            self.receipt_writer.write_receipt(receipt_id, receipt_payload)
            return decision, receipt

        try:
            partition_key, profile = self._partitioning(envelope)
            eb_ref = self.bus.publish(profile.stream, partition_key, envelope)
        except IngestionError as exc:
            return self._quarantine(envelope, exc)
        except Exception as exc:
            logger.exception("IG event bus publish error")
            return self._quarantine(envelope, IngestionError("EB_PUBLISH_FAILED"))
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
        return decision, receipt

    def _quarantine(self, envelope: dict[str, Any], exc: Exception) -> tuple[AdmissionDecision, Receipt]:
        code = reason_code(exc)
        logger.warning(
            "IG quarantine event_id=%s event_type=%s reason=%s",
            envelope.get("event_id"),
            envelope.get("event_type"),
            code,
        )
        event_id = envelope.get("event_id") or "unknown"
        quarantine_id = quarantine_id_from(event_id)
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
        self.receipt_writer.write_receipt(receipt_id, receipt_payload)
        receipt = Receipt(payload=receipt_payload)
        return decision, receipt

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
        run_facts = self.store.read_json(facts_ref)
        self._verify_run_pins(envelope, run_facts)
        logger.info("IG run joinability ok run_id=%s facts_ref=%s", run_id, facts_ref)

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
