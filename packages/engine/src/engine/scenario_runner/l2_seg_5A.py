"""Scenario runner for Segment 5A (S0 gate)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.layers.l2.seg_5A import S0GateRunner, S0Inputs, S0Outputs
from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment5AConfig:
    """User configuration for running Segment 5A."""

    data_root: Path
    upstream_manifest_fingerprint: str
    parameter_hash: str
    run_id: str
    dictionary_path: Optional[Path] = None
    validation_bundle_1a: Optional[Path] = None
    validation_bundle_1b: Optional[Path] = None
    validation_bundle_2a: Optional[Path] = None
    validation_bundle_2b: Optional[Path] = None
    validation_bundle_3a: Optional[Path] = None
    validation_bundle_3b: Optional[Path] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class Segment5AResult:
    """Structured result for Segment 5A runs."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_inputs_digest: str
    run_report_path: Path


class Segment5AOrchestrator:
    """Runs Segment 5A S0."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()

    def run(self, config: Segment5AConfig) -> Segment5AResult:
        # Ensure dictionary loads early for validation
        load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()

        logger.info(
            "Segment5A S0 orchestrator invoked (upstream_manifest=%s, parameter_hash=%s)",
            config.upstream_manifest_fingerprint,
            config.parameter_hash,
        )
        s0_inputs = S0Inputs(
            base_path=data_root,
            output_base_path=data_root,
            upstream_manifest_fingerprint=config.upstream_manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            run_id=config.run_id,
            dictionary_path=config.dictionary_path,
            validation_bundle_1a=config.validation_bundle_1a,
            validation_bundle_1b=config.validation_bundle_1b,
            validation_bundle_2a=config.validation_bundle_2a,
            validation_bundle_2b=config.validation_bundle_2b,
            validation_bundle_3a=config.validation_bundle_3a,
            validation_bundle_3b=config.validation_bundle_3b,
            notes=config.notes,
        )
        logger.info("Segment5A S0 starting (upstream_manifest=%s)", config.upstream_manifest_fingerprint)
        s0_outputs: S0Outputs = self._s0_runner.run(s0_inputs)
        logger.info("Segment5A S0 completed (manifest=%s)", s0_outputs.manifest_fingerprint)

        return Segment5AResult(
            manifest_fingerprint=s0_outputs.manifest_fingerprint,
            parameter_hash=s0_outputs.parameter_hash,
            receipt_path=s0_outputs.receipt_path,
            sealed_inputs_path=s0_outputs.sealed_inputs_path,
            sealed_inputs_digest=s0_outputs.sealed_inputs_digest,
            run_report_path=s0_outputs.run_report_path,
        )


__all__ = ["Segment5AConfig", "Segment5AResult", "Segment5AOrchestrator"]
