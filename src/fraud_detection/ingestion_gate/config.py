"""IG configuration loaders (wiring + policy)."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .security import load_allowlist

@dataclass(frozen=True)
class PolicyRev:
    policy_id: str
    revision: str
    content_digest: str | None = None


@dataclass(frozen=True)
class WiringProfile:
    profile_id: str
    object_store_root: str
    object_store_endpoint: str | None
    object_store_region: str | None
    object_store_path_style: bool | None
    admission_db_path: str
    sr_ledger_prefix: str
    engine_root_path: str | None
    health_probe_interval_seconds: int
    health_deny_on_amber: bool
    health_amber_sleep_seconds: float
    bus_publish_failure_threshold: int
    metrics_flush_seconds: int
    quarantine_spike_threshold: int
    quarantine_spike_window_seconds: int
    schema_root: str
    engine_contracts_root: str
    engine_catalogue_path: str
    gate_map_path: str
    partitioning_profiles_ref: str
    partitioning_profile_id: str
    schema_policy_ref: str
    class_map_ref: str
    policy_rev: str
    event_bus_kind: str = "file"
    event_bus_path: str | None = None
    control_bus_kind: str = "file"
    control_bus_root: str | None = None
    control_bus_topic: str = "fp.bus.control.v1"
    control_bus_stream: str | None = None
    control_bus_region: str | None = None
    control_bus_endpoint_url: str | None = None
    auth_mode: str = "disabled"
    api_key_header: str = "X-IG-Api-Key"
    auth_allowlist: list[str] | None = None
    auth_allowlist_ref: str | None = None
    ready_allowlist_run_ids: list[str] | None = None
    ready_allowlist_ref: str | None = None
    push_rate_limit_per_minute: int = 0
    ready_rate_limit_per_minute: int = 0
    store_read_failure_threshold: int = 3
    store_read_retry_attempts: int = 3
    store_read_retry_backoff_seconds: float = 0.2
    store_read_retry_max_seconds: float = 2.0
    ready_lease_backend: str = "none"
    ready_lease_dsn: str | None = None
    ready_lease_namespace: str = "ig_ready"
    ready_lease_owner_id: str | None = None
    pull_shard_mode: str = "output_id"
    pull_shard_size: int = 0
    pull_time_budget_seconds: float | None = None

    @classmethod
    def load(cls, path: Path) -> "WiringProfile":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        policy = data.get("policy", {})
        wiring = data.get("wiring", {})
        object_store = wiring.get("object_store", {})
        event_bus = wiring.get("event_bus", {})
        control_bus = wiring.get("control_bus", {})
        security = wiring.get("security", {})
        ready_lease = wiring.get("ready_lease", {})
        pull_sharding = wiring.get("pull_sharding", {})
        pull_time_budget = wiring.get("pull_time_budget_seconds")
        if isinstance(pull_time_budget, str) and pull_time_budget.strip():
            pull_time_budget = float(pull_time_budget)
        endpoint = _resolve_env(object_store.get("endpoint"))
        region = _resolve_env(object_store.get("region"))
        path_style = object_store.get("path_style")
        if isinstance(path_style, str):
            path_style = path_style.lower() in {"1", "true", "yes"}
        root = object_store.get("root")
        bucket = object_store.get("bucket")
        object_store_root = root or "runs"
        if not root and bucket:
            if endpoint or region or object_store.get("kind") == "s3":
                object_store_root = f"s3://{bucket}"
            else:
                object_store_root = bucket
        profile_id = data["profile_id"]
        admission_db_path = wiring.get("admission_db_path")
        if not admission_db_path:
            if str(object_store_root).startswith("s3://"):
                admission_db_path = "runs/fraud-platform/ig/index/ig_admission.db"
            else:
                admission_db_path = str(Path(object_store_root) / "fraud-platform/ig/index/ig_admission.db")
        event_bus_path = wiring.get("event_bus_path") or event_bus.get("root")
        control_bus_root = control_bus.get("root") or wiring.get("control_bus_root")
        control_bus_topic = control_bus.get("topic") or event_bus.get("topic_control") or "fp.bus.control.v1"
        auth_allowlist = list(security.get("auth_allowlist") or [])
        auth_allowlist_ref = security.get("auth_allowlist_ref")
        if auth_allowlist_ref:
            auth_allowlist.extend(load_allowlist(auth_allowlist_ref))
        ready_allowlist = list(security.get("ready_allowlist_run_ids") or [])
        ready_allowlist_ref = security.get("ready_allowlist_ref")
        if ready_allowlist_ref:
            ready_allowlist.extend(load_allowlist(ready_allowlist_ref))
        return cls(
            profile_id=profile_id,
            object_store_root=object_store_root,
            object_store_endpoint=endpoint,
            object_store_region=region,
            object_store_path_style=path_style,
            admission_db_path=admission_db_path,
            sr_ledger_prefix=wiring.get("sr_ledger_prefix", "fraud-platform/sr"),
            engine_root_path=wiring.get("engine_root_path"),
            health_probe_interval_seconds=int(wiring.get("health_probe_interval_seconds", 30)),
            health_deny_on_amber=bool(wiring.get("health_deny_on_amber", False)),
            health_amber_sleep_seconds=float(wiring.get("health_amber_sleep_seconds", 0)),
            bus_publish_failure_threshold=int(wiring.get("bus_publish_failure_threshold", 3)),
            metrics_flush_seconds=int(wiring.get("metrics_flush_seconds", 30)),
            quarantine_spike_threshold=int(wiring.get("quarantine_spike_threshold", 25)),
            quarantine_spike_window_seconds=int(wiring.get("quarantine_spike_window_seconds", 60)),
            schema_root=wiring.get("schema_root", "docs/model_spec/platform/contracts"),
            engine_contracts_root=wiring.get(
                "engine_contracts_root",
                "docs/model_spec/data-engine/interface_pack/contracts",
            ),
            engine_catalogue_path=wiring.get(
                "engine_catalogue_path",
                "docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
            ),
            gate_map_path=wiring.get(
                "gate_map_path",
                "docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
            ),
            partitioning_profiles_ref=policy.get(
                "partitioning_profiles_ref",
                "config/platform/ig/partitioning_profiles_v0.yaml",
            ),
            partitioning_profile_id=policy.get(
                "partitioning_profile_id",
                "ig.partitioning.v0.traffic",
            ),
            schema_policy_ref=policy.get(
                "schema_policy_ref",
                "config/platform/ig/schema_policy_v0.yaml",
            ),
            class_map_ref=policy.get(
                "class_map_ref",
                "config/platform/ig/class_map_v0.yaml",
            ),
            policy_rev=policy.get("policy_rev", profile_id),
            event_bus_kind=wiring.get("event_bus_kind", "file"),
            event_bus_path=event_bus_path,
            control_bus_kind=control_bus.get("kind", wiring.get("control_bus_kind", "file")),
            control_bus_root=control_bus_root,
            control_bus_topic=control_bus_topic,
            control_bus_stream=control_bus.get("stream"),
            control_bus_region=control_bus.get("region"),
            control_bus_endpoint_url=control_bus.get("endpoint_url"),
            auth_mode=security.get("auth_mode", "disabled"),
            api_key_header=security.get("api_key_header", "X-IG-Api-Key"),
            auth_allowlist=auth_allowlist or None,
            auth_allowlist_ref=auth_allowlist_ref,
            ready_allowlist_run_ids=ready_allowlist or None,
            ready_allowlist_ref=ready_allowlist_ref,
            push_rate_limit_per_minute=int(security.get("push_rate_limit_per_minute", 0)),
            ready_rate_limit_per_minute=int(security.get("ready_rate_limit_per_minute", 0)),
            store_read_failure_threshold=int(security.get("store_read_failure_threshold", 3)),
            store_read_retry_attempts=int(security.get("store_read_retry_attempts", 3)),
            store_read_retry_backoff_seconds=float(security.get("store_read_retry_backoff_seconds", 0.2)),
            store_read_retry_max_seconds=float(security.get("store_read_retry_max_seconds", 2.0)),
            ready_lease_backend=ready_lease.get("backend", "none"),
            ready_lease_dsn=_resolve_env(ready_lease.get("dsn")),
            ready_lease_namespace=ready_lease.get("namespace", "ig_ready"),
            ready_lease_owner_id=_resolve_env(ready_lease.get("owner_id")),
            pull_shard_mode=pull_sharding.get("mode", "output_id"),
            pull_shard_size=int(pull_sharding.get("shard_size", 0)),
            pull_time_budget_seconds=pull_time_budget,
        )


@dataclass(frozen=True)
class SchemaPolicyEntry:
    event_type: str
    class_name: str
    schema_version_required: bool
    allowed_schema_versions: list[str] | None
    payload_schema_ref: str | None


@dataclass(frozen=True)
class SchemaPolicy:
    default_action: str
    policies: dict[str, SchemaPolicyEntry]

    @classmethod
    def load(cls, path: Path) -> "SchemaPolicy":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        policies: dict[str, SchemaPolicyEntry] = {}
        for item in data.get("policies", []):
            entry = SchemaPolicyEntry(
                event_type=item["event_type"],
                class_name=item.get("class", "traffic"),
                schema_version_required=bool(item.get("schema_version_required", False)),
                allowed_schema_versions=item.get("allowed_schema_versions"),
                payload_schema_ref=item.get("payload_schema_ref"),
            )
            policies[entry.event_type] = entry
        return cls(default_action=data.get("default_action", "quarantine"), policies=policies)

    def for_event(self, event_type: str) -> SchemaPolicyEntry | None:
        return self.policies.get(event_type)


@dataclass(frozen=True)
class ClassMap:
    required_pins: dict[str, list[str]]
    event_classes: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> "ClassMap":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        classes = data.get("classes", {})
        required_pins: dict[str, list[str]] = {}
        for class_name, class_def in classes.items():
            required_pins[class_name] = list(class_def.get("required_pins", []))
        event_classes: dict[str, str] = {}
        for event_type, class_name in data.get("event_types", {}).items():
            event_classes[event_type] = class_name
        return cls(required_pins=required_pins, event_classes=event_classes)

    def class_for(self, event_type: str) -> str:
        return self.event_classes.get(event_type, "traffic")

    def required_pins_for(self, event_type: str) -> list[str]:
        return self.required_pins.get(self.class_for(event_type), [])


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


_ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _resolve_env(value: str | None) -> str | None:
    if value is None or not isinstance(value, str):
        return value
    match = _ENV_PATTERN.match(value.strip())
    if not match:
        return value
    return os.getenv(match.group(1))
