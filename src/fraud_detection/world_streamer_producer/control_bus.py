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

