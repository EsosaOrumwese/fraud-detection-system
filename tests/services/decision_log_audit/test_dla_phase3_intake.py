from __future__ import annotations

from dataclasses import replace
import sqlite3
from pathlib import Path

from fraud_detection.decision_log_audit.config import load_intake_policy
from fraud_detection.decision_log_audit.inlet import (
    DLA_INLET_ACCEPT,
    DLA_INLET_PAYLOAD_CONTRACT_INVALID,
    DLA_INLET_RUN_SCOPE_MISMATCH,
    DLA_INLET_UNKNOWN_EVENT_FAMILY,
    DlaBusInput,
    DecisionLogAuditInlet,
)
from fraud_detection.decision_log_audit.intake import (
    DLA_INTAKE_RUN_SCOPE_SKIPPED,
    DLA_INTAKE_PAYLOAD_HASH_MISMATCH,
    DLA_INTAKE_WRITE_FAILED,
    DecisionLogAuditBusConsumer,
    DecisionLogAuditIntakeProcessor,
    DecisionLogAuditIntakeRuntimeConfig,
)
from fraud_detection.decision_log_audit.storage import DecisionLogAuditIntakeStore


def _policy():
    return load_intake_policy(Path("config/platform/dla/intake_policy_v0.yaml"))


def _decision_payload(*, amount: float = 100.0) -> dict[str, object]:
    return {
        "decision_id": "a" * 32,
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
            "platform_run_id": "platform_20260207T102700Z",
            "scenario_run_id": "1" * 32,
            "manifest_fingerprint": "2" * 64,
            "parameter_hash": "3" * 64,
            "scenario_id": "scenario.v0",
            "seed": 42,
        },
        "decided_at_utc": "2026-02-07T10:27:00.000000Z",
        "policy_rev": {"policy_id": "df.policy.v0", "revision": "r8"},
        "run_config_digest": "4" * 64,
        "source_event": {
            "event_id": "evt_abc",
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


def _decision_envelope(*, event_id: str = "evt_100", amount: float = 100.0) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": "decision_response",
        "schema_version": "v1",
        "ts_utc": "2026-02-07T10:45:00.000000Z",
        "manifest_fingerprint": "2" * 64,
        "parameter_hash": "3" * 64,
        "seed": 42,
        "scenario_id": "scenario.v0",
        "platform_run_id": "platform_20260207T102700Z",
        "scenario_run_id": "1" * 32,
        "run_id": "1" * 32,
        "payload": _decision_payload(amount=amount),
    }


def test_phase3_intake_policy_loads_and_exposes_allowlist() -> None:
    policy = _policy()
    assert policy.policy_id == "dla.intake.v0"
    assert policy.allowed_schema_versions("decision_response") == ("v1",)
    assert policy.payload_contract("action_outcome") == "action_outcome"


def test_phase3_inlet_accepts_valid_decision_response() -> None:
    inlet = DecisionLogAuditInlet(_policy())
    result = inlet.evaluate(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="100",
            offset_kind="kinesis_sequence",
            payload=_decision_envelope(),
            published_at_utc="2026-02-07T10:45:01.000000Z",
        )
    )
    assert result.accepted is True
    assert result.reason_code == DLA_INLET_ACCEPT
    assert result.candidate is not None
    assert result.candidate.event_type == "decision_response"


def test_phase3_inlet_rejects_unknown_event_family() -> None:
    inlet = DecisionLogAuditInlet(_policy())
    envelope = _decision_envelope()
    envelope["event_type"] = "arrival_events_5B"
    result = inlet.evaluate(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="100",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == DLA_INLET_UNKNOWN_EVENT_FAMILY


def test_phase3_inlet_enforces_run_scope_before_event_family() -> None:
    policy = replace(_policy(), required_platform_run_id="platform_20260207T102700Z")
    inlet = DecisionLogAuditInlet(policy)
    envelope = _decision_envelope()
    envelope["event_type"] = "arrival_events_5B"
    envelope["platform_run_id"] = "platform_20260207T102701Z"
    result = inlet.evaluate(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="100",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == DLA_INLET_RUN_SCOPE_MISMATCH


def test_phase3_inlet_rejects_incomplete_payload_contract() -> None:
    inlet = DecisionLogAuditInlet(_policy())
    envelope = _decision_envelope()
    envelope["payload"] = {"decision_kind": "txn_disposition"}
    result = inlet.evaluate(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="100",
            offset_kind="kinesis_sequence",
            payload=envelope,
        )
    )
    assert result.accepted is False
    assert result.reason_code == DLA_INLET_PAYLOAD_CONTRACT_INVALID


def test_phase3_processor_does_not_advance_checkpoint_when_quarantine_write_fails(tmp_path: Path, monkeypatch) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    def _boom(**kwargs):
        raise RuntimeError("quarantine down")

    monkeypatch.setattr(store, "append_quarantine", _boom)

    result = processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="0",
            offset_kind="file_line",
            payload={"bad": "envelope"},
        )
    )
    assert result.reason_code == DLA_INTAKE_WRITE_FAILED
    assert result.checkpoint_advanced is False
    assert store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0) is None


def test_phase3_processor_does_not_advance_checkpoint_when_candidate_write_fails(tmp_path: Path, monkeypatch) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    def _boom(**kwargs):
        raise RuntimeError("candidate write failed")

    monkeypatch.setattr(store, "append_candidate", _boom)

    result = processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="0",
            offset_kind="file_line",
            payload=_decision_envelope(),
        )
    )
    assert result.reason_code == DLA_INTAKE_WRITE_FAILED
    assert result.checkpoint_advanced is False
    assert store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0) is None


