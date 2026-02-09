from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.degrade_ladder.config import load_policy_bundle
from fraud_detection.degrade_ladder.contracts import DegradeDecision
from fraud_detection.degrade_ladder.evaluator import (
    DlEvaluationError,
    evaluate_posture,
    evaluate_posture_safe,
    resolve_scope,
)
from fraud_detection.degrade_ladder.signals import DlSignalSample, build_signal_snapshot


def _profile():
    bundle = load_policy_bundle(Path("config/platform/dl/policy_profiles_v0.yaml"))
    return bundle.profile("local_parity"), bundle.policy_rev


def _sample(
    *,
    name: str,
    observed_at_utc: str,
    scope_key: str,
    status: str = "OK",
    value: object = 1,
) -> DlSignalSample:
    return DlSignalSample(
        name=name,
        scope_key=scope_key,
        observed_at_utc=observed_at_utc,
        status=status,
        value=value,
    )


def _healthy_snapshot(scope_key: str, decision_time_utc: str):
    return build_signal_snapshot(
        [
            _sample(name="ofp_health", observed_at_utc="2026-02-07T03:05:40.000000Z", scope_key=scope_key),
            _sample(name="ieg_health", observed_at_utc="2026-02-07T03:05:40.000000Z", scope_key=scope_key),
            _sample(name="eb_consumer_lag", observed_at_utc="2026-02-07T03:05:40.000000Z", scope_key=scope_key),
            _sample(name="registry_health", observed_at_utc="2026-02-07T03:05:40.000000Z", scope_key=scope_key),
            _sample(name="posture_store_health", observed_at_utc="2026-02-07T03:05:40.000000Z", scope_key=scope_key),
            _sample(name="control_publish_health", observed_at_utc="2026-02-07T03:05:30.000000Z", scope_key=scope_key),
        ],
        scope_key=scope_key,
        decision_time_utc=decision_time_utc,
        required_signal_names=[
            "ofp_health",
            "ieg_health",
            "eb_consumer_lag",
            "registry_health",
            "posture_store_health",
        ],
        optional_signal_names=["control_publish_health"],
        required_max_age_seconds=120,
    )


def _required_gap_snapshot(scope_key: str, decision_time_utc: str):
    return build_signal_snapshot(
        [
            _sample(name="ofp_health", observed_at_utc="2026-02-07T03:05:40.000000Z", scope_key=scope_key),
        ],
        scope_key=scope_key,
        decision_time_utc=decision_time_utc,
        required_signal_names=[
            "ofp_health",
            "ieg_health",
            "eb_consumer_lag",
            "registry_health",
            "posture_store_health",
        ],
        optional_signal_names=["control_publish_health"],
        required_max_age_seconds=120,
    )


def _prior_decision(
    *,
    mode: str,
    decided_at_utc: str,
    posture_seq: int = 1,
    reason: str = "seed prior",
) -> DegradeDecision:
    profile, policy_rev = _profile()
    return DegradeDecision(
        mode=mode,
        capabilities_mask=profile.modes[mode].capabilities_mask,
        policy_rev=policy_rev,
        posture_seq=posture_seq,
        decided_at_utc=decided_at_utc,
        reason=reason,
        evidence_refs=(),
    )


def test_scope_resolution_is_explicit_and_deterministic() -> None:
    global_scope = resolve_scope(scope_kind="GLOBAL")
    assert global_scope.scope_key == "scope=GLOBAL"

    manifest_scope = resolve_scope(
        scope_kind="MANIFEST",
        manifest_fingerprint="abc123",
    )
    assert manifest_scope.scope_key == "scope=MANIFEST|manifest_fingerprint=abc123"

    run_scope = resolve_scope(
        scope_kind="RUN",
        manifest_fingerprint="abc123",
        run_id="platform_20260207T032500Z",
        scenario_id="scenario_alpha",
        parameter_hash="p123",
    )
    assert (
        run_scope.scope_key
        == "scope=RUN|manifest_fingerprint=abc123|run_id=platform_20260207T032500Z|scenario_id=scenario_alpha|parameter_hash=p123"
    )
    assert run_scope == resolve_scope(
        scope_kind="RUN",
        manifest_fingerprint="abc123",
        run_id="platform_20260207T032500Z",
        scenario_id="scenario_alpha",
        parameter_hash="p123",
    )

    with pytest.raises(DlEvaluationError):
        resolve_scope(scope_kind="MANIFEST")


