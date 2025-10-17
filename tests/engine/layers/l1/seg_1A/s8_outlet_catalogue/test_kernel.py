from __future__ import annotations

from engine.layers.l1.seg_1A.s8_outlet_catalogue.contexts import (
    CountrySequencingInput,
    MerchantSequencingInput,
    S8DeterministicContext,
)
from engine.layers.l1.seg_1A.s8_outlet_catalogue.kernel import build_outlet_catalogue


def test_build_outlet_catalogue_generates_rows_and_events() -> None:
    merchant = MerchantSequencingInput(
        merchant_id=101,
        home_country_iso="US",
        single_vs_multi_flag=True,
        raw_nb_outlet_draw=3,
        global_seed=42,
        domain=(
            CountrySequencingInput(
                legal_country_iso="US",
                candidate_rank=0,
                allocated_count=2,
                is_home=True,
            ),
            CountrySequencingInput(
                legal_country_iso="CA",
                candidate_rank=1,
                allocated_count=1,
                is_home=False,
            ),
        ),
    )
    context = S8DeterministicContext(
        parameter_hash="phash",
        manifest_fingerprint="a" * 64,
        seed=42,
        run_id="run-1",
        merchants=(merchant,),
        candidate_lookup={101: {"US": 0, "CA": 1}},
        membership_lookup={101: {"CA": True}},
        counts_source="s7_in_memory",
        source_paths={},
    )

    rows, sequence_events, overflow_events, metrics = build_outlet_catalogue(context)

    assert overflow_events == tuple()
    assert len(rows) == 3
    assert len(sequence_events) == 2
    assert metrics.rows_total == 3
    assert metrics.hist_final_country_outlet_count["b1"] == 1
    assert metrics.hist_final_country_outlet_count["b2_3"] == 1
    assert metrics.domain_size_distribution["b2"] == 1
    assert metrics.overflow_merchant_ids == tuple()

