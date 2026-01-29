"""Event Bus publisher interface + local file-bus adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
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
        head_path = topic_dir / "head.json"
        offset = _load_next_offset(head_path, log_path)
        record = {
            "partition_key": partition_key,
            "payload": payload,
            "published_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _write_head(head_path, offset + 1)
        return EbRef(
            topic=topic,
            partition=partition,
            offset=str(offset),
            offset_kind="file_line",
            published_at_utc=record["published_at_utc"],
        )


def _load_next_offset(head_path: Path, log_path: Path) -> int:
    if log_path.exists():
        return sum(1 for _ in log_path.open("r", encoding="utf-8"))
    if head_path.exists():
        return 0
    head = _read_head(head_path)
    if head is not None:
        return head
    return 0


def _read_head(head_path: Path) -> int | None:
    if not head_path.exists():
        return None
    try:
        payload = json.loads(head_path.read_text(encoding="utf-8"))
        value = payload.get("next_offset")
        if isinstance(value, int) and value >= 0:
            return value
    except Exception:
        return None
    return None


def _write_head(head_path: Path, next_offset: int) -> None:
    tmp_path = head_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps({"next_offset": next_offset}, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )
    tmp_path.replace(head_path)