def test_evaluator_is_deterministic_for_identical_inputs() -> None:
    profile, policy_rev = _profile()
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    snapshot = _healthy_snapshot(scope_key, "2026-02-07T03:06:00.000000Z")

    decision_a = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=snapshot,
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        scope_key=scope_key,
        posture_seq=2,
    )
    decision_b = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=snapshot,
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        scope_key=scope_key,
        posture_seq=2,
    )
    assert decision_a.mode == "NORMAL"
    assert decision_a.digest() == decision_b.digest()
    assert decision_a.reason == decision_b.reason


def test_required_gaps_force_fail_closed() -> None:
    profile, policy_rev = _profile()
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    decision = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_required_gap_snapshot(scope_key, "2026-02-07T03:06:00.000000Z"),
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        scope_key=scope_key,
        posture_seq=3,
    )
    assert decision.mode == "FAIL_CLOSED"


def test_hysteresis_blocks_upshift_before_quiet_period() -> None:
    profile, policy_rev = _profile()
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    decision = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key, "2026-02-07T03:06:30.000000Z"),
        decision_time_utc="2026-02-07T03:06:30.000000Z",
        scope_key=scope_key,
        posture_seq=5,
        prior_decision=_prior_decision(mode="FAIL_CLOSED", decided_at_utc="2026-02-07T03:06:00.000000Z"),
    )
    assert decision.mode == "FAIL_CLOSED"
    assert "upshift_held_quiet_period" in (decision.reason or "")


def test_hysteresis_allows_one_rung_upshift_after_quiet_period() -> None:
    profile, policy_rev = _profile()
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    decision = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key, "2026-02-07T03:06:30.000000Z"),
        decision_time_utc="2026-02-07T03:06:30.000000Z",
        scope_key=scope_key,
        posture_seq=6,
        prior_decision=_prior_decision(mode="FAIL_CLOSED", decided_at_utc="2026-02-07T03:05:00.000000Z"),
    )
    assert decision.mode == "DEGRADED_2"
    assert "upshift_one_rung:FAIL_CLOSED->DEGRADED_2" in (decision.reason or "")


def test_hysteresis_accumulates_held_elapsed_across_iterations() -> None:
    profile, policy_rev = _profile()
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    prior_reason = (
        "baseline=all_signals_ok;"
        "transition=upshift_held_quiet_period:59s<60s;"
        "profile=local_parity;"
        "scope=scope=GLOBAL"
    )
    decision = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(scope_key, "2026-02-07T03:06:30.000000Z"),
        decision_time_utc="2026-02-07T03:06:30.000000Z",
        scope_key=scope_key,
        posture_seq=7,
        prior_decision=_prior_decision(
            mode="FAIL_CLOSED",
            decided_at_utc="2026-02-07T03:06:29.000000Z",
            reason=prior_reason,
        ),
    )
    assert decision.mode == "DEGRADED_2"
    assert "upshift_one_rung:FAIL_CLOSED->DEGRADED_2" in (decision.reason or "")


def test_downshift_is_immediate_when_baseline_is_worse() -> None:
    profile, policy_rev = _profile()
    scope_key = resolve_scope(scope_kind="GLOBAL").scope_key
    decision = evaluate_posture(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_required_gap_snapshot(scope_key, "2026-02-07T03:10:00.000000Z"),
        decision_time_utc="2026-02-07T03:10:00.000000Z",
        scope_key=scope_key,
        posture_seq=8,
        prior_decision=_prior_decision(mode="NORMAL", decided_at_utc="2026-02-07T03:09:59.000000Z"),
    )
    assert decision.mode == "FAIL_CLOSED"
    assert "downshift_immediate" in (decision.reason or "")


def test_evaluate_posture_safe_forces_fail_closed_on_error() -> None:
    profile, policy_rev = _profile()
    global_scope = resolve_scope(scope_kind="GLOBAL").scope_key
    run_scope = resolve_scope(
        scope_kind="RUN",
        manifest_fingerprint="abc123",
        run_id="platform_20260207T033000Z",
    ).scope_key
    decision = evaluate_posture_safe(
        profile=profile,
        policy_rev=policy_rev,
        snapshot=_healthy_snapshot(global_scope, "2026-02-07T03:06:00.000000Z"),
        decision_time_utc="2026-02-07T03:06:00.000000Z",
        scope_key=run_scope,
        posture_seq=9,
    )
    assert decision.mode == "FAIL_CLOSED"
    assert (decision.reason or "").startswith("EVALUATOR_FAIL_CLOSED:")
