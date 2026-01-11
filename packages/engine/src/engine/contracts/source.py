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

    def resolve_dataset_dictionary(self, segment: str) -> Path:
        if self.layout == "model_spec":
            return (
                self._model_spec_root()
                / "layer-1"
                / "specs"
                / "contracts"
                / segment
                / f"dataset_dictionary.layer1.{segment}.yaml"
            )
        if self.layout == "contracts":
            return (
                self._contracts_root()
                / "dataset_dictionary"
                / "l1"
                / f"seg_{segment}"
                / f"layer1.{segment}.yaml"
            )
        raise ContractError(f"Unknown contracts layout: {self.layout}")

    def resolve_artefact_registry(self, segment: str) -> Path:
        if self.layout == "model_spec":
            return (
                self._model_spec_root()
                / "layer-1"
                / "specs"
                / "contracts"
                / segment
                / f"artefact_registry_{segment}.yaml"
            )
        if self.layout == "contracts":
            return self._contracts_root() / "artefact_registry" / f"artefact_registry_{segment}.yaml"
        raise ContractError(f"Unknown contracts layout: {self.layout}")

    def resolve_schema_pack(self, segment: str, kind: str) -> Path:
        if self.layout == "model_spec":
            return (
                self._model_spec_root()
                / "layer-1"
                / "specs"
                / "contracts"
                / segment
                / f"schemas.{kind}.yaml"
            )
        if self.layout == "contracts":
            return self._contracts_root() / "schemas" / "layer1" / f"schemas.{kind}.yaml"
        raise ContractError(f"Unknown contracts layout: {self.layout}")
