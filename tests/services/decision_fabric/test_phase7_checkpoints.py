from __future__ import annotations

from pathlib import Path

from fraud_detection.decision_fabric.checkpoints import (
    CHECKPOINT_BLOCKED,
    CHECKPOINT_COMMITTED,
    DecisionCheckpointGate,
)
from fraud_detection.decision_fabric.publish import PUBLISH_ADMIT, PUBLISH_DUPLICATE, PUBLISH_QUARANTINE


def _checkpoint_ref() -> dict[str, object]:
    return {
        "stream": "fp.bus.traffic.fraud.v1",
        "partition": 0,
        "offset": "10",
        "offset_kind": "kinesis_sequence",
    }


def test_checkpoint_blocked_until_ledger_and_publish_are_recorded(tmp_path: Path) -> None:
    gate = DecisionCheckpointGate(tmp_path / "checkpoint.sqlite")
    token = gate.issue_token(
        source_event_id="evt_1",
        decision_id="1" * 32,
        issued_at_utc="2026-02-07T12:00:00.000000Z",
    )

    blocked_before_ledger = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-07T12:00:01.000000Z",
    )
    assert blocked_before_ledger.status == CHECKPOINT_BLOCKED
    assert blocked_before_ledger.reason == "LEDGER_NOT_COMMITTED"

    gate.mark_ledger_committed(token_id=token.token_id)
    blocked_before_publish = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-07T12:00:02.000000Z",
    )
    assert blocked_before_publish.status == CHECKPOINT_BLOCKED
    assert blocked_before_publish.reason == "PUBLISH_NOT_RECORDED"


def test_checkpoint_blocks_quarantine_and_allows_admit_duplicate(tmp_path: Path) -> None:
    gate = DecisionCheckpointGate(tmp_path / "checkpoint.sqlite")

    token_quarantine = gate.issue_token(
        source_event_id="evt_q",
        decision_id="2" * 32,
        issued_at_utc="2026-02-07T12:00:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token_quarantine.token_id)
    gate.mark_publish_result(
        token_id=token_quarantine.token_id,
        decision_publish=PUBLISH_QUARANTINE,
        action_publishes=tuple(),
        halted=True,
        halt_reason="DECISION_QUARANTINED",
    )
    blocked = gate.commit_checkpoint(
        token_id=token_quarantine.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-07T12:00:01.000000Z",
    )
    assert blocked.status == CHECKPOINT_BLOCKED
    assert blocked.reason == "PUBLISH_HALTED"

    token_admit = gate.issue_token(
        source_event_id="evt_a",
        decision_id="3" * 32,
        issued_at_utc="2026-02-07T12:00:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token_admit.token_id)
    gate.mark_publish_result(
        token_id=token_admit.token_id,
        decision_publish=PUBLISH_ADMIT,
        action_publishes=(PUBLISH_ADMIT,),
        halted=False,
        halt_reason=None,
    )
    committed_admit = gate.commit_checkpoint(
        token_id=token_admit.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-07T12:00:02.000000Z",
    )
    assert committed_admit.status == CHECKPOINT_COMMITTED

    token_duplicate = gate.issue_token(
        source_event_id="evt_d",
        decision_id="4" * 32,
        issued_at_utc="2026-02-07T12:00:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token_duplicate.token_id)
    gate.mark_publish_result(
        token_id=token_duplicate.token_id,
        decision_publish=PUBLISH_DUPLICATE,
        action_publishes=(PUBLISH_DUPLICATE,),
        halted=False,
        halt_reason=None,
    )
    committed_duplicate = gate.commit_checkpoint(
        token_id=token_duplicate.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-07T12:00:03.000000Z",
    )
    assert committed_duplicate.status == CHECKPOINT_COMMITTED


def test_checkpoint_blocks_when_action_is_quarantined(tmp_path: Path) -> None:
    gate = DecisionCheckpointGate(tmp_path / "checkpoint.sqlite")
    token = gate.issue_token(
        source_event_id="evt_qa",
        decision_id="5" * 32,
        issued_at_utc="2026-02-07T12:00:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token.token_id)
    gate.mark_publish_result(
        token_id=token.token_id,
        decision_publish=PUBLISH_ADMIT,
        action_publishes=(PUBLISH_ADMIT, PUBLISH_QUARANTINE),
        halted=False,
        halt_reason=None,
    )
    blocked = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-07T12:00:01.000000Z",
    )
    assert blocked.status == CHECKPOINT_BLOCKED
    assert blocked.reason == "ACTION_QUARANTINED"
