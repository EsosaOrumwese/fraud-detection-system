"""Validation helpers for S3 cross-border universe outputs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

import polars as pl

from ...s0_foundations.exceptions import err
from ..l0 import build_candidate_seeds, evaluate_rule_ladder, load_rule_ladder, rank_candidates
from ..l0.types import RankedCandidateRow, RuleLadder
from ..l2.deterministic import MerchantContext, S3DeterministicContext

logger = logging.getLogger(__name__)


def _expected_candidates(
    *,
    ladder: RuleLadder,
    merchants: Iterable[MerchantContext],
    iso_universe: Iterable[str],
) -> Mapping[int, Sequence[RankedCandidateRow]]:
    expected: Dict[int, Sequence[RankedCandidateRow]] = {}
    for merchant in merchants:
        evaluation = evaluate_rule_ladder(
            ladder,
            merchant_id=merchant.merchant_id,
            home_country_iso=merchant.home_country_iso,
            channel=merchant.channel,
            mcc=merchant.mcc,
            n_outlets=merchant.n_outlets,
        )
        seeds = build_candidate_seeds(
            ladder,
            evaluation,
            merchant_id=merchant.merchant_id,
            home_country_iso=merchant.home_country_iso,
            iso_universe=iso_universe,
        )
        ranked = rank_candidates(ladder, seeds=seeds)
        expected[merchant.merchant_id] = ranked
    return expected


def validate_s3_candidate_set(
    *,
    deterministic: S3DeterministicContext,
    candidate_set_path: Path,
    rule_ladder_path: Path,
) -> None:
    """Validate the persisted S3 candidate set against deterministic context."""

    if not candidate_set_path.exists():
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            f"s3_candidate_set missing at '{candidate_set_path}'",
        )

    frame = pl.read_parquet(candidate_set_path)
    if "parameter_hash" not in frame.columns:
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            "s3_candidate_set missing column 'parameter_hash'",
        )
    if frame.height == 0:
        raise err("ERR_S3_EGRESS_SHAPE", "s3_candidate_set is empty")

    parameter_hash_values = frame.get_column("parameter_hash").to_list()
    if any(value != deterministic.parameter_hash for value in parameter_hash_values):
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            "s3_candidate_set parameter_hash column does not match deterministic context",
        )
    if "produced_by_fingerprint" in frame.columns:
        fingerprint_values = frame.get_column("produced_by_fingerprint").to_list()
        if any(
            value not in (None, deterministic.manifest_fingerprint)
            for value in fingerprint_values
        ):
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                "s3_candidate_set produced_by_fingerprint column does not match manifest",
            )

    ladder = load_rule_ladder(rule_ladder_path.expanduser().resolve())
    expected = _expected_candidates(
        ladder=ladder,
        merchants=deterministic.merchants,
        iso_universe=deterministic.iso_countries,
    )

    actual_rows = frame.sort(["merchant_id", "candidate_rank", "country_iso"]).to_dicts()
    actual_by_merchant: Dict[int, List[dict]] = {}
    for row in actual_rows:
        merchant_id = int(row["merchant_id"])
        actual_by_merchant.setdefault(merchant_id, []).append(row)

    expected_merchant_ids = set(expected.keys())
    actual_merchant_ids = set(actual_by_merchant.keys())
    if expected_merchant_ids != actual_merchant_ids:
        missing = expected_merchant_ids - actual_merchant_ids
        extra = actual_merchant_ids - expected_merchant_ids
        if missing:
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"s3_candidate_set missing merchants {sorted(missing)}",
            )
        raise err(
            "ERR_S3_EGRESS_SHAPE",
            f"s3_candidate_set contains unexpected merchants {sorted(extra)}",
        )

    for merchant_id, expected_rows in expected.items():
        actual = actual_by_merchant.get(merchant_id, [])
        if len(actual) != len(expected_rows):
            raise err(
                "ERR_S3_EGRESS_SHAPE",
                f"merchant {merchant_id} candidate count mismatch "
                f"(expected {len(expected_rows)}, found {len(actual)})",
            )

        seen_countries: set[str] = set()
        for index, (expected_row, actual_row) in enumerate(zip(expected_rows, actual)):
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
            reason_codes = tuple(sorted(actual_row["reason_codes"]))
            filter_tags = tuple(sorted(actual_row["filter_tags"]))
            if reason_codes != tuple(sorted(expected_row.reason_codes)):
                raise err(
                    "ERR_S3_EGRESS_SHAPE",
                    f"merchant {merchant_id} reason_codes mismatch for {country}",
                )
            if filter_tags != tuple(sorted(expected_row.filter_tags)):
                raise err(
                    "ERR_S3_EGRESS_SHAPE",
                    f"merchant {merchant_id} filter_tags mismatch for {country}",
                )

    logger.info(
        "S3 validator: candidate set verified for %d merchants",
        len(expected_merchant_ids),
    )


__all__ = ["validate_s3_candidate_set"]
