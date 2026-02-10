from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from fraud_detection.degrade_ladder.config import load_policy_bundle
from fraud_detection.degrade_ladder.contracts import DegradeDecision
from fraud_detection.degrade_ladder.serve import DlCurrentPostureService
from fraud_detection.degrade_ladder.store import (
    DlPostureStoreError,
    SqliteDlPostureStore,
    build_store,
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
        reason=f"test:{mode}",
        evidence_refs=(),
    )


def _sqlite_store(tmp_path: Path) -> SqliteDlPostureStore:
    store = build_store(str(tmp_path / "dl_phase4.sqlite"), stream_id="dl.phase4")
    assert isinstance(store, SqliteDlPostureStore)
    return store


def test_store_commit_and_read_roundtrip(tmp_path: Path) -> None:
    store = _sqlite_store(tmp_path)
    scope_key = "scope=GLOBAL"
    decision = _decision(mode="NORMAL", posture_seq=3, decided_at_utc="2026-02-07T03:30:00.000000Z")

    result = store.commit_current(scope_key=scope_key, decision=decision)
    assert result.status == "inserted"
    assert result.posture_seq == 3

    loaded = store.read_current(scope_key=scope_key)
    assert loaded is not None
    assert loaded.scope_key == scope_key
    assert loaded.decision.digest() == decision.digest()
    assert loaded.policy_id == decision.policy_rev.policy_id


def test_store_rejects_seq_regression_and_preserves_previous_commit(tmp_path: Path) -> None:
    store = _sqlite_store(tmp_path)
    scope_key = "scope=GLOBAL"
    store.commit_current(
        scope_key=scope_key,
        decision=_decision(mode="DEGRADED_1", posture_seq=5, decided_at_utc="2026-02-07T03:31:00.000000Z"),
    )

    with pytest.raises(DlPostureStoreError):
        store.commit_current(
            scope_key=scope_key,
            decision=_decision(mode="NORMAL", posture_seq=4, decided_at_utc="2026-02-07T03:31:10.000000Z"),
        )

    loaded = store.read_current(scope_key=scope_key)
    assert loaded is not None
    assert loaded.decision.posture_seq == 5
    assert loaded.decision.mode == "DEGRADED_1"


def test_serve_returns_current_posture_with_staleness_metadata(tmp_path: Path) -> None:
    store = _sqlite_store(tmp_path)
    profile, policy_rev = _profile_and_rev()
    service = DlCurrentPostureService(
        store=store,
        fallback_profile=profile,
        fallback_policy_rev=policy_rev,
    )
    scope_key = "scope=GLOBAL"
    store.commit_current(
        scope_key=scope_key,
        decision=_decision(mode="NORMAL", posture_seq=7, decided_at_utc="2026-02-07T03:40:00.000000Z"),
    )

    result = service.get_current_posture(
        scope_key=scope_key,
        decision_time_utc="2026-02-07T03:40:30.000000Z",
        max_age_seconds=120,
    )
    assert result.source == "CURRENT_POSTURE"
    assert result.trust_state == "TRUSTED"
    assert result.decision.mode == "NORMAL"
    assert result.age_seconds == 30
    assert result.is_stale is False


def test_serve_clamps_fail_closed_when_record_is_stale(tmp_path: Path) -> None:
    store = _sqlite_store(tmp_path)
    profile, policy_rev = _profile_and_rev()
    service = DlCurrentPostureService(
        store=store,
        fallback_profile=profile,
        fallback_policy_rev=policy_rev,
    )
    scope_key = "scope=GLOBAL"
    store.commit_current(
        scope_key=scope_key,
        decision=_decision(mode="NORMAL", posture_seq=8, decided_at_utc="2026-02-07T03:00:00.000000Z"),
    )

    result = service.get_current_posture(
        scope_key=scope_key,
        decision_time_utc="2026-02-07T03:05:00.000000Z",
        max_age_seconds=120,
    )
    assert result.source == "FAILSAFE_STALE"
    assert result.decision.mode == "FAIL_CLOSED"
    assert result.trust_state == "TRUSTED"
    assert result.is_stale is True
    assert result.staleness_reason is not None
    assert "POSTURE_STALE" in result.staleness_reason


def test_serve_clamps_fail_closed_when_store_row_is_corrupt(tmp_path: Path) -> None:
    store = _sqlite_store(tmp_path)
    profile, policy_rev = _profile_and_rev()
    service = DlCurrentPostureService(
        store=store,
        fallback_profile=profile,
        fallback_policy_rev=policy_rev,
    )
    scope_key = "scope=GLOBAL"
    store.commit_current(
        scope_key=scope_key,
        decision=_decision(mode="DEGRADED_1", posture_seq=9, decided_at_utc="2026-02-07T03:42:00.000000Z"),
    )

    with sqlite3.connect(str(store.path)) as conn:
        conn.execute(
            """
            UPDATE dl_current_posture
            SET decision_json = ?
            WHERE stream_id = ? AND scope_key = ?
            """,
            ("not-json", store.stream_id, scope_key),
        )

    result = service.get_current_posture(
        scope_key=scope_key,
        decision_time_utc="2026-02-07T03:42:10.000000Z",
        max_age_seconds=120,
    )
    assert result.source == "FAILSAFE_STORE_ERROR"
    assert result.decision.mode == "FAIL_CLOSED"
    assert result.trust_state == "UNTRUSTED"
    assert result.staleness_reason is not None
    assert "STORE_ERROR:" in result.staleness_reason
