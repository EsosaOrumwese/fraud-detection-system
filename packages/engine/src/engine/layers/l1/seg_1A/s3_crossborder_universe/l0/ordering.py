"""Deterministic ordering for S3 candidate rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from ...s0_foundations.exceptions import err
from .types import CandidateSeed, RankedCandidateRow, RuleLadder


@dataclass(frozen=True)
class _SortableRow:
    candidate: CandidateSeed
    admission_key: Tuple[int, int, str]
    original_index: int


def _lookup_key(ladder: RuleLadder, rule_id: str) -> Tuple[int, int, str]:
    for rule in ladder.rules:
        if rule.rule_id == rule_id:
            return (rule.precedence_rank, rule.priority, rule.rule_id)
    raise err(
        "ERR_S3_ORDERING_KEY_UNDEFINED",
        f"admitting rule '{rule_id}' not present in ladder",
    )


def rank_candidates(
    ladder: RuleLadder,
    *,
    seeds: Iterable[CandidateSeed],
) -> Tuple[RankedCandidateRow, ...]:
    """Assign candidate_rank values following the S3.3 specification."""

    seed_list = list(seeds)
    if not seed_list:
        raise err("ERR_S3_ORDERING_HOME_MISSING", "candidate set is empty")

    home_rows = [seed for seed in seed_list if seed.is_home]
    if len(home_rows) != 1:
        raise err(
            "ERR_S3_ORDERING_HOME_MISSING",
            "candidate set must contain exactly one home row",
        )
    home_seed = home_rows[0]

    seen_countries = set()
    ranked: List[RankedCandidateRow] = [
        RankedCandidateRow(
            merchant_id=home_seed.merchant_id,
            country_iso=home_seed.country_iso,
            is_home=True,
            candidate_rank=0,
            filter_tags=home_seed.filter_tags,
            reason_codes=home_seed.reason_codes,
            admitting_rules=home_seed.admitting_rules,
        )
    ]
    seen_countries.add(home_seed.country_iso)

    foreign_rows: List[_SortableRow] = []
    for index, seed in enumerate(seed_list):
        if seed is home_seed:
            continue
        if seed.country_iso in seen_countries:
            raise err(
                "ERR_S3_ORDERING_UNSTABLE",
                f"duplicate country '{seed.country_iso}' in candidate set",
            )
        if not seed.admitting_rules:
            raise err(
                "ERR_S3_ORDERING_KEY_UNDEFINED",
                f"candidate '{seed.country_iso}' missing admitting rules",
            )
        key_candidates = [_lookup_key(ladder, rule_id) for rule_id in seed.admitting_rules]
        admission_key = min(key_candidates)
        foreign_rows.append(
            _SortableRow(candidate=seed, admission_key=admission_key, original_index=index)
        )
        seen_countries.add(seed.country_iso)

    foreign_rows.sort(
        key=lambda item: (item.admission_key, item.candidate.country_iso, item.original_index)
    )

    current_rank = 1
    for row in foreign_rows:
        ranked.append(
            RankedCandidateRow(
                merchant_id=row.candidate.merchant_id,
                country_iso=row.candidate.country_iso,
                is_home=False,
                candidate_rank=current_rank,
                filter_tags=row.candidate.filter_tags,
                reason_codes=row.candidate.reason_codes,
                admitting_rules=row.candidate.admitting_rules,
            )
        )
        current_rank += 1

    return tuple(ranked)


__all__ = ["rank_candidates"]
