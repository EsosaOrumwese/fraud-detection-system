from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from fraud_detection.action_layer.authz import authorize_intent, build_denied_outcome_payload
from fraud_detection.action_layer.checkpoints import CHECKPOINT_COMMITTED, ActionCheckpointGate
from fraud_detection.action_layer.contracts import ActionIntent, ActionOutcome
from fraud_detection.action_layer.execution import (
    EXECUTION_COMMITTED,
    ActionEffectExecutor,
    ActionExecutionEngine,
    ActionExecutionRequest,
    ActionExecutionResult,
    build_execution_outcome_payload,
)
from fraud_detection.action_layer.idempotency import AL_DROP_DUPLICATE, AL_EXECUTE, ActionIdempotencyGate
from fraud_detection.action_layer.policy import AlAuthzPolicy, AlPolicyBundle, load_policy_bundle
from fraud_detection.action_layer.publish import ActionLayerIgPublisher, PublishedOutcomeRecord, build_action_outcome_envelope
from fraud_detection.action_layer.replay import REPLAY_MATCH, REPLAY_NEW, ActionOutcomeReplayLedger
from fraud_detection.action_layer.storage import ActionLedgerStore, ActionOutcomeStore
from fraud_detection.decision_fabric.context import (
    CONTEXT_READY,
    ContextEvidence,
    DecisionBudgetSnapshot,
    DecisionContextResult,
)
from fraud_detection.decision_fabric.inlet import DecisionTriggerCandidate, SourceEbRef
from fraud_detection.decision_fabric.posture import DfPostureEnforcementResult, DfPostureStamp
from fraud_detection.decision_fabric.registry import RegistryPolicyRev, RegistryResolutionResult, RegistryScopeKey
from fraud_detection.decision_fabric.synthesis import DecisionSynthesizer
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev


@dataclass(frozen=True)
class _ParityProof:
    expected_events: int
    observed_outcomes: int
    publish_admit_total: int
    duplicate_drops: int
    effect_execution_calls: int
    status: str
    reasons: tuple[str, ...]
    artifact_path: str


class _Response:
    def __init__(self, *, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body, sort_keys=True)

    def json(self) -> dict[str, Any]:
        return dict(self._body)


class _Session:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, json: Mapping[str, Any], timeout: float, headers: Mapping[str, str]) -> _Response:
        payload = dict(json)
        self.requests.append(payload)
        event_id = str(payload.get("event_id") or "")
        return _Response(
            status_code=200,
            body={
                "decision": "ADMIT",
                "receipt": {"receipt_id": f"al_rcpt_{event_id}", "event_id": event_id},
                "receipt_ref": f"runs/fraud-platform/receipts/{event_id}.json",
            },
        )


class _CountingExecutor(ActionEffectExecutor):
    def __init__(self) -> None:
        self.calls: list[ActionExecutionRequest] = []

    def execute(self, request: ActionExecutionRequest) -> ActionExecutionResult:
        self.calls.append(request)
        return ActionExecutionResult(
            state=EXECUTION_COMMITTED,
            provider_code="OK",
            provider_ref=f"exec_{request.idempotency_token}",
            message="committed",
        )


def _candidate(index: int) -> DecisionTriggerCandidate:
    source_event_id = f"evt_{index:06d}"
    offset = str(1000 + index)
    return DecisionTriggerCandidate(
        source_event_id=source_event_id,
        event_class="traffic_fraud",
        payload_hash=f"{index:064x}"[-64:],
        source_event_type="transaction_fraud",
        schema_version="v1",
        source_ts_utc="2026-02-07T20:00:00.000000Z",
        pins={
            "platform_run_id": "platform_20260207T200000Z",
            "scenario_run_id": "a" * 32,
            "scenario_id": "fraud_synth_v1",
            "manifest_fingerprint": "b" * 64,
            "parameter_hash": "c" * 64,
            "seed": 7,
        },
        source_eb_ref=SourceEbRef(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset=offset,
            offset_kind="kinesis_sequence",
            published_at_utc="2026-02-07T20:00:01.000000Z",
        ),
    )


