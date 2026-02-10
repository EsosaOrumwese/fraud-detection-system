from __future__ import annotations

from pathlib import Path

import pytest

from fraud_detection.case_trigger.config import load_trigger_policy
from fraud_detection.case_trigger.replay import (
    REPLAY_MATCH,
    REPLAY_NEW,
    REPLAY_PAYLOAD_MISMATCH,
    CaseTriggerReplayError,
    CaseTriggerReplayLedger,
)


def _policy():
    return load_trigger_policy(Path("config/platform/case_trigger/trigger_policy_v0.yaml"))


def _trigger_payload(*, source_ref_id: str = "decision:dec_001") -> dict[str, object]:
    return {
        "trigger_type": "DECISION_ESCALATION",
        "source_ref_id": source_ref_id,
        "case_subject_key": {
            "platform_run_id": "platform_20260209T160500Z",
            "event_class": "traffic_fraud",
            "event_id": "evt_decision_trigger_001",
        },
        "pins": {
            "platform_run_id": "platform_20260209T160500Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "observed_time": "2026-02-09T16:05:00.000000Z",
        "evidence_refs": [
            {"ref_type": "DECISION", "ref_id": "dec_001"},
            {"ref_type": "DLA_AUDIT_RECORD", "ref_id": "audit_001"},
        ],
        "trigger_payload": {"severity": "HIGH"},
    }


def test_phase3_replay_registers_new_match_and_payload_mismatch(tmp_path: Path) -> None:
    ledger = CaseTriggerReplayLedger(tmp_path / "case_trigger_replay.sqlite")
    payload = _trigger_payload()
    policy = _policy()

    first = ledger.register_case_trigger(
        payload=payload,
        source_class="DF_DECISION",
        observed_at_utc="2026-02-09T16:05:01.000000Z",
        policy=policy,
    )
    assert first.outcome == REPLAY_NEW

    second = ledger.register_case_trigger(
        payload=payload,
        source_class="DF_DECISION",
        observed_at_utc="2026-02-09T16:05:02.000000Z",
        policy=policy,
    )
    assert second.outcome == REPLAY_MATCH
    assert second.replay_count == 1

    mutated = _trigger_payload()
    mutated["trigger_payload"] = {"severity": "CRITICAL"}
    mismatch = ledger.register_case_trigger(
        payload=mutated,
        source_class="DF_DECISION",
        observed_at_utc="2026-02-09T16:05:03.000000Z",
        policy=policy,
    )
    assert mismatch.outcome == REPLAY_PAYLOAD_MISMATCH
    assert mismatch.mismatch_count == 1
    assert ledger.mismatch_count(mismatch.case_trigger_id) == 1

    entry = ledger.lookup(mismatch.case_trigger_id)
    assert entry is not None
    assert entry.payload_hash == first.payload_hash
    assert entry.replay_count == 1
    assert entry.mismatch_count == 1


def test_phase3_replay_restart_preserves_identity_chain_hash(tmp_path: Path) -> None:
    path = tmp_path / "case_trigger_replay.sqlite"
    first = CaseTriggerReplayLedger(path)
    policy = _policy()
    payloads = [
        _trigger_payload(source_ref_id="decision:dec_001"),
        _trigger_payload(source_ref_id="decision:dec_002"),
        _trigger_payload(source_ref_id="decision:dec_003"),
    ]
    for index, payload in enumerate(payloads):
        result = first.register_case_trigger(
            payload=payload,
            source_class="DF_DECISION",
            observed_at_utc=f"2026-02-09T16:06:0{index}.000000Z",
            policy=policy,
        )
        assert result.outcome == REPLAY_NEW
    chain_first = first.identity_chain_hash()

    restarted = CaseTriggerReplayLedger(path)
    for index, payload in enumerate(payloads):
        replay = restarted.register_case_trigger(
            payload=payload,
            source_class="DF_DECISION",
            observed_at_utc=f"2026-02-09T16:06:1{index}.000000Z",
            policy=policy,
        )
        assert replay.outcome == REPLAY_MATCH
    chain_second = restarted.identity_chain_hash()
    assert chain_first == chain_second


def test_phase3_replay_rejects_contract_invalid_payload(tmp_path: Path) -> None:
    ledger = CaseTriggerReplayLedger(tmp_path / "invalid_payload.sqlite")
    payload = _trigger_payload()
    payload["trigger_type"] = "UNSUPPORTED"
    with pytest.raises(CaseTriggerReplayError):
        ledger.register_case_trigger(
            payload=payload,
            source_class="DF_DECISION",
            observed_at_utc="2026-02-09T16:07:00.000000Z",
            policy=_policy(),
        )


def test_phase3_replay_rejects_source_class_mismatch(tmp_path: Path) -> None:
    ledger = CaseTriggerReplayLedger(tmp_path / "source_mismatch.sqlite")
    with pytest.raises(CaseTriggerReplayError):
        ledger.register_case_trigger(
            payload=_trigger_payload(),
            source_class="AL_OUTCOME",
            observed_at_utc="2026-02-09T16:07:01.000000Z",
            policy=_policy(),
        )
