"""Configuration loader for SR wiring and policy profiles."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class WiringProfile(BaseModel):
    profile_id: str = "local"
    object_store_root: str
    control_bus_topic: str
    control_bus_root: str
    control_bus_kind: str = "file"
    control_bus_stream: str | None = None
    control_bus_region: str | None = None
    control_bus_endpoint_url: str | None = None
    engine_catalogue_path: str
    gate_map_path: str
    schema_root: str
    engine_contracts_root: str
    oracle_engine_run_root: str | None = None
    oracle_scenario_id: str | None = None
    oracle_stream_view_root: str | None = None
    engine_command: list[str] | None = None
    engine_command_cwd: str | None = None
    engine_command_timeout_seconds: int | None = None
    authority_store_dsn: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_path_style: bool | None = None
    auth_mode: str = "disabled"
    auth_allowlist: list[str] = []
    reemit_allowlist: list[str] = []
    reemit_rate_limit_max: int | None = None
    reemit_rate_limit_window_seconds: int = 3600
    acceptance_mode: str = "local_parity"
    execution_mode: str = "local"
    execution_launch_ref: str | None = None
    execution_identity_env: str | None = None
    state_mode: str = "local"
    reemit_same_platform_run_only: bool = False
    reemit_cross_run_override_required: bool = True
    reemit_cross_run_reason_allowlist: list[str] = []


class PolicyProfile(BaseModel):
    policy_id: str
    revision: str
    content_digest: str
    reuse_policy: str
    evidence_wait_seconds: int
    attempt_limit: int
    traffic_output_ids: list[str]

    def as_rev(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "revision": self.revision,
            "content_digest": self.content_digest,
        }


def _expand_str(value: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group(1)
        if ":-" in token:
            key, default = token.split(":-", 1)
            actual = os.getenv(key, "")
            return actual if actual.strip() else default
        actual = os.getenv(token, "")
        if not actual.strip():
            raise ValueError(f"missing environment variable: {token}")
        return actual

    return _VAR_PATTERN.sub(replacer, value)


def _expand_payload(value: Any) -> Any:
    if isinstance(value, str):
        return _expand_str(value)
    if isinstance(value, list):
        return [_expand_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _expand_payload(item) for key, item in value.items()}
    return value


def load_wiring(path: Path) -> WiringProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    expanded = _expand_payload(data)
    return WiringProfile(**expanded)


def load_policy(path: Path) -> PolicyProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    expanded = _expand_payload(data)
    return PolicyProfile(**expanded)
