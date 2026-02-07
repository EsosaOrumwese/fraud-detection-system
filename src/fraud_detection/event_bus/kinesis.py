"""Kinesis publish-only Event Bus adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

import boto3

from .publisher import EbRef

logger = logging.getLogger("fraud_detection.event_bus")


@dataclass(frozen=True)
class KinesisConfig:
    stream_name: str | None
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

    def describe_stream(self, stream_name: str) -> dict[str, Any]:
        if not stream_name:
            raise RuntimeError("KINESIS_STREAM_NAME_MISSING")
        return self._client.describe_stream_summary(StreamName=stream_name)

    def publish(self, topic: str, partition_key: str, payload: dict[str, Any]) -> EbRef:
        stream_name = self.config.stream_name or topic
        if not stream_name:
            raise RuntimeError("KINESIS_STREAM_NAME_MISSING")
        data = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        response = self._client.put_record(
            StreamName=stream_name,
            PartitionKey=partition_key,
            Data=data,
        )
        logger.info(
            "EB publish stream=%s topic=%s partition_key=%s seq=%s bytes=%s",
            stream_name,
            topic,
            partition_key,
            response.get("SequenceNumber", ""),
            len(data),
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
    stream_name: str | None,
    region: str | None = None,
    endpoint_url: str | None = None,
) -> KinesisEventBusPublisher:
    region = region or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
    endpoint = endpoint_url or os.getenv("AWS_ENDPOINT_URL") or os.getenv("KINESIS_ENDPOINT_URL")
    return KinesisEventBusPublisher(KinesisConfig(stream_name=stream_name, region=region, endpoint_url=endpoint))


class KinesisEventBusReader:
    def __init__(self, *, stream_name: str | None, region: str | None = None, endpoint_url: str | None = None) -> None:
        self.stream_name = stream_name
        self._client = boto3.client(
            "kinesis",
            region_name=region or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION"),
            endpoint_url=endpoint_url or os.getenv("AWS_ENDPOINT_URL") or os.getenv("KINESIS_ENDPOINT_URL"),
        )

    def list_shards(self, stream_name: str) -> list[str]:
        if not stream_name:
            raise RuntimeError("KINESIS_STREAM_NAME_MISSING")
        response = self._client.list_shards(StreamName=stream_name)
        return [shard.get("ShardId", "") for shard in response.get("Shards", []) if shard.get("ShardId")]

    def read(
        self,
        *,
        stream_name: str,
        shard_id: str,
        from_sequence: str | None,
        limit: int,
        start_position: str = "trim_horizon",
    ) -> list[dict[str, Any]]:
        if not stream_name:
            raise RuntimeError("KINESIS_STREAM_NAME_MISSING")
        iterator_args: dict[str, Any] = {
            "StreamName": stream_name,
            "ShardId": shard_id,
            "ShardIteratorType": "TRIM_HORIZON",
        }
        if from_sequence:
            iterator_args["ShardIteratorType"] = "AFTER_SEQUENCE_NUMBER"
            iterator_args["StartingSequenceNumber"] = from_sequence
        elif str(start_position).strip().lower() == "latest":
            iterator_args["ShardIteratorType"] = "LATEST"
        iterator_resp = self._client.get_shard_iterator(**iterator_args)
        shard_iterator = iterator_resp.get("ShardIterator")
        if not shard_iterator:
            return []
        records_resp = self._client.get_records(ShardIterator=shard_iterator, Limit=max(1, int(limit)))
        records: list[dict[str, Any]] = []
        for record in records_resp.get("Records", []):
            payload = json.loads(record.get("Data") or b"{}")
            published_at = record.get("ApproximateArrivalTimestamp")
            published_at_utc = None
            if published_at is not None:
                try:
                    if isinstance(published_at, datetime):
                        published_at_utc = published_at.astimezone(timezone.utc).isoformat()
                    else:
                        published_at_utc = str(published_at)
                except Exception:
                    published_at_utc = None
            records.append(
                {
                    "sequence_number": record.get("SequenceNumber"),
                    "partition_key": record.get("PartitionKey"),
                    "payload": payload,
                    "published_at_utc": published_at_utc,
                }
            )
        return records
