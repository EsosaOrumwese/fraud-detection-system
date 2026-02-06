"""OFP configuration loader (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

from fraud_detection.platform_runtime import resolve_run_scoped_path

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(value: str | None) -> str | None:
    if value is None or not isinstance(value, str):
        return value
    match = _ENV_PATTERN.fullmatch(value.strip())
    if not match:
        return value
    return os.getenv(match.group(1), "")


def _resolve_ref(value: str | None, *, base_dir: Path) -> str | None:
    if not value:
        return value
    ref = Path(value)
    if not ref.is_absolute():
        if not ref.exists():
            ref = base_dir / value
    return str(ref)


@dataclass(frozen=True)
class OfpPolicy:
    feature_group_name: str
    feature_group_version: str
    key_precedence: list[str]
    amount_fields: list[str]
    stream_id_base: str
    stream_id: str
    run_config_digest: str


@dataclass(frozen=True)
class OfpWiring:
    profile_id: str
    projection_db_dsn: str
    event_bus_kind: str
    event_bus_root: str | None
    event_bus_stream: str | None
    event_bus_region: str | None
    event_bus_endpoint_url: str | None
    event_bus_topic: str
    engine_contracts_root: str
    poll_max_records: int
    poll_sleep_seconds: float
    required_platform_run_id: str | None


@dataclass(frozen=True)
class OfpProfile:
    policy: OfpPolicy
    wiring: OfpWiring

    @classmethod
    def load(cls, path: Path) -> "OfpProfile":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if "ofp" in data:
            data = data["ofp"]
        policy = data.get("policy", {})
        wiring = data.get("wiring", {})
        event_bus = wiring.get("event_bus", {})

        profile_id = str(data.get("profile_id") or wiring.get("profile_id") or "local")
        required_platform_run_id = _resolve_env(wiring.get("required_platform_run_id"))
        if not required_platform_run_id:
            required_platform_run_id = os.getenv("OFP_REQUIRED_PLATFORM_RUN_ID") or os.getenv("PLATFORM_RUN_ID")
        required_platform_run_id = required_platform_run_id or None

        stream_id_base = str(policy.get("stream_id") or "ofp.v0")
        stream_id = stream_id_base
        if required_platform_run_id:
            stream_id = f"{stream_id_base}::{required_platform_run_id}"

        projection_db_dsn = _resolve_env(wiring.get("projection_db_dsn"))
        projection_db_dsn = resolve_run_scoped_path(
            projection_db_dsn,
            suffix="online_feature_plane/projection/online_feature_plane.db",
            create_if_missing=True,
        )
        if not projection_db_dsn:
            raise ValueError("PLATFORM_RUN_ID required to resolve OFP projection_db_dsn.")

        event_bus_kind = str(wiring.get("event_bus_kind") or "file").strip().lower()
        event_bus_root = _resolve_env(event_bus.get("root") or event_bus.get("path"))
        event_bus_stream = _resolve_env(event_bus.get("stream"))
        event_bus_region = _resolve_env(event_bus.get("region"))
        event_bus_endpoint_url = _resolve_env(event_bus.get("endpoint_url"))
        topics = _load_topics(event_bus, base_dir=path.parent)
        if len(topics) != 1:
            raise ValueError(f"OFP expects exactly one traffic topic in v0, found {len(topics)}")
        event_bus_topic = topics[0]

        engine_contracts_root = str(
            wiring.get("engine_contracts_root")
            or "docs/model_spec/data-engine/interface_pack/contracts"
        )
        poll_max_records = int(wiring.get("poll_max_records", 200))
        poll_sleep_seconds = float(wiring.get("poll_sleep_seconds", 0.2))

        key_precedence = [str(item) for item in list(policy.get("key_precedence") or ["flow_id", "event_id"])]
        amount_fields = [str(item) for item in list(policy.get("amount_fields") or ["amount"])]
        feature_group_name = str(policy.get("feature_group_name") or "core_features")
        feature_group_version = str(policy.get("feature_group_version") or "v1")
        run_config_digest = _run_config_digest(
            feature_group_name=feature_group_name,
            feature_group_version=feature_group_version,
            key_precedence=key_precedence,
            amount_fields=amount_fields,
            stream_id_base=stream_id_base,
            event_bus_kind=event_bus_kind,
            event_bus_topic=event_bus_topic,
        )
        return cls(
            policy=OfpPolicy(
                feature_group_name=feature_group_name,
                feature_group_version=feature_group_version,
                key_precedence=key_precedence,
                amount_fields=amount_fields,
                stream_id_base=stream_id_base,
                stream_id=stream_id,
                run_config_digest=run_config_digest,
            ),
            wiring=OfpWiring(
                profile_id=profile_id,
                projection_db_dsn=projection_db_dsn,
                event_bus_kind=event_bus_kind,
                event_bus_root=event_bus_root,
                event_bus_stream=event_bus_stream,
                event_bus_region=event_bus_region,
                event_bus_endpoint_url=event_bus_endpoint_url,
                event_bus_topic=event_bus_topic,
                engine_contracts_root=engine_contracts_root,
                poll_max_records=poll_max_records,
                poll_sleep_seconds=poll_sleep_seconds,
                required_platform_run_id=required_platform_run_id,
            ),
        )


def _load_topics(event_bus: dict[str, Any], *, base_dir: Path) -> list[str]:
    env_topics = os.getenv("OFP_TOPICS")
    if env_topics:
        return [item.strip() for item in env_topics.split(",") if item.strip()]
    env_ref = os.getenv("OFP_TOPICS_REF")
    if env_ref:
        ref_path = Path(env_ref)
        if not ref_path.is_absolute():
            if not ref_path.exists():
                ref_path = base_dir / ref_path
        payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
        topics = payload.get("topics") if isinstance(payload, dict) else payload
        if isinstance(topics, list):
            return [str(item) for item in topics if str(item).strip()]
    explicit_topic = _resolve_env(event_bus.get("topic"))
    if explicit_topic:
        return [str(explicit_topic)]
    explicit_topics = event_bus.get("topics")
    if isinstance(explicit_topics, list):
        return [str(item) for item in explicit_topics if str(item).strip()]
    ref = _resolve_env(event_bus.get("topics_ref") or "config/platform/ofp/topics_v0.yaml")
    ref_path = Path(ref) if ref else None
    if ref_path is None:
        return []
    if not ref_path.is_absolute():
        if not ref_path.exists():
            ref_path = base_dir / ref_path
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    topics = payload.get("topics") if isinstance(payload, dict) else payload
    if not isinstance(topics, list):
        return []
    return [str(item) for item in topics if str(item).strip()]


def _run_config_digest(
    *,
    feature_group_name: str,
    feature_group_version: str,
    key_precedence: list[str],
    amount_fields: list[str],
    stream_id_base: str,
    event_bus_kind: str,
    event_bus_topic: str,
) -> str:
    payload = {
        "feature_group_name": feature_group_name,
        "feature_group_version": feature_group_version,
        "key_precedence": list(key_precedence),
        "amount_fields": list(amount_fields),
        "stream_id_base": stream_id_base,
        "event_bus_kind": event_bus_kind,
        "event_bus_topic": event_bus_topic,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

