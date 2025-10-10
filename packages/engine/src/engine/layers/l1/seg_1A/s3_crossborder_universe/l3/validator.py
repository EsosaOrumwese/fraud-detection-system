"""Validation helpers for S3 cross-border universe outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import polars as pl

from ...s0_foundations.exceptions import err
from ..l0.policy import BaseWeightPolicy, ThresholdsPolicy
from ..l0.types import CountRow, PriorRow, RankedCandidateRow
from ..l1.kernels import S3FeatureToggles, run_kernels
from ..l2.deterministic import S3DeterministicContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S3ValidationResult:
    """Summary of S3 validation outcomes."""

    metrics: Mapping[str, float]
    _failed_merchants: Mapping[int, str] = field(default_factory=dict, repr=False)

    @property
    def failed_merchants(self) -> Mapping[int, str]:
        return getattr(self, "_failed_merchants", {})

    @failed_merchants.setter
    def failed_merchants(self, value: Mapping[int, str]) -> None:
        object.__setattr__(self, "_failed_merchants", value)

    @property
    def passed(self) -> bool:
        return not bool(getattr(self, "_failed_merchants", {}))


def _ensure_dataset_exists(path: Path | None, dataset: str) -> Path:
    if path is None:
        raise err("ERR_S3_EGRESS_SHAPE", f"{dataset} output missing (path=None)")
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            f"{dataset} output missing at '{resolved}'",
        )
    return resolved


def _assert_partition_column(
    frame: pl.DataFrame,
    *,
    column: str,
    expected: str,
    dataset: str,
) -> None:
    if column not in frame.columns:
        raise err("ERR_S3_EGRESS_SHAPE", f"{dataset} missing column '{column}'")
    series = frame.get_column(column)
    if series.null_count() > 0:
        raise err("ERR_S3_EGRESS_SHAPE", f"{dataset} column '{column}' contains nulls")
    if not bool((series == expected).all()):
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            f"{dataset} partition column '{column}' mismatch (expected '{expected}')",
        )


def _sorted_tuple(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted(str(value) for value in values))


def _group_expected_candidates(
    rows: Sequence[RankedCandidateRow],
) -> Dict[int, List[RankedCandidateRow]]:
    grouped: Dict[int, List[RankedCandidateRow]] = {}
    for row in rows:
        grouped.setdefault(row.merchant_id, []).append(row)
    return grouped


def _group_expected_priors(rows: Sequence[PriorRow] | None) -> Dict[Tuple[int, str], PriorRow]:
    if not rows:
        return {}
    return {(row.merchant_id, row.country_iso): row for row in rows}


def _group_expected_counts(rows: Sequence[CountRow] | None) -> Dict[Tuple[int, str], CountRow]:
    if not rows:
        return {}
    return {(row.merchant_id, row.country_iso): row for row in rows}


def _group_expected_sequence(
    rows: Sequence
    | None,
) -> Dict[Tuple[int, str, int], Tuple[int, str | None]]:
    if not rows:
        return {}
    return {
        (row.merchant_id, row.country_iso, row.site_order): (row.site_order, row.site_id)
        for row in rows
    }


def _assert_unique(
    frame: pl.DataFrame,
    columns: list[str],
    dataset: str,
    error_code: str = "ERR_S3_DUPLICATE_ROW",
) -> None:
    if frame.height == 0:
        return
    dup_counts = (
        frame.group_by(columns)
        .agg(pl.len().alias("_count"))
        .filter(pl.col("_count") > 1)
    )
    if dup_counts.height > 0:
        keys = dup_counts.select(pl.struct(columns)).to_series().to_list()
        raise err(
            error_code,
            f"{dataset} contains duplicate keys {keys}",
        )


def validate_s3_outputs(
    *,
    deterministic: S3DeterministicContext,
    candidate_set_path: Path,
    rule_ladder_path: Path,
    toggles: S3FeatureToggles,
    base_weight_policy: BaseWeightPolicy | None = None,
    thresholds_policy: ThresholdsPolicy | None = None,
    base_weight_priors_path: Path | None = None,
    integerised_counts_path: Path | None = None,
    site_sequence_path: Path | None = None,
) -> S3ValidationResult:
    """Validate all S3 materialised outputs against deterministic expectations."""

    toggles.validate()

    candidate_path = _ensure_dataset_exists(candidate_set_path, "s3_candidate_set")
    candidate_frame = pl.read_parquet(candidate_path)
    if candidate_frame.height == 0:
        raise err("ERR_S3_EGRESS_SHAPE", "s3_candidate_set is empty")
    if any(candidate_frame[col].null_count() > 0 for col in candidate_frame.columns):
        raise err("ERR_S3_EGRESS_SHAPE", "s3_candidate_set contains null values")
    _assert_partition_column(
        candidate_frame,
        column="parameter_hash",
        expected=deterministic.parameter_hash,
        dataset="s3_candidate_set",
    )
    if "produced_by_fingerprint" in candidate_frame.columns:
        _assert_partition_column(
            candidate_frame,
            column="produced_by_fingerprint",
            expected=deterministic.manifest_fingerprint,
            dataset="s3_candidate_set",
        )

    _assert_unique(
        candidate_frame,
        ["merchant_id", "country_iso"],
        "s3_candidate_set",
    )
    _assert_unique(
        candidate_frame,
        ["merchant_id", "candidate_rank"],
        "s3_candidate_set",
    )

    kernel_result = run_kernels(
        deterministic=deterministic,
        artefact_path=rule_ladder_path.expanduser().resolve(),
        toggles=toggles,
        base_weight_policy=base_weight_policy,
        thresholds_policy=thresholds_policy,
    )

    expected_candidates = _group_expected_candidates(kernel_result.ranked_candidates)
    actual_candidates: Dict[int, List[dict]] = {}
    for row in candidate_frame.sort(["merchant_id", "candidate_rank"]).to_dicts():
        merchant_id = int(row["merchant_id"])
        actual_candidates.setdefault(merchant_id, []).append(row)

    expected_merchants = set(expected_candidates.keys())
    actual_merchants = set(actual_candidates.keys())
    if expected_merchants != actual_merchants:
        missing = expected_merchants - actual_merchants
        extra = actual_merchants - expected_merchants
        if missing:
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"s3_candidate_set missing merchants {sorted(missing)}",
            )
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            f"s3_candidate_set contains unexpected merchants {sorted(extra)}",
        )

    eligible_crossborder = 0
    for merchant_id, expected_rows in expected_candidates.items():
        actual_rows = actual_candidates.get(merchant_id, [])
        if len(actual_rows) != len(expected_rows):
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"merchant {merchant_id} candidate count mismatch "
                f"(expected {len(expected_rows)}, found {len(actual_rows)})",
            )
        seen_countries: set[str] = set()
        for index, (expected_row, actual_row) in enumerate(zip(expected_rows, actual_rows)):
            country = str(actual_row["country_iso"])
            if country in seen_countries:
                raise err(
                    "ERR_S3_ORDERING_UNSTABLE",
                    f"merchant {merchant_id} has duplicate country '{country}'",
                )
            seen_countries.add(country)
            candidate_rank = int(actual_row["candidate_rank"])
            if candidate_rank != index:
                raise err(
                    "ERR_S3_ORDERING_NONCONTIGUOUS",
                    f"merchant {merchant_id} candidate ranks not contiguous",
                )
            is_home = bool(actual_row["is_home"])
            if is_home != expected_row.is_home or country != expected_row.country_iso:
                raise err(
                    "ERR_S3_ORDERING_UNSTABLE",
                    f"merchant {merchant_id} candidate mismatch for rank {index}",
                )
            if index == 0 and not is_home:
                raise err(
                    "ERR_S3_ORDERING_HOME_MISSING",
                    f"merchant {merchant_id} missing home row at rank 0",
                )
            actual_reasons = _sorted_tuple(actual_row.get("reason_codes", []))
            expected_reasons = _sorted_tuple(expected_row.reason_codes)
            if actual_reasons != expected_reasons:
                raise err(
                    "ERR_S3_EGRESS_SHAPE",
                    f"merchant {merchant_id} reason_codes mismatch for {country}",
                )
            actual_tags = _sorted_tuple(actual_row.get("filter_tags", []))
            expected_tags = _sorted_tuple(expected_row.filter_tags)
            if actual_tags != expected_tags:
                raise err(
                    "ERR_S3_EGRESS_SHAPE",
                    f"merchant {merchant_id} filter_tags mismatch for {country}",
                )
        if len(expected_rows) > 1:
            eligible_crossborder += 1

    priors_map = _group_expected_priors(kernel_result.priors)
    priors_rows = len(priors_map)
    priors_root: Path | None = None
    if toggles.priors_enabled:
        if base_weight_policy is None:
            raise err(
                "ERR_S3_PRIOR_DISABLED",
                "base-weight policy required when priors are enabled",
            )
        priors_root = _ensure_dataset_exists(base_weight_priors_path, "s3_base_weight_priors")
        priors_frame = pl.read_parquet(priors_root)
        if priors_frame.height == 0:
            raise err("ERR_S3_PRIOR_DOMAIN", "s3_base_weight_priors is empty")
        _assert_partition_column(
            priors_frame,
            column="parameter_hash",
            expected=deterministic.parameter_hash,
            dataset="s3_base_weight_priors",
        )
        if "produced_by_fingerprint" in priors_frame.columns:
            _assert_partition_column(
                priors_frame,
                column="produced_by_fingerprint",
                expected=deterministic.manifest_fingerprint,
                dataset="s3_base_weight_priors",
            )
        _assert_unique(
            priors_frame,
            ["merchant_id", "country_iso"],
            "s3_base_weight_priors",
        )
        actual_keys = set()
        for row in priors_frame.to_dicts():
            merchant_id = int(row["merchant_id"])
            country = str(row["country_iso"])
            dp_value = int(row["dp"])
            key = (merchant_id, country)
            actual_keys.add(key)
            expected_row = priors_map.get(key)
            if expected_row is None:
                raise err(
                    "ERR_S3_EGRESS_SHAPE",
                    f"s3_base_weight_priors has unexpected row ({merchant_id}, {country})",
                )
            if dp_value != expected_row.dp:
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    f"s3_base_weight_priors dp mismatch for ({merchant_id}, {country})",
                )
            actual_weight = str(row["base_weight_dp"])
            if actual_weight != expected_row.base_weight_dp:
                raise err(
                    "ERR_S3_PRIOR_DOMAIN",
                    f"s3_base_weight_priors weight mismatch for ({merchant_id}, {country})",
                )
        if actual_keys != set(priors_map.keys()):
            missing = set(priors_map.keys()) - actual_keys
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"s3_base_weight_priors missing rows {sorted(missing)}",
            )
    else:
        if base_weight_priors_path is not None and base_weight_priors_path.exists():
            raise err(
                "ERR_S3_PRIOR_DISABLED",
                "priors output present but priors feature disabled",
            )

    counts_map = _group_expected_counts(kernel_result.counts)
    counts_rows = len(counts_map)
    counts_root: Path | None = None
    if toggles.integerisation_enabled:
        counts_root = _ensure_dataset_exists(integerised_counts_path, "s3_integerised_counts")
        counts_frame = pl.read_parquet(counts_root)
        if counts_frame.height == 0:
            raise err("ERR_S3_INTEGER_SUM_MISMATCH", "s3_integerised_counts is empty")
        _assert_partition_column(
            counts_frame,
            column="parameter_hash",
            expected=deterministic.parameter_hash,
            dataset="s3_integerised_counts",
        )
        if "produced_by_fingerprint" in counts_frame.columns:
            _assert_partition_column(
                counts_frame,
                column="produced_by_fingerprint",
                expected=deterministic.manifest_fingerprint,
                dataset="s3_integerised_counts",
            )
        _assert_unique(
            counts_frame,
            ["merchant_id", "country_iso"],
            "s3_integerised_counts",
        )
        counts_by_merchant: Dict[int, int] = {}
        actual_keys = set()
        for row in counts_frame.to_dicts():
            merchant_id = int(row["merchant_id"])
            country = str(row["country_iso"])
            key = (merchant_id, country)
            actual_keys.add(key)
            expected_row = counts_map.get(key)
            if expected_row is None:
                raise err(
                    "ERR_S3_EGRESS_SHAPE",
                    f"s3_integerised_counts has unexpected row ({merchant_id}, {country})",
                )
            actual_count = int(row["count"])
            if actual_count != expected_row.count:
                raise err(
                    "ERR_S3_INTEGER_SUM_MISMATCH",
                    f"count mismatch for ({merchant_id}, {country})",
                )
            actual_rank = int(row["residual_rank"])
            if actual_rank != expected_row.residual_rank:
                raise err(
                    "ERR_S3_INTEGER_SUM_MISMATCH",
                    f"residual rank mismatch for ({merchant_id}, {country})",
                )
            counts_by_merchant[merchant_id] = (
                counts_by_merchant.get(merchant_id, 0) + actual_count
            )
        if actual_keys != set(counts_map.keys()):
            missing = set(counts_map.keys()) - actual_keys
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"s3_integerised_counts missing rows {sorted(missing)}",
            )
        expected_totals = {merchant.merchant_id: merchant.n_outlets for merchant in deterministic.merchants}
        for merchant_id, total in counts_by_merchant.items():
            expected_total = expected_totals.get(merchant_id)
            if expected_total is None:
                raise err(
                    "ERR_S3_INTEGER_SUM_MISMATCH",
                    f"integerised count found for unknown merchant {merchant_id}",
                )
            if total != expected_total:
                raise err(
                    "ERR_S3_INTEGER_SUM_MISMATCH",
                    f"integerised counts sum {total} != N {expected_total} for merchant {merchant_id}",
                )
    else:
        if integerised_counts_path is not None and integerised_counts_path.exists():
            raise err(
                "ERR_S3_INTEGER_SUM_MISMATCH",
                "integerised counts output present but integerisation disabled",
            )

    sequence_rows = 0
    sequence_root: Path | None = None
    if toggles.sequencing_enabled:
        sequence_root = _ensure_dataset_exists(site_sequence_path, "s3_site_sequence")
        sequence_frame = pl.read_parquet(sequence_root)
        _assert_partition_column(
            sequence_frame,
            column="parameter_hash",
            expected=deterministic.parameter_hash,
            dataset="s3_site_sequence",
        )
        if "produced_by_fingerprint" in sequence_frame.columns:
            _assert_partition_column(
                sequence_frame,
                column="produced_by_fingerprint",
                expected=deterministic.manifest_fingerprint,
                dataset="s3_site_sequence",
            )
        _assert_unique(
            sequence_frame,
            ["merchant_id", "country_iso", "site_order"],
            "s3_site_sequence",
        )
        if "site_id" in sequence_frame.columns:
            _assert_unique(
                sequence_frame.drop_nulls("site_id"),
                ["merchant_id", "country_iso", "site_id"],
                "s3_site_sequence",
            )
        expected_sequence = _group_expected_sequence(kernel_result.sequence)
        sequence_rows = len(expected_sequence)
        actual_keys = set()
        for row in sequence_frame.to_dicts():
            merchant_id = int(row["merchant_id"])
            country = str(row["country_iso"])
            site_order = int(row["site_order"])
            site_id = row.get("site_id")
            key = (merchant_id, country, site_order)
            actual_keys.add(key)
            expected = expected_sequence.get(key)
            if expected is None:
                raise err(
                    "ERR_S3_SEQUENCE_GAP",
                    f"s3_site_sequence has unexpected row ({merchant_id}, {country}, {site_order})",
                )
            if site_id is None or str(site_id) != f"{site_order:06d}":
                raise err(
                    "ERR_S3_SITE_SEQUENCE_OVERFLOW",
                    f"s3_site_sequence site_id mismatch for ({merchant_id}, {country}, {site_order})",
                )
        if actual_keys != set(expected_sequence.keys()):
            missing = set(expected_sequence.keys()) - actual_keys
            raise err(
                "ERR_S3_SEQUENCE_GAP",
                f"s3_site_sequence missing rows {sorted(missing)}",
            )
    else:
        if site_sequence_path is not None and site_sequence_path.exists():
            raise err(
                "ERR_S3_SEQUENCE_GAP",
                "site sequence output present but sequencing disabled",
            )

    metrics: Dict[str, float] = {
        "version": 1.0,
        "merchant_count": float(len(expected_merchants)),
        "candidate_rows": float(len(kernel_result.ranked_candidates)),
        "eligible_crossborder_merchants": float(eligible_crossborder),
        "priors_enabled": 1.0 if toggles.priors_enabled else 0.0,
        "priors_rows": float(priors_rows),
        "integerisation_enabled": 1.0 if toggles.integerisation_enabled else 0.0,
        "integerised_rows": float(counts_rows),
        "sequencing_enabled": 1.0 if toggles.sequencing_enabled else 0.0,
        "sequence_rows": float(sequence_rows),
        "total_outlets": float(sum(merchant.n_outlets for merchant in deterministic.merchants)),
    }
    logger.info(
        "S3 validator: merchants=%d candidates=%d priors=%d counts=%d sequence=%d",
        int(metrics["merchant_count"]),
        int(metrics["candidate_rows"]),
        int(metrics["priors_rows"]),
        int(metrics["integerised_rows"]),
        int(metrics["sequence_rows"]),
    )
    return S3ValidationResult(metrics=metrics)


def validate_s3_candidate_set(
    *,
    deterministic: S3DeterministicContext,
    candidate_set_path: Path,
    rule_ladder_path: Path,
) -> None:
    """Backwards compatible wrapper that validates only the candidate set."""

    validate_s3_outputs(
        deterministic=deterministic,
        candidate_set_path=candidate_set_path,
        rule_ladder_path=rule_ladder_path,
        toggles=S3FeatureToggles(),
    )


__all__ = ["S3ValidationResult", "validate_s3_outputs", "validate_s3_candidate_set"]
