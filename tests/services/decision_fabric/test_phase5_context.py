from __future__ import annotations

from pathlib import Path

from fraud_detection.decision_fabric.context import (
    CONTEXT_BLOCKED,
    CONTEXT_MISSING,
    CONTEXT_READY,
    CONTEXT_WAITING,
    DECISION_DEADLINE_EXCEEDED,
    DecisionContextAcquirer,
    DecisionContextPolicy,
)
from fraud_detection.decision_fabric.inlet import DecisionTriggerCandidate, SourceEbRef
from fraud_detection.decision_fabric.posture import DfPostureStamp
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, PolicyRev


class StubOfpClient:
    def __init__(self, snapshot: dict[str, object] | None = None) -> None:
        self.snapshot = snapshot or {}
        self.last_payload: dict[str, object] | None = None

    def get_features(self, payload: dict[str, object]) -> dict[str, object]:
        self.last_payload = payload
        return {"status": "OK", "snapshot": dict(self.snapshot)}


class RaisingOfpClient:
    def get_features(self, payload: dict[str, object]) -> dict[str, object]:
        raise AssertionError("OFP should not be called")


def _policy() -> DecisionContextPolicy:
    return DecisionContextPolicy.load(Path("config/platform/df/context_policy_v0.yaml"))


def _candidate() -> DecisionTriggerCandidate:
    return DecisionTriggerCandidate(
        source_event_id="evt_001",
        event_class="traffic_fraud",
        payload_hash="f" * 64,
        source_event_type="transaction_fraud",
        schema_version="v1",
        source_ts_utc="2026-02-07T11:00:00Z",
        pins={
            "platform_run_id": "platform_20260207T110000Z",
            "scenario_run_id": "a" * 32,
            "scenario_id": "fraud_synth_v1",
            "manifest_fingerprint": "b" * 64,
            "parameter_hash": "c" * 64,
            "seed": 123,
        },
        source_eb_ref=SourceEbRef(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="100",
            offset_kind="kinesis_sequence",
            published_at_utc="2026-02-07T11:00:01Z",
        ),
    )


def _posture(*, allow_ieg: bool, allowed_feature_groups: tuple[str, ...]) -> DfPostureStamp:
    return DfPostureStamp(
        scope_key="env:local_parity",
        mode="NORMAL",
        capabilities_mask=CapabilitiesMask(
            allow_ieg=allow_ieg,
            allowed_feature_groups=allowed_feature_groups,
            allow_model_primary=True,
            allow_model_stage2=False,
            allow_fallback_heuristics=True,
            action_posture="NORMAL",
        ),
        policy_rev=PolicyRev(policy_id="dl.policy.v0", revision="r1"),
        posture_seq=1,
        decided_at_utc="2026-02-07T11:00:00Z",
        source="DL",
        trust_state="TRUSTED",
        served_at_utc="2026-02-07T11:00:00Z",
        reasons=(),
    )


def _ofp_snapshot() -> dict[str, object]:
    return {
        "snapshot_hash": "d" * 64,
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "100"}],
        },
        "pins": _candidate().pins,
        "created_at_utc": "2026-02-07T11:00:01Z",
        "as_of_time_utc": "2026-02-07T11:00:00Z",
        "feature_groups": [{"name": "core_features", "version": "v1"}],
        "feature_def_policy_rev": {"policy_id": "ofp.features.v0", "revision": "r1", "content_digest": "e" * 64},
        "features": {},
        "run_config_digest": "f" * 64,
        "freshness": {"state": "GREEN", "flags": [], "stale_groups": [], "missing_groups": []},
    }


def test_ofp_request_uses_source_ts() -> None:
    policy = _policy()
    stub = StubOfpClient(snapshot=_ofp_snapshot())
    acquirer = DecisionContextAcquirer(policy=policy, ofp_client=stub)
    result = acquirer.acquire(
        candidate=_candidate(),
        posture=_posture(allow_ieg=True, allowed_feature_groups=("core_features",)),
        decision_started_at_utc="2026-02-07T11:00:00Z",
        now_utc="2026-02-07T11:00:00Z",
        context_refs={
            "arrival_events": {"topic": "fp.bus.context.arrival_events.v1", "partition": 0, "offset": "1"},
            "flow_anchor": {"topic": "fp.bus.context.flow_anchor.fraud.v1", "partition": 0, "offset": "2"},
        },
        feature_keys=[{"key_type": "flow_id", "key_id": "flow_1"}],
    )
    assert result.status == CONTEXT_READY
    assert stub.last_payload is not None
    assert stub.last_payload["as_of_time_utc"] == _candidate().source_ts_utc


