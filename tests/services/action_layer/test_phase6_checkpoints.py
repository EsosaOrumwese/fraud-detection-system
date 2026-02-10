from __future__ import annotations

from pathlib import Path

from fraud_detection.action_layer.checkpoints import (
    CHECKPOINT_BLOCKED,
    CHECKPOINT_COMMITTED,
    ActionCheckpointGate,
)
from fraud_detection.action_layer.publish import PUBLISH_ADMIT, PUBLISH_AMBIGUOUS, PUBLISH_DUPLICATE


def test_checkpoint_advances_only_after_outcome_and_publish_gates(tmp_path: Path) -> None:
    gate = ActionCheckpointGate(tmp_path / "al_checkpoint.sqlite")
    token = gate.issue_token(
        outcome_id="1" * 32,
        action_id="2" * 32,
        decision_id="3" * 32,
        issued_at_utc="2026-02-07T19:12:00.000000Z",
    )
    checkpoint_ref = {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset": "12"}

    blocked_before_append = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=checkpoint_ref,
        committed_at_utc="2026-02-07T19:12:01.000000Z",
    )
    assert blocked_before_append.status == CHECKPOINT_BLOCKED
    assert blocked_before_append.reason == "OUTCOME_NOT_COMMITTED"

    gate.mark_outcome_appended(token_id=token.token_id, outcome_hash="a" * 64)
    blocked_before_publish = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=checkpoint_ref,
        committed_at_utc="2026-02-07T19:12:02.000000Z",
    )
    assert blocked_before_publish.status == CHECKPOINT_BLOCKED
    assert blocked_before_publish.reason == "PUBLISH_NOT_RECORDED"

    gate.mark_publish_result(
        token_id=token.token_id,
        publish_decision=PUBLISH_ADMIT,
        receipt_ref="runs/fraud-platform/x/ig/receipts/r1.json",
        reason_code=None,
    )
    committed = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=checkpoint_ref,
        committed_at_utc="2026-02-07T19:12:03.000000Z",
    )
    assert committed.status == CHECKPOINT_COMMITTED
    assert committed.reason is None


def test_checkpoint_blocks_when_publish_is_ambiguous(tmp_path: Path) -> None:
    gate = ActionCheckpointGate(tmp_path / "al_checkpoint.sqlite")
    token = gate.issue_token(
        outcome_id="4" * 32,
        action_id="5" * 32,
        decision_id="6" * 32,
        issued_at_utc="2026-02-07T19:13:00.000000Z",
    )
    gate.mark_outcome_appended(token_id=token.token_id, outcome_hash="b" * 64)
    gate.mark_publish_result(
        token_id=token.token_id,
        publish_decision=PUBLISH_AMBIGUOUS,
        receipt_ref=None,
        reason_code="IG_PUSH_RETRY_EXHAUSTED:timeout",
    )
    blocked = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref={"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset": "13"},
        committed_at_utc="2026-02-07T19:13:01.000000Z",
    )
    assert blocked.status == CHECKPOINT_BLOCKED
    assert blocked.reason == "PUBLISH_AMBIGUOUS"


def test_checkpoint_restart_recovery_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "al_checkpoint.sqlite"
    first = ActionCheckpointGate(path)
    token = first.issue_token(
        outcome_id="7" * 32,
        action_id="8" * 32,
        decision_id="9" * 32,
        issued_at_utc="2026-02-07T19:14:00.000000Z",
    )
    first.mark_outcome_appended(token_id=token.token_id, outcome_hash="c" * 64)
    first.mark_publish_result(
        token_id=token.token_id,
        publish_decision=PUBLISH_DUPLICATE,
        receipt_ref="runs/fraud-platform/x/ig/receipts/r2.json",
        reason_code=None,
    )
    committed_first = first.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref={"topic": "fp.bus.traffic.fraud.v1", "partition": 1, "offset": "14"},
        committed_at_utc="2026-02-07T19:14:01.000000Z",
    )
    assert committed_first.status == CHECKPOINT_COMMITTED

    restarted = ActionCheckpointGate(path)
    committed_second = restarted.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref={"topic": "fp.bus.traffic.fraud.v1", "partition": 1, "offset": "14"},
        committed_at_utc="2026-02-07T19:14:02.000000Z",
    )
    assert committed_second.status == CHECKPOINT_COMMITTED

