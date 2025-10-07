"""Sanity tests for S0 foundations primitives."""

from __future__ import annotations

import json
import math
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_1A.s0_foundations import (
    CrossborderEligibility,
    PhiloxEngine,
    SchemaAuthority,
    build_numeric_policy_attestation,
    build_run_context,
    compute_parameter_hash,
    compute_run_id,
    iter_design_vectors,
    load_crossborder_eligibility,
    load_dispersion_coefficients,
    load_hurdle_coefficients,
    load_math_profile_manifest,
    load_numeric_policy,
    evaluate_eligibility,
)
from engine.layers.l1.seg_1A.s0_foundations.l0.artifacts import hash_artifacts
from engine.layers.l1.seg_1A.s0_foundations.l1.context import RunContext
from engine.layers.l1.seg_1A.s0_foundations.l2.output import S0Outputs, write_outputs
from engine.layers.l1.seg_1A.s0_foundations.l2.runner import S0FoundationsRunner


@pytest.fixture()
def sample_context() -> tuple[RunContext, SchemaAuthority]:
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
        ingress_ref="l1/seg_1A/merchant_ids.schema.json",
        segment_ref=None,
        rng_ref=None,
    )
    context = build_run_context(
        merchant_table=merchants,
        iso_table=iso,
        gdp_table=gdp,
        bucket_table=buckets,
        schema_authority=authority,
    )
    return context, authority


@pytest.fixture()
def parameter_files(tmp_path: Path) -> dict[str, Path]:
    hurdle = {
        "dicts": {
            "mcc": [5411, 5732],
            "channel": ["CP", "CNP"],
            "gdp_bucket": [1, 2, 3, 4, 5],
        },
        "beta": [0.1] + [0.0] * 2 + [0.0, 0.0] + [0.0] * 5,
        "beta_mu": [0.2] + [0.0] * 2 + [0.0, 0.0],
    }
    dispersion = {
        "dicts": {"mcc": [5411, 5732], "channel": ["CP", "CNP"]},
        "beta_phi": [0.3] + [0.0] * 2 + [0.0, 0.0] + [0.1],
    }
    eligibility = {
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
    hurdle_path = tmp_path / "hurdle_coefficients.yaml"
    dispersion_path = tmp_path / "nb_dispersion_coefficients.yaml"
    eligibility_path = tmp_path / "crossborder_hyperparams.yaml"
    hurdle_path.write_text(json.dumps(hurdle), encoding="utf-8")
    dispersion_path.write_text(json.dumps(dispersion), encoding="utf-8")
    eligibility_path.write_text(json.dumps(eligibility), encoding="utf-8")
    return {
        "hurdle_coefficients.yaml": hurdle_path,
        "nb_dispersion_coefficients.yaml": dispersion_path,
        "crossborder_hyperparams.yaml": eligibility_path,
    }


@pytest.fixture()
def governance_files(tmp_path: Path) -> tuple[Path, Path]:
    numeric_policy = {
        "binary_format": "ieee754-binary64",
        "rounding_mode": "rne",
        "fma_allowed": False,
        "flush_to_zero": False,
        "denormals_are_zero": False,
        "sum_policy": "serial_neumaier",
        "parallel_decision_kernels": "disallowed",
        "version": "1.0",
        "nan_inf_is_error": True,
    }
    math_manifest = {
        "math_profile_id": "mlr-math-1.2.0",
        "vendor": "acme",
        "build": "glibc-2.38",
        "functions": ["exp", "log"],
        "artifacts": [{"name": "libmlr_math.so", "sha256": "deadbeef" * 8}],
    }
    policy_path = tmp_path / "numeric_policy.json"
    manifest_path = tmp_path / "math_profile_manifest.json"
    policy_path.write_text(json.dumps(numeric_policy), encoding="utf-8")
    manifest_path.write_text(json.dumps(math_manifest), encoding="utf-8")
    return policy_path, manifest_path


def test_numeric_policy_loader(governance_files):
    policy_path, manifest_path = governance_files
    policy, policy_digest = load_numeric_policy(policy_path)
    profile, profile_digest = load_math_profile_manifest(manifest_path)
    attestation = build_numeric_policy_attestation(
        policy=policy,
        policy_digest=policy_digest,
        math_profile=profile,
        math_digest=profile_digest,
    )
    assert attestation.content["flags"]["binary_format"] == "ieee754-binary64"


@pytest.fixture()
def runner_and_context(parameter_files, governance_files):
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
        ingress_ref="l1/seg_1A/merchant_ids.schema.json",
        segment_ref=None,
        rng_ref=None,
    )
    runner = S0FoundationsRunner(schema_authority=authority)
    policy_path, manifest_path = governance_files
    sealed = runner.seal(
        merchant_table=merchants,
        iso_table=iso,
        gdp_table=gdp,
        bucket_table=buckets,
        parameter_files=parameter_files,
        manifest_artifacts=[],
        git_commit_raw=b"\x00" * 32,
        numeric_policy_path=policy_path,
        math_profile_manifest_path=manifest_path,
    )
    return runner, sealed


def test_outputs_bundle(tmp_path: Path, runner_and_context, parameter_files):
    runner, sealed = runner_and_context
    outputs = runner.build_outputs_bundle(
        sealed=sealed,
        parameter_files=parameter_files,
        include_diagnostics=True,
    )
    assert isinstance(outputs, S0Outputs)
    assert outputs.crossborder_flags.height == 2

    seed = 1234
    run_id = runner.issue_run_id(
        manifest_fingerprint_bytes=sealed.manifest_fingerprint.manifest_fingerprint_bytes,
        seed=seed,
        start_time_ns=100,
    )
    engine = runner.philox_engine(
        seed=seed, manifest_fingerprint=sealed.manifest_fingerprint
    )
    write_outputs(
        base_path=tmp_path,
        sealed=sealed,
        outputs=outputs,
        run_id=run_id,
        seed=seed,
        philox_engine=engine,
    )
    attest_path = (
        tmp_path
        / "validation_bundle"
        / f"manifest_fingerprint={sealed.manifest_fingerprint.manifest_fingerprint}"
        / "numeric_policy_attest.json"
    )
    assert attest_path.exists()


# Existing lightweight tests -------------------------------------------------


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
