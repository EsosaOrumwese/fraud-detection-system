import json
import math

import pytest

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error
from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine
from engine.layers.l1.seg_1A.s4_ztp_target import (
    S4HyperParameters,
    S4MerchantTarget,
    ZTPEventWriter,
    compute_lambda_regime,
    derive_poisson_substream,
    run_sampler,
)


def _make_writer(tmp_path, *, seed=101, parameter_hash="a" * 64, manifest="b" * 64, run="c" * 32):
    """Create a writer backed by a unique tmp directory."""

    base = tmp_path / f"seed={seed}"
    base.mkdir(parents=True, exist_ok=True)
    return ZTPEventWriter(
        base_path=base,
        seed=seed,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest,
        run_id=run,
    )


def _make_substream(*, seed: int, manifest: str, merchant_id: int):
    engine = PhiloxEngine(seed=seed, manifest_fingerprint=manifest)
    return derive_poisson_substream(engine, merchant_id=merchant_id)


def test_compute_lambda_regime_threshold_and_regime():
    hyper = S4HyperParameters(theta0=math.log(9.0), theta1=0.0, theta2=None)
    result = compute_lambda_regime(hyperparams=hyper, n_outlets=4, feature_value=0.0)
    assert result.lambda_extra == pytest.approx(9.0)
    assert result.regime == "inversion"

    hyper_hi = S4HyperParameters(theta0=math.log(12.0), theta1=0.0, theta2=None)
    result_hi = compute_lambda_regime(hyperparams=hyper_hi, n_outlets=4, feature_value=0.0)
    assert result_hi.lambda_extra == pytest.approx(12.0)
    assert result_hi.regime == "ptrs"


def test_compute_lambda_regime_validations():
    hyper = S4HyperParameters(theta0=0.0, theta1=0.0, theta2=0.0)

    with pytest.raises(S0Error) as exc:
        compute_lambda_regime(hyperparams=hyper, n_outlets=1, feature_value=0.0)
    assert exc.value.context.code == "ERR_S4_BRANCH_PURITY"

    with pytest.raises(S0Error) as exc:
        compute_lambda_regime(hyperparams=hyper, n_outlets=4, feature_value=1.1)
    assert exc.value.context.code == "ERR_S4_FEATURE_DOMAIN"


