"""Scenario Runner orchestration (v0 core flows)."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fnmatch import fnmatch
from typing import Any

import logging as _logging
from .authority import EquivalenceRegistry, LeaseManager, RunHandle, build_authority_store
from .bus import FileControlBus, KinesisControlBus
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
from .models import (
    CanonicalRunIntent,
    ReemitKind,
    ReemitRequest,
    ReemitResponse,
    RunPlan,
    RunRequest,
    RunResponse,
    RunStatusState,
    Strategy,
)

narrative_logger = _logging.getLogger("fraud_detection.platform_narrative")
from .obs import (
    CompositeObsSink,
    ConsoleObsSink,
    MetricsObsSink,
    ObsEvent,
    ObsOutcome,
    ObsPhase,
    ObsSeverity,
    OtlpObsSink,
    ObsSink,
)
from .security import is_authorized
from .schemas import SchemaRegistry
from .storage import build_object_store
from ..platform_runtime import platform_run_prefix, resolve_platform_run_id, resolve_run_scoped_path
from ..platform_provenance import runtime_provenance


_PLATFORM_RUN_ID_RE = re.compile(r"^platform_[0-9]{8}T[0-9]{6}Z$")


def _platform_run_id_from_prefix(run_prefix: str | None) -> str | None:
    if not run_prefix:
        return None
    candidate = run_prefix.rstrip("/").split("/")[-1]
    if _PLATFORM_RUN_ID_RE.match(candidate):
        return candidate
    return None


class ScenarioRunner:
    def __init__(
        self,
        wiring: WiringProfile,
        policy: PolicyProfile,
        engine_invoker: EngineInvoker,
        obs_sink: ObsSink | None = None,
        run_prefix: str | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.wiring = wiring
        self.policy = policy
        self.engine_invoker = engine_invoker
        self.execution_identity: str | None = None
        self._validate_settlement_lock()
        self.schemas = SchemaRegistry(Path(wiring.schema_root))
        self.engine_schemas = SchemaRegistry(Path(wiring.engine_contracts_root))
        self.oracle_schemas = SchemaRegistry(Path(wiring.schema_root).parent / "oracle_store")
        self.store = build_object_store(
            wiring.object_store_root,
            s3_endpoint_url=wiring.s3_endpoint_url,
            s3_region=wiring.s3_region,
            s3_path_style=wiring.s3_path_style,
        )
        prefix_platform_id = _platform_run_id_from_prefix(run_prefix)
        self.platform_run_id = prefix_platform_id or resolve_platform_run_id(create_if_missing=True)
        if not self.platform_run_id:
            raise RuntimeError("PLATFORM_RUN_ID required to build SR run-scoped artifacts.")
        if run_prefix and not prefix_platform_id:
            self.logger.warning(
                "SR: run_prefix '%s' does not end with platform_run_id; using %s for pins.",
                run_prefix,
                self.platform_run_id,
            )
        self.run_prefix = run_prefix or platform_run_prefix(create_if_missing=True)
        if not self.run_prefix:
            raise RuntimeError("PLATFORM_RUN_ID required to build SR run-scoped artifacts.")
        self.ledger = Ledger(self.store, prefix=f"{self.run_prefix}/sr", schemas=self.schemas)
        self.control_bus = self._build_control_bus(wiring)
        self.catalogue = OutputCatalogue(Path(wiring.engine_catalogue_path))
        self.gate_map = GateMap(Path(wiring.gate_map_path))
        self.metrics_sink = MetricsObsSink()
        if not wiring.object_store_root.startswith("s3://"):
            self.logger.warning(
                "SR: runtime artifacts may include sensitive capability tokens under %s/%s; review and avoid committing.",
                wiring.object_store_root.rstrip("/"),
                f"{self.run_prefix}/sr/index",
            )
        if obs_sink is None:
            sinks = []
            if os.getenv("SR_OBS_CONSOLE", "true").lower() == "true":
                sinks.append(ConsoleObsSink())
            if os.getenv("SR_OTLP_ENABLED", "false").lower() == "true":
                sinks.append(OtlpObsSink())
            sinks.append(self.metrics_sink)
            self.obs_sink = CompositeObsSink(sinks)
        else:
            self.obs_sink = obs_sink
        authority_dsn = wiring.authority_store_dsn
        if authority_dsn is None:
            if wiring.object_store_root.startswith("s3://"):
                raise RuntimeError("authority_store_dsn required for non-local object store")
            default_path = Path(wiring.object_store_root) / self.run_prefix / "sr/index/sr_authority.db"
            authority_dsn = f"sqlite:///{default_path.as_posix()}"
        authority_store = build_authority_store(authority_dsn)
        self.equiv_registry = EquivalenceRegistry(authority_store)
        self.lease_manager = LeaseManager(authority_store)

    def submit_run(self, request: RunRequest) -> RunResponse:
        requested_outputs = request.output_ids or []
        output_label = "policy_default" if request.output_ids is None else str(len(requested_outputs))
        if not is_authorized(request.invoker, self.wiring.auth_allowlist, self.wiring.auth_mode):
            run_id = run_id_from_equivalence_key(request.run_equivalence_key)
            self.ledger.append_record(
                run_id,
                self._event(
                    "AUTH_DENIED",
                    run_id,
                    {"invoker": request.invoker or "unknown", "action": "submit_run"},
                ),
            )
            self._emit_obs(
                ObsEvent.now(
                    event_kind="AUTH_DENIED",
                    phase=ObsPhase.INGRESS,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins={"run_id": run_id},
                    details={"action": "submit_run"},
                )
            )
            return RunResponse(
                run_id=run_id,
                state=RunStatusState.FAILED,
                record_ref=f"{self.ledger.prefix}/run_record/{run_id}.jsonl",
                message="Unauthorized.",
            )
        self.logger.info(
            "SR: submit request received (run_equivalence_key=%s, requested_outputs=%s, engine_root=%s)",
            request.run_equivalence_key,
            output_label,
            request.engine_run_root,
        )
        self._emit_obs(
            ObsEvent.now(
                event_kind="RUN_REQUEST_RECEIVED",
                phase=ObsPhase.INGRESS,
                outcome=ObsOutcome.OK,
                severity=ObsSeverity.INFO,
                pins={"run_equivalence_key": request.run_equivalence_key},
                details={"requested_outputs": output_label},
            )
        )
        self.schemas.validate(
            "run_request.schema.yaml",
            request.model_dump(mode="json", exclude_none=True),
        )
        canonical = self._canonicalize(request)
        resolved_engine_root = self._resolve_engine_root(request.engine_run_root)
        oracle_scope_reason = self._validate_oracle_scope(
            request_root=request.engine_run_root,
            resolved_engine_root=resolved_engine_root,
            scenario_id=canonical.scenario_id,
        )
        if oracle_scope_reason:
            run_id = run_id_from_equivalence_key(request.run_equivalence_key)
            self.ledger.append_record(
                run_id,
                self._event(
                    "ORACLE_SCOPE_REJECTED",
                    run_id,
                    {"reason": oracle_scope_reason},
                ),
            )
            self._emit_obs(
                ObsEvent.now(
                    event_kind="ORACLE_SCOPE_REJECTED",
                    phase=ObsPhase.INGRESS,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins={"run_id": run_id, "scenario_id": canonical.scenario_id},
                    details={"reason": oracle_scope_reason},
                )
            )
            return RunResponse(
                run_id=run_id,
                state=RunStatusState.FAILED,
                record_ref=f"{self.ledger.prefix}/run_record/{run_id}.jsonl",
                message=f"Oracle scope rejected: {oracle_scope_reason}",
            )
        if resolved_engine_root and resolved_engine_root != request.engine_run_root:
            self.logger.info(
                "SR: oracle engine root enforced (request_root=%s, oracle_root=%s)",
                request.engine_run_root,
                resolved_engine_root,
            )
        if resolved_engine_root:
            canonical = canonical.model_copy(update={"engine_run_root": resolved_engine_root})
        intent_fingerprint = self._intent_fingerprint(canonical)
        run_id, first_seen = self.equiv_registry.resolve(canonical.run_equivalence_key, intent_fingerprint)
        self.logger.info(
            "SR: run_id resolved (run_id=%s, first_seen=%s)",
            run_id,
            first_seen,
        )
        self._emit_obs(
            ObsEvent.now(
                event_kind="RUN_ACCEPTED",
                phase=ObsPhase.AUTHORITY,
                outcome=ObsOutcome.OK,
                severity=ObsSeverity.INFO,
                pins=self._obs_pins(canonical, run_id),
            )
        )

        leader, lease_token = self.lease_manager.acquire(run_id, owner_id="sr-local")
        if not leader:
            self.logger.info("SR: lease held by another runner (run_id=%s)", run_id)
            self._emit_obs(
                ObsEvent.now(
                    event_kind="LEASE_BUSY",
                    phase=ObsPhase.AUTHORITY,
                    outcome=ObsOutcome.SKIP,
                    severity=ObsSeverity.WARN,
                    pins=self._obs_pins(canonical, run_id),
                )
            )
            status = self.ledger.read_status(run_id)
            return RunResponse(
                run_id=run_id,
                state=status.state if status else RunStatusState.OPEN,
                status_ref=f"{self.run_prefix}/sr/run_status/{run_id}.json" if status else None,
                record_ref=status.record_ref if status else None,
                facts_view_ref=status.facts_view_ref if status else None,
                message="Lease held by another runner; returning current status.",
            )

        run_handle = RunHandle(run_id=run_id, intent_fingerprint=intent_fingerprint, leader=True, lease_token=lease_token)
        self._anchor_run(run_handle)
        self.logger.info("SR: run anchored (run_id=%s)", run_id)
        self._emit_obs(
            ObsEvent.now(
                event_kind="RUN_ANCHORED",
                phase=ObsPhase.AUTHORITY,
                outcome=ObsOutcome.OK,
                severity=ObsSeverity.INFO,
                pins=self._obs_pins(canonical, run_id),
            )
        )

        try:
            plan = self._compile_plan(canonical, run_id)
        except RuntimeError as exc:
            reason = "PLAN_INVALID"
            message = str(exc)
            if message.startswith("UNKNOWN_GATE_ID:"):
                reason = "UNKNOWN_GATE_ID"
            elif message.startswith("UNKNOWN_OUTPUT_ID:"):
                reason = "UNKNOWN_OUTPUT_ID"
            elif message.startswith("ENGINE_INVOCATION_INVALID"):
                reason = "ENGINE_INVOCATION_INVALID"
            failure_bundle = EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=[],
                gate_receipts=[],
                reason=reason,
            )
            self._commit_terminal(run_handle, failure_bundle)
            self._emit_obs(
                ObsEvent.now(
                    event_kind="PLAN_FAILED",
                    phase=ObsPhase.PLAN,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins=self._obs_pins(canonical, run_id),
                    policy_rev=self.policy.as_rev(),
                    details={"reason": reason},
                )
            )
            return self._response_from_status(run_id, "Run failed.")
        self._commit_plan(run_handle, plan)
        self.logger.info(
            "SR: plan committed (run_id=%s, outputs=%d, required_gates=%d, strategy=%s)",
            run_id,
            len(plan.intended_outputs),
            len(plan.required_gates),
            plan.strategy.value,
        )
        self._emit_obs(
            ObsEvent.now(
                event_kind="PLAN_COMMITTED",
                phase=ObsPhase.PLAN,
                outcome=ObsOutcome.OK,
                severity=ObsSeverity.INFO,
                pins=self._obs_pins(canonical, run_id),
                policy_rev=plan.policy_rev,
                details={"plan_hash": plan.plan_hash},
            )
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
            self._emit_obs(
                ObsEvent.now(
                    event_kind="EVIDENCE_REUSE_RESULT",
                    phase=ObsPhase.EVIDENCE,
                    outcome=self._obs_outcome(reuse_result.status),
                    severity=ObsSeverity.INFO,
                    pins=self._obs_pins(canonical, run_id),
                    policy_rev=plan.policy_rev,
                    details={"reason": reuse_result.reason},
                )
            )
            if reuse_result.status == EvidenceStatus.COMPLETE:
                return self._commit_ready(
                    run_handle,
                    canonical,
                    plan,
                    reuse_result,
                    engine_run_root=canonical.engine_run_root,
                )
            if reuse_result.status == EvidenceStatus.WAITING:
                self._commit_waiting(run_handle, reuse_result)
                return self._response_from_status(run_id, "Evidence incomplete; waiting.")
            if reuse_result.status in (EvidenceStatus.FAIL, EvidenceStatus.CONFLICT):
                self._commit_terminal(run_handle, reuse_result)
                return self._response_from_status(run_id, "Reuse evidence failed.")

        # Invoke engine path (IP1)
        self.logger.info("SR: invoking engine (run_id=%s)", run_id)
        self._emit_obs(
            ObsEvent.now(
                event_kind="ENGINE_ATTEMPT_START",
                phase=ObsPhase.ENGINE,
                outcome=ObsOutcome.OK,
                severity=ObsSeverity.INFO,
                pins=self._obs_pins(canonical, run_id),
                policy_rev=plan.policy_rev,
            )
        )
        attempt_result = self._invoke_engine(run_handle, canonical, plan)
        self.logger.info(
            "SR: engine attempt finished (run_id=%s, outcome=%s, reason=%s)",
            run_id,
            attempt_result.outcome,
            attempt_result.reason_code,
        )
        self._emit_obs(
            ObsEvent.now(
                event_kind="ENGINE_ATTEMPT_FINISH",
                phase=ObsPhase.ENGINE,
                outcome=ObsOutcome.OK if attempt_result.outcome == "SUCCEEDED" else ObsOutcome.FAIL,
                severity=ObsSeverity.INFO if attempt_result.outcome == "SUCCEEDED" else ObsSeverity.ERROR,
                pins=self._obs_pins(canonical, run_id),
                policy_rev=plan.policy_rev,
                attempt_id=attempt_result.attempt_id,
                details={"reason_code": attempt_result.reason_code},
            )
        )
        if attempt_result.outcome != "SUCCEEDED":
            failure_bundle = EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=[],
                gate_receipts=[],
                reason=attempt_result.reason_code or "ENGINE_FAILED",
            )
            self._commit_terminal(run_handle, failure_bundle)
            self._emit_obs(
                ObsEvent.now(
                    event_kind="ENGINE_FAILED",
                    phase=ObsPhase.ENGINE,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins=self._obs_pins(canonical, run_id),
                    policy_rev=plan.policy_rev,
                    attempt_id=attempt_result.attempt_id,
                    details={"reason_code": attempt_result.reason_code},
                )
            )
            return self._response_from_status(run_id, "Engine attempt failed.")

        evidence = self._collect_evidence(canonical, plan, attempt_result)
        self.logger.info(
            "SR: evidence collection complete (run_id=%s, status=%s, reason=%s)",
            run_id,
            evidence.status.value,
            evidence.reason,
        )
        self._emit_obs(
            ObsEvent.now(
                event_kind="EVIDENCE_COMPLETE",
                phase=ObsPhase.EVIDENCE,
                outcome=self._obs_outcome(evidence.status),
                severity=ObsSeverity.INFO if evidence.status == EvidenceStatus.COMPLETE else ObsSeverity.WARN,
                pins=self._obs_pins(canonical, run_id),
                policy_rev=plan.policy_rev,
                details={"reason": evidence.reason},
            )
        )
        if evidence.status == EvidenceStatus.COMPLETE:
            return self._commit_ready(
                run_handle,
                canonical,
                plan,
                evidence,
                engine_run_root=attempt_result.engine_run_root,
            )
        if evidence.status == EvidenceStatus.WAITING:
            self._commit_waiting(run_handle, evidence)
            return self._response_from_status(run_id, "Evidence incomplete; waiting.")
        self._commit_terminal(run_handle, evidence)
        return self._response_from_status(run_id, "Evidence failed or conflicted.")

    def reemit(self, request: ReemitRequest) -> ReemitResponse:
        self.schemas.validate(
            "reemit_request.schema.yaml",
            request.model_dump(mode="json", exclude_none=True),
        )
        run_id = request.run_id
        if not is_authorized(
            request.requested_by,
            self.wiring.reemit_allowlist or self.wiring.auth_allowlist,
            self.wiring.auth_mode,
        ):
            self.ledger.append_record(
                run_id,
                self._event(
                    "AUTH_DENIED",
                    run_id,
                    {"invoker": request.requested_by or "unknown", "action": "reemit"},
                ),
            )
            self._emit_obs(
                ObsEvent.now(
                    event_kind="AUTH_DENIED",
                    phase=ObsPhase.REEMIT,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins={"run_id": run_id},
                    details={"action": "reemit"},
                )
            )
            return ReemitResponse(run_id=run_id, message="Unauthorized.")
        self._emit_obs(
            ObsEvent.now(
                event_kind="REEMIT_REQUESTED",
                phase=ObsPhase.REEMIT,
                outcome=ObsOutcome.OK,
                severity=ObsSeverity.INFO,
                pins={"run_id": run_id},
                details={"reemit_kind": request.reemit_kind.value},
            )
        )
        ops_lease_key = f"reemit:{run_id}:{request.reemit_kind.value}"
        ops_lease = LeaseManager(self.lease_manager.store, ttl_seconds=60)
        leader, lease_token = ops_lease.acquire(ops_lease_key, owner_id="sr-reemit")
        if not leader:
            self._emit_obs(
                ObsEvent.now(
                    event_kind="REEMIT_BUSY",
                    phase=ObsPhase.REEMIT,
                    outcome=ObsOutcome.SKIP,
                    severity=ObsSeverity.WARN,
                    pins={"run_id": run_id},
                )
            )
            return ReemitResponse(run_id=run_id, message="Reemit busy; another operator is active.")

        status = self.ledger.read_status(run_id)
        if status is None:
            self._emit_obs(
                ObsEvent.now(
                    event_kind="REEMIT_NOT_FOUND",
                    phase=ObsPhase.REEMIT,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins={"run_id": run_id},
                )
            )
            return ReemitResponse(run_id=run_id, message="Run not found.")
        request_details = {
            "reemit_kind": request.reemit_kind.value,
            "reason": request.reason,
            "requested_by": request.requested_by,
            "emit_platform_run_id": request.emit_platform_run_id,
        }
        request_event = self._event(
            "REEMIT_REQUESTED",
            run_id,
            {key: value for key, value in request_details.items() if value},
        )
        self.ledger.append_record(run_id, request_event)

        ready_allowed = request.reemit_kind in (ReemitKind.READY_ONLY, ReemitKind.BOTH)
        terminal_allowed = request.reemit_kind in (ReemitKind.TERMINAL_ONLY, ReemitKind.BOTH)
        source_ready_platform_run_id: str | None = None
        target_ready_platform_run_id: str | None = None
        reemit_scope_reason: str | None = None
        if ready_allowed and status.state == RunStatusState.READY and request.emit_platform_run_id:
            source_ready_platform_run_id, target_ready_platform_run_id, reemit_scope_reason = self._resolve_reemit_platform_scope(
                run_id,
                request,
            )
            if reemit_scope_reason:
                failure_event = self._event("REEMIT_FAILED", run_id, {"reason": reemit_scope_reason})
                self.ledger.append_record(run_id, failure_event)
                return ReemitResponse(
                    run_id=run_id,
                    status_state=status.state,
                    published=[],
                    message=self._reemit_scope_message(reemit_scope_reason),
                )
        if ready_allowed and status.state == RunStatusState.READY and not target_ready_platform_run_id:
            target_ready_platform_run_id = request.emit_platform_run_id

        if request.dry_run:
            would_publish: list[str] = []
            if ready_allowed and status.state == RunStatusState.READY:
                would_publish.append("READY")
            if terminal_allowed and status.state in (RunStatusState.FAILED, RunStatusState.QUARANTINED):
                would_publish.append("TERMINAL")
            self.ledger.append_record(
                run_id,
                self._event(
                    "REEMIT_DRY_RUN",
                    run_id,
                    {
                        "reemit_kind": request.reemit_kind.value,
                        "would_publish": would_publish,
                        "source_platform_run_id": source_ready_platform_run_id,
                        "target_platform_run_id": target_ready_platform_run_id,
                    },
                ),
            )
            message = "Dry-run complete; no publish performed."
            if not would_publish:
                message = "Dry-run complete; not applicable."
            return ReemitResponse(
                run_id=run_id,
                status_state=status.state,
                published=[],
                message=message,
            )

        if self._reemit_rate_limited(run_id):
            failure_event = self._event("REEMIT_FAILED", run_id, {"reason": "REEMIT_RATE_LIMIT"})
            self.ledger.append_record(run_id, failure_event)
            return ReemitResponse(run_id=run_id, status_state=status.state, message="Reemit rate limit exceeded.")

        if (
            ready_allowed
            and status.state == RunStatusState.READY
            and source_ready_platform_run_id
            and target_ready_platform_run_id
            and source_ready_platform_run_id != target_ready_platform_run_id
            and request.cross_run_override
        ):
            override = request.cross_run_override
            self._append_governance_fact(
                run_id,
                "GOV_REEMIT_OVERRIDE_APPROVED",
                {
                    "source_platform_run_id": source_ready_platform_run_id,
                    "target_platform_run_id": target_ready_platform_run_id,
                    "override_id": override.override_id,
                    "reason_code": override.reason_code,
                    "evidence_ref": override.evidence_ref,
                    "approved_by": override.approved_by,
                    "approved_at_utc": override.approved_at_utc.isoformat(),
                    "ticket_ref": override.ticket_ref,
                },
            )

        published: list[str] = []
        attempted = False
        if ready_allowed and status.state == RunStatusState.READY:
            attempted = True
            ready_key = self._reemit_ready(
                run_id,
                status,
                target_platform_run_id=target_ready_platform_run_id,
            )
            if ready_key:
                published.append(ready_key)
        if terminal_allowed and status.state in (RunStatusState.FAILED, RunStatusState.QUARANTINED):
            attempted = True
            terminal_key = self._reemit_terminal(run_id, status)
            if terminal_key:
                published.append(terminal_key)

        if not published:
            if attempted:
                self._emit_obs(
                    ObsEvent.now(
                        event_kind="REEMIT_FAILED",
                        phase=ObsPhase.REEMIT,
                        outcome=ObsOutcome.FAIL,
                        severity=ObsSeverity.ERROR,
                        pins={"run_id": run_id},
                    )
                )
                return ReemitResponse(run_id=run_id, status_state=status.state, published=[], message="Reemit failed.")
            reason = "REEMIT_NOT_APPLICABLE"
            if status.state == RunStatusState.READY and terminal_allowed:
                reason = "REEMIT_TERMINAL_ONLY_MISMATCH"
            elif status.state in (RunStatusState.FAILED, RunStatusState.QUARANTINED) and ready_allowed:
                reason = "REEMIT_READY_ONLY_MISMATCH"
            failure_event = self._event("REEMIT_FAILED", run_id, {"reason": reason})
            self.ledger.append_record(run_id, failure_event)
            self._emit_obs(
                ObsEvent.now(
                    event_kind="REEMIT_NOT_APPLICABLE",
                    phase=ObsPhase.REEMIT,
                    outcome=ObsOutcome.SKIP,
                    severity=ObsSeverity.WARN,
                    pins={"run_id": run_id},
                    details={"reason": reason},
                )
            )
            return ReemitResponse(run_id=run_id, status_state=status.state, published=[], message="Reemit not applicable.")

        return ReemitResponse(run_id=run_id, status_state=status.state, published=published, message="Reemit published.")

    def _resolve_reemit_platform_scope(
        self,
        run_id: str,
        request: ReemitRequest,
    ) -> tuple[str | None, str | None, str | None]:
        facts_view = self.ledger.read_facts_view(run_id)
        if facts_view is None:
            return None, request.emit_platform_run_id, "FACTS_VIEW_MISSING"
        pins = facts_view.get("pins") or {}
        source_platform_run_id = (
            facts_view.get("platform_run_id")
            or pins.get("platform_run_id")
            or self.platform_run_id
        )
        target_platform_run_id = request.emit_platform_run_id or source_platform_run_id
        if source_platform_run_id == target_platform_run_id:
            return source_platform_run_id, target_platform_run_id, None
        if not self.wiring.reemit_same_platform_run_only:
            return source_platform_run_id, target_platform_run_id, None
        if not self.wiring.reemit_cross_run_override_required:
            return source_platform_run_id, target_platform_run_id, None
        override = request.cross_run_override
        if override is None:
            return source_platform_run_id, target_platform_run_id, "CROSS_RUN_OVERRIDE_REQUIRED"
        allowlist = {value.strip().upper() for value in self.wiring.reemit_cross_run_reason_allowlist if value.strip()}
        if allowlist and override.reason_code.strip().upper() not in allowlist:
            return source_platform_run_id, target_platform_run_id, "CROSS_RUN_OVERRIDE_REASON_NOT_ALLOWED"
        return source_platform_run_id, target_platform_run_id, None

    def _reemit_scope_message(self, reason: str) -> str:
        if reason == "CROSS_RUN_OVERRIDE_REQUIRED":
            return "Cross-run reemit blocked; governance override evidence required."
        if reason == "CROSS_RUN_OVERRIDE_REASON_NOT_ALLOWED":
            return "Cross-run reemit blocked; override reason is not allowlisted."
        if reason == "FACTS_VIEW_MISSING":
            return "Reemit failed."
        return "Reemit failed."

    def _resolve_run_config_digest(
        self,
        *,
        plan: RunPlan | None = None,
        facts_view: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        if plan is not None:
            value = str(plan.policy_rev.get("content_digest") or "").strip()
            if value:
                return value, "run_plan.policy_rev.content_digest"
        if facts_view is not None:
            direct = str(facts_view.get("run_config_digest") or "").strip()
            if direct:
                return direct, "run_facts_view.run_config_digest"
            policy_value = str((facts_view.get("policy_rev") or {}).get("content_digest") or "").strip()
            if policy_value:
                return policy_value, "run_facts_view.policy_rev.content_digest"
        fallback = str(self.policy.content_digest or "").strip()
        return fallback, "scenario_runner.policy.content_digest"

    def _has_ambiguous_oracle_selector(self, value: str) -> bool:
        lowered = value.strip().lower()
        if not lowered:
            return False
        if "*" in lowered or "?" in lowered:
            return True
        ambiguous_tokens = ["/latest", "=latest", "/current", "=current"]
        return any(token in lowered for token in ambiguous_tokens)

    def _validate_oracle_scope(
        self,
        *,
        request_root: str | None,
        resolved_engine_root: str | None,
        scenario_id: str,
    ) -> str | None:
        acceptance_mode = str(self.wiring.acceptance_mode or "local_parity").strip().lower()
        if acceptance_mode != "dev_min_managed":
            return None
        pinned_engine_root = str(self.wiring.oracle_engine_run_root or "").strip()
        pinned_scenario_id = str(self.wiring.oracle_scenario_id or "").strip()
        pinned_stream_view_root = str(self.wiring.oracle_stream_view_root or "").strip()
        if not pinned_engine_root:
            return "ORACLE_ENGINE_RUN_ROOT_MISSING"
        if not pinned_scenario_id:
            return "ORACLE_SCENARIO_ID_MISSING"
        if not pinned_stream_view_root:
            return "ORACLE_STREAM_VIEW_ROOT_MISSING"
        if self._has_ambiguous_oracle_selector(pinned_engine_root):
            return "ORACLE_ENGINE_ROOT_AMBIGUOUS"
        if self._has_ambiguous_oracle_selector(pinned_stream_view_root):
            return "ORACLE_STREAM_VIEW_ROOT_AMBIGUOUS"
        if not pinned_engine_root.startswith("s3://"):
            return "ORACLE_ENGINE_ROOT_NOT_MANAGED"
        if not pinned_stream_view_root.startswith("s3://"):
            return "ORACLE_STREAM_VIEW_ROOT_NOT_MANAGED"
        effective_root = str(resolved_engine_root or "").strip()
        if not effective_root:
            return "ORACLE_ENGINE_ROOT_UNRESOLVED"
        if effective_root != pinned_engine_root:
            return "ORACLE_ENGINE_ROOT_MISMATCH"
        requested_root = str(request_root or "").strip()
        if requested_root and requested_root != pinned_engine_root:
            return "ORACLE_ENGINE_ROOT_REQUEST_MISMATCH"
        if scenario_id.strip() != pinned_scenario_id:
            return "ORACLE_SCENARIO_ID_MISMATCH"
        stream_prefix = f"{pinned_engine_root.rstrip('/')}/stream_view/"
        if not pinned_stream_view_root.startswith(stream_prefix):
            return "ORACLE_STREAM_VIEW_SCOPE_MISMATCH"
        return None

    def _validate_settlement_lock(self) -> None:
        acceptance_mode = str(self.wiring.acceptance_mode or "local_parity").strip().lower()
        if acceptance_mode != "dev_min_managed":
            return
        violations: list[str] = []
        if str(self.wiring.execution_mode or "").strip().lower() != "managed":
            violations.append("execution_mode must be managed")
        if str(self.wiring.state_mode or "").strip().lower() != "managed":
            violations.append("state_mode must be managed")
        if not str(self.wiring.execution_launch_ref or "").strip():
            violations.append("execution_launch_ref is required")
        identity_env = str(self.wiring.execution_identity_env or "").strip()
        if not identity_env:
            violations.append("execution_identity_env is required")
        else:
            identity_value = str(os.getenv(identity_env, "")).strip()
            if not identity_value:
                violations.append(f"{identity_env} must be set")
            else:
                self.execution_identity = identity_value
        if not str(self.wiring.object_store_root or "").strip().startswith("s3://"):
            violations.append("object_store_root must be s3:// for dev_min_managed")
        if str(self.wiring.control_bus_kind or "file").strip().lower() == "file":
            violations.append("control_bus_kind=file is not acceptance-valid for dev_min_managed")
        authority_dsn = str(self.wiring.authority_store_dsn or "").strip().lower()
        if not authority_dsn:
            violations.append("authority_store_dsn is required for dev_min_managed")
        elif authority_dsn.startswith("sqlite://"):
            violations.append("authority_store_dsn sqlite is not acceptance-valid for dev_min_managed")
        oracle_engine_run_root = str(self.wiring.oracle_engine_run_root or "").strip()
        oracle_scenario_id = str(self.wiring.oracle_scenario_id or "").strip()
        oracle_stream_view_root = str(self.wiring.oracle_stream_view_root or "").strip()
        if not oracle_engine_run_root:
            violations.append("oracle_engine_run_root is required for dev_min_managed")
        if not oracle_scenario_id:
            violations.append("oracle_scenario_id is required for dev_min_managed")
        if not oracle_stream_view_root:
            violations.append("oracle_stream_view_root is required for dev_min_managed")
        if oracle_engine_run_root and not oracle_engine_run_root.startswith("s3://"):
            violations.append("oracle_engine_run_root must be s3:// for dev_min_managed")
        if oracle_stream_view_root and not oracle_stream_view_root.startswith("s3://"):
            violations.append("oracle_stream_view_root must be s3:// for dev_min_managed")
        if oracle_engine_run_root and self._has_ambiguous_oracle_selector(oracle_engine_run_root):
            violations.append("oracle_engine_run_root cannot use latest/current/wildcard selectors")
        if oracle_stream_view_root and self._has_ambiguous_oracle_selector(oracle_stream_view_root):
            violations.append("oracle_stream_view_root cannot use latest/current/wildcard selectors")
        if (
            oracle_engine_run_root
            and oracle_stream_view_root
            and not oracle_stream_view_root.startswith(f"{oracle_engine_run_root.rstrip('/')}/stream_view/")
        ):
            violations.append("oracle_stream_view_root must be scoped under oracle_engine_run_root/stream_view/")
        if violations:
            raise RuntimeError("SR_SETTLEMENT_LOCK_FAIL_CLOSED: " + "; ".join(violations))

    def _build_control_bus(self, wiring: WiringProfile):
        kind = (wiring.control_bus_kind or "file").lower()
        if kind == "kinesis":
            if not wiring.control_bus_stream:
                raise RuntimeError("control_bus_stream required for kinesis")
            return KinesisControlBus(
                wiring.control_bus_stream,
                region=wiring.control_bus_region,
                endpoint_url=wiring.control_bus_endpoint_url,
            )
        if kind == "file":
            if not wiring.control_bus_root:
                raise RuntimeError("control_bus_root required for file bus")
            control_root = resolve_run_scoped_path(
                wiring.control_bus_root,
                suffix="control_bus",
                create_if_missing=True,
            )
            if not control_root:
                raise RuntimeError("control_bus_root resolution failed")
            return FileControlBus(Path(control_root))
        raise RuntimeError(f"unsupported control_bus_kind: {kind}")

    def _reemit_ready(
        self,
        run_id: str,
        status,
        *,
        target_platform_run_id: str | None = None,
    ) -> str | None:
        facts_view = self.ledger.read_facts_view(run_id)
        if facts_view is None:
            failure_event = self._event("REEMIT_FAILED", run_id, {"reason": "FACTS_VIEW_MISSING"})
            self.ledger.append_record(run_id, failure_event)
            return None
        bundle_hash = facts_view.get("bundle_hash")
        facts_view_hash = bundle_hash or self._hash_payload(facts_view)
        pins = facts_view.get("pins") or {}
        source_platform_run_id = facts_view.get("platform_run_id") or pins.get("platform_run_id") or self.platform_run_id
        platform_run_id = target_platform_run_id or source_platform_run_id
        scenario_run_id = facts_view.get("scenario_run_id") or pins.get("scenario_run_id") or run_id
        reemit_key = hash_payload(f"ready|{platform_run_id}|{scenario_run_id}|{facts_view_hash}")
        run_config_digest, _ = self._resolve_run_config_digest(facts_view=facts_view)
        ready_payload = {
            "run_id": run_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "facts_view_ref": status.facts_view_ref or f"{self.ledger.prefix}/run_facts_view/{run_id}.json",
            "bundle_hash": bundle_hash or facts_view_hash,
            "message_id": reemit_key,
            "run_config_digest": run_config_digest,
            "manifest_fingerprint": pins.get("manifest_fingerprint"),
            "parameter_hash": pins.get("parameter_hash"),
            "scenario_id": pins.get("scenario_id"),
            "emitted_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        oracle_pack_ref = facts_view.get("oracle_pack_ref")
        if oracle_pack_ref:
            ready_payload["oracle_pack_ref"] = oracle_pack_ref
        self.schemas.validate("run_ready_signal.schema.yaml", ready_payload)
        try:
            self.control_bus.publish(
                self.wiring.control_bus_topic,
                ready_payload,
                message_id=reemit_key,
                attributes={"kind": "READY_REEMIT", "run_id": run_id},
                partition_key=run_id,
            )
            publish_event = self._event("REEMIT_PUBLISHED", run_id, {"kind": "READY", "message_id": reemit_key})
            self.ledger.append_record(run_id, publish_event)
            self._append_governance_fact(
                run_id,
                "GOV_REEMIT_KEY",
                {"kind": "READY", "reemit_key": reemit_key},
            )
            self.logger.info("SR: re-emit READY published (run_id=%s, key=%s)", run_id, reemit_key)
            return reemit_key
        except Exception as exc:
            error_text = str(exc)[:512]
            failure_event = self._event(
                "REEMIT_FAILED",
                run_id,
                {"kind": "READY", "message_id": reemit_key, "error": error_text},
            )
            self.ledger.append_record(run_id, failure_event)
            self.logger.warning("SR: re-emit READY failed (run_id=%s, error=%s)", run_id, error_text)
            return None

    def _reemit_terminal(self, run_id: str, status) -> str | None:
        status_payload = status.model_dump(mode="json", exclude_none=True)
        status_hash = self._hash_payload(status_payload)
        reemit_key = hash_payload(f"terminal|{run_id}|{status.state.value}|{status_hash}")
        terminal_payload = {
            "run_id": run_id,
            "status_state": status.state.value,
            "status_ref": f"{self.ledger.prefix}/run_status/{run_id}.json",
            "record_ref": status.record_ref or f"{self.ledger.prefix}/run_record/{run_id}.jsonl",
            "reason_code": status.reason_code,
            "reemit_key": reemit_key,
            "emitted_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        self.schemas.validate("run_terminal_signal.schema.yaml", terminal_payload)
        try:
            self.control_bus.publish(
                self.wiring.control_bus_topic,
                terminal_payload,
                message_id=reemit_key,
                attributes={"kind": "TERMINAL_REEMIT", "run_id": run_id, "state": status.state.value},
                partition_key=run_id,
            )
            publish_event = self._event("REEMIT_PUBLISHED", run_id, {"kind": "TERMINAL", "message_id": reemit_key})
            self.ledger.append_record(run_id, publish_event)
            self._append_governance_fact(
                run_id,
                "GOV_REEMIT_KEY",
                {"kind": "TERMINAL", "reemit_key": reemit_key},
            )
            self.logger.info("SR: re-emit terminal published (run_id=%s, key=%s)", run_id, reemit_key)
            return reemit_key
        except Exception as exc:
            error_text = str(exc)[:512]
            failure_event = self._event(
                "REEMIT_FAILED",
                run_id,
                {"kind": "TERMINAL", "message_id": reemit_key, "error": error_text},
            )
            self.ledger.append_record(run_id, failure_event)
            self.logger.warning("SR: re-emit terminal failed (run_id=%s, error=%s)", run_id, error_text)
            return None

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
        self._append_governance_fact(
            run_handle.run_id,
            "GOV_POLICY_REV",
            plan.policy_rev,
        )
        self._append_governance_fact(
            run_handle.run_id,
            "GOV_PLAN_HASH",
            {"plan_hash": plan.plan_hash},
        )

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

        try:
            self.engine_schemas.validate("engine_invocation.schema.yaml", invocation)
        except ValueError:
            ended_at = datetime.now(tz=timezone.utc)
            duration_ms = int((time.monotonic() - started_mono) * 1000)
            attempt_payload: dict[str, Any] = {
                "run_id": run_handle.run_id,
                "attempt_id": attempt_id,
                "attempt_no": attempt_no,
                "invoker": intent.invoker or "sr-local",
                "outcome": "FAILED",
                "reason_code": "ENGINE_INVOCATION_INVALID",
                "started_at_utc": started_at.isoformat(),
                "ended_at_utc": ended_at.isoformat(),
                "duration_ms": duration_ms,
                "invocation": invocation,
            }
            self.schemas.validate("engine_attempt.schema.yaml", attempt_payload)
            finish_event = self._event("ENGINE_ATTEMPT_FINISHED", run_handle.run_id, attempt_payload)
            self.ledger.append_record(run_handle.run_id, finish_event)
            return EngineAttemptResult(
                run_id=run_handle.run_id,
                attempt_id=attempt_id,
                attempt_no=attempt_no,
                outcome="FAILED",
                reason_code="ENGINE_INVOCATION_INVALID",
                engine_run_root=intent.engine_run_root,
                invocation=invocation,
                duration_ms=duration_ms,
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
                engine_store = self._build_engine_store(engine_run_root)
                receipt_path = "run_receipt.json"
                if engine_store is None or not engine_store.exists(receipt_path):
                    outcome = "FAILED"
                    reason_code = "ENGINE_RECEIPT_MISSING"
                else:
                    try:
                        receipt_payload = json.loads(engine_store.read_text(receipt_path))
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
                            run_receipt_ref = self._engine_join(engine_run_root, receipt_path)

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
        engine_root = attempt.engine_run_root
        if engine_root is None:
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
        engine_store = self._build_engine_store(engine_root)
        if not engine_root or engine_store is None:
            return EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=[],
                gate_receipts=[],
                reason="ENGINE_ROOT_MISSING",
            )
        for output_id in plan.intended_outputs:
            entry = self.catalogue.get(output_id)
            output_path = self._render_template(entry.path_template, intent, plan.run_id)
            matches = self._resolve_engine_paths(engine_store, engine_root, output_path)
            if not matches:
                if entry.availability != "optional":
                    missing_outputs.append(output_id)
                else:
                    optional_missing.append(output_id)
                continue
            content_digest = self._compute_output_digest(engine_store, matches)
            pins = self._locator_pins(entry, intent, plan.run_id)
            locator = EngineOutputLocator(
                output_id=output_id,
                path=self._engine_join(engine_root, output_path),
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

        gate_verifier = GateVerifier(engine_root or "", self.gate_map, store=engine_store)
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
        *,
        engine_run_root: str | None,
    ) -> RunResponse:
        self._ensure_lease(run_handle)
        oracle_pack_ref, oracle_error = self._build_oracle_pack_ref(
            engine_run_root,
            intent,
            intended_outputs=plan.intended_outputs,
        )
        if oracle_error:
            failure_bundle = EvidenceBundle(
                status=EvidenceStatus.FAIL,
                locators=bundle.locators,
                gate_receipts=bundle.gate_receipts,
                instance_receipts=bundle.instance_receipts,
                bundle_hash=bundle.bundle_hash,
                reason=oracle_error,
                notes=bundle.notes,
            )
            self._commit_terminal(run_handle, failure_bundle)
            self._emit_obs(
                ObsEvent.now(
                    event_kind="ORACLE_PACK_INVALID",
                    phase=ObsPhase.COMMIT,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins=self._obs_pins(intent, plan.run_id),
                    policy_rev=plan.policy_rev,
                    details={"reason": oracle_error},
                )
            )
            return self._response_from_status(plan.run_id, "Oracle pack invalid; run failed.")
        run_config_digest, run_config_digest_source = self._resolve_run_config_digest(plan=plan)
        provenance = runtime_provenance(
            component="scenario_runner",
            environment=self.wiring.profile_id,
            config_revision=str(plan.policy_rev.get("revision") or self.policy.policy_rev),
            run_config_digest=run_config_digest,
        )
        facts_view = {
            "run_id": plan.run_id,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": plan.run_id,
            "pins": {
                "manifest_fingerprint": intent.manifest_fingerprint,
                "parameter_hash": intent.parameter_hash,
                "seed": intent.seed,
                "scenario_id": intent.scenario_id,
                "run_id": plan.run_id,
                "platform_run_id": self.platform_run_id,
                "scenario_run_id": plan.run_id,
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
            "run_config_digest": run_config_digest,
            "service_release_id": provenance["service_release_id"],
            "environment": provenance["environment"],
            "provenance": provenance,
            "plan_ref": f"{self.run_prefix}/sr/run_plan/{plan.run_id}.json",
            "record_ref": f"{self.run_prefix}/sr/run_record/{plan.run_id}.jsonl",
            "status_ref": f"{self.run_prefix}/sr/run_status/{plan.run_id}.json",
        }
        if oracle_pack_ref:
            facts_view["oracle_pack_ref"] = oracle_pack_ref
        if bundle.instance_receipts:
            facts_view["instance_receipts"] = bundle.instance_receipts
        if bundle.notes:
            facts_view["evidence_notes"] = bundle.notes
        self.ledger.commit_facts_view(plan.run_id, facts_view)
        event = self._event("READY_COMMITTED", plan.run_id, {"bundle_hash": bundle.bundle_hash})
        self.ledger.commit_ready(plan.run_id, event)
        self.logger.info("SR: READY committed (run_id=%s)", plan.run_id)
        self._emit_obs(
            ObsEvent.now(
                event_kind="READY_COMMITTED",
                phase=ObsPhase.COMMIT,
                outcome=ObsOutcome.OK,
                severity=ObsSeverity.INFO,
                pins=self._obs_pins(intent, plan.run_id),
                policy_rev=plan.policy_rev,
                details={"bundle_hash": bundle.bundle_hash},
            )
        )
        if bundle.bundle_hash:
            self._append_governance_fact(
                plan.run_id,
                "GOV_BUNDLE_HASH",
                {"bundle_hash": bundle.bundle_hash},
            )
        self._append_governance_fact(
            plan.run_id,
            "GOV_RUN_IDENTITY_SOURCES",
            {
                "platform_run_id_source": "scenario_runner.platform_run_id",
                "scenario_run_id_source": "run_plan.run_id",
                "run_config_digest_source": run_config_digest_source,
                "acceptance_mode": self.wiring.acceptance_mode,
                "execution_mode": self.wiring.execution_mode,
                "state_mode": self.wiring.state_mode,
            },
        )
        publish_key = self._ready_publish_key(
            self.platform_run_id,
            plan.run_id,
            bundle.bundle_hash,
            plan.plan_hash,
        )
        ready_payload = {
            "run_id": plan.run_id,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": plan.run_id,
            "facts_view_ref": f"{self.run_prefix}/sr/run_facts_view/{plan.run_id}.json",
            "bundle_hash": bundle.bundle_hash,
            "message_id": publish_key,
            "run_config_digest": run_config_digest,
            "service_release_id": provenance["service_release_id"],
            "environment": provenance["environment"],
            "provenance": provenance,
            "manifest_fingerprint": intent.manifest_fingerprint,
            "parameter_hash": intent.parameter_hash,
            "scenario_id": intent.scenario_id,
            "emitted_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        if oracle_pack_ref:
            ready_payload["oracle_pack_ref"] = oracle_pack_ref
        self.ledger.write_ready_signal(plan.run_id, ready_payload)
        try:
            self.control_bus.publish(
                self.wiring.control_bus_topic,
                ready_payload,
                message_id=publish_key,
                attributes={"kind": "READY", "run_id": plan.run_id},
                partition_key=plan.run_id,
            )
            publish_event = self._event("READY_PUBLISHED", plan.run_id, {"message_id": publish_key})
            self.ledger.append_record(plan.run_id, publish_event)
            narrative_logger.info(
                "SR READY published run_id=%s bundle_hash=%s message_id=%s",
                plan.run_id,
                bundle.bundle_hash,
                publish_key,
            )
            self._emit_obs(
                ObsEvent.now(
                    event_kind="READY_PUBLISHED",
                    phase=ObsPhase.COMMIT,
                    outcome=ObsOutcome.OK,
                    severity=ObsSeverity.INFO,
                    pins=self._obs_pins(intent, plan.run_id),
                    policy_rev=plan.policy_rev,
                    details={"message_id": publish_key},
                )
            )
        except Exception as exc:
            error_text = str(exc)[:512]
            fail_event = self._event("READY_PUBLISH_FAILED", plan.run_id, {"message_id": publish_key, "error": error_text})
            self.ledger.append_record(plan.run_id, fail_event)
            self.logger.warning("SR: READY publish failed (run_id=%s, error=%s)", plan.run_id, error_text)
            self._emit_obs(
                ObsEvent.now(
                    event_kind="READY_PUBLISH_FAILED",
                    phase=ObsPhase.COMMIT,
                    outcome=ObsOutcome.FAIL,
                    severity=ObsSeverity.ERROR,
                    pins=self._obs_pins(intent, plan.run_id),
                    policy_rev=plan.policy_rev,
                    details={"message_id": publish_key, "error": error_text},
                )
            )
        return self._response_from_status(plan.run_id, "READY committed")

    def _build_oracle_pack_ref(
        self,
        engine_run_root: str | None,
        intent: CanonicalRunIntent,
        *,
        intended_outputs: list[str] | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not engine_run_root:
            return None, None
        ref: dict[str, Any] = {"engine_run_root": engine_run_root}
        pinned_scenario_id = str(self.wiring.oracle_scenario_id or intent.scenario_id).strip()
        if pinned_scenario_id:
            ref["scenario_id"] = pinned_scenario_id
        stream_view_root = str(self.wiring.oracle_stream_view_root or "").strip()
        if stream_view_root:
            ref["stream_view_root"] = stream_view_root
            if intended_outputs:
                stream_refs: dict[str, str] = {}
                for output_id in sorted(set(intended_outputs)):
                    stream_refs[output_id] = f"{stream_view_root.rstrip('/')}/output_id={output_id}"
                ref["stream_view_output_refs"] = stream_refs
                stream_error = self._validate_stream_view_output_refs(
                    stream_view_root=stream_view_root,
                    output_ids=sorted(set(intended_outputs)),
                )
                if stream_error:
                    return None, stream_error
        engine_store = self._build_engine_store(engine_run_root)
        manifest_path = "_oracle_pack_manifest.json"
        if engine_store is None or not engine_store.exists(manifest_path):
            return ref, None
        try:
            payload = json.loads(engine_store.read_text(manifest_path))
            self.oracle_schemas.validate("oracle_pack_manifest.schema.yaml", payload)
        except (ValueError, json.JSONDecodeError) as exc:
            self.logger.warning("SR: oracle pack manifest invalid root=%s error=%s", engine_run_root, str(exc))
            return None, "ORACLE_PACK_INVALID"
        world_key = payload.get("world_key") or {}
        if world_key.get("manifest_fingerprint") != intent.manifest_fingerprint:
            return None, "ORACLE_PACK_MISMATCH"
        if world_key.get("parameter_hash") != intent.parameter_hash:
            return None, "ORACLE_PACK_MISMATCH"
        if world_key.get("scenario_id") != intent.scenario_id:
            return None, "ORACLE_PACK_MISMATCH"
        if int(world_key.get("seed", -1)) != int(intent.seed):
            return None, "ORACLE_PACK_MISMATCH"
        ref.update(
            {
                "oracle_pack_id": payload.get("oracle_pack_id"),
                "manifest_ref": self._engine_join(engine_run_root, manifest_path),
                "engine_release": payload.get("engine_release"),
            }
        )
        return ref, None

    def _validate_stream_view_output_refs(self, *, stream_view_root: str, output_ids: list[str]) -> str | None:
        acceptance_mode = str(self.wiring.acceptance_mode or "local_parity").strip().lower()
        if acceptance_mode != "dev_min_managed":
            return None
        stream_store = self._build_engine_store(stream_view_root)
        if stream_store is None:
            return "ORACLE_STREAM_VIEW_STORE_UNRESOLVED"
        for output_id in output_ids:
            prefix = f"output_id={output_id}"
            try:
                files = stream_store.list_files(prefix)
            except Exception:
                return f"ORACLE_STREAM_VIEW_LIST_FAILED:{output_id}"
            if not files:
                return f"ORACLE_STREAM_VIEW_OUTPUT_MISSING:{output_id}"
            normalized_files = [str(path).replace("\\", "/") for path in files]
            has_manifest = any(path.endswith("/_stream_view_manifest.json") for path in normalized_files)
            has_receipt = any(path.endswith("/_stream_sort_receipt.json") for path in normalized_files)
            has_parquet = any(path.endswith(".parquet") for path in normalized_files)
            if not has_manifest:
                return f"ORACLE_STREAM_VIEW_MANIFEST_MISSING:{output_id}"
            if not has_receipt:
                return f"ORACLE_STREAM_VIEW_RECEIPT_MISSING:{output_id}"
            if not has_parquet:
                return f"ORACLE_STREAM_VIEW_PARTS_MISSING:{output_id}"
        return None

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
        if state == RunStatusState.QUARANTINED:
            self._write_quarantine_record(run_handle.run_id, bundle)
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
            status_ref=f"{self.run_prefix}/sr/run_status/{run_id}.json",
            record_ref=f"{self.run_prefix}/sr/run_record/{run_id}.jsonl",
            facts_view_ref=f"{self.run_prefix}/sr/run_facts_view/{run_id}.json" if status and status.state == RunStatusState.READY else None,
            message=message,
        )

    def _event(self, kind: str, run_id: str, details: dict[str, Any]) -> dict[str, Any]:
        payload = {"event_kind": kind, "run_id": run_id, "details": details}
        event_id = hash_payload(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        payload["event_id"] = event_id
        payload["ts_utc"] = datetime.now(tz=timezone.utc).isoformat()
        return payload

    def _ready_publish_key(
        self,
        platform_run_id: str,
        scenario_run_id: str,
        bundle_hash: str | None,
        plan_hash: str,
    ) -> str:
        key_source = bundle_hash or plan_hash
        return hash_payload(f"ready|{platform_run_id}|{scenario_run_id}|{key_source}")

    def _hash_payload(self, payload: dict[str, Any]) -> str:
        return hash_payload(json.dumps(payload, sort_keys=True, ensure_ascii=True))

    def _obs_pins(self, intent: CanonicalRunIntent, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "platform_run_id": self.platform_run_id,
            "scenario_run_id": run_id,
            "manifest_fingerprint": intent.manifest_fingerprint,
            "parameter_hash": intent.parameter_hash,
            "seed": intent.seed,
            "scenario_id": intent.scenario_id,
        }

    def _obs_outcome(self, status: EvidenceStatus) -> ObsOutcome:
        if status == EvidenceStatus.COMPLETE:
            return ObsOutcome.OK
        if status == EvidenceStatus.WAITING:
            return ObsOutcome.WAITING
        if status == EvidenceStatus.CONFLICT:
            return ObsOutcome.CONFLICT
        return ObsOutcome.FAIL

    def _emit_obs(self, event: ObsEvent) -> None:
        if event.severity == ObsSeverity.DEBUG and os.getenv("SR_OBS_DROP_DEBUG", "true").lower() == "true":
            return
        try:
            self.obs_sink.emit(event)
        except Exception:
            return

    def _append_governance_fact(self, run_id: str, fact_kind: str, payload: dict[str, Any]) -> None:
        try:
            event = self._event(fact_kind, run_id, payload)
            self.ledger.append_record(run_id, event)
        except Exception as exc:
            self.logger.warning(
                "SR: governance fact append failed (run_id=%s, fact_kind=%s, error=%s)",
                run_id,
                fact_kind,
                str(exc)[:512],
            )

    def _write_quarantine_record(self, run_id: str, bundle: EvidenceBundle) -> None:
        payload = {
            "run_id": run_id,
            "reason": bundle.reason,
            "missing": bundle.missing,
            "record_ref": f"{self.ledger.prefix}/run_record/{run_id}.jsonl",
            "status_ref": f"{self.ledger.prefix}/run_status/{run_id}.json",
            "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        path = f"{self.ledger.prefix}/quarantine/{run_id}.json"
        try:
            self.store.write_json(path, payload)
        except Exception as exc:
            self.logger.warning("SR: quarantine write failed (run_id=%s, error=%s)", run_id, str(exc)[:512])

    def _reemit_rate_limited(self, run_id: str) -> bool:
        limit = self.wiring.reemit_rate_limit_max
        if limit is None or limit <= 0:
            return False
        window_seconds = max(1, self.wiring.reemit_rate_limit_window_seconds)
        cutoff = datetime.now(tz=timezone.utc).timestamp() - window_seconds
        events = self.ledger.read_record_events(run_id)
        recent = 0
        for event in events:
            if event.get("event_kind") != "REEMIT_PUBLISHED":
                continue
            ts = event.get("ts_utc")
            if not ts:
                continue
            try:
                ts_value = datetime.fromisoformat(ts).timestamp()
            except ValueError:
                continue
            if ts_value >= cutoff:
                recent += 1
        return recent >= limit

    def _render_template(self, template: str, intent: CanonicalRunIntent, run_id: str) -> str:
        rendered = template
        rendered = rendered.replace("{manifest_fingerprint}", intent.manifest_fingerprint)
        rendered = rendered.replace("{parameter_hash}", intent.parameter_hash)
        rendered = rendered.replace("{seed}", str(intent.seed))
        rendered = rendered.replace("{scenario_id}", intent.scenario_id)
        rendered = rendered.replace("{run_id}", run_id)
        return rendered

    def _compute_output_digest(self, store: Any, relative_paths: list[str]) -> str:
        hasher = hashlib.sha256()
        for rel in sorted(relative_paths):
            hasher.update(store.read_bytes(rel))
        return hasher.hexdigest()

    def _engine_join(self, engine_root: str | None, relative_path: str) -> str:
        if not engine_root:
            return relative_path
        if engine_root.startswith("s3://"):
            return f"{engine_root.rstrip('/')}/{relative_path.lstrip('/')}"
        return str(Path(engine_root) / relative_path)

    def _build_engine_store(self, engine_run_root: str | None) -> Any | None:
        if not engine_run_root:
            return None
        return build_object_store(
            engine_run_root,
            s3_endpoint_url=self.wiring.s3_endpoint_url,
            s3_region=self.wiring.s3_region,
            s3_path_style=self.wiring.s3_path_style,
        )

    def _resolve_engine_root(self, request_root: str | None) -> str | None:
        oracle_root = getattr(self.wiring, "oracle_engine_run_root", None)
        return oracle_root or request_root

    def _resolve_engine_paths(
        self, store: Any | None, engine_root: str | None, output_path: str
    ) -> list[str]:
        if store is None or engine_root is None:
            return []
        if not engine_root.startswith("s3://"):
            base = Path(engine_root) / output_path
            if "*" in output_path:
                matches = list(base.parent.glob(base.name))
                return [str(path.relative_to(Path(engine_root))) for path in matches if path.is_file()]
            if base.exists():
                if base.is_dir():
                    return [
                        str(path.relative_to(Path(engine_root)))
                        for path in base.rglob("*")
                        if path.is_file()
                    ]
                return [output_path]
            return []
        if "*" in output_path:
            parent = output_path.rsplit("/", 1)[0] if "/" in output_path else ""
            pattern = Path(output_path).name
            candidates = self._list_relative_files(store, engine_root, parent)
            matches = [name for name in candidates if fnmatch(name, pattern)]
            return [f"{parent}/{name}" if parent else name for name in matches]
        if store.exists(output_path):
            return [output_path]
        children = self._list_relative_files(store, engine_root, output_path)
        return [f"{output_path.rstrip('/')}/{name}" if output_path else name for name in children]

    def _list_relative_files(self, store: Any, engine_root: str, relative_dir: str) -> list[str]:
        files = store.list_files(relative_dir)
        if engine_root.startswith("s3://"):
            base = f"{engine_root.rstrip('/')}/{relative_dir.strip('/')}"
            if base and not base.endswith("/"):
                base += "/"
            rels: list[str] = []
            for uri in files:
                if not uri.startswith(base):
                    continue
                rel = uri[len(base):]
                if rel:
                    rels.append(rel)
            return rels
        base = Path(engine_root) / relative_dir
        rels = []
        for file_path in files:
            try:
                rels.append(str(Path(file_path).relative_to(base)))
            except ValueError:
                continue
        return rels

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
