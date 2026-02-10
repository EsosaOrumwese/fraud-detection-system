from __future__ import annotations

from pathlib import Path

import pytest

import fraud_detection.action_layer.storage as storage_module
from fraud_detection.action_layer.storage import ActionLedgerStore, ActionLedgerStoreError, build_storage_layout


def test_action_storage_layout_uses_configured_locators(tmp_path: Path) -> None:
    layout = build_storage_layout(
        {
            "ledger_locator": str(tmp_path / "ledger.sqlite"),
            "outcomes_locator": str(tmp_path / "outcomes.sqlite"),
        }
    )
    assert layout.ledger_locator.endswith("ledger.sqlite")
    assert layout.outcomes_locator.endswith("outcomes.sqlite")


def test_action_ledger_registers_new_duplicate_and_hash_mismatch(tmp_path: Path) -> None:
    store = ActionLedgerStore(locator=str(tmp_path / "al_ledger.sqlite"))
    created = store.register_intent(
        platform_run_id="platform_20260207T182000Z",
        scenario_run_id="a" * 32,
        idempotency_key="merchant:42:evt:123",
        action_id="1" * 32,
        decision_id="2" * 32,
        payload_hash="3" * 64,
        first_seen_at_utc="2026-02-07T18:20:00.000000Z",
    )
    assert created.status == "NEW"

    duplicate = store.register_intent(
        platform_run_id="platform_20260207T182000Z",
        scenario_run_id="a" * 32,
        idempotency_key="merchant:42:evt:123",
        action_id="1" * 32,
        decision_id="2" * 32,
        payload_hash="3" * 64,
        first_seen_at_utc="2026-02-07T18:20:01.000000Z",
    )
    assert duplicate.status == "DUPLICATE"
    assert duplicate.record.first_seen_at_utc == "2026-02-07T18:20:00.000000Z"

    mismatch = store.register_intent(
        platform_run_id="platform_20260207T182000Z",
        scenario_run_id="a" * 32,
        idempotency_key="merchant:42:evt:123",
        action_id="1" * 32,
        decision_id="2" * 32,
        payload_hash="9" * 64,
        first_seen_at_utc="2026-02-07T18:20:02.000000Z",
    )
    assert mismatch.status == "HASH_MISMATCH"
    assert mismatch.record.payload_hash == "3" * 64


def test_phase1_postgres_sql_placeholders_follow_psycopg_contract() -> None:
    rendered, ordered = storage_module._render_sql_with_params(  # noqa: SLF001
        "SELECT 1 FROM al_intent_ledger WHERE platform_run_id = {p2} AND scenario_run_id = {p1}",
        "postgres",
        ("scenario_x", "platform_y"),
    )
    assert rendered.count("%s") == 2
    assert "{p1}" not in rendered and "{p2}" not in rendered
    assert ordered == ("platform_y", "scenario_x")


def test_phase1_placeholder_index_out_of_range_fails_closed() -> None:
    with pytest.raises(ActionLedgerStoreError, match="out of range"):
        storage_module._render_sql_with_params("SELECT * FROM al_intent_ledger WHERE idempotency_key = {p3}", "postgres", ("x",))  # noqa: SLF001
