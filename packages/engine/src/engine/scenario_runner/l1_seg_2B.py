"""Scenario runner for Segment 2B (S0 gate)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.layers.l1.seg_2B import (
    S0GateInputs,
    S0GateRunner,
    S0GateOutputs,
    S1WeightsInputs,
    S1WeightsRunner,
    S1WeightsResult,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment2BConfig:
    """User-supplied configuration for running Segment 2B S0."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    parameter_hash: str
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_path: Optional[Path] = None
    notes: Optional[str] = None
    pin_civil_time: bool = False
    run_s1: bool = False
    s1_resume: bool = False


@dataclass(frozen=True)
class Segment2BResult:
    """Structured result for Segment 2B S0 runs."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    inventory_path: Path
    flag_sha256_hex: str
    verified_at_utc: str
    s1_output_path: Optional[Path] = None
    s1_run_report_path: Optional[Path] = None
    s1_resumed: bool = False


class Segment2BOrchestrator:
    """Runs Segment 2B S0 gate."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = S1WeightsRunner()

    def run(self, config: Segment2BConfig) -> Segment2BResult:
        data_root = config.data_root.expanduser().resolve()
        gate_inputs = S0GateInputs(
            data_root=data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            git_commit_hex=config.git_commit_hex,
            dictionary_path=config.dictionary_path,
            validation_bundle_path=config.validation_bundle_path,
            notes=config.notes,
            pin_civil_time=config.pin_civil_time,
        )
        gate_output: S0GateOutputs = self._s0_runner.run(gate_inputs)
        s1_result: S1WeightsResult | None = None
        if config.run_s1:
            s1_inputs = S1WeightsInputs(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=gate_output.manifest_fingerprint,
                dictionary_path=config.dictionary_path,
                resume=config.s1_resume,
            )
            s1_result = self._s1_runner.run(s1_inputs)
        return Segment2BResult(
            manifest_fingerprint=gate_output.manifest_fingerprint,
            parameter_hash=gate_output.parameter_hash,
            receipt_path=gate_output.receipt_path,
            inventory_path=gate_output.inventory_path,
            flag_sha256_hex=gate_output.flag_sha256_hex,
            verified_at_utc=gate_output.verified_at_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            s1_output_path=s1_result.output_path if s1_result else None,
            s1_run_report_path=s1_result.run_report_path if s1_result else None,
            s1_resumed=s1_result.resumed if s1_result else False,
        )


__all__ = ["Segment2BConfig", "Segment2BOrchestrator", "Segment2BResult"]
