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


class Segment3BOrchestrator:
    """Runs Segment 3B S0 and S1 sequentially."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = VirtualsRunner()
        self._s2_runner = EdgesRunner()
        self._s3_runner = AliasRunner()

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
        s2_output_path: Path | None = None
        s2_index_path: Path | None = None
        s2_run_report_path: Path | None = None
        s2_resumed = False
        s3_blob_path: Path | None = None
        s3_index_path: Path | None = None
        s3_universe_hash_path: Path | None = None
        s3_run_report_path: Path | None = None
        s3_resumed = False
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
        if config.run_s2:
            s2_inputs = EdgesInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                seed=int(config.seed),
                dictionary_path=config.dictionary_path,
            )
            s2_result: EdgesResult = self._s2_runner.run(s2_inputs)
            s2_output_path = s2_result.edge_catalogue_path
            s2_index_path = s2_result.edge_catalogue_index_path
            s2_run_report_path = s2_result.run_report_path
            s2_resumed = s2_result.resumed
        if config.run_s3:
            s3_inputs = AliasInputs(
                data_root=data_root,
                manifest_fingerprint=s0_outputs.manifest_fingerprint,
                seed=int(config.seed),
                dictionary_path=config.dictionary_path,
            )
            s3_result: AliasResult = self._s3_runner.run(s3_inputs)
            s3_blob_path = s3_result.alias_blob_path
            s3_index_path = s3_result.alias_index_path
            s3_universe_hash_path = s3_result.edge_universe_hash_path
            s3_run_report_path = s3_result.run_report_path
            s3_resumed = s3_result.resumed

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
        )
