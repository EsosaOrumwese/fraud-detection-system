from __future__ import annotations

from pathlib import Path

import pytest

import fraud_detection.decision_fabric.replay as replay_module
from fraud_detection.decision_fabric.replay import (
    REPLAY_MATCH,
    REPLAY_NEW,
    REPLAY_PAYLOAD_MISMATCH,
    DecisionReplayLedger,
)


def _decision_payload(*, decision_id: str, action_kind: str) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decision_kind": "fraud_decision_v0",
        "bundle_ref": {"bundle_id": "a" * 64},
        "snapshot_hash": "b" * 64,
        "graph_version": {"version_id": "c" * 32, "watermark_ts_utc": "2026-02-07T12:00:00.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "1"}],
        },
        "degrade_posture": {
            "mode": "NORMAL",
            "capabilities_mask": {
                "allow_ieg": True,
                "allowed_feature_groups": ["core_features"],
                "allow_model_primary": True,
                "allow_model_stage2": False,
                "allow_fallback_heuristics": True,
                "action_posture": "NORMAL",
            },
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1"},
            "posture_seq": 1,
            "decided_at_utc": "2026-02-07T12:00:00.000000Z",
        },
        "pins": {
            "manifest_fingerprint": "d" * 64,
            "parameter_hash": "e" * 64,
            "seed": 7,
            "scenario_id": "fraud_synth_v1",
            "platform_run_id": "platform_20260207T120000Z",
            "scenario_run_id": "f" * 32,
        },
        "decided_at_utc": "2026-02-07T12:00:00.000000Z",
        "policy_rev": {"policy_id": "df.registry_resolution.v0", "revision": "r1"},
        "run_config_digest": "1" * 64,
        "source_event": {
            "event_id": "evt_1",
            "event_type": "transaction_fraud",
            "ts_utc": "2026-02-07T12:00:00.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "1",
                "offset_kind": "kinesis_sequence",
            },
        },
        "decision": {"action_kind": action_kind},
    }


def test_replay_ledger_new_then_match(tmp_path: Path) -> None:
    ledger = DecisionReplayLedger(tmp_path / "replay.sqlite")
    payload = _decision_payload(decision_id="1" * 32, action_kind="ALLOW")
    first = ledger.register_decision(decision_payload=payload, observed_at_utc="2026-02-07T12:00:01.000000Z")
    second = ledger.register_decision(decision_payload=payload, observed_at_utc="2026-02-07T12:00:02.000000Z")

    assert first.outcome == REPLAY_NEW
    assert second.outcome == REPLAY_MATCH
    entry = ledger.lookup("1" * 32)
    assert entry is not None
    assert entry.replay_count == 1
    assert entry.mismatch_count == 0


def test_replay_ledger_payload_mismatch_is_anomaly_and_immutable(tmp_path: Path) -> None:
    ledger = DecisionReplayLedger(tmp_path / "replay.sqlite")
    payload_a = _decision_payload(decision_id="2" * 32, action_kind="ALLOW")
    payload_b = _decision_payload(decision_id="2" * 32, action_kind="STEP_UP")
    first = ledger.register_decision(decision_payload=payload_a, observed_at_utc="2026-02-07T12:00:01.000000Z")
    mismatch = ledger.register_decision(decision_payload=payload_b, observed_at_utc="2026-02-07T12:00:02.000000Z")

    assert first.outcome == REPLAY_NEW
    assert mismatch.outcome == REPLAY_PAYLOAD_MISMATCH
    assert mismatch.stored_payload_hash == first.payload_hash
    entry = ledger.lookup("2" * 32)
    assert entry is not None
    assert entry.payload_hash == first.payload_hash
    assert entry.mismatch_count == 1
    assert ledger.mismatch_count("2" * 32) == 1


def test_replay_ledger_routes_postgres_locator(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _FakeResult:
        def fetchone(self) -> tuple[str, int, int] | None:
            return None

    class _FakeConn:
        def __enter__(self) -> "_FakeConn":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, *_args, **_kwargs) -> _FakeResult:
            return _FakeResult()

    def _fake_connect(dsn: str, **_kwargs):
        calls.append(dsn)
        return _FakeConn()

    monkeypatch.setattr(replay_module, "postgres_threadlocal_connection", _fake_connect)
    ledger = DecisionReplayLedger("postgresql://platform:platform@localhost:5434/platform")
    assert ledger.backend == "postgres"
    assert calls == ["postgresql://platform:platform@localhost:5434/platform"]
