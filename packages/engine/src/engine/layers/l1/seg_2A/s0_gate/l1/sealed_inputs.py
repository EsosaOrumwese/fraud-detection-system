"""Dataclasses describing sealed inputs for Segment 2A S0."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ..exceptions import err
from ..l0 import ArtifactDigest
from ..l0.filesystem import aggregate_sha256, total_size_bytes


@dataclass(frozen=True)
class SealedAsset:
    """Represents a single asset sealed into the 2A manifest."""

    asset_id: str
    schema_ref: str
    asset_kind: str
    catalog_path: str
    resolved_path: Path
    partition_keys: tuple[str, ...]
    version_tag: str
    license_class: str
    digests: tuple[ArtifactDigest, ...]
    notes: str | None = None
    sha256_hex: str = field(init=False)
    size_bytes: int = field(init=False)

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise err("E_ASSET_ID_MISSING", "sealed asset must declare a non-empty id")
        if not self.schema_ref:
            raise err("E_ASSET_SCHEMA_MISSING", f"sealed asset '{self.asset_id}' missing schema_ref")
        if not self.digests:
            raise err(
                "E_ASSET_EMPTY_DIGESTS",
                f"sealed asset '{self.asset_id}' has no hashed artefacts",
            )
        object.__setattr__(self, "sha256_hex", aggregate_sha256(self.digests))
        object.__setattr__(self, "size_bytes", total_size_bytes(self.digests))

    def as_receipt_entry(self) -> dict[str, object]:
        """Representation suitable for embedding in the receipt."""

        return {
            "id": self.asset_id,
            "partition": list(self.partition_keys),
            "schema_ref": self.schema_ref,
        }

    def as_inventory_row(self, *, manifest_fingerprint: str) -> dict[str, object]:
        """Row payload for the sealed_inputs_v1 manifest."""

        return {
            "manifest_fingerprint": manifest_fingerprint,
            "asset_id": self.asset_id,
            "asset_kind": self.asset_kind,
            "basename": self.resolved_path.name,
            "version_tag": self.version_tag,
            "schema_ref": self.schema_ref,
            "catalog_path": self.catalog_path,
            "partition_keys": list(self.partition_keys),
            "sha256_hex": self.sha256_hex,
            "size_bytes": self.size_bytes,
            "license_class": self.license_class,
            "notes": self.notes,
        }


def ensure_unique_assets(assets: Iterable[SealedAsset]) -> list[SealedAsset]:
    """Ensure asset identifiers are unique."""

    seen: set[str] = set()
    normalised: list[SealedAsset] = []
    for asset in assets:
        if asset.asset_id in seen:
            raise err(
                "E_ASSET_DUPLICATE",
                f"duplicate sealed asset '{asset.asset_id}' encountered",
            )
        seen.add(asset.asset_id)
        normalised.append(asset)
    return normalised


__all__ = ["SealedAsset", "ensure_unique_assets"]
