from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from engine.layers.l1.seg_1A.s0_foundations.l1.context import MerchantUniverse
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord
from engine.layers.l1.seg_1A.s7_integer_allocation.types import (
    DomainAllocation,
    MerchantAllocationResult,
)
from engine.layers.l1.seg_1A.s8_outlet_catalogue.runner import S8Runner


def _make_candidate_set(base_path: Path, parameter_hash: str) -> None:
    path = base_path / "data" / "layer1" / "1A" / "s3_candidate_set" / f"parameter_hash={parameter_hash}"
    path.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {"merchant_id": 101, "country_iso": "US", "candidate_rank": 0, "is_home": True},
            {"merchant_id": 101, "country_iso": "CA", "candidate_rank": 1, "is_home": False},
        ]
    )
    frame.to_parquet(path / "part-00000.parquet", index=False)


def _make_integerised_counts(base_path: Path, parameter_hash: str) -> None:
    path = base_path / "data" / "layer1" / "1A" / "s3_integerised_counts" / f"parameter_hash={parameter_hash}"
    path.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {"merchant_id": 101, "country_iso": "US", "count": 2},
            {"merchant_id": 101, "country_iso": "CA", "count": 1},
        ]
    )
    frame.to_parquet(path / "part-00000.parquet", index=False)


@pytest.fixture
def merchant_universe() -> MerchantUniverse:
    table = pl.DataFrame(
        [
            {"merchant_id": 101, "mcc": "5411", "channel_sym": "CP", "home_country_iso": "US", "merchant_u64": 1010},
        ]
    )
    return MerchantUniverse(table=table)


def _decisions() -> list[HurdleDecision]:
    # Values outside the fields consulted by S8 are filled with neutral defaults.
    return [
        HurdleDecision(
            merchant_id=101,
            eta=0.0,
            pi=0.0,
            deterministic=True,
            is_multi=True,
            u=None,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 0),
            draws=0,
            blocks=0,
        )
    ]


def _nb_finals() -> list[NBFinalRecord]:
    return [
        NBFinalRecord(
            merchant_id=101,
            mu=1.0,
            phi=1.0,
            n_outlets=3,
            nb_rejections=0,
            attempts=1,
        )
    ]


def _s7_results() -> list[MerchantAllocationResult]:
    allocations = (
        DomainAllocation(
            country_iso="US",
            candidate_rank=0,
            is_home=True,
            weight=0.7,
            share=0.7,
            lower_bound=1,
            upper_bound=None,
            base_count=1,
            allocated_count=2,
            residual=0.2,
            residual_rank=1,
        ),
        DomainAllocation(
            country_iso="CA",
            candidate_rank=1,
            is_home=False,
            weight=0.3,
            share=0.3,
            lower_bound=0,
            upper_bound=None,
            base_count=0,
            allocated_count=1,
            residual=0.1,
            residual_rank=2,
        ),
    )
    return [
        MerchantAllocationResult(
            merchant_id=101,
            settlement_currency="USD",
            total_outlets=3,
            k_target=1,
            k_realised=1,
            shortfall=False,
            domain_allocations=allocations,
            remainder=0,
            bounds_enforced=False,
        )
    ]


def test_s8_runner_emits_catalogue(tmp_path: Path, merchant_universe: MerchantUniverse) -> None:
    parameter_hash = "phash-demo"
    manifest_fingerprint = "f" * 64
    seed = 2025
    run_id = "run-001"

    _make_candidate_set(tmp_path, parameter_hash)
    _make_integerised_counts(tmp_path, parameter_hash)

    runner = S8Runner()
    outputs = runner.run(
        base_path=tmp_path,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        run_id=run_id,
        merchant_universe=merchant_universe,
        hurdle_decisions=_decisions(),
        nb_finals=_nb_finals(),
        s7_results=_s7_results(),
    )

    assert outputs.catalogue_path.exists()
    assert outputs.sequence_finalize_path is not None and outputs.sequence_finalize_path.exists()
    assert outputs.validation_bundle_path is not None and outputs.validation_bundle_path.exists()
    assert outputs.metrics.rows_total == 3
    assert outputs.metrics.overflow_merchant_ids == tuple()
