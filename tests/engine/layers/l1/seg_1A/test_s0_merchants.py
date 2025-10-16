from __future__ import annotations

import polars as pl

from engine.layers.l1.seg_1A.s0_foundations.l1.context import SchemaAuthority
from engine.layers.l1.seg_1A.s0_foundations.l1.merchants import build_run_context


def test_run_context_captures_settlement_share_vector(tmp_path):
    merchant_table = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "mcc": [1234, 2345],
            "channel": ["card_present", "card_not_present"],
            "home_country_iso": ["US", "GB"],
            "settlement_currency": ["USD", "GBP"],
            "settlement_currency_vector": [
                {"USD": 0.7, "CAD": 0.3},
                None,
            ],
        }
    )
    iso_table = pl.DataFrame({"country_iso": ["US", "GB"]})
    gdp_table = pl.DataFrame(
        {
            "country_iso": ["US", "GB"],
            "observation_year": [2024, 2024],
            "gdp_pc_usd_2015": [60000.0, 50000.0],
        }
    )
    bucket_table = pl.DataFrame(
        {
            "country_iso": ["US", "GB"],
            "bucket_id": [1, 2],
        }
    )

    schema_authority = SchemaAuthority(
        ingress_ref="l1/seg_1A/merchant_ids.schema.json",
        segment_ref="l1/seg_1A/s0_outputs.schema.json",
        rng_ref="layer1/schemas.layer1.yaml",
    )

    context = build_run_context(
        merchant_table=merchant_table,
        iso_table=iso_table,
        gdp_table=gdp_table,
        bucket_table=bucket_table,
        schema_authority=schema_authority,
    )

    merchants_df = context.merchants.merchants.sort("merchant_id")
    assert "settlement_currency_vector" in merchants_df.columns
    row0 = merchants_df.filter(pl.col("merchant_id") == 1).row(0, named=True)
    row1 = merchants_df.filter(pl.col("merchant_id") == 2).row(0, named=True)

    assert row0["settlement_currency"] == "USD"
    assert row0["settlement_currency_vector"] == {"USD": 0.7, "CAD": 0.3}
    assert row1["settlement_currency_vector"] == {"GBP": 1.0}
