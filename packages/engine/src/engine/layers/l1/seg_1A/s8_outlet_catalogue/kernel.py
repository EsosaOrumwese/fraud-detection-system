"""Core sequencing logic for S8 outlet catalogue generation."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Sequence, Tuple

from ..s0_foundations.exceptions import err
from .contexts import S8DeterministicContext, S8Metrics
from .types import OutletCatalogueRow, SequenceFinalizeEvent, SiteSequenceOverflowEvent

MAX_SEQUENCE = 999_999
_COUNT_BUCKETS = ("b1", "b2_3", "b4_10", "b11_25", "b26_plus")
_DOMAIN_BUCKETS = ("b1", "b2", "b3_5", "b6_10", "b11_plus")


def build_outlet_catalogue(
    context: S8DeterministicContext,
) -> Tuple[
    Sequence[OutletCatalogueRow],
    Sequence[SequenceFinalizeEvent],
    Sequence[SiteSequenceOverflowEvent],
    S8Metrics,
]:
    """Transform the deterministic context into outlet rows and instrumentation events."""
    rows: list[OutletCatalogueRow] = []
    sequence_events: list[SequenceFinalizeEvent] = []
    overflow_events: list[SiteSequenceOverflowEvent] = []
    metrics = S8Metrics(
        rows_total_by_country=defaultdict(int),
        hist_final_country_outlet_count={bucket: 0 for bucket in _COUNT_BUCKETS},
        domain_size_distribution={bucket: 0 for bucket in _DOMAIN_BUCKETS},
    )

    pk_digest = hashlib.sha256()
    overflow_merchants: set[int] = set()

    candidate_lookup = context.candidate_lookup or {}
    membership_lookup = context.membership_lookup or {}

    for merchant in context.merchants:
        merchant_id = merchant.merchant_id
        domain = merchant.domain
        domain_size = len(domain)

        _increment_bucket(metrics.domain_size_distribution, _DOMAIN_BUCKETS, domain_size)

        allocated_sum = sum(entry.allocated_count for entry in domain)
        if allocated_sum != merchant.raw_nb_outlet_draw:
            metrics.sum_law_mismatch_count += 1
            raise err(
                "E_S8_SUM_LAW",
                f"sum of final_country_outlet_count mismatch for merchant_id={merchant_id} "
                f"(expected={merchant.raw_nb_outlet_draw}, actual={allocated_sum})",
            )

        overflow_entries = [entry for entry in domain if entry.allocated_count > MAX_SEQUENCE]
        if overflow_entries:
            overflow_merchants.add(merchant_id)
            for entry in overflow_entries:
                overflow_events.append(
                    SiteSequenceOverflowEvent(
                        merchant_id=merchant_id,
                        legal_country_iso=entry.legal_country_iso,
                        attempted_sequence=int(entry.allocated_count),
                        manifest_fingerprint=context.manifest_fingerprint,
                    )
                )
            # Guardrail: merchant fails wholesale on overflow, no rows emitted.
            continue

        metrics.merchants_in_egress += 1

        for domain_entry in domain:
            iso = domain_entry.legal_country_iso
            allocated = domain_entry.allocated_count
            candidate_map = candidate_lookup.get(merchant_id, {})
            if not domain_entry.is_home and candidate_map and iso not in candidate_map:
                metrics.s3_membership_miss_count += 1
            membership_map = membership_lookup.get(merchant_id)
            if membership_map is not None and not domain_entry.is_home:
                if not membership_map.get(iso, False):
                    metrics.s3_membership_miss_count += 1

            if not _is_valid_iso(iso):
                metrics.iso_fk_violation_count += 1

            metrics.blocks_with_rows += 1
            metrics.rows_total += allocated
            metrics.rows_total_by_country[iso] += allocated
            _increment_bucket(metrics.hist_final_country_outlet_count, _COUNT_BUCKETS, allocated)

            for site_order in range(1, allocated + 1):
                site_id = f"{site_order:06d}"
                row = OutletCatalogueRow(
                    manifest_fingerprint=context.manifest_fingerprint,
                    merchant_id=merchant_id,
                    site_id=site_id,
                    home_country_iso=merchant.home_country_iso,
                    legal_country_iso=iso,
                    single_vs_multi_flag=merchant.single_vs_multi_flag,
                    raw_nb_outlet_draw=merchant.raw_nb_outlet_draw,
                    final_country_outlet_count=allocated,
                    site_order=site_order,
                    global_seed=merchant.global_seed,
                )
                rows.append(row)
                pk_digest.update(f"{merchant_id}|{iso}|{site_order}".encode("utf-8"))

            sequence_events.append(
                SequenceFinalizeEvent(
                    merchant_id=merchant_id,
                    legal_country_iso=iso,
                    site_order_start=1,
                    site_order_end=allocated,
                    site_count=allocated,
                    manifest_fingerprint=context.manifest_fingerprint,
                )
            )

    metrics.pk_hash_hex = pk_digest.hexdigest()
    metrics.overflow_merchant_ids = tuple(sorted(overflow_merchants))
    metrics.rows_total_by_country = dict(metrics.rows_total_by_country)

    return tuple(rows), tuple(sequence_events), tuple(overflow_events), metrics


def _increment_bucket(target: dict[str, int], buckets: Tuple[str, ...], value: int) -> None:
    if value <= 0:
        bucket = buckets[0]
    elif buckets == _DOMAIN_BUCKETS:
        if value == 1:
            bucket = "b1"
        elif value == 2:
            bucket = "b2"
        elif 3 <= value <= 5:
            bucket = "b3_5"
        elif 6 <= value <= 10:
            bucket = "b6_10"
        else:
            bucket = "b11_plus"
    else:
        if value == 1:
            bucket = "b1"
        elif 2 <= value <= 3:
            bucket = "b2_3"
        elif 4 <= value <= 10:
            bucket = "b4_10"
        elif 11 <= value <= 25:
            bucket = "b11_25"
        else:
            bucket = "b26_plus"
    target[bucket] = target.get(bucket, 0) + 1


def _is_valid_iso(code: str) -> bool:
    return len(code) == 2 and code.isalpha() and code.isupper()


__all__ = [
    "build_outlet_catalogue",
]
