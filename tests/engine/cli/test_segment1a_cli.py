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


def _json_load(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _fake_result(
    *,
    output_dir: Path,
    parameter_hash: str,
    manifest_fingerprint: str,
    run_id: str,
    seed: int,
) -> Segment1ARunResult:
    parameter_scoped_dir = (
        output_dir / "parameter_scoped" / f"parameter_hash={parameter_hash}"
    )
    catalogue_path = _touch(parameter_scoped_dir / "s2_nb_catalogue.json")

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
    s1_events_path = _touch(output_dir / "logs" / "rng" / "events" / "hurdle_bernoulli" / "part-00000.jsonl")
    s1_trace_path = _touch(output_dir / "logs" / "rng" / "trace" / "hurdle_trace.jsonl")

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

    s2_result = SimpleNamespace(
        deterministic=SimpleNamespace(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
        )
    )

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

    s5_context = SimpleNamespace(
        weights_path=_touch(output_dir / "weights.parquet"),
        sparse_flag_path=None,
        merchant_currency_path=None,
        stage_log_path=None,
        receipt_path=_touch(output_dir / "S5_VALIDATION.json"),
        policy_digest="0" * 64,
        policy_path=_touch(output_dir / "s5_policy.yaml"),
        policy_semver="1.0.0",
        policy_version="2025-10-16",
    )

    s6_policy = _touch(output_dir / "s6_policy.yaml")
    s6_context = SimpleNamespace(
        deterministic=SimpleNamespace(policy_path=s6_policy),
        events_path=None,
        trace_path=None,
        membership_path=None,
        policy_digest="1" * 64,
        policy_path=s6_policy,
        policy_semver="0.1.0",
        policy_version="2025-10-16",
        events_expected=0,
        events_written=0,
        shortfall_count=0,
        reason_code_counts={},
        membership_rows=0,
        trace_events=0,
        trace_reconciled=True,
        log_all_candidates=True,
        rng_isolation_ok=True,
        validation_payload=None,
        validation_passed=True,
    )

    return Segment1ARunResult(
        s0_result=s0_result,
        s1_result=SimpleNamespace(run_id=run_id, events_path=s1_events_path, trace_path=s1_trace_path),
        s2_result=s2_result,
        hurdle_context=hurdle_context,
        nb_context=nb_context,
        s3_result=SimpleNamespace(run_id=run_id),
        s3_context=s3_context,
        s4_result=SimpleNamespace(run_id=run_id),
        s4_context=s4_context,
        s5_result=SimpleNamespace(run_id=run_id),
        s5_context=s5_context,
        s6_result=SimpleNamespace(run_id=run_id),
        s6_context=s6_context,
    )


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

    parameter_hash = "a" * 64
    manifest_fingerprint = "b" * 64
    run_id = "c" * 32
    seed = 987654321

    fake_result = _fake_result(
        output_dir=output_dir,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id=run_id,
        seed=seed,
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
    assert captured_kwargs["validate_s6"] is True
    assert captured_kwargs["s4_validation_output"] == validation_output_dir.resolve()
    assert captured_kwargs["base_path"] == output_dir.resolve()


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_segment1a_cli_writes_result_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    merchant_table = _touch(tmp_path / "merchant.parquet")
    iso_table = _touch(tmp_path / "iso.parquet")
    gdp_table = _touch(tmp_path / "gdp.parquet")
    bucket_table = _touch(tmp_path / "bucket.parquet")
    validation_policy = tmp_path / "validation.yaml"
    validation_policy.write_text("corridors: {}", encoding="utf-8")

    result_json = tmp_path / "summary.json"
    parameter_hash = "d" * 64
    manifest_fingerprint = "e" * 64
    run_id = "f" * 32
    seed = 123456789

    features_path = _touch(tmp_path / "features.parquet")

    fake_result = _fake_result(
        output_dir=output_dir,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id=run_id,
        seed=seed,
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
            "1" * 40,
            "--seed",
            str(seed),
            "--validation-policy",
            str(validation_policy),
            "--s4-features",
            str(features_path),
            "--result-json",
            str(result_json),
        ]
    )

    assert exit_code == 0
    assert result_json.exists()

    summary = _json_load(result_json)
    assert summary["seed"] == seed
    assert summary["output_dir"] == str(output_dir.resolve())
    assert summary["s0"]["run_id"] == run_id
    assert summary["s4"]["validation_enabled"] is True
    assert summary["s4"]["features_path"] == str(features_path.resolve())
    assert summary["s2"]["catalogue_path"].endswith("s2_nb_catalogue.json")
    assert summary["s3"]["toggles"]["priors"] is False