def test_mask_blocks_ofp_call() -> None:
    policy = _policy()
    acquirer = DecisionContextAcquirer(policy=policy, ofp_client=RaisingOfpClient())
    result = acquirer.acquire(
        candidate=_candidate(),
        posture=_posture(allow_ieg=False, allowed_feature_groups=()),
        decision_started_at_utc="2026-02-07T11:00:00Z",
        now_utc="2026-02-07T11:00:00Z",
        context_refs={
            "arrival_events": {"topic": "fp.bus.context.arrival_events.v1", "partition": 0, "offset": "1"},
            "flow_anchor": {"topic": "fp.bus.context.flow_anchor.fraud.v1", "partition": 0, "offset": "2"},
        },
        feature_keys=[{"key_type": "flow_id", "key_id": "flow_1"}],
    )
    assert result.status == CONTEXT_BLOCKED


def test_decision_deadline_enforced() -> None:
    policy = _policy()
    stub = StubOfpClient(snapshot=_ofp_snapshot())
    acquirer = DecisionContextAcquirer(policy=policy, ofp_client=stub)
    result = acquirer.acquire(
        candidate=_candidate(),
        posture=_posture(allow_ieg=True, allowed_feature_groups=("core_features",)),
        decision_started_at_utc="2026-02-07T11:00:00Z",
        now_utc="2026-02-07T11:00:03Z",
        context_refs={
            "arrival_events": {"topic": "fp.bus.context.arrival_events.v1", "partition": 0, "offset": "1"},
            "flow_anchor": {"topic": "fp.bus.context.flow_anchor.fraud.v1", "partition": 0, "offset": "2"},
        },
        feature_keys=[{"key_type": "flow_id", "key_id": "flow_1"}],
    )
    assert result.status == DECISION_DEADLINE_EXCEEDED


def test_join_wait_and_missing_context() -> None:
    policy = _policy()
    stub = StubOfpClient(snapshot=_ofp_snapshot())
    acquirer = DecisionContextAcquirer(policy=policy, ofp_client=stub)

    waiting = acquirer.acquire(
        candidate=_candidate(),
        posture=_posture(allow_ieg=True, allowed_feature_groups=("core_features",)),
        decision_started_at_utc="2026-02-07T11:00:00Z",
        now_utc="2026-02-07T11:00:00Z",
        context_refs={},
        feature_keys=[{"key_type": "flow_id", "key_id": "flow_1"}],
    )
    assert waiting.status == CONTEXT_WAITING

    missing = acquirer.acquire(
        candidate=_candidate(),
        posture=_posture(allow_ieg=True, allowed_feature_groups=("core_features",)),
        decision_started_at_utc="2026-02-07T11:00:00Z",
        now_utc="2026-02-07T11:00:01.200Z",
        context_refs={},
        feature_keys=[{"key_type": "flow_id", "key_id": "flow_1"}],
    )
    assert missing.status == CONTEXT_MISSING


def test_evidence_refs_include_ofp_basis() -> None:
    policy = _policy()
    stub = StubOfpClient(snapshot=_ofp_snapshot())
    acquirer = DecisionContextAcquirer(policy=policy, ofp_client=stub)
    result = acquirer.acquire(
        candidate=_candidate(),
        posture=_posture(allow_ieg=True, allowed_feature_groups=("core_features",)),
        decision_started_at_utc="2026-02-07T11:00:00Z",
        now_utc="2026-02-07T11:00:00Z",
        context_refs={
            "arrival_events": {"topic": "fp.bus.context.arrival_events.v1", "partition": 0, "offset": "1"},
            "flow_anchor": {"topic": "fp.bus.context.flow_anchor.fraud.v1", "partition": 0, "offset": "2"},
        },
        feature_keys=[{"key_type": "flow_id", "key_id": "flow_1"}],
    )
    assert result.status == CONTEXT_READY
    assert result.evidence.ofp_eb_offset_basis is not None
    assert result.evidence.source_eb_ref["topic"] == "fp.bus.traffic.fraud.v1"
