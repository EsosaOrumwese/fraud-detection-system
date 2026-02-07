from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.decision_fabric.checkpoints import CHECKPOINT_COMMITTED, DecisionCheckpointGate
from fraud_detection.decision_fabric.context import (
    CONTEXT_READY,
    ContextEvidence,
    DecisionBudgetSnapshot,
    DecisionContextResult,
)
from fraud_detection.decision_fabric.inlet import DecisionTriggerCandidate, SourceEbRef
from fraud_detection.decision_fabric.observability import DfRunMetrics
from fraud_detection.decision_fabric.posture import DfPostureEnforcementResult, DfPostureStamp
from fraud_detection.decision_fabric.reconciliation import DfReconciliationBuilder
from fraud_detection.decision_fabric.replay import REPLAY_NEW, DecisionReplayLedger
from fraud_detection.decision_fabric.synthesis import DecisionSynthesizer
from fraud_detection.decision_fabric.registry import RegistryPolicyRev, RegistryResolutionResult, RegistryScopeKey
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev


def _candidate(index: int) -> DecisionTriggerCandidate:
    source_event_id = f"evt_{index:06d}"
    offset = str(1000 + index)
    return DecisionTriggerCandidate(
        source_event_id=source_event_id,
        source_event_type="transaction_fraud",
        schema_version="v1",
        source_ts_utc="2026-02-07T14:00:00.000000Z",
        pins={
            "platform_run_id": "platform_20260207T140000Z",
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
            published_at_utc="2026-02-07T14:00:01.000000Z",
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
        decided_at_utc="2026-02-07T14:00:00.000000Z",
        source="CURRENT_POSTURE",
        trust_state="TRUSTED",
        served_at_utc="2026-02-07T14:00:00.100000Z",
        reasons=("DL_SOURCE:CURRENT_POSTURE",),
    )


def _context_result() -> DecisionContextResult:
    candidate = _candidate(0)
    return DecisionContextResult(
        status=CONTEXT_READY,
        reasons=(),
        budget=DecisionBudgetSnapshot(
            decision_deadline_ms=1500,
            join_wait_budget_ms=900,
            started_at_utc="2026-02-07T14:00:00.000000Z",
            now_utc="2026-02-07T14:00:00.050000Z",
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
                "offsets": [{"partition": 0, "offset": "100"}],
                "basis_digest": "e" * 64,
            },
            graph_version={"version_id": "1" * 32, "watermark_ts_utc": "2026-02-07T14:00:00.000000Z"},
        ),
        ofp_snapshot={"snapshot_hash": "f" * 64},
        feature_group_versions={"core_features": "v1"},
        graph_version={"version_id": "1" * 32, "watermark_ts_utc": "2026-02-07T14:00:00.000000Z"},
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


@pytest.mark.parametrize("event_count", [20, 200])
def test_phase8_component_local_parity_proof(event_count: int, tmp_path: Path) -> None:
    replay = DecisionReplayLedger(tmp_path / "replay.sqlite")
    checkpoints = DecisionCheckpointGate(tmp_path / "checkpoints.sqlite")
    metrics = DfRunMetrics(
        platform_run_id="platform_20260207T140000Z",
        scenario_run_id="a" * 32,
    )
    reconciliation = DfReconciliationBuilder(
        platform_run_id="platform_20260207T140000Z",
        scenario_run_id="a" * 32,
    )
    synthesizer = DecisionSynthesizer()

    for index in range(event_count):
        candidate = _candidate(index)
        artifacts = synthesizer.synthesize(
            candidate=candidate,
            posture=_posture(),
            registry_result=_registry_result(),
            context_result=_context_result(),
            run_config_digest="5" * 64,
            decided_at_utc="2026-02-07T14:00:00.100000Z",
            requested_at_utc="2026-02-07T14:00:00.100000Z",
        )
        replay_result = replay.register_decision(
            decision_payload=artifacts.decision_payload,
            observed_at_utc="2026-02-07T14:00:00.200000Z",
        )
        assert replay_result.outcome == REPLAY_NEW

        token = checkpoints.issue_token(
            source_event_id=candidate.source_event_id,
            decision_id=artifacts.decision_payload["decision_id"],
            issued_at_utc="2026-02-07T14:00:00.250000Z",
        )
        checkpoints.mark_ledger_committed(token_id=token.token_id)
        checkpoints.mark_publish_result(
            token_id=token.token_id,
            decision_publish="ADMIT",
            action_publishes=("ADMIT",),
            halted=False,
            halt_reason=None,
        )
        commit_result = checkpoints.commit_checkpoint(
            token_id=token.token_id,
            checkpoint_ref={
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": str(1000 + index),
            },
            committed_at_utc="2026-02-07T14:00:00.300000Z",
        )
        assert commit_result.status == CHECKPOINT_COMMITTED

        metrics.record_decision(
            decision_payload=artifacts.decision_payload,
            latency_ms=10.0 + float(index % 7),
            publish_decision="ADMIT",
        )
        reconciliation.add_record(
            decision_payload=artifacts.decision_payload,
            action_intents=tuple(artifacts.action_intents),
            publish_decision="ADMIT",
            decision_receipt_ref=f"runs/fraud-platform/platform_20260207T140000Z/ingestion_gate/receipts/dec_{index}.json",
            action_receipt_refs=(
                f"runs/fraud-platform/platform_20260207T140000Z/ingestion_gate/receipts/act_{index}.json",
            ),
        )

    metrics_snapshot = metrics.snapshot(generated_at_utc="2026-02-07T14:01:00.000000Z")
    assert metrics_snapshot["metrics"]["decisions_total"] == event_count
    assert metrics_snapshot["metrics"]["publish_admit_total"] == event_count
    assert metrics_snapshot["latency_ms"]["count"] == event_count

    recon_summary = reconciliation.summary(generated_at_utc="2026-02-07T14:01:00.000000Z")
    assert recon_summary["totals"]["decisions_total"] == event_count
    assert recon_summary["totals"]["quarantined_total"] == 0
    proof = reconciliation.parity_proof(expected_events=event_count)
    assert proof.status == "PASS"
