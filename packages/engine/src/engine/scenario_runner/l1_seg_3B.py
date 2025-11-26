"""Scenario runner for Segment 3B (S0 gate + S1 virtuals)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.layers.l1.seg_3B import (
    S0GateInputs,
    S0GateRunner,
    VirtualsInputs,
    VirtualsResult,
    VirtualsRunner,
)
from engine.layers.l1.seg_3B.shared.dictionary import load_dictionary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment3BConfig:
    """User configuration for running Segment 3B."""

    data_root: Path
    upstream_manifest_fingerprint: str
    seed: int
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_1a: Optional[Path] = None
    validation_bundle_1b: Optional[Path] = None
    validation_bundle_2a: Optional[Path] = None
    validation_bundle_3a: Optional[Path] = None
    notes: Optional[str] = None
    resume: bool = False
    run_s1: bool = True


@dataclass(frozen=True)
class Segment3BResult:
    """Structured result for Segment 3B runs."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    run_report_path: Path
    resumed: bool
    s1_output_path: Path | None = None
    s1_run_report_path: Path | None = None
    s1_resumed: bool = False


class Segment3BOrchestrator:
    """Runs Segment 3B S0 and S1 sequentially."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = VirtualsRunner()

    def run(self, config: Segment3BConfig) -> Segment3BResult:
        dictionary = load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()

        s0_inputs = S0GateInputs(
            base_path=data_root,
            output_base_path=data_root,
            seed=config.seed,
            upstream_manifest_fingerprint=config.upstream_manifest_fingerprint,
            git_commit_hex=config.git_commit_hex,
            dictionary_path=config.dictionary_path,
            validation_bundle_1a=config.validation_bundle_1a,
            validation_bundle_1b=config.validation_bundle_1b,
            validation_bundle_2a=config.validation_bundle_2a,
            validation_bundle_3a=config.validation_bundle_3a,
            notes=config.notes,
        )
        s0_outputs = self._s0_runner.run(s0_inputs)

        s1_output_path: Path | None = None
        s1_run_report: Path | None = None
        s1_resumed = False
        if config.run_s1:
            s1_inputs = VirtualsInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                seed=int(config.seed),
                dictionary_path=config.dictionary_path,
            )
            s1_result: VirtualsResult = self._s1_runner.run(s1_inputs)
            s1_output_path = s1_result.classification_path
            s1_run_report = s1_result.run_report_path
            s1_resumed = s1_result.resumed

        return Segment3BResult(
            manifest_fingerprint=s0_outputs.manifest_fingerprint,
            parameter_hash=s0_outputs.parameter_hash,
            receipt_path=s0_outputs.receipt_path,
            sealed_inputs_path=s0_outputs.sealed_inputs_path,
            run_report_path=s0_outputs.run_report_path,
            resumed=False,
            s1_output_path=s1_output_path,
            s1_run_report_path=s1_run_report,
            s1_resumed=s1_resumed,
        )
