from __future__ import annotations

from pathlib import Path

from fraud_detection.action_layer.storage import ActionLedgerStore, build_storage_layout


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

