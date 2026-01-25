"""Pull ingestion state tracking (run records + checkpoints)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from .store import ObjectStore
from .store import LocalObjectStore, S3ObjectStore


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

    def checkpoint_path(self, run_id: str, output_id: str, shard_id: int | None = None) -> str:
        if shard_id is None:
            return f"{self.prefix}/checkpoints/run_id={run_id}/output_id={output_id}.json"
        return f"{self.prefix}/checkpoints/run_id={run_id}/output_id={output_id}/shard={shard_id}.json"

    def chain_state_path(self, run_id: str) -> str:
        return f"{self.prefix}/chain_state/run_id={run_id}.json"

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
        event = dict(payload)
        chain_state = self._read_chain_state(run_id)
        prev_hash = chain_state.get("last_hash") if chain_state else None
        if not prev_hash:
            prev_hash = "0" * 64
        event["prev_hash"] = prev_hash
        event_hash = _hash_event(prev_hash, event)
        event["event_hash"] = event_hash
        ref = self.store.append_jsonl(self.events_path(run_id), [event])
        self._write_chain_state(run_id, event_hash, (chain_state or {}).get("event_count", 0) + 1)
        return ref.path

    def checkpoint_exists(self, run_id: str, output_id: str, shard_id: int | None = None) -> bool:
        return self.store.exists(self.checkpoint_path(run_id, output_id, shard_id=shard_id))

    def write_checkpoint(self, run_id: str, output_id: str, payload: dict[str, Any], shard_id: int | None = None) -> bool:
        try:
            self.store.write_json_if_absent(self.checkpoint_path(run_id, output_id, shard_id=shard_id), payload)
            return True
        except FileExistsError:
            return False

    def iter_events(self, run_id: str) -> list[dict[str, Any]]:
        path = self.events_path(run_id)
        return _read_jsonl(self.store, path)

    def list_checkpoints(self, run_id: str) -> list[dict[str, Any]]:
        return _list_checkpoint_payloads(self.store, f"{self.prefix}/checkpoints/run_id={run_id}")

    def _read_chain_state(self, run_id: str) -> dict[str, Any] | None:
        path = self.chain_state_path(run_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def _write_chain_state(self, run_id: str, event_hash: str, event_count: int) -> None:
        payload = {
            "run_id": run_id,
            "last_hash": event_hash,
            "event_count": event_count,
            "updated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        self.store.write_json(self.chain_state_path(run_id), payload)


def _hash_event(prev_hash: str, payload: dict[str, Any]) -> str:
    event = dict(payload)
    event.pop("event_hash", None)
    encoded = json.dumps(event, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}:{encoded}".encode("utf-8")).hexdigest()


def _read_jsonl(store: ObjectStore, relative_path: str) -> list[dict[str, Any]]:
    if isinstance(store, LocalObjectStore):
        path = store.root / relative_path
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events
    if isinstance(store, S3ObjectStore):
        key = store._key(relative_path)
        try:
            response = store._client.get_object(Bucket=store.bucket, Key=key)
        except Exception:
            return []
        text = response["Body"].read().decode("utf-8")
        events = []
        for line in text.splitlines():
            if line.strip():
                events.append(json.loads(line))
        return events
    return []


def _list_checkpoint_payloads(store: ObjectStore, prefix: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if isinstance(store, LocalObjectStore):
        root = store.root / prefix
        if root.exists():
            for path in root.rglob("*.json"):
                payloads.append(json.loads(path.read_text(encoding="utf-8")))
        return payloads
    if isinstance(store, S3ObjectStore):
        prefix_key = store._key(prefix + "/")
        paginator = store._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=store.bucket, Prefix=prefix_key):
            for item in page.get("Contents", []):
                key = item["Key"]
                obj = store._client.get_object(Bucket=store.bucket, Key=key)
                payloads.append(json.loads(obj["Body"].read().decode("utf-8")))
        return payloads
    return payloads
