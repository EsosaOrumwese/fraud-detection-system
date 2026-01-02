"""Scenario runner for Segment 3A (S0 gate)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from engine.layers.l1.seg_3A import S0GateInputs, S0GateRunner
from engine.layers.l1.seg_3A.s1_escalation import EscalationInputs, EscalationRunner
from engine.layers.l1.seg_3A.s2_priors import PriorsInputs, PriorsRunner
from engine.layers.l1.seg_3A.s3_zone_shares import ZoneSharesInputs, ZoneSharesRunner
from engine.layers.l1.seg_3A.s4_zone_counts import ZoneCountsInputs, ZoneCountsRunner
from engine.layers.l1.seg_3A.s5_zone_alloc import ZoneAllocInputs, ZoneAllocRunner
from engine.layers.l1.seg_3A.s6_validation import ValidationInputs, ValidationRunner
from engine.layers.l1.seg_3A.s7_bundle import BundleInputs, BundleRunner
from engine.layers.l1.seg_3A.shared.dictionary import (
    load_dictionary,
    render_dataset_path,
)
from engine.shared.heartbeat import state_heartbeat

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment3AConfig:
    """User-supplied configuration for running Segment 3A S0."""

    data_root: Path
    upstream_manifest_fingerprint: str
    seed: int
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_1a: Optional[Path] = None
    validation_bundle_1b: Optional[Path] = None
    validation_bundle_2a: Optional[Path] = None
    notes: Optional[str] = None
    resume: bool = False
    resume_manifest_fingerprint: Optional[str] = None
    run_s1: bool = False
    run_s2: bool = False
    run_s3: bool = False
    run_s4: bool = False
    run_s5: bool = False
    run_s6: bool = False
    run_s7: bool = False
    parameter_hash: Optional[str] = None
    run_id: str = "00000000000000000000000000000000"


@dataclass(frozen=True)
class Segment3AResult:
    """Structured result for Segment 3A runs."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    resumed: bool
    s1_output_path: Path | None = None
    s1_run_report_path: Path | None = None
    s1_resumed: bool = False
    s2_output_path: Path | None = None
    s2_run_report_path: Path | None = None
    s2_resumed: bool = False
    s3_output_path: Path | None = None
    s3_run_report_path: Path | None = None
    s3_resumed: bool = False
    s4_output_path: Path | None = None
    s4_run_report_path: Path | None = None
    s4_resumed: bool = False
    s5_output_path: Path | None = None
    s5_run_report_path: Path | None = None
    s5_universe_hash_path: Path | None = None
    s5_resumed: bool = False
    s6_report_path: Path | None = None
    s6_issues_path: Path | None = None
    s6_receipt_path: Path | None = None
    s6_run_report_path: Path | None = None
    s6_resumed: bool = False
    s7_bundle_path: Path | None = None
    s7_passed_flag_path: Path | None = None
    s7_index_path: Path | None = None
    s7_run_report_path: Path | None = None
    s7_resumed: bool = False


