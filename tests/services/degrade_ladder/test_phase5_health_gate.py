from __future__ import annotations

from pathlib import Path

from fraud_detection.degrade_ladder.config import load_policy_bundle
from fraud_detection.degrade_ladder.contracts import DegradeDecision
from fraud_detection.degrade_ladder.health import DlHealthGateController, DlHealthPolicy
from fraud_detection.degrade_ladder.serve import DlCurrentPostureService, DlGuardedPostureService
from fraud_detection.degrade_ladder.store import SqliteDlPostureStore, build_store


def _profile_and_rev():
    bundle = load_policy_bundle(Path("config/platform/dl/policy_profiles_v0.yaml"))
    return bundle.profile("local_parity"), bundle.policy_rev


def _decision(*, mode: str, posture_seq: int, decided_at_utc: str) -> DegradeDecision:
    profile, policy_rev = _profile_and_rev()
    return DegradeDecision(
        mode=mode,
        capabilities_mask=profile.modes[mode].capabilities_mask,
        policy_rev=policy_rev,
        posture_seq=posture_seq,
        decided_at_utc=decided_at_utc,
        reason=f"seed:{mode}",
        evidence_refs=(),
    )


def _store(tmp_path: Path) -> SqliteDlPostureStore:
    store = build_store(str(tmp_path / "dl_phase5.sqlite"), stream_id="dl.phase5")
    assert isinstance(store, SqliteDlPostureStore)
    return store


def test_health_classifier_uses_pinned_state_set(tmp_path: Path) -> None:
    gate = DlHealthGateController()
    scope = "scope=GLOBAL"
    healthy = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:50:00.000000Z",
        policy_ok=True,
        required_signals_ok=True,
        store_ok=True,
        serve_ok=True,
        control_publish_ok=True,
    )
    impaired = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:50:10.000000Z",
        policy_ok=True,
        required_signals_ok=True,
        store_ok=True,
        serve_ok=True,
        control_publish_ok=False,
    )
    assert healthy.state == "HEALTHY"
    assert impaired.state == "IMPAIRED"


def test_blind_gate_forces_fail_closed_even_with_healthy_store(tmp_path: Path) -> None:
    store = _store(tmp_path)
    profile, policy_rev = _profile_and_rev()
    base = DlCurrentPostureService(store=store, fallback_profile=profile, fallback_policy_rev=policy_rev)
    guarded = DlGuardedPostureService(base_service=base, health_gate=DlHealthGateController())

    scope = "scope=GLOBAL"
    store.commit_current(
        scope_key=scope,
        decision=_decision(mode="NORMAL", posture_seq=1, decided_at_utc="2026-02-07T03:51:00.000000Z"),
    )

    result, gate = guarded.get_guarded_posture(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:51:05.000000Z",
        max_age_seconds=120,
        policy_ok=True,
        required_signals_ok=False,
    )
    assert gate.state == "BLIND"
    assert gate.forced_mode == "FAIL_CLOSED"
    assert result.source == "FAILSAFE_HEALTH_GATE"
    assert result.decision.mode == "FAIL_CLOSED"


def test_broken_gate_forces_fail_closed_and_requests_rebuild(tmp_path: Path) -> None:
    store = _store(tmp_path)
    profile, policy_rev = _profile_and_rev()
    base = DlCurrentPostureService(store=store, fallback_profile=profile, fallback_policy_rev=policy_rev)
    guarded = DlGuardedPostureService(base_service=base, health_gate=DlHealthGateController())

    result, gate = guarded.get_guarded_posture(
        scope_key="scope=GLOBAL",
        decision_time_utc="2026-02-07T03:52:00.000000Z",
        max_age_seconds=120,
        policy_ok=True,
        required_signals_ok=True,
        store_ok=False,
        serve_ok=False,
        reason_codes=("POSTURE_STORE_CORRUPT",),
    )
    assert gate.state == "BROKEN"
    assert gate.rebuild_requested is True
    assert gate.rebuild_reason == "POSTURE_STORE_CORRUPT"
    assert result.decision.mode == "FAIL_CLOSED"


def test_recovery_requires_positive_observations_not_elapsed_time() -> None:
    gate = DlHealthGateController(
        DlHealthPolicy(healthy_clear_observations=2, hold_down_seconds=0, rebuild_cooldown_seconds=60)
    )
    scope = "scope=GLOBAL"
    first = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:53:00.000000Z",
        policy_ok=False,
        required_signals_ok=True,
        store_ok=True,
        serve_ok=True,
    )
    second = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:53:30.000000Z",
        policy_ok=True,
        required_signals_ok=True,
        store_ok=True,
        serve_ok=True,
    )
    third = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:54:00.000000Z",
        policy_ok=True,
        required_signals_ok=True,
        store_ok=True,
        serve_ok=True,
    )
    assert first.state == "BLIND"
    assert second.state == "BLIND"
    assert "RECOVERY_PENDING" in second.reason_codes
    assert third.state == "HEALTHY"


def test_rebuild_trigger_is_cooldown_limited() -> None:
    gate = DlHealthGateController(
        DlHealthPolicy(healthy_clear_observations=1, hold_down_seconds=0, rebuild_cooldown_seconds=120)
    )
    scope = "scope=GLOBAL"
    first = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:55:00.000000Z",
        policy_ok=True,
        required_signals_ok=True,
        store_ok=False,
        serve_ok=False,
        reason_codes=("POSTURE_STORE_CORRUPT",),
    )
    second = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:55:30.000000Z",
        policy_ok=True,
        required_signals_ok=True,
        store_ok=False,
        serve_ok=False,
        reason_codes=("POSTURE_STORE_CORRUPT",),
    )
    third = gate.evaluate(
        scope_key=scope,
        decision_time_utc="2026-02-07T03:57:01.000000Z",
        policy_ok=True,
        required_signals_ok=True,
        store_ok=False,
        serve_ok=False,
        reason_codes=("POSTURE_STORE_CORRUPT",),
    )
    assert first.rebuild_requested is True
    assert second.rebuild_requested is False
    assert third.rebuild_requested is True


def test_guarded_service_escalates_store_missing_to_broken_gate(tmp_path: Path) -> None:
    store = _store(tmp_path)
    profile, policy_rev = _profile_and_rev()
    base = DlCurrentPostureService(store=store, fallback_profile=profile, fallback_policy_rev=policy_rev)
    guarded = DlGuardedPostureService(base_service=base, health_gate=DlHealthGateController())

    result, gate = guarded.get_guarded_posture(
        scope_key="scope=GLOBAL",
        decision_time_utc="2026-02-07T03:58:00.000000Z",
        max_age_seconds=120,
        policy_ok=True,
        required_signals_ok=True,
    )
    assert gate.state == "BROKEN"
    assert result.source == "FAILSAFE_HEALTH_GATE"
    assert result.decision.mode == "FAIL_CLOSED"
