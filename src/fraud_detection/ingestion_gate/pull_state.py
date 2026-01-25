"""Pull ingestion state tracking (run records + checkpoints)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .store import ObjectStore


@dataclass(frozen=True)
class PullRunStore:
    store: ObjectStore
    prefix: str = "fraud-platform/ig/pull_runs"

    def message_record_path(self, message_id: str) -> str:
        return f"{self.prefix}/message_id={message_id}.json"

    def status_path(self, run_id: str) -> str:
        return f"{self.prefix}/run_id={run_id}.json"

    def events_path(self, run_id: str) -> str:
        return f"{self.prefix}/run_id={run_id}.events.jsonl"

    def checkpoint_path(self, run_id: str, output_id: str) -> str:
        return f"{self.prefix}/checkpoints/run_id={run_id}/output_id={output_id}.json"

    def ensure_message_record(self, message_id: str, run_id: str, status_ref: str) -> bool:
        payload = {
            "message_id": message_id,
            "run_id": run_id,
            "status_ref": status_ref,
            "created_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        try:
            self.store.write_json_if_absent(self.message_record_path(message_id), payload)
            return True
        except FileExistsError:
            return False

    def read_message_record(self, message_id: str) -> dict[str, Any] | None:
        path = self.message_record_path(message_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def write_status(self, run_id: str, payload: dict[str, Any]) -> str:
        ref = self.store.write_json(self.status_path(run_id), payload)
        return ref.path

    def read_status(self, run_id: str) -> dict[str, Any] | None:
        path = self.status_path(run_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def append_event(self, run_id: str, payload: dict[str, Any]) -> str:
        ref = self.store.append_jsonl(self.events_path(run_id), [payload])
        return ref.path

    def checkpoint_exists(self, run_id: str, output_id: str) -> bool:
        return self.store.exists(self.checkpoint_path(run_id, output_id))

    def write_checkpoint(self, run_id: str, output_id: str, payload: dict[str, Any]) -> bool:
        try:
            self.store.write_json_if_absent(self.checkpoint_path(run_id, output_id), payload)
            return True
        except FileExistsError:
            return False
