"""Contract source resolution (model_spec vs contracts mirror)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.core.errors import ContractError


@dataclass(frozen=True)
class ContractSource:
    root: Path
    layout: str

    def _model_spec_root(self) -> Path:
        return self.root / "docs" / "model_spec" / "data-engine"

    def _contracts_root(self) -> Path:
        return self.root / "contracts"

    def _layer_for_segment(self, segment: str) -> str:
        if not segment:
            raise ContractError("Segment is required for contract resolution.")
        prefix = str(segment).strip()
        if not prefix:
            raise ContractError("Segment is required for contract resolution.")
        if prefix[0] in {"1", "2", "3", "4"}:
            return "layer-1"
        if prefix[0] == "5":
            return "layer-2"
        if prefix[0] == "6":
            return "layer-3"
        raise ContractError(f"Unknown segment for contract resolution: {segment}")

    def _layer_tag(self, layer: str) -> str:
        return layer.replace("-", "")

    def resolve_dataset_dictionary(self, segment: str) -> Path:
        layer = self._layer_for_segment(segment)
        layer_tag = self._layer_tag(layer)
        if self.layout == "model_spec":
            return (
                self._model_spec_root()
                / layer
                / "specs"
                / "contracts"
                / segment
                / f"dataset_dictionary.{layer_tag}.{segment}.yaml"
            )
        if self.layout == "contracts":
            return (
                self._contracts_root()
                / "dataset_dictionary"
                / layer_tag.replace("layer", "l")
                / f"seg_{segment}"
                / f"{layer_tag}.{segment}.yaml"
            )
        raise ContractError(f"Unknown contracts layout: {self.layout}")

    def resolve_artefact_registry(self, segment: str) -> Path:
        if self.layout == "model_spec":
            return (
                self._model_spec_root()
                / self._layer_for_segment(segment)
                / "specs"
                / "contracts"
                / segment
                / f"artefact_registry_{segment}.yaml"
            )
        if self.layout == "contracts":
            return self._contracts_root() / "artefact_registry" / f"artefact_registry_{segment}.yaml"
        raise ContractError(f"Unknown contracts layout: {self.layout}")

    def resolve_schema_pack(self, segment: str, kind: str) -> Path:
        layer = self._layer_for_segment(segment)
        if self.layout == "model_spec":
            return (
                self._model_spec_root()
                / layer
                / "specs"
                / "contracts"
                / segment
                / f"schemas.{kind}.yaml"
            )
        if self.layout == "contracts":
            layer_tag = self._layer_tag(layer)
            return self._contracts_root() / "schemas" / layer_tag / f"schemas.{kind}.yaml"
        raise ContractError(f"Unknown contracts layout: {self.layout}")
