"""Control bus consumer for SR READY signals."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .admission import IngestionGate
from .errors import IngestionError
from .pull_state import PullRunStore
from .schemas import SchemaRegistry

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
                logger.warning("IG control bus invalid json path=%s", path)
                continue
            if envelope.get("topic") != self.topic:
                continue
            payload = envelope.get("payload") or {}
            if self.registry:
                try:
                    self.registry.validate("run_ready_signal.schema.yaml", payload)
                except ValueError as exc:
                    logger.warning("IG control bus payload invalid path=%s error=%s", path, str(exc))
                    continue
            run_id = payload.get("run_id")
            facts_view_ref = payload.get("facts_view_ref")
            bundle_hash = payload.get("bundle_hash")
            message_id = envelope.get("message_id")
            if not all([run_id, facts_view_ref, bundle_hash, message_id]):
                logger.warning("IG control bus missing fields path=%s", path)
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


class ReadyConsumer:
    def __init__(self, gate: IngestionGate, reader: FileControlBusReader, pull_store: PullRunStore | None = None) -> None:
        self.gate = gate
        self.reader = reader
        self.pull_store = pull_store or gate.pull_store

    def poll_once(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for message in self.reader.iter_ready_messages():
            results.append(self._process_message(message))
        return results

    def _process_message(self, message: ReadyMessage) -> dict[str, Any]:
        status_ref = self.pull_store.status_path(message.run_id)
        try:
            self.gate.enforce_ready_allowlist(message.run_id)
            self.gate.enforce_ready_rate_limit()
        except IngestionError as exc:
            return {
                "message_id": message.message_id,
                "run_id": message.run_id,
                "status": "SKIPPED_UNAUTHORIZED" if exc.code == "RUN_NOT_ALLOWED" else "SKIPPED_RATE_LIMIT",
                "reason_code": exc.code,
            }
        existing = self.pull_store.read_message_record(message.message_id)
        if existing:
            existing_status = self.pull_store.read_status(existing.get("run_id", message.run_id))
            if existing_status and existing_status.get("status") == "COMPLETED":
                logger.info("IG READY duplicate skipped message_id=%s run_id=%s", message.message_id, message.run_id)
                return {"message_id": message.message_id, "run_id": message.run_id, "status": "SKIPPED_DUPLICATE"}
        else:
            created = self.pull_store.ensure_message_record(message.message_id, message.run_id, status_ref)
            if not created:
                existing = self.pull_store.read_message_record(message.message_id)
        try:
            status = self.gate.admit_pull_with_state(
                message.facts_view_ref,
                run_id=message.run_id,
                message_id=message.message_id,
            )
        except IngestionError as exc:
            logger.warning("IG READY processing failed message_id=%s reason=%s", message.message_id, exc.code)
            return {"message_id": message.message_id, "run_id": message.run_id, "status": "FAILED", "reason_code": exc.code}
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("IG READY processing exception message_id=%s", message.message_id)
            return {"message_id": message.message_id, "run_id": message.run_id, "status": "FAILED", "reason_code": "INTERNAL_ERROR"}
        return {"message_id": message.message_id, "run_id": message.run_id, "status": status.get("status"), "status_ref": status.get("status_ref")}
