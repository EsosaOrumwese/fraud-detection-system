"""Scenario runner for Segment 1B (S0 → S2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from engine.layers.l1.seg_1B import (
    GateInputs,
    S0GateRunner,
    S1RunnerConfig,
    S1RunResult,
    S1TileIndexRunner,
    S2RunnerConfig,
    S2RunResult,
    S2TileWeightsRunner,
)
from engine.layers.l1.seg_1B.shared.dictionary import load_dictionary


@dataclass(frozen=True)
class Segment1BConfig:
    """User-supplied configuration for running Segment 1B."""

    data_root: Path
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None
    basis: str = "uniform"
    dp: int = 2
    manifest_fingerprint: Optional[str] = None
    seed: Optional[str] = None
    notes: Optional[str] = None
    validation_bundle_path: Optional[Path] = None
    skip_s0: bool = False


@dataclass(frozen=True)
class Segment1BResult:
    """Structured result capturing outputs from S0–S2."""

    s0_receipt_path: Optional[Path]
    s1: S1RunResult
    s2: S2RunResult


class Segment1BOrchestrator:
    """Runs Segment 1B states sequentially."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = S1TileIndexRunner()
        self._s2_runner = S2TileWeightsRunner()

    def run(self, config: Segment1BConfig) -> Segment1BResult:
        dictionary = config.dictionary or load_dictionary()
        data_root = config.data_root.expanduser().resolve()

        receipt_path: Optional[Path] = None
        if not config.skip_s0:
            if not config.manifest_fingerprint or config.seed is None:
                raise ValueError("manifest_fingerprint and seed must be provided when S0 is executed")
            gate_inputs = GateInputs(
                base_path=data_root,
                output_base_path=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                notes=config.notes,
                dictionary=dictionary,
                validation_bundle_path=config.validation_bundle_path,
            )
            gate_result = self._s0_runner.run(gate_inputs)
            receipt_path = gate_result.receipt_path

        s1_result = self._s1_runner.run(
            S1RunnerConfig(
                data_root=data_root,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
            )
        )

        prepared = self._s2_runner.prepare(
            S2RunnerConfig(
                data_root=data_root,
                parameter_hash=config.parameter_hash,
                basis=config.basis,
                dp=config.dp,
                dictionary=dictionary,
            )
        )
        masses = self._s2_runner.compute_masses(prepared)
        self._s2_runner.measure_baselines(
            prepared,
            measure_raster=prepared.governed.basis == "population",
        )
        quantised = self._s2_runner.quantise(prepared, masses)
        s2_result = self._s2_runner.materialise(prepared, quantised)

        return Segment1BResult(
            s0_receipt_path=receipt_path,
            s1=s1_result,
            s2=s2_result,
        )


__all__ = ["Segment1BConfig", "Segment1BOrchestrator", "Segment1BResult"]

