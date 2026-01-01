"""Scenario runner for Segment 6B (S0 gate through S5 validation)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from engine.layers.l3.seg_6B import (
    ArrivalInputs,
    ArrivalRunner,
    BaselineInputs,
    BaselineRunner,
    FraudInputs,
    FraudRunner,
    LabelInputs,
    LabelRunner,
    S0GateRunner,
    S0Inputs,
    S0Outputs,
    ValidationInputs,
    ValidationRunner,
)
from engine.layers.l3.seg_6B.shared.dictionary import load_dictionary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment6BConfig:
    """User configuration for running Segment 6B."""

    data_root: Path
    manifest_fingerprint: str
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
    validation_bundle_5b: Optional[Path] = None
    validation_bundle_6a: Optional[Path] = None
    run_s1: bool = True
    run_s2: bool = True
    run_s3: bool = True
    run_s4: bool = True
    run_s5: bool = True


@dataclass(frozen=True)
class Segment6BResult:
    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    sealed_inputs_digest: str
    s1_arrival_entities_paths: dict[str, Path]
    s1_session_index_paths: dict[str, Path]
    s2_flow_paths: dict[str, Path]
    s2_event_paths: dict[str, Path]
    s3_campaign_paths: dict[str, Path]
    s3_flow_paths: dict[str, Path]
    s3_event_paths: dict[str, Path]
    s4_flow_truth_paths: dict[str, Path]
    s4_flow_bank_paths: dict[str, Path]
    s4_event_label_paths: dict[str, Path]
    s4_case_timeline_paths: dict[str, Path]
    s5_report_path: Path | None
    s5_issue_table_path: Path | None
    s5_bundle_index_path: Path | None
    s5_passed_flag_path: Path | None


class Segment6BOrchestrator:
    """Runs Segment 6B S0-S5."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()

    def run(self, config: Segment6BConfig) -> Segment6BResult:
        load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().absolute()

        logger.info(
            "Segment6B S0 orchestrator invoked (manifest=%s, parameter_hash=%s)",
            config.manifest_fingerprint,
            config.parameter_hash,
        )
        s0_inputs = S0Inputs(
            base_path=data_root,
            output_base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
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
            validation_bundle_5b=config.validation_bundle_5b,
            validation_bundle_6a=config.validation_bundle_6a,
        )
        logger.info("Segment6B S0 starting (manifest=%s)", config.manifest_fingerprint)
        s0_outputs: S0Outputs = self._s0_runner.run(s0_inputs)
        logger.info("Segment6B S0 completed (manifest=%s)", s0_outputs.manifest_fingerprint)

        s1_arrival_entities_paths: dict[str, Path] = {}
        s1_session_index_paths: dict[str, Path] = {}
        if config.run_s1:
            logger.info("Segment6B S1 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s1_inputs = ArrivalInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s1_result = ArrivalRunner().run(s1_inputs)
            s1_arrival_entities_paths = s1_result.arrival_entities_paths
            s1_session_index_paths = s1_result.session_index_paths

        s2_flow_paths: dict[str, Path] = {}
        s2_event_paths: dict[str, Path] = {}
        if config.run_s2 and config.run_s1:
            logger.info("Segment6B S2 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s2_inputs = BaselineInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s2_result = BaselineRunner().run(s2_inputs)
            s2_flow_paths = s2_result.flow_paths
            s2_event_paths = s2_result.event_paths

        s3_campaign_paths: dict[str, Path] = {}
        s3_flow_paths: dict[str, Path] = {}
        s3_event_paths: dict[str, Path] = {}
        if config.run_s3 and config.run_s2:
            logger.info("Segment6B S3 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s3_inputs = FraudInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s3_result = FraudRunner().run(s3_inputs)
            s3_campaign_paths = s3_result.campaign_paths
            s3_flow_paths = s3_result.flow_paths
            s3_event_paths = s3_result.event_paths

        s4_flow_truth_paths: dict[str, Path] = {}
        s4_flow_bank_paths: dict[str, Path] = {}
        s4_event_label_paths: dict[str, Path] = {}
        s4_case_timeline_paths: dict[str, Path] = {}
        if config.run_s4 and config.run_s3:
            logger.info("Segment6B S4 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s4_inputs = LabelInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s4_result = LabelRunner().run(s4_inputs)
            s4_flow_truth_paths = s4_result.flow_truth_paths
            s4_flow_bank_paths = s4_result.flow_bank_paths
            s4_event_label_paths = s4_result.event_label_paths
            s4_case_timeline_paths = s4_result.case_timeline_paths

        s5_report_path = None
        s5_issue_table_path = None
        s5_bundle_index_path = None
        s5_passed_flag_path = None
        if config.run_s5 and config.run_s4:
            logger.info("Segment6B S5 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s5_inputs = ValidationInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                parameter_hash=s0_outputs.parameter_hash,
                seed=config.seed,
                run_id=config.run_id,
                dictionary_path=config.dictionary_path,
            )
            s5_result = ValidationRunner().run(s5_inputs)
            s5_report_path = s5_result.report_path
            s5_issue_table_path = s5_result.issue_table_path
            s5_bundle_index_path = s5_result.bundle_index_path
            s5_passed_flag_path = s5_result.passed_flag_path

        return Segment6BResult(
            manifest_fingerprint=s0_outputs.manifest_fingerprint,
            parameter_hash=s0_outputs.parameter_hash,
            receipt_path=s0_outputs.receipt_path,
            sealed_inputs_path=s0_outputs.sealed_inputs_path,
            sealed_inputs_digest=s0_outputs.sealed_inputs_digest,
            s1_arrival_entities_paths=s1_arrival_entities_paths,
            s1_session_index_paths=s1_session_index_paths,
            s2_flow_paths=s2_flow_paths,
            s2_event_paths=s2_event_paths,
            s3_campaign_paths=s3_campaign_paths,
            s3_flow_paths=s3_flow_paths,
            s3_event_paths=s3_event_paths,
            s4_flow_truth_paths=s4_flow_truth_paths,
            s4_flow_bank_paths=s4_flow_bank_paths,
            s4_event_label_paths=s4_event_label_paths,
            s4_case_timeline_paths=s4_case_timeline_paths,
            s5_report_path=s5_report_path,
            s5_issue_table_path=s5_issue_table_path,
            s5_bundle_index_path=s5_bundle_index_path,
            s5_passed_flag_path=s5_passed_flag_path,
        )


__all__ = ["Segment6BConfig", "Segment6BResult", "Segment6BOrchestrator"]
