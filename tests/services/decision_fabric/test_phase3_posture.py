from __future__ import annotations

from dataclasses import dataclass

from fraud_detection.degrade_ladder.contracts import CapabilitiesMask, DegradeDecision, PolicyRev
from fraud_detection.degrade_ladder.health import DlHealthGate
from fraud_detection.degrade_ladder.serve import DlServeResult
from fraud_detection.decision_fabric.posture import (
    DfPostureResolver,
    DfPostureTransitionGuard,
    enforce_posture_constraints,
    posture_stamp_from_dl,
)


def _decision(
    *,
    mode: str,
    posture_seq: int,
    decided_at_utc: str,
    allow_ieg: bool = True,
    allowed_groups: tuple[str, ...] = ("core_features",),
    allow_model_primary: bool = True,
    allow_model_stage2: bool = True,
    allow_fallback_heuristics: bool = True,
    action_posture: str = "NORMAL",
) -> DegradeDecision:
    return DegradeDecision(
        mode=mode,
        capabilities_mask=CapabilitiesMask(
            allow_ieg=allow_ieg,
            allowed_feature_groups=allowed_groups,
            allow_model_primary=allow_model_primary,
            allow_model_stage2=allow_model_stage2,
            allow_fallback_heuristics=allow_fallback_heuristics,
            action_posture=action_posture,
        ),
        policy_rev=PolicyRev(policy_id="dl.policy.v0", revision="r1", content_digest="a" * 64),
        posture_seq=posture_seq,
        decided_at_utc=decided_at_utc,
        reason="policy_eval",
    )


def _serve_result(
    *,
    decision: object,
    source: str = "CURRENT_POSTURE",
    trust_state: str = "TRUSTED",
    decision_time_utc: str = "2026-02-07T11:00:00.000000Z",
    staleness_reason: str | None = None,
) -> DlServeResult:
    return DlServeResult(
        scope_key="scope=GLOBAL",
        decision=decision,  # type: ignore[arg-type]
        source=source,
        trust_state=trust_state,
        served_at_utc="2026-02-07T11:00:01.000000Z",
        decision_time_utc=decision_time_utc,
        record_updated_at_utc="2026-02-07T11:00:00.500000Z",
        age_seconds=1,
        is_stale=staleness_reason is not None,
        staleness_reason=staleness_reason,
    )


def _health_gate(*, state: str = "HEALTHY", reasons: tuple[str, ...] = ()) -> DlHealthGate:
    return DlHealthGate(
        scope_key="scope=GLOBAL",
        state=state,
        forced_mode="FAIL_CLOSED" if state in {"BLIND", "BROKEN"} else None,
        reason_codes=reasons,
        effective_at_utc="2026-02-07T11:00:00.000000Z",
        hold_down_until_utc=None,
        healthy_observation_streak=1,
        rebuild_requested=False,
        rebuild_reason=None,
    )


def test_enforce_posture_constraints_applies_mask_as_hard_limits() -> None:
    stamp = posture_stamp_from_dl(
        dl_result=_serve_result(
            decision=_decision(
                mode="DEGRADED_2",
                posture_seq=11,
                decided_at_utc="2026-02-07T11:00:00.000000Z",
                allow_ieg=False,
                allowed_groups=("core_features",),
                allow_model_primary=True,
                allow_model_stage2=False,
                allow_fallback_heuristics=False,
                action_posture="STEP_UP_ONLY",
            )
        )
    )
    result = enforce_posture_constraints(
        posture=stamp,
        require_ieg=True,
        requested_feature_groups=("core_features", "velocity"),
        require_model_primary=True,
        require_model_stage2=True,
        require_fallback_heuristics=True,
        requested_action_posture="NORMAL",
    )
    assert result.blocked is True
    assert "CAPABILITY_BLOCK:allow_ieg" in result.reasons
    assert "CAPABILITY_BLOCK:feature_group=velocity" in result.reasons
    assert "CAPABILITY_BLOCK:allow_model_stage2" in result.reasons
    assert "CAPABILITY_BLOCK:allow_fallback_heuristics" in result.reasons
    assert "CAPABILITY_BLOCK:action_posture" in result.reasons
    assert result.allowed_feature_groups == ("core_features",)


