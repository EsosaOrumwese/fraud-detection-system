"""Replay basis manifest for CSFB backfill/rebuild flows (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CsfbReplayPartitionRange:
    partition: int
    from_offset: str | None
    to_offset: str | None
    offset_kind: str | None = None


@dataclass(frozen=True)
class CsfbReplayTopicRange:
    topic: str
    partitions: list[CsfbReplayPartitionRange]


@dataclass(frozen=True)
class CsfbReplayManifest:
    payload: dict[str, Any]
    topics: list[CsfbReplayTopicRange]
    pins: dict[str, Any] | None

    @classmethod
    def load(cls, path: Path) -> "CsfbReplayManifest":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CSFB replay manifest must be a mapping")
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CsfbReplayManifest":
        topics_payload = payload.get("topics")
        if not isinstance(topics_payload, list) or not topics_payload:
            raise ValueError("CSFB replay manifest requires non-empty topics")

        topics: list[CsfbReplayTopicRange] = []
        for item in topics_payload:
            if not isinstance(item, dict):
                raise ValueError("CSFB replay topic entry must be a mapping")
            topic_name = str(item.get("topic") or "").strip()
            if not topic_name:
                raise ValueError("CSFB replay topic requires 'topic'")

            partitions_payload = item.get("partitions")
            if not isinstance(partitions_payload, list) or not partitions_payload:
                raise ValueError(f"CSFB replay topic '{topic_name}' requires partitions")

            partitions: list[CsfbReplayPartitionRange] = []
            for part in partitions_payload:
                if not isinstance(part, dict):
                    raise ValueError("CSFB replay partition entry must be a mapping")
                if "partition" not in part:
                    raise ValueError(f"CSFB replay partition missing 'partition' for topic '{topic_name}'")
                try:
                    partition_id = int(part.get("partition"))
                except (TypeError, ValueError) as exc:
                    raise ValueError("CSFB replay partition must be int") from exc
                from_offset = _offset_str(part.get("from_offset"))
                to_offset = _offset_str(part.get("to_offset"))
                if from_offset is None and to_offset is None:
                    raise ValueError(
                        f"CSFB replay partition for topic '{topic_name}' requires explicit from_offset or to_offset"
                    )
                offset_kind = _offset_str(part.get("offset_kind"))
                partitions.append(
                    CsfbReplayPartitionRange(
                        partition=partition_id,
                        from_offset=from_offset,
                        to_offset=to_offset,
                        offset_kind=offset_kind,
                    )
                )
            topics.append(CsfbReplayTopicRange(topic=topic_name, partitions=partitions))

        pins = payload.get("pins")
        if pins is not None and not isinstance(pins, dict):
            raise ValueError("CSFB replay pins must be a mapping")
        return cls(payload=payload, topics=topics, pins=pins)

    def canonical_json(self) -> str:
        return json.dumps(self.payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))

    def replay_id(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:32]


def _offset_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None
