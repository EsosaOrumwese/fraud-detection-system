"""Governance facts emission for IG."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from fraud_detection.event_bus import EventBusPublisher
from fraud_detection.platform_provenance import runtime_provenance
from fraud_detection.platform_governance import emit_platform_governance_event
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
    prefix: str
    _quarantine_ts: deque[float] = field(default_factory=deque)
    _last_spike_ts: float | None = None

    def emit_policy_activation(self, policy_rev: dict[str, Any]) -> None:
        digest = policy_rev.get("content_digest")
        if not digest:
            return
        active_path = f"{self.prefix}/ig/policy/active.json"
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
        platform_run_id = _platform_run_id_from_prefix(self.prefix)
        emit_platform_governance_event(
            store=self.store,
            event_family="POLICY_REV_CHANGED",
            actor_id="SYSTEM::ingestion_gate",
            source_type="SYSTEM",
            source_component="ingestion_gate",
            platform_run_id=platform_run_id,
            dedupe_key=f"ig_policy_activation:{digest}",
            details={
                "policy_id": payload["policy_id"],
                "revision": payload["revision"],
                "content_digest": payload["content_digest"],
                "activated_at_utc": payload["activated_at_utc"],
                "run_config_digest": payload["content_digest"],
                "provenance": runtime_provenance(
                    component="ingestion_gate",
                    config_revision=str(payload["revision"]),
                    run_config_digest=str(payload["content_digest"]),
                ),
            },
        )
        envelope = _make_envelope("ig.policy.activation", payload)
        self._emit_audit(envelope)

    def emit_quarantine_spike(self, count: int) -> None:
        now = datetime.now(tz=timezone.utc).timestamp()
        window_start = now - self.quarantine_spike_window_seconds
        while self._quarantine_ts and self._quarantine_ts[0] < window_start:
            self._quarantine_ts.popleft()
        self._quarantine_ts.append(now)
        if len(self._quarantine_ts) < self.quarantine_spike_threshold:
            return
        if self._last_spike_ts and (now - self._last_spike_ts) < self.quarantine_spike_window_seconds:
            return
        self._last_spike_ts = now
        payload = {
            "policy_id": self.policy_id,
            "quarantine_count": len(self._quarantine_ts),
            "window_seconds": self.quarantine_spike_window_seconds,
            "detected_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        }
        envelope = _make_envelope("ig.quarantine.spike", payload)
        self._emit_audit(envelope)

    def emit_audit_verification(self, payload: dict[str, Any]) -> None:
        envelope = _make_envelope("ig.audit.verify", payload)
        self._emit_audit(envelope)

    def _emit_audit(self, envelope: dict[str, Any]) -> None:
        profile_id = "ig.partitioning.v0.audit"
        partition_key = self.partitioning.derive_key(profile_id, envelope)
        stream = self.partitioning.get(profile_id).stream
        self.bus.publish(stream, partition_key, envelope)


def _make_envelope(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    ts = datetime.now(tz=timezone.utc).isoformat()
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    event_id = hashlib.sha256(f"{event_type}:{ts}:{encoded}".encode("utf-8")).hexdigest()
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ts_utc": ts,
        "manifest_fingerprint": "0" * 64,
        "payload": payload,
    }


def _platform_run_id_from_prefix(prefix: str) -> str:
    text = str(prefix or "").strip().rstrip("/")
    if not text:
        raise ValueError("governance prefix missing run scope")
    if text.startswith("fraud-platform/"):
        run_id = text.split("/", 1)[1]
        if run_id:
            return run_id
    parts = [item for item in text.split("/") if item]
    if not parts:
        raise ValueError("governance prefix missing run scope")
    return parts[-1]
