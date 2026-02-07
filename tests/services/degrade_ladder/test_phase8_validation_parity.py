from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fraud_detection.degrade_ladder.config import load_policy_bundle
from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, DegradeDecision
from fraud_detection.degrade_ladder.evaluator import evaluate_posture, resolve_scope
from fraud_detection.degrade_ladder.serve import DlCurrentPostureService
from fraud_detection.degrade_ladder.signals import DlSignalSample, build_signal_snapshot
from fraud_detection.degrade_ladder.store import SqliteDlPostureStore, build_store


@dataclass(frozen=True)
class _DfIntent:
    use_ieg: bool
    feature_groups: tuple[str, ...]
    use_model_primary: bool
    use_model_stage2: bool
    action: str


def _profile_and_rev():
    bundle = load_policy_bundle(Path("config/platform/dl/policy_profiles_v0.yaml"))
    return bundle.profile("local_parity"), bundle.policy_rev


def _sqlite_store(tmp_path: Path) -> SqliteDlPostureStore:
    store = build_store(str(tmp_path / "dl_phase8.sqlite"), stream_id="dl.phase8")
    assert isinstance(store, SqliteDlPostureStore)
    return store


def _shift(ts_utc: str, *, seconds: int) -> str:
    dt = datetime.fromisoformat(ts_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    return (dt + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def _healthy_snapshot(
    *,
    scope_key: str,
    decision_time_utc: str,
    required_signals: tuple[str, ...],
    optional_signals: tuple[str, ...] = ("control_publish_health",),
):
    observed = _shift(decision_time_utc, seconds=-10)
    samples = [
        DlSignalSample(
            name=name,
            scope_key=scope_key,
            observed_at_utc=observed,
            status="OK",
        )
        for name in required_signals + optional_signals
    ]
    return build_signal_snapshot(
        samples,
        scope_key=scope_key,
        decision_time_utc=decision_time_utc,
        required_signal_names=list(required_signals),
        optional_signal_names=list(optional_signals),
        required_max_age_seconds=120,
    )


def _required_gap_snapshot(
    *,
    scope_key: str,
    decision_time_utc: str,
    required_signals: tuple[str, ...],
):
    observed = _shift(decision_time_utc, seconds=-10)
    return build_signal_snapshot(
        [
            DlSignalSample(
                name=required_signals[0],
                scope_key=scope_key,
                observed_at_utc=observed,
                status="OK",
            )
        ],
        scope_key=scope_key,
        decision_time_utc=decision_time_utc,
        required_signal_names=list(required_signals),
        optional_signal_names=["control_publish_health"],
        required_max_age_seconds=120,
    )


def _apply_mask(mask: CapabilitiesMask, intent: _DfIntent) -> dict[str, object]:
    allowed_groups = set(mask.allowed_feature_groups)
    action = intent.action
    if mask.action_posture == "STEP_UP_ONLY" and action not in {"BLOCK", "CHALLENGE"}:
        action = "CHALLENGE"
    return {
        "use_ieg": intent.use_ieg and mask.allow_ieg,
        "feature_groups": tuple(group for group in intent.feature_groups if group in allowed_groups),
        "use_model_primary": intent.use_model_primary and mask.allow_model_primary,
        "use_model_stage2": intent.use_model_stage2 and mask.allow_model_stage2,
        "action": action,
    }


def test_phase8_integration_df_consumes_posture_and_enforces_mask(tmp_path: Path) -> None:
    profile, policy_rev = _profile_and_rev()
    store = _sqlite_store(tmp_path)
    serve = DlCurrentPostureService(store=store, fallback_profile=profile, fallback_policy_rev=policy_rev)

    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    decision = DegradeDecision(
        mode="DEGRADED_2",
        capabilities_mask=profile.modes["DEGRADED_2"].capabilities_mask,
        policy_rev=policy_rev,
        posture_seq=12,
        decided_at_utc="2026-02-07T08:30:00.000000Z",
        reason="phase8 integration fixture",
        evidence_refs=(),
    )
    store.commit_current(scope_key=scope_key, decision=decision)
    served = serve.get_current_posture(
        scope_key=scope_key,
        decision_time_utc="2026-02-07T08:30:20.000000Z",
        max_age_seconds=120,
    )

    intent = _DfIntent(
        use_ieg=True,
        feature_groups=("core_features", "velocity", "entity_graph"),
        use_model_primary=True,
        use_model_stage2=True,
        action="AUTO_APPROVE",
    )
    enforced = _apply_mask(served.decision.capabilities_mask, intent)
    assert served.source == "CURRENT_POSTURE"
    assert served.decision.mode == "DEGRADED_2"
    assert enforced["use_ieg"] is False
    assert enforced["feature_groups"] == ("core_features",)
    assert enforced["use_model_primary"] is True
    assert enforced["use_model_stage2"] is False
    assert enforced["action"] == "CHALLENGE"


def test_phase8_replay_same_snapshot_and_policy_gives_same_posture(tmp_path: Path) -> None:
    profile, policy_rev = _profile_and_rev()
    required_signals = profile.signal_policy.required_signals
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    decision_time = "2026-02-07T08:40:00.000000Z"
    snapshot = _healthy_snapshot(
        scope_key=scope_key,
        decision_time_utc=decision_time,
        required_signals=required_signals,
    )

    first = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=snapshot,
        decision_time_utc=decision_time,
        scope_key=scope_key,
        posture_seq=21,
    )
    second = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=snapshot,
        decision_time_utc=decision_time,
        scope_key=scope_key,
        posture_seq=21,
    )
    assert first.digest() == second.digest()

    store = _sqlite_store(tmp_path)
    store.commit_current(scope_key=scope_key, decision=first)
    replay_snapshot = _healthy_snapshot(
        scope_key=scope_key,
        decision_time_utc=decision_time,
        required_signals=required_signals,
    )
    replay = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=replay_snapshot,
        decision_time_utc=decision_time,
        scope_key=scope_key,
        posture_seq=21,
    )
    assert replay.digest() == first.digest()
    loaded = store.read_current(scope_key=scope_key)
    assert loaded is not None
    assert loaded.decision.digest() == first.digest()


