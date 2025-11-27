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
    EdgesInputs,
    EdgesResult,
    EdgesRunner,
    AliasInputs,
    AliasResult,
    AliasRunner,
    RoutingInputs,
    RoutingResult,
    RoutingRunner,
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
    run_s2: bool = False
    run_s3: bool = False
    run_s4: bool = False


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
    s2_output_path: Path | None = None
    s2_index_path: Path | None = None
    s2_run_report_path: Path | None = None
    s2_resumed: bool = False
    s3_blob_path: Path | None = None
    s3_index_path: Path | None = None
    s3_universe_hash_path: Path | None = None
    s3_run_report_path: Path | None = None
    s3_resumed: bool = False
    s4_routing_policy_path: Path | None = None
    s4_validation_contract_path: Path | None = None
    s4_run_report_path: Path | None = None
    s4_run_summary_path: Path | None = None
    s4_resumed: bool = False


class Segment3BOrchestrator:
    """Runs Segment 3B S0 and S1 sequentially."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = VirtualsRunner()
        self._s2_runner = EdgesRunner()
        self._s3_runner = AliasRunner()
        self._s4_runner = RoutingRunner()

    def run(self, config: Segment3BConfig) -> Segment3BResult:
        dictionary = load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()

        logger.info(
            "Segment3B S0 orchestrator invoked (upstream_manifest=%s, seed=%s)",
            config.upstream_manifest_fingerprint,
            config.seed,
        )
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
        logger.info("Segment3B S0 starting (upstream_manifest=%s)", config.upstream_manifest_fingerprint)
        s0_outputs = self._s0_runner.run(s0_inputs)
        logger.info("Segment3B S0 completed (manifest=%s)", s0_outputs.manifest_fingerprint)

        s1_output_path: Path | None = None
        s1_run_report: Path | None = None
        s1_resumed = False
        s2_output_path: Path | None = None
        s2_index_path: Path | None = None
        s2_run_report_path: Path | None = None
        s2_resumed = False
        s3_blob_path: Path | None = None
        s3_index_path: Path | None = None
        s3_universe_hash_path: Path | None = None
        s3_run_report_path: Path | None = None
        s3_resumed = False
        s4_routing_policy_path: Path | None = None
        s4_validation_contract_path: Path | None = None
        s4_run_report_path: Path | None = None
        s4_run_summary_path: Path | None = None
        s4_resumed = False
        if config.run_s1:
            logger.info("Segment3B S1 starting (manifest=%s, seed=%s)", s0_outputs.manifest_fingerprint, config.seed)
            s1_inputs = VirtualsInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                seed=int(config.seed),
                dictionary_path=config.dictionary_path,
            )
            s1_result: VirtualsResult = self._s1_runner.run(s1_inputs)
            logger.info("Segment3B S1 completed (classification=%s)", s1_result.classification_path)
            s1_output_path = s1_result.classification_path
            s1_run_report = s1_result.run_report_path
            s1_resumed = s1_result.resumed
        if config.run_s2:
            logger.info("Segment3B S2 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s2_inputs = EdgesInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                seed=int(config.seed),
                dictionary_path=config.dictionary_path,
            )
            s2_result: EdgesResult = self._s2_runner.run(s2_inputs)
            logger.info("Segment3B S2 completed (edges=%s)", s2_result.edge_catalogue_path)
            s2_output_path = s2_result.edge_catalogue_path
            s2_index_path = s2_result.edge_catalogue_index_path
            s2_run_report_path = s2_result.run_report_path
            s2_resumed = s2_result.resumed
        if config.run_s3:
            logger.info("Segment3B S3 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s3_inputs = AliasInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                seed=int(config.seed),
                dictionary_path=config.dictionary_path,
            )
            s3_result: AliasResult = self._s3_runner.run(s3_inputs)
            logger.info("Segment3B S3 completed (alias=%s)", s3_result.alias_index_path)
            s3_blob_path = s3_result.alias_blob_path
            s3_index_path = s3_result.alias_index_path
            s3_universe_hash_path = s3_result.edge_universe_hash_path
            s3_run_report_path = s3_result.run_report_path
            s3_resumed = s3_result.resumed
        if config.run_s4:
            logger.info("Segment3B S4 starting (manifest=%s)", s0_outputs.manifest_fingerprint)
            s4_inputs = RoutingInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                seed=int(config.seed),
                dictionary_path=config.dictionary_path,
            )
            s4_result = self._s4_runner.run(s4_inputs)
            logger.info("Segment3B S4 completed (routing_policy=%s)", s4_result.routing_policy_path)
            s4_routing_policy_path = s4_result.routing_policy_path
            s4_validation_contract_path = s4_result.validation_contract_path
            s4_run_report_path = s4_result.run_report_path
            s4_run_summary_path = s4_result.run_summary_path
            s4_resumed = s4_result.resumed

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
            s2_output_path=s2_output_path,
            s2_index_path=s2_index_path,
            s2_run_report_path=s2_run_report_path,
            s2_resumed=s2_resumed,
            s3_blob_path=s3_blob_path,
            s3_index_path=s3_index_path,
            s3_universe_hash_path=s3_universe_hash_path,
            s3_run_report_path=s3_run_report_path,
            s3_resumed=s3_resumed,
            s4_routing_policy_path=s4_routing_policy_path,
            s4_validation_contract_path=s4_validation_contract_path,
            s4_run_report_path=s4_run_report_path,
            s4_run_summary_path=s4_run_summary_path,
            s4_resumed=s4_resumed,
        )