def _posture() -> DfPostureStamp:
    return DfPostureStamp(
        scope_key="scope=GLOBAL",
        mode="NORMAL",
        capabilities_mask=CapabilitiesMask(
            allow_ieg=True,
            allowed_feature_groups=("core_features",),
            allow_model_primary=True,
            allow_model_stage2=False,
            allow_fallback_heuristics=True,
            action_posture="NORMAL",
        ),
        policy_rev=PolicyRev(policy_id="dl.policy.v0", revision="r1", content_digest="d" * 64),
        posture_seq=10,
        decided_at_utc="2026-02-07T20:00:00.000000Z",
        source="CURRENT_POSTURE",
        trust_state="TRUSTED",
        served_at_utc="2026-02-07T20:00:00.100000Z",
        reasons=("DL_SOURCE:CURRENT_POSTURE",),
    )


def _context_result(candidate: DecisionTriggerCandidate) -> DecisionContextResult:
    return DecisionContextResult(
        status=CONTEXT_READY,
        reasons=(),
        budget=DecisionBudgetSnapshot(
            decision_deadline_ms=1500,
            join_wait_budget_ms=900,
            started_at_utc="2026-02-07T20:00:00.000000Z",
            now_utc="2026-02-07T20:00:00.050000Z",
            elapsed_ms=50,
            decision_remaining_ms=1450,
            join_wait_remaining_ms=850,
            decision_expired=False,
            join_wait_expired=False,
        ),
        enforcement=DfPostureEnforcementResult(
            blocked=False,
            reasons=(),
            allow_ieg=True,
            allowed_feature_groups=("core_features",),
            allow_model_primary=True,
            allow_model_stage2=False,
            allow_fallback_heuristics=True,
            action_posture="NORMAL",
        ),
        evidence=ContextEvidence(
            source_eb_ref=candidate.source_eb_ref.as_dict(),
            context_refs={"flow_anchor": {"topic": "fp.bus.context.flow_anchor.fraud.v1", "partition": 0, "offset": "90"}},
            ofp_snapshot_hash="f" * 64,
            ofp_eb_offset_basis={
                "stream": "fp.bus.traffic.fraud.v1",
                "offset_kind": "kinesis_sequence",
                "offsets": [{"partition": 0, "offset": str(candidate.source_eb_ref.offset)}],
                "basis_digest": "e" * 64,
            },
            graph_version={"version_id": "1" * 32, "watermark_ts_utc": "2026-02-07T20:00:00.000000Z"},
        ),
        ofp_snapshot={"snapshot_hash": "f" * 64},
        feature_group_versions={"core_features": "v1"},
        graph_version={"version_id": "1" * 32, "watermark_ts_utc": "2026-02-07T20:00:00.000000Z"},
    )


def _registry_result() -> RegistryResolutionResult:
    return RegistryResolutionResult(
        outcome="RESOLVED",
        scope_key=RegistryScopeKey(environment="local_parity", mode="fraud", bundle_slot="primary"),
        bundle_ref={"bundle_id": "9" * 64, "bundle_version": "v1", "registry_ref": "registry://active"},
        resolved_via="ACTIVE",
        reason_codes=("ACTIVE_BUNDLE_RESOLVED",),
        registry_event_id="reg_evt_1",
        compatibility={"compatible": True},
        policy_rev=RegistryPolicyRev(policy_id="df.registry_resolution.v0", revision="r1", content_digest="8" * 64),
        snapshot_digest="7" * 64,
        basis_digest="6" * 64,
    )


