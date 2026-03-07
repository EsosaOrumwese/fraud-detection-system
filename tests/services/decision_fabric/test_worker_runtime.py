from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fraud_detection.decision_fabric.context import CONTEXT_WAITING
from fraud_detection.decision_fabric.inlet import DecisionTriggerCandidate, DfInletResult, SourceEbRef
from fraud_detection.decision_fabric.observability import DfRunMetrics
from fraud_detection.decision_fabric.reconciliation import DfReconciliationBuilder
from fraud_detection.decision_fabric.worker import DecisionFabricWorker, _ConsumerCheckpointStore, _decision_started_at


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
            self.first_seen_requests: list[tuple[str, int, str, str, str]] = []

        def defer(self, *, topic: str, partition: int, offset: str, offset_kind: str) -> None:
            self.deferred.append((topic, partition, offset, offset_kind))

        def advance(self, *, topic: str, partition: int, offset: str, offset_kind: str) -> None:
            self.advanced.append((topic, partition, offset, offset_kind))

        def ensure_first_seen(
            self,
            *,
            topic: str,
            partition: int,
            offset: str,
            offset_kind: str,
            observed_at_utc: str,
        ) -> str:
            self.first_seen_requests.append((topic, partition, offset, offset_kind, observed_at_utc))
            return observed_at_utc

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
            reasons=("CONTEXT_WAITING:flow_anchor",),
        )
    )
    worker._metrics = None
    worker._reconciliation = None

    outcome = worker._process_record(row)

    assert outcome == "BLOCKED"
    assert worker.consumer_checkpoints.deferred == [
        (candidate.source_eb_ref.topic, candidate.source_eb_ref.partition, candidate.source_eb_ref.offset, candidate.source_eb_ref.offset_kind)
    ]
    assert worker.consumer_checkpoints.advanced == []


def test_consumer_checkpoint_store_persists_first_seen_for_same_offset(tmp_path: Path) -> None:
    path = tmp_path / "df_consumer_checkpoints.sqlite"
    store = _ConsumerCheckpointStore(path, "df.v0::run")

    first = store.ensure_first_seen(
        topic="fp.bus.traffic.fraud.v1",
        partition=1,
        offset="42",
        offset_kind="kafka_offset",
        observed_at_utc="2026-03-07T15:00:00.000000Z",
    )
    restarted_store = _ConsumerCheckpointStore(path, "df.v0::run")
    second = restarted_store.ensure_first_seen(
        topic="fp.bus.traffic.fraud.v1",
        partition=1,
        offset="42",
        offset_kind="kafka_offset",
        observed_at_utc="2026-03-07T15:00:05.000000Z",
    )

    assert first == "2026-03-07T15:00:00.000000Z"
    assert second == first


def test_consumer_checkpoint_store_clears_first_seen_on_advance(tmp_path: Path) -> None:
    store = _ConsumerCheckpointStore(tmp_path / "df_consumer_checkpoints.sqlite", "df.v0::run")

    first = store.ensure_first_seen(
        topic="fp.bus.traffic.fraud.v1",
        partition=2,
        offset="99",
        offset_kind="kafka_offset",
        observed_at_utc="2026-03-07T15:01:00.000000Z",
    )
    store.advance(
        topic="fp.bus.traffic.fraud.v1",
        partition=2,
        offset="99",
        offset_kind="kafka_offset",
    )
    second = store.ensure_first_seen(
        topic="fp.bus.traffic.fraud.v1",
        partition=2,
        offset="100",
        offset_kind="kafka_offset",
        observed_at_utc="2026-03-07T15:01:07.000000Z",
    )

    assert first == "2026-03-07T15:01:00.000000Z"
    assert second == "2026-03-07T15:01:07.000000Z"


