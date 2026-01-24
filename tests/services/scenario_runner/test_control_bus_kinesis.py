from __future__ import annotations

import json
import os
import time

import pytest

from fraud_detection.scenario_runner.bus import KinesisControlBus


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _require_env() -> dict[str, str]:
    endpoint = _env("SR_KINESIS_ENDPOINT_URL")
    stream = _env("SR_KINESIS_STREAM")
    region = _env("SR_KINESIS_REGION") or _env("AWS_DEFAULT_REGION")
    access_key = _env("AWS_ACCESS_KEY_ID")
    secret_key = _env("AWS_SECRET_ACCESS_KEY")
    if not all([endpoint, stream, region, access_key, secret_key]):
        pytest.skip("LocalStack Kinesis env not configured")
    return {
        "endpoint": endpoint,
        "stream": stream,
        "region": region,
    }


def _ensure_stream(client, stream_name: str) -> None:
    try:
        client.describe_stream_summary(StreamName=stream_name)
        return
    except client.exceptions.ResourceNotFoundException:
        client.create_stream(StreamName=stream_name, ShardCount=1)

    for _ in range(20):
        summary = client.describe_stream_summary(StreamName=stream_name)
        if summary["StreamDescriptionSummary"]["StreamStatus"] == "ACTIVE":
            return
        time.sleep(0.5)
    raise RuntimeError("Kinesis stream did not become ACTIVE")


def test_kinesis_control_bus_publish_roundtrip() -> None:
    env = _require_env()
    import boto3

    client = boto3.client("kinesis", region_name=env["region"], endpoint_url=env["endpoint"])
    _ensure_stream(client, env["stream"])

    bus = KinesisControlBus(stream_name=env["stream"], region=env["region"], endpoint_url=env["endpoint"])
    payload = {"run_id": "0" * 32, "facts_view_ref": "sr/run_facts_view/x", "bundle_hash": "a" * 64}
    message_id = "m" * 32
    published = bus.publish(
        topic="fp.bus.control.v1",
        payload=payload,
        message_id=message_id,
        attributes={"kind": "READY"},
        partition_key="0" * 32,
    )
    assert published.sequence_number is not None
    assert published.shard_id is not None

    iterator = client.get_shard_iterator(
        StreamName=env["stream"],
        ShardId=published.shard_id,
        ShardIteratorType="AT_SEQUENCE_NUMBER",
        StartingSequenceNumber=published.sequence_number,
    )["ShardIterator"]
    records = client.get_records(ShardIterator=iterator, Limit=10)["Records"]
    assert records
    raw = records[0]["Data"].decode("utf-8")
    envelope = json.loads(raw)
    assert envelope["message_id"] == message_id
    assert envelope["payload"]["run_id"] == payload["run_id"]