def test_run_sampler_accepts_first_attempt(tmp_path):
    seed = 123
    manifest = "d" * 64
    merchant_id = 42

    writer = _make_writer(tmp_path, seed=seed, manifest=manifest)
    substream = _make_substream(seed=seed, manifest=manifest, merchant_id=merchant_id)

    hyper = S4HyperParameters(theta0=0.5, theta1=0.1, theta2=0.0, max_zero_attempts=5, exhaustion_policy="abort")
    merchant = S4MerchantTarget(
        merchant_id=merchant_id,
        n_outlets=5,
        admissible_foreign_count=3,
        is_multi=True,
        is_eligible=True,
        feature_value=0.2,
    )
    lambda_regime = compute_lambda_regime(
        hyperparams=hyper,
        n_outlets=merchant.n_outlets,
        feature_value=merchant.feature_value,
    )

    outcome = run_sampler(
        merchant=merchant,
        lambda_regime=lambda_regime,
        hyperparams=hyper,
        admissible_foreign_count=merchant.admissible_foreign_count,
        poisson_substream=substream,
        writer=writer,
    )

    assert outcome.k_target == 4
    assert outcome.attempts == 1
    assert not outcome.exhausted

    poisson_records = [
        json.loads(line)
        for line in writer.poisson_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(poisson_records) == 1
    assert poisson_records[0]["context"] == "ztp"
    assert poisson_records[0]["attempt"] == 1
    assert poisson_records[0]["k"] == 4

    assert not writer.rejection_events_path.exists()
    assert not writer.retry_exhausted_events_path.exists()

    final_records = [
        json.loads(line)
        for line in writer.final_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(final_records) == 1
    final = final_records[0]
    assert final["exhausted"] is False
    assert final["K_target"] == 4
    assert final["attempts"] == 1
    assert final["regime"] == "inversion"


def test_run_sampler_abort_policy_emits_retry(tmp_path):
    seed = 111
    manifest = "4" * 64
    merchant_id = 55

    writer = _make_writer(tmp_path, seed=seed, manifest=manifest, parameter_hash="1" * 64, run="3" * 32)
    substream = _make_substream(seed=seed, manifest=manifest, merchant_id=merchant_id)

    hyper = S4HyperParameters(theta0=-5.0, theta1=0.0, theta2=0.0, max_zero_attempts=2, exhaustion_policy="abort")
    merchant = S4MerchantTarget(
        merchant_id=merchant_id,
        n_outlets=2,
        admissible_foreign_count=2,
        is_multi=True,
        is_eligible=True,
        feature_value=0.0,
    )
    lambda_regime = compute_lambda_regime(
        hyperparams=hyper,
        n_outlets=merchant.n_outlets,
        feature_value=merchant.feature_value,
    )

    outcome = run_sampler(
        merchant=merchant,
        lambda_regime=lambda_regime,
        hyperparams=hyper,
        admissible_foreign_count=merchant.admissible_foreign_count,
        poisson_substream=substream,
        writer=writer,
    )

    assert outcome.k_target is None
    assert outcome.exhausted
    assert outcome.attempts == hyper.max_zero_attempts
    assert writer.retry_exhausted_events_path.exists()
    assert not writer.final_events_path.exists()

    retry_records = [
        json.loads(line)
        for line in writer.retry_exhausted_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(retry_records) == 1
    retry = retry_records[0]
    assert retry["aborted"] is True
    assert retry["attempts"] == hyper.max_zero_attempts
    assert retry["lambda_extra"] == pytest.approx(outcome.lambda_extra)


def test_run_sampler_downgrade_emits_final_with_zero(tmp_path):
    seed = 222
    manifest = "5" * 64
    merchant_id = 77

    writer = _make_writer(tmp_path, seed=seed, manifest=manifest, parameter_hash="6" * 64, run="7" * 32)
    substream = _make_substream(seed=seed, manifest=manifest, merchant_id=merchant_id)

    hyper = S4HyperParameters(theta0=-5.0, theta1=0.0, theta2=0.0, max_zero_attempts=3, exhaustion_policy="downgrade_domestic")
    merchant = S4MerchantTarget(
        merchant_id=merchant_id,
        n_outlets=2,
        admissible_foreign_count=2,
        is_multi=True,
        is_eligible=True,
        feature_value=0.0,
    )
    lambda_regime = compute_lambda_regime(
        hyperparams=hyper,
        n_outlets=merchant.n_outlets,
        feature_value=merchant.feature_value,
    )

    outcome = run_sampler(
        merchant=merchant,
        lambda_regime=lambda_regime,
        hyperparams=hyper,
        admissible_foreign_count=merchant.admissible_foreign_count,
        poisson_substream=substream,
        writer=writer,
    )

    assert outcome.k_target == 0
    assert outcome.exhausted
    assert not writer.retry_exhausted_events_path.exists()
    assert writer.final_events_path.exists()

    final_records = [
        json.loads(line)
        for line in writer.final_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(final_records) == 1
    final = final_records[0]
    assert final["exhausted"] is True
    assert final["K_target"] == 0
    assert final["attempts"] == hyper.max_zero_attempts
    assert "reason" not in final


def test_run_sampler_no_admissible_short_circuit(tmp_path):
    seed = 333
    manifest = "8" * 64
    merchant_id = 88

    writer = _make_writer(tmp_path, seed=seed, manifest=manifest, parameter_hash="9" * 64, run="0" * 32)
    substream = _make_substream(seed=seed, manifest=manifest, merchant_id=merchant_id)

    hyper = S4HyperParameters(theta0=0.25, theta1=0.0, theta2=0.0, max_zero_attempts=5, exhaustion_policy="abort")
    merchant = S4MerchantTarget(
        merchant_id=merchant_id,
        n_outlets=3,
        admissible_foreign_count=0,
        is_multi=True,
        is_eligible=True,
        feature_value=0.5,
    )
    lambda_regime = compute_lambda_regime(
        hyperparams=hyper,
        n_outlets=merchant.n_outlets,
        feature_value=merchant.feature_value,
    )

    outcome = run_sampler(
        merchant=merchant,
        lambda_regime=lambda_regime,
        hyperparams=hyper,
        admissible_foreign_count=0,
        poisson_substream=substream,
        writer=writer,
    )

    assert outcome.k_target == 0
    assert outcome.attempts == 0
    assert not outcome.exhausted
    assert outcome.reason == "no_admissible"

    final_records = [
        json.loads(line)
        for line in writer.final_events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(final_records) == 1
    final = final_records[0]
    assert final["reason"] == "no_admissible"
    assert final["attempts"] == 0
    assert final["K_target"] == 0