def test_phase3_processor_advances_checkpoint_for_quarantine_path(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    result = processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="0",
            offset_kind="file_line",
            payload={"bad": "envelope"},
        )
    )
    assert result.accepted is False
    assert result.checkpoint_advanced is True
    checkpoint = store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0)
    assert checkpoint is not None
    assert checkpoint.next_offset == "1"


def test_phase3_processor_run_scope_mismatch_skips_quarantine_and_advances_checkpoint(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    policy = replace(_policy(), required_platform_run_id="platform_20260207T102701Z")
    processor = DecisionLogAuditIntakeProcessor(policy, store)

    result = processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="0",
            offset_kind="file_line",
            payload=_decision_envelope(),
        )
    )

    assert result.accepted is False
    assert result.reason_code == DLA_INLET_RUN_SCOPE_MISMATCH
    assert result.write_status == DLA_INTAKE_RUN_SCOPE_SKIPPED
    assert result.checkpoint_advanced is True

    checkpoint = store.get_checkpoint(topic="fp.bus.traffic.fraud.v1", partition=0)
    assert checkpoint is not None
    assert checkpoint.next_offset == "1"

    conn = sqlite3.connect(locator)
    quarantine_count = conn.execute("SELECT COUNT(*) FROM dla_intake_quarantine").fetchone()
    conn.close()
    assert quarantine_count is not None
    assert int(quarantine_count[0]) == 0


def test_phase3_processor_routes_hash_mismatch_to_quarantine_and_advances_checkpoint(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    processor = DecisionLogAuditIntakeProcessor(_policy(), store)

    first = processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="0",
            offset_kind="file_line",
            payload=_decision_envelope(event_id="evt_same", amount=100.0),
        )
    )
    second = processor.process_record(
        DlaBusInput(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="1",
            offset_kind="file_line",
            payload=_decision_envelope(event_id="evt_same", amount=999.0),
        )
    )

    assert first.accepted is True
    assert first.checkpoint_advanced is True
    assert second.accepted is False
    assert second.reason_code == DLA_INTAKE_PAYLOAD_HASH_MISMATCH
    assert second.checkpoint_advanced is True

    conn = sqlite3.connect(locator)
    row = conn.execute(
        "SELECT reason_code FROM dla_intake_quarantine WHERE source_partition = ? AND source_offset = ?",
        (0, "1"),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == DLA_INTAKE_PAYLOAD_HASH_MISMATCH


def test_phase3_intake_metrics_snapshot_counts_accepted_attempts(tmp_path: Path) -> None:
    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    platform_run_id = "platform_20260209T102145Z"
    scenario_run_id = "001e5209754de3e6332eb3e100d420ee"

    accepted = store.record_intake_attempt(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="0",
        offset_kind="file_line",
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        event_type="decision_response",
        event_id="evt_accept",
        accepted=True,
        reason_code=DLA_INLET_ACCEPT,
        write_status="NEW",
        checkpoint_advanced=True,
        detail=None,
    )
    rejected = store.record_intake_attempt(
        topic="fp.bus.traffic.fraud.v1",
        partition=0,
        offset="1",
        offset_kind="file_line",
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
        event_type="decision_response",
        event_id="evt_reject",
        accepted=False,
        reason_code=DLA_INTAKE_PAYLOAD_HASH_MISMATCH,
        write_status="NEW",
        checkpoint_advanced=True,
        detail=None,
    )

    assert accepted.status == "NEW"
    assert rejected.status == "NEW"

    metrics = store.intake_metrics_snapshot(
        platform_run_id=platform_run_id,
        scenario_run_id=scenario_run_id,
    )
    assert metrics["accepted_total"] == 1
    assert metrics["rejected_total"] == 1


def test_phase3_kinesis_consumer_uses_trim_horizon_for_initial_run_scoped_read(tmp_path: Path, monkeypatch) -> None:
    class _FakeKinesisReader:
        def __init__(self, *, stream_name: str | None, region: str | None = None, endpoint_url: str | None = None) -> None:
            self.calls: list[dict[str, object]] = []

        def list_shards(self, stream_name: str) -> list[str]:
            return ["shardId-000000000000"]

        def read(
            self,
            *,
            stream_name: str,
            shard_id: str,
            from_sequence: str | None,
            limit: int,
            start_position: str = "trim_horizon",
        ) -> list[dict[str, object]]:
            self.calls.append(
                {
                    "stream_name": stream_name,
                    "shard_id": shard_id,
                    "from_sequence": from_sequence,
                    "limit": limit,
                    "start_position": start_position,
                }
            )
            return []

    monkeypatch.setattr("fraud_detection.event_bus.kinesis.KinesisEventBusReader", _FakeKinesisReader)

    locator = str(tmp_path / "dla_intake.sqlite")
    store = DecisionLogAuditIntakeStore(locator=locator)
    policy = replace(_policy(), required_platform_run_id="platform_20260207T102701Z")
    consumer = DecisionLogAuditBusConsumer(
        policy=policy,
        store=store,
        runtime=DecisionLogAuditIntakeRuntimeConfig(
            event_bus_kind="kinesis",
            event_bus_stream="auto",
            event_bus_region="us-east-1",
            event_bus_endpoint_url="http://localhost:4566",
            event_bus_start_position="latest",
            poll_max_records=10,
            poll_sleep_seconds=0.1,
        ),
    )

    processed = consumer.run_once()
    assert processed == 0
    assert consumer._kinesis_reader is not None
    assert len(consumer._kinesis_reader.calls) == 1
    assert consumer._kinesis_reader.calls[0]["start_position"] == "trim_horizon"
