"""Configuration loader for SR wiring and policy profiles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class WiringProfile(BaseModel):
    object_store_root: str
    control_bus_topic: str
    control_bus_root: str
    engine_catalogue_path: str
    gate_map_path: str
    schema_root: str
    engine_contracts_root: str
    authority_store_dsn: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_path_style: bool | None = None


class PolicyProfile(BaseModel):
    policy_id: str
    revision: str
    content_digest: str
    reuse_policy: str
    evidence_wait_seconds: int
    attempt_limit: int
    traffic_output_ids: list[str]
    allow_instance_proof_bridge: bool = False

    def as_rev(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "revision": self.revision,
            "content_digest": self.content_digest,
        }


def load_wiring(path: Path) -> WiringProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return WiringProfile(**data)


def load_policy(path: Path) -> PolicyProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PolicyProfile(**data)
