"""Utilities for working with sealed assets in Segment 2B."""

from __future__ import annotations

from pathlib import Path

from engine.layers.l1.seg_2B.s0_gate.exceptions import err
from engine.layers.l1.seg_2B.s0_gate.l0.filesystem import (
    aggregate_sha256,
    expand_files,
    hash_files,
)


def verify_sealed_digest(
    *,
    asset_id: str,
    path: Path,
    expected_hex: str,
    code: str,
) -> str:
    """Validate that ``path`` matches the aggregated digest recorded by S0."""

    if not expected_hex:
        return ""
    files = expand_files(path)
    digests = hash_files(files, error_prefix=code)
    aggregate = aggregate_sha256(digests)
    if aggregate.lower() != expected_hex.lower():
        raise err(
            code,
            (
                f"sealed asset '{asset_id}' digest mismatch "
                f"(expected {expected_hex}, observed {aggregate})"
            ),
        )
    return aggregate


__all__ = ["verify_sealed_digest"]

