from __future__ import annotations

import hashlib
from pathlib import Path

from engine.layers.l1.seg_1A.s6_foreign_selection.contexts import S6DeterministicContext
from engine.layers.l1.seg_1A.s6_foreign_selection.types import (
    CandidateInput,
    CandidateSelection,
    MerchantSelectionInput,
    MerchantSelectionResult,
)
from engine.layers.l1.seg_1A.s6_foreign_selection.policy import SelectionOverrides
from engine.layers.l1.seg_1A.s7_integer_allocation.loader import build_deterministic_context
from engine.layers.l1.seg_1A.s7_integer_allocation.policy import IntegerisationPolicy
from engine.layers.l1.seg_1A.s7_integer_allocation.types import DomainMember
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord


def _write_s5_pass(directory: Path) -> None:
    receipt = directory / "S5_VALIDATION.json"
    flag = directory / "_passed.flag"
    payload = "{}"
    receipt.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    flag.write_text(f"sha256_hex={digest}\n", encoding="ascii")


def _policy() -> IntegerisationPolicy:
    return IntegerisationPolicy(
        policy_semver="1.0.0",
        policy_version="2025-10-16",
        dp_resid=8,
        dirichlet_enabled=False,
        dirichlet_alpha0=None,
        bounds_enabled=False,
        bounds=None,
    )


def test_build_deterministic_context_includes_home(tmp_path: Path) -> None:
    base_path = tmp_path
    weights_dir = base_path / "data" / "layer1" / "1A" / "ccy_country_weights_cache" / "parameter_hash=testhash"
    weights_dir.mkdir(parents=True, exist_ok=True)
    _write_s5_pass(weights_dir)

    nb_finals = [
        NBFinalRecord(
            merchant_id=1,
            mu=2.0,
            phi=1.0,
            n_outlets=4,
            nb_rejections=0,
            attempts=1,
        )
    ]
    s6_deterministic = S6DeterministicContext(
        parameter_hash="testhash",
        manifest_fingerprint="abc123",
        seed=123,
        run_id="runid",
        merchants=(
            MerchantSelectionInput(
                merchant_id=1,
                settlement_currency="USD",
                k_target=1,
                candidates=(
                    CandidateInput(
                        merchant_id=1,
                        country_iso="US",
                        candidate_rank=0,
                        weight=0.6,
                        is_home=True,
                    ),
                    CandidateInput(
                        merchant_id=1,
                        country_iso="CA",
                        candidate_rank=1,
                        weight=0.4,
                        is_home=False,
                    ),
                ),
            ),
        ),
        policy_path=base_path / "dummy.yaml",
    )

    s6_results = [
        MerchantSelectionResult(
            merchant_id=1,
            settlement_currency="USD",
            k_target=1,
            k_realised=1,
            shortfall=False,
            reason_code="none",
            overrides=SelectionOverrides(
                emit_membership_dataset=False,
                max_candidates_cap=0,
                zero_weight_rule="exclude",
            ),
            truncated_by_cap=False,
            candidates=(
                CandidateSelection(
                    merchant_id=1,
                    country_iso="CA",
                    candidate_rank=1,
                    weight=0.4,
                    weight_normalised=0.4,
                    uniform=0.1,
                    key=0.2,
                    eligible=True,
                    selected=True,
                    selection_order=1,
                ),
            ),
            domain_total=1,
            domain_considered=1,
            domain_eligible=1,
            zero_weight_considered=0,
            expected_events=1,
            ties_resolved=0,
            policy_cap_applied=False,
            cap_value=0,
        )
    ]

    context = build_deterministic_context(
        base_path=base_path,
        parameter_hash="testhash",
        manifest_fingerprint="abc123",
        seed=123,
        run_id="runid",
        policy_path=base_path / "policy.yaml",
        nb_finals=nb_finals,
        s6_context=s6_deterministic,
        s6_results=s6_results,
        policy=_policy(),
    )

    assert context.parameter_hash == "testhash"
    assert len(context.merchants) == 1
    merchant = context.merchants[0]
    assert merchant.merchant_id == 1
    assert len(merchant.domain) == 2
    assert [member.country_iso for member in merchant.domain] == ["US", "CA"]
    assert any(member.is_home for member in merchant.domain)
    assert all(isinstance(member, DomainMember) for member in merchant.domain)
