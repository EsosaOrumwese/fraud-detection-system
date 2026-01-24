from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.scenario_runner.authority import build_authority_store


def _sqlite_dsn(db_path: Path) -> str:
    return f"sqlite:///{db_path.as_posix()}"


def test_equivalence_resolution_sqlite(tmp_path: Path) -> None:
    store = build_authority_store(_sqlite_dsn(tmp_path / "sr_authority.db"))
    run_id, first = store.resolve_equivalence("rk-1", "fp-1")
    assert first is True
    run_id_again, first_again = store.resolve_equivalence("rk-1", "fp-1")
    assert run_id_again == run_id
    assert first_again is False
    with pytest.raises(RuntimeError):
        store.resolve_equivalence("rk-1", "fp-2")


def test_lease_acquire_renew_release_sqlite(tmp_path: Path) -> None:
    store = build_authority_store(_sqlite_dsn(tmp_path / "sr_authority.db"))
    run_id, _ = store.resolve_equivalence("rk-lease", "fp-lease")
    ok, token = store.acquire_lease(run_id, "owner-a", ttl_seconds=300)
    assert ok is True
    assert token
    ok2, _ = store.acquire_lease(run_id, "owner-b", ttl_seconds=300)
    assert ok2 is False
    assert store.renew_lease(run_id, token, ttl_seconds=300) is True
    assert store.release_lease(run_id, token) is True
    ok3, token2 = store.acquire_lease(run_id, "owner-b", ttl_seconds=300)
    assert ok3 is True
    assert token2
