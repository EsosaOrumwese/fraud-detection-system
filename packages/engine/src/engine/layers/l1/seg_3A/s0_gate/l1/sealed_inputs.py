"""Dataclasses describing sealed inputs for Segment 3A S0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..exceptions import err
from ..l0 import ArtifactDigest, aggregate_sha256, total_size_bytes


@dataclass(frozen=True)
class SealedArtefact:
    """Represents a single artefact sealed into the 3A manifest."""

    owner_segment: str
    artefact_kind: str
    logical_id: str
    path: Path
    schema_ref: str
    role: str
    license_class: str
    digests: tuple[ArtifactDigest, ...]
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.logical_id:
            raise err("E_ASSET_ID_EMPTY", "sealed artefact must have a logical_id")
        if not self.schema_ref:
            raise err("E_ASSET_SCHEMA_EMPTY", f"{self.logical_id} missing schema_ref")
        if not self.digests:
            raise err("E_ASSET_DIGEST_EMPTY", f"{self.logical_id} has no digests")

    @property
    def sha256_hex(self) -> str:
        return aggregate_sha256(self.digests)

    @property
    def size_bytes(self) -> int:
        return total_size_bytes(self.digests)

    def as_row(self, manifest_fingerprint: str) -> dict[str, object]:
        """Row payload for sealed_inputs_3A parquet."""

        return {
            "manifest_fingerprint": manifest_fingerprint,
            "owner_segment": self.owner_segment,
            "artefact_kind": self.artefact_kind,
            "logical_id": self.logical_id,
            "path": str(self.path),
            "schema_ref": self.schema_ref,
            "sha256_hex": self.sha256_hex,
            "role": self.role,
            "license_class": self.license_class,
            "notes": self.notes or "",
        }


def ensure_unique_assets(assets: Iterable[SealedArtefact]) -> list[SealedArtefact]:
    """Ensure artefact logical_ids are unique."""

    seen: set[str] = set()
    out: list[SealedArtefact] = []
    for asset in assets:
        if asset.logical_id in seen:
            raise err("E_ASSET_DUPLICATE", f"duplicate sealed artefact '{asset.logical_id}'")
        seen.add(asset.logical_id)
        out.append(asset)
    return out


__all__ = ["SealedArtefact", "ensure_unique_assets"]
