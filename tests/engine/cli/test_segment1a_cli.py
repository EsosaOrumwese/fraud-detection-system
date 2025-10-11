from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import engine.cli.segment1a as segment1a
from engine.cli.segment1a import main as run_segment1a
from engine.scenario_runner.l1_seg_1A import Segment1ARunResult


def _touch(path: Path) -> Path:
    """Create an empty file and return the resolved path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path.resolve()


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_segment1a_cli_passes_s4_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    merchant_table = _touch(tmp_path / "merchant.parquet")
    iso_table = _touch(tmp_path / "iso.parquet")
    gdp_table = _touch(tmp_path / "gdp.parquet")
    bucket_table = _touch(tmp_path / "bucket.parquet")
    validation_policy = tmp_path / "validation.yaml"
    validation_policy.write_text("corridors: {}", encoding="utf-8")

    features_path = _touch(tmp_path / "features.parquet")
    validation_output_dir = tmp_path / "s4_validation"
    validation_output_dir.mkdir()

    # Pre-create output paths that the CLI logs.
    parameter_hash = "a" * 64
    manifest_fingerprint = "b" * 64
    run_id = "c" * 32
    seed = 987654321

    poisson_path = _touch(output_dir / "logs" / "rng" / "events" / "poisson_component" / "part-00000.jsonl")
    rejection_path = _touch(output_dir / "logs" / "rng" / "events" / "ztp_rejection" / "part-00000.jsonl")
    retry_path = _touch(output_dir / "logs" / "rng" / "events" / "ztp_retry_exhausted" / "part-00000.jsonl")
    final_path = _touch(output_dir / "logs" / "rng" / "events" / "ztp_final" / "part-00000.jsonl")
    trace_path = _touch(output_dir / "logs" / "rng" / "trace" / "rng_trace_log.jsonl")
    candidate_set_path = _touch(output_dir / "parameter_scoped" / "parameter_hash=test" / "s3_candidate_set.parquet")
    nb_final_path = _touch(output_dir / "logs" / "rng" / "events" / "nb_final" / "part-00000.jsonl")
    gamma_path = _touch(output_dir / "logs" / "rng" / "events" / "gamma_component" / "part-00000.jsonl")
    nb_poisson_path = _touch(output_dir / "logs" / "rng" / "events" / "nb_poisson" / "part-00000.jsonl")
    nb_trace_path = _touch(output_dir / "logs" / "rng" / "trace" / "nb_trace.jsonl")
    catalogue_path = _touch(output_dir / "s1_catalogue.json")

    s4_deterministic = SimpleNamespace(
        merchants=(SimpleNamespace(merchant_id=1),),
        run_id=run_id,
        seed=seed,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
    )
    s4_context = SimpleNamespace(
        deterministic=s4_deterministic,
        finals=(),
        poisson_events_path=poisson_path,
        rejection_events_path=rejection_path,
        retry_exhausted_events_path=retry_path,
        final_events_path=final_path,
        trace_path=trace_path,
        metrics={"attempts": 1.0},
        validation_passed=True,
        validation_artifacts_path=None,
    )

    s3_deterministic = SimpleNamespace(merchants=(1,))
    s3_context = SimpleNamespace(
        deterministic=s3_deterministic,
        candidate_set_path=candidate_set_path,
        base_weight_priors_path=None,
        integerised_counts_path=None,
        site_sequence_path=None,
        metrics={"candidates": 1},
        validation_passed=True,
        validation_failed_merchants=None,
        validation_artifacts_path=None,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
    )

    nb_context = SimpleNamespace(
        finals=[SimpleNamespace(merchant_id=1)],
        final_events_path=nb_final_path,
        gamma_events_path=gamma_path,
        poisson_events_path=nb_poisson_path,
        trace_path=nb_trace_path,
        validation_artifacts_path=None,
        metrics={"merchant_count": 1},
    )

    s2_result = SimpleNamespace(deterministic=SimpleNamespace(run_id=run_id))
    s0_result = SimpleNamespace(
        sealed=SimpleNamespace(
            parameter_hash=SimpleNamespace(parameter_hash=parameter_hash),
            manifest_fingerprint=SimpleNamespace(manifest_fingerprint=manifest_fingerprint),
        ),
        outputs=None,
        run_id=run_id,
        base_path=output_dir,
    )

    hurdle_context = SimpleNamespace(
        catalogue_path=catalogue_path,
        multi_merchant_ids=[1],
    )

    fake_result = Segment1ARunResult(
        s0_result=s0_result,
        s1_result=SimpleNamespace(run_id=run_id),
        s2_result=s2_result,
        hurdle_context=hurdle_context,
        nb_context=nb_context,
        s3_result=SimpleNamespace(run_id=run_id),
        s3_context=s3_context,
        s4_result=SimpleNamespace(run_id=run_id),
        s4_context=s4_context,
    )

    captured_kwargs: dict[str, object] = {}

    class FakeSegment1AOrchestrator:
        def run(self, **kwargs):
            captured_kwargs.update(kwargs)
            return fake_result

    monkeypatch.setattr(segment1a, "Segment1AOrchestrator", lambda: FakeSegment1AOrchestrator())

    exit_code = run_segment1a(
        [
            "--output-dir",
            str(output_dir),
            "--merchant-table",
            str(merchant_table),
            "--iso-table",
            str(iso_table),
            "--gdp-table",
            str(gdp_table),
            "--bucket-table",
            str(bucket_table),
            "--git-commit",
            "f" * 40,
            "--seed",
            str(seed),
            "--validation-policy",
            str(validation_policy),
            "--s4-features",
            str(features_path),
            "--s4-validation-output",
            str(validation_output_dir),
        ]
    )

    assert exit_code == 0
    assert captured_kwargs["validate_s4"] is True
    assert captured_kwargs["s4_features"] == features_path
    assert captured_kwargs["s4_validation_output"] == validation_output_dir.resolve()
    assert captured_kwargs["base_path"] == output_dir.resolve()
