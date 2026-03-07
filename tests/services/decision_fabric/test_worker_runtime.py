from __future__ import annotations

from types import SimpleNamespace

from fraud_detection.decision_fabric.context import CONTEXT_WAITING
from fraud_detection.decision_fabric.inlet import DecisionTriggerCandidate, DfInletResult, SourceEbRef
from fraud_detection.decision_fabric.worker import DecisionFabricWorker, _decision_started_at


def _candidate() -> DecisionTriggerCandidate:
    return DecisionTriggerCandidate(
        source_event_id="evt_001",
        event_class="traffic_fraud",
        payload_hash="f" * 64,
        source_event_type="s3_event_stream_with_fraud_6B",
        schema_version="v1",
        source_ts_utc="2026-03-07T10:00:00.000000Z",
        pins={
            "platform_run_id": "platform_20260307T100000Z",
            "scenario_run_id": "a" * 32,
            "manifest_fingerprint": "b" * 64,
            "parameter_hash": "c" * 64,
            "scenario_id": "fraud_synth_v1",
            "seed": 7,
        },
        source_eb_ref=SourceEbRef(
            topic="fp.bus.traffic.fraud.v1",
            partition=0,
            offset="101",
            offset_kind="kafka_offset",
            published_at_utc="2026-03-07T10:00:01.123456Z",
        ),
    )


def test_decision_started_at_prefers_valid_publish_timestamp() -> None:
    assert (
        _decision_started_at(
            published_at_utc="2026-03-07T10:00:01.123456Z",
            observed_at_utc="2026-03-07T10:00:05.000000Z",
        )
        == "2026-03-07T10:00:01.123456Z"
    )


def test_decision_started_at_falls_back_when_publish_timestamp_invalid() -> None:
    assert (
        _decision_started_at(
            published_at_utc="not-a-timestamp",
            observed_at_utc="2026-03-07T10:00:05.000000Z",
        )
        == "2026-03-07T10:00:05.000000Z"
    )


def test_worker_defers_context_waiting_without_publish_or_advance() -> None:
    candidate = _candidate()
    row = {
        "topic": candidate.source_eb_ref.topic,
        "partition": candidate.source_eb_ref.partition,
        "offset": candidate.source_eb_ref.offset,
        "offset_kind": candidate.source_eb_ref.offset_kind,
        "payload": {
            "event_id": candidate.source_event_id,
            "event_type": candidate.source_event_type,
            "schema_version": candidate.schema_version,
            "ts_utc": candidate.source_ts_utc,
            **candidate.pins,
            "payload": {"flow_id": "flow-1"},
        },
        "published_at_utc": candidate.source_eb_ref.published_at_utc,
    }

    class _Checkpoints:
        def __init__(self) -> None:
            self.deferred: list[tuple[str, int, str, str]] = []
            self.advanced: list[tuple[str, int, str, str]] = []

        def defer(self, *, topic: str, partition: int, offset: str, offset_kind: str) -> None:
            self.deferred.append((topic, partition, offset, offset_kind))

        def advance(self, *, topic: str, partition: int, offset: str, offset_kind: str) -> None:
            self.advanced.append((topic, partition, offset, offset_kind))

    worker = DecisionFabricWorker.__new__(DecisionFabricWorker)
    worker.config = SimpleNamespace(required_platform_run_id=candidate.pins["platform_run_id"])
    worker.inlet = SimpleNamespace(
        evaluate=lambda _bus: DfInletResult(accepted=True, reason_code="ACCEPT", candidate=candidate)
    )
    worker.consumer_checkpoints = _Checkpoints()
    worker._ensure_scenario = lambda _candidate: True
    worker._resolve_posture = lambda _candidate: SimpleNamespace()
    worker._context_refs = lambda _candidate, _envelope: {}
    worker.acquirer = SimpleNamespace(
        acquire=lambda **_kwargs: SimpleNamespace(
            status=CONTEXT_WAITING,
            reasons=("CONTEXT_WAITING:arrival_events", "CONTEXT_WAITING:flow_anchor"),
        )
    )
    worker._metrics = None
    worker._reconciliation = None

    worker._process_record(row)

    assert worker.consumer_checkpoints.deferred == [
        (candidate.source_eb_ref.topic, candidate.source_eb_ref.partition, candidate.source_eb_ref.offset, candidate.source_eb_ref.offset_kind)
    ]
    assert worker.consumer_checkpoints.advanced == []
