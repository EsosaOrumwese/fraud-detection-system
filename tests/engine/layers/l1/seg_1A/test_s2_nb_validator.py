import json
from pathlib import Path

import pytest

from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error
from engine.layers.l1.seg_1A.s0_foundations.l1.design import (
    DesignDictionaries,
    DesignVectors,
    DispersionCoefficients,
    HurdleCoefficients,
)
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision
from engine.layers.l1.seg_1A.s2_nb_outlets import (
    S2NegativeBinomialRunner,
    build_deterministic_context,
    validate_nb_run,
)


def _make_coefficients() -> tuple[HurdleCoefficients, DispersionCoefficients]:
    dicts = DesignDictionaries(
        mcc=(1234,),
        channel=("CP", "CNP"),
        gdp_bucket=(1, 2, 3, 4, 5),
    )
    hurdle = HurdleCoefficients(
        dictionaries=dicts,
        beta=tuple(0.0 for _ in range(1 + len(dicts.mcc) + len(dicts.channel) + len(dicts.gdp_bucket))),
        beta_mu=(0.2, 0.1, -0.05, 0.03),
    )
    dispersion = DispersionCoefficients(
        dictionaries=dicts,
        beta_phi=(0.1, -0.02, 0.04, 0.01, 0.5),
    )
    return hurdle, dispersion


def _design_vectors() -> tuple[DesignVectors, ...]:
    return (
        DesignVectors(
            merchant_id=1,
            bucket=1,
            gdp=1000.0,
            log_gdp=float(6.907755278982137),
            x_hurdle=(1.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0),
            x_nb_mean=(1.0, 1.0, 1.0, 0.0),
            x_nb_dispersion=(1.0, 1.0, 1.0, 0.0, float(6.907755278982137)),
        ),
        DesignVectors(
            merchant_id=2,
            bucket=2,
            gdp=1500.0,
            log_gdp=float(7.313220387090301),
            x_hurdle=(1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0),
            x_nb_mean=(1.0, 1.0, 0.0, 1.0),
            x_nb_dispersion=(1.0, 1.0, 0.0, 1.0, float(7.313220387090301)),
        ),
    )


def _decisions() -> tuple[HurdleDecision, ...]:
    return (
        HurdleDecision(
            merchant_id=1,
            eta=0.0,
            pi=0.5,
            deterministic=False,
            is_multi=True,
            u=0.25,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=1,
        ),
        HurdleDecision(
            merchant_id=2,
            eta=0.0,
            pi=0.5,
            deterministic=False,
            is_multi=True,
            u=0.75,
            rng_counter_before=(0, 0),
            rng_counter_after=(0, 1),
            draws=1,
            blocks=1,
        ),
    )


def test_validate_nb_run_passes(tmp_path: Path) -> None:
    hurdle, dispersion = _make_coefficients()
    design_vectors = _design_vectors()
    decisions = _decisions()
    deterministic = build_deterministic_context(
        parameter_hash="a" * 64,
        manifest_fingerprint="b" * 64,
        run_id="c" * 32,
        seed=123456789,
        multi_merchant_ids=[decision.merchant_id for decision in decisions],
        decisions=decisions,
        design_vectors=design_vectors,
        hurdle=hurdle,
        dispersion=dispersion,
    )

    runner = S2NegativeBinomialRunner()
    result = runner.run(base_path=tmp_path, deterministic=deterministic)

    # should not raise
    policy = {
        "corridors": {"rho_reject_max": 1.0, "p99_max": 100},
        "cusum": {"reference_k": 0.5, "threshold_h": 100.0},
    }
    validation_dir = tmp_path / "validation"
    metrics = validate_nb_run(
        base_path=tmp_path,
        deterministic=deterministic,
        expected_finals=result.finals,
        policy=policy,
        output_dir=validation_dir,
    )

    assert {record.merchant_id for record in result.finals} == {1, 2}
    assert all(record.n_outlets >= 2 for record in result.finals)
    assert metrics["merchant_count"] == pytest.approx(2.0)
    assert 0.0 <= metrics["rho_reject"] <= 1.0
    assert (validation_dir / "metrics.csv").exists()
    assert (validation_dir / "cusum_trace.csv").exists()


def test_validate_nb_run_detects_tampered_final(tmp_path: Path) -> None:
    hurdle, dispersion = _make_coefficients()
    design_vectors = _design_vectors()
    decisions = _decisions()
    deterministic = build_deterministic_context(
        parameter_hash="a" * 64,
        manifest_fingerprint="b" * 64,
        run_id="c" * 32,
        seed=987654321,
        multi_merchant_ids=[decision.merchant_id for decision in decisions],
        decisions=decisions,
        design_vectors=design_vectors,
        hurdle=hurdle,
        dispersion=dispersion,
    )

    runner = S2NegativeBinomialRunner()
    result = runner.run(base_path=tmp_path, deterministic=deterministic)

    final_path = result.final_events_path
    lines = final_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["mu"] = tampered["mu"] * 1.1
    lines[0] = json.dumps(tampered, sort_keys=True)
    final_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    policy = {
        "corridors": {"rho_reject_max": 1.0, "p99_max": 100},
        "cusum": {"reference_k": 0.5, "threshold_h": 100.0},
    }
    with pytest.raises(S0Error):
        validate_nb_run(
            base_path=tmp_path,
            deterministic=deterministic,
            expected_finals=result.finals,
            policy=policy,
            output_dir=tmp_path / "validation",
        )


def test_validate_nb_run_requires_policy(tmp_path: Path) -> None:
    hurdle, dispersion = _make_coefficients()
    design_vectors = _design_vectors()
    decisions = _decisions()
    deterministic = build_deterministic_context(
        parameter_hash="f" * 64,
        manifest_fingerprint="e" * 64,
        run_id="d" * 32,
        seed=192837465,
        multi_merchant_ids=[decision.merchant_id for decision in decisions],
        decisions=decisions,
        design_vectors=design_vectors,
        hurdle=hurdle,
        dispersion=dispersion,
    )

    runner = S2NegativeBinomialRunner()
    result = runner.run(base_path=tmp_path, deterministic=deterministic)

    with pytest.raises(S0Error):
        validate_nb_run(
            base_path=tmp_path,
            deterministic=deterministic,
            expected_finals=result.finals,
            policy=None,
            output_dir=None,
        )


def test_validate_nb_run_detects_corridor_breach(tmp_path: Path) -> None:
    hurdle, dispersion = _make_coefficients()
    design_vectors = _design_vectors()
    decisions = _decisions()
    deterministic = build_deterministic_context(
        parameter_hash="1" * 64,
        manifest_fingerprint="2" * 64,
        run_id="3" * 32,
        seed=246813579,
        multi_merchant_ids=[decision.merchant_id for decision in decisions],
        decisions=decisions,
        design_vectors=design_vectors,
        hurdle=hurdle,
        dispersion=dispersion,
    )

    runner = S2NegativeBinomialRunner()
    result = runner.run(base_path=tmp_path, deterministic=deterministic)

    # Force breach by setting zero thresholds
    policy = {
        "corridors": {"rho_reject_max": 0.0, "p99_max": 0},
        "cusum": {"reference_k": 0.0, "threshold_h": 0.0},
    }
    with pytest.raises(S0Error):
        validate_nb_run(
            base_path=tmp_path,
            deterministic=deterministic,
            expected_finals=result.finals,
            policy=policy,
            output_dir=tmp_path / "validation",
        )
