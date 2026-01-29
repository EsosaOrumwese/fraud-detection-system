"""Event Bus publisher interface + local file-bus adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class EbRef:
    topic: str
    partition: int
    offset: str
    offset_kind: str
    published_at_utc: str | None = None


class EventBusPublisher(Protocol):
    def publish(self, topic: str, partition_key: str, payload: dict[str, Any]) -> EbRef:
        ...


class FileEventBusPublisher:
    """Local append-only bus for tests; provides stable offsets per topic."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(self, topic: str, partition_key: str, payload: dict[str, Any]) -> EbRef:
        topic_dir = self.root / topic
        topic_dir.mkdir(parents=True, exist_ok=True)
        partition = 0
        log_path = topic_dir / "partition=0.jsonl"
        offset = 0
        if log_path.exists():
            offset = sum(1 for _ in log_path.open("r", encoding="utf-8"))
        record = {
            "partition_key": partition_key,
            "payload": payload,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        return EbRef(
            topic=topic,
            partition=partition,
            offset=str(offset),
            offset_kind="file_line",
        )
