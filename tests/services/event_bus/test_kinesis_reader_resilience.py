from __future__ import annotations

from botocore.exceptions import ClientError

from fraud_detection.event_bus.kinesis import KinesisEventBusReader


def _client_error(code: str, message: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        operation_name="KinesisOperation",
    )


class _FallbackIteratorClient:
    def __init__(self) -> None:
        self.iterator_calls: list[dict[str, object]] = []

    def list_shards(self, *, StreamName: str):  # type: ignore[no-untyped-def]
        return {"Shards": [{"ShardId": "shardId-000000000000"}]}

    def get_shard_iterator(self, **kwargs):  # type: ignore[no-untyped-def]
        self.iterator_calls.append(dict(kwargs))
        if len(self.iterator_calls) == 1:
            raise _client_error("ResourceNotFoundException", "stale sequence")
        return {"ShardIterator": "it-fallback"}

    def get_records(self, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "Records": [
                {
                    "SequenceNumber": "42",
                    "PartitionKey": "pk",
                    "Data": b'{"event_id":"evt-1"}',
                }
            ]
        }


class _ListShardFailureClient:
    def list_shards(self, *, StreamName: str):  # type: ignore[no-untyped-def]
        raise _client_error("InternalError", "temporary backend outage")


class _RecordsFailureClient:
    def list_shards(self, *, StreamName: str):  # type: ignore[no-untyped-def]
        return {"Shards": [{"ShardId": "shardId-000000000000"}]}

    def get_shard_iterator(self, **kwargs):  # type: ignore[no-untyped-def]
        return {"ShardIterator": "it-1"}

    def get_records(self, **kwargs):  # type: ignore[no-untyped-def]
        raise _client_error("ServiceUnavailableException", "backend unavailable")


def test_kinesis_reader_resets_stale_sequence_and_falls_back_to_start_position() -> None:
    reader = KinesisEventBusReader(stream_name="auto", region="us-east-1", endpoint_url="http://localhost:4566")
    fake = _FallbackIteratorClient()
    reader._client = fake  # type: ignore[attr-defined]

    records = reader.read(
        stream_name="fp.bus.context.arrival_events.v1",
        shard_id="shardId-000000000000",
        from_sequence="1001",
        limit=10,
        start_position="latest",
    )

    assert len(records) == 1
    assert records[0]["payload"] == {"event_id": "evt-1"}
    assert len(fake.iterator_calls) == 2
    assert fake.iterator_calls[0]["ShardIteratorType"] == "AFTER_SEQUENCE_NUMBER"
    assert fake.iterator_calls[1]["ShardIteratorType"] == "LATEST"

    second_poll = reader.read(
        stream_name="fp.bus.context.arrival_events.v1",
        shard_id="shardId-000000000000",
        from_sequence="1001",
        limit=10,
        start_position="latest",
    )
    assert len(second_poll) == 1
    assert len(fake.iterator_calls) == 3
    assert fake.iterator_calls[2]["ShardIteratorType"] == "LATEST"
    assert "StartingSequenceNumber" not in fake.iterator_calls[2]


def test_kinesis_reader_returns_empty_shard_list_on_transient_list_failure() -> None:
    reader = KinesisEventBusReader(stream_name="auto", region="us-east-1", endpoint_url="http://localhost:4566")
    reader._client = _ListShardFailureClient()  # type: ignore[attr-defined]

    assert reader.list_shards("fp.bus.context.arrival_events.v1") == []


def test_kinesis_reader_returns_empty_records_on_transient_get_records_failure() -> None:
    reader = KinesisEventBusReader(stream_name="auto", region="us-east-1", endpoint_url="http://localhost:4566")
    reader._client = _RecordsFailureClient()  # type: ignore[attr-defined]

    records = reader.read(
        stream_name="fp.bus.context.arrival_events.v1",
        shard_id="shardId-000000000000",
        from_sequence="123",
        limit=10,
        start_position="trim_horizon",
    )

    assert records == []
