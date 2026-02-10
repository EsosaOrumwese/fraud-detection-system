from __future__ import annotations

from pathlib import Path

from fraud_detection.action_layer.replay import (
    REPLAY_MATCH,
    REPLAY_NEW,
    REPLAY_PAYLOAD_MISMATCH,
    ActionOutcomeReplayLedger,
)


def _outcome_payload(*, outcome_id: str) -> dict[str, object]:
    return {
        "outcome_id": outcome_id,
        "decision_id": "2" * 32,
        "action_id": "3" * 32,
        "action_kind": "txn_disposition_publish",
        "status": "EXECUTED",
        "idempotency_key": f"idempo:{outcome_id}",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "authz_policy_rev": {"policy_id": "al.policy.v0", "revision": "r1"},
        "run_config_digest": "4" * 64,
        "pins": {
            "platform_run_id": "platform_20260207T191500Z",
            "scenario_run_id": "5" * 32,
            "manifest_fingerprint": "6" * 64,
            "parameter_hash": "7" * 64,
            "scenario_id": "scenario.v0",
            "seed": 9,
            "run_id": "8" * 32,
        },
        "completed_at_utc": "2026-02-07T19:15:00.000000Z",
        "attempt_seq": 1,
        "reason": "EXECUTED",
        "outcome_payload": {"terminal_state": "EXECUTED"},
    }


def test_replay_registers_new_match_and_payload_mismatch(tmp_path: Path) -> None:
    ledger = ActionOutcomeReplayLedger(tmp_path / "al_replay.sqlite")
    payload = _outcome_payload(outcome_id="a" * 32)

    first = ledger.register_outcome(
        outcome_payload=payload,
        observed_at_utc="2026-02-07T19:15:01.000000Z",
    )
    assert first.outcome == REPLAY_NEW

    second = ledger.register_outcome(
        outcome_payload=payload,
        observed_at_utc="2026-02-07T19:15:02.000000Z",
    )
    assert second.outcome == REPLAY_MATCH
    assert second.replay_count == 1

    mutated = dict(payload)
    mutated["status"] = "FAILED"
    mismatch = ledger.register_outcome(
        outcome_payload=mutated,
        observed_at_utc="2026-02-07T19:15:03.000000Z",
    )
    assert mismatch.outcome == REPLAY_PAYLOAD_MISMATCH
    assert mismatch.mismatch_count == 1
    assert ledger.mismatch_count("a" * 32) == 1


def test_duplicate_storm_produces_replay_matches_without_mismatch(tmp_path: Path) -> None:
    ledger = ActionOutcomeReplayLedger(tmp_path / "al_replay.sqlite")
    payload = _outcome_payload(outcome_id="b" * 32)

    first = ledger.register_outcome(
        outcome_payload=payload,
        observed_at_utc="2026-02-07T19:16:00.000000Z",
    )
    assert first.outcome == REPLAY_NEW

    for index in range(50):
        result = ledger.register_outcome(
            outcome_payload=payload,
            observed_at_utc=f"2026-02-07T19:16:{index:02d}.000000Z",
        )
        assert result.outcome == REPLAY_MATCH

    entry = ledger.lookup("b" * 32)
    assert entry is not None
    assert entry.replay_count == 50
    assert entry.mismatch_count == 0


def test_replay_restart_preserves_identity_chain_hash(tmp_path: Path) -> None:
    path = tmp_path / "al_replay.sqlite"
    first = ActionOutcomeReplayLedger(path)
    payloads = [
        _outcome_payload(outcome_id="c" * 32),
        _outcome_payload(outcome_id="d" * 32),
        _outcome_payload(outcome_id="e" * 32),
    ]
    for index, payload in enumerate(payloads):
        first.register_outcome(
            outcome_payload=payload,
            observed_at_utc=f"2026-02-07T19:17:0{index}.000000Z",
        )
    chain_first = first.identity_chain_hash()

    restarted = ActionOutcomeReplayLedger(path)
    for index, payload in enumerate(payloads):
        replay = restarted.register_outcome(
            outcome_payload=payload,
            observed_at_utc=f"2026-02-07T19:17:1{index}.000000Z",
        )
        assert replay.outcome == REPLAY_MATCH
    chain_second = restarted.identity_chain_hash()

    assert chain_first == chain_second

