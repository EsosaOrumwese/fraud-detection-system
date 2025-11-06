"""High-level orchestration skeleton for Segment 2A S0 gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Optional

import polars as pl

from ..exceptions import S0GateError, err
from ..l1.sealed_inputs import SealedInput, normalise_inputs


@dataclass(frozen=True)
class GateInputs:
    """Configuration required to execute the 2A S0 gate."""

    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    dictionary_path: Optional[Path] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class SealedInputsInventory:
    """Placeholder for the payload that will back ``sealed_inputs_v1``."""

    manifest_fingerprint: str
    rows: pl.DataFrame


@dataclass(frozen=True)
class GateOutputs:
    """Result bundle emitted by :class:`S0GateRunner`."""

    receipt_path: Path
    inventory_path: Path
    sealed_inputs: tuple[SealedInput, ...]
    verified_at_utc: datetime


class S0GateRunner:
    """Skeleton orchestrator wiring together S0 phases.

    The concrete implementation will be delivered across later phases.  The
    class exists now so that orchestration code can depend on a stable import
    surface while we incrementally fill in behaviour.
    """

    def __init__(self) -> None:
        self._sealed_inputs: list[SealedInput] = []

    def register_asset(self, asset: SealedInput) -> None:
        """Record a sealed asset definition.

        This helper allows tests and higher layers to describe the assets that
        need to be sealed without yet performing I/O.
        """

        self._sealed_inputs.append(asset)

    def build_receipt_payload(self, inputs: GateInputs) -> Mapping[str, object]:
        """Assemble the JSON-ready payload for ``s0_gate_receipt_2A``.

        For now we only enforce structural expectations; later phases will add
        manifest hashing, dictionary resolution, and bundle verification.
        """

        sealed = normalise_inputs(self._sealed_inputs)
        payload = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "validation_bundle_path": "",  # to be populated in phase 2
            "flag_sha256_hex": "",
            "verified_at_utc": datetime.utcnow().isoformat(timespec="microseconds") + "Z",
            "sealed_inputs": [
                {
                    "id": item.asset_id,
                    "partition": list(item.partition_keys),
                    "schema_ref": item.schema_ref,
                }
                for item in sealed
            ],
            "notes": inputs.notes,
        }
        return payload

    def run(self, inputs: GateInputs) -> GateOutputs:
        """Execute the gate (placeholder implementation).

        The method returns stubbed paths so that orchestration wiring can be
        validated without touching the filesystem yet.
        """

        payload = self.build_receipt_payload(inputs)
        if not payload["manifest_fingerprint"]:
            raise err("E_MANIFEST_EMPTY", "manifest fingerprint must be provided for S0")

        # Future phases will persist the payload and inventory; the skeleton
        # returns descriptive dummy paths so callers can log intent.
        dummy_root = Path("data/layer1/2A/s0_gate_receipt") / f"fingerprint={inputs.manifest_fingerprint}"
        receipt_path = dummy_root / "s0_gate_receipt.json"
        inventory_path = (
            Path("data/layer1/2A/sealed_inputs")
            / f"fingerprint={inputs.manifest_fingerprint}"
            / "sealed_inputs_v1.parquet"
        )

        sealed = tuple(normalise_inputs(self._sealed_inputs))
        verified_at = datetime.utcnow()

        return GateOutputs(
            receipt_path=receipt_path,
            inventory_path=inventory_path,
            sealed_inputs=sealed,
            verified_at_utc=verified_at,
        )


__all__ = [
    "GateInputs",
    "GateOutputs",
    "SealedInput",
    "SealedInputsInventory",
    "S0GateRunner",
    "S0GateError",
]
