from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error
from engine.layers.l1.seg_1A.s0_foundations.l1.context import MerchantUniverse
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord
from engine.layers.l1.seg_1A.s7_integer_allocation.types import (
    DomainAllocation,
    MerchantAllocationResult,
)
from engine.layers.l1.seg_1A.s8_outlet_catalogue.loader import load_deterministic_context


def _merchant_universe() -> MerchantUniverse:
    frame = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "mcc": ["5411", "5999"],
            "channel_sym": ["CP", "CNP"],
            "home_country_iso": ["US", "GB"],
            "merchant_u64": [1, 2],
        }
    )
    return MerchantUniverse(frame)


def _hurdle_decisions() -> list[HurdleDecision]:
    return [
        HurdleDecision(
            merchant_id=1,
            eta=0.0,
            pi=0.9,
            deterministic=False,
            is_multi=True,
            u=0.1,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=0,
        ),
        HurdleDecision(
            merchant_id=2,
            eta=0.0,
            pi=0.1,
            deterministic=False,
            is_multi=False,
            u=0.9,
            rng_counter_before=(0, 1),
            rng_counter_after=(0, 2),
            draws=1,
            blocks=0,
        ),
    ]


def _nb_finals() -> list[NBFinalRecord]:
    return [
        NBFinalRecord(
            merchant_id=1,
            mu=3.0,
            phi=1.0,
            n_outlets=3,
            nb_rejections=0,
            attempts=1,
        )
    ]


def _s7_results() -> list[MerchantAllocationResult]:
    domain_allocations = (
        DomainAllocation(
            country_iso="US",
            candidate_rank=0,
            is_home=True,
            weight=0.6,
            share=0.6,
            lower_bound=0,
            upper_bound=None,
            base_count=2,
            allocated_count=2,
            residual=0.2,
            residual_rank=1,
        ),
        DomainAllocation(
            country_iso="CA",
            candidate_rank=1,
            is_home=False,
            weight=0.4,
            share=0.4,
            lower_bound=0,
            upper_bound=None,
            base_count=1,
            allocated_count=1,
            residual=0.1,
            residual_rank=2,
        ),
    )
    return [
        MerchantAllocationResult(
            merchant_id=1,
            settlement_currency="USD",
            total_outlets=3,
            k_target=1,
            k_realised=1,
            shortfall=False,
            domain_allocations=domain_allocations,
            remainder=0,
            bounds_enforced=False,
        )
    ]


def _write_candidate_set(base_path: Path, parameter_hash: str) -> None:
    path = base_path / "data" / "layer1" / "1A" / "s3_candidate_set" / f"parameter_hash={parameter_hash}"
    path.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {"merchant_id": 1, "country_iso": "US", "candidate_rank": 0, "is_home": True},
            {"merchant_id": 1, "country_iso": "CA", "candidate_rank": 1, "is_home": False},
            {"merchant_id": 2, "country_iso": "GB", "candidate_rank": 0, "is_home": True},
        ]
    )
    frame.to_parquet(path / "part-00000.parquet", index=False)


def _write_integerised_counts(base_path: Path, parameter_hash: str) -> None:
    path = base_path / "data" / "layer1" / "1A" / "s3_integerised_counts" / f"parameter_hash={parameter_hash}"
    path.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {"merchant_id": 1, "country_iso": "US", "count": 2},
            {"merchant_id": 1, "country_iso": "CA", "count": 1},
        ]
    )
    frame.to_parquet(path / "part-00000.parquet", index=False)


def test_load_deterministic_context_success(tmp_path):
    _write_candidate_set(tmp_path, "abc123")
    _write_integerised_counts(tmp_path, "abc123")
    context = load_deterministic_context(
        base_path=tmp_path,
        parameter_hash="abc123",
        manifest_fingerprint="f" * 64,
        seed=42,
        run_id="run-1",
        merchant_universe=_merchant_universe(),
        hurdle_decisions=_hurdle_decisions(),
        nb_finals=_nb_finals(),
        s7_results=_s7_results(),
    )

    assert context.parameter_hash == "abc123"
    assert context.manifest_fingerprint == "f" * 64
    assert context.seed == 42
    assert context.run_id == "run-1"
    assert len(context.merchants) == 2

    multi = next(item for item in context.merchants if item.merchant_id == 1)
    assert multi.single_vs_multi_flag is True
    assert multi.global_seed == 42
    assert multi.raw_nb_outlet_draw == 3
    assert multi.home_country_iso == "US"
    assert len(multi.domain) == 2
    assert sum(domain.allocated_count for domain in multi.domain) == 3

    single = next(item for item in context.merchants if item.merchant_id == 2)
    assert single.single_vs_multi_flag is False
    assert single.home_country_iso == "GB"
    assert single.raw_nb_outlet_draw == 1
    assert len(single.domain) == 1
    only_domain = single.domain[0]
    assert only_domain.legal_country_iso == "GB"
    assert only_domain.candidate_rank == 0
    assert only_domain.allocated_count == 1


def test_load_deterministic_context_missing_s7(tmp_path):
    _write_candidate_set(tmp_path, "abc123")
    with pytest.raises(S0Error) as exc:
        load_deterministic_context(
            base_path=tmp_path,
            parameter_hash="abc123",
            manifest_fingerprint="f" * 64,
            seed=42,
            run_id="run-1",
            merchant_universe=_merchant_universe(),
            hurdle_decisions=_hurdle_decisions(),
            nb_finals=_nb_finals(),
            s7_results=[],
        )
    assert exc.value.context.code == "E_S8_S7_MISSING"
