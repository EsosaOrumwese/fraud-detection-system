"""IEG configuration loader (platform profiles)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from ..platform_runtime import resolve_run_scoped_path

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return value
    match = _ENV_PATTERN.fullmatch(value.strip())
    if match:
        return os.getenv(match.group(1)) or ""
    return value


def _resolve_ref(value: str | None, *, base_dir: Path) -> str | None:
    if not value:
        return value
    resolved = Path(value)
    if not resolved.is_absolute():
        if not resolved.exists():
            resolved = base_dir / value
    return str(resolved)


def _resolve_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "y", "on"}:
            return True
        if token in {"0", "false", "no", "n", "off"}:
            return False
    return default

@dataclass(frozen=True)
class IegPolicy:
    classification_ref: str
    identity_hints_ref: str
    retention_ref: str
    class_map_ref: str
    partitioning_profiles_ref: str
    graph_stream_base: str
    graph_stream_id: str
    run_config_digest: str


@dataclass(frozen=True)
class IegWiring:
    profile_id: str
    projection_db_dsn: str
    event_bus_kind: str
    event_bus_root: str | None
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    event_bus_topics: list[str]
    schema_root: str
    engine_contracts_root: str
    poll_max_records: int
    poll_sleep_seconds: float
    checkpoint_every: int
    max_inflight: int
    batch_size: int
    required_platform_run_id: str | None
    lock_run_scope_on_first_event: bool


@dataclass(frozen=True)
class IegRetention:
    entity_days: int | None
    identifier_days: int | None
    edge_days: int | None
    apply_failure_days: int | None
    checkpoint_days: int | None

    @classmethod
    def load(cls, path: Path) -> "IegRetention":
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "retention" in payload:
            payload = payload["retention"]
        if not isinstance(payload, dict):
            payload = {}
        return cls(
            entity_days=_parse_days(payload.get("entity_days")),
            identifier_days=_parse_days(payload.get("identifier_days")),
            edge_days=_parse_days(payload.get("edge_days")),
            apply_failure_days=_parse_days(payload.get("apply_failure_days")),
            checkpoint_days=_parse_days(payload.get("checkpoint_days")),
        )

    def is_enabled(self) -> bool:
        return any(
            value is not None
            for value in (
                self.entity_days,
                self.identifier_days,
                self.edge_days,
                self.apply_failure_days,
                self.checkpoint_days,
            )
        )


@dataclass(frozen=True)
class IegProfile:
    policy: IegPolicy
    wiring: IegWiring
    retention: IegRetention

    @classmethod
    def load(cls, path: Path) -> "IegProfile":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "ieg" in data:
            data = data["ieg"]
        policy = data.get("policy", {})
        wiring = data.get("wiring", {})
        event_bus = wiring.get("event_bus", {})

        profile_id = data.get("profile_id") or wiring.get("profile_id") or "local"
        classification_ref = _resolve_ref(
            _resolve_env(policy.get("classification_ref") or "config/platform/ieg/classification_v0.yaml"),
            base_dir=path.parent,
        )
        identity_hints_ref = _resolve_ref(
            _resolve_env(policy.get("identity_hints_ref") or "config/platform/ieg/identity_hints_v0.yaml"),
            base_dir=path.parent,
        )
        retention_ref = _resolve_ref(
            _resolve_env(policy.get("retention_ref") or "config/platform/ieg/retention_v0.yaml"),
            base_dir=path.parent,
        )
        class_map_ref = _resolve_ref(
            _resolve_env(policy.get("class_map_ref") or "config/platform/ig/class_map_v0.yaml"),
            base_dir=path.parent,
        )
        partitioning_profiles_ref = _resolve_ref(
            _resolve_env(
                policy.get("partitioning_profiles_ref") or "config/platform/ig/partitioning_profiles_v0.yaml"
            ),
            base_dir=path.parent,
        )
        graph_stream_base = str(policy.get("graph_stream_id") or "ieg.v0")
        required_platform_run_id = _resolve_env(wiring.get("required_platform_run_id"))
        if not required_platform_run_id:
            required_platform_run_id = os.getenv("IEG_REQUIRED_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID")
        required_platform_run_id = required_platform_run_id or None
        lock_run_scope_on_first_event = _resolve_bool(
            wiring.get("lock_run_scope_on_first_event") or os.getenv("IEG_LOCK_RUN_SCOPE"),
            default=True,
        )
        graph_stream_id = graph_stream_base
        if required_platform_run_id:
            graph_stream_id = f"{graph_stream_base}::{required_platform_run_id}"

        projection_db_dsn = _resolve_env(wiring.get("projection_db_dsn"))
        projection_db_dsn = resolve_run_scoped_path(
            projection_db_dsn,
            suffix="identity_entity_graph/projection/identity_entity_graph.db",
            create_if_missing=True,
        )
        if not projection_db_dsn:
            raise ValueError("PLATFORM_RUN_ID required to resolve projection_db_dsn.")

        event_bus_kind = (wiring.get("event_bus_kind") or "file").strip().lower()
        event_bus_root = _resolve_env(event_bus.get("root") or event_bus.get("path"))
        event_bus_stream = _resolve_env(event_bus.get("stream"))
        event_bus_region = _resolve_env(event_bus.get("region"))
        event_bus_endpoint_url = _resolve_env(event_bus.get("endpoint_url"))
        event_bus_topics = _load_topics(event_bus, base_dir=path.parent)

        schema_root = wiring.get("schema_root", "docs/model_spec/platform/contracts")
        engine_contracts_root = wiring.get(
            "engine_contracts_root",
            "docs/model_spec/data-engine/interface_pack/contracts",
        )

        poll_max_records = int(wiring.get("poll_max_records", 200))
        poll_sleep_seconds = float(wiring.get("poll_sleep_seconds", 0.5))
        checkpoint_every = int(wiring.get("checkpoint_every", 1))
        max_inflight = int(wiring.get("max_inflight", poll_max_records))
        batch_size = int(wiring.get("batch_size", min(poll_max_records, 50)))
        if max_inflight < 1:
            max_inflight = max(1, poll_max_records)
        if batch_size < 1:
            batch_size = min(max_inflight, 1)
        if batch_size > max_inflight:
            batch_size = max_inflight
        run_config_digest = _run_config_digest(
            classification_ref=classification_ref,
            identity_hints_ref=identity_hints_ref,
            retention_ref=retention_ref,
            class_map_ref=class_map_ref,
            partitioning_profiles_ref=partitioning_profiles_ref,
            event_bus_kind=event_bus_kind,
            graph_stream_base=graph_stream_base,
            lock_run_scope_on_first_event=lock_run_scope_on_first_event,
            event_bus_topics=event_bus_topics,
        )

        return cls(
            policy=IegPolicy(
                classification_ref=classification_ref,
                identity_hints_ref=identity_hints_ref,
                retention_ref=retention_ref,
                class_map_ref=class_map_ref,
                partitioning_profiles_ref=partitioning_profiles_ref,
                graph_stream_base=graph_stream_base,
                graph_stream_id=graph_stream_id,
                run_config_digest=run_config_digest,
            ),
            wiring=IegWiring(
                profile_id=profile_id,
                projection_db_dsn=projection_db_dsn,
                event_bus_kind=event_bus_kind,
                event_bus_root=event_bus_root,
                event_bus_stream=event_bus_stream,
                event_bus_region=event_bus_region,
                event_bus_endpoint_url=event_bus_endpoint_url,
                event_bus_topics=event_bus_topics,
                schema_root=schema_root,
                engine_contracts_root=engine_contracts_root,
                poll_max_records=poll_max_records,
                poll_sleep_seconds=poll_sleep_seconds,
                checkpoint_every=checkpoint_every,
                max_inflight=max_inflight,
                batch_size=batch_size,
                required_platform_run_id=required_platform_run_id,
                lock_run_scope_on_first_event=lock_run_scope_on_first_event,
            ),
            retention=IegRetention.load(Path(retention_ref)),
        )


def _load_topics(event_bus: dict[str, Any], *, base_dir: Path) -> list[str]:
    env_override = os.getenv("IEG_TOPICS")
    if env_override:
        return [item.strip() for item in env_override.split(",") if item.strip()]
    env_ref = os.getenv("IEG_TOPICS_REF")
    if env_ref:
        ref_path = Path(env_ref)
        if not ref_path.is_absolute():
            if not ref_path.exists():
                ref_path = base_dir / ref_path
        payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
        topics = payload.get("topics") if isinstance(payload, dict) else payload
        if isinstance(topics, list):
            return [str(item) for item in topics if str(item).strip()]
    explicit = event_bus.get("topics")
    if isinstance(explicit, list):
        return [str(item) for item in explicit if str(item).strip()]
    ref = _resolve_env(event_bus.get("topics_ref") or "config/platform/ieg/topics_v0.yaml")
    if not ref:
        return []
    ref_path = Path(ref)
    if not ref_path.is_absolute():
        if not ref_path.exists():
            ref_path = base_dir / ref
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    topics = payload.get("topics") if isinstance(payload, dict) else payload
    if not isinstance(topics, list):
        return []
    return [str(item) for item in topics if str(item).strip()]


def _run_config_digest(
    *,
    classification_ref: str,
    identity_hints_ref: str,
    retention_ref: str,
    class_map_ref: str,
    partitioning_profiles_ref: str,
    event_bus_kind: str,
    graph_stream_base: str,
    lock_run_scope_on_first_event: bool,
    event_bus_topics: list[str],
) -> str:
    topics = sorted({str(item) for item in event_bus_topics if str(item).strip()})
    payload = {
        "policy_refs": {
            "classification_ref": classification_ref,
            "identity_hints_ref": identity_hints_ref,
            "retention_ref": retention_ref,
            "class_map_ref": class_map_ref,
            "partitioning_profiles_ref": partitioning_profiles_ref,
        },
        "event_bus_kind": event_bus_kind,
        "graph_stream_base": graph_stream_base,
        "lock_run_scope_on_first_event": bool(lock_run_scope_on_first_event),
        "event_bus_topics": topics,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_days(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
