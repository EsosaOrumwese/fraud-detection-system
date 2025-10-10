"""Orchestrator for the S3 cross-border universe state (L2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

import polars as pl

from ...s0_foundations.exceptions import err
from ..l0.policy import BaseWeightPolicy, ThresholdsPolicy
from ..l1.kernels import (
    S3FeatureToggles,
    S3KernelResult,
    run_kernels,
)
from ..l2.deterministic import S3DeterministicContext
from ...shared.dictionary import load_dictionary, resolve_dataset_path


@dataclass(frozen=True)
class S3RunResult:
    """Materialised artefacts emitted by the S3 runner."""

    deterministic: S3DeterministicContext
    candidate_set_path: Path
    base_weight_priors_path: Path | None = None
    integerised_counts_path: Path | None = None
    site_sequence_path: Path | None = None


class S3CrossBorderRunner:
    """High-level entry point that wires S3 deterministic kernels to I/O."""

    def run(
        self,
        *,
        base_path: Path,
        deterministic: S3DeterministicContext,
        rule_ladder_path: Path,
        toggles: S3FeatureToggles | None = None,
        base_weight_policy: BaseWeightPolicy | None = None,
        thresholds_policy: ThresholdsPolicy | None = None,
    ) -> S3RunResult:
        base_path = base_path.expanduser().resolve()
        toggles = toggles or S3FeatureToggles()
        dictionary = load_dictionary()
        kernel_result = run_kernels(
            deterministic=deterministic,
            artefact_path=rule_ladder_path.expanduser().resolve(),
            toggles=toggles,
            base_weight_policy=base_weight_policy,
            thresholds_policy=thresholds_policy,
        )
        candidate_path = self._write_candidate_set(
            base_path=base_path,
            deterministic=deterministic,
            kernel_result=kernel_result,
            dictionary=dictionary,
        )
        priors_path = (
            self._write_priors(
                base_path=base_path,
                deterministic=deterministic,
                priors=kernel_result.priors,
                dictionary=dictionary,
            )
            if kernel_result.priors is not None
            else None
        )
        counts_path = (
            self._write_counts(
                base_path=base_path,
                deterministic=deterministic,
                counts=kernel_result.counts,
                dictionary=dictionary,
            )
            if kernel_result.counts is not None
            else None
        )
        sequence_path = (
            self._write_sequence(
                base_path=base_path,
                deterministic=deterministic,
                sequence=kernel_result.sequence,
                dictionary=dictionary,
            )
            if kernel_result.sequence is not None
            else None
        )
        return S3RunResult(
            deterministic=deterministic,
            candidate_set_path=candidate_path,
            base_weight_priors_path=priors_path,
            integerised_counts_path=counts_path,
            site_sequence_path=sequence_path,
        )

    def _write_candidate_set(
        self,
        *,
        base_path: Path,
        deterministic: S3DeterministicContext,
        kernel_result: S3KernelResult,
        dictionary: Mapping[str, object],
    ) -> Path:
        parameter_hash = deterministic.parameter_hash
        manifest_fingerprint = deterministic.manifest_fingerprint

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
        output_path = resolve_dataset_path(
            "s3_candidate_set",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(output_path, compression="zstd")
        return output_path

    def _write_priors(
        self,
        *,
        base_path: Path,
        deterministic: S3DeterministicContext,
        priors: Tuple,
        dictionary: Mapping[str, object],
    ) -> Path:
        parameter_hash = deterministic.parameter_hash
        manifest_fingerprint = deterministic.manifest_fingerprint

        data = {
            "parameter_hash": [],
            "produced_by_fingerprint": [],
            "merchant_id": [],
            "country_iso": [],
            "base_weight_dp": [],
            "dp": [],
        }
        for row in priors:
            data["parameter_hash"].append(parameter_hash)
            data["produced_by_fingerprint"].append(manifest_fingerprint)
            data["merchant_id"].append(row.merchant_id)
            data["country_iso"].append(row.country_iso)
            data["base_weight_dp"].append(row.base_weight_dp)
            data["dp"].append(row.dp)

        frame = pl.DataFrame(data).sort(["merchant_id", "country_iso"])
        self._assert_partition_value(
            frame,
            column="parameter_hash",
            expected=parameter_hash,
            dataset="s3_base_weight_priors",
        )
        self._assert_partition_value(
            frame,
            column="produced_by_fingerprint",
            expected=manifest_fingerprint,
            dataset="s3_base_weight_priors",
        )
        output_path = resolve_dataset_path(
            "s3_base_weight_priors",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(output_path, compression="zstd")
        return output_path

    def _write_counts(
        self,
        *,
        base_path: Path,
        deterministic: S3DeterministicContext,
        counts: Tuple,
        dictionary: Mapping[str, object],
    ) -> Path:
        parameter_hash = deterministic.parameter_hash
        manifest_fingerprint = deterministic.manifest_fingerprint

        data = {
            "parameter_hash": [],
            "produced_by_fingerprint": [],
            "merchant_id": [],
            "country_iso": [],
            "count": [],
            "residual_rank": [],
        }
        for row in counts:
            data["parameter_hash"].append(parameter_hash)
            data["produced_by_fingerprint"].append(manifest_fingerprint)
            data["merchant_id"].append(row.merchant_id)
            data["country_iso"].append(row.country_iso)
            data["count"].append(row.count)
            data["residual_rank"].append(row.residual_rank)

        frame = pl.DataFrame(data).sort(["merchant_id", "country_iso"])
        self._assert_partition_value(
            frame,
            column="parameter_hash",
            expected=parameter_hash,
            dataset="s3_integerised_counts",
        )
        self._assert_partition_value(
            frame,
            column="produced_by_fingerprint",
            expected=manifest_fingerprint,
            dataset="s3_integerised_counts",
        )
        output_path = resolve_dataset_path(
            "s3_integerised_counts",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(output_path, compression="zstd")
        return output_path

    def _write_sequence(
        self,
        *,
        base_path: Path,
        deterministic: S3DeterministicContext,
        sequence: Tuple,
        dictionary: Mapping[str, object],
    ) -> Path:
        parameter_hash = deterministic.parameter_hash
        manifest_fingerprint = deterministic.manifest_fingerprint

        data = {
            "parameter_hash": [],
            "produced_by_fingerprint": [],
            "merchant_id": [],
            "country_iso": [],
            "site_order": [],
            "site_id": [],
        }
        for row in sequence:
            data["parameter_hash"].append(parameter_hash)
            data["produced_by_fingerprint"].append(manifest_fingerprint)
            data["merchant_id"].append(row.merchant_id)
            data["country_iso"].append(row.country_iso)
            data["site_order"].append(row.site_order)
            data["site_id"].append(row.site_id)

        frame = pl.DataFrame(data).sort(["merchant_id", "country_iso", "site_order"])
        self._assert_partition_value(
            frame,
            column="parameter_hash",
            expected=parameter_hash,
            dataset="s3_site_sequence",
        )
        self._assert_partition_value(
            frame,
            column="produced_by_fingerprint",
            expected=manifest_fingerprint,
            dataset="s3_site_sequence",
        )
        output_path = resolve_dataset_path(
            "s3_site_sequence",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(output_path, compression="zstd")
        return output_path

    @staticmethod
    def _template_args(deterministic: S3DeterministicContext) -> Mapping[str, object]:
        """Build template arguments for dataset dictionary rendering."""

        return {
            "parameter_hash": deterministic.parameter_hash,
            "manifest_fingerprint": deterministic.manifest_fingerprint,
            "seed": deterministic.seed,
            "run_id": deterministic.run_id,
        }

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
