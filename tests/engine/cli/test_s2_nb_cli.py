import json
from pathlib import Path

import polars as pl
import pytest

from engine.cli.s2_nb_outlets import main as run_s2_cli


def _write_yaml(path: Path, payload: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _hurdle_event_record(
    *,
    seed: int,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
) -> dict:
    return {
        "ts_utc": "2025-10-10T00:00:00.000000Z",
        "module": "1A.hurdle_sampler",
        "substream_label": "hurdle_bernoulli",
        "seed": seed,
        "run_id": run_id,
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "rng_counter_before_hi": 0,
        "rng_counter_before_lo": 0,
        "rng_counter_after_hi": 0,
        "rng_counter_after_lo": 1,
        "draws": "1",
        "blocks": 1,
        "merchant_id": 1,
        "pi": 0.5,
        "eta": 0.0,
        "deterministic": False,
        "is_multi": True,
        "u": 0.25,
        "gdp_bucket_id": 1,
    }


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_s2_cli_runs_and_writes_outputs(tmp_path: Path) -> None:
    seed = 123456789
    parameter_hash = "a" * 64
    manifest_fingerprint = "b" * 64
    run_id = "c" * 32

    design_path = tmp_path / "design.parquet"
    frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "bucket": [1],
            "gdp_pc_usd_2015": [1000.0],
            "log_gdp_pc_usd_2015": [float(6.907755278982137)],
            "x_hurdle": [[1.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]],
            "x_nb_mean": [[1.0, 1.0, 1.0, 0.0]],
            "x_nb_dispersion": [[1.0, 1.0, 1.0, 0.0, float(6.907755278982137)]],
        }
    )
    frame.write_parquet(design_path)

    hurdle_yaml = {
        "dicts": {
            "mcc": [1234],
            "channel": ["CP", "CNP"],
            "gdp_bucket": [1, 2, 3, 4, 5],
        },
        "beta": [0.0] * 9,
        "beta_mu": [0.2, 0.1, -0.05, 0.03],
    }
    dispersion_yaml = {
        "dicts": {
            "mcc": [1234],
            "channel": ["CP", "CNP"],
            "gdp_bucket": [1, 2, 3, 4, 5],
        },
        "beta_phi": [0.1, -0.02, 0.04, 0.01, 0.5],
    }
    hurdle_path = tmp_path / "hurdle.yaml"
    dispersion_path = tmp_path / "dispersion.yaml"
    _write_yaml(hurdle_path, hurdle_yaml)
    _write_yaml(dispersion_path, dispersion_yaml)
    validation_policy = {
        "corridors": {"rho_reject_max": 1.0, "p99_max": 100},
        "cusum": {"reference_k": 0.5, "threshold_h": 100.0},
    }
    validation_policy_path = tmp_path / "validation_policy.yaml"
    _write_yaml(validation_policy_path, validation_policy)

    hurdle_log_path = (
        tmp_path
        / "logs"
        / "rng"
        / "events"
        / "hurdle_bernoulli"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    hurdle_log_path.mkdir(parents=True, exist_ok=True)
    (hurdle_log_path / "part-00000.jsonl").write_text(
        json.dumps(
            _hurdle_event_record(
                seed=seed,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                run_id=run_id,
            ),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    result_json = tmp_path / "s2_result.json"

    exit_code = run_s2_cli(
        [
            "--output-dir",
            str(tmp_path),
            "--design-matrix",
            str(design_path),
            "--hurdle-coeff",
            str(hurdle_path),
            "--dispersion-coeff",
            str(dispersion_path),
            "--validation-policy",
            str(validation_policy_path),
            "--parameter-hash",
            parameter_hash,
            "--manifest-fingerprint",
            manifest_fingerprint,
            "--run-id",
            run_id,
            "--seed",
            str(seed),
            "--result-json",
            str(result_json),
        ]
    )

    assert exit_code == 0
    assert result_json.exists()
    payload = json.loads(result_json.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["parameter_hash"] == parameter_hash
    assert payload["manifest_fingerprint"] == manifest_fingerprint
    assert payload["seed"] == seed
    assert len(payload["finals"]) == 1
    assert payload["metrics"]["merchant_count"] >= 1
    validation_artifacts_path = payload["validation_artifacts_path"]

    nb_final_path = Path(payload["nb_final_path"])
    gamma_path = Path(payload["gamma_events_path"])
    poisson_path = Path(payload["poisson_events_path"])
    trace_path = Path(payload["trace_path"])

    for path in (nb_final_path, gamma_path, poisson_path, trace_path):
        assert path.exists(), f"Expected output file missing: {path}"

    validation_dir = (
        tmp_path
        / "validation"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
        / "s2"
    )
    assert (validation_dir / "metrics.csv").exists()
    assert (validation_dir / "cusum_trace.csv").exists()

    catalogue_path = (
        tmp_path
        / "parameter_scoped"
        / f"parameter_hash={parameter_hash}"
        / "s2_nb_catalogue.json"
    )
    assert catalogue_path.exists()

    if validation_artifacts_path:
        bundle_dir = (
            tmp_path
            / "validation_bundle"
            / f"manifest_fingerprint={manifest_fingerprint}"
        )
        s2_bundle_dir = bundle_dir / "s2_nb_outlets"
        assert (s2_bundle_dir / "metrics.json").exists()
        assert (s2_bundle_dir / "metrics.csv").exists()
        assert (s2_bundle_dir / "cusum_trace.csv").exists()