def _al_bundle_for_df_actions() -> AlPolicyBundle:
    base = load_policy_bundle(Path("config/platform/al/policy_v0.yaml"))
    action_kinds = tuple(sorted(set(base.authz.allowed_action_kinds + ("ALLOW", "STEP_UP", "QUEUE_REVIEW"))))
    return AlPolicyBundle(
        version=base.version,
        policy_rev=base.policy_rev,
        execution_posture=base.execution_posture,
        authz=AlAuthzPolicy(
            allowed_origins=base.authz.allowed_origins,
            allowed_action_kinds=action_kinds,
            actor_principal_prefix_allowlist=base.authz.actor_principal_prefix_allowlist,
        ),
        retry_policy=base.retry_policy,
    )


def _process_action_intent(
    *,
    intent_payload: Mapping[str, Any],
    run_index: int,
    idempotency: ActionIdempotencyGate,
    bundle: AlPolicyBundle,
    executor: _CountingExecutor,
    publisher: ActionLayerIgPublisher,
    outcomes: ActionOutcomeStore,
    checkpoints: ActionCheckpointGate,
    replay: ActionOutcomeReplayLedger,
) -> tuple[str, dict[str, Any] | None, PublishedOutcomeRecord | None]:
    intent = ActionIntent.from_payload(intent_payload)
    seen_at = f"2026-02-07T20:00:{run_index % 60:02d}.000000Z"
    idempotency_decision = idempotency.evaluate(intent=intent, first_seen_at_utc=seen_at)
    if idempotency_decision.disposition == AL_DROP_DUPLICATE:
        return "DROPPED_DUPLICATE", None, None
    if idempotency_decision.disposition != AL_EXECUTE:
        raise AssertionError(f"unexpected idempotency disposition: {idempotency_decision.disposition}")

    authz_decision = authorize_intent(intent, bundle=bundle)
    if authz_decision.allowed:
        engine = ActionExecutionEngine(executor=executor, retry_policy=bundle.retry_policy, sleeper=lambda _: None)
        terminal = engine.execute(intent=intent, semantic_key=idempotency_decision.semantic_key)
        outcome_payload = build_execution_outcome_payload(
            intent=intent,
            authz_policy_rev=bundle.policy_rev.as_dict(),
            terminal=terminal,
            posture_mode=bundle.execution_posture.mode,
            completed_at_utc=f"2026-02-07T20:01:{run_index % 60:02d}.000000Z",
        )
    else:
        outcome_payload = build_denied_outcome_payload(
            intent=intent,
            decision=authz_decision,
            completed_at_utc=f"2026-02-07T20:01:{run_index % 60:02d}.000000Z",
        )

    outcome = ActionOutcome.from_payload(outcome_payload)
    append_result = outcomes.register_outcome(
        outcome_payload=outcome.as_dict(),
        recorded_at_utc=f"2026-02-07T20:02:{run_index % 60:02d}.000000Z",
    )
    assert append_result.status in {"NEW", "DUPLICATE"}
    envelope = build_action_outcome_envelope(outcome)
    published = publisher.publish_envelope(envelope)
    assert published.decision == "ADMIT"
    publish_write = outcomes.register_publish_result(
        outcome_id=outcome.outcome_id,
        event_id=published.event_id,
        event_type=published.event_type,
        publish_decision=published.decision,
        receipt=published.receipt,
        receipt_ref=published.receipt_ref,
        reason_code=published.reason_code,
        published_at_utc=f"2026-02-07T20:03:{run_index % 60:02d}.000000Z",
    )
    assert publish_write.status in {"NEW", "DUPLICATE"}

    token = checkpoints.issue_token(
        outcome_id=outcome.outcome_id,
        action_id=str(outcome.payload["action_id"]),
        decision_id=str(outcome.payload["decision_id"]),
        issued_at_utc=f"2026-02-07T20:04:{run_index % 60:02d}.000000Z",
    )
    checkpoints.mark_outcome_appended(token_id=token.token_id, outcome_hash=append_result.record.payload_hash)
    checkpoints.mark_publish_result(
        token_id=token.token_id,
        publish_decision=published.decision,
        receipt_ref=published.receipt_ref,
        reason_code=published.reason_code,
    )
    committed = checkpoints.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref={
            "topic": "fp.bus.traffic.fraud.v1",
            "partition": 0,
            "offset": str(1000 + run_index),
        },
        committed_at_utc=f"2026-02-07T20:05:{run_index % 60:02d}.000000Z",
    )
    assert committed.status == CHECKPOINT_COMMITTED

    replay_result = replay.register_outcome(
        outcome_payload=outcome.as_dict(),
        observed_at_utc=f"2026-02-07T20:06:{run_index % 60:02d}.000000Z",
    )
    assert replay_result.outcome in {REPLAY_NEW, REPLAY_MATCH}
    return "PROCESSED", outcome.as_dict(), published


