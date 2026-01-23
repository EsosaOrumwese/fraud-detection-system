"""Control bus publisher abstractions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PublishedMessage:
    topic: str
    path: str
    message_id: str


class FileControlBus:
    def __init__(self, root: Path) -> None:
        self.root = root

    def publish(self, topic: str, payload: dict[str, Any], message_id: str) -> PublishedMessage:
        topic_dir = self.root / topic
        topic_dir.mkdir(parents=True, exist_ok=True)
        path = topic_dir / f"{message_id}.json"
        if not path.exists():
            path.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
        return PublishedMessage(topic=topic, path=str(path), message_id=message_id)
