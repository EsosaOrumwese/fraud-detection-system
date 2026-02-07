from __future__ import annotations

import sqlite3
from pathlib import Path

from fraud_detection.decision_log_audit.config import load_intake_policy
from fraud_detection.decision_log_audit.intake import (
    DLA_INTAKE_REPLAY_DIVERGENCE,
    DLA_INTAKE_WRITE_FAILED,
    DlaBusInput,
    DecisionLogAuditIntakeProcessor,
)
from fraud_detection.decision_log_audit.storage import DecisionLogAuditIntakeStore


PINS = {
    "platform_run_id": "platform_20260207T102700Z",
    "scenario_run_id": "1" * 32,
    "manifest_fingerprint": "2" * 64,
    "parameter_hash": "3" * 64,
    "scenario_id": "scenario.v0",
    "seed": 42,
    "run_id": "1" * 32,
}


def _policy():
    return load_intake_policy(Path("config/platform/dla/intake_policy_v0.yaml"))


def _decision_payload(*, decision_id: str = "a" * 32, amount: float = 100.0) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decision_kind": "txn_disposition",
        "bundle_ref": {"bundle_id": "b" * 64, "bundle_version": "2026.02.07", "registry_ref": "registry://active"},
        "snapshot_hash": "c" * 64,
        "graph_version": {"version_id": "d" * 32, "watermark_ts_utc": "2026-02-07T10:27:00.000000Z"},
        "eb_offset_basis": {
            "stream": "fp.bus.traffic.fraud.v1",
            "offset_kind": "kinesis_sequence",
            "offsets": [{"partition": 0, "offset": "101"}],
        },
        "degrade_posture": {
            "mode": "NORMAL",
            "capabilities_mask": {
                "allow_ieg": True,
                "allowed_feature_groups": ["core_features"],
                "allow_model_primary": True,
                "allow_model_stage2": True,
                "allow_fallback_heuristics": True,
                "action_posture": "NORMAL",
            },
            "policy_rev": {"policy_id": "dl.policy.v0", "revision": "r1"},
            "posture_seq": 3,
            "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        },
        "pins": {
            "platform_run_id": PINS["platform_run_id"],
            "scenario_run_id": PINS["scenario_run_id"],
            "manifest_fingerprint": PINS["manifest_fingerprint"],
            "parameter_hash": PINS["parameter_hash"],
            "scenario_id": PINS["scenario_id"],
            "seed": PINS["seed"],
            "run_id": PINS["run_id"],
        },
        "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8"},
        "run_config_digest": "4" * 64,
        "source_event": {
            "event_id": "evt_src",
            "event_type": "transaction_authorization",
            "ts_utc": "2026-02-07T10:26:59.000000Z",
            "eb_ref": {
                "topic": "fp.bus.traffic.fraud.v1",
                "partition": 0,
                "offset": "100",
                "offset_kind": "kinesis_sequence",
            },
        },
        "decision": {"disposition": "ALLOW", "amount": amount},
    }


def _envelope(*, event_id: str, decision_id: str = "a" * 32, amount: float = 100.0) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "decision_response",
        "schema_version": "v1",
        "ts_utc": "2026-02-07T10:45:00.000000Z",
        "manifest_fingerprint": PINS["manifest_fingerprint"],
        "parameter_hash": PINS["parameter_hash"],
        "seed": PINS["seed"],
        "scenario_id": PINS["scenario_id"],
        "platform_run_id": PINS["platform_run_id"],
        "scenario_run_id": PINS["scenario_run_id"],
        "run_id": PINS["run_id"],
        "payload": _decision_payload(decision_id=decision_id, amount=amount),
    }


def _process(processor: DecisionLogAuditIntakeProcessor, *, offset: str, envelope: dict[str, object]):
    return processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset=offset,
            offset_kind="file_line",
            payload=envelope,
        )
    )


def test_phase6_crash_restart_replay_reconstructs_lineage_before_checkpoint(tmp_path: Path, monkeypatch) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    original_apply = store.apply_lineage_candidate
    state = {"calls": 0}

    def _flaky_apply(**kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("lineage temporarily unavailable")
        return original_apply(**kwargs)

    monkeypatch.setattr(store, "apply_lineage_candidate", _flaky_apply)

    first = _process(processor, offset="0", envelope=_envelope(event_id="evt_decision_retry"))
    assert first.accepted is False
    assert first.reason_code == DLA_INTAKE_WRITE_FAILED
    assert first.checkpoint_advanced is False

    second = _process(processor, offset="0", envelope=_envelope(event_id="evt_decision_retry"))
    assert second.accepted is True
    assert second.checkpoint_advanced is True

    checkpoint = store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0)
    assert checkpoint is not None
    assert checkpoint.next_offset == "1"

    chain = store.get_lineage_chain(decision_id="a" * 32)
    assert chain is not None
    assert chain.decision_event_id == "evt_decision_retry"

    conn = sqlite3.connect(locator)
    candidate_count = conn.execute("SELECT COUNT(*) FROM dla_intake_candidates").fetchone()[0]
    conn.close()
    assert candidate_count == 1


def test_phase6_replay_same_offset_same_signature_is_idempotent(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    first = _process(processor, offset="0", envelope=_envelope(event_id="evt_decision_same"))
    second = _process(processor, offset="0", envelope=_envelope(event_id="evt_decision_same"))

    assert first.accepted is True
    assert second.accepted is True
    checkpoint = store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0)
    assert checkpoint is not None
    assert checkpoint.next_offset == "1"

    conn = sqlite3.connect(locator)
    candidate_count = conn.execute("SELECT COUNT(*) FROM dla_intake_candidates").fetchone()[0]
    replay_obs_count = conn.execute("SELECT COUNT(*) FROM dla_intake_replay_observations").fetchone()[0]
    conn.close()
    assert candidate_count == 1
    assert replay_obs_count == 1


def test_phase6_replay_divergence_emits_anomaly_and_blocks_checkpoint(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    first = _process(
        processor,
        offset="0",
        envelope=_envelope(event_id="evt_decision_original", decision_id="f" * 32, amount=100.0),
    )
    second = _process(
        processor,
        offset="0",
        envelope=_envelope(event_id="evt_decision_drift", decision_id="f" * 32, amount=999.0),
    )

    assert first.accepted is True
    assert second.accepted is False
    assert second.reason_code == DLA_INTAKE_REPLAY_DIVERGENCE
    assert second.checkpoint_advanced is False

    checkpoint = store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0)
    assert checkpoint is not None
    assert checkpoint.next_offset == "1"

    conn = sqlite3.connect(locator)
    candidate_count = conn.execute("SELECT COUNT(*) FROM dla_intake_candidates").fetchone()[0]
    quarantine_row = conn.execute(
        "SELECT reason_code FROM dla_intake_quarantine WHERE source_partition = ? AND source_offset = ?",
        (0, "0"),
    ).fetchall()
    conn.close()
    assert candidate_count == 1
    assert any(str(row[0]) == DLA_INTAKE_REPLAY_DIVERGENCE for row in quarantine_row)