def test_phase8_df_to_al_execution_and_outcome_continuity(tmp_path: Path) -> None:
    synthesizer = DecisionSynthesizer()
    candidate = _candidate(1)
    artifacts = synthesizer.synthesize(
        candidate=candidate,
        posture=_posture(),
        registry_result=_registry_result(),
        context_result=_context_result(candidate),
        run_config_digest="5" * 64,
        decided_at_utc="2026-02-07T20:00:00.100000Z",
        requested_at_utc="2026-02-07T20:00:00.100000Z",
    )
    action_intent = dict(artifacts.action_intents[0])
    assert action_intent["decision_id"] == artifacts.decision_payload["decision_id"]

    session = _Session()
    publisher = ActionLayerIgPublisher(
        ig_ingest_url="http://example.invalid",
        timeout_seconds=0.1,
        max_attempts=1,
        session=session,
    )
    idempotency = ActionIdempotencyGate(store=ActionLedgerStore(locator=str(tmp_path / "phase8_ledger.sqlite")))
    outcomes = ActionOutcomeStore(locator=str(tmp_path / "phase8_outcomes.sqlite"))
    checkpoints = ActionCheckpointGate(tmp_path / "phase8_checkpoints.sqlite")
    replay = ActionOutcomeReplayLedger(tmp_path / "phase8_replay.sqlite")
    bundle = _al_bundle_for_df_actions()
    executor = _CountingExecutor()

    status, outcome_payload, published = _process_action_intent(
        intent_payload=action_intent,
        run_index=1,
        idempotency=idempotency,
        bundle=bundle,
        executor=executor,
        publisher=publisher,
        outcomes=outcomes,
        checkpoints=checkpoints,
        replay=replay,
    )
    assert status == "PROCESSED"
    assert outcome_payload is not None
    assert published is not None
    assert outcome_payload["decision_id"] == artifacts.decision_payload["decision_id"]
    assert published.event_type == "action_outcome"
    assert len(executor.calls) == 1
    assert session.requests[0]["parent_event_id"] == artifacts.decision_payload["decision_id"]


