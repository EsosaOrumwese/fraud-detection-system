"""Platform-wide governance fact writer (idempotent append-only)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from fraud_detection.platform_provenance import runtime_provenance
from fraud_detection.scenario_runner.storage import (
    LocalObjectStore,
    ObjectStore,
    S3ObjectStore,
    build_object_store,
)


EVENT_FAMILIES: frozenset[str] = frozenset(
    {
        "RUN_READY_SEEN",
        "RUN_STARTED",
        "RUN_ENDED",
        "RUN_CANCELLED",
        "POLICY_REV_CHANGED",
        "CORRIDOR_ANOMALY",
        "EVIDENCE_REF_RESOLVED",
        "RUN_REPORT_GENERATED",
    }
)

LOGGER = logging.getLogger(__name__)


class PlatformGovernanceError(ValueError):
    """Raised when governance events are invalid."""


@dataclass(frozen=True)
class GovernanceEvent:
    event_family: str
    actor_id: str
    source_type: str
    source_component: str
    platform_run_id: str
    details: dict[str, Any]
    scenario_run_id: str | None = None
    manifest_fingerprint: str | None = None
    parameter_hash: str | None = None
    seed: str | int | None = None
    scenario_id: str | None = None
    dedupe_key: str | None = None
    event_id: str | None = None
    ts_utc: str | None = None


class PlatformGovernanceWriter:
    """Writes governance facts with marker-based idempotency."""

    def __init__(self, store: ObjectStore) -> None:
        self.store = store

    def emit(self, event: GovernanceEvent) -> dict[str, Any] | None:
        payload = _normalize_event(event)
        marker_path = _marker_path(self.store, payload["pins"]["platform_run_id"], payload["event_id"])
        event_path = _event_path(self.store, payload["pins"]["platform_run_id"], payload["event_id"])
        marker_payload = {
            "event_id": payload["event_id"],
            "event_family": payload["event_family"],
            "ts_utc": payload["ts_utc"],
        }
        try:
            self.store.write_json_if_absent(event_path, payload)
        except FileExistsError:
            return None
        try:
            self.store.write_json_if_absent(marker_path, marker_payload)
        except FileExistsError:
            pass
        try:
            self.store.append_jsonl(
                _events_path(self.store, payload["pins"]["platform_run_id"]),
                [payload],
            )
        except Exception as exc:
            if "S3_APPEND_CONFLICT" not in str(exc):
                raise
            LOGGER.warning(
                "Governance projection append deferred platform_run_id=%s event_id=%s reason=%s",
                payload["pins"]["platform_run_id"],
                payload["event_id"],
                str(exc)[:256],
            )
        return payload

    def query(
        self,
        *,
        platform_run_id: str,
        event_family: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        run_id = _required(platform_run_id, "platform_run_id")
        family_filter = event_family.strip().upper() if event_family else None
        items = self._event_payloads(run_id=run_id)
        if family_filter:
            items = [
                payload
                for payload in items
                if str(payload.get("event_family") or "").upper() == family_filter
            ]
        if limit is not None and limit > 0:
            return items[-limit:]
        return items

    def _event_payloads(self, *, run_id: str) -> list[dict[str, Any]]:
        items = self._event_payloads_from_objects(run_id=run_id)
        if items:
            return items
        return self._event_payloads_from_projection(run_id=run_id)

    def _event_payloads_from_objects(self, *, run_id: str) -> list[dict[str, Any]]:
        if not hasattr(self.store, "list_files"):
            return []
        try:
            files = list(getattr(self.store, "list_files")(_events_dir(self.store, run_id)))
        except Exception:
            return []
        items: list[dict[str, Any]] = []
        for file_path in sorted(files):
            payload = _read_store_json(self.store, file_path)
            if payload:
                items.append(payload)
        items.sort(key=lambda item: (str(item.get("ts_utc") or ""), str(item.get("event_id") or "")))
        return items

    def _event_payloads_from_projection(self, *, run_id: str) -> list[dict[str, Any]]:
        if not hasattr(self.store, "read_text"):
            return []
        path = _events_path(self.store, run_id)
        if not self.store.exists(path):
            return []
        text = self.store.read_text(path)
        items: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                items.append(payload)
        items.sort(key=lambda item: (str(item.get("ts_utc") or ""), str(item.get("event_id") or "")))
        return items


def emit_platform_governance_event(
    *,
    store: ObjectStore,
    event_family: str,
    actor_id: str,
    source_type: str,
    source_component: str,
    platform_run_id: str,
    details: dict[str, Any],
    scenario_run_id: str | None = None,
    manifest_fingerprint: str | None = None,
    parameter_hash: str | None = None,
    seed: str | int | None = None,
    scenario_id: str | None = None,
    dedupe_key: str | None = None,
    event_id: str | None = None,
    ts_utc: str | None = None,
) -> dict[str, Any] | None:
    writer = PlatformGovernanceWriter(store)
    return writer.emit(
        GovernanceEvent(
            event_family=event_family,
            actor_id=actor_id,
            source_type=source_type,
            source_component=source_component,
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
            scenario_id=scenario_id,
            details=details,
            dedupe_key=dedupe_key,
            event_id=event_id,
            ts_utc=ts_utc,
        )
    )


def build_platform_governance_writer(
    *,
    object_store_root: str | None = None,
    object_store_endpoint: str | None = None,
    object_store_region: str | None = None,
    object_store_path_style: bool | None = None,
) -> PlatformGovernanceWriter:
    root = object_store_root or (os.getenv("PLATFORM_STORE_ROOT") or "").strip() or "runs/fraud-platform"
    endpoint = object_store_endpoint or _strip_or_none(os.getenv("OBJECT_STORE_ENDPOINT"))
    region = object_store_region or _strip_or_none(os.getenv("OBJECT_STORE_REGION"))
    path_style_env = _strip_or_none(os.getenv("OBJECT_STORE_PATH_STYLE"))
    path_style = object_store_path_style
    if path_style is None and path_style_env is not None:
        path_style = path_style_env.lower() in {"1", "true", "yes"}
    store = build_object_store(
        root,
        s3_endpoint_url=endpoint,
        s3_region=region,
        s3_path_style=path_style,
    )
    return PlatformGovernanceWriter(store)


def _normalize_event(event: GovernanceEvent) -> dict[str, Any]:
    family = _required(event.event_family, "event_family").upper()
    if family not in EVENT_FAMILIES:
        raise PlatformGovernanceError(f"unsupported event_family: {family}")
    actor_id = _required(event.actor_id, "actor_id")
    source_type = _required(event.source_type, "source_type")
    source_component = _required(event.source_component, "source_component")
    platform_run_id = _required(event.platform_run_id, "platform_run_id")
    details = _mapping(event.details, "details")
    run_config_digest = _run_config_digest_from_details(details)

    pins: dict[str, Any] = {"platform_run_id": platform_run_id}
    if event.scenario_run_id:
        pins["scenario_run_id"] = str(event.scenario_run_id)
    if event.manifest_fingerprint:
        pins["manifest_fingerprint"] = str(event.manifest_fingerprint)
    if event.parameter_hash:
        pins["parameter_hash"] = str(event.parameter_hash)
    if event.seed is not None and str(event.seed).strip():
        pins["seed"] = str(event.seed)
    if event.scenario_id:
        pins["scenario_id"] = str(event.scenario_id)

    ts_utc = event.ts_utc or datetime.now(tz=timezone.utc).isoformat()
    event_id = event.event_id or _event_id(
        family=family,
        platform_run_id=platform_run_id,
        scenario_run_id=str(event.scenario_run_id or ""),
        source_component=source_component,
        dedupe_key=event.dedupe_key,
        details=details,
    )
    provenance = _provenance_from_details(details) or runtime_provenance(
        component=source_component,
        run_config_digest=run_config_digest,
    )
    return {
        "event_id": event_id,
        "event_family": family,
        "ts_utc": ts_utc,
        "actor": {
            "actor_id": actor_id,
            "source_type": _normalize_source_type(source_type),
            "source_component": source_component,
        },
        "pins": pins,
        "provenance": provenance,
        "details": details,
    }


def _event_id(
    *,
    family: str,
    platform_run_id: str,
    scenario_run_id: str,
    source_component: str,
    dedupe_key: str | None,
    details: dict[str, Any],
) -> str:
    stable_key = dedupe_key or json.dumps(details, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    raw = f"{family}|{platform_run_id}|{scenario_run_id}|{source_component}|{stable_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _events_path(store: ObjectStore, platform_run_id: str) -> str:
    return f"{_run_prefix_for_store(store, platform_run_id)}/obs/governance/events.jsonl"


def _events_dir(store: ObjectStore, platform_run_id: str) -> str:
    return f"{_run_prefix_for_store(store, platform_run_id)}/obs/governance/events"


def _event_path(store: ObjectStore, platform_run_id: str, event_id: str) -> str:
    return f"{_run_prefix_for_store(store, platform_run_id)}/obs/governance/events/{event_id}.json"


def _marker_path(store: ObjectStore, platform_run_id: str, event_id: str) -> str:
    return f"{_run_prefix_for_store(store, platform_run_id)}/obs/governance/markers/{event_id}.json"


def _run_prefix_for_store(store: ObjectStore, platform_run_id: str) -> str:
    if isinstance(store, S3ObjectStore):
        return platform_run_id
    if isinstance(store, LocalObjectStore):
        root: Path = store.root
        if root.name == "fraud-platform":
            return platform_run_id
    return f"fraud-platform/{platform_run_id}"


def _required(value: str | None, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PlatformGovernanceError(f"{field_name} is required")
    return text


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlatformGovernanceError(f"{field_name} must be a mapping")
    return dict(value)


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _run_config_digest_from_details(details: dict[str, Any]) -> str | None:
    candidate = details.get("run_config_digest")
    text = str(candidate or "").strip()
    if text:
        return text
    policy = details.get("policy_rev")
    if isinstance(policy, dict):
        digest = str(policy.get("content_digest") or "").strip()
        if digest:
            return digest
    return None


def _normalize_source_type(source_type: str) -> str:
    text = str(source_type or "").strip().upper()
    if text in {"SERVICE", "SYSTEM"}:
        return "SYSTEM"
    if text in {"HUMAN", "USER", "OPERATOR"}:
        return "HUMAN"
    return text or "SYSTEM"


def _provenance_from_details(details: dict[str, Any]) -> dict[str, Any] | None:
    value = details.get("provenance")
    if not isinstance(value, dict):
        return None
    payload = dict(value)
    if not payload.get("service_release_id") or not payload.get("environment"):
        return None
    return payload


def _read_store_json(store: ObjectStore, path: str) -> dict[str, Any]:
    try:
        if isinstance(store, S3ObjectStore):
            payload = store.read_json(_s3_relative_path(store, path))
        else:
            payload = store.read_json(path)
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _s3_relative_path(store: S3ObjectStore, absolute_path: str) -> str:
    text = str(absolute_path or "").strip()
    if not text.startswith("s3://"):
        return text
    prefix = f"s3://{store.bucket}/"
    if not text.startswith(prefix):
        return text
    key = text[len(prefix) :]
    store_prefix = f"{store.prefix}/" if store.prefix else ""
    if store_prefix and key.startswith(store_prefix):
        return key[len(store_prefix) :]
    return key
