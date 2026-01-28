"""Oracle Store configuration loader (platform profiles)."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from pathlib import Path

import yaml


_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return value
    match = _ENV_PATTERN.fullmatch(value.strip())
    if match:
        return os.getenv(match.group(1)) or ""
    return value


@dataclass(frozen=True)
class OraclePolicy:
    policy_rev: str
    require_gate_pass: bool


@dataclass(frozen=True)
class OracleWiring:
    profile_id: str
    object_store_root: str
    object_store_endpoint: str | None
    object_store_region: str | None
    object_store_path_style: bool | None
    schema_root: str
    engine_catalogue_path: str
    oracle_root: str


@dataclass(frozen=True)
class OracleProfile:
    policy: OraclePolicy
    wiring: OracleWiring

    @classmethod
    def load(cls, path: Path) -> "OracleProfile":
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        policy = data.get("policy", {})
        wiring = data.get("wiring", {})
        object_store = wiring.get("object_store", {})

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

        schema_root = wiring.get("schema_root", "docs/model_spec/platform/contracts")
        engine_catalogue_path = wiring.get(
            "engine_catalogue_path",
            "docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        )
        oracle_root = _resolve_env(wiring.get("oracle_root") or "runs/local_full_run-5")

        return cls(
            policy=OraclePolicy(policy_rev=policy_rev, require_gate_pass=require_gate_pass),
            wiring=OracleWiring(
                profile_id=data["profile_id"],
                object_store_root=object_store_root,
                object_store_endpoint=endpoint,
                object_store_region=region,
                object_store_path_style=path_style,
                schema_root=schema_root,
                engine_catalogue_path=engine_catalogue_path,
                oracle_root=oracle_root,
            ),
        )
