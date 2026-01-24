"""Scenario Runner orchestration (v0 core flows)."""

from __future__ import annotations

import json
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .authority import EquivalenceRegistry, LeaseManager, RunHandle, build_authority_store
from .bus import FileControlBus
from .catalogue import OutputCatalogue, OutputEntry
from .config import PolicyProfile, WiringProfile
from .evidence import (
    EvidenceBundle,
    EvidenceStatus,
    GateReceipt,
    GateStatus,
    GateVerifier,
    GateVerificationResult,
    EngineOutputLocator,
    GateMap,
    hash_bundle,
    is_instance_scope,
    locator_to_wire,
    make_digest,
    receipt_to_wire,
    scope_parts,
)
from .engine import EngineInvoker, EngineAttemptResult
from .ids import attempt_id_for, hash_payload, run_id_from_equivalence_key, scenario_set_to_id
from .ledger import Ledger
from .models import CanonicalRunIntent, RunPlan, RunRequest, RunResponse, RunStatusState, Strategy
from .schemas import SchemaRegistry
from .storage import build_object_store


class ScenarioRunner:
    def __init__(
        self,
        wiring: WiringProfile,
        policy: PolicyProfile,
        engine_invoker: EngineInvoker,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.wiring = wiring
        self.policy = policy
        self.engine_invoker = engine_invoker
        self.schemas = SchemaRegistry(Path(wiring.schema_root))
        self.engine_schemas = SchemaRegistry(Path(wiring.engine_contracts_root))
        self.store = build_object_store(
            wiring.object_store_root,
            s3_endpoint_url=wiring.s3_endpoint_url,
            s3_region=wiring.s3_region,
            s3_path_style=wiring.s3_path_style,
        )
        self.ledger = Ledger(self.store, prefix="fraud-platform/sr", schemas=self.schemas)
        self.control_bus = FileControlBus(Path(wiring.control_bus_root))
        self.catalogue = OutputCatalogue(Path(wiring.engine_catalogue_path))
        self.gate_map = GateMap(Path(wiring.gate_map_path))
        authority_dsn = wiring.authority_store_dsn
        if authority_dsn is None:
            if wiring.object_store_root.startswith("s3://"):
                raise RuntimeError("authority_store_dsn required for non-local object store")
            default_path = Path(wiring.object_store_root) / "fraud-platform/sr/index/sr_authority.db"
            authority_dsn = f"sqlite:///{default_path.as_posix()}"
        authority_store = build_authority_store(authority_dsn)
        self.equiv_registry = EquivalenceRegistry(authority_store)
        self.lease_manager = LeaseManager(authority_store)

    def submit_run(self, request: RunRequest) -> RunResponse:
        requested_outputs = request.output_ids or []
        output_label = "policy_default" if request.output_ids is None else str(len(requested_outputs))
        self.logger.info(
            "SR: submit request received (run_equivalence_key=%s, requested_outputs=%s, engine_root=%s)",
            request.run_equivalence_key,
            output_label,
            request.engine_run_root,
        )
        self.schemas.validate(
            "run_request.schema.yaml",
            request.model_dump(mode="json", exclude_none=True),
        )
        canonical = self._canonicalize(request)
        intent_fingerprint = self._intent_fingerprint(canonical)
        run_id, first_seen = self.equiv_registry.resolve(canonical.run_equivalence_key, intent_fingerprint)
        self.logger.info(
            "SR: run_id resolved (run_id=%s, first_seen=%s)",
            run_id,
            first_seen,
        )

        leader, lease_token = self.lease_manager.acquire(run_id, owner_id="sr-local")
        if not leader:
            self.logger.info("SR: lease held by another runner (run_id=%s)", run_id)
            status = self.ledger.read_status(run_id)
            return RunResponse(
                run_id=run_id,
                state=status.state if status else RunStatusState.OPEN,
                status_ref=f"fraud-platform/sr/run_status/{run_id}.json" if status else None,
                record_ref=status.record_ref if status else None,
                facts_view_ref=status.facts_view_ref if status else None,
                message="Lease held by another runner; returning current status.",
            )

        run_handle = RunHandle(run_id=run_id, intent_fingerprint=intent_fingerprint, leader=True, lease_token=lease_token)
        self._anchor_run(run_handle)
        self.logger.info("SR: run anchored (run_id=%s)", run_id)

        try:
            plan = self._compile_plan(canonical, run_id)
        except RuntimeError as exc:
            reason = "PLAN_INVALID"
            message = str(exc)
            if message.startswith("UNKNOWN_GATE_ID:"):
                reason = "UNKNOWN_GATE_ID"
            elif message.startswith("UNKNOWN_OUTPUT_ID:"):
                reason = "UNKNOWN_OUTPUT_ID"
            failure_bundle = EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=[],
                gate_receipts=[],
                reason=reason,
            )
            self._commit_terminal(run_handle, failure_bundle)
            return self._response_from_status(run_id, "Run failed.")
        self._commit_plan(run_handle, plan)
        self.logger.info(
            "SR: plan committed (run_id=%s, outputs=%d, required_gates=%d, strategy=%s)",
            run_id,
            len(plan.intended_outputs),
            len(plan.required_gates),
            plan.strategy.value,
        )

        strategy = plan.strategy
        if strategy in (Strategy.AUTO, Strategy.FORCE_REUSE):
            self.logger.info("SR: attempting evidence reuse (run_id=%s)", run_id)
            reuse_result = self._reuse_evidence(canonical, plan)
            self.logger.info(
                "SR: reuse evidence result (run_id=%s, status=%s, reason=%s)",
                run_id,
                reuse_result.status.value,
                reuse_result.reason,
            )
            if reuse_result.status == EvidenceStatus.COMPLETE:
                return self._commit_ready(run_handle, canonical, plan, reuse_result)
            if reuse_result.status == EvidenceStatus.WAITING:
                self._commit_waiting(run_handle, reuse_result)
                return self._response_from_status(run_id, "Evidence incomplete; waiting.")
            if reuse_result.status in (EvidenceStatus.FAIL, EvidenceStatus.CONFLICT):
                self._commit_terminal(run_handle, reuse_result)
                return self._response_from_status(run_id, "Reuse evidence failed.")

        # Invoke engine path (IP1)
        self.logger.info("SR: invoking engine (run_id=%s)", run_id)
        attempt_result = self._invoke_engine(run_handle, canonical, plan)
        self.logger.info(
            "SR: engine attempt finished (run_id=%s, outcome=%s, reason=%s)",
            run_id,
            attempt_result.outcome,
            attempt_result.reason_code,
        )
        if attempt_result.outcome != "SUCCEEDED":
            failure_bundle = EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=[],
                gate_receipts=[],
                reason=attempt_result.reason_code or "ENGINE_FAILED",
            )
            self._commit_terminal(run_handle, failure_bundle)
            return self._response_from_status(run_id, "Engine attempt failed.")

        evidence = self._collect_evidence(canonical, plan, attempt_result)
        self.logger.info(
            "SR: evidence collection complete (run_id=%s, status=%s, reason=%s)",
            run_id,
            evidence.status.value,
            evidence.reason,
        )
        if evidence.status == EvidenceStatus.COMPLETE:
            return self._commit_ready(run_handle, canonical, plan, evidence)
        if evidence.status == EvidenceStatus.WAITING:
            self._commit_waiting(run_handle, evidence)
            return self._response_from_status(run_id, "Evidence incomplete; waiting.")
        self._commit_terminal(run_handle, evidence)
        return self._response_from_status(run_id, "Evidence failed or conflicted.")

    def _canonicalize(self, request: RunRequest) -> CanonicalRunIntent:
        scenario_id = request.scenario.scenario_id
        scenario_set = request.scenario.scenario_set
        if scenario_set:
            scenario_id = scenario_set_to_id(scenario_set)
        return CanonicalRunIntent(
            request_id=request.request_id,
            run_equivalence_key=request.run_equivalence_key,
            manifest_fingerprint=request.manifest_fingerprint,
            parameter_hash=request.parameter_hash,
            seed=request.seed,
            scenario_id=scenario_id,
            scenario_set=scenario_set,
            window_start_utc=request.window.window_start_utc,
            window_end_utc=request.window.window_end_utc,
            window_tz=request.window.window_tz,
            requested_strategy=request.requested_strategy,
            output_ids=request.output_ids,
            engine_run_root=request.engine_run_root,
            notes=request.notes,
            invoker=request.invoker,
        )

    def _intent_fingerprint(self, intent: CanonicalRunIntent) -> str:
        payload = {
            "manifest_fingerprint": intent.manifest_fingerprint,
            "parameter_hash": intent.parameter_hash,
            "seed": intent.seed,
            "scenario_id": intent.scenario_id,
            "scenario_set": intent.scenario_set,
            "window_start_utc": intent.window_start_utc.isoformat(),
            "window_end_utc": intent.window_end_utc.isoformat(),
            "window_tz": intent.window_tz,
        }
        return hash_payload(json.dumps(payload, sort_keys=True, ensure_ascii=True))

    def _compile_plan(self, intent: CanonicalRunIntent, run_id: str) -> RunPlan:
        output_ids = intent.output_ids or self.policy.traffic_output_ids
        for output_id in output_ids:
            if not self.catalogue.has(output_id):
                raise RuntimeError(f"UNKNOWN_OUTPUT_ID:{output_id}")
        required = set(self.gate_map.required_gate_set(output_ids))
        for output_id in output_ids:
            entry = self.catalogue.get(output_id)
            required.update(entry.read_requires_gates)
        unknown = sorted(gate_id for gate_id in required if not self.gate_map.has_gate(gate_id))
        if unknown:
            raise RuntimeError(f"UNKNOWN_GATE_ID:{','.join(unknown)}")
        strategy = self._select_strategy(intent)
        created_at = datetime.now(tz=timezone.utc)
        plan = RunPlan(
            run_id=run_id,
            plan_hash="",
            policy_rev=self.policy.as_rev(),
            strategy=strategy,
            intended_outputs=sorted(output_ids),
            required_gates=sorted(required),
            evidence_deadline_utc=created_at + timedelta(seconds=self.policy.evidence_wait_seconds),
            attempt_limit=self.policy.attempt_limit,
            created_at_utc=created_at,
        )
        payload = json.dumps(plan.model_dump(mode="json", exclude={"plan_hash"}), sort_keys=True, ensure_ascii=True)
        plan.plan_hash = hash_payload(payload)
        return plan

    def _select_strategy(self, intent: CanonicalRunIntent) -> Strategy:
        if self.policy.reuse_policy.upper() != "ALLOW":
            return Strategy.FORCE_INVOKE
        if intent.requested_strategy:
            return intent.requested_strategy
        return Strategy.AUTO

    def _anchor_run(self, run_handle: RunHandle) -> None:
        self._ensure_lease(run_handle)
        event = self._event("RUN_ACCEPTED", run_handle.run_id, {"intent_fingerprint": run_handle.intent_fingerprint})
        self.ledger.anchor_run(run_handle.run_id, event)

    def _commit_plan(self, run_handle: RunHandle, plan: RunPlan) -> None:
        self._ensure_lease(run_handle)
        event = self._event("PLAN_COMMITTED", run_handle.run_id, {"plan_hash": plan.plan_hash})
        self.ledger.commit_plan(plan, event)

    def _invoke_engine(self, run_handle: RunHandle, intent: CanonicalRunIntent, plan: RunPlan) -> EngineAttemptResult:
        self._ensure_lease(run_handle)
        scenario_binding: dict[str, Any]
        if intent.scenario_set:
            scenario_binding = {"scenario_set": intent.scenario_set}
        else:
            scenario_binding = {"scenario_id": intent.scenario_id}
        invocation = {
            "manifest_fingerprint": intent.manifest_fingerprint,
            "parameter_hash": intent.parameter_hash,
            "seed": intent.seed,
            "run_id": run_handle.run_id,
            "scenario_binding": scenario_binding,
            "engine_run_root": intent.engine_run_root,
        }
        if intent.invoker:
            invocation["invoker"] = intent.invoker
        if intent.request_id:
            invocation["request_id"] = intent.request_id
        self.engine_schemas.validate("engine_invocation.schema.yaml", invocation)

        prior_attempts = len(
            [event for event in self.ledger.read_record_events(run_handle.run_id) if event.get("event_kind") == "ENGINE_ATTEMPT_FINISHED"]
        )
        attempt_no = prior_attempts + 1
        attempt_id = attempt_id_for(run_handle.run_id, attempt_no)
        started_at = datetime.now(tz=timezone.utc)
        started_mono = time.monotonic()

        if attempt_no > plan.attempt_limit:
            ended_at = datetime.now(tz=timezone.utc)
            duration_ms = int((time.monotonic() - started_mono) * 1000)
            attempt_payload: dict[str, Any] = {
                "run_id": run_handle.run_id,
                "attempt_id": attempt_id,
                "attempt_no": attempt_no,
                "invoker": intent.invoker or "sr-local",
                "outcome": "FAILED",
                "started_at_utc": started_at.isoformat(),
                "ended_at_utc": ended_at.isoformat(),
                "duration_ms": duration_ms,
                "invocation": invocation,
            }
            attempt_payload["reason_code"] = "ATTEMPT_LIMIT_EXCEEDED"
            if intent.engine_run_root:
                attempt_payload["engine_run_root"] = intent.engine_run_root
            self.schemas.validate("engine_attempt.schema.yaml", attempt_payload)
            finish_event = self._event("ENGINE_ATTEMPT_FINISHED", run_handle.run_id, attempt_payload)
            self.ledger.append_record(run_handle.run_id, finish_event)
            return EngineAttemptResult(
                run_id=run_handle.run_id,
                attempt_id=attempt_id,
                attempt_no=attempt_no,
                outcome="FAILED",
                reason_code="ATTEMPT_LIMIT_EXCEEDED",
                engine_run_root=intent.engine_run_root,
                invocation=invocation,
            )

        attempt_event = self._event(
            "ENGINE_ATTEMPT_LAUNCH_REQUESTED",
            run_handle.run_id,
            {"attempt_id": attempt_id, "attempt_no": attempt_no, "invoker": intent.invoker or "sr-local"},
        )
        self.ledger.mark_executing(run_handle.run_id, attempt_event)
        attempt = self.engine_invoker.invoke(run_handle.run_id, attempt_no, invocation)

        outcome = attempt.outcome
        reason_code = attempt.reason_code
        engine_run_root = attempt.engine_run_root
        run_receipt_ref = None
        logs_ref: dict[str, str] | None = None

        if attempt.stdout or attempt.stderr:
            logs_ref = {}
            base = f"{self.ledger.prefix}/engine_attempt_logs/run_id={run_handle.run_id}/attempt_no={attempt_no}"
            if attempt.stdout:
                stdout_ref = self.store.write_text(f"{base}/stdout.log", attempt.stdout)
                logs_ref["stdout_ref"] = stdout_ref.path
            if attempt.stderr:
                stderr_ref = self.store.write_text(f"{base}/stderr.log", attempt.stderr)
                logs_ref["stderr_ref"] = stderr_ref.path

        if outcome == "SUCCEEDED":
            if not engine_run_root:
                outcome = "FAILED"
                reason_code = "ENGINE_ROOT_MISSING"
            else:
                receipt_path = Path(engine_run_root) / "run_receipt.json"
                if not receipt_path.exists():
                    outcome = "FAILED"
                    reason_code = "ENGINE_RECEIPT_MISSING"
                else:
                    try:
                        receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                        self.engine_schemas.validate("run_receipt.schema.yaml", receipt_payload)
                    except (ValueError, json.JSONDecodeError):
                        outcome = "FAILED"
                        reason_code = "ENGINE_RECEIPT_INVALID"
                    else:
                        if receipt_payload.get("run_id") != run_handle.run_id:
                            outcome = "FAILED"
                            reason_code = "ENGINE_RECEIPT_MISMATCH"
                        elif receipt_payload.get("manifest_fingerprint") != intent.manifest_fingerprint:
                            outcome = "FAILED"
                            reason_code = "ENGINE_RECEIPT_MISMATCH"
                        elif receipt_payload.get("parameter_hash") != intent.parameter_hash:
                            outcome = "FAILED"
                            reason_code = "ENGINE_RECEIPT_MISMATCH"
                        elif receipt_payload.get("seed") != intent.seed:
                            outcome = "FAILED"
                            reason_code = "ENGINE_RECEIPT_MISMATCH"
                        else:
                            run_receipt_ref = str(receipt_path)

        ended_at = datetime.now(tz=timezone.utc)
        duration_ms = int((time.monotonic() - started_mono) * 1000)
        attempt_payload: dict[str, Any] = {
            "run_id": run_handle.run_id,
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "invoker": intent.invoker or "sr-local",
            "outcome": outcome,
            "started_at_utc": started_at.isoformat(),
            "ended_at_utc": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "invocation": invocation,
        }
        if reason_code:
            attempt_payload["reason_code"] = reason_code
        if engine_run_root:
            attempt_payload["engine_run_root"] = engine_run_root
        if run_receipt_ref:
            attempt_payload["run_receipt_ref"] = run_receipt_ref
        if logs_ref:
            attempt_payload["logs_ref"] = logs_ref
        self.schemas.validate("engine_attempt.schema.yaml", attempt_payload)
        finish_event = self._event("ENGINE_ATTEMPT_FINISHED", run_handle.run_id, attempt_payload)
        self.ledger.append_record(run_handle.run_id, finish_event)

        return EngineAttemptResult(
            run_id=run_handle.run_id,
            attempt_id=attempt_id,
            attempt_no=attempt_no,
            outcome=outcome,
            reason_code=reason_code,
            engine_run_root=engine_run_root,
            invocation=invocation,
            duration_ms=duration_ms,
            run_receipt_ref=run_receipt_ref,
        )

    def _reuse_evidence(self, intent: CanonicalRunIntent, plan: RunPlan) -> EvidenceBundle:
        engine_root = intent.engine_run_root
        if not engine_root:
            return EvidenceBundle(status=EvidenceStatus.FAIL, locators=[], gate_receipts=[], reason="ENGINE_ROOT_MISSING")
        return self._collect_evidence(intent, plan, EngineAttemptResult(
            run_id=plan.run_id,
            attempt_id="reuse",
            attempt_no=0,
            outcome="SUCCEEDED",
            reason_code=None,
            engine_run_root=engine_root,
            invocation={},
        ))

    def _collect_evidence(
        self,
        intent: CanonicalRunIntent,
        plan: RunPlan,
        attempt: EngineAttemptResult,
    ) -> EvidenceBundle:
        engine_root = Path(attempt.engine_run_root) if attempt.engine_run_root else None
        if engine_root is None or not engine_root.exists():
            return EvidenceBundle(status=EvidenceStatus.FAIL, locators=[], gate_receipts=[], reason="ENGINE_ROOT_MISSING")

        self.logger.info(
            "SR: collecting evidence (run_id=%s, outputs=%d, required_gates=%d)",
            plan.run_id,
            len(plan.intended_outputs),
            len(plan.required_gates),
        )

        locators: list[EngineOutputLocator] = []
        locator_by_output: dict[str, EngineOutputLocator] = {}
        missing_outputs: list[str] = []
        optional_missing: list[str] = []
        for output_id in plan.intended_outputs:
            entry = self.catalogue.get(output_id)
            output_path = self._render_template(entry.path_template, intent, plan.run_id)
            full_path = engine_root / output_path
            if "*" in output_path:
                matches = list(full_path.parent.glob(full_path.name))
                if not matches:
                    if entry.availability != "optional":
                        missing_outputs.append(output_id)
                    else:
                        optional_missing.append(output_id)
                    continue
            elif not full_path.exists():
                if entry.availability != "optional":
                    missing_outputs.append(output_id)
                else:
                    optional_missing.append(output_id)
                continue
            content_digest = self._compute_output_digest(full_path)
            pins = self._locator_pins(entry, intent, plan.run_id)
            locator = EngineOutputLocator(
                output_id=output_id,
                path=str(full_path),
                content_digest=make_digest(content_digest),
                **pins,
            )
            try:
                self.engine_schemas.validate("engine_output_locator.schema.yaml", locator_to_wire(locator))
            except ValueError:
                return EvidenceBundle(
                    status=EvidenceStatus.FAIL,
                    locators=locators,
                    gate_receipts=[],
                    reason="LOCATOR_SCHEMA_INVALID",
                )
            locators.append(locator)
            locator_by_output[output_id] = locator
        self.logger.info(
            "SR: locator scan complete (present=%d, missing_required=%d, missing_optional=%d)",
            len(locators),
            len(missing_outputs),
            len(optional_missing),
        )

        gate_verifier = GateVerifier(engine_root, self.gate_map)
        gate_receipts: list[GateReceipt] = []
        missing_gates: list[str] = []
        failed_gates: list[str] = []
        conflict_gates: list[str] = []
        conflict = False
        for gate_id in plan.required_gates:
            if not self.gate_map.has_gate(gate_id):
                return EvidenceBundle(
                    status=EvidenceStatus.FAIL,
                    locators=locators,
                    gate_receipts=gate_receipts,
                    reason="UNKNOWN_GATE_ID",
                )
            tokens = self._gate_tokens_for_scope(gate_id, intent, plan.run_id)
            result: GateVerificationResult = gate_verifier.verify(gate_id, tokens)
            if result.missing:
                missing_gates.append(gate_id)
                continue
            if result.conflict:
                conflict = True
                conflict_gates.append(gate_id)
            if result.receipt:
                try:
                    self.engine_schemas.validate("gate_receipt.schema.yaml", receipt_to_wire(result.receipt))
                except ValueError:
                    return EvidenceBundle(
                        status=EvidenceStatus.FAIL,
                        locators=locators,
                        gate_receipts=gate_receipts,
                        reason="RECEIPT_SCHEMA_INVALID",
                    )
                gate_receipts.append(result.receipt)
                if result.receipt.status == GateStatus.FAIL:
                    failed_gates.append(gate_id)

        self.logger.info(
            "SR: gate verification summary (passed=%d, failed=%d, missing=%d, conflicts=%d)",
            len(gate_receipts) - len(failed_gates),
            len(failed_gates),
            len(missing_gates),
            len(conflict_gates),
        )

        if conflict:
            return EvidenceBundle(status=EvidenceStatus.CONFLICT, locators=locators, gate_receipts=gate_receipts, reason="EVIDENCE_CONFLICT")

        instance_receipts: list[dict[str, Any]] = []
        instance_missing: list[str] = []
        evidence_notes: list[str] = []
        for output_id, locator in locator_by_output.items():
            entry = self.catalogue.get(output_id)
            if not is_instance_scope(entry.scope):
                continue
            try:
                receipt_payload = self._ensure_instance_receipt(entry, locator, intent, plan.run_id)
            except RuntimeError as exc:
                return EvidenceBundle(
                    status=EvidenceStatus.FAIL,
                    locators=locators,
                    gate_receipts=gate_receipts,
                    instance_receipts=instance_receipts,
                    reason=str(exc),
                )
            if receipt_payload is None:
                instance_missing.append(f"instance_proof:{output_id}")
                continue
            instance_receipts.append(receipt_payload)
        if instance_receipts:
            self.logger.info(
                "SR: instance receipts emitted (count=%d)",
                len(instance_receipts),
            )

        now = datetime.now(tz=timezone.utc)
        if missing_outputs or missing_gates or instance_missing:
            if now < plan.evidence_deadline_utc:
                return EvidenceBundle(
                    status=EvidenceStatus.WAITING,
                    locators=locators,
                    gate_receipts=gate_receipts,
                    instance_receipts=instance_receipts,
                    missing=missing_outputs + missing_gates + instance_missing,
                    reason="EVIDENCE_WAITING",
                    notes=evidence_notes or None,
                )
            return EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=locators,
                gate_receipts=gate_receipts,
                instance_receipts=instance_receipts,
                missing=missing_outputs + missing_gates + instance_missing,
                reason="EVIDENCE_MISSING_DEADLINE",
                notes=evidence_notes or None,
            )

        if any(receipt.status == GateStatus.FAIL for receipt in gate_receipts):
            return EvidenceBundle(status=EvidenceStatus.FAIL, locators=locators, gate_receipts=gate_receipts, reason="GATE_FAIL")

        bundle_hash = hash_bundle(locators, gate_receipts, plan.policy_rev, instance_receipts)
        return EvidenceBundle(
            status=EvidenceStatus.COMPLETE,
            locators=locators,
            gate_receipts=gate_receipts,
            instance_receipts=instance_receipts,
            bundle_hash=bundle_hash,
            notes=evidence_notes or None,
        )

    def _commit_ready(
        self,
        run_handle: RunHandle,
        intent: CanonicalRunIntent,
        plan: RunPlan,
        bundle: EvidenceBundle,
    ) -> RunResponse:
        self._ensure_lease(run_handle)
        facts_view = {
            "run_id": plan.run_id,
            "pins": {
                "manifest_fingerprint": intent.manifest_fingerprint,
                "parameter_hash": intent.parameter_hash,
                "seed": intent.seed,
                "scenario_id": intent.scenario_id,
                "run_id": plan.run_id,
            },
            "locators": [locator_to_wire(locator) for locator in bundle.locators],
            "output_roles": {
                output_id: "business_traffic" if output_id in self.policy.traffic_output_ids else "non_traffic"
                for output_id in plan.intended_outputs
            },
            "intended_outputs": plan.intended_outputs,
            "gate_receipts": [receipt_to_wire(receipt) for receipt in bundle.gate_receipts],
            "policy_rev": plan.policy_rev,
            "bundle_hash": bundle.bundle_hash,
            "plan_ref": f"fraud-platform/sr/run_plan/{plan.run_id}.json",
            "record_ref": f"fraud-platform/sr/run_record/{plan.run_id}.jsonl",
            "status_ref": f"fraud-platform/sr/run_status/{plan.run_id}.json",
        }
        if bundle.instance_receipts:
            facts_view["instance_receipts"] = bundle.instance_receipts
        if bundle.notes:
            facts_view["evidence_notes"] = bundle.notes
        self.ledger.commit_facts_view(plan.run_id, facts_view)
        event = self._event("READY_COMMITTED", plan.run_id, {"bundle_hash": bundle.bundle_hash})
        self.ledger.commit_ready(plan.run_id, event)
        self.logger.info("SR: READY committed (run_id=%s)", plan.run_id)
        ready_payload = {
            "run_id": plan.run_id,
            "facts_view_ref": f"fraud-platform/sr/run_facts_view/{plan.run_id}.json",
            "bundle_hash": bundle.bundle_hash,
        }
        self.ledger.write_ready_signal(plan.run_id, ready_payload)
        self.control_bus.publish(self.wiring.control_bus_topic, ready_payload, message_id=bundle.bundle_hash or plan.plan_hash)
        return self._response_from_status(plan.run_id, "READY committed")

    def _commit_waiting(self, run_handle: RunHandle, bundle: EvidenceBundle) -> None:
        self._ensure_lease(run_handle)
        event = self._event("EVIDENCE_WAITING", run_handle.run_id, {"missing": bundle.missing})
        self.ledger.commit_waiting(run_handle.run_id, event)
        self.logger.info("SR: evidence waiting (run_id=%s, missing=%s)", run_handle.run_id, bundle.missing)

    def _commit_terminal(self, run_handle: RunHandle, bundle: EvidenceBundle) -> None:
        self._ensure_lease(run_handle)
        state = RunStatusState.QUARANTINED if bundle.status == EvidenceStatus.CONFLICT else RunStatusState.FAILED
        event_kind = "EVIDENCE_CONFLICT" if bundle.status == EvidenceStatus.CONFLICT else "EVIDENCE_FAIL"
        event = self._event(event_kind, run_handle.run_id, {"reason": bundle.reason, "missing": bundle.missing})
        self.ledger.commit_terminal(run_handle.run_id, state, bundle.reason or "FAIL", event)
        self.logger.info(
            "SR: terminal commit (run_id=%s, state=%s, reason=%s)",
            run_handle.run_id,
            state.value,
            bundle.reason,
        )

    def _response_from_status(self, run_id: str, message: str) -> RunResponse:
        status = self.ledger.read_status(run_id)
        return RunResponse(
            run_id=run_id,
            state=status.state if status else RunStatusState.OPEN,
            status_ref=f"fraud-platform/sr/run_status/{run_id}.json",
            record_ref=f"fraud-platform/sr/run_record/{run_id}.jsonl",
            facts_view_ref=f"fraud-platform/sr/run_facts_view/{run_id}.json" if status and status.state == RunStatusState.READY else None,
            message=message,
        )

    def _event(self, kind: str, run_id: str, details: dict[str, Any]) -> dict[str, Any]:
        payload = {"event_kind": kind, "run_id": run_id, "details": details}
        event_id = hash_payload(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        payload["event_id"] = event_id
        payload["ts_utc"] = datetime.now(tz=timezone.utc).isoformat()
        return payload

    def _render_template(self, template: str, intent: CanonicalRunIntent, run_id: str) -> str:
        rendered = template
        rendered = rendered.replace("{manifest_fingerprint}", intent.manifest_fingerprint)
        rendered = rendered.replace("{parameter_hash}", intent.parameter_hash)
        rendered = rendered.replace("{seed}", str(intent.seed))
        rendered = rendered.replace("{scenario_id}", intent.scenario_id)
        rendered = rendered.replace("{run_id}", run_id)
        return rendered

    def _compute_output_digest(self, path: Path) -> str:
        def digest_files(files: list[Path]) -> str:
            hasher = hashlib.sha256()
            for file_path in files:
                hasher.update(file_path.read_bytes())
            return hasher.hexdigest()

        if path.is_file():
            return digest_files([path])
        if path.is_dir():
            files = sorted([p for p in path.rglob("*") if p.is_file()], key=lambda p: str(p))
            return digest_files(files)
        matches = sorted([p for p in path.parent.glob(path.name) if p.is_file()], key=lambda p: str(p))
        return digest_files(matches)

    def _locator_pins(self, entry: OutputEntry, intent: CanonicalRunIntent, run_id: str) -> dict[str, Any]:
        partitions = entry.partitions or []
        pins: dict[str, Any] = {}
        if not partitions:
            pins["manifest_fingerprint"] = intent.manifest_fingerprint
            return pins
        for part in partitions:
            if part == "manifest_fingerprint":
                pins["manifest_fingerprint"] = intent.manifest_fingerprint
            elif part == "parameter_hash":
                pins["parameter_hash"] = intent.parameter_hash
            elif part == "seed":
                pins["seed"] = intent.seed
            elif part == "scenario_id":
                pins["scenario_id"] = intent.scenario_id
            elif part == "run_id":
                pins["run_id"] = run_id
        return pins

    def _gate_tokens_for_scope(self, gate_id: str, intent: CanonicalRunIntent, run_id: str) -> dict[str, Any]:
        entry = self.gate_map.gate_entry(gate_id)
        scope = entry.get("scope", "")
        parts = scope_parts(scope)
        tokens: dict[str, Any] = {"manifest_fingerprint": intent.manifest_fingerprint}
        if "parameter" in parts or "parameter_hash" in parts:
            tokens["parameter_hash"] = intent.parameter_hash
        if "seed" in parts:
            tokens["seed"] = intent.seed
        if "scenario" in parts or "scenario_id" in parts:
            tokens["scenario_id"] = intent.scenario_id
        if "run" in parts or "run_id" in parts:
            tokens["run_id"] = run_id
        return tokens

    def _instance_receipt_scope(
        self,
        entry: OutputEntry,
        intent: CanonicalRunIntent,
        run_id: str,
    ) -> tuple[dict[str, Any], list[str]]:
        partitions = entry.partitions or []
        tokens = {
            "manifest_fingerprint": intent.manifest_fingerprint,
            "parameter_hash": intent.parameter_hash,
            "seed": intent.seed,
            "scenario_id": intent.scenario_id,
            "run_id": run_id,
        }
        scope: dict[str, Any] = {"manifest_fingerprint": intent.manifest_fingerprint}
        missing: list[str] = []
        for key in partitions:
            value = tokens.get(key)
            if value is None:
                missing.append(key)
                continue
            scope[key] = value
        return scope, missing

    def _instance_receipt_store_path(self, output_id: str, scope: dict[str, Any]) -> str:
        order = ["manifest_fingerprint", "parameter_hash", "seed", "scenario_id", "run_id"]
        segments = [f"{key}={scope[key]}" for key in order if key in scope]
        partition_path = "/".join(segments)
        return f"{self.ledger.prefix}/instance_receipts/output_id={output_id}/{partition_path}/instance_receipt.json"

    def _normalize_instance_receipt(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        normalized.pop("produced_at_utc", None)
        return normalized

    def _ensure_instance_receipt(
        self,
        entry: OutputEntry,
        locator: EngineOutputLocator,
        intent: CanonicalRunIntent,
        run_id: str,
    ) -> dict[str, Any] | None:
        if locator.content_digest is None:
            raise RuntimeError("INSTANCE_DIGEST_MISSING")
        scope, missing = self._instance_receipt_scope(entry, intent, run_id)
        if missing:
            raise RuntimeError("INSTANCE_SCOPE_MISSING")
        receipt_path = self._instance_receipt_store_path(locator.output_id, scope)
        receipt_payload = {
            "output_id": locator.output_id,
            "status": "PASS",
            "scope": scope,
            "target_ref": locator_to_wire(locator),
            "target_digest": {"algo": locator.content_digest.algo, "hex": locator.content_digest.hex},
            "receipt_kind": "instance_proof",
            "artifacts": {"receipt_path": receipt_path},
        }
        try:
            self.engine_schemas.validate("instance_proof_receipt.schema.yaml", receipt_payload)
        except ValueError as exc:
            raise RuntimeError("INSTANCE_RECEIPT_SCHEMA_INVALID") from exc
        try:
            self.store.write_json_if_absent(receipt_path, receipt_payload)
            return receipt_payload
        except FileExistsError:
            existing = self.store.read_json(receipt_path)
            if self._normalize_instance_receipt(existing) != self._normalize_instance_receipt(receipt_payload):
                raise RuntimeError("INSTANCE_RECEIPT_DRIFT")
            return existing

    def _ensure_lease(self, run_handle: RunHandle) -> None:
        if not run_handle.lease_token:
            raise RuntimeError("LEASE_TOKEN_MISSING")
        if not self.lease_manager.check(run_handle.run_id, run_handle.lease_token):
            raise RuntimeError("LEASE_LOST")
        if not self.lease_manager.renew(run_handle.run_id, run_handle.lease_token):
            raise RuntimeError("LEASE_LOST")
