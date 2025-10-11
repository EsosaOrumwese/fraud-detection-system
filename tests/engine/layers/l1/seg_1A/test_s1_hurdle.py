import json
from pathlib import Path

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine
from engine.layers.l1.seg_1A.s1_hurdle import HURDLE_MODULE_NAME, HURDLE_SUBSTREAM_LABEL, HurdleDesignRow, S1HurdleRunner, derive_hurdle_substream
from engine.layers.l1.seg_1A.s1_hurdle.l3.validator import validate_hurdle_run


def _create_audit_log(base_path: Path, *, seed: int, parameter_hash: str, run_id: str) -> None:
    rng_log = (
        base_path
        / "rng_logs"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
        / "rng_audit_log.json"
    )
    rng_log.parent.mkdir(parents=True, exist_ok=True)
    rng_log.write_text("{}", encoding="utf-8")


def test_s1_runner_emits_events_and_catalogue(tmp_path):
    parameter_hash = "a" * 64
    manifest_fingerprint = "b" * 64
    seed = 123456789
    run_id = "c" * 32

    _create_audit_log(tmp_path, seed=seed, parameter_hash=parameter_hash, run_id=run_id)

    design_rows = [
        HurdleDesignRow(merchant_id=1, bucket_id=1, design_vector=(1.0,)),
    ]
    beta = (0.0,)  # logistic(0) = 0.5 so the draw will exercise the stochastic path

    runner = S1HurdleRunner()
    result = runner.run(
        base_path=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        beta=beta,
        design_rows=design_rows,
        seed=seed,
        run_id=run_id,
    )

    # Ensure the stochastic decision matches a regenerated Philox uniform
    engine = PhiloxEngine(seed=seed, manifest_fingerprint=manifest_fingerprint)
    regenerated_u = derive_hurdle_substream(engine, merchant_id=1).uniform()
    expected_multi = regenerated_u < 0.5
    assert (1 in result.multi_merchant_ids) == expected_multi

    # Catalogue captures gating metadata
    assert result.catalogue_path.exists()
    catalogue = json.loads(result.catalogue_path.read_text(encoding="utf-8"))
    assert catalogue["module"] == HURDLE_MODULE_NAME
    assert catalogue["substream_label"] == HURDLE_SUBSTREAM_LABEL
    assert set(result.multi_merchant_ids) == set(catalogue["multi_merchant_ids"])
    assert isinstance(result.gated_streams, tuple)
    assert "gated_streams" in catalogue
    assert isinstance(catalogue["gated_streams"], list)

    # Validation should replay the event without raising
    validate_hurdle_run(
        base_path=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        seed=seed,
        run_id=run_id,
        beta=beta,
        design_rows=design_rows,
    )
