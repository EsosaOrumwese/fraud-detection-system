from __future__ import annotations

from pathlib import Path

import pytest

import fraud_detection.case_trigger.checkpoints as checkpoints_module
from fraud_detection.case_trigger.checkpoints import (
    CHECKPOINT_BLOCKED,
    CHECKPOINT_COMMITTED,
    CaseTriggerCheckpointError,
    CaseTriggerCheckpointGate,
)
from fraud_detection.case_trigger.config import load_trigger_policy
from fraud_detection.case_trigger.publish import (
    PUBLISH_ADMIT,
    PUBLISH_AMBIGUOUS,
    PUBLISH_DUPLICATE,
    PUBLISH_QUARANTINE,
)
from fraud_detection.case_trigger.replay import (
    REPLAY_MATCH,
    REPLAY_NEW,
    CaseTriggerReplayLedger,
)


def _policy():
    return load_trigger_policy(Path("config/platform/case_trigger/trigger_policy_v0.yaml"))


def _trigger_payload() -> dict[str, object]:
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": "decision:dec_001",
        "case_subject_key": {
            "platform_run_id": "platform_20260209T162500Z",
            "event_class": "traffic_fraud",
            "event_id": "evt_decision_trigger_001",
        },
        "pins": {
            "platform_run_id": "platform_20260209T162500Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": "2026-02-09T16:25:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def _checkpoint_ref() -> dict[str, object]:
    return {
        "stream": "fp.bus.case.v1",
        "partition": 0,
        "offset": "11",
        "offset_kind": "kinesis_sequence",
    }


def test_phase5_checkpoint_blocked_until_ledger_and_publish_recorded(tmp_path: Path) -> None:
    gate = CaseTriggerCheckpointGate(tmp_path / "checkpoint.sqlite")
    token = gate.issue_token(
        source_ref_id="decision:dec_001",
        case_trigger_id="a" * 32,
        issued_at_utc="2026-02-09T16:25:01.000000Z",
    )

    blocked_before_ledger = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:25:02.000000Z",
    )
    assert blocked_before_ledger.status == CHECKPOINT_BLOCKED
    assert blocked_before_ledger.reason == "LEDGER_NOT_COMMITTED"

    gate.mark_ledger_committed(token_id=token.token_id)
    blocked_before_publish = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:25:03.000000Z",
    )
    assert blocked_before_publish.status == CHECKPOINT_BLOCKED
    assert blocked_before_publish.reason == "PUBLISH_NOT_RECORDED"


