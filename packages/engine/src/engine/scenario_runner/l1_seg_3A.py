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
from engine.layers.l1.seg_3A.shared.dictionary import (
    load_dictionary,
    render_dataset_path,
)

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
    parameter_hash: Optional[str] = None


@dataclass(frozen=True)
class Segment3AResult:
    """Structured result for Segment 3A runs."""

    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    sealed_inputs_path: Path
    determinism_receipt_path: Path
    resumed: bool
    s1_output_path: Path | None = None
    s1_run_report_path: Path | None = None
    s1_resumed: bool = False
    s2_output_path: Path | None = None
    s2_run_report_path: Path | None = None
    s2_resumed: bool = False


class Segment3AOrchestrator:
    """Runs Segment 3A S0 gate with optional resumability."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = EscalationRunner()
        self._s2_runner = PriorsRunner()

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
                det_path = (
                    data_root
                    / "data"
                    / "layer1"
                    / "3A"
                    / "s0_gate_receipt"
                    / "determinism_receipt.json"
                )
                parameter_hash_from_receipt = parameter_hash
                return Segment3AResult(
                    manifest_fingerprint=resume_manifest,
                    parameter_hash=parameter_hash,
                    receipt_path=receipt_path,
                    sealed_inputs_path=sealed_inputs_path,
                    determinism_receipt_path=det_path,
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
        outputs = self._s0_runner.run(inputs)
        parameter_hash = outputs.parameter_hash
        if config.run_s1:
            s1_result = self._s1_runner.run(
                EscalationInputs(
                    data_root=data_root,
                    manifest_fingerprint=outputs.manifest_fingerprint,
                    seed=config.seed,
                    dictionary_path=config.dictionary_path,
                )
            )
            s1_output_path = s1_result.output_path
            s1_run_report_path = s1_result.run_report_path
            s1_resumed = s1_result.resumed
        if config.run_s2:
            parameter_hash_to_use = config.parameter_hash or parameter_hash
            s2_result = self._s2_runner.run(
                PriorsInputs(
                    data_root=data_root,
                    manifest_fingerprint=outputs.manifest_fingerprint,
                    parameter_hash=parameter_hash_to_use,
                    dictionary_path=config.dictionary_path,
                )
            )
            s2_output_path = s2_result.output_path
            s2_report_path = s2_result.run_report_path
            s2_resumed = s2_result.resumed

        return Segment3AResult(
            manifest_fingerprint=outputs.manifest_fingerprint,
            parameter_hash=parameter_hash,
            receipt_path=outputs.receipt_path,
            sealed_inputs_path=outputs.sealed_inputs_path,
            determinism_receipt_path=outputs.determinism_receipt_path,
            resumed=False,
            s1_output_path=s1_output_path,
            s1_run_report_path=s1_run_report_path,
            s1_resumed=s1_resumed,
            s2_output_path=s2_output_path,
            s2_run_report_path=s2_report_path,
            s2_resumed=s2_resumed,
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
