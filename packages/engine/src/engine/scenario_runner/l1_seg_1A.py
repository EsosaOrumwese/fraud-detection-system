"""Scenario-runner helpers for Layer-1 Segment 1A states."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

import yaml

from engine.layers.l1.seg_1A.s0_foundations import S0FoundationsRunner, SchemaAuthority
from engine.layers.l1.seg_1A.s0_foundations.exceptions import err
from engine.layers.l1.seg_1A.s0_foundations.l1.design import iter_design_vectors
from engine.layers.l1.seg_1A.s0_foundations.l2.runner import S0RunResult
from engine.layers.l1.seg_1A.s1_hurdle import HurdleDesignRow, S1HurdleRunner
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import S1RunResult
from engine.layers.l1.seg_1A.s1_hurdle.l3.catalogue import GatedStream
from engine.layers.l1.seg_1A.s1_hurdle.l3.validator import validate_hurdle_run
from engine.layers.l1.seg_1A.s2_nb_outlets import (
    NBFinalRecord,
    S2DeterministicContext,
    S2NegativeBinomialRunner,
    S2RunResult,
    build_deterministic_context,
    validate_nb_run,
)
from engine.layers.l1.seg_1A.s2_nb_outlets.l3.bundle import publish_s2_validation_artifacts
from engine.layers.l1.seg_1A.s2_nb_outlets.l3.catalogue import write_nb_catalogue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HurdleStateContext:
    """Context bundle handed to downstream states after S1 completes."""

    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    seed: int
    multi_merchant_ids: Tuple[int, ...]
    gated_streams: Tuple[GatedStream, ...]
    catalogue_path: Path

    @property
    def gated_dataset_ids(self) -> Tuple[str, ...]:
        """Return the dataset identifiers gated by the hurdle stream."""

        return tuple(stream.dataset_id for stream in self.gated_streams)

    def stream_by_dataset(self) -> Dict[str, GatedStream]:
        """Return a dictionary keyed by dataset identifier."""

        return {stream.dataset_id: stream for stream in self.gated_streams}


def build_hurdle_context(result: S1RunResult) -> HurdleStateContext:
    """Construct the downstream-facing context from an ``S1RunResult``."""

    return HurdleStateContext(
        parameter_hash=result.parameter_hash,
        manifest_fingerprint=result.manifest_fingerprint,
        run_id=result.run_id,
        seed=result.seed,
        multi_merchant_ids=result.multi_merchant_ids,
        gated_streams=result.gated_streams,
        catalogue_path=result.catalogue_path,
    )


@dataclass(frozen=True)
class S2StateContext:
    """Downstream context bundle produced after S2 NB sampling completes."""

    deterministic: S2DeterministicContext
    finals: Tuple[NBFinalRecord, ...]
    gamma_events_path: Path
    poisson_events_path: Path
    final_events_path: Path
    trace_path: Path
    metrics: Dict[str, float] | None
    catalogue_path: Path | None
    validation_artifacts_path: Path | None

    @property
    def parameter_hash(self) -> str:
        """Parameter hash carried across the S2 deterministic context."""

        return self.deterministic.parameter_hash

    @property
    def manifest_fingerprint(self) -> str:
        """Manifest fingerprint for the run."""

        return self.deterministic.manifest_fingerprint

    @property
    def run_id(self) -> str:
        """Run identifier used by the RNG envelopes."""

        return self.deterministic.run_id

    @property
    def seed(self) -> int:
        """Philox seed associated with the run."""

        return self.deterministic.seed

    def final_by_merchant(self) -> Dict[int, NBFinalRecord]:
        """Return the accepted NB outcome per merchant."""

        return {record.merchant_id: record for record in self.finals}

    def counts_by_merchant(self) -> Dict[int, Tuple[int, int]]:
        """Return ``(n_outlets, nb_rejections)`` for quick downstream use."""

        return {
            record.merchant_id: (record.n_outlets, record.nb_rejections)
            for record in self.finals
        }


def build_s2_context(
    result: S2RunResult,
    *,
    metrics: Dict[str, float] | None,
    catalogue_path: Path | None,
    validation_artifacts_path: Path | None,
) -> S2StateContext:
    """Construct the downstream-facing context from an ``S2RunResult``."""

    return S2StateContext(
        deterministic=result.deterministic,
        finals=result.finals,
        gamma_events_path=result.gamma_events_path,
        poisson_events_path=result.poisson_events_path,
        final_events_path=result.final_events_path,
        trace_path=result.trace_path,
        metrics=metrics,
        catalogue_path=catalogue_path,
        validation_artifacts_path=validation_artifacts_path,
    )


@dataclass(frozen=True)
class Segment1ARunResult:
    """Combined result for running S0 foundations, S1 hurdle, and S2 NB sampling."""

    s0_result: S0RunResult
    s1_result: S1RunResult
    s2_result: S2RunResult
    hurdle_context: HurdleStateContext
    nb_context: S2StateContext


class Segment1AOrchestrator:
    """Convenience wrapper that executes S0 foundations followed by S1 hurdle."""

    def __init__(self, *, schema_authority: SchemaAuthority | None = None) -> None:
        authority = schema_authority or SchemaAuthority(
            ingress_ref="l1/seg_1A/merchant_ids.schema.json",
            segment_ref="l1/seg_1A/s0_outputs.schema.json",
            rng_ref="layer1/schemas.layer1.yaml",
        )
        self._authority = authority
        self._s0_runner = S0FoundationsRunner(schema_authority=authority)
        self._s1_runner = S1HurdleRunner()
        self._s2_runner = S2NegativeBinomialRunner()

    def run(
        self,
        *,
        base_path: Path,
        merchant_table: Path,
        iso_table: Path,
        gdp_table: Path,
        bucket_table: Path,
        parameter_files: Mapping[str, Path],
        git_commit_hex: str,
        seed: int,
        numeric_policy_path: Path | None = None,
        math_profile_manifest_path: Path | None = None,
        include_diagnostics: bool = True,
        validate_s0: bool = True,
        validate_s1: bool = True,
        validate_s2: bool = True,
        extra_manifest_artifacts: Sequence[Path] | None = None,
        validation_policy_path: Path | None = None,
    ) -> Segment1ARunResult:
        base_path = base_path.expanduser().resolve()
        param_mapping = {
            name: Path(path).expanduser().resolve() for name, path in parameter_files.items()
        }
        extras = (
            [Path(item).expanduser().resolve() for item in extra_manifest_artifacts]
            if extra_manifest_artifacts
            else []
        )
        validation_policy: Mapping[str, object] | None = None
        if validation_policy_path is not None:
            policy_path = validation_policy_path.expanduser().resolve()
            data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, Mapping):
                raise err(
                    "ERR_S2_CORRIDOR_POLICY_MISSING",
                    f"validation policy at {policy_path} must decode to a mapping",
                )
            validation_policy = data

        logger.info(
            "Segment1A orchestrator starting (seed=%d, git_commit=%s, base_path=%s)",
            seed,
            git_commit_hex,
            base_path,
        )

        s0_result = self._s0_runner.run_from_paths(
            base_path=base_path,
            merchant_table_path=merchant_table.expanduser().resolve(),
            iso_table_path=iso_table.expanduser().resolve(),
            gdp_table_path=gdp_table.expanduser().resolve(),
            bucket_table_path=bucket_table.expanduser().resolve(),
            parameter_files=param_mapping,
            git_commit_hex=git_commit_hex,
            seed=seed,
            numeric_policy_path=(
                numeric_policy_path.expanduser().resolve()
                if numeric_policy_path is not None
                else None
            ),
            math_profile_manifest_path=(
                math_profile_manifest_path.expanduser().resolve()
                if math_profile_manifest_path is not None
                else None
            ),
            include_diagnostics=include_diagnostics,
            validate=validate_s0,
            extra_manifest_artifacts=extras,
        )

        logger.info(
            "Segment1A S0 completed (run_id=%s, parameter_hash=%s)",
            s0_result.run_id,
            s0_result.sealed.parameter_hash.parameter_hash,
        )

        design_vectors = tuple(
            iter_design_vectors(
                s0_result.sealed.context,
                hurdle=s0_result.outputs.hurdle_coefficients,
                dispersion=s0_result.outputs.dispersion_coefficients,
            )
        )
        design_rows: Tuple[HurdleDesignRow, ...] = tuple(
            HurdleDesignRow(
                merchant_id=vector.merchant_id,
                bucket_id=vector.bucket,
                design_vector=vector.x_hurdle,
            )
            for vector in design_vectors
        )

        s1_result = self._s1_runner.run(
            base_path=base_path,
            manifest_fingerprint=s0_result.sealed.manifest_fingerprint.manifest_fingerprint,
            parameter_hash=s0_result.sealed.parameter_hash.parameter_hash,
            beta=s0_result.outputs.hurdle_coefficients.beta,
            design_rows=design_rows,
            seed=seed,
            run_id=s0_result.run_id,
        )

        logger.info(
            "Segment1A S1 completed (multi_merchants=%d)",
            len(s1_result.multi_merchant_ids),
        )

        if validate_s1:
            validate_hurdle_run(
                base_path=base_path,
                manifest_fingerprint=s1_result.manifest_fingerprint,
                parameter_hash=s1_result.parameter_hash,
                seed=s1_result.seed,
                run_id=s1_result.run_id,
                beta=s0_result.outputs.hurdle_coefficients.beta,
                design_rows=design_rows,
            )
            logger.info("Segment1A S1 validation passed")

        hurdle_context = build_hurdle_context(s1_result)

        deterministic_context = build_deterministic_context(
            parameter_hash=s1_result.parameter_hash,
            manifest_fingerprint=s1_result.manifest_fingerprint,
            run_id=s1_result.run_id,
            seed=s1_result.seed,
            multi_merchant_ids=s1_result.multi_merchant_ids,
            decisions=s1_result.decisions,
            design_vectors=design_vectors,
            hurdle=s0_result.outputs.hurdle_coefficients,
            dispersion=s0_result.outputs.dispersion_coefficients,
        )

        logger.info(
            "Segment1A S2 deterministic context built (merchants=%d)",
            len(deterministic_context.rows),
        )

        s2_result = self._s2_runner.run(
            base_path=base_path,
            deterministic=deterministic_context,
        )

        logger.info(
            "Segment1A S2 completed (accepted_merchants=%d)",
            len(s2_result.finals),
        )

        metrics: Dict[str, float] | None = None
        validation_output_dir: Path | None = None
        validation_artifacts_path: Path | None = None
        if validate_s2:
            if validation_policy is None:
                raise err(
                    "ERR_S2_CORRIDOR_POLICY_MISSING",
                    "validation policy path must be supplied when validate_s2=True",
                )
            validation_output_dir = (
                base_path
                / "validation"
                / f"parameter_hash={deterministic_context.parameter_hash}"
                / f"run_id={deterministic_context.run_id}"
                / "s2"
            )
            metrics = validate_nb_run(
                base_path=base_path,
                deterministic=deterministic_context,
                expected_finals=s2_result.finals,
                policy=validation_policy,
                output_dir=validation_output_dir,
            )
            logger.info("Segment1A S2 validation passed")

        catalogue_path = write_nb_catalogue(
            base_path=base_path,
            parameter_hash=s2_result.deterministic.parameter_hash,
            multi_merchant_ids=hurdle_context.multi_merchant_ids,
            metrics=metrics,
        )
        if metrics is not None:
            validation_artifacts_path = publish_s2_validation_artifacts(
                base_path=base_path,
                manifest_fingerprint=s2_result.deterministic.manifest_fingerprint,
                metrics=metrics,
                validation_output_dir=validation_output_dir,
            )
        nb_context = build_s2_context(
            s2_result,
            metrics=metrics,
            catalogue_path=catalogue_path,
            validation_artifacts_path=validation_artifacts_path,
        )
        logger.info(
            "Segment1A orchestrator finished (run_id=%s)",
            s2_result.deterministic.run_id,
        )
        return Segment1ARunResult(
            s0_result=s0_result,
            s1_result=s1_result,
            s2_result=s2_result,
            hurdle_context=hurdle_context,
            nb_context=nb_context,
        )


__all__ = [
    "HurdleStateContext",
    "S2StateContext",
    "Segment1ARunResult",
    "Segment1AOrchestrator",
    "build_hurdle_context",
    "build_s2_context",
]
