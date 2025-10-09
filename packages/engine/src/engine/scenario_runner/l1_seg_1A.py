"""Scenario-runner helpers for Layer-1 Segment 1A states."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

from engine.layers.l1.seg_1A.s0_foundations import S0FoundationsRunner, SchemaAuthority
from engine.layers.l1.seg_1A.s0_foundations.l1.design import iter_design_vectors
from engine.layers.l1.seg_1A.s0_foundations.l2.runner import S0RunResult
from engine.layers.l1.seg_1A.s1_hurdle import HurdleDesignRow, S1HurdleRunner
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import S1RunResult
from engine.layers.l1.seg_1A.s1_hurdle.l3.catalogue import GatedStream
from engine.layers.l1.seg_1A.s1_hurdle.l3.validator import validate_hurdle_run


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
class Segment1ARunResult:
    """Combined result for running S0 Foundations followed by S1 hurdle."""

    s0_result: S0RunResult
    s1_result: S1RunResult
    hurdle_context: HurdleStateContext


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
        extra_manifest_artifacts: Sequence[Path] | None = None,
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

        design_rows: Tuple[HurdleDesignRow, ...] = tuple(
            HurdleDesignRow(
                merchant_id=vector.merchant_id,
                bucket_id=vector.bucket,
                design_vector=vector.x_hurdle,
            )
            for vector in iter_design_vectors(
                s0_result.sealed.context,
                hurdle=s0_result.outputs.hurdle_coefficients,
                dispersion=s0_result.outputs.dispersion_coefficients,
            )
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

        hurdle_context = build_hurdle_context(s1_result)
        return Segment1ARunResult(
            s0_result=s0_result,
            s1_result=s1_result,
            hurdle_context=hurdle_context,
        )


__all__ = [
    "HurdleStateContext",
    "Segment1ARunResult",
    "Segment1AOrchestrator",
    "build_hurdle_context",
]
