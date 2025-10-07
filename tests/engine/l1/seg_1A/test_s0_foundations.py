"""Sanity tests for S0 foundations primitives."""

from __future__ import annotations

from pathlib import Path

import math
import polars as pl
import pytest

from engine.layers.l1.seg_1A.s0_foundations import (
    CrossborderEligibility,
    PhiloxEngine,
    SchemaAuthority,
    build_run_context,
    compute_parameter_hash,
    compute_run_id,
    iter_design_vectors,
    load_crossborder_eligibility,
    load_dispersion_coefficients,
    load_hurdle_coefficients,
    evaluate_eligibility,
)
from engine.layers.l1.seg_1A.s0_foundations.l0.artifacts import hash_artifacts


@pytest.fixture()
def sample_context() -> tuple:
    merchants = pl.DataFrame(
        {
            "merchant_id": [1, 2],
            "mcc": [5411, 5732],
            "channel": ["card_present", "card_not_present"],
            "home_country_iso": ["GB", "DE"],
        }
    )
    iso = pl.DataFrame({"country_iso": ["GB", "DE"]})
    gdp = pl.DataFrame(
        {
            "country_iso": ["GB", "DE"],
            "observation_year": [2024, 2024],
            "gdp_pc_usd_2015": [50000.0, 48000.0],
        }
    )
    buckets = pl.DataFrame({"country_iso": ["GB", "DE"], "bucket": [4, 3]})
    authority = SchemaAuthority(
        ingress_ref="schemas.ingress.layer1.yaml#/merchant_ids",
        segment_ref="schemas.1A.yaml",
        rng_ref="schemas.layer1.yaml#/rng/events/core",
    )
    context = build_run_context(
        merchant_table=merchants,
        iso_table=iso,
        gdp_table=gdp,
        bucket_table=buckets,
        schema_authority=authority,
    )
    return context, authority


def test_context_maps_channels(sample_context):
    context, _ = sample_context
    table = context.merchants.merchants
    assert table.get_column("channel_sym").to_list() == ["CP", "CNP"]
    assert table.get_column("merchant_u64").dtype == pl.UInt64


def test_parameter_hash_roundtrip(tmp_path: Path):
    file_a = tmp_path / "hurdle_coefficients.yaml"
    file_b = tmp_path / "nb_dispersion_coefficients.yaml"
    file_c = tmp_path / "crossborder_hyperparams.yaml"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")
    file_c.write_text("c", encoding="utf-8")

    digests = hash_artifacts([file_a, file_b, file_c], error_prefix="E_PARAM")
    result = compute_parameter_hash(digests)
    assert len(result.parameter_hash) == 64
    # Deterministic: re-compute and compare
    again = compute_parameter_hash(digests)
    assert again.parameter_hash == result.parameter_hash


def test_philox_engine_deterministic():
    manifest = bytes.fromhex("ab" * 32)
    engine = PhiloxEngine(seed=1234, manifest_fingerprint=manifest)
    substream_a = engine.derive_substream("unit_test", [])
    substream_b = engine.derive_substream("unit_test", [])
    assert substream_a.uniform() == pytest.approx(substream_b.uniform())


def test_design_vectors(sample_context):
    context, _ = sample_context
    hurdle_yaml = {
        "dicts": {
            "mcc": [5411, 5732],
            "channel": ["CP", "CNP"],
            "gdp_bucket": [1, 2, 3, 4, 5],
        },
        "beta": [0.1] + [0.0] * 2 + [0.0, 0.0] + [0.0] * 5,
        "beta_mu": [0.2] + [0.0] * 2 + [0.0, 0.0],
    }
    dispersion_yaml = {
        "dicts": {"mcc": [5411, 5732], "channel": ["CP", "CNP"]},
        "beta_phi": [0.3] + [0.0] * 2 + [0.0, 0.0] + [0.1],
    }
    hurdle = load_hurdle_coefficients(hurdle_yaml)
    dispersion = load_dispersion_coefficients(
        dispersion_yaml, reference=hurdle.dictionaries
    )
    vectors = list(iter_design_vectors(context, hurdle=hurdle, dispersion=dispersion))
    assert len(vectors) == 2
    assert math.isclose(vectors[0].log_gdp, math.log(50000.0))


def test_crossborder_eligibility(sample_context):
    context, _ = sample_context
    cb_yaml = {
        "eligibility": {
            "rule_set_id": "elig.v1",
            "default_decision": "deny",
            "rules": [
                {
                    "id": "ALLOW_GB",
                    "priority": 10,
                    "decision": "allow",
                    "mcc": ["*"],
                    "channel": ["*"],
                    "iso": ["GB"],
                }
            ],
        }
    }
    bundle = load_crossborder_eligibility(cb_yaml, iso_set=set(context.iso_countries))
    assert isinstance(bundle, CrossborderEligibility)
    flags = evaluate_eligibility(
        context, bundle=bundle, parameter_hash="deadbeef", produced_by_fingerprint=None
    )
    assert flags.filter(pl.col("merchant_id") == 1).to_dicts()[0]["is_eligible"] is True
    assert (
        flags.filter(pl.col("merchant_id") == 2).to_dicts()[0]["is_eligible"] is False
    )


def test_run_id_uniqueness():
    manifest_bytes = bytes.fromhex("12" * 32)
    run_id_a = compute_run_id(
        manifest_fingerprint_bytes=manifest_bytes, seed=1, start_time_ns=100
    )
    run_id_b = compute_run_id(
        manifest_fingerprint_bytes=manifest_bytes,
        seed=1,
        start_time_ns=100,
        existing_ids={run_id_a},
    )
    assert run_id_a != run_id_b
