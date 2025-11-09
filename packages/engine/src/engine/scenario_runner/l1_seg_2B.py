"""Scenario runner for Segment 2B (S0 gate)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from engine.layers.l1.seg_2B import (
    S0GateInputs,
    S0GateRunner,
    S0GateOutputs,
    S1WeightsInputs,
    S1WeightsRunner,
    S1WeightsResult,
    S2AliasInputs,
    S2AliasResult,
    S2AliasRunner,
    S3DayEffectsInputs,
    S3DayEffectsResult,
    S3DayEffectsRunner,
    S4GroupWeightsInputs,
    S4GroupWeightsResult,
    S4GroupWeightsRunner,
    S5RouterArrival,
    S5RouterInputs,
    S5RouterResult,
    S5RouterRunner,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment2BConfig:
    """User-supplied configuration for running Segment 2B S0."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    seg2a_manifest_fingerprint: str
    parameter_hash: str
    git_commit_hex: str
    dictionary_path: Optional[Path] = None
    validation_bundle_path: Optional[Path] = None
    notes: Optional[str] = None
    pin_civil_time: bool = False
    run_s1: bool = False
    s1_resume: bool = False
    s1_emit_run_report_stdout: bool = True
    run_s2: bool = False
    s2_resume: bool = False
    s2_emit_run_report_stdout: bool = True
    run_s3: bool = False
    s3_resume: bool = False
    s3_emit_run_report_stdout: bool = True
    run_s4: bool = False
    s4_resume: bool = False
    s4_emit_run_report_stdout: bool = True
    run_s5: bool = False
    s5_emit_selection_log: bool = False
    s5_arrivals_path: Optional[Path] = None


@dataclass(frozen=True)
class Segment2BResult:
    """Structured result for Segment 2B S0 runs."""

    manifest_fingerprint: str
    seg2a_manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    inventory_path: Path
    flag_sha256_hex: str
    verified_at_utc: str
    s1_output_path: Optional[Path] = None
    s1_run_report_path: Optional[Path] = None
    s1_resumed: bool = False
    s2_index_path: Optional[Path] = None
    s2_blob_path: Optional[Path] = None
    s2_run_report_path: Optional[Path] = None
    s2_resumed: bool = False
    s3_output_path: Optional[Path] = None
    s3_run_report_path: Optional[Path] = None
    s3_resumed: bool = False
    s4_output_path: Optional[Path] = None
    s4_run_report_path: Optional[Path] = None
    s4_resumed: bool = False
    s5_run_id: Optional[str] = None
    s5_rng_event_group_path: Optional[Path] = None
    s5_rng_event_site_path: Optional[Path] = None
    s5_rng_trace_log_path: Optional[Path] = None
    s5_rng_audit_log_path: Optional[Path] = None
    s5_selection_log_paths: Tuple[Path, ...] = ()
    s5_run_report_path: Optional[Path] = None


