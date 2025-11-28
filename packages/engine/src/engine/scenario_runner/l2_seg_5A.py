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
    run_s1: bool = True
    run_s2: bool = True
    run_s3: bool = True


@dataclass(frozen=True)
class Segment5AResult:
    """Structured result for Segment 5A runs."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_inputs_digest: str
    run_report_path: Path
    s1_profile_path: Path | None = None
    s1_class_profile_path: Path | None = None
    s1_run_report_path: Path | None = None
    s1_resumed: bool = False
    s2_grid_path: Path | None = None
    s2_shape_path: Path | None = None
    s2_catalogue_path: Path | None = None
    s2_run_report_path: Path | None = None
    s2_resumed: bool = False
    s3_baseline_path: Path | None = None
    s3_class_baseline_path: Path | None = None
    s3_run_report_path: Path | None = None
    s3_resumed: bool = False


class Segment5AOrchestrator:
    """Runs Segment 5A S0."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()

    def run(self, config: Segment5AConfig) -> Segment5AResult:
        # Ensure dictionary loads early for validation
        load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().absolute()

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

        s1_profile_path = None
        s1_class_profile_path = None
        s1_run_report_path = None
        s1_resumed = False
        s2_grid_path = None
        s2_shape_path = None
        s2_catalogue_path = None
        s2_run_report_path = None
        s2_resumed = False
        s3_baseline_path = None
        s3_class_baseline_path = None
        s3_run_report_path = None
        s3_resumed = False

        if config.run_s1:
            logger.info("Segment5A S1 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            from engine.layers.l2.seg_5A.s1_profiles.runner import ProfilesInputs, ProfilesRunner  # lazy import

            s1_inputs = ProfilesInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s1_result = ProfilesRunner().run(s1_inputs)
            logger.info("Segment5A S1 completed (profiles=%s)", s1_result.profile_path)
            s1_profile_path = s1_result.profile_path
            s1_class_profile_path = s1_result.class_profile_path
            s1_run_report_path = s1_result.run_report_path
            s1_resumed = s1_result.resumed

        if config.run_s2:
            logger.info("Segment5A S2 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            from engine.layers.l2.seg_5A.s2_shapes.runner import ShapesInputs, ShapesRunner  # lazy import

            s2_inputs = ShapesInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s2_result = ShapesRunner().run(s2_inputs)
            logger.info("Segment5A S2 completed (shapes=%s)", s2_result.shape_path)
            s2_grid_path = s2_result.grid_path
            s2_shape_path = s2_result.shape_path
            s2_catalogue_path = s2_result.catalogue_path
            s2_run_report_path = s2_result.run_report_path
            s2_resumed = s2_result.resumed

        if config.run_s3 and config.run_s1 and config.run_s2:
            logger.info("Segment5A S3 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            from engine.layers.l2.seg_5A.s3_baselines.runner import BaselineInputs, BaselineRunner  # lazy import

            s3_inputs = BaselineInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s3_result = BaselineRunner().run(s3_inputs)
            logger.info("Segment5A S3 completed (baseline=%s)", s3_result.baseline_path)
            s3_baseline_path = s3_result.baseline_path
            s3_class_baseline_path = s3_result.class_baseline_path
            s3_run_report_path = s3_result.run_report_path
            s3_resumed = s3_result.resumed

        return Segment5AResult(
            manifest_fingerprint=s0_outputs.manifest_fingerprint,
            parameter_hash=s0_outputs.parameter_hash,
            receipt_path=s0_outputs.receipt_path,
            sealed_inputs_path=s0_outputs.sealed_inputs_path,
            sealed_inputs_digest=s0_outputs.sealed_inputs_digest,
            run_report_path=s0_outputs.run_report_path,
            s1_profile_path=s1_profile_path,
            s1_class_profile_path=s1_class_profile_path,
            s1_run_report_path=s1_run_report_path,
            s1_resumed=s1_resumed,
            s2_grid_path=s2_grid_path,
            s2_shape_path=s2_shape_path,
            s2_catalogue_path=s2_catalogue_path,
            s2_run_report_path=s2_run_report_path,
            s2_resumed=s2_resumed,
            s3_baseline_path=s3_baseline_path,
            s3_class_baseline_path=s3_class_baseline_path,
            s3_run_report_path=s3_run_report_path,
            s3_resumed=s3_resumed,
        )


__all__ = ["Segment5AConfig", "Segment5AResult", "Segment5AOrchestrator"]
