"""Scenario runner for Segment 2A (S0 gate plus provisional lookup S1)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from engine.layers.l1.seg_2A import (
    ProvisionalLookupInputs,
    ProvisionalLookupRunner,
    ProvisionalLookupResult,
    S0GateRunner,
)
from engine.layers.l1.seg_2A.s0_gate.l2.runner import GateInputs
from engine.layers.l1.seg_2A.shared.dictionary import load_dictionary, render_dataset_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment2AConfig:
    """User-supplied configuration for running Segment 2A."""

    data_root: Path
    upstream_manifest_fingerprint: str
    parameter_hash: str
    seed: int
    tzdb_release_tag: str
    git_commit_hex: str
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None
    validation_bundle_path: Optional[Path] = None
    notes: Optional[str] = None
    resume: bool = False
    resume_manifest_fingerprint: Optional[str] = None
    run_s1: bool = False
    s1_chunk_size: int = 250_000
    s1_resume: bool = False


@dataclass(frozen=True)
class Segment2AResult:
    """Structured result for Segment 2A runs."""

    manifest_fingerprint: str
    receipt_path: Path
    inventory_path: Path
    resumed: bool
    s1_output_path: Path | None = None
    s1_resumed: bool = False


class Segment2AOrchestrator:
    """Runs Segment 2A (S0, optional S1) with optional resumability."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = ProvisionalLookupRunner()

    def run(self, config: Segment2AConfig) -> Segment2AResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()

        logger.info(
            "Segment2A S0 orchestrator invoked (upstream_manifest=%s, seed=%s, tz_release=%s)",
            config.upstream_manifest_fingerprint,
            config.seed,
            config.tzdb_release_tag,
        )

        s0_resumed = False
        gate_manifest: str | None = None
        gate_receipt_path: Path | None = None
        gate_inventory_path: Path | None = None
        if config.resume:
            manifest = config.resume_manifest_fingerprint
            if not manifest:
                raise ValueError(
                    "resume requested but resume_manifest_fingerprint was not provided"
                )
            receipt_path, inventory_path = self._resolve_output_paths(
                data_root=data_root,
                dictionary=dictionary,
                manifest_fingerprint=manifest,
            )
            if receipt_path.exists() and inventory_path.exists():
                logger.info(
                    "Segment2A resume detected (manifest=%s); skipping S0 execution",
                    manifest,
                )
                s0_resumed = True
                gate_manifest = manifest
                gate_receipt_path = receipt_path
                gate_inventory_path = inventory_path
                if not config.run_s1:
                    return Segment2AResult(
                        manifest_fingerprint=manifest,
                        receipt_path=receipt_path,
                        inventory_path=inventory_path,
                        resumed=True,
                    )
            else:
                logger.warning(
                    "Segment2A resume requested for manifest %s but outputs are missing; "
                    "running S0 from scratch",
                    manifest,
                )

        if not s0_resumed:
            gate_inputs = GateInputs(
                base_path=data_root,
                output_base_path=data_root,
                seed=config.seed,
                upstream_manifest_fingerprint=config.upstream_manifest_fingerprint,
                tzdb_release_tag=config.tzdb_release_tag,
                git_commit_hex=config.git_commit_hex,
                dictionary_path=config.dictionary_path,
                validation_bundle_path=config.validation_bundle_path,
                notes=config.notes,
            )
            gate_result = self._s0_runner.run(gate_inputs)
            gate_manifest = gate_result.manifest_fingerprint
            gate_receipt_path = gate_result.receipt_path
            gate_inventory_path = gate_result.inventory_path
            logger.info(
                "Segment2A S0 completed (manifest=%s, receipt=%s)",
                gate_manifest,
                gate_receipt_path,
            )
        else:
            gate_result = None

        assert gate_manifest is not None and gate_receipt_path is not None and gate_inventory_path is not None
        s1_result: ProvisionalLookupResult | None = None
        if config.run_s1:
            logger.info(
                "Segment2A S1 starting (seed=%s, manifest=%s)",
                config.seed,
                gate_manifest,
            )
            s1_result = self._s1_runner.run(
                ProvisionalLookupInputs(
                    data_root=data_root,
                    seed=config.seed,
                    manifest_fingerprint=gate_manifest,
                    chunk_size=max(config.s1_chunk_size, 1),
                    resume=config.s1_resume,
                    dictionary=dictionary,
                )
            )
            logger.info(
                "Segment2A S1 completed (output=%s, resumed=%s)",
                s1_result.output_path,
                s1_result.resumed,
            )

        return Segment2AResult(
            manifest_fingerprint=gate_manifest,
            receipt_path=gate_receipt_path,
            inventory_path=gate_inventory_path,
            resumed=s0_resumed,
            s1_output_path=s1_result.output_path if s1_result else None,
            s1_resumed=s1_result.resumed if s1_result else False,
        )

    @staticmethod
    def _resolve_output_paths(
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
    ) -> tuple[Path, Path]:
        template_args = {"manifest_fingerprint": manifest_fingerprint}
        receipt_rel = render_dataset_path(
            "s0_gate_receipt_2A",
            template_args=template_args,
            dictionary=dictionary,
        )
        inventory_rel = render_dataset_path(
            "sealed_inputs_v1",
            template_args=template_args,
            dictionary=dictionary,
        )
        receipt_path = (data_root / receipt_rel).resolve()
        inventory_path = (data_root / inventory_rel).resolve()
        return receipt_path, inventory_path


__all__ = ["Segment2AConfig", "Segment2AOrchestrator", "Segment2AResult"]
