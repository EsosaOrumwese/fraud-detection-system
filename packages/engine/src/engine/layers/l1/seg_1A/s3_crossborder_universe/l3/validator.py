"""Validation helpers for S3 cross-border universe outputs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import polars as pl
from jsonschema import Draft201909Validator, ValidationError

from ...s0_foundations.exceptions import err
from ..l0.policy import BaseWeightPolicy, ThresholdsPolicy
from ..l0.types import CountRow, PriorRow, RankedCandidateRow
from ..l1.kernels import S3FeatureToggles, run_kernels
from ..l2.deterministic import S3DeterministicContext
from ...shared.dictionary import get_repo_root

logger = logging.getLogger(__name__)

_SCHEMA_VALIDATORS: Dict[str, Draft201909Validator] | None = None
_SCHEMA_FILE_RELATIVE = Path("contracts/schemas/l1/seg_1A/s3_outputs.schema.json")
_SCHEMA_SKIP_KEYS = {"$schema", "$id", "title", "description"}


@dataclass(frozen=True)
class S3ValidationResult:
    """Summary of S3 validation outcomes."""

    metrics: Mapping[str, float]
    passed: bool = True
    failed_merchants: Mapping[int, str] = field(default_factory=dict, repr=False)
    diagnostics: Tuple[Mapping[str, object], ...] = field(default_factory=tuple, repr=False)


def _schema_validators() -> Dict[str, Draft201909Validator]:
    """Lazily load and cache JSON-Schema validators for S3 outputs."""

    global _SCHEMA_VALIDATORS
    if _SCHEMA_VALIDATORS is not None:
        return _SCHEMA_VALIDATORS

    schema_path = get_repo_root() / _SCHEMA_FILE_RELATIVE
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise err("E_SCHEMA_NOT_FOUND", f"S3 schema file missing at '{schema_path}'") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise err("E_SCHEMA_FORMAT", f"S3 schema file '{schema_path}' is not valid JSON") from exc

    validators: Dict[str, Draft201909Validator] = {}
    for key, schema in payload.items():
        if key in _SCHEMA_SKIP_KEYS:
            continue
        try:
            validators[key] = Draft201909Validator(schema)
        except Exception as exc:  # pragma: no cover - jsonschema raises various subclasses
            raise err(
                "E_SCHEMA_FORMAT",
                f"S3 schema '{schema_path}' key '{key}' could not be compiled: {exc}",
            ) from exc
    _SCHEMA_VALIDATORS = validators
    return validators


def _validate_schema_array(section: str, rows: Sequence[Mapping[str, object]]) -> None:
    """Validate ``rows`` against the named schema section."""

    validators = _schema_validators()
    validator = validators.get(section)
    if validator is None:
        raise err(
            "E_SCHEMA_POINTER",
            f"S3 schema does not define section '{section}'",
        )
    try:
        validator.validate(list(rows))
    except ValidationError as exc:
        raise err(
            "ERR_S3_SCHEMA_VALIDATION",
            f"S3 schema validation failed for '{section}': {exc.message}",
        ) from exc


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


def _threshold_bounds_for_merchant(
    policy: ThresholdsPolicy | None,
    rows: Sequence[RankedCandidateRow],
    *,
    n_outlets: int,
) -> tuple[Dict[str, int], Dict[str, int | None]]:
    if policy is None or not policy.enabled:
        return {}, {}
    if not rows:
        return {}, {}
    home_rows = [row for row in rows if row.is_home]
    if len(home_rows) != 1:
        raise err(
            "ERR_S3_INTEGER_FEASIBILITY",
            "candidate set must contain exactly one home row for bounds",
        )
    num_candidates = len(rows)
    L_home = min(int(policy.home_min), int(n_outlets))
    if (
        policy.force_at_least_one_foreign_if_foreign_present
        and num_candidates > 1
        and n_outlets >= 2
    ):
        U_home = int(n_outlets) - 1
    else:
        U_home = int(n_outlets)
    if policy.min_one_per_country_when_feasible and n_outlets >= num_candidates and n_outlets >= 2:
        L_foreign = 1
    else:
        L_foreign = 0
    if policy.foreign_cap_mode == "n_minus_home_min":
        U_foreign = max(L_foreign, int(n_outlets) - L_home)
    else:
        U_foreign = int(n_outlets)

    floors: Dict[str, int] = {}
    ceilings: Dict[str, int | None] = {}
    for row in rows:
        if row.is_home:
            floors[row.country_iso] = L_home
            ceilings[row.country_iso] = U_home
        else:
            floors[row.country_iso] = L_foreign
            ceilings[row.country_iso] = U_foreign
    return floors, ceilings


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

    merchants_map = {merchant.merchant_id: merchant for merchant in deterministic.merchants}

    candidate_root = _ensure_dataset_exists(candidate_set_path, "s3_candidate_set")
    candidate_frame = (
        pl.read_parquet(candidate_root)
        .sort(["merchant_id", "candidate_rank", "country_iso"])
    )
    _validate_schema_array("candidate_set", candidate_frame.to_dicts())
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
    _assert_unique(candidate_frame, ["merchant_id", "country_iso"], "s3_candidate_set")
    _assert_unique(candidate_frame, ["merchant_id", "candidate_rank"], "s3_candidate_set")

    kernel_result = run_kernels(
        deterministic=deterministic,
        artefact_path=rule_ladder_path.expanduser().resolve(),
        toggles=toggles,
        base_weight_policy=base_weight_policy,
        thresholds_policy=thresholds_policy,
    )

    expected_candidates = _group_expected_candidates(kernel_result.ranked_candidates)
    expected_priors = _group_expected_priors(kernel_result.priors)
    expected_counts = _group_expected_counts(kernel_result.counts)
    expected_sequence = _group_expected_sequence(kernel_result.sequence)

    actual_candidates: Dict[int, List[dict]] = {}
    for row in candidate_frame.to_dicts():
        merchant_id = int(row["merchant_id"])
        actual_candidates.setdefault(merchant_id, []).append(row)

    actual_priors: Dict[Tuple[int, str], Mapping[str, object]] = {}
    priors_by_merchant: Dict[int, List[Mapping[str, object]]] = {}
    priors_rows = 0
    priors_merchants = 0
    priors_total_weight = Decimal("0")

    if toggles.priors_enabled:
        priors_root = _ensure_dataset_exists(base_weight_priors_path, "s3_base_weight_priors")
        priors_frame = pl.read_parquet(priors_root).sort(["merchant_id", "country_iso"])
        _validate_schema_array("base_weight_priors", priors_frame.to_dicts())
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
        _assert_unique(priors_frame, ["merchant_id", "country_iso"], "s3_base_weight_priors")
        for row in priors_frame.to_dicts():
            merchant_id = int(row["merchant_id"])
            country = str(row["country_iso"])
            actual_priors[(merchant_id, country)] = row
            priors_by_merchant.setdefault(merchant_id, []).append(row)
            priors_total_weight += Decimal(str(row["base_weight_dp"]))
        priors_rows = len(actual_priors)
        priors_merchants = len(priors_by_merchant)
    else:
        if base_weight_priors_path is not None and base_weight_priors_path.exists():
            raise err(
                "ERR_S3_PRIOR_DISABLED",
                "base-weight priors output present but priors disabled",
            )

    actual_counts: Dict[Tuple[int, str], Mapping[str, object]] = {}
    counts_by_merchant: Dict[int, List[Mapping[str, object]]] = {}
    counts_rows = 0
    counts_merchants = 0

    if toggles.integerisation_enabled:
        counts_root = _ensure_dataset_exists(integerised_counts_path, "s3_integerised_counts")
        counts_frame = pl.read_parquet(counts_root).sort(["merchant_id", "country_iso"])
        _validate_schema_array("integerised_counts", counts_frame.to_dicts())
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
        _assert_unique(counts_frame, ["merchant_id", "country_iso"], "s3_integerised_counts")
        for row in counts_frame.to_dicts():
            merchant_id = int(row["merchant_id"])
            country = str(row["country_iso"])
            actual_counts[(merchant_id, country)] = row
            counts_by_merchant.setdefault(merchant_id, []).append(row)
        counts_rows = len(actual_counts)
        counts_merchants = len(counts_by_merchant)
    else:
        if integerised_counts_path is not None and integerised_counts_path.exists():
            raise err(
                "ERR_S3_INTEGER_SUM_MISMATCH",
                "integerised counts output present but integerisation disabled",
            )

    actual_sequence: Dict[Tuple[int, str, int], Mapping[str, object]] = {}
    sequence_by_merchant: Dict[int, List[Mapping[str, object]]] = {}
    sequence_rows = 0
    sequence_merchants = 0

    if toggles.sequencing_enabled:
        sequence_root = _ensure_dataset_exists(site_sequence_path, "s3_site_sequence")
        sequence_frame = pl.read_parquet(sequence_root).sort(
            ["merchant_id", "country_iso", "site_order"]
        )
        _validate_schema_array("site_sequence", sequence_frame.to_dicts())
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
        for row in sequence_frame.to_dicts():
            merchant_id = int(row["merchant_id"])
            country = str(row["country_iso"])
            site_order = int(row["site_order"])
            key = (merchant_id, country, site_order)
            actual_sequence[key] = row
            sequence_by_merchant.setdefault(merchant_id, []).append(row)
        sequence_rows = len(actual_sequence)
        sequence_merchants = len(sequence_by_merchant)
    else:
        if site_sequence_path is not None and site_sequence_path.exists():
            raise err(
                "ERR_S3_SEQUENCE_GAP",
                "site sequence output present but sequencing disabled",
            )

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
    floor_hits_total = 0
    ceiling_hits_total = 0
    residual_rows_total = 0
    diagnostics: List[Mapping[str, object]] = []

    remaining_priors = set(actual_priors.keys())
    remaining_counts = set(actual_counts.keys())
    remaining_sequence = set(actual_sequence.keys())

    for merchant_id, expected_rows in expected_candidates.items():
        actual_rows = actual_candidates.get(merchant_id, [])
        if len(actual_rows) != len(expected_rows):
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"merchant {merchant_id} candidate count mismatch "
                f"(expected {len(expected_rows)}, found {len(actual_rows)})",
            )
        seen_countries: set[str] = set()
        for index, (expected_row, actual_row) in enumerate(
            zip(expected_rows, actual_rows)
        ):
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

        diag_entry: Dict[str, object] = {
            "merchant_id": merchant_id,
            "candidate_count": len(actual_rows),
            "eligible_crossborder": len(expected_rows) > 1,
            "total_outlets": merchants_map.get(merchant_id, None).n_outlets
            if merchant_id in merchants_map
            else None,
        }

        if toggles.priors_enabled:
            merchant_priors = priors_by_merchant.get(merchant_id, [])
            expected_keys = {
                (merchant_id, row.country_iso)
                for row in expected_rows
                if (merchant_id, row.country_iso) in expected_priors
            }
            actual_keys = {
                (merchant_id, str(row["country_iso"])) for row in merchant_priors
            }
            if expected_keys != actual_keys:
                missing = expected_keys - actual_keys
                extra = actual_keys - expected_keys
                if missing:
                    raise err(
                        "ERR_S3_EGRESS_SHAPE",
                        f"s3_base_weight_priors missing rows {sorted(missing)}",
                    )
                raise err(
                    "ERR_S3_EGRESS_SHAPE",
                    f"s3_base_weight_priors contains unexpected rows {sorted(extra)}",
                )
            prior_sum = Decimal("0")
            for key in expected_keys:
                expected_prior = expected_priors[key]
                actual_row = actual_priors[key]
                remaining_priors.discard(key)
                if str(actual_row["base_weight_dp"]) != expected_prior.base_weight_dp:
                    raise err(
                        "ERR_S3_EGRESS_SHAPE",
                        f"s3_base_weight_priors mismatch for {key} "
                        f"(expected {expected_prior.base_weight_dp}, "
                        f"found {actual_row['base_weight_dp']})",
                    )
                if int(actual_row["dp"]) != expected_prior.dp:
                    raise err(
                        "ERR_S3_EGRESS_SHAPE",
                        f"s3_base_weight_priors dp mismatch for {key} "
                        f"(expected {expected_prior.dp}, found {actual_row['dp']})",
                    )
                prior_sum += Decimal(expected_prior.base_weight_dp)
            diag_entry["prior_row_count"] = len(expected_keys)
            diag_entry["prior_weight_sum"] = str(prior_sum)
        elif expected_priors:
            if priors_rows:
                raise err(
                    "ERR_S3_PRIOR_DISABLED",
                    "priors disabled but kernel produced priors",
                )

        if toggles.integerisation_enabled:
            merchant_counts = counts_by_merchant.get(merchant_id, [])
            if not merchant_counts and expected_counts:
                raise err(
                    "ERR_S3_INTEGER_SUM_MISMATCH",
                    f"s3_integerised_counts missing merchant {merchant_id}",
                )
            floor_hits = 0
            ceiling_hits = 0
            residual_hits = 0
            total_count = 0
            merchant_total = merchants_map.get(merchant_id)
            floors_map, ceilings_map = _threshold_bounds_for_merchant(
                thresholds_policy,
                expected_rows,
                n_outlets=merchant_total.n_outlets if merchant_total else 0,
            )
            for row in merchant_counts:
                key = (merchant_id, str(row["country_iso"]))
                remaining_counts.discard(key)
                expected = expected_counts.get(key)
                if expected is None:
                    raise err(
                        "ERR_S3_INTEGER_SUM_MISMATCH",
                        f"s3_integerised_counts unexpected row {key}",
                    )
                count_value = int(row["count"])
                if count_value != expected.count:
                    raise err(
                        "ERR_S3_INTEGER_SUM_MISMATCH",
                        f"integerised count mismatch for {key}",
                    )
                total_count += count_value
                if floors_map.get(key[1]) is not None and count_value == floors_map[key[1]]:
                    floor_hits += 1
                ceiling = ceilings_map.get(key[1])
                if ceiling is not None and count_value == ceiling:
                    ceiling_hits += 1
                if int(row["residual_rank"]) > 0:
                    residual_hits += 1
            expected_total = merchants_map.get(merchant_id, None)
            if expected_total is not None and total_count != expected_total.n_outlets:
                raise err(
                    "ERR_S3_INTEGER_SUM_MISMATCH",
                    f"integerised counts sum {total_count} != N {expected_total.n_outlets} "
                    f"for merchant {merchant_id}",
                )
            floor_hits_total += floor_hits
            ceiling_hits_total += ceiling_hits
            residual_rows_total += residual_hits
            diag_entry["integerised_count_rows"] = len(merchant_counts)
            diag_entry["integerisation_floor_hits"] = floor_hits
            diag_entry["integerisation_ceiling_hits"] = ceiling_hits
            diag_entry["integerisation_residual_rows"] = residual_hits
        elif expected_counts:
            if counts_rows:
                raise err(
                    "ERR_S3_INTEGER_SUM_MISMATCH",
                    "integerisation disabled but kernel produced counts",
                )

        if toggles.sequencing_enabled:
            merchant_sequence = sequence_by_merchant.get(merchant_id, [])
            for row in merchant_sequence:
                key = (merchant_id, str(row["country_iso"]), int(row["site_order"]))
                remaining_sequence.discard(key)
                if key not in expected_sequence:
                    raise err(
                        "ERR_S3_SEQUENCE_GAP",
                        f"s3_site_sequence unexpected row {key}",
                    )
                site_id = row.get("site_id")
                if site_id is None or str(site_id) != f"{key[2]:06d}":
                    raise err(
                        "ERR_S3_SITE_SEQUENCE_OVERFLOW",
                        f"s3_site_sequence site_id mismatch for {key}",
                    )
            diag_entry["site_sequence_rows"] = len(merchant_sequence)
        elif expected_sequence:
            if sequence_rows:
                raise err(
                    "ERR_S3_SEQUENCE_GAP",
                    "sequencing disabled but kernel produced sequence rows",
                )

        diagnostics.append(diag_entry)

    if remaining_priors:
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            f"s3_base_weight_priors contains extra rows {sorted(remaining_priors)}",
        )
    if remaining_counts:
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            f"s3_integerised_counts contains extra rows {sorted(remaining_counts)}",
        )
    if remaining_sequence:
        raise err(
            "ERR_S3_SEQUENCE_GAP",
            f"s3_site_sequence contains extra rows {sorted(remaining_sequence)}",
        )

    metrics: Dict[str, float] = {
        "version": 1.0,
        "schema_validated": 1.0,
        "merchant_count": float(len(expected_candidates)),
        "candidate_rows": float(candidate_frame.height),
        "eligible_crossborder_merchants": float(eligible_crossborder),
        "priors_enabled": 1.0 if toggles.priors_enabled else 0.0,
        "priors_rows": float(priors_rows),
        "priors_merchants": float(priors_merchants),
        "priors_total_weight": float(priors_total_weight) if toggles.priors_enabled else 0.0,
        "integerisation_enabled": 1.0 if toggles.integerisation_enabled else 0.0,
        "integerised_rows": float(counts_rows),
        "integerised_merchants": float(counts_merchants),
        "integerisation_floor_hits": float(floor_hits_total),
        "integerisation_ceiling_hits": float(ceiling_hits_total),
        "integerisation_residual_rows": float(residual_rows_total),
        "sequencing_enabled": 1.0 if toggles.sequencing_enabled else 0.0,
        "sequence_rows": float(sequence_rows),
        "sequence_merchants": float(sequence_merchants),
        "total_outlets": float(
            sum(merchant.n_outlets for merchant in deterministic.merchants)
        ),
        "diagnostic_rows": float(len(diagnostics)),
    }
    logger.info(
        "S3 validator: merchants=%d candidates=%d priors=%d counts=%d sequence=%d",
        int(metrics["merchant_count"]),
        int(metrics["candidate_rows"]),
        int(metrics["priors_rows"]),
        int(metrics["integerised_rows"]),
        int(metrics["sequence_rows"]),
    )
    return S3ValidationResult(metrics=metrics, diagnostics=tuple(diagnostics))



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
