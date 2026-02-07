from __future__ import annotations

from fraud_detection.event_bus.kinesis import KinesisEventBusReader


class _FakeKinesisClient:
    def __init__(self) -> None:
        self.iterator_calls: list[dict[str, object]] = []

    def get_shard_iterator(self, **kwargs):  # type: ignore[no-untyped-def]
        self.iterator_calls.append(dict(kwargs))
        return {"ShardIterator": "it"}

    def get_records(self, **kwargs):  # type: ignore[no-untyped-def]
        return {"Records": []}


def test_kinesis_reader_uses_latest_start_position_when_requested() -> None:
    reader = KinesisEventBusReader(stream_name="auto", region="us-east-1", endpoint_url="http://localhost:4566")
    fake = _FakeKinesisClient()
    reader._client = fake  # type: ignore[attr-defined]

    records = reader.read(
        stream_name="fp.bus.traffic.fraud.v1",
        shard_id="shardId-000000000000",
        from_sequence=None,
        limit=10,
        start_position="latest",
    )

    assert records == []
    assert fake.iterator_calls
    assert fake.iterator_calls[-1]["ShardIteratorType"] == "LATEST"


def test_kinesis_reader_prefers_after_sequence_over_start_position() -> None:
    reader = KinesisEventBusReader(stream_name="auto", region="us-east-1", endpoint_url="http://localhost:4566")
    fake = _FakeKinesisClient()
    reader._client = fake  # type: ignore[attr-defined]

    records = reader.read(
        stream_name="fp.bus.traffic.fraud.v1",
        shard_id="shardId-000000000000",
        from_sequence="123",
        limit=10,
        start_position="latest",
    )

    assert records == []
    assert fake.iterator_calls
    assert fake.iterator_calls[-1]["ShardIteratorType"] == "AFTER_SEQUENCE_NUMBER"
    assert fake.iterator_calls[-1]["StartingSequenceNumber"] == "123"