@pytest.mark.parametrize("event_count", [20, 200])
def test_phase8_component_local_parity_proof(event_count: int, tmp_path: Path) -> None:
    synthesizer = DecisionSynthesizer()
    session = _Session()
    publisher = ActionLayerIgPublisher(
        ig_ingest_url="http://example.invalid",
        timeout_seconds=0.1,
        max_attempts=1,
        session=session,
    )
    idempotency = ActionIdempotencyGate(store=ActionLedgerStore(locator=str(tmp_path / "phase8_ledger.sqlite")))
    outcomes = ActionOutcomeStore(locator=str(tmp_path / "phase8_outcomes.sqlite"))
    checkpoints = ActionCheckpointGate(tmp_path / "phase8_checkpoints.sqlite")
    replay = ActionOutcomeReplayLedger(tmp_path / "phase8_replay.sqlite")
    bundle = _al_bundle_for_df_actions()
    executor = _CountingExecutor()

    produced_outcomes: list[dict[str, Any]] = []
    produced_intents: list[dict[str, Any]] = []
    duplicate_drops = 0
    for index in range(event_count):
        candidate = _candidate(index)
        artifacts = synthesizer.synthesize(
            candidate=candidate,
            posture=_posture(),
            registry_result=_registry_result(),
            context_result=_context_result(candidate),
            run_config_digest="5" * 64,
            decided_at_utc="2026-02-07T20:00:00.100000Z",
            requested_at_utc="2026-02-07T20:00:00.100000Z",
        )
        status, outcome_payload, published = _process_action_intent(
            intent_payload=artifacts.action_intents[0],
            run_index=index,
            idempotency=idempotency,
            bundle=bundle,
            executor=executor,
            publisher=publisher,
            outcomes=outcomes,
            checkpoints=checkpoints,
            replay=replay,
        )
        assert status == "PROCESSED"
        assert outcome_payload is not None
        assert published is not None
        produced_outcomes.append(outcome_payload)
        produced_intents.append(dict(artifacts.action_intents[0]))

    for index, intent_payload in enumerate(produced_intents):
        status, _, _ = _process_action_intent(
            intent_payload=intent_payload,
            run_index=event_count + index,
            idempotency=idempotency,
            bundle=bundle,
            executor=executor,
            publisher=publisher,
            outcomes=outcomes,
            checkpoints=checkpoints,
            replay=replay,
        )
        if status == "DROPPED_DUPLICATE":
            duplicate_drops += 1

    original_chain = replay.identity_chain_hash()
    reopened = ActionOutcomeReplayLedger(tmp_path / "phase8_replay.sqlite")
    for index, payload in enumerate(produced_outcomes):
        replayed = reopened.register_outcome(
            outcome_payload=payload,
            observed_at_utc=f"2026-02-07T20:08:{index % 60:02d}.000000Z",
        )
        assert replayed.outcome == REPLAY_MATCH
    reopened_chain = reopened.identity_chain_hash()
    assert original_chain == reopened_chain

    platform_run_id = str(produced_outcomes[0]["pins"]["platform_run_id"]) if produced_outcomes else "platform_unknown"
    artifact_dir = Path("runs/fraud-platform") / platform_run_id / "action_layer" / "reconciliation"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"phase8_parity_proof_{event_count}.json"

    reasons: list[str] = []
    observed_outcomes = len(produced_outcomes)
    publish_admit_total = len(session.requests)
    if observed_outcomes != event_count:
        reasons.append(f"OBSERVED_MISMATCH:{observed_outcomes}:{event_count}")
    if publish_admit_total != event_count:
        reasons.append(f"PUBLISH_ADMIT_MISMATCH:{publish_admit_total}:{event_count}")
    if duplicate_drops != event_count:
        reasons.append(f"DUPLICATE_DROP_MISMATCH:{duplicate_drops}:{event_count}")
    if len(executor.calls) != event_count:
        reasons.append(f"EFFECT_CALL_MISMATCH:{len(executor.calls)}:{event_count}")

    proof = _ParityProof(
        expected_events=event_count,
        observed_outcomes=observed_outcomes,
        publish_admit_total=publish_admit_total,
        duplicate_drops=duplicate_drops,
        effect_execution_calls=len(executor.calls),
        status="PASS" if not reasons else "FAIL",
        reasons=tuple(reasons),
        artifact_path=str(artifact_path),
    )
    artifact_path.write_text(
        json.dumps(
            {
                "expected_events": proof.expected_events,
                "observed_outcomes": proof.observed_outcomes,
                "publish_admit_total": proof.publish_admit_total,
                "duplicate_drops": proof.duplicate_drops,
                "effect_execution_calls": proof.effect_execution_calls,
                "status": proof.status,
                "reasons": list(proof.reasons),
                "artifact_path": proof.artifact_path,
            },
            sort_keys=True,
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert proof.status == "PASS"
