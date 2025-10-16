from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from engine.layers.l1.seg_1A.s5_currency_weights.builder import build_weights
from engine.layers.l1.seg_1A.s5_currency_weights.contexts import S5PolicyMetadata
from engine.layers.l1.seg_1A.s5_currency_weights.loader import ShareSurface
from engine.layers.l1.seg_1A.s5_currency_weights.persist import (
    PARTITION_FILENAME,
    PersistConfig,
    build_receipt_payload,
    write_ccy_country_weights,
    write_validation_receipt,
)
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

    results = list(build_weights(settlement, ccy, policy))

    config = PersistConfig(parameter_hash="abc123", output_dir=tmp_path, emit_sparse_flag=True)
    parquet_path = write_ccy_country_weights(results, config)

    df = pd.read_parquet(parquet_path)
    assert set(df.columns) >= {"parameter_hash", "currency", "country_iso", "weight", "obs_count"}
    assert (df["parameter_hash"] == "abc123").all()

    validate_weights_df(df, parameter_hash="abc123")

    policy_path = tmp_path / "policy.yaml"
    policy_digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    policy_metadata = S5PolicyMetadata(
        path=policy_path,
        digest_hex=policy_digest,
        version="2025-10-16",
        semver="1.0.0",
    )
    schema_refs = {
        "settlement_shares": "schemas.ingress.layer1.yaml#/settlement_shares",
        "ccy_country_shares": "schemas.ingress.layer1.yaml#/ccy_country_shares",
        "ccy_country_weights_cache": "schemas.1A.yaml#/prep/ccy_country_weights_cache",
    }
    payload = build_receipt_payload(
        results=results,
        parameter_hash="abc123",
        policy_metadata=policy_metadata,
        schema_refs=schema_refs,
        rng_before={"events_total": 0, "draws_total": 0},
        rng_after={"events_total": 0, "draws_total": 0},
        currencies_total_inputs=1,
    )
    write_validation_receipt(payload=payload, config=config, target_dir=parquet_path.parent)

    receipt = json.loads((parquet_path.parent / "S5_VALIDATION.json").read_text())
    assert receipt["parameter_hash"] == "abc123"
    assert receipt["by_currency"][0]["currency"] == "USD"
    passed_contents = (parquet_path.parent / "_passed.flag").read_text(encoding="ascii").strip()
    assert passed_contents.startswith("sha256_hex=")
    assert receipt["rng_trace_delta_events"] == 0
    assert receipt["rng_trace_delta_draws"] == 0
    sparse_path = (
        tmp_path
        / "sparse_flag"
        / "parameter_hash=abc123"
        / PARTITION_FILENAME
    )
    df_sparse = pd.read_parquet(sparse_path)
    assert set(df_sparse.columns) >= {"parameter_hash", "currency", "is_sparse", "obs_count", "threshold"}
    assert len(df_sparse) == 1
    assert bool(df_sparse.loc[0, "is_sparse"]) is False

    usd_metrics = receipt["by_currency"][0]
    assert pytest.approx(usd_metrics["probability_sum"], abs=1e-12) == 1.0
    assert pytest.approx(usd_metrics["quantised_sum"], abs=1e-12) == 1.0


def test_validate_detects_sum_failure(tmp_path):
    policy = _load_policy(tmp_path, _BASE_POLICY)
    settlement = [ShareSurface(currency="USD", country_iso="US", share=1.0, obs_count=10)]
    ccy = []
    results = list(build_weights(settlement, ccy, policy))

    config = PersistConfig(parameter_hash="hash", output_dir=tmp_path, emit_validation=False)
    parquet_path = write_ccy_country_weights(results, config)
    df = pd.read_parquet(parquet_path)
    df.loc[df.index[0], "weight"] = 0.5

    with pytest.raises(ValidationError):
        validate_weights_df(df, parameter_hash="hash")
