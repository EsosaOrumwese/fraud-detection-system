"""Replay manifest loader for IEG."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ReplayPartitionRange:
    partition: int
    from_offset: str | None
    to_offset: str | None
    offset_kind: str | None = None


@dataclass(frozen=True)
class ReplayTopicRange:
    topic: str
    partitions: list[ReplayPartitionRange]


@dataclass(frozen=True)
class ReplayManifest:
    payload: dict[str, Any]
    stream_id: str | None
    topics: list[ReplayTopicRange]
    pins: dict[str, Any] | None

    @classmethod
    def load(cls, path: Path) -> "ReplayManifest":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Replay manifest must be a mapping")
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ReplayManifest":
        topics_payload = payload.get("topics")
        if not isinstance(topics_payload, list) or not topics_payload:
            raise ValueError("Replay manifest requires non-empty topics list")
        topics: list[ReplayTopicRange] = []
        for topic_item in topics_payload:
            if not isinstance(topic_item, dict):
                raise ValueError("Replay manifest topic entry must be a mapping")
            topic_name = topic_item.get("topic")
            if not topic_name:
                raise ValueError("Replay manifest topic missing 'topic'")
            partitions_payload = topic_item.get("partitions")
            if not isinstance(partitions_payload, list) or not partitions_payload:
                raise ValueError(f"Replay manifest topic '{topic_name}' missing partitions")
            partitions: list[ReplayPartitionRange] = []
            for partition_item in partitions_payload:
                if not isinstance(partition_item, dict):
                    raise ValueError("Replay manifest partition entry must be a mapping")
                partition_value = partition_item.get("partition")
                if partition_value is None:
                    raise ValueError(f"Replay manifest partition missing 'partition' for topic {topic_name}")
                try:
                    partition_id = int(partition_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("Replay manifest partition must be int") from exc
                from_offset = _offset_str(partition_item.get("from_offset"))
                to_offset = _offset_str(partition_item.get("to_offset"))
                offset_kind = partition_item.get("offset_kind")
                partitions.append(
                    ReplayPartitionRange(
                        partition=partition_id,
                        from_offset=from_offset,
                        to_offset=to_offset,
                        offset_kind=str(offset_kind) if offset_kind else None,
                    )
                )
            topics.append(ReplayTopicRange(topic=str(topic_name), partitions=partitions))
        stream_id = payload.get("stream_id")
        stream_id = str(stream_id) if stream_id else None
        pins = payload.get("pins")
        if pins is not None and not isinstance(pins, dict):
            raise ValueError("Replay manifest pins must be a mapping")
        return cls(payload=payload, stream_id=stream_id, topics=topics, pins=pins)

    def canonical_json(self) -> str:
        return json.dumps(self.payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def replay_id(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:32]

    def basis(self, *, event_bus_kind: str | None = None, stream_override: str | None = None) -> dict[str, Any]:
        topics: dict[str, Any] = {}
        for topic in self.topics:
            partitions: dict[str, Any] = {}
            for partition in topic.partitions:
                entry: dict[str, Any] = {}
                if partition.from_offset is not None:
                    entry["from_offset"] = partition.from_offset
                if partition.to_offset is not None:
                    entry["to_offset"] = partition.to_offset
                if partition.offset_kind:
                    entry["offset_kind"] = partition.offset_kind
                partitions[str(partition.partition)] = entry
            topics[topic.topic] = {"partitions": partitions}
        basis: dict[str, Any] = {
            "stream_id": stream_override or self.stream_id,
            "topics": topics,
        }
        if event_bus_kind:
            basis["event_bus_kind"] = event_bus_kind
        return basis


def _offset_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    return str(value)
