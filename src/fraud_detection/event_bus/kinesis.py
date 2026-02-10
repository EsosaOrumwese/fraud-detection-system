"""Kinesis publish-only Event Bus adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .publisher import EbRef

logger = logging.getLogger("fraud_detection.event_bus")

_STALE_SEQUENCE_ERROR_CODES = {
    "InvalidArgumentException",
    "ResourceNotFoundException",
}


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
        self._stale_sequence_by_shard: dict[tuple[str, str], str] = {}
        self._client = boto3.client(
            "kinesis",
            region_name=region or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION"),
            endpoint_url=endpoint_url or os.getenv("AWS_ENDPOINT_URL") or os.getenv("KINESIS_ENDPOINT_URL"),
        )

    def list_shards(self, stream_name: str) -> list[str]:
        if not stream_name:
            raise RuntimeError("KINESIS_STREAM_NAME_MISSING")
        try:
            response = self._client.list_shards(StreamName=stream_name)
        except Exception as exc:
            logger.warning(
                "Kinesis list_shards failed stream=%s code=%s detail=%s",
                stream_name,
                _error_code(exc),
                _error_detail(exc),
            )
            return []
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
        key = (stream_name, shard_id)
        cached_stale = self._stale_sequence_by_shard.get(key)
        sequence_for_iterator = from_sequence
        if sequence_for_iterator and cached_stale == sequence_for_iterator:
            sequence_for_iterator = None
        elif sequence_for_iterator and cached_stale and cached_stale != sequence_for_iterator:
            self._stale_sequence_by_shard.pop(key, None)
        iterator_args = _iterator_args(
            stream_name=stream_name,
            shard_id=shard_id,
            from_sequence=sequence_for_iterator,
            start_position=start_position,
        )
        try:
            iterator_resp = self._client.get_shard_iterator(**iterator_args)
        except Exception as exc:
            if sequence_for_iterator and _error_code(exc) in _STALE_SEQUENCE_ERROR_CODES:
                self._stale_sequence_by_shard[key] = sequence_for_iterator
                fallback_args = _iterator_args(
                    stream_name=stream_name,
                    shard_id=shard_id,
                    from_sequence=None,
                    start_position=start_position,
                )
                logger.warning(
                    "Kinesis stale checkpoint reset stream=%s shard=%s seq=%s code=%s",
                    stream_name,
                    shard_id,
                    sequence_for_iterator,
                    _error_code(exc),
                )
                try:
                    iterator_resp = self._client.get_shard_iterator(**fallback_args)
                except Exception as fallback_exc:
                    logger.warning(
                        "Kinesis fallback iterator failed stream=%s shard=%s code=%s detail=%s",
                        stream_name,
                        shard_id,
                        _error_code(fallback_exc),
                        _error_detail(fallback_exc),
                    )
                    return []
            else:
                logger.warning(
                    "Kinesis get_shard_iterator failed stream=%s shard=%s code=%s detail=%s",
                    stream_name,
                    shard_id,
                    _error_code(exc),
                    _error_detail(exc),
                )
                return []
        shard_iterator = iterator_resp.get("ShardIterator")
        if not shard_iterator:
            return []
        try:
            records_resp = self._client.get_records(ShardIterator=shard_iterator, Limit=max(1, int(limit)))
        except Exception as exc:
            logger.warning(
                "Kinesis get_records failed stream=%s shard=%s code=%s detail=%s",
                stream_name,
                shard_id,
                _error_code(exc),
                _error_detail(exc),
            )
            return []
        records: list[dict[str, Any]] = []
        for record in records_resp.get("Records", []):
            try:
                payload = _decode_data(record.get("Data"))
            except Exception:
                logger.warning(
                    "Kinesis record decode failed stream=%s shard=%s sequence=%s",
                    stream_name,
                    shard_id,
                    record.get("SequenceNumber"),
                )
                continue
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


def _iterator_args(
    *,
    stream_name: str,
    shard_id: str,
    from_sequence: str | None,
    start_position: str,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "StreamName": stream_name,
        "ShardId": shard_id,
        "ShardIteratorType": "TRIM_HORIZON",
    }
    if from_sequence:
        args["ShardIteratorType"] = "AFTER_SEQUENCE_NUMBER"
        args["StartingSequenceNumber"] = from_sequence
    elif str(start_position).strip().lower() == "latest":
        args["ShardIteratorType"] = "LATEST"
    return args


def _decode_data(data: Any) -> dict[str, Any]:
    if data in (None, b"", ""):
        return {}
    if isinstance(data, bytes):
        return json.loads(data.decode("utf-8"))
    if isinstance(data, str):
        return json.loads(data)
    return json.loads(data)


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Code") or "")
    return exc.__class__.__name__


def _error_detail(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        return str(exc.response.get("Error", {}).get("Message") or "")[:256]
    return str(exc)[:256]
