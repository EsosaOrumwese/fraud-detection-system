from __future__ import annotations

from pathlib import Path

from fraud_detection.action_layer.contracts import ActionIntent
from fraud_detection.action_layer.idempotency import (
    AL_DROP_DUPLICATE,
    AL_EXECUTE,
    AL_QUARANTINE,
    ActionIdempotencyGate,
    build_action_payload_hash,
)
from fraud_detection.action_layer.storage import ActionLedgerStore


def _intent_payload() -> dict[str, object]:
    return {
        "action_id": "1" * 32,
        "decision_id": "2" * 32,
        "action_kind": "txn_disposition_publish",
        "idempotency_key": "merchant_42:evt_123:publish",
        "pins": {
            "platform_run_id": "platform_20260207T183600Z",
            "scenario_run_id": "3" * 32,
            "manifest_fingerprint": "4" * 64,
            "parameter_hash": "5" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "requested_at_utc": "2026-02-07T18:36:00.000000Z",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "policy_rev": {"policy_id": "al.policy.v0", "revision": "r1"},
        "run_config_digest": "7" * 64,
        "action_payload": {"target": "fraud.disposition"},
    }


def test_action_payload_hash_changes_when_action_payload_changes() -> None:
    payload_a = _intent_payload()
    payload_b = _intent_payload()
    payload_b["action_payload"] = {"target": "fraud.review"}
    assert build_action_payload_hash(payload_a) != build_action_payload_hash(payload_b)


def test_idempotency_gate_executes_new_then_drops_duplicate(tmp_path: Path) -> None:
    store = ActionLedgerStore(locator=str(tmp_path / "al_semantic.sqlite"))
    gate = ActionIdempotencyGate(store=store)
    intent = ActionIntent.from_payload(_intent_payload())

    first = gate.evaluate(intent=intent, first_seen_at_utc="2026-02-07T18:36:00.000000Z")
    assert first.disposition == AL_EXECUTE
    assert first.ledger_status == "NEW"

    duplicate = gate.evaluate(intent=intent, first_seen_at_utc="2026-02-07T18:36:01.000000Z")
    assert duplicate.disposition == AL_DROP_DUPLICATE
    assert duplicate.ledger_status == "DUPLICATE"
    assert duplicate.semantic_key == first.semantic_key


def test_idempotency_gate_quarantines_payload_hash_mismatch(tmp_path: Path) -> None:
    store = ActionLedgerStore(locator=str(tmp_path / "al_semantic.sqlite"))
    gate = ActionIdempotencyGate(store=store)

    payload_a = _intent_payload()
    payload_b = _intent_payload()
    payload_b["action_payload"] = {"target": "fraud.review"}
    # Preserve same semantic identity on purpose (same run pins + idempotency key).
    intent_a = ActionIntent.from_payload(payload_a)
    intent_b = ActionIntent.from_payload(payload_b)

    first = gate.evaluate(intent=intent_a, first_seen_at_utc="2026-02-07T18:36:00.000000Z")
    assert first.disposition == AL_EXECUTE

    mismatch = gate.evaluate(intent=intent_b, first_seen_at_utc="2026-02-07T18:36:02.000000Z")
    assert mismatch.disposition == AL_QUARANTINE
    assert mismatch.ledger_status == "HASH_MISMATCH"


def test_semantic_ledger_is_run_scoped(tmp_path: Path) -> None:
    store = ActionLedgerStore(locator=str(tmp_path / "al_semantic.sqlite"))
    gate = ActionIdempotencyGate(store=store)

    payload_a = _intent_payload()
    payload_b = _intent_payload()
    payload_b["pins"]["platform_run_id"] = "platform_20260207T183700Z"  # type: ignore[index]
    intent_a = ActionIntent.from_payload(payload_a)
    intent_b = ActionIntent.from_payload(payload_b)

    first = gate.evaluate(intent=intent_a, first_seen_at_utc="2026-02-07T18:36:00.000000Z")
    second = gate.evaluate(intent=intent_b, first_seen_at_utc="2026-02-07T18:37:00.000000Z")

    assert first.disposition == AL_EXECUTE
    assert second.disposition == AL_EXECUTE
    assert first.semantic_key != second.semantic_key

