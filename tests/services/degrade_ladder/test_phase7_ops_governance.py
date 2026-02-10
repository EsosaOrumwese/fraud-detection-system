from __future__ import annotations

from pathlib import Path

from fraud_detection.degrade_ladder.config import load_policy_bundle
from fraud_detection.degrade_ladder.contracts import DegradeDecision
from fraud_detection.degrade_ladder.ops import SqliteDlOpsStore, build_ops_store
from fraud_detection.degrade_ladder.signals import DlSignalSample, build_signal_snapshot


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
        reason=f"ops:{mode}",
        evidence_refs=(),
    )


def _store(tmp_path: Path) -> SqliteDlOpsStore:
    store = build_ops_store(str(tmp_path / "dl_phase7.sqlite"), stream_id="dl.phase7")
    assert isinstance(store, SqliteDlOpsStore)
    return store


def test_policy_activation_event_has_policy_stamp_and_redaction(tmp_path: Path) -> None:
    _, policy_rev = _profile_and_rev()
    store = _store(tmp_path)
    scope = "scope=GLOBAL"

    event_id = store.record_policy_activation(
        scope_key=scope,
        policy_rev=policy_rev,
        actor="ops.user",
        reason="activate baseline corridor",
        ts_utc="2026-02-07T07:20:00.000000Z",
        metadata={
            "access_token": "top-secret-token",
            "nested": {"password": "dont-store-me", "safe_field": "ok"},
        },
    )
    events = store.query_governance_events(event_type="dl.policy_activated.v1", scope_key=scope, limit=10)
    assert len(events) == 1
    event = events[0]
    assert event.event_id == event_id
    assert event.policy_id == policy_rev.policy_id
    assert event.policy_revision == policy_rev.revision
    assert event.payload["metadata"]["access_token"] == "[REDACTED]"
    assert event.payload["metadata"]["nested"]["password"] == "[REDACTED]"
    assert event.payload["metadata"]["nested"]["safe_field"] == "ok"


def test_forced_fail_closed_transition_emits_structured_queryable_events(tmp_path: Path) -> None:
    store = _store(tmp_path)
    scope = "scope=RUN|manifest_fingerprint=mf123|run_id=platform_abc"
    decision = _decision(mode="FAIL_CLOSED", posture_seq=11, decided_at_utc="2026-02-07T07:21:00.000000Z")

    transition_id = store.record_posture_transition(
        scope_key=scope,
        decision=decision,
        previous_mode="DEGRADED_2",
        source="HEALTH_GATE_BROKEN",
        forced_fail_closed=True,
        reason_codes=("POSTURE_STORE_CORRUPT",),
        ts_utc="2026-02-07T07:21:01.000000Z",
    )
    transition_events = store.query_governance_events(event_type="dl.posture_transition.v1", scope_key=scope, limit=10)
    forced_events = store.query_governance_events(event_type="dl.fail_closed_forced.v1", scope_key=scope, limit=10)

    assert len(transition_events) == 1
    assert transition_events[0].event_id == transition_id
    assert transition_events[0].policy_id == decision.policy_rev.policy_id
    assert transition_events[0].policy_revision == decision.policy_rev.revision
    assert transition_events[0].payload["posture_seq"] == 11
    assert len(forced_events) == 1
    assert forced_events[0].payload["reason_codes"] == ["POSTURE_STORE_CORRUPT"]


def test_ops_metrics_cover_required_phase7_categories(tmp_path: Path) -> None:
    store = _store(tmp_path)
    scope = "scope=GLOBAL"
    decision = _decision(mode="NORMAL", posture_seq=1, decided_at_utc="2026-02-07T07:22:00.000000Z")

    store.record_posture_transition(
        scope_key=scope,
        decision=decision,
        previous_mode=None,
        source="EVALUATOR",
        ts_utc="2026-02-07T07:22:01.000000Z",
    )
    store.record_evaluator_error(
        scope_key=scope,
        error_code="SNAPSHOT_SCOPE_MISMATCH",
        ts_utc="2026-02-07T07:22:02.000000Z",
    )

    snapshot = build_signal_snapshot(
        [
            DlSignalSample(
                name="ofp_health",
                scope_key=scope,
                observed_at_utc="2026-02-07T07:21:55.000000Z",
                status="OK",
            ),
            DlSignalSample(
                name="ieg_health",
                scope_key=scope,
                observed_at_utc="2026-02-07T07:19:00.000000Z",
                status="OK",
            ),
        ],
        scope_key=scope,
        decision_time_utc="2026-02-07T07:22:05.000000Z",
        required_signal_names=["ofp_health", "ieg_health"],
        required_max_age_seconds=120,
    )
    store.record_signal_snapshot(
        scope_key=scope,
        snapshot=snapshot,
        ts_utc="2026-02-07T07:22:05.000000Z",
    )
    store.record_serve_result(
        scope_key=scope,
        source="FAILSAFE_STALE",
        ts_utc="2026-02-07T07:22:06.000000Z",
    )

    metrics = store.metrics_snapshot(scope_key=scope)
    assert metrics["posture_transitions_total"] == 1
    assert metrics["evaluator_errors_total"] == 1
    assert metrics["signal_required_ok_total"] == 1
    assert metrics["signal_required_bad_total"] == 1
    assert metrics["serve_fallback_total"] == 1
