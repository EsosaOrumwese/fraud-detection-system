"""OFP configuration loader (Phase 3)."""

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
_DURATION_PATTERN = re.compile(r"^\s*(\d+)\s*([smhdSMHD])\s*$")

_DEFAULT_WINDOWS = [
    {"window": "1h", "duration": "1h", "ttl": "1h"},
    {"window": "24h", "duration": "24h", "ttl": "24h"},
    {"window": "7d", "duration": "7d", "ttl": "7d"},
]


@dataclass(frozen=True)
class FeatureDefPolicyRev:
    policy_id: str
    revision: str
    content_digest: str


@dataclass(frozen=True)
class FeatureWindowSpec:
    window: str
    duration_seconds: int
    ttl_seconds: int


@dataclass(frozen=True)
class FeatureGroupSpec:
    name: str
    version: str
    key_type: str
    windows: list[FeatureWindowSpec]


@dataclass(frozen=True)
class OfpPolicy:
    feature_group_name: str
    feature_group_version: str
    feature_groups: list[FeatureGroupSpec]
    feature_def_policy_rev: FeatureDefPolicyRev
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

        features_ref = _resolve_env(policy.get("features_ref") or os.getenv("OFP_FEATURES_REF") or "config/platform/ofp/features_v0.yaml")
        feature_def_policy_rev, feature_groups = _load_feature_definitions(features_ref, base_dir=path.parent)

        configured_group_name = str(policy.get("feature_group_name") or "").strip()
        configured_group_version = str(policy.get("feature_group_version") or "").strip()
        active_group = _resolve_active_group(
            feature_groups,
            configured_group_name=configured_group_name,
            configured_group_version=configured_group_version,
        )

        run_config_digest = _run_config_digest(
            feature_def_policy_rev=feature_def_policy_rev,
            feature_groups=feature_groups,
            feature_group_name=active_group.name,
            feature_group_version=active_group.version,
            key_precedence=key_precedence,
            amount_fields=amount_fields,
            stream_id_base=stream_id_base,
            event_bus_kind=event_bus_kind,
            event_bus_topic=event_bus_topic,
        )
        return cls(
            policy=OfpPolicy(
                feature_group_name=active_group.name,
                feature_group_version=active_group.version,
                feature_groups=feature_groups,
                feature_def_policy_rev=feature_def_policy_rev,
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


def _resolve_env(value: str | None) -> str | None:
    if value is None or not isinstance(value, str):
        return value
    match = _ENV_PATTERN.fullmatch(value.strip())
    if not match:
        return value
    return os.getenv(match.group(1), "")


def _resolve_ref(value: str | None, *, base_dir: Path) -> Path:
    if not value:
        raise ValueError("missing required reference path")
    ref = Path(str(value))
    if not ref.is_absolute() and not ref.exists():
        ref = base_dir / ref
    return ref


def _load_topics(event_bus: dict[str, Any], *, base_dir: Path) -> list[str]:
    env_topics = os.getenv("OFP_TOPICS")
    if env_topics:
        return [item.strip() for item in env_topics.split(",") if item.strip()]
    env_ref = os.getenv("OFP_TOPICS_REF")
    if env_ref:
        ref_path = _resolve_ref(env_ref, base_dir=base_dir)
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
    ref_path = _resolve_ref(ref, base_dir=base_dir)
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    topics = payload.get("topics") if isinstance(payload, dict) else payload
    if not isinstance(topics, list):
        return []
    return [str(item) for item in topics if str(item).strip()]


def _load_feature_definitions(
    features_ref: str | None,
    *,
    base_dir: Path,
) -> tuple[FeatureDefPolicyRev, list[FeatureGroupSpec]]:
    ref_path = _resolve_ref(features_ref, base_dir=base_dir)
    if not ref_path.exists():
        raise ValueError(f"OFP features_ref not found: {ref_path}")
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OFP features_ref payload must be a mapping")

    policy_id = str(payload.get("policy_id") or "").strip()
    revision = str(payload.get("revision") or "").strip()
    if not policy_id or not revision:
        raise ValueError("OFP feature definition policy must include non-empty policy_id and revision")

    groups_payload = payload.get("feature_groups")
    if not isinstance(groups_payload, list) or not groups_payload:
        raise ValueError("OFP feature definition policy must include non-empty feature_groups")

    groups: list[FeatureGroupSpec] = []
    for index, entry in enumerate(groups_payload):
        if not isinstance(entry, dict):
            raise ValueError(f"feature_groups[{index}] must be a mapping")
        name = str(entry.get("name") or "").strip()
        version = str(entry.get("version") or "").strip()
        key_type = str(entry.get("key_type") or "flow_id").strip()
        if not name or not version or not key_type:
            raise ValueError(f"feature_groups[{index}] requires name/version/key_type")

        windows_payload = entry.get("windows")
        if windows_payload is None:
            windows_payload = list(_DEFAULT_WINDOWS)
        if not isinstance(windows_payload, list) or not windows_payload:
            raise ValueError(f"feature_groups[{index}].windows must be a non-empty list")

        windows: list[FeatureWindowSpec] = []
        seen: set[str] = set()
        for widx, wentry in enumerate(windows_payload):
            window, duration_seconds, ttl_seconds = _parse_window_spec(
                wentry, index=index, window_index=widx
            )
            if window in seen:
                raise ValueError(f"feature_groups[{index}].windows has duplicate window '{window}'")
            seen.add(window)
            windows.append(
                FeatureWindowSpec(
                    window=window,
                    duration_seconds=duration_seconds,
                    ttl_seconds=ttl_seconds,
                )
            )
        groups.append(
            FeatureGroupSpec(
                name=name,
                version=version,
                key_type=key_type,
                windows=windows,
            )
        )

    digest_payload = {
        "policy_id": policy_id,
        "revision": revision,
        "feature_groups": [_group_to_payload(group) for group in groups],
    }
    canonical = json.dumps(digest_payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    content_digest = str(payload.get("content_digest") or "").strip()
    if not content_digest:
        content_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return (
        FeatureDefPolicyRev(
            policy_id=policy_id,
            revision=revision,
            content_digest=content_digest,
        ),
        groups,
    )


def _resolve_active_group(
    groups: list[FeatureGroupSpec],
    *,
    configured_group_name: str,
    configured_group_version: str,
) -> FeatureGroupSpec:
    if not groups:
        raise ValueError("OFP feature definition policy contains no groups")
    if not configured_group_name and not configured_group_version:
        return groups[0]
    for group in groups:
        if group.name == configured_group_name and group.version == configured_group_version:
            return group
    raise ValueError(
        "Configured OFP feature_group_name/version not found in feature definition policy: "
        f"{configured_group_name}:{configured_group_version}"
    )


def _parse_window_spec(entry: Any, *, index: int, window_index: int) -> tuple[str, int, int]:
    if isinstance(entry, str):
        window = entry.strip()
        duration_raw = window
        ttl_raw = window
    elif isinstance(entry, dict):
        window = str(entry.get("window") or entry.get("name") or entry.get("duration") or "").strip()
        duration_raw = str(entry.get("duration") or window).strip()
        ttl_raw = str(entry.get("ttl") or duration_raw).strip()
    else:
        raise ValueError(f"feature_groups[{index}].windows[{window_index}] must be string or mapping")

    if not window:
        raise ValueError(f"feature_groups[{index}].windows[{window_index}] missing window name")

    duration_seconds = _parse_duration_to_seconds(duration_raw)
    ttl_seconds = _parse_duration_to_seconds(ttl_raw)
    if ttl_seconds < duration_seconds:
        raise ValueError(
            f"feature_groups[{index}].windows[{window_index}] ttl must be >= duration"
        )
    return window, duration_seconds, ttl_seconds


def _parse_duration_to_seconds(value: str) -> int:
    token = str(value or "").strip()
    match = _DURATION_PATTERN.fullmatch(token)
    if not match:
        raise ValueError(f"invalid duration token '{value}' (expected integer + unit s|m|h|d)")
    magnitude = int(match.group(1))
    unit = match.group(2).lower()
    scale = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    seconds = magnitude * scale
    if seconds <= 0:
        raise ValueError(f"duration must be > 0: {value}")
    return seconds


def _group_to_payload(group: FeatureGroupSpec) -> dict[str, Any]:
    return {
        "name": group.name,
        "version": group.version,
        "key_type": group.key_type,
        "windows": [
            {
                "window": window.window,
                "duration_seconds": window.duration_seconds,
                "ttl_seconds": window.ttl_seconds,
            }
            for window in group.windows
        ],
    }


def _run_config_digest(
    *,
    feature_def_policy_rev: FeatureDefPolicyRev,
    feature_groups: list[FeatureGroupSpec],
    feature_group_name: str,
    feature_group_version: str,
    key_precedence: list[str],
    amount_fields: list[str],
    stream_id_base: str,
    event_bus_kind: str,
    event_bus_topic: str,
) -> str:
    payload = {
        "feature_def_policy_rev": {
            "policy_id": feature_def_policy_rev.policy_id,
            "revision": feature_def_policy_rev.revision,
            "content_digest": feature_def_policy_rev.content_digest,
        },
        "feature_groups": [_group_to_payload(group) for group in feature_groups],
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
