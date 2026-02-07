from __future__ import annotations

import copy
import json

from fraud_detection.decision_fabric.context import (
    CONTEXT_READY,
    ContextEvidence,
    DecisionBudgetSnapshot,
    DecisionContextResult,
)
from fraud_detection.decision_fabric.inlet import DecisionTriggerCandidate, SourceEbRef
from fraud_detection.decision_fabric.posture import DfPostureEnforcementResult, DfPostureStamp
from fraud_detection.decision_fabric.registry import RegistryPolicyRev, RegistryResolutionResult, RegistryScopeKey
from fraud_detection.decision_fabric.synthesis import ACTION_STEP_UP, DecisionSynthesizer
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev


def _candidate() -> DecisionTriggerCandidate:
    return DecisionTriggerCandidate(
        source_event_id="evt_001",
        source_event_type="transaction_fraud",
        schema_version="v1",
        source_ts_utc="2026-02-07T11:00:00.000000Z",
        pins={
            "platform_run_id": "platform_20260207T110000Z",
            "scenario_run_id": "a" * 32,
            "scenario_id": "fraud_synth_v1",
            "manifest_fingerprint": "b" * 64,
            "parameter_hash": "c" * 64,
            "seed": 7,
        },
        source_eb_ref=SourceEbRef(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="100",
            offset_kind="kinesis_sequence",
            published_at_utc="2026-02-07T11:00:01.000000Z",
        ),
    )


def _posture(action_posture: str = "NORMAL") -> DfPostureStamp:
    return DfPostureStamp(
        scope_key="scope=GLOBAL",
        mode="NORMAL",
        capabilities_mask=CapabilitiesMask(
            allow_ieg=True,
            allowed_feature_groups=("core_features",),
            allow_model_primary=True,
            allow_model_stage2=False,
            allow_fallback_heuristics=True,
            action_posture=action_posture,
        ),
        policy_rev=PolicyRev(policy_id="dl.policy.v0", revision="r1", content_digest="d" * 64),
        posture_seq=10,
        decided_at_utc="2026-02-07T11:00:00.000000Z",
        source="CURRENT_POSTURE",
        trust_state="TRUSTED",
        served_at_utc="2026-02-07T11:00:00.100000Z",
        reasons=("DL_SOURCE:CURRENT_POSTURE",),
    )


def _context_result() -> DecisionContextResult:
    return DecisionContextResult(
        status=CONTEXT_READY,
        reasons=(),
        budget=DecisionBudgetSnapshot(
            decision_deadline_ms=1500,
            join_wait_budget_ms=900,
            started_at_utc="2026-02-07T11:00:00.000000Z",
            now_utc="2026-02-07T11:00:00.050000Z",
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
            source_eb_ref=_candidate().source_eb_ref.as_dict(),
            context_refs={"flow_anchor": {"topic": "fp.bus.context.flow_anchor.fraud.v1", "partition": 0, "offset": "90"}},
            ofp_snapshot_hash="f" * 64,
            ofp_eb_offset_basis={
                "stream": "fp.bus.traffic.fraud.v1",
                "offset_kind": "kinesis_sequence",
                "offsets": [{"partition": 0, "offset": "100"}],
                "basis_digest": "e" * 64,
            },
            graph_version={"version_id": "1" * 32, "watermark_ts_utc": "2026-02-07T11:00:00.000000Z"},
        ),
        ofp_snapshot={"snapshot_hash": "f" * 64},
        feature_group_versions={"core_features": "v1"},
        graph_version={"version_id": "1" * 32, "watermark_ts_utc": "2026-02-07T11:00:00.000000Z"},
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


def test_synthesis_is_deterministic_for_fixed_basis() -> None:
    synthesizer = DecisionSynthesizer()
    first = synthesizer.synthesize(
        candidate=_candidate(),
        posture=_posture(),
        registry_result=_registry_result(),
        context_result=_context_result(),
        run_config_digest="5" * 64,
        decided_at_utc="2026-02-07T11:00:00.100000Z",
        requested_at_utc="2026-02-07T11:00:00.100000Z",
    )
    second = synthesizer.synthesize(
        candidate=_candidate(),
        posture=_posture(),
        registry_result=_registry_result(),
        context_result=_context_result(),
        run_config_digest="5" * 64,
        decided_at_utc="2026-02-07T11:00:00.100000Z",
        requested_at_utc="2026-02-07T11:00:00.100000Z",
    )
    assert json.dumps(first.decision_payload, sort_keys=True) == json.dumps(second.decision_payload, sort_keys=True)
    assert json.dumps(first.action_intents, sort_keys=True) == json.dumps(second.action_intents, sort_keys=True)
    assert first.decision_envelope["event_id"] == second.decision_envelope["event_id"]


def test_action_posture_is_clamped_when_step_up_only() -> None:
    synthesizer = DecisionSynthesizer()
    artifacts = synthesizer.synthesize(
        candidate=_candidate(),
        posture=_posture(action_posture="STEP_UP_ONLY"),
        registry_result=_registry_result(),
        context_result=_context_result(),
        run_config_digest="5" * 64,
        decided_at_utc="2026-02-07T11:00:00.100000Z",
        requested_at_utc="2026-02-07T11:00:00.100000Z",
    )
    assert artifacts.decision_payload["decision"]["action_kind"] == ACTION_STEP_UP
    assert "ACTION_POSTURE_CLAMPED:STEP_UP_ONLY" in artifacts.decision_payload["reason_codes"]
    assert artifacts.action_intents[0]["action_kind"] == ACTION_STEP_UP


def test_correction_is_append_only_with_supersede_link() -> None:
    synthesizer = DecisionSynthesizer()
    artifacts = synthesizer.synthesize(
        candidate=_candidate(),
        posture=_posture(),
        registry_result=_registry_result(),
        context_result=_context_result(),
        run_config_digest="5" * 64,
        decided_at_utc="2026-02-07T11:00:00.100000Z",
        requested_at_utc="2026-02-07T11:00:00.100000Z",
    )
    original = copy.deepcopy(artifacts.decision_payload)
    corrected = synthesizer.build_correction(
        original_decision_payload=artifacts.decision_payload,
        corrected_decision_fragment={"action_kind": ACTION_STEP_UP},
        correction_reason="manual_adjustment",
        corrected_at_utc="2026-02-07T11:00:05.000000Z",
        decision_scope="fraud.primary",
    )
    assert artifacts.decision_payload == original
    assert corrected["decision_id"] != original["decision_id"]
    assert corrected["decision"]["supersedes_decision_id"] == original["decision_id"]
    assert "CORRECTION" in corrected["reason_codes"]
