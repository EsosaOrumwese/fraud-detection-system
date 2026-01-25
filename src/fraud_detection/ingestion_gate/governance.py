"""Governance facts emission for IG."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .event_bus import EventBusPublisher
from .partitioning import PartitioningProfiles
from .store import ObjectStore


@dataclass
class GovernanceEmitter:
    store: ObjectStore
    bus: EventBusPublisher
    partitioning: PartitioningProfiles
    quarantine_spike_threshold: int
    quarantine_spike_window_seconds: int
    policy_id: str

    def emit_policy_activation(self, policy_rev: dict[str, Any]) -> None:
        digest = policy_rev.get("content_digest")
        if not digest:
            return
        active_path = "fraud-platform/ig/policy/active.json"
        previous = None
        if self.store.exists(active_path):
            previous = self.store.read_json(active_path)
        if previous and previous.get("content_digest") == digest:
            return
        payload = {
            "policy_id": policy_rev.get("policy_id"),
            "revision": policy_rev.get("revision"),
            "content_digest": digest,
            "activated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        self.store.write_json(active_path, payload)
        envelope = _make_envelope("ig.policy.activation", payload)
        self._emit_audit(envelope)

    def emit_quarantine_spike(self, count: int) -> None:
        if count < self.quarantine_spike_threshold:
            return
        payload = {
            "policy_id": self.policy_id,
            "quarantine_count": count,
            "window_seconds": self.quarantine_spike_window_seconds,
            "detected_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        envelope = _make_envelope("ig.quarantine.spike", payload)
        self._emit_audit(envelope)

    def _emit_audit(self, envelope: dict[str, Any]) -> None:
        profile_id = "ig.partitioning.v0.audit"
        partition_key = self.partitioning.derive_key(profile_id, envelope)
        stream = self.partitioning.get(profile_id).stream
        self.bus.publish(stream, partition_key, envelope)


def _make_envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    ts = datetime.now(tz=timezone.utc).isoformat()
    base = f"{event_type}:{ts}"
    event_id = hashlib.sha256(base.encode("utf-8")).hexdigest()
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ts_utc": ts,
        "manifest_fingerprint": "0" * 64,
        "payload": payload,
    }