class Segment3AOrchestrator:
    """Runs Segment 3A S0 gate with optional resumability."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = EscalationRunner()
        self._s2_runner = PriorsRunner()
        self._s3_runner = ZoneSharesRunner()
        self._s4_runner = ZoneCountsRunner()
        self._s5_runner = ZoneAllocRunner()
        self._s6_runner = ValidationRunner()
        self._s7_runner = BundleRunner()

    def run(self, config: Segment3AConfig) -> Segment3AResult:
        dictionary = load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()

        logger.info(
            "Segment3A S0 orchestrator invoked (upstream_manifest=%s, seed=%s)",
            config.upstream_manifest_fingerprint,
            config.seed,
        )

        resume_manifest = config.resume_manifest_fingerprint
        if config.resume and not resume_manifest:
            raise ValueError("resume requested but resume_manifest_fingerprint not provided")

        s1_output_path = None
        s1_run_report_path = None
        s1_resumed = False
        s2_output_path = None
        s2_report_path = None
        s2_resumed = False
        s3_output_path = None
        s3_run_report_path = None
        s3_resumed = False
        s4_output_path = None
        s4_run_report_path = None
        s4_resumed = False
        s5_output_path = None
        s5_run_report_path = None
        s5_resumed = False
        s5_universe_hash_path = None
        s6_report_path = None
        s6_issues_path = None
        s6_receipt_path = None
        s6_run_report_path = None
        s6_resumed = False
        s7_bundle_path = None
        s7_passed_flag_path = None
        s7_index_path = None
        s7_run_report_path = None
        s7_resumed = False
        parameter_hash_from_receipt: str | None = None

        if config.resume and resume_manifest:
            receipt_path, sealed_inputs_path = self._resolve_output_paths(
                data_root=data_root,
                dictionary=dictionary,
                manifest_fingerprint=resume_manifest,
            )
            if receipt_path.exists() and sealed_inputs_path.exists():
                payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                parameter_hash = payload.get("parameter_hash")
                if not isinstance(parameter_hash, str) or not parameter_hash:
                    raise ValueError(f"segment3a receipt '{receipt_path}' missing parameter_hash")
                parameter_hash_from_receipt = parameter_hash
                return Segment3AResult(
                    manifest_fingerprint=resume_manifest,
                    parameter_hash=parameter_hash,
                    receipt_path=receipt_path,
                    sealed_inputs_path=sealed_inputs_path,
                    resumed=True,
                )

        inputs = S0GateInputs(
            base_path=data_root,
            output_base_path=data_root,
            seed=config.seed,
            upstream_manifest_fingerprint=config.upstream_manifest_fingerprint,
            git_commit_hex=config.git_commit_hex,
            dictionary_path=config.dictionary_path,
            validation_bundle_1a=config.validation_bundle_1a,
            validation_bundle_1b=config.validation_bundle_1b,
            validation_bundle_2a=config.validation_bundle_2a,
            notes=config.notes,
        )
        logger.info("Segment3A S0 starting (upstream_manifest=%s)", config.upstream_manifest_fingerprint)
        with state_heartbeat(logger, "Segment3A S0"):
            outputs = self._s0_runner.run(inputs)
        logger.info("Segment3A S0 completed (manifest=%s)", outputs.manifest_fingerprint)
        parameter_hash = outputs.parameter_hash
        if config.run_s1:
            logger.info("Segment3A S1 starting (manifest=%s, seed=%s)", outputs.manifest_fingerprint, config.seed)
            with state_heartbeat(logger, "Segment3A S1"):
                s1_result = self._s1_runner.run(
                    EscalationInputs(
                        data_root=data_root,
                        manifest_fingerprint=outputs.manifest_fingerprint,
                        seed=config.seed,
                        dictionary_path=config.dictionary_path,
                    )
                )
            logger.info("Segment3A S1 completed (output=%s)", s1_result.output_path)
            s1_output_path = s1_result.output_path
            s1_run_report_path = s1_result.run_report_path
            s1_resumed = s1_result.resumed
        if config.run_s2:
            parameter_hash_to_use = config.parameter_hash or parameter_hash
            logger.info("Segment3A S2 starting (manifest=%s)", outputs.manifest_fingerprint)
            with state_heartbeat(logger, "Segment3A S2"):
                s2_result = self._s2_runner.run(
                    PriorsInputs(
                        data_root=data_root,
                        manifest_fingerprint=outputs.manifest_fingerprint,
                        parameter_hash=parameter_hash_to_use,
                        seed=config.seed,
                        dictionary_path=config.dictionary_path,
                    )
                )
            logger.info("Segment3A S2 completed (output=%s)", s2_result.output_path)
            s2_output_path = s2_result.output_path
            s2_report_path = s2_result.run_report_path
            s2_resumed = s2_result.resumed
        if config.run_s3:
            parameter_hash_to_use = config.parameter_hash or parameter_hash
            logger.info("Segment3A S3 starting (manifest=%s, seed=%s)", outputs.manifest_fingerprint, config.seed)
            with state_heartbeat(logger, "Segment3A S3"):
                s3_result = self._s3_runner.run(
                    ZoneSharesInputs(
                        data_root=data_root,
                        manifest_fingerprint=outputs.manifest_fingerprint,
                        parameter_hash=parameter_hash_to_use,
                        seed=config.seed,
                        run_id=config.run_id,
                        dictionary_path=config.dictionary_path,
                    )
                )
            logger.info("Segment3A S3 completed (output=%s)", s3_result.output_path)
            s3_output_path = s3_result.output_path
            s3_run_report_path = s3_result.run_report_path
            s3_resumed = s3_result.resumed
        if config.run_s4:
            parameter_hash_to_use = config.parameter_hash or parameter_hash
            logger.info("Segment3A S4 starting (manifest=%s, seed=%s)", outputs.manifest_fingerprint, config.seed)
            with state_heartbeat(logger, "Segment3A S4"):
                s4_result = self._s4_runner.run(
                    ZoneCountsInputs(
                        data_root=data_root,
                        manifest_fingerprint=outputs.manifest_fingerprint,
                        parameter_hash=parameter_hash_to_use,
                        seed=config.seed,
                        dictionary_path=config.dictionary_path,
                    )
                )
            logger.info("Segment3A S4 completed (output=%s)", s4_result.output_path)
            s4_output_path = s4_result.output_path
            s4_run_report_path = s4_result.run_report_path
            s4_resumed = s4_result.resumed
        if config.run_s5:
            parameter_hash_to_use = config.parameter_hash or parameter_hash
            logger.info("Segment3A S5 starting (manifest=%s, seed=%s)", outputs.manifest_fingerprint, config.seed)
            with state_heartbeat(logger, "Segment3A S5"):
                s5_result = self._s5_runner.run(
                    ZoneAllocInputs(
                        data_root=data_root,
                        manifest_fingerprint=outputs.manifest_fingerprint,
                        parameter_hash=parameter_hash_to_use,
                        seed=config.seed,
                        dictionary_path=config.dictionary_path,
                    )
                )
            logger.info("Segment3A S5 completed (output=%s)", s5_result.output_path)
            s5_output_path = s5_result.output_path
            s5_run_report_path = s5_result.run_report_path
            s5_universe_hash_path = s5_result.universe_hash_path
            s5_resumed = s5_result.resumed
        if config.run_s6:
            parameter_hash_to_use = config.parameter_hash or parameter_hash
            logger.info("Segment3A S6 starting (manifest=%s)", outputs.manifest_fingerprint)
            with state_heartbeat(logger, "Segment3A S6"):
                s6_result = self._s6_runner.run(
                    ValidationInputs(
                        data_root=data_root,
                        manifest_fingerprint=outputs.manifest_fingerprint,
                        parameter_hash=parameter_hash_to_use,
                        seed=config.seed,
                        run_id=config.run_id,
                        dictionary_path=config.dictionary_path,
                    )
                )
            logger.info("Segment3A S6 completed (report=%s)", s6_result.report_path)
            s6_report_path = s6_result.report_path
            s6_issues_path = s6_result.issues_path
            s6_receipt_path = s6_result.receipt_path
            s6_run_report_path = s6_result.run_report_path
            s6_resumed = s6_result.resumed
        if config.run_s7:
            parameter_hash_to_use = config.parameter_hash or parameter_hash
            logger.info("Segment3A S7 starting (manifest=%s)", outputs.manifest_fingerprint)
            with state_heartbeat(logger, "Segment3A S7"):
                s7_result = self._s7_runner.run(
                    BundleInputs(
                        data_root=data_root,
                        manifest_fingerprint=outputs.manifest_fingerprint,
                        parameter_hash=parameter_hash_to_use,
                        seed=config.seed,
                        dictionary_path=config.dictionary_path,
                    )
                )
            logger.info("Segment3A S7 completed (bundle=%s)", s7_result.bundle_path)
            s7_bundle_path = s7_result.bundle_path
            s7_passed_flag_path = s7_result.passed_flag_path
            s7_index_path = s7_result.index_path
            s7_run_report_path = s7_result.run_report_path
            s7_resumed = s7_result.resumed

        return Segment3AResult(
            manifest_fingerprint=outputs.manifest_fingerprint,
            parameter_hash=parameter_hash,
            receipt_path=outputs.receipt_path,
            sealed_inputs_path=outputs.sealed_inputs_path,
            resumed=False,
            s1_output_path=s1_output_path,
            s1_run_report_path=s1_run_report_path,
            s1_resumed=s1_resumed,
            s2_output_path=s2_output_path,
            s2_run_report_path=s2_report_path,
            s2_resumed=s2_resumed,
            s3_output_path=s3_output_path,
            s3_run_report_path=s3_run_report_path,
            s3_resumed=s3_resumed,
            s4_output_path=s4_output_path,
            s4_run_report_path=s4_run_report_path,
            s4_resumed=s4_resumed,
            s5_output_path=s5_output_path,
            s5_run_report_path=s5_run_report_path,
            s5_universe_hash_path=s5_universe_hash_path,
            s5_resumed=s5_resumed,
            s6_report_path=s6_report_path,
            s6_issues_path=s6_issues_path,
            s6_receipt_path=s6_receipt_path,
            s6_run_report_path=s6_run_report_path,
            s6_resumed=s6_resumed,
            s7_bundle_path=s7_bundle_path,
            s7_passed_flag_path=s7_passed_flag_path,
            s7_index_path=s7_index_path,
            s7_run_report_path=s7_run_report_path,
            s7_resumed=s7_resumed,
        )

    def _resolve_output_paths(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
    ) -> tuple[Path, Path]:
        receipt_rel = render_dataset_path(
            dataset_id="s0_gate_receipt_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        sealed_rel = render_dataset_path(
            dataset_id="sealed_inputs_3A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        return data_root / receipt_rel, data_root / sealed_rel