class Segment2BOrchestrator:
    """Runs Segment 2B S0 gate."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = S1WeightsRunner()
        self._s2_runner = S2AliasRunner()
        self._s3_runner = S3DayEffectsRunner()
        self._s4_runner = S4GroupWeightsRunner()
        self._s5_runner = S5RouterRunner()
        self._s5_runner = S5RouterRunner()

    def run(self, config: Segment2BConfig) -> Segment2BResult:
        data_root = config.data_root.expanduser().resolve()
        gate_inputs = S0GateInputs(
            data_root=data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            seg2a_manifest_fingerprint=config.seg2a_manifest_fingerprint,
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
            logger.info(
                "Segment2B S1 starting (seed=%s, manifest=%s)",
                config.seed,
                gate_output.manifest_fingerprint,
            )
            s1_inputs = S1WeightsInputs(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=gate_output.manifest_fingerprint,
                dictionary_path=config.dictionary_path,
                resume=config.s1_resume,
                emit_run_report_stdout=config.s1_emit_run_report_stdout,
            )
            s1_result = self._s1_runner.run(s1_inputs)
            logger.info(
                "Segment2B S1 %s (output=%s, run_report=%s)",
                "resumed" if s1_result.resumed else "completed",
                s1_result.output_path,
                s1_result.run_report_path,
            )
        s2_result: S2AliasResult | None = None
        if config.run_s2:
            logger.info(
                "Segment2B S2 starting (seed=%s, manifest=%s)",
                config.seed,
                gate_output.manifest_fingerprint,
            )
            s2_inputs = S2AliasInputs(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=gate_output.manifest_fingerprint,
                dictionary_path=config.dictionary_path,
                resume=config.s2_resume,
                emit_run_report_stdout=config.s2_emit_run_report_stdout,
            )
            s2_result = self._s2_runner.run(s2_inputs)
            logger.info(
                "Segment2B S2 %s (index=%s, blob=%s)",
                "resumed" if s2_result.resumed else "completed",
                s2_result.index_path,
                s2_result.blob_path,
            )
        s3_result: S3DayEffectsResult | None = None
        if config.run_s3:
            logger.info(
                "Segment2B S3 starting (seed=%s, manifest=%s)",
                config.seed,
                gate_output.manifest_fingerprint,
            )
            s3_inputs = S3DayEffectsInputs(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=gate_output.manifest_fingerprint,
                seg2a_manifest_fingerprint=config.seg2a_manifest_fingerprint,
                dictionary_path=config.dictionary_path,
                resume=config.s3_resume,
                emit_run_report_stdout=config.s3_emit_run_report_stdout,
            )
            s3_result = self._s3_runner.run(s3_inputs)
            logger.info(
                "Segment2B S3 %s (output=%s)",
                "resumed" if s3_result.resumed else "completed",
                s3_result.output_path,
            )
        s4_result: S4GroupWeightsResult | None = None
        if config.run_s4:
            logger.info(
                "Segment2B S4 starting (seed=%s, manifest=%s)",
                config.seed,
                gate_output.manifest_fingerprint,
            )
            s4_inputs = S4GroupWeightsInputs(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=gate_output.manifest_fingerprint,
                seg2a_manifest_fingerprint=config.seg2a_manifest_fingerprint,
                dictionary_path=config.dictionary_path,
                resume=config.s4_resume,
                emit_run_report_stdout=config.s4_emit_run_report_stdout,
            )
            s4_result = self._s4_runner.run(s4_inputs)
            logger.info(
                "Segment2B S4 %s (output=%s)",
                "resumed" if s4_result.resumed else "completed",
                s4_result.output_path,
            )
        s5_result: S5RouterResult | None = None
        if config.run_s5:
            arrivals: List[S5RouterArrival] | None = None
            if config.s5_arrivals_path is not None:
                arrivals = self._load_arrivals_from_file(config.s5_arrivals_path)
            logger.info(
                "Segment2B S5 starting (seed=%s, manifest=%s)",
                config.seed,
                gate_output.manifest_fingerprint,
            )
            s5_inputs = S5RouterInputs(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=gate_output.manifest_fingerprint,
                seg2a_manifest_fingerprint=config.seg2a_manifest_fingerprint,
                parameter_hash=gate_output.parameter_hash,
                git_commit_hex=config.git_commit_hex,
                arrivals=arrivals,
                dictionary_path=config.dictionary_path,
                emit_selection_log=config.s5_emit_selection_log,
            )
            s5_result = self._s5_runner.run(s5_inputs)
            logger.info(
                "Segment2B S5 completed (run_id=%s, selections=%s)",
                s5_result.run_id,
                s5_result.arrivals_processed,
            )
        return Segment2BResult(
            manifest_fingerprint=gate_output.manifest_fingerprint,
            seg2a_manifest_fingerprint=config.seg2a_manifest_fingerprint,
            parameter_hash=gate_output.parameter_hash,
            receipt_path=gate_output.receipt_path,
            inventory_path=gate_output.inventory_path,
            flag_sha256_hex=gate_output.flag_sha256_hex,
            verified_at_utc=gate_output.verified_at_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            s1_output_path=s1_result.output_path if s1_result else None,
            s1_run_report_path=s1_result.run_report_path if s1_result else None,
            s1_resumed=s1_result.resumed if s1_result else False,
            s2_index_path=s2_result.index_path if s2_result else None,
            s2_blob_path=s2_result.blob_path if s2_result else None,
            s2_run_report_path=s2_result.run_report_path if s2_result else None,
            s2_resumed=s2_result.resumed if s2_result else False,
            s3_output_path=s3_result.output_path if s3_result else None,
            s3_run_report_path=s3_result.run_report_path if s3_result else None,
            s3_resumed=s3_result.resumed if s3_result else False,
            s4_output_path=s4_result.output_path if s4_result else None,
            s4_run_report_path=s4_result.run_report_path if s4_result else None,
            s4_resumed=s4_result.resumed if s4_result else False,
            s5_run_id=s5_result.run_id if s5_result else None,
            s5_rng_event_group_path=s5_result.rng_event_group_path if s5_result else None,
            s5_rng_event_site_path=s5_result.rng_event_site_path if s5_result else None,
            s5_rng_trace_log_path=s5_result.rng_trace_log_path if s5_result else None,
            s5_rng_audit_log_path=s5_result.rng_audit_log_path if s5_result else None,
            s5_selection_log_paths=s5_result.selection_log_paths if s5_result else (),
            s5_run_report_path=s5_result.run_report_path if s5_result else None,
        )

    @staticmethod
    def _load_arrivals_from_file(path: Path) -> List[S5RouterArrival]:
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"arrivals file '{resolved}' not found")
        arrivals: List[S5RouterArrival] = []
        with resolved.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                payload_str = line.strip()
                if not payload_str:
                    continue
                try:
                    payload = json.loads(payload_str)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"arrivals file '{resolved}' line {line_no} is not valid JSON"
                    ) from exc
                arrivals.append(S5RouterArrival.from_payload(payload))
        return arrivals


__all__ = ["Segment2BConfig", "Segment2BOrchestrator", "Segment2BResult"]
