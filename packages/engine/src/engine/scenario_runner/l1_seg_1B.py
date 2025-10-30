"""Scenario runner for Segment 1B (S0 → S9)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from engine.layers.l1.seg_1B import (
    GateInputs,
    S0GateRunner,
    S1RunnerConfig,
    S1RunResult,
    S1TileIndexRunner,
    S2RunnerConfig,
    S2RunResult,
    S2TileWeightsRunner,
    S3RequirementsRunner,
    S3RunResult,
    S3RunnerConfig,
    S4AllocPlanRunner,
    S4RunResult,
    S4RunnerConfig,
    S5RunResult,
    S5RunnerConfig,
    S5SiteTileAssignmentRunner,
    S6RunResult,
    S6RunnerConfig,
    S6SiteJitterRunner,
    S7RunResult,
    S7RunnerConfig,
    S7SiteSynthesisRunner,
    S8RunResult,
    S8RunnerConfig,
    S8SiteLocationsRunner,
    S9RunResult,
    S9RunnerConfig,
    S9ValidationRunner,
)
from engine.layers.l1.seg_1B.shared.dictionary import load_dictionary


@dataclass(frozen=True)
class Segment1BConfig:
    """User-supplied configuration for running Segment 1B."""

    data_root: Path
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None
    basis: str = "uniform"
    dp: int = 2
    manifest_fingerprint: Optional[str] = None
    seed: Optional[str] = None
    notes: Optional[str] = None
    validation_bundle_path: Optional[Path] = None
    skip_s0: bool = False
    s1_workers: int = 1
    s4_workers: int = 1


@dataclass(frozen=True)
class Segment1BResult:
    """Structured result capturing outputs from S0–S9."""

    s0_receipt_path: Optional[Path]
    s1: S1RunResult
    s2: S2RunResult
    s3: S3RunResult
    s4: S4RunResult
    s5: S5RunResult
    s6: S6RunResult
    s7: S7RunResult
    s8: S8RunResult
    s9: S9RunResult


logger = logging.getLogger(__name__)


class Segment1BOrchestrator:
    """Runs Segment 1B states sequentially."""

    def __init__(self) -> None:
        self._s0_runner = S0GateRunner()
        self._s1_runner = S1TileIndexRunner()
        self._s2_runner = S2TileWeightsRunner()
        self._s3_runner = S3RequirementsRunner()
        self._s4_runner = S4AllocPlanRunner()
        self._s5_runner = S5SiteTileAssignmentRunner()
        self._s6_runner = S6SiteJitterRunner()
        self._s7_runner = S7SiteSynthesisRunner()
        self._s8_runner = S8SiteLocationsRunner()
        self._s9_runner = S9ValidationRunner()

    def run(self, config: Segment1BConfig) -> Segment1BResult:
        dictionary = config.dictionary or load_dictionary()
        data_root = config.data_root.expanduser().resolve()

        receipt_path: Optional[Path] = None
        if not config.skip_s0:
            if not config.manifest_fingerprint or config.seed is None:
                raise ValueError("manifest_fingerprint and seed must be provided when S0 is executed")
            logger.info(
                "Segment1B S0 gate starting (parameter_hash=%s, manifest=%s)",
                config.parameter_hash,
                config.manifest_fingerprint,
            )
            gate_inputs = GateInputs(
                base_path=data_root,
                output_base_path=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                notes=config.notes,
                dictionary=dictionary,
                validation_bundle_path=config.validation_bundle_path,
            )
            gate_result = self._s0_runner.run(gate_inputs)
            receipt_path = gate_result.receipt_path
            logger.info("Segment1B S0 completed (receipt=%s)", receipt_path)

        if not config.manifest_fingerprint or config.seed is None:
            raise ValueError("manifest_fingerprint and seed must be provided for S3 requirements")

        logger.info("Segment1B S1 starting")
        s1_result = self._s1_runner.run(
            S1RunnerConfig(
                data_root=data_root,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
                workers=max(1, config.s1_workers),
            )
        )
        logger.info(
            "Segment1B S1 completed (tile_index=%s, tile_bounds=%s)",
            s1_result.tile_index_path,
            s1_result.tile_bounds_path,
        )

        logger.info("Segment1B S2 starting")
        prepared_s2 = self._s2_runner.prepare(
            S2RunnerConfig(
                data_root=data_root,
                parameter_hash=config.parameter_hash,
                basis=config.basis,
                dp=config.dp,
                dictionary=dictionary,
            )
        )
        masses = self._s2_runner.compute_masses(prepared_s2)
        self._s2_runner.measure_baselines(
            prepared_s2,
            measure_raster=prepared_s2.governed.basis == "population",
        )
        quantised = self._s2_runner.quantise(prepared_s2, masses)
        logger.info(
            "Segment1B S2 progress (rows_emitted=%d, countries=%d, temp_dir=%s)",
            quantised.rows_emitted,
            len(quantised.summaries),
            quantised.temp_dir,
        )
        s2_result = self._s2_runner.materialise(prepared_s2, quantised)
        logger.info(
            "Segment1B S2 completed (weights=%s, report=%s)",
            s2_result.tile_weights_path,
            s2_result.report_path,
        )

        logger.info("Segment1B S3 starting")
        prepared_s3 = self._s3_runner.prepare(
            S3RunnerConfig(
                data_root=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
            )
        )
        aggregation = self._s3_runner.aggregate(prepared_s3)
        logger.info(
            "Segment1B S3 aggregation (rows=%d, merchants=%d, countries=%d, source_rows=%d)",
            aggregation.rows_emitted,
            aggregation.merchants_total,
            aggregation.countries_total,
            aggregation.source_rows_total,
        )
        s3_result = self._s3_runner.materialise(prepared_s3, aggregation)
        logger.info(
            "Segment1B S3 completed (requirements=%s, report=%s)",
            s3_result.requirements_path,
            s3_result.report_path,
        )

        logger.info("Segment1B S4 starting")
        s4_result = self._s4_runner.run(
            S4RunnerConfig(
                data_root=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
                workers=config.s4_workers,
            )
        )
        logger.info(
            "Segment1B S4 completed (alloc_plan=%s, report=%s)",
            s4_result.alloc_plan_path,
            s4_result.report_path,
        )
        logger.info(
            "Segment1B S4 summary (rows=%d, merchants=%d, pairs=%d, shortfall=%d, ties_broken=%d)",
            s4_result.rows_emitted,
            s4_result.merchants_total,
            s4_result.pairs_total,
            s4_result.shortfall_total,
            s4_result.ties_broken_total,
        )

        logger.info("Segment1B S5 starting")
        s5_result = self._s5_runner.run(
            S5RunnerConfig(
                data_root=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
            )
        )
        logger.info(
            "Segment1B S5 completed (dataset=%s, report=%s)",
            s5_result.dataset_path,
            s5_result.run_report_path,
        )
        logger.info(
            "Segment1B S5 summary (rows=%d, pairs=%d, rng_events=%d, run_id=%s)",
            s5_result.rows_emitted,
            s5_result.pairs_total,
            s5_result.rng_events_emitted,
            s5_result.run_id,
        )

        logger.info("Segment1B S6 starting")
        s6_result = self._s6_runner.run(
            S6RunnerConfig(
                data_root=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
                run_id_override=s5_result.run_id,
            )
        )
        logger.info(
            "Segment1B S6 completed (dataset=%s, report=%s)",
            s6_result.dataset_path,
            s6_result.run_report_path,
        )
        logger.info(
            "Segment1B S6 summary (rows=%d, rng_events=%d, counter_span=%d, run_id=%s)",
            s6_result.rows_emitted,
            s6_result.rng_events_total,
            s6_result.counter_span,
            s6_result.run_id,
        )

        logger.info("Segment1B S7 starting")
        s7_result = self._s7_runner.run(
            S7RunnerConfig(
                data_root=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
            )
        )
        logger.info(
            "Segment1B S7 completed (dataset=%s, report=%s)",
            s7_result.dataset_path,
            s7_result.run_summary_path,
        )
        logger.info(
            "Segment1B S7 summary (run_id=%s, wall_clock=%.2fs, cpu=%.2fs)",
            s7_result.run_id,
            s7_result.wall_clock_seconds,
            s7_result.cpu_seconds,
        )

        logger.info("Segment1B S8 starting")
        s8_result = self._s8_runner.run(
            S8RunnerConfig(
                data_root=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                seed=config.seed,
                parameter_hash=config.parameter_hash,
                dictionary=dictionary,
            )
        )
        logger.info(
            "Segment1B S8 completed (dataset=%s, report=%s)",
            s8_result.dataset_path,
            s8_result.run_summary_path,
        )
        logger.info(
            "Segment1B S8 summary (run_id=%s, wall_clock=%.2fs, cpu=%.2fs)",
            s8_result.run_id,
            s8_result.wall_clock_seconds,
            s8_result.cpu_seconds,
        )

        seed_int = int(config.seed)

        s9_result = self._s9_runner.run(
            S9RunnerConfig(
                base_path=data_root,
                seed=seed_int,
                parameter_hash=config.parameter_hash,
                manifest_fingerprint=config.manifest_fingerprint,
                run_id=s6_result.run_id,
                dictionary=dictionary,
            )
        )
        logger.info(
            "Segment1B S9 completed (bundle=%s, passed=%s, failures=%d)",
            s9_result.bundle_path,
            s9_result.result.passed,
            len(s9_result.result.failures),
        )

        return Segment1BResult(
            s0_receipt_path=receipt_path,
            s1=s1_result,
            s2=s2_result,
            s3=s3_result,
            s4=s4_result,
            s5=s5_result,
            s6=s6_result,
            s7=s7_result,
            s8=s8_result,
            s9=s9_result,
        )


__all__ = ["Segment1BConfig", "Segment1BOrchestrator", "Segment1BResult"]
