from __future__ import annotations

import pytest

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error
from engine.layers.l1.seg_1A.s5_currency_weights.contexts import MerchantCurrencyInput
from engine.layers.l1.seg_1A.s5_currency_weights.merchant_currency import (
    MerchantCurrencyRecord,
    derive_merchant_currency,
)
from engine.layers.l1.seg_1A.s5_currency_weights.persist import (
    PARTITION_FILENAME,
    PersistConfig,
    write_merchant_currency,
)


def test_derive_prefers_share_vector():
    inputs = [
        MerchantCurrencyInput(
            merchant_id=1,
            home_country_iso="US",
            share_vector={"usd": 0.6, "cad": 0.4},
        )
    ]
    result = derive_merchant_currency(inputs, {"US": "USD"})
    assert result == (
        MerchantCurrencyRecord(
            merchant_id=1,
            kappa="USD",
            source="ingress_share_vector",
            tie_break_used=False,
        ),
    )


def test_derive_tie_breaks_lexicographically():
    inputs = [
        MerchantCurrencyInput(
            merchant_id=7,
            home_country_iso="US",
            share_vector={"usd": 0.5, "aed": 0.5},
        )
    ]
    result = derive_merchant_currency(inputs, {"US": "USD"})
    assert result[0].kappa == "AED"
    assert result[0].tie_break_used is True
    assert result[0].source == "ingress_share_vector"


def test_derive_falls_back_to_legal_tender():
    inputs = [
        MerchantCurrencyInput(
            merchant_id=42,
            home_country_iso="GB",
            share_vector=None,
        )
    ]
    result = derive_merchant_currency(inputs, {"GB": "GBP"})
    assert result[0].kappa == "GBP"
    assert result[0].source == "home_primary_legal_tender"
    assert result[0].tie_break_used is False


def test_derive_raises_when_mapping_missing():
    inputs = [
        MerchantCurrencyInput(
            merchant_id=5,
            home_country_iso="FR",
            share_vector=None,
        )
    ]
    with pytest.raises(S0Error) as exc:
        derive_merchant_currency(inputs, {})
    assert exc.value.context.code == "E_MCURR_RESOLUTION"


def test_write_merchant_currency(tmp_path):
    records = (
        MerchantCurrencyRecord(
            merchant_id=1,
            kappa="USD",
            source="home_primary_legal_tender",
            tie_break_used=False,
        ),
        MerchantCurrencyRecord(
            merchant_id=2,
            kappa="CAD",
            source="home_primary_legal_tender",
            tie_break_used=False,
        ),
    )
    config = PersistConfig(parameter_hash="abc123", output_dir=tmp_path)
    parquet_path = write_merchant_currency(records, config)
    assert parquet_path.name == PARTITION_FILENAME
    df = pytest.importorskip("pandas").read_parquet(parquet_path)
    assert list(df.columns) == [
        "parameter_hash",
        "merchant_id",
        "kappa",
        "source",
        "tie_break_used",
    ]
    assert df["parameter_hash"].unique().tolist() == ["abc123"]
    assert df["merchant_id"].tolist() == [1, 2]
