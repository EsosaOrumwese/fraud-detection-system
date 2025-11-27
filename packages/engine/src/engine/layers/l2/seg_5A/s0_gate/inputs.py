"""Dataclasses describing sealed inputs for Segment 5A S0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from engine.layers.l1.seg_3A.s0_gate.l0 import ArtifactDigest, aggregate_sha256, total_size_bytes


class S0InputError(RuntimeError):
    """Raised when sealed input rows are invalid."""


@dataclass(frozen=True)
class SealedArtefact:
    """Represents a single artefact sealed into the 5A manifest."""

    manifest_fingerprint: str
    parameter_hash: str
    owner_layer: str
    owner_segment: str
    artifact_id: str
    manifest_key: str
    role: str
    schema_ref: str
    path_template: str
    partition_keys: tuple[str, ...]
    version: str
    digests: tuple[ArtifactDigest, ...]
    source_dictionary: str
    source_registry: str
    status: str = "REQUIRED"
    read_scope: str = "METADATA_ONLY"
    notes: str | None = None
    license_class: str | None = None
    owner_team: str | None = None

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise S0InputError("sealed artefact must have an artifact_id")
        if not self.schema_ref:
            raise S0InputError(f"{self.artifact_id} missing schema_ref")
        if not self.digests:
            raise S0InputError(f"{self.artifact_id} has no digests")

    @property
    def sha256_hex(self) -> str:
        return aggregate_sha256(self.digests)

    @property
    def size_bytes(self) -> int:
        return total_size_bytes(self.digests)

    def as_row(self) -> dict[str, object]:
        return {
            "manifest_fingerprint": self.manifest_fingerprint,
            "parameter_hash": self.parameter_hash,
            "owner_layer": self.owner_layer,
            "owner_segment": self.owner_segment,
            "artifact_id": self.artifact_id,
            "manifest_key": self.manifest_key,
            "role": self.role,
            "schema_ref": self.schema_ref,
            "path_template": self.path_template,
            "partition_keys": list(self.partition_keys),
            "sha256_hex": self.sha256_hex,
            "version": self.version,
            "source_dictionary": self.source_dictionary,
            "source_registry": self.source_registry,
            "status": self.status,
            "read_scope": self.read_scope,
            "notes": self.notes or "",
            "license_class": self.license_class or "",
            "owner_team": self.owner_team or "",
        }


def ensure_unique_assets(assets: Iterable[SealedArtefact]) -> list[SealedArtefact]:
    seen: set[tuple[str, str]] = set()
    out: list[SealedArtefact] = []
    for asset in assets:
        key = (asset.owner_segment, asset.artifact_id)
        if key in seen:
            raise S0InputError(f"duplicate sealed artefact '{asset.artifact_id}' for segment {asset.owner_segment}")
        seen.add(key)
        out.append(asset)
    return out


__all__ = ["SealedArtefact", "ensure_unique_assets", "S0InputError"]
