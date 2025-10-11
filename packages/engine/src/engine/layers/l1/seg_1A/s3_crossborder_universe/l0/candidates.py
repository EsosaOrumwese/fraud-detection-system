"""Deterministic construction of S3 candidate rows (pre-ranking)."""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, MutableMapping, Tuple

from ...s0_foundations.exceptions import err
from .types import CandidateSeed, RuleDefinition, RuleLadder, RuleLadderEvaluation


def _rule_lookup(ladder: RuleLadder) -> Mapping[str, RuleDefinition]:
    return {rule.rule_id: rule for rule in ladder.rules}


def _sorted_unique(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted({value for value in values}))


def _merge_tags(*groups: Iterable[str]) -> Tuple[str, ...]:
    tags: set[str] = set()
    for group in groups:
        tags.update(group)
    return tuple(sorted(tags))


def build_candidate_seeds(
    ladder: RuleLadder,
    evaluation: RuleLadderEvaluation,
    *,
    merchant_id: int,
    home_country_iso: str,
    iso_universe: Iterable[str],
) -> Tuple[CandidateSeed, ...]:
    """Create unordered candidate rows (S3.2 output) given ladder evaluation."""

    iso_set = {code.upper() for code in iso_universe}
    if home_country_iso.upper() not in iso_set:
        raise err(
            "ERR_S3_CANDIDATE_CONSTRUCTION",
            f"home_country_iso '{home_country_iso}' not present in ISO universe",
        )

    rule_by_id = _rule_lookup(ladder)
    decision_rule = rule_by_id.get(evaluation.decision_rule_id)
    if decision_rule is None:
        raise err(
            "ERR_S3_RULE_LADDER_INVALID",
            f"decision rule '{evaluation.decision_rule_id}' missing from artefact",
        )

    seeds: List[CandidateSeed] = []

    decision_reason_codes = (
        (decision_rule.reason_code,) if decision_rule.reason_code else tuple()
    )
    home_tags = _merge_tags(
        ("HOME",),
        ladder.default_tags,
        evaluation.merchant_tags,
        decision_rule.row_tags,
    )
    seeds.append(
        CandidateSeed(
            merchant_id=merchant_id,
            country_iso=home_country_iso.upper(),
            is_home=True,
            filter_tags=home_tags,
            reason_codes=decision_reason_codes,
            admitting_rules=(decision_rule.rule_id,),
        )
    )

    if not evaluation.eligible_crossborder:
        return tuple(seeds)

    # Start from evaluation-admitted countries and add any default sets wired to
    # the decision.
    admitting: Dict[str, List[str]] = {
        iso.upper(): list(rule_ids)
        for iso, rule_ids in evaluation.admitting_rules_by_country.items()
    }

    for set_name in ladder.default_admit_sets:
        default_rules = admitting.setdefault(home_country_iso.upper(), [])
        # Ensure the decision rule is recorded; these defaults apply globally.
        if decision_rule.rule_id not in default_rules:
            default_rules.append(decision_rule.rule_id)
        for iso in ladder.named_sets.get(set_name, ()):
            admitting.setdefault(iso.upper(), []).append(decision_rule.rule_id)

    # Remove denied countries.
    for iso, rule_ids in evaluation.denying_rules_by_country.items():
        iso_upper = iso.upper()
        if iso_upper in admitting:
            admitting.pop(iso_upper, None)

    # Remove home (always included separately).
    admitting.pop(home_country_iso.upper(), None)

    candidate_countries = sorted(admitting.keys())

    for iso in candidate_countries:
        if iso not in iso_set:
            raise err(
                "ERR_S3_CANDIDATE_CONSTRUCTION",
                f"policy admitted country '{iso}' not present in ISO universe",
            )
        raw_rules = admitting[iso]
        if not raw_rules:
            raise err(
                "ERR_S3_CANDIDATE_CONSTRUCTION",
                f"country '{iso}' lacks admitting rules after policy expansion",
            )
        unique_rules: List[str] = []
        seen_rules: set[str] = set()
        for rule_id in raw_rules:
            if rule_id not in seen_rules:
                unique_rules.append(rule_id)
                seen_rules.add(rule_id)
        reason_codes: List[str] = []
        row_tags: List[str] = []
        for rule_id in unique_rules:
            rule = rule_by_id.get(rule_id)
            if rule is None:
                raise err(
                    "ERR_S3_RULE_LADDER_INVALID",
                    f"rule '{rule_id}' missing from artefact",
                )
            if rule.reason_code:
                reason_codes.append(rule.reason_code)
            row_tags.extend(rule.row_tags)
        reason_codes.extend(decision_reason_codes)
        row_tags.extend(evaluation.row_tags_by_country.get(iso, ()))

        filter_tags = _merge_tags(
            ladder.default_tags,
            evaluation.merchant_tags,
            row_tags,
        )
        seeds.append(
            CandidateSeed(
                merchant_id=merchant_id,
                country_iso=iso,
                is_home=False,
                filter_tags=filter_tags,
                reason_codes=_sorted_unique(reason_codes),
                admitting_rules=tuple(unique_rules),
            )
        )

    return tuple(seeds)


__all__ = ["build_candidate_seeds"]
