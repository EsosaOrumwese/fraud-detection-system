"""Kinesis publish-only Event Bus adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Any

import boto3

from .publisher import EbRef


@dataclass(frozen=True)
class KinesisConfig:
    stream_name: str
    region: str | None
    endpoint_url: str | None


class KinesisEventBusPublisher:
    def __init__(self, config: KinesisConfig) -> None:
        self.config = config
        self._client = boto3.client(
            "kinesis",
            region_name=config.region,
            endpoint_url=config.endpoint_url,
        )

    def publish(self, topic: str, partition_key: str, payload: dict[str, Any]) -> EbRef:
        data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        response = self._client.put_record(
            StreamName=self.config.stream_name,
            PartitionKey=partition_key,
            Data=data,
        )
        published_at = datetime.now(tz=timezone.utc).isoformat()
        return EbRef(
            topic=topic,
            partition=int(response.get("ShardId", "shardId-000000000000").split("-")[-1]),
            offset=response.get("SequenceNumber", ""),
            offset_kind="kinesis_sequence",
            published_at_utc=published_at,
        )


def build_kinesis_publisher(
    *,
    stream_name: str,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> KinesisEventBusPublisher:
    region = region or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
    endpoint = endpoint_url or os.getenv("AWS_ENDPOINT_URL") or os.getenv("KINESIS_ENDPOINT_URL")
    return KinesisEventBusPublisher(KinesisConfig(stream_name=stream_name, region=region, endpoint_url=endpoint))
