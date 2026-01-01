"""Dataclasses describing sealed inputs for Segment 2B S0."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from ..exceptions import err
from ..l0 import ArtifactDigest, aggregate_sha256, total_size_bytes


@dataclass(frozen=True)
class SealedAsset:
    """Represents a single asset sealed into the 2B manifest."""

    asset_id: str
    schema_ref: str
    catalog_path: str
    resolved_path: Path
    partition: Mapping[str, str]
    version_tag: str
    digests: tuple[ArtifactDigest, ...]
    notes: str | None = None
    sha256_hex: str = field(init=False)
    size_bytes: int = field(init=False)

    def __post_init__(self) -> None:
        if not self.asset_id:
            raise err("E_ASSET_ID_MISSING", "sealed asset must declare a non-empty id")
        if not self.schema_ref:
            raise err(
                "E_ASSET_SCHEMA_MISSING",
                f"sealed asset '{self.asset_id}' missing schema_ref",
            )
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
            "partition": dict(self.partition),
            "schema_ref": self.schema_ref,
        }

    def as_inventory_row(self) -> dict[str, object]:
        """Row payload for the sealed_inputs_v1 inventory."""

        return {
            "asset_id": self.asset_id,
            "version_tag": self.version_tag,
            "sha256_hex": self.sha256_hex,
            "path": self.catalog_path,
            "partition": dict(self.partition),
            "schema_ref": self.schema_ref,
        }


def ensure_unique_assets(assets: Iterable[SealedAsset]) -> list[SealedAsset]:
    """Ensure asset identifiers are unique."""

    seen: set[str] = set()
    ordered: list[SealedAsset] = []
    for asset in assets:
        if asset.asset_id in seen:
            raise err(
                "E_ASSET_DUPLICATE",
                f"duplicate sealed asset '{asset.asset_id}' encountered",
            )
        seen.add(asset.asset_id)
        ordered.append(asset)
    return ordered


__all__ = ["SealedAsset", "ensure_unique_assets"]
