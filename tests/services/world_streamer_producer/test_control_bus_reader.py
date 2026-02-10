from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from fraud_detection.world_streamer_producer.control_bus import KinesisControlBusReader


def _ready_record(message_id: str, sequence: str) -> dict[str, object]:
    envelope = {
        "topic": "fp.bus.control.v1",
        "message_id": message_id,
        "payload": {
            "run_id": "run-1",
            "facts_view_ref": "s3://fraud-platform/platform_x/sr/run_facts_view/run-1.json",
            "bundle_hash": "bundle-1",
        },
    }
    return {"Data": json.dumps(envelope).encode("utf-8"), "SequenceNumber": sequence}


class _FakeKinesisClient:
    def __init__(self, pages_by_iterator: dict[str, list[dict[str, object]]]) -> None:
        self.pages_by_iterator = pages_by_iterator
        self.get_shard_iterator_calls: list[dict[str, object]] = []
        self.get_records_calls: list[tuple[str, int]] = []

    def describe_stream(self, *, StreamName: str) -> dict[str, object]:
        return {"StreamDescription": {"Shards": [{"ShardId": "shard-000000000000"}]}}

    def get_shard_iterator(self, **kwargs: object) -> dict[str, object]:
        self.get_shard_iterator_calls.append(kwargs)
        return {"ShardIterator": "iter-0"}

    def get_records(self, *, ShardIterator: str, Limit: int) -> dict[str, object]:
        self.get_records_calls.append((ShardIterator, Limit))
        queue = self.pages_by_iterator.setdefault(ShardIterator, [])
        if queue:
            return queue.pop(0)
        return {"Records": [], "NextShardIterator": ShardIterator}


def test_kinesis_reader_advances_pages_and_caches_next_iterator(monkeypatch) -> None:
    fake_client = _FakeKinesisClient(
        {
            "iter-0": [{"Records": [_ready_record("m1", "1"), _ready_record("m2", "2")], "NextShardIterator": "iter-1"}],
            "iter-1": [{"Records": [_ready_record("m3", "3")], "NextShardIterator": "iter-2"}],
            "iter-2": [{"Records": [], "NextShardIterator": "iter-2"}],
        }
    )
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: fake_client))

    reader = KinesisControlBusReader("fp.bus.control", "fp.bus.control.v1", max_records=100)
    messages = list(reader.iter_ready_messages())
    assert [item.message_id for item in messages] == ["m1", "m2", "m3"]
    assert len(fake_client.get_shard_iterator_calls) == 1

    second_poll = list(reader.iter_ready_messages())
    assert second_poll == []
    assert len(fake_client.get_shard_iterator_calls) == 1
    assert fake_client.get_records_calls[-1][0] == "iter-2"


def test_kinesis_reader_yields_new_records_after_idle_page(monkeypatch) -> None:
    fake_client = _FakeKinesisClient(
        {
            "iter-0": [{"Records": [_ready_record("m1", "1")], "NextShardIterator": "iter-1"}],
            "iter-1": [
                {"Records": [], "NextShardIterator": "iter-1"},
                {"Records": [_ready_record("m2", "2")], "NextShardIterator": "iter-2"},
            ],
            "iter-2": [{"Records": [], "NextShardIterator": "iter-2"}],
        }
    )
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *args, **kwargs: fake_client))

    reader = KinesisControlBusReader("fp.bus.control", "fp.bus.control.v1", max_records=100)
    first_poll = list(reader.iter_ready_messages())
    assert [item.message_id for item in first_poll] == ["m1"]

    second_poll = list(reader.iter_ready_messages())
    assert [item.message_id for item in second_poll] == ["m2"]
    assert len(fake_client.get_shard_iterator_calls) == 1