def test_phase8_local_parity_transition_proof_normal_to_degraded_and_back() -> None:
    profile, policy_rev = _profile_and_rev()
    required_signals = profile.signal_policy.required_signals
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key

    t0 = "2026-02-07T08:50:00.000000Z"
    t1 = "2026-02-07T08:51:00.000000Z"
    t2 = "2026-02-07T08:51:30.000000Z"
    t3 = "2026-02-07T08:52:40.000000Z"
    t4 = "2026-02-07T08:53:55.000000Z"
    t5 = "2026-02-07T08:55:10.000000Z"

    d0 = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key=scope_key, decision_time_utc=t0, required_signals=required_signals),
        decision_time_utc=t0,
        scope_key=scope_key,
        posture_seq=1,
    )
    d1 = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_required_gap_snapshot(scope_key=scope_key, decision_time_utc=t1, required_signals=required_signals),
        decision_time_utc=t1,
        scope_key=scope_key,
        posture_seq=2,
        prior_decision=d0,
    )
    d2 = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key=scope_key, decision_time_utc=t2, required_signals=required_signals),
        decision_time_utc=t2,
        scope_key=scope_key,
        posture_seq=3,
        prior_decision=d1,
    )
    d3 = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key=scope_key, decision_time_utc=t3, required_signals=required_signals),
        decision_time_utc=t3,
        scope_key=scope_key,
        posture_seq=4,
        prior_decision=d2,
    )
    d4 = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key=scope_key, decision_time_utc=t4, required_signals=required_signals),
        decision_time_utc=t4,
        scope_key=scope_key,
        posture_seq=5,
        prior_decision=d3,
    )
    d5 = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key=scope_key, decision_time_utc=t5, required_signals=required_signals),
        decision_time_utc=t5,
        scope_key=scope_key,
        posture_seq=6,
        prior_decision=d4,
    )

    assert [d0.mode, d1.mode, d2.mode, d3.mode, d4.mode, d5.mode] == [
        "NORMAL",
        "FAIL_CLOSED",
        "FAIL_CLOSED",
        "DEGRADED_2",
        "DEGRADED_1",
        "NORMAL",
    ]
