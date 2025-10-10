"""Orchestrator for the S3 cross-border universe state (L2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from ...s0_foundations.exceptions import err
from ..l1.kernels import (
    S3FeatureToggles,
    S3KernelResult,
    run_kernels,
)
from ..l2.deterministic import S3DeterministicContext


@dataclass(frozen=True)
class S3RunResult:
    """Materialised artefacts emitted by the S3 runner."""

    deterministic: S3DeterministicContext
    candidate_set_path: Path


class S3CrossBorderRunner:
    """High-level entry point that wires S3 deterministic kernels to I/O."""

    def run(
        self,
        *,
        base_path: Path,
        deterministic: S3DeterministicContext,
        rule_ladder_path: Path,
        toggles: S3FeatureToggles | None = None,
    ) -> S3RunResult:
        base_path = base_path.expanduser().resolve()
        toggles = toggles or S3FeatureToggles()
        kernel_result = run_kernels(
            deterministic=deterministic,
            artefact_path=rule_ladder_path.expanduser().resolve(),
            toggles=toggles,
        )
        candidate_path = self._write_candidate_set(
            base_path=base_path,
            deterministic=deterministic,
            kernel_result=kernel_result,
        )
        return S3RunResult(
            deterministic=deterministic,
            candidate_set_path=candidate_path,
        )

    def _write_candidate_set(
        self,
        *,
        base_path: Path,
        deterministic: S3DeterministicContext,
        kernel_result: S3KernelResult,
    ) -> Path:
        parameter_hash = deterministic.parameter_hash
        manifest_fingerprint = deterministic.manifest_fingerprint

        parameter_dir = (
            base_path / "parameter_scoped" / f"parameter_hash={parameter_hash}"
        )
        parameter_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "parameter_hash": [],
            "produced_by_fingerprint": [],
            "merchant_id": [],
            "country_iso": [],
            "candidate_rank": [],
            "is_home": [],
            "reason_codes": [],
            "filter_tags": [],
        }
        for row in kernel_result.ranked_candidates:
            data["parameter_hash"].append(parameter_hash)
            data["produced_by_fingerprint"].append(manifest_fingerprint)
            data["merchant_id"].append(row.merchant_id)
            data["country_iso"].append(row.country_iso)
            data["candidate_rank"].append(row.candidate_rank)
            data["is_home"].append(row.is_home)
            data["reason_codes"].append(list(row.reason_codes))
            data["filter_tags"].append(list(row.filter_tags))

        frame = pl.DataFrame(data)
        if frame.height == 0:
            raise err("ERR_S3_CANDIDATE_CONSTRUCTION", "candidate set is empty")
        frame = frame.sort(["merchant_id", "candidate_rank", "country_iso"])

        self._assert_partition_value(
            frame,
            column="parameter_hash",
            expected=parameter_hash,
            dataset="s3_candidate_set",
        )
        self._assert_partition_value(
            frame,
            column="produced_by_fingerprint",
            expected=manifest_fingerprint,
            dataset="s3_candidate_set",
        )

        output_path = parameter_dir / "s3_candidate_set.parquet"
        frame.write_parquet(output_path, compression="zstd")
        return output_path

    @staticmethod
    def _assert_partition_value(
        frame: pl.DataFrame,
        *,
        column: str,
        expected: str,
        dataset: str,
    ) -> None:
        if column not in frame.columns:
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"{dataset} missing required column '{column}'",
            )
        series = frame.get_column(column)
        if series.null_count() > 0:
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"{dataset} column '{column}' contains nulls",
            )
        if not bool((series == expected).all()):
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"{dataset} column '{column}' mismatch with expected partition '{expected}'",
            )


__all__ = ["S3CrossBorderRunner", "S3RunResult"]
