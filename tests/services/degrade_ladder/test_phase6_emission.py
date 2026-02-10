from __future__ import annotations

from pathlib import Path

from fraud_detection.degrade_ladder.config import load_policy_bundle
from fraud_detection.degrade_ladder.contracts import DegradeDecision
from fraud_detection.degrade_ladder.emission import (
    GLOBAL_MANIFEST_SENTINEL,
    DlControlPublisher,
    SqliteDlOutboxStore,
    build_outbox_store,
    build_posture_change_event,
    deterministic_posture_event_id,
)


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
        reason=f"emission:{mode}",
        evidence_refs=(),
    )


def _store(tmp_path: Path) -> SqliteDlOutboxStore:
    store = build_outbox_store(str(tmp_path / "dl_phase6.sqlite"), stream_id="dl.phase6")
    assert isinstance(store, SqliteDlOutboxStore)
    return store


class _RecordingPublisher(DlControlPublisher):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[dict[str, object]] = []

    def publish(self, event: dict[str, object]) -> None:
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.events.append(event)


def test_event_identity_is_deterministic_and_global_manifest_is_sentinel() -> None:
    decision = _decision(mode="DEGRADED_1", posture_seq=17, decided_at_utc="2026-02-07T07:00:00.000000Z")
    event = build_posture_change_event(
        scope_key="scope=GLOBAL",
        decision=decision,
        change_kind="MODE_CHANGED",
    )
    event_id_a = deterministic_posture_event_id(scope_key="scope=GLOBAL", posture_seq=17)
    event_id_b = deterministic_posture_event_id(scope_key="scope=GLOBAL", posture_seq=17)
    assert event_id_a == event_id_b
    assert event["event_id"] == event_id_a
    assert event["manifest_fingerprint"] == GLOBAL_MANIFEST_SENTINEL


def test_enqueue_is_idempotent_for_duplicate_transition(tmp_path: Path) -> None:
    store = _store(tmp_path)
    decision = _decision(mode="NORMAL", posture_seq=1, decided_at_utc="2026-02-07T07:01:00.000000Z")
    inserted_first = store.enqueue_posture_change(
        scope_key="scope=GLOBAL",
        decision=decision,
        change_kind="MODE_CHANGED",
    )
    inserted_second = store.enqueue_posture_change(
        scope_key="scope=GLOBAL",
        decision=decision,
        change_kind="MODE_CHANGED",
    )
    assert inserted_first is True
    assert inserted_second is False


def test_drain_preserves_per_scope_ordering(tmp_path: Path) -> None:
    store = _store(tmp_path)
    scope_a = "scope=RUN|manifest_fingerprint=mf1|run_id=platform_1"
    scope_b = "scope=RUN|manifest_fingerprint=mf2|run_id=platform_2"
    store.enqueue_posture_change(
        scope_key=scope_a,
        decision=_decision(mode="DEGRADED_1", posture_seq=2, decided_at_utc="2026-02-07T07:02:10.000000Z"),
        change_kind="MODE_CHANGED",
    )
    store.enqueue_posture_change(
        scope_key=scope_a,
        decision=_decision(mode="NORMAL", posture_seq=1, decided_at_utc="2026-02-07T07:02:00.000000Z"),
        change_kind="MODE_CHANGED",
    )
    store.enqueue_posture_change(
        scope_key=scope_b,
        decision=_decision(mode="NORMAL", posture_seq=1, decided_at_utc="2026-02-07T07:02:00.000000Z"),
        change_kind="MODE_CHANGED",
    )

    publisher = _RecordingPublisher()
    first = store.drain_once(
        publisher=publisher,
        max_events=10,
        now_utc="2026-02-07T07:03:00.000000Z",
    )
    assert first.published == 2
    published_pairs = [
        (
            str(event["payload"]["scope_key"]),  # type: ignore[index]
            int(event["payload"]["posture_seq"]),  # type: ignore[index]
        )
        for event in publisher.events
    ]
    assert (scope_a, 1) in published_pairs
    assert (scope_b, 1) in published_pairs

    second = store.drain_once(
        publisher=publisher,
        max_events=10,
        now_utc="2026-02-07T07:03:01.000000Z",
    )
    assert second.published == 1
    assert (
        str(publisher.events[-1]["payload"]["scope_key"]),  # type: ignore[index]
        int(publisher.events[-1]["payload"]["posture_seq"]),  # type: ignore[index]
    ) == (scope_a, 2)


def test_retry_backoff_and_dead_letter_transitions(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.enqueue_posture_change(
        scope_key="scope=GLOBAL",
        decision=_decision(mode="DEGRADED_2", posture_seq=5, decided_at_utc="2026-02-07T07:05:00.000000Z"),
        change_kind="MODE_CHANGED",
    )
    failing = _RecordingPublisher(fail=True)

    first = store.drain_once(
        publisher=failing,
        max_events=10,
        max_attempts=2,
        base_backoff_seconds=10,
        now_utc="2026-02-07T07:05:10.000000Z",
    )
    assert first.failed == 1
    assert first.dead_lettered == 0

    second = store.drain_once(
        publisher=failing,
        max_events=10,
        max_attempts=2,
        base_backoff_seconds=10,
        now_utc="2026-02-07T07:05:15.000000Z",
    )
    assert second.considered == 0

    third = store.drain_once(
        publisher=failing,
        max_events=10,
        max_attempts=2,
        base_backoff_seconds=10,
        now_utc="2026-02-07T07:05:21.000000Z",
    )
    assert third.dead_lettered == 1

    metrics = store.metrics(now_utc="2026-02-07T07:05:22.000000Z")
    assert metrics.dead_letter_count == 1
    assert metrics.pending_count == 0


def test_metrics_surface_pending_backlog_and_oldest_age(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.enqueue_posture_change(
        scope_key="scope=GLOBAL",
        decision=_decision(mode="NORMAL", posture_seq=1, decided_at_utc="2026-02-07T07:10:00.000000Z"),
        change_kind="MODE_CHANGED",
    )
    store.enqueue_posture_change(
        scope_key="scope=RUN|manifest_fingerprint=mf3|run_id=platform_3",
        decision=_decision(mode="DEGRADED_1", posture_seq=1, decided_at_utc="2026-02-07T07:10:30.000000Z"),
        change_kind="MODE_CHANGED",
    )

    metrics = store.metrics(now_utc="2026-02-07T07:12:00.000000Z")
    assert metrics.pending_count == 2
    assert metrics.failed_count == 0
    assert metrics.dead_letter_count == 0
    assert metrics.oldest_pending_age_seconds is not None
    assert metrics.oldest_pending_age_seconds >= 120