def test_run_once_blocks_later_rows_from_same_partition_after_defer() -> None:
    worker = DecisionFabricWorker.__new__(DecisionFabricWorker)
    rows = [
        {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kafka_offset", "offset": "101"},
        {"topic": "fp.bus.traffic.fraud.v1", "partition": 0, "offset_kind": "kafka_offset", "offset": "102"},
        {"topic": "fp.bus.traffic.fraud.v1", "partition": 1, "offset_kind": "kafka_offset", "offset": "201"},
    ]
    seen: list[str] = []

    worker.config = SimpleNamespace(event_bus_kind="file")
    worker._iter_records = lambda: rows
    worker._export = lambda: None

    def _process(row: dict[str, str]) -> str:
        seen.append(str(row["offset"]))
        if str(row["partition"]) == "0" or row["partition"] == 0:
            return "BLOCKED" if str(row["offset"]) == "101" else "ADVANCED"
        return "ADVANCED"

    worker._process_record = _process

    processed = worker.run_once()

    assert processed == 2
    assert seen == ["101", "201"]


def test_worker_context_refs_prefer_structured_csfb_context_refs() -> None:
    candidate = _candidate()
    worker = DecisionFabricWorker.__new__(DecisionFabricWorker)
    worker.csfb_query = SimpleNamespace(
        query=lambda _payload: {
            "status": "READY",
            "context_refs": {
                "arrival_events": {
                    "topic": "fp.bus.context.arrival_events.v1",
                    "partition": 1,
                    "offset": "25",
                    "offset_kind": "kafka_offset",
                },
                "flow_anchor": {
                    "topic": "fp.bus.context.flow_anchor.fraud.v1",
                    "partition": 2,
                    "offset": "77",
                    "offset_kind": "kafka_offset",
                },
            },
            "flow_binding": {
                "source_event": {
                    "event_type": "s3_flow_anchor_with_fraud_6B",
                    "eb_ref": {
                        "topic": "wrong-topic",
                        "partition": 9,
                        "offset": "999",
                        "offset_kind": "kafka_offset",
                    },
                }
            },
        }
    )

    refs = worker._context_refs(candidate, {"payload": {"flow_id": "flow-1"}})

    assert refs["arrival_events"]["topic"] == "fp.bus.context.arrival_events.v1"
    assert refs["flow_anchor"]["topic"] == "fp.bus.context.flow_anchor.fraud.v1"


def test_prime_consumer_boundaries_bootstraps_kafka_offsets() -> None:
    class _Checkpoints:
        def __init__(self) -> None:
            self.bootstrapped: list[tuple[str, int, str, str]] = []

        def next_offset(self, *, topic: str, partition: int) -> None:
            return None

        def bootstrap(self, *, topic: str, partition: int, next_offset: str, offset_kind: str) -> None:
            self.bootstrapped.append((topic, partition, next_offset, offset_kind))

    class _Reader:
        def resolve_start_offset(self, *, topic: str, partition: int, from_offset: int | None, start_position: str) -> int:
            assert from_offset is None
            assert start_position == "latest"
            return 1000 + int(partition)

    worker = DecisionFabricWorker.__new__(DecisionFabricWorker)
    worker.config = SimpleNamespace(event_bus_kind="kafka", event_bus_start_position="latest")
    worker.trigger_policy = SimpleNamespace(admitted_traffic_topics=("fp.bus.traffic.fraud.v1",))
    worker.consumer_checkpoints = _Checkpoints()
    worker._kafka_reader = _Reader()
    worker._kafka_partitions = lambda _topic: [0, 1, 2]

    worker._prime_consumer_boundaries()

    assert worker.consumer_checkpoints.bootstrapped == [
        ("fp.bus.traffic.fraud.v1", 0, "1000", "kafka_offset"),
        ("fp.bus.traffic.fraud.v1", 1, "1001", "kafka_offset"),
        ("fp.bus.traffic.fraud.v1", 2, "1002", "kafka_offset"),
    ]


def test_run_once_exports_zero_state_when_run_scope_seeded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    worker = DecisionFabricWorker.__new__(DecisionFabricWorker)
    worker.config = SimpleNamespace(event_bus_kind="file", platform_run_id="platform_20260307T223245Z")
    worker._kafka_reader = None
    worker.trigger_policy = SimpleNamespace(admitted_traffic_topics=tuple())
    worker.consumer_checkpoints = None
    worker._iter_records = lambda: []
    worker._scenario_run_id = "a" * 32
    worker._metrics = DfRunMetrics(platform_run_id="platform_20260307T223245Z", scenario_run_id="a" * 32)
    worker._reconciliation = DfReconciliationBuilder(
        platform_run_id="platform_20260307T223245Z",
        scenario_run_id="a" * 32,
    )

    processed = worker.run_once()

    metrics_path = (
        tmp_path
        / "runs"
        / "fraud-platform"
        / "platform_20260307T223245Z"
        / "decision_fabric"
        / "metrics"
        / "last_metrics.json"
    )
    health_path = (
        tmp_path
        / "runs"
        / "fraud-platform"
        / "platform_20260307T223245Z"
        / "decision_fabric"
        / "health"
        / "last_health.json"
    )

    assert processed == 0
    assert metrics_path.exists()
    assert health_path.exists()
