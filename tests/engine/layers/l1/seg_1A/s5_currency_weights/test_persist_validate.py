from __future__ import annotations

import json

import pandas as pd
import pytest

from engine.layers.l1.seg_1A.s5_currency_weights.builder import build_weights
from engine.layers.l1.seg_1A.s5_currency_weights.loader import ShareSurface
from engine.layers.l1.seg_1A.s5_currency_weights.persist import PersistConfig, write_ccy_country_weights
from engine.layers.l1.seg_1A.s5_currency_weights.policy import load_policy
from engine.layers.l1.seg_1A.s5_currency_weights.validate import ValidationError, validate_weights_df


_BASE_POLICY = """
semver: "1.0.0"
version: "2025-10-16"
dp: 4
defaults:
  blend_weight: 0.5
  alpha: 0.0
  obs_floor: 0
  min_share: 0.0
  shrink_exponent: 1.0
per_currency: {}
overrides:
  alpha_iso: {}
  min_share_iso: {}
"""


def _load_policy(tmp_path, text: str):
    path = tmp_path / "policy.yaml"
    path.write_text(text, encoding="utf-8")
    return load_policy(path)


def test_persist_and_validate(tmp_path):
    policy = _load_policy(tmp_path, _BASE_POLICY)

    settlement = [
        ShareSurface(currency="USD", country_iso="US", share=0.7, obs_count=120),
        ShareSurface(currency="USD", country_iso="CA", share=0.3, obs_count=120),
    ]
    ccy = [
        ShareSurface(currency="USD", country_iso="US", share=0.6, obs_count=40),
        ShareSurface(currency="USD", country_iso="CA", share=0.4, obs_count=40),
    ]

    results = build_weights(settlement, ccy, policy)

    config = PersistConfig(parameter_hash="abc123", output_dir=tmp_path)
    parquet_path = write_ccy_country_weights(results, config)

    df = pd.read_parquet(parquet_path)
    assert set(df.columns) >= {"parameter_hash", "currency", "country_iso", "weight", "obs_count"}
    assert (df["parameter_hash"] == "abc123").all()

    validate_weights_df(df, parameter_hash="abc123")

    receipt = json.loads((parquet_path.parent / "S5_VALIDATION.json").read_text())
    assert receipt["parameter_hash"] == "abc123"
    assert receipt["currencies"][0]["currency"] == "USD"


def test_validate_detects_sum_failure(tmp_path):
    policy = _load_policy(tmp_path, _BASE_POLICY)
    settlement = [ShareSurface(currency="USD", country_iso="US", share=1.0, obs_count=10)]
    ccy = []
    results = build_weights(settlement, ccy, policy)

    config = PersistConfig(parameter_hash="hash", output_dir=tmp_path, emit_validation=False)
    parquet_path = write_ccy_country_weights(results, config)
    df = pd.read_parquet(parquet_path)
    df.loc[df.index[0], "weight"] = 0.5

    with pytest.raises(ValidationError):
        validate_weights_df(df, parameter_hash="hash")
