"""Scenario Runner orchestration (v0 core flows)."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .authority import EquivalenceRegistry, LeaseManager, RunHandle
from .bus import FileControlBus
from .catalogue import OutputCatalogue
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
)
from .engine import EngineInvoker, EngineAttemptResult
from .ids import hash_payload, run_id_from_equivalence_key, scenario_set_to_id
from .ledger import Ledger
from .models import CanonicalRunIntent, RunPlan, RunRequest, RunResponse, RunStatusState, Strategy
from .schemas import SchemaRegistry
from .storage import LocalObjectStore


class ScenarioRunner:
    def __init__(
        self,
        wiring: WiringProfile,
        policy: PolicyProfile,
        engine_invoker: EngineInvoker,
    ) -> None:
        self.wiring = wiring
        self.policy = policy
        self.engine_invoker = engine_invoker
        self.schemas = SchemaRegistry(Path(wiring.schema_root))
        self.store = LocalObjectStore(Path(wiring.object_store_root))
        self.ledger = Ledger(self.store, prefix="fraud-platform/sr", schemas=self.schemas)
        self.control_bus = FileControlBus(Path(wiring.control_bus_root))
        self.catalogue = OutputCatalogue(Path(wiring.engine_catalogue_path))
        self.gate_map = GateMap(Path(wiring.gate_map_path))
        self.equiv_registry = EquivalenceRegistry(Path(wiring.object_store_root) / "fraud-platform/sr/index")
        self.lease_manager = LeaseManager(Path(wiring.object_store_root) / "fraud-platform/sr/index/leases")

    def submit_run(self, request: RunRequest) -> RunResponse:
        self.schemas.validate("run_request.schema.yaml", request.model_dump())
        canonical = self._canonicalize(request)
        intent_fingerprint = self._intent_fingerprint(canonical)
        run_id, first_seen = self.equiv_registry.resolve(canonical.run_equivalence_key, intent_fingerprint)

        leader, lease_token = self.lease_manager.acquire(run_id, owner_id="sr-local")
        if not leader:
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

        plan = self._compile_plan(canonical, run_id)
        self._commit_plan(run_handle, plan)

        strategy = plan.strategy
        if strategy in (Strategy.AUTO, Strategy.FORCE_REUSE):
            reuse_result = self._reuse_evidence(canonical, plan)
            if reuse_result.status == EvidenceStatus.COMPLETE:
                return self._commit_ready(run_handle, canonical, plan, reuse_result)
            if reuse_result.status == EvidenceStatus.WAITING:
                self._commit_waiting(run_handle, reuse_result)
                return self._response_from_status(run_id, "Evidence incomplete; waiting.")
            if reuse_result.status in (EvidenceStatus.FAIL, EvidenceStatus.CONFLICT):
                self._commit_terminal(run_handle, reuse_result)
                return self._response_from_status(run_id, "Reuse evidence failed.")

        # Invoke engine path (IP1)
        attempt_result = self._invoke_engine(run_id, canonical)
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
                raise RuntimeError(f"Unknown output_id {output_id}")
        required = set(self.gate_map.required_gate_set(output_ids))
        for output_id in output_ids:
            entry = self.catalogue.get(output_id)
            required.update(entry.read_requires_gates)
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
        payload = json.dumps(plan.model_dump(exclude={"plan_hash"}), sort_keys=True, ensure_ascii=True)
        plan.plan_hash = hash_payload(payload)
        return plan

    def _select_strategy(self, intent: CanonicalRunIntent) -> Strategy:
        if self.policy.reuse_policy.upper() != "ALLOW":
            return Strategy.FORCE_INVOKE
        if intent.requested_strategy:
            return intent.requested_strategy
        return Strategy.AUTO

    def _anchor_run(self, run_handle: RunHandle) -> None:
        event = self._event("RUN_ACCEPTED", run_handle.run_id, {"intent_fingerprint": run_handle.intent_fingerprint})
        self.ledger.anchor_run(run_handle.run_id, event)

    def _commit_plan(self, run_handle: RunHandle, plan: RunPlan) -> None:
        event = self._event("PLAN_COMMITTED", run_handle.run_id, {"plan_hash": plan.plan_hash})
        self.ledger.commit_plan(plan, event)

    def _invoke_engine(self, run_id: str, intent: CanonicalRunIntent) -> EngineAttemptResult:
        invocation = {
            "manifest_fingerprint": intent.manifest_fingerprint,
            "parameter_hash": intent.parameter_hash,
            "seed": intent.seed,
            "run_id": run_id,
            "scenario_binding": {
                "scenario_id": intent.scenario_id,
                "scenario_set": intent.scenario_set,
            },
            "engine_run_root": intent.engine_run_root,
        }
        attempt_event = self._event("ENGINE_ATTEMPT_LAUNCH_REQUESTED", run_id, {"attempt_no": 1})
        self.ledger.mark_executing(run_id, attempt_event)
        attempt = self.engine_invoker.invoke(run_id, 1, invocation)
        finish_event = self._event(
            "ENGINE_ATTEMPT_FINISHED",
            run_id,
            {"attempt_id": attempt.attempt_id, "outcome": attempt.outcome, "reason": attempt.reason_code},
        )
        self.ledger.append_record(run_id, finish_event)
        return attempt

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

        locators: list[EngineOutputLocator] = []
        missing_outputs: list[str] = []
        for output_id in plan.intended_outputs:
            entry = self.catalogue.get(output_id)
            output_path = self._render_template(entry.path_template, intent, plan.run_id)
            full_path = engine_root / output_path
            if "*" in output_path:
                matches = list(full_path.parent.glob(full_path.name))
                if not matches:
                    missing_outputs.append(output_id)
                    continue
            elif not full_path.exists():
                missing_outputs.append(output_id)
                continue
            content_digest = self._compute_output_digest(full_path)
            locator = EngineOutputLocator(
                output_id=output_id,
                path=str(full_path),
                manifest_fingerprint=intent.manifest_fingerprint,
                parameter_hash=intent.parameter_hash,
                seed=intent.seed,
                scenario_id=intent.scenario_id,
                run_id=plan.run_id,
                content_digest=content_digest,
            )
            locators.append(locator)

        gate_verifier = GateVerifier(engine_root, self.gate_map)
        gate_receipts: list[GateReceipt] = []
        missing_gates: list[str] = []
        conflict = False
        for gate_id in plan.required_gates:
            tokens = {
                "manifest_fingerprint": intent.manifest_fingerprint,
                "parameter_hash": intent.parameter_hash,
                "seed": intent.seed,
                "scenario_id": intent.scenario_id,
                "run_id": plan.run_id,
            }
            result: GateVerificationResult = gate_verifier.verify(gate_id, tokens)
            if result.missing:
                missing_gates.append(gate_id)
                continue
            if result.conflict:
                conflict = True
            if result.receipt:
                gate_receipts.append(result.receipt)

        if conflict:
            return EvidenceBundle(status=EvidenceStatus.CONFLICT, locators=locators, gate_receipts=gate_receipts, reason="EVIDENCE_CONFLICT")

        now = datetime.now(tz=timezone.utc)
        if missing_outputs or missing_gates:
            if now < plan.evidence_deadline_utc:
                return EvidenceBundle(
                    status=EvidenceStatus.WAITING,
                    locators=locators,
                    gate_receipts=gate_receipts,
                    missing=missing_outputs + missing_gates,
                    reason="EVIDENCE_WAITING",
                )
            return EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=locators,
                gate_receipts=gate_receipts,
                missing=missing_outputs + missing_gates,
                reason="EVIDENCE_MISSING_DEADLINE",
            )

        if any(receipt.status == GateStatus.FAIL for receipt in gate_receipts):
            return EvidenceBundle(status=EvidenceStatus.FAIL, locators=locators, gate_receipts=gate_receipts, reason="GATE_FAIL")

        bundle_hash = hash_bundle(locators, gate_receipts, plan.policy_rev)
        return EvidenceBundle(
            status=EvidenceStatus.COMPLETE,
            locators=locators,
            gate_receipts=gate_receipts,
            bundle_hash=bundle_hash,
        )

    def _commit_ready(
        self,
        run_handle: RunHandle,
        intent: CanonicalRunIntent,
        plan: RunPlan,
        bundle: EvidenceBundle,
    ) -> RunResponse:
        facts_view = {
            "run_id": plan.run_id,
            "pins": {
                "manifest_fingerprint": intent.manifest_fingerprint,
                "parameter_hash": intent.parameter_hash,
                "seed": intent.seed,
                "scenario_id": intent.scenario_id,
                "run_id": plan.run_id,
            },
            "locators": [locator.__dict__ for locator in bundle.locators],
            "output_roles": {
                output_id: "business_traffic" if output_id in self.policy.traffic_output_ids else "non_traffic"
                for output_id in plan.intended_outputs
            },
            "intended_outputs": plan.intended_outputs,
            "gate_receipts": [receipt.__dict__ for receipt in bundle.gate_receipts],
            "policy_rev": plan.policy_rev,
            "bundle_hash": bundle.bundle_hash,
            "plan_ref": f"fraud-platform/sr/run_plan/{plan.run_id}.json",
            "record_ref": f"fraud-platform/sr/run_record/{plan.run_id}.jsonl",
            "status_ref": f"fraud-platform/sr/run_status/{plan.run_id}.json",
        }
        self.ledger.commit_facts_view(plan.run_id, facts_view)
        event = self._event("READY_COMMITTED", plan.run_id, {"bundle_hash": bundle.bundle_hash})
        self.ledger.commit_ready(plan.run_id, event)
        ready_payload = {
            "run_id": plan.run_id,
            "facts_view_ref": f"fraud-platform/sr/run_facts_view/{plan.run_id}.json",
            "bundle_hash": bundle.bundle_hash,
        }
        self.ledger.write_ready_signal(plan.run_id, ready_payload)
        self.control_bus.publish(self.wiring.control_bus_topic, ready_payload, message_id=bundle.bundle_hash or plan.plan_hash)
        return self._response_from_status(plan.run_id, "READY committed")

    def _commit_waiting(self, run_handle: RunHandle, bundle: EvidenceBundle) -> None:
        event = self._event("EVIDENCE_WAITING", run_handle.run_id, {"missing": bundle.missing})
        self.ledger.commit_waiting(run_handle.run_id, event)

    def _commit_terminal(self, run_handle: RunHandle, bundle: EvidenceBundle) -> None:
        state = RunStatusState.QUARANTINED if bundle.status == EvidenceStatus.CONFLICT else RunStatusState.FAILED
        event_kind = "EVIDENCE_CONFLICT" if bundle.status == EvidenceStatus.CONFLICT else "EVIDENCE_FAIL"
        event = self._event(event_kind, run_handle.run_id, {"reason": bundle.reason, "missing": bundle.missing})
        self.ledger.commit_terminal(run_handle.run_id, state, bundle.reason or "FAIL", event)

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
