"""Helpers for loading token-less policies sealed by Segment 2B S0."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Tuple

from ..s0_gate.exceptions import err
from .dictionary import repository_root


def resolve_catalog_path(*, base_path: Path, relative_path: str, repo_root: Path | None = None) -> Path:
    """Resolve a catalog-relative policy path to an absolute path."""

    repo = repo_root or repository_root()
    rel_path = Path(relative_path.strip("/"))
    candidate = (base_path / rel_path).resolve()
    if candidate.exists():
        return candidate
    fallback = (repo / rel_path).resolve()
    if fallback.exists():
        return fallback
    return candidate


def load_policy_asset(
    *,
    asset_id: str,
    sealed_records: Mapping[str, "SealedInputRecord"],
    base_path: Path,
    repo_root: Path | None = None,
    error_prefix: str = "E_POLICY",
) -> Tuple[Mapping[str, object], str, str, Path]:
    """Load a token-less policy from the sealed inventory and verify its digest."""

    from .receipt import SealedInputRecord  # Local import to avoid cycles

    record = sealed_records.get(asset_id)
    if record is None:
        raise err(
            f"{error_prefix}_MISSING",
            f"sealed asset '{asset_id}' missing from inventory",
        )
    policy_path = resolve_catalog_path(
        base_path=base_path,
        relative_path=record.catalog_path,
        repo_root=repo_root,
    )
    if not policy_path.exists():
        raise err(
            f"{error_prefix}_PATH",
            f"policy '{asset_id}' not found at '{policy_path}'",
        )
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    file_bytes = policy_path.read_bytes()
    file_digest = hashlib.sha256(file_bytes).hexdigest()
    aggregated_digest = hashlib.sha256(file_digest.encode("ascii")).hexdigest()
    if aggregated_digest != record.sha256_hex:
        raise err(
            f"{error_prefix}_DIGEST",
            f"policy '{asset_id}' digest mismatch: expected {record.sha256_hex}, observed {aggregated_digest}",
        )
    determinism_digest = payload.get("sha256_hex")
    if determinism_digest and determinism_digest != file_digest:
        raise err(
            f"{error_prefix}_DIGEST",
            f"policy '{asset_id}' embedded digest mismatch",
        )
    return payload, aggregated_digest, file_digest, policy_path


__all__ = ["load_policy_asset", "resolve_catalog_path"]
