"""Utilities for working with S0 sealed_inputs in Segment 2A."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

from engine.layers.l1.seg_2A.s0_gate.exceptions import S0GateError, err
from engine.layers.l1.seg_2A.s0_gate.l0.filesystem import (
    aggregate_sha256,
    expand_files,
    hash_files,
)

from .receipt import SealedInputRecord, load_sealed_inputs_inventory


def build_sealed_asset_map(
    *,
    base_path: Path,
    manifest_fingerprint: str,
    dictionary: Mapping[str, object],
) -> Mapping[str, SealedInputRecord]:
    """Load sealed_inputs_v1 and index it by asset_id."""

    records = load_sealed_inputs_inventory(
        base_path=base_path,
        manifest_fingerprint=manifest_fingerprint,
        dictionary=dictionary,
    )
    return {record.asset_id: record for record in records}


def require_sealed_asset(
    *,
    asset_id: str,
    sealed_assets: Mapping[str, SealedInputRecord],
    code: str,
) -> SealedInputRecord:
    """Fetch a sealed asset row or raise using the provided canonical code."""

    record = sealed_assets.get(asset_id)
    if record is None:
        raise err(
            code,
            f"sealed asset '{asset_id}' missing from sealed_inputs_v1",
        )
    return record


def ensure_catalog_path(
    *,
    asset_id: str,
    record: SealedInputRecord,
    expected_relative_path: str,
    code: str,
) -> None:
    """Ensure the sealed record path matches the dictionary-rendered relative path."""

    normalized_expected = expected_relative_path.strip("/\\")
    normalized_record = record.catalog_path.strip("/\\")
    if normalized_expected != normalized_record:
        raise err(
            code,
            (
                f"sealed asset '{asset_id}' path mismatch "
                f"(sealed='{record.catalog_path}', expected='{expected_relative_path}')"
            ),
        )


def resolve_sealed_path(*, base_path: Path, record: SealedInputRecord, code: str) -> Path:
    """Resolve a sealed asset catalogue path under the provided base path."""

    candidate = (base_path / record.catalog_path).resolve()
    if not candidate.exists():
        raise err(
            code,
            f"sealed asset '{record.asset_id}' not found at '{candidate}'",
        )
    return candidate


def verify_sealed_digest(
    *,
    asset_id: str,
    path: Path,
    expected_hex: str,
    code: str,
) -> str:
    """Validate that the on-disk asset matches the sealed aggregated digest."""

    try:
        files = expand_files(path)
        digests = hash_files(files, error_prefix=code)
        aggregate = aggregate_sha256(digests)
    except S0GateError as exc:
        raise err(code, f"unable to hash sealed asset '{asset_id}': {exc}") from exc

    if aggregate.lower() != expected_hex.lower():
        raise err(
            code,
            (
                f"sealed asset '{asset_id}' digest mismatch "
                f"(expected={expected_hex}, observed={aggregate})"
            ),
        )
    return aggregate


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
    except FileNotFoundError:
        return ""
    return digest.hexdigest()


__all__ = [
    "build_sealed_asset_map",
    "ensure_catalog_path",
    "require_sealed_asset",
    "resolve_sealed_path",
    "verify_sealed_digest",
]
