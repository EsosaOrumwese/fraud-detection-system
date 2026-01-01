"""Scenario runner for Segment 5B (S0 gate through S5 validation)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.layers.l2.seg_5B import (
    ArrivalInputs,
    ArrivalRunner,
    CountInputs,
    CountRunner,
    IntensityInputs,
    IntensityRunner,
    S0GateRunner,
    S0Inputs,
    S0Outputs,
    TimeGridInputs,
    TimeGridRunner,
    ValidationInputs,
    ValidationRunner,
)
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment5BConfig:
    """User configuration for running Segment 5B."""

    data_root: Path
    upstream_manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Optional[Path] = None
    validation_bundle_1a: Optional[Path] = None
    validation_bundle_1b: Optional[Path] = None
    validation_bundle_2a: Optional[Path] = None
    validation_bundle_2b: Optional[Path] = None
    validation_bundle_3a: Optional[Path] = None
    validation_bundle_3b: Optional[Path] = None
    validation_bundle_5a: Optional[Path] = None
    run_s1: bool = True
    run_s2: bool = True
    run_s3: bool = True
    run_s4: bool = True
    run_s5: bool = True


@dataclass(frozen=True)
class Segment5BResult:
    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_inputs_digest: str
    run_report_path: Path
    s1_time_grid_paths: dict[str, Path]
    s1_grouping_paths: dict[str, Path]
    s2_intensity_paths: dict[str, Path]
    s2_latent_paths: dict[str, Path]
    s3_count_paths: dict[str, Path]
    s4_arrival_paths: dict[str, Path]
    s4_summary_paths: dict[str, Path]
    s5_bundle_index_path: Path | None
    s5_report_path: Path | None
    s5_issue_table_path: Path | None
    s5_passed_flag_path: Path | None
    s5_run_report_path: Path | None
    s5_overall_status: str | None


class Segment5BOrchestrator:
    """Runs Segment 5B S0-S5."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()

    def run(self, config: Segment5BConfig) -> Segment5BResult:
        load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().absolute()

        logger.info(
            "Segment5B S0 orchestrator invoked (upstream_manifest=%s, parameter_hash=%s)",
            config.upstream_manifest_fingerprint,
            config.parameter_hash,
        )
        s0_inputs = S0Inputs(
            base_path=data_root,
            output_base_path=data_root,
            upstream_manifest_fingerprint=config.upstream_manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            seed=config.seed,
            run_id=config.run_id,
            dictionary_path=config.dictionary_path,
            validation_bundle_1a=config.validation_bundle_1a,
            validation_bundle_1b=config.validation_bundle_1b,
            validation_bundle_2a=config.validation_bundle_2a,
            validation_bundle_2b=config.validation_bundle_2b,
            validation_bundle_3a=config.validation_bundle_3a,
            validation_bundle_3b=config.validation_bundle_3b,
            validation_bundle_5a=config.validation_bundle_5a,
        )
        logger.info("Segment5B S0 starting (manifest=%s)", config.upstream_manifest_fingerprint)
        s0_outputs: S0Outputs = self._s0_runner.run(s0_inputs)
        logger.info("Segment5B S0 completed (manifest=%s)", s0_outputs.manifest_fingerprint)

        s1_time_grid_paths: dict[str, Path] = {}
        s1_grouping_paths: dict[str, Path] = {}
        if config.run_s1:
            logger.info("Segment5B S1 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s1_inputs = TimeGridInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s1_result = TimeGridRunner().run(s1_inputs)
            s1_time_grid_paths = s1_result.time_grid_paths
            s1_grouping_paths = s1_result.grouping_paths

        s2_intensity_paths: dict[str, Path] = {}
        s2_latent_paths: dict[str, Path] = {}
        if config.run_s2 and config.run_s1:
            logger.info("Segment5B S2 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s2_inputs = IntensityInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s2_result = IntensityRunner().run(s2_inputs)
            s2_intensity_paths = s2_result.intensity_paths
            s2_latent_paths = s2_result.latent_field_paths

        s3_count_paths: dict[str, Path] = {}
        if config.run_s3 and config.run_s2:
            logger.info("Segment5B S3 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s3_inputs = CountInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s3_result = CountRunner().run(s3_inputs)
            s3_count_paths = s3_result.count_paths

        s4_arrival_paths: dict[str, Path] = {}
        s4_summary_paths: dict[str, Path] = {}
        if config.run_s4 and config.run_s3:
            logger.info("Segment5B S4 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s4_inputs = ArrivalInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s4_result = ArrivalRunner().run(s4_inputs)
            s4_arrival_paths = s4_result.arrival_paths
            s4_summary_paths = s4_result.summary_paths

        s5_bundle_index_path = None
        s5_report_path = None
        s5_issue_table_path = None
        s5_passed_flag_path = None
        s5_run_report_path = None
        s5_overall_status = None
        if config.run_s5 and config.run_s4:
            logger.info("Segment5B S5 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s5_inputs = ValidationInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s5_result = ValidationRunner().run(s5_inputs)
            s5_bundle_index_path = s5_result.bundle_index_path
            s5_report_path = s5_result.report_path
            s5_issue_table_path = s5_result.issue_table_path
            s5_passed_flag_path = s5_result.passed_flag_path
            s5_run_report_path = s5_result.run_report_path
            s5_overall_status = s5_result.overall_status

        return Segment5BResult(
            manifest_fingerprint=s0_outputs.manifest_fingerprint,
            parameter_hash=s0_outputs.parameter_hash,
            receipt_path=s0_outputs.receipt_path,
            sealed_inputs_path=s0_outputs.sealed_inputs_path,
            sealed_inputs_digest=s0_outputs.sealed_inputs_digest,
            run_report_path=s0_outputs.run_report_path,
            s1_time_grid_paths=s1_time_grid_paths,
            s1_grouping_paths=s1_grouping_paths,
            s2_intensity_paths=s2_intensity_paths,
            s2_latent_paths=s2_latent_paths,
            s3_count_paths=s3_count_paths,
            s4_arrival_paths=s4_arrival_paths,
            s4_summary_paths=s4_summary_paths,
            s5_bundle_index_path=s5_bundle_index_path,
            s5_report_path=s5_report_path,
            s5_issue_table_path=s5_issue_table_path,
            s5_passed_flag_path=s5_passed_flag_path,
            s5_run_report_path=s5_run_report_path,
            s5_overall_status=s5_overall_status,
        )


__all__ = ["Segment5BConfig", "Segment5BResult", "Segment5BOrchestrator"]
