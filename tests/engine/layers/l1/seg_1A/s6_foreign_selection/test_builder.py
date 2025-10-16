from __future__ import annotations

from engine.layers.l1.seg_1A.s6_foreign_selection.builder import select_foreign_set
from engine.layers.l1.seg_1A.s6_foreign_selection.policy import SelectionPolicy
from engine.layers.l1.seg_1A.s6_foreign_selection.types import (
    CandidateInput,
    MerchantSelectionInput,
)


def _policy(**kwargs) -> SelectionPolicy:
    return SelectionPolicy(
        policy_semver=kwargs.get("policy_semver", "0.1.0"),
        policy_version=kwargs.get("policy_version", "2025-10-16"),
        emit_membership_dataset=kwargs.get("emit_membership_dataset", False),
        log_all_candidates=kwargs.get("log_all_candidates", True),
        max_candidates_cap=kwargs.get("max_candidates_cap", 0),
        zero_weight_rule=kwargs.get("zero_weight_rule", "exclude"),
        dp_score_print=None,
        per_currency=kwargs.get("per_currency", {}),
    )


def test_select_foreign_set_picks_top_keys():
    policy = _policy()
    candidates = (
        CandidateInput(
            merchant_id=1,
            country_iso="CA",
            candidate_rank=1,
            weight=0.6,
            is_home=False,
        ),
        CandidateInput(
            merchant_id=1,
            country_iso="FR",
            candidate_rank=2,
            weight=0.4,
            is_home=False,
        ),
        CandidateInput(
            merchant_id=1,
            country_iso="US",
            candidate_rank=0,
            weight=0.5,
            is_home=True,
        ),
    )
    merchant = MerchantSelectionInput(
        merchant_id=1,
        settlement_currency="USD",
        k_target=1,
        candidates=candidates,
    )

    uniforms = iter([0.2, 0.7])

    def provider(*_):
        return next(uniforms)

    results = select_foreign_set(
        policy=policy,
        merchants=[merchant],
        uniform_provider=provider,
    )

    assert len(results) == 1
    result = results[0]
    assert result.reason_code == "none"
    assert result.k_realised == 1
    selected = [candidate for candidate in result.candidates if candidate.selected]
    assert len(selected) == 1
    assert selected[0].country_iso == "CA"
    assert selected[0].selection_order == 1
    assert selected[0].uniform is not None


def test_zero_weight_domain_returns_empty_selection():
    policy = _policy(zero_weight_rule="exclude")
    candidates = (
        CandidateInput(
            merchant_id=2,
            country_iso="GB",
            candidate_rank=1,
            weight=0.0,
            is_home=False,
        ),
        CandidateInput(
            merchant_id=2,
            country_iso="US",
            candidate_rank=0,
            weight=1.0,
            is_home=True,
        ),
    )
    merchant = MerchantSelectionInput(
        merchant_id=2,
        settlement_currency="USD",
        k_target=2,
        candidates=candidates,
    )

    results = select_foreign_set(
        policy=policy,
        merchants=[merchant],
        uniform_provider=lambda *_: 0.5,
    )

    assert results[0].k_realised == 0
    assert results[0].reason_code == "ZERO_WEIGHT_DOMAIN"
    assert results[0].candidates == ()
