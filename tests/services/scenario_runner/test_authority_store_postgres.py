from __future__ import annotations

import os
import uuid

import pytest

from fraud_detection.scenario_runner.authority import build_authority_store

pytestmark = pytest.mark.parity


def test_postgres_authority_store_smoke() -> None:
    dsn = os.getenv("SR_TEST_PG_DSN")
    if not dsn:
        pytest.skip("SR_TEST_PG_DSN not set")
    store = build_authority_store(dsn)
    run_key = f"rk-{uuid.uuid4().hex}"
    fp = f"fp-{uuid.uuid4().hex}"
    run_id, first = store.resolve_equivalence(run_key, fp)
    assert first is True
    run_id_again, first_again = store.resolve_equivalence(run_key, fp)
    assert run_id_again == run_id
    assert first_again is False
    ok, token = store.acquire_lease(run_id, "owner-test", ttl_seconds=60)
    assert ok is True
    assert token
    assert store.check_lease(run_id, token) is True
    assert store.renew_lease(run_id, token, ttl_seconds=60) is True
    assert store.release_lease(run_id, token) is True
