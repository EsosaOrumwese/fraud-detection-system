"""Control bus publisher abstractions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PublishedMessage:
    topic: str
    message_id: str
    path: str | None = None
    sequence_number: str | None = None
    shard_id: str | None = None


class FileControlBus:
    def __init__(self, root: Path) -> None:
        self.root = root

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        message_id: str,
        attributes: dict[str, str] | None = None,
        partition_key: str | None = None,
    ) -> PublishedMessage:
        topic_dir = self.root / topic
        topic_dir.mkdir(parents=True, exist_ok=True)
        path = topic_dir / f"{message_id}.json"
        if not path.exists():
            envelope = {
                "topic": topic,
                "message_id": message_id,
                "published_at_utc": datetime.now(tz=timezone.utc).isoformat(),
                "attributes": attributes or {},
                "partition_key": partition_key,
                "payload": payload,
            }
            path.write_text(json.dumps(envelope, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        return PublishedMessage(topic=topic, path=str(path), message_id=message_id)


class KinesisControlBus:
    def __init__(self, stream_name: str, region: str | None = None, endpoint_url: str | None = None) -> None:
        self.stream_name = stream_name
        self.region = region
        self.endpoint_url = endpoint_url

    def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        message_id: str,
        attributes: dict[str, str] | None = None,
        partition_key: str | None = None,
    ) -> PublishedMessage:
        import boto3

        envelope = {
            "topic": topic,
            "message_id": message_id,
            "published_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "attributes": attributes or {},
            "partition_key": partition_key,
            "payload": payload,
        }
        data = json.dumps(envelope, sort_keys=True, ensure_ascii=True).encode("utf-8")
        client = boto3.client("kinesis", region_name=self.region, endpoint_url=self.endpoint_url)
        response = client.put_record(
            StreamName=self.stream_name,
            Data=data,
            PartitionKey=partition_key or message_id,
        )
        return PublishedMessage(
            topic=topic,
            message_id=message_id,
            sequence_number=response.get("SequenceNumber"),
            shard_id=response.get("ShardId"),
        )
