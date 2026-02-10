"""READY control bus reader for WSP."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from fraud_detection.scenario_runner.schemas import SchemaRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReadyMessage:
    message_id: str
    run_id: str
    facts_view_ref: str
    bundle_hash: str
    payload: dict[str, Any]
    envelope: dict[str, Any]
    source_path: Path


class FileControlBusReader:
    def __init__(self, root: Path, topic: str, registry: SchemaRegistry | None = None) -> None:
        self.root = root
        self.topic = topic
        self.registry = registry

    def iter_ready_messages(self) -> Iterable[ReadyMessage]:
        topic_dir = self.root / self.topic
        if not topic_dir.exists():
            return []
        messages: list[ReadyMessage] = []
        for path in sorted(topic_dir.glob("*.json")):
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("WSP control bus invalid json path=%s", path)
                continue
            if envelope.get("topic") != self.topic:
                continue
            payload = envelope.get("payload") or {}
            if self.registry:
                try:
                    self.registry.validate("run_ready_signal.schema.yaml", payload)
                except ValueError as exc:
                    logger.warning("WSP control bus payload invalid path=%s error=%s", path, str(exc))
                    continue
            run_id = payload.get("run_id")
            facts_view_ref = payload.get("facts_view_ref")
            bundle_hash = payload.get("bundle_hash")
            message_id = envelope.get("message_id")
            if not all([run_id, facts_view_ref, bundle_hash, message_id]):
                logger.warning("WSP control bus missing fields path=%s", path)
                continue
            messages.append(
                ReadyMessage(
                    message_id=message_id,
                    run_id=run_id,
                    facts_view_ref=facts_view_ref,
                    bundle_hash=bundle_hash,
                    payload=payload,
                    envelope=envelope,
                    source_path=path,
                )
            )
        return messages


class KinesisControlBusReader:
    def __init__(
        self,
        stream_name: str,
        topic: str,
        *,
        region: str | None = None,
        endpoint_url: str | None = None,
        registry: SchemaRegistry | None = None,
        max_records: int = 1000,
    ) -> None:
        import boto3

        self.stream_name = stream_name
        self.topic = topic
        self.registry = registry
        self.max_records = max_records
        self._client = boto3.client("kinesis", region_name=region, endpoint_url=endpoint_url)
        self._next_iterator_by_shard: dict[str, str] = {}

    def iter_ready_messages(self) -> Iterable[ReadyMessage]:
        messages: list[ReadyMessage] = []
        stream = self._client.describe_stream(StreamName=self.stream_name)
        shards = stream.get("StreamDescription", {}).get("Shards", [])
        for shard in shards:
            shard_id = shard.get("ShardId")
            if not shard_id:
                continue
            iterator = self._next_iterator_by_shard.get(shard_id)
            if not iterator:
                iterator = self._client.get_shard_iterator(
                    StreamName=self.stream_name,
                    ShardId=shard_id,
                    ShardIteratorType="TRIM_HORIZON",
                ).get("ShardIterator")
            if not iterator:
                continue
            while iterator:
                response = self._client.get_records(ShardIterator=iterator, Limit=self.max_records)
                records = response.get("Records", [])
                next_iterator = response.get("NextShardIterator")
                if next_iterator:
                    self._next_iterator_by_shard[shard_id] = next_iterator
                for record in records:
                    try:
                        envelope = json.loads(record.get("Data", b"").decode("utf-8"))
                    except Exception:
                        logger.warning("WSP control bus invalid json shard=%s", shard_id)
                        continue
                    if envelope.get("topic") != self.topic:
                        continue
                    payload = envelope.get("payload") or {}
                    if self.registry:
                        try:
                            self.registry.validate("run_ready_signal.schema.yaml", payload)
                        except ValueError as exc:
                            logger.warning("WSP control bus payload invalid shard=%s error=%s", shard_id, str(exc))
                            continue
                    run_id = payload.get("run_id")
                    facts_view_ref = payload.get("facts_view_ref")
                    bundle_hash = payload.get("bundle_hash")
                    message_id = envelope.get("message_id")
                    if not all([run_id, facts_view_ref, bundle_hash, message_id]):
                        logger.warning("WSP control bus missing fields shard=%s", shard_id)
                        continue
                    sequence = record.get("SequenceNumber") or ""
                    messages.append(
                        ReadyMessage(
                            message_id=message_id,
                            run_id=run_id,
                            facts_view_ref=facts_view_ref,
                            bundle_hash=bundle_hash,
                            payload=payload,
                            envelope=envelope,
                            source_path=Path(f"kinesis://{self.stream_name}/{sequence}"),
                        )
                    )
                if not records:
                    break
                iterator = next_iterator
        return messages
