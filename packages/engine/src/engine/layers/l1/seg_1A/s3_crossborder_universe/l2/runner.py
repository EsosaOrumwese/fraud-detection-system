"""Orchestrator for the S3 cross-border universe state (L2)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

from ...s0_foundations.exceptions import err
from ..l0.policy import BaseWeightPolicy, BoundsPolicy, ThresholdsPolicy
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
        bounds_policy: BoundsPolicy | None = None,
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
            bounds_policy=bounds_policy,
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

        ranked = tuple(kernel_result.ranked_candidates)
        if not ranked:
            raise err("ERR_S3_CANDIDATE_CONSTRUCTION", "candidate set is empty")
        ranked_sorted = tuple(
            sorted(ranked, key=lambda row: (row.merchant_id, row.candidate_rank, row.country_iso))
        )

        schema = pa.schema(
            [
                ("parameter_hash", pa.string()),
                ("produced_by_fingerprint", pa.string()),
                ("merchant_id", pa.uint64()),
                ("country_iso", pa.string()),
                ("candidate_rank", pa.uint32()),
                ("is_home", pa.bool_()),
                ("reason_codes", pa.list_(pa.string())),
                ("filter_tags", pa.list_(pa.string())),
            ]
        )

        def _row_iter() -> Iterator[Mapping[str, object]]:
            for row in ranked_sorted:
                yield {
                    "parameter_hash": parameter_hash,
                    "produced_by_fingerprint": manifest_fingerprint,
                    "merchant_id": row.merchant_id,
                    "country_iso": row.country_iso,
                    "candidate_rank": row.candidate_rank,
                    "is_home": row.is_home,
                    "reason_codes": list(row.reason_codes),
                    "filter_tags": list(row.filter_tags),
                }

        output_path = resolve_dataset_path(
            "s3_candidate_set",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        self._write_parquet_rows(
            output_path,
            _row_iter(),
            schema,
            dataset="s3_candidate_set",
            expected_partitions={
                "parameter_hash": parameter_hash,
                "produced_by_fingerprint": manifest_fingerprint,
            },
        )
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

        sorted_priors = tuple(sorted(priors, key=lambda row: (row.merchant_id, row.country_iso)))

        schema = pa.schema(
            [
                ("parameter_hash", pa.string()),
                ("produced_by_fingerprint", pa.string()),
                ("merchant_id", pa.uint64()),
                ("country_iso", pa.string()),
                ("base_weight_dp", pa.string()),
                ("dp", pa.int64()),
            ]
        )

        def _row_iter() -> Iterator[Mapping[str, object]]:
            for row in sorted_priors:
                yield {
                    "parameter_hash": parameter_hash,
                    "produced_by_fingerprint": manifest_fingerprint,
                    "merchant_id": row.merchant_id,
                    "country_iso": row.country_iso,
                    "base_weight_dp": row.base_weight_dp,
                    "dp": row.dp,
                }

        output_path = resolve_dataset_path(
            "s3_base_weight_priors",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        self._write_parquet_rows(
            output_path,
            _row_iter(),
            schema,
            dataset="s3_base_weight_priors",
            expected_partitions={
                "parameter_hash": parameter_hash,
                "produced_by_fingerprint": manifest_fingerprint,
            },
        )
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

        sorted_counts = tuple(sorted(counts, key=lambda row: (row.merchant_id, row.country_iso)))

        schema = pa.schema(
            [
                ("parameter_hash", pa.string()),
                ("produced_by_fingerprint", pa.string()),
                ("merchant_id", pa.uint64()),
                ("country_iso", pa.string()),
                ("count", pa.int64()),
                ("residual_rank", pa.int64()),
            ]
        )

        def _row_iter() -> Iterator[Mapping[str, object]]:
            for row in sorted_counts:
                yield {
                    "parameter_hash": parameter_hash,
                    "produced_by_fingerprint": manifest_fingerprint,
                    "merchant_id": row.merchant_id,
                    "country_iso": row.country_iso,
                    "count": row.count,
                    "residual_rank": row.residual_rank,
                }

        output_path = resolve_dataset_path(
            "s3_integerised_counts",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        self._write_parquet_rows(
            output_path,
            _row_iter(),
            schema,
            dataset="s3_integerised_counts",
            expected_partitions={
                "parameter_hash": parameter_hash,
                "produced_by_fingerprint": manifest_fingerprint,
            },
        )
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

        sorted_sequence = tuple(
            sorted(sequence, key=lambda row: (row.merchant_id, row.country_iso, row.site_order))
        )

        schema = pa.schema(
            [
                ("parameter_hash", pa.string()),
                ("produced_by_fingerprint", pa.string()),
                ("merchant_id", pa.uint64()),
                ("country_iso", pa.string()),
                ("site_order", pa.uint32()),
                ("site_id", pa.string()),
            ]
        )

        def _row_iter() -> Iterator[Mapping[str, object]]:
            for row in sorted_sequence:
                yield {
                    "parameter_hash": parameter_hash,
                    "produced_by_fingerprint": manifest_fingerprint,
                    "merchant_id": row.merchant_id,
                    "country_iso": row.country_iso,
                    "site_order": row.site_order,
                    "site_id": row.site_id,
                }

        output_path = resolve_dataset_path(
            "s3_site_sequence",
            base_path=base_path,
            template_args=self._template_args(deterministic),
            dictionary=dictionary,
        )
        self._write_parquet_rows(
            output_path,
            _row_iter(),
            schema,
            dataset="s3_site_sequence",
            expected_partitions={
                "parameter_hash": parameter_hash,
                "produced_by_fingerprint": manifest_fingerprint,
            },
        )
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
    def _write_parquet_rows(
        output_path: Path,
        rows: Iterable[Mapping[str, object]],
        schema: pa.Schema,
        *,
        dataset: str,
        expected_partitions: Mapping[str, object],
        chunk_size: int = 8192,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer: pq.ParquetWriter | None = None
        rows_written = 0
        try:
            for batch in _chunked(rows, chunk_size):
                if not batch:
                    continue
                for row in batch:
                    for column, expected in expected_partitions.items():
                        value = row.get(column)
                        if value != expected:
                            raise err(
                                "ERR_S3_EGRESS_SHAPE",
                                f"{dataset} column '{column}' mismatch with expected partition '{expected}'",
                            )
                table = pa.Table.from_pylist(batch, schema=schema)
                if writer is None:
                    writer = pq.ParquetWriter(str(output_path), table.schema, compression="zstd")
                writer.write_table(table)
                rows_written += table.num_rows
        finally:
            if writer is not None:
                writer.close()

        if rows_written == 0:
            empty_payload = {
                field.name: pa.array([], type=field.type) for field in schema
            }
            table = pa.Table.from_pydict(empty_payload, schema=schema)
            pq.write_table(table, output_path, compression="zstd")


def _chunked(iterable: Iterable[Mapping[str, object]], size: int) -> Iterator[Sequence[Mapping[str, object]]]:
    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            break
        yield batch


__all__ = ["S3CrossBorderRunner", "S3RunResult"]
