"""WSP configuration loader (platform profiles)."""

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


@dataclass(frozen=True)
class PolicyProfile:
    policy_rev: str
    require_gate_pass: bool
    stream_speedup: float
    traffic_output_ids: list[str]


@dataclass(frozen=True)
class WiringProfile:
    profile_id: str
    object_store_root: str
    object_store_endpoint: str | None
    object_store_region: str | None
    object_store_path_style: bool | None
    control_bus_kind: str
    control_bus_root: str
    control_bus_topic: str
    control_bus_stream: str | None
    control_bus_region: str | None
    control_bus_endpoint_url: str | None
    schema_root: str
    engine_catalogue_path: str
    oracle_root: str
    oracle_engine_run_root: str | None
    oracle_scenario_id: str | None
    stream_view_root: str | None
    ig_ingest_url: str
    checkpoint_backend: str
    checkpoint_root: str
    checkpoint_dsn: str | None
    checkpoint_every: int
    producer_id: str
    producer_allowlist_ref: str | None


@dataclass(frozen=True)
class WspProfile:
    policy: PolicyProfile
    wiring: WiringProfile

    @classmethod
    def load(cls, path: Path) -> "WspProfile":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        policy = data.get("policy", {})
        wiring = data.get("wiring", {})
        object_store = wiring.get("object_store", {})
        control_bus = wiring.get("control_bus", {})
        checkpoint = wiring.get("wsp_checkpoint", {})
        producer = wiring.get("wsp_producer", {})

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

        policy_rev = policy.get("policy_rev", data.get("profile_id", "local"))
        require_gate_pass = bool(policy.get("require_gate_pass", True))
        stream_speedup = float(policy.get("stream_speedup", 1.0))
        traffic_output_ids = _load_output_ids(policy, base_dir=path.parent)

        control_bus_kind = control_bus.get("kind", "file")
        control_bus_root = control_bus.get("root", "runs/fraud-platform/control_bus")
        control_bus_root = resolve_run_scoped_path(
            _resolve_env(control_bus_root),
            suffix="control_bus",
            create_if_missing=True,
        )
        control_bus_topic = control_bus.get("topic", "fp.bus.control.v1")
        control_bus_stream = _resolve_env(control_bus.get("stream"))
        control_bus_region = _resolve_env(control_bus.get("region"))
        control_bus_endpoint_url = _resolve_env(control_bus.get("endpoint_url"))

        schema_root = wiring.get("schema_root", "docs/model_spec/platform/contracts")
        engine_catalogue_path = wiring.get(
            "engine_catalogue_path",
            "docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        )
        oracle_root = _resolve_env(wiring.get("oracle_root") or "runs/local_full_run-5")
        oracle_engine_run_root = _resolve_env(wiring.get("oracle_engine_run_root"))
        oracle_scenario_id = _resolve_env(wiring.get("oracle_scenario_id"))
        stream_view_root = _resolve_env(wiring.get("oracle_stream_view_root"))
        ig_ingest_url = _resolve_env(wiring.get("ig_ingest_url") or "http://localhost:8081")

        checkpoint_backend = checkpoint.get("backend", "file")
        checkpoint_root = resolve_run_scoped_path(
            _resolve_env(checkpoint.get("root") or "runs/fraud-platform/wsp/checkpoints"),
            suffix="wsp/checkpoints",
            create_if_missing=True,
        )
        checkpoint_dsn = _resolve_env(checkpoint.get("dsn"))
        checkpoint_every = int(checkpoint.get("flush_every", 1))
        producer_id = (producer.get("producer_id") or "svc:world_stream_producer").strip()
        producer_allowlist_ref = _resolve_env(
            producer.get("allowlist_ref") or "config/platform/wsp/producer_allowlist_v0.txt"
        )
        if producer_allowlist_ref:
            allowlist_path = Path(producer_allowlist_ref)
            if not allowlist_path.is_absolute():
                if not allowlist_path.exists():
                    allowlist_path = path.parent / allowlist_path
                producer_allowlist_ref = str(allowlist_path)

        return cls(
            policy=PolicyProfile(
                policy_rev=policy_rev,
                require_gate_pass=require_gate_pass,
                stream_speedup=stream_speedup,
                traffic_output_ids=traffic_output_ids,
            ),
            wiring=WiringProfile(
                profile_id=data["profile_id"],
                object_store_root=object_store_root,
                object_store_endpoint=endpoint,
                object_store_region=region,
                object_store_path_style=path_style,
                control_bus_kind=control_bus_kind,
                control_bus_root=control_bus_root,
                control_bus_topic=control_bus_topic,
                control_bus_stream=control_bus_stream,
                control_bus_region=control_bus_region,
                control_bus_endpoint_url=control_bus_endpoint_url,
                schema_root=schema_root,
                engine_catalogue_path=engine_catalogue_path,
                oracle_root=oracle_root,
                oracle_engine_run_root=oracle_engine_run_root,
                oracle_scenario_id=oracle_scenario_id,
                stream_view_root=stream_view_root,
                ig_ingest_url=ig_ingest_url,
                checkpoint_backend=checkpoint_backend,
                checkpoint_root=checkpoint_root,
                checkpoint_dsn=checkpoint_dsn,
                checkpoint_every=checkpoint_every,
                producer_id=producer_id,
                producer_allowlist_ref=producer_allowlist_ref,
            ),
        )


def _load_output_ids(policy: dict[str, Any], *, base_dir: Path) -> list[str]:
    env_override = os.getenv("WSP_TRAFFIC_OUTPUT_IDS")
    if env_override:
        return [item.strip() for item in env_override.split(",") if item.strip()]
    env_ref = os.getenv("WSP_TRAFFIC_OUTPUT_IDS_REF")
    if env_ref:
        ref_path = Path(env_ref)
        if not ref_path.is_absolute():
            if not ref_path.exists():
                ref_path = base_dir / ref_path
        payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            items = payload.get("output_ids") or []
        else:
            items = payload or []
        if isinstance(items, list):
            return [str(item) for item in items if str(item).strip()]
    explicit = policy.get("traffic_output_ids")
    if isinstance(explicit, list):
        return [str(item) for item in explicit if str(item).strip()]
    ref = _resolve_env(policy.get("traffic_output_ids_ref"))
    if not ref:
        return []
    ref_path = Path(ref)
    if not ref_path.is_absolute():
        if not ref_path.exists():
            ref_path = base_dir / ref_path
    payload = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("output_ids") or []
    else:
        items = payload or []
    if not isinstance(items, list):
        return []
    return [str(item) for item in items if str(item).strip()]
