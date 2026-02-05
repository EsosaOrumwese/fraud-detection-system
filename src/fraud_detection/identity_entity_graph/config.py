"""IEG configuration loader (platform profiles)."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class IegPolicy:
    classification_ref: str
    identity_hints_ref: str
    class_map_ref: str
    partitioning_profiles_ref: str
    graph_stream_id: str


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


@dataclass(frozen=True)
class IegProfile:
    policy: IegPolicy
    wiring: IegWiring

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
        graph_stream_id = str(policy.get("graph_stream_id") or "ieg.v0")

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

        return cls(
            policy=IegPolicy(
                classification_ref=classification_ref,
                identity_hints_ref=identity_hints_ref,
                class_map_ref=class_map_ref,
                partitioning_profiles_ref=partitioning_profiles_ref,
                graph_stream_id=graph_stream_id,
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
            ),
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