def test_posture_stamp_from_dl_fail_closes_when_dl_result_is_malformed() -> None:
    malformed = _serve_result(decision={"mode": "BROKEN"})
    stamp = posture_stamp_from_dl(dl_result=malformed)
    assert stamp.mode == "FAIL_CLOSED"
    assert stamp.source == "DF_FAILSAFE_INVALID_DL_RESULT"
    assert any(reason.startswith("DL_POSTURE_INVALID") for reason in stamp.reasons)


def test_posture_stamp_digest_is_deterministic() -> None:
    serve_result = _serve_result(
        decision=_decision(mode="DEGRADED_1", posture_seq=5, decided_at_utc="2026-02-07T11:00:00.000000Z")
    )
    gate = _health_gate(state="IMPAIRED", reasons=("CONTROL_PUBLISH_UNHEALTHY",))
    stamp_a = posture_stamp_from_dl(dl_result=serve_result, health_gate=gate)
    stamp_b = posture_stamp_from_dl(dl_result=serve_result, health_gate=gate)
    assert stamp_a.digest() == stamp_b.digest()
    assert stamp_a.canonical_json() == stamp_b.canonical_json()


def test_transition_guard_allows_immediate_tighten_and_controls_relax() -> None:
    guard = DfPostureTransitionGuard(min_relax_interval_seconds=30)
    normal = posture_stamp_from_dl(
        dl_result=_serve_result(
            decision=_decision(mode="NORMAL", posture_seq=10, decided_at_utc="2026-02-07T11:00:00.000000Z")
        )
    )
    tightened = posture_stamp_from_dl(
        dl_result=_serve_result(
            decision=_decision(mode="DEGRADED_2", posture_seq=11, decided_at_utc="2026-02-07T11:00:01.000000Z")
        )
    )
    relaxed_early = posture_stamp_from_dl(
        dl_result=_serve_result(
            decision=_decision(mode="NORMAL", posture_seq=12, decided_at_utc="2026-02-07T11:00:05.000000Z")
        )
    )
    relaxed_late = posture_stamp_from_dl(
        dl_result=_serve_result(
            decision=_decision(mode="NORMAL", posture_seq=13, decided_at_utc="2026-02-07T11:00:45.000000Z")
        )
    )
    assert guard.apply(normal).mode == "NORMAL"
    assert guard.apply(tightened).mode == "DEGRADED_2"
    held = guard.apply(relaxed_early)
    assert held.mode == "DEGRADED_2"
    assert held.source == "DF_TRANSITION_HOLD"
    assert "RELAX_BLOCKED_HOLD_DOWN" in held.reasons
    accepted = guard.apply(relaxed_late)
    assert accepted.mode == "NORMAL"
    assert accepted.source == "CURRENT_POSTURE"


@dataclass
class _StubGuardedService:
    result: DlServeResult
    gate: DlHealthGate

    def get_guarded_posture(self, **_: object) -> tuple[DlServeResult, DlHealthGate]:
        return self.result, self.gate


def test_resolver_carries_failsafe_stale_posture() -> None:
    stale_result = _serve_result(
        decision=_decision(mode="FAIL_CLOSED", posture_seq=20, decided_at_utc="2026-02-07T11:00:00.000000Z"),
        source="FAILSAFE_STALE",
        trust_state="TRUSTED",
        staleness_reason="POSTURE_STALE:91s>90s",
    )
    resolver = DfPostureResolver(
        guarded_service=_StubGuardedService(result=stale_result, gate=_health_gate(state="BLIND")),
        max_age_seconds=90,
    )
    stamp = resolver.resolve(
        scope_key="scope=GLOBAL",
        decision_time_utc="2026-02-07T11:01:31.000000Z",
        policy_ok=True,
        required_signals_ok=False,
    )
    assert stamp.mode == "FAIL_CLOSED"
    assert stamp.source == "FAILSAFE_STALE"
    assert any(reason.startswith("DL_STALENESS:") for reason in stamp.reasons)