def test_phase5_checkpoint_publish_decision_safety(tmp_path: Path) -> None:
    gate = CaseTriggerCheckpointGate(tmp_path / "checkpoint.sqlite")
    token = gate.issue_token(
        source_ref_id="decision:dec_001",
        case_trigger_id="b" * 32,
        issued_at_utc="2026-02-09T16:26:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token.token_id)

    gate.mark_publish_result(
        token_id=token.token_id,
        publish_decision=PUBLISH_AMBIGUOUS,
        halted=False,
        halt_reason=None,
    )
    blocked_ambiguous = gate.commit_checkpoint(
        token_id=token.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:26:01.000000Z",
    )
    assert blocked_ambiguous.status == CHECKPOINT_BLOCKED
    assert blocked_ambiguous.reason == "PUBLISH_AMBIGUOUS"

    token2 = gate.issue_token(
        source_ref_id="decision:dec_002",
        case_trigger_id="c" * 32,
        issued_at_utc="2026-02-09T16:26:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token2.token_id)
    gate.mark_publish_result(
        token_id=token2.token_id,
        publish_decision=PUBLISH_QUARANTINE,
        halted=False,
        halt_reason=None,
    )
    blocked_quarantine = gate.commit_checkpoint(
        token_id=token2.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:26:02.000000Z",
    )
    assert blocked_quarantine.status == CHECKPOINT_BLOCKED
    assert blocked_quarantine.reason == "PUBLISH_QUARANTINED"

    token_halted = gate.issue_token(
        source_ref_id="decision:dec_004",
        case_trigger_id="h" * 32,
        issued_at_utc="2026-02-09T16:26:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token_halted.token_id)
    gate.mark_publish_result(
        token_id=token_halted.token_id,
        publish_decision=PUBLISH_ADMIT,
        halted=True,
        halt_reason="OFP_HEALTH_NON_OK",
    )
    blocked_halted = gate.commit_checkpoint(
        token_id=token_halted.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:26:02.500000Z",
    )
    assert blocked_halted.status == CHECKPOINT_BLOCKED
    assert blocked_halted.reason == "PUBLISH_HALTED"

    token3 = gate.issue_token(
        source_ref_id="decision:dec_003",
        case_trigger_id="d" * 32,
        issued_at_utc="2026-02-09T16:26:00.000000Z",
    )
    gate.mark_ledger_committed(token_id=token3.token_id)
    gate.mark_publish_result(
        token_id=token3.token_id,
        publish_decision=PUBLISH_DUPLICATE,
        halted=False,
        halt_reason=None,
    )
    committed = gate.commit_checkpoint(
        token_id=token3.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:26:03.000000Z",
    )
    assert committed.status == CHECKPOINT_COMMITTED


def test_phase5_retry_replay_preserves_identity_and_checkpoint_token(tmp_path: Path) -> None:
    replay = CaseTriggerReplayLedger(tmp_path / "replay.sqlite")
    gate = CaseTriggerCheckpointGate(tmp_path / "checkpoint.sqlite")
    payload = _trigger_payload()
    policy = _policy()

    first = replay.register_case_trigger(
        payload=payload,
        source_class="DF_DECISION",
        observed_at_utc="2026-02-09T16:27:00.000000Z",
        policy=policy,
    )
    assert first.outcome == REPLAY_NEW
    token_first = gate.issue_token(
        source_ref_id=str(payload["source_ref_id"]),
        case_trigger_id=first.case_trigger_id,
        issued_at_utc="2026-02-09T16:27:00.100000Z",
    )
    gate.mark_ledger_committed(token_id=token_first.token_id)
    gate.mark_publish_result(
        token_id=token_first.token_id,
        publish_decision=PUBLISH_ADMIT,
        halted=False,
        halt_reason=None,
    )
    first_commit = gate.commit_checkpoint(
        token_id=token_first.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:27:00.200000Z",
    )
    assert first_commit.status == CHECKPOINT_COMMITTED

    retry = replay.register_case_trigger(
        payload=payload,
        source_class="DF_DECISION",
        observed_at_utc="2026-02-09T16:27:01.000000Z",
        policy=policy,
    )
    assert retry.outcome == REPLAY_MATCH
    assert retry.case_trigger_id == first.case_trigger_id

    token_retry = gate.issue_token(
        source_ref_id=str(payload["source_ref_id"]),
        case_trigger_id=retry.case_trigger_id,
        issued_at_utc="2026-02-09T16:27:01.100000Z",
    )
    assert token_retry.token_id == token_first.token_id
    gate.mark_ledger_committed(token_id=token_retry.token_id)
    gate.mark_publish_result(
        token_id=token_retry.token_id,
        publish_decision=PUBLISH_DUPLICATE,
        halted=False,
        halt_reason=None,
    )
    retry_commit = gate.commit_checkpoint(
        token_id=token_retry.token_id,
        checkpoint_ref=_checkpoint_ref(),
        committed_at_utc="2026-02-09T16:27:01.200000Z",
    )
    assert retry_commit.status == CHECKPOINT_COMMITTED


def test_phase5_checkpoint_rejects_unknown_publish_decision(tmp_path: Path) -> None:
    gate = CaseTriggerCheckpointGate(tmp_path / "checkpoint.sqlite")
    token = gate.issue_token(
        source_ref_id="decision:dec_001",
        case_trigger_id="e" * 32,
        issued_at_utc="2026-02-09T16:28:00.000000Z",
    )
    with pytest.raises(CaseTriggerCheckpointError):
        gate.mark_publish_result(
            token_id=token.token_id,
            publish_decision="UNSUPPORTED",
            halted=False,
            halt_reason=None,
        )


def test_phase5_checkpoint_gate_routes_postgres_locator(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _FakeResult:
        rowcount = 1

        def fetchone(self):
            return None

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, *_args, **_kwargs):
            return _FakeResult()

        class _Tx:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        def transaction(self):
            return self._Tx()

    def _fake_connect(dsn: str):
        calls.append(dsn)
        return _FakeConn()

    monkeypatch.setattr(checkpoints_module.psycopg, "connect", _fake_connect)
    gate = CaseTriggerCheckpointGate("postgresql://platform:platform@localhost:5434/platform")
    assert gate.backend == "postgres"
    assert calls == ["postgresql://platform:platform@localhost:5434/platform"]
