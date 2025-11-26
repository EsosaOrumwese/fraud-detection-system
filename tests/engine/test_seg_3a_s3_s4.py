from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest

from engine.layers.l1.seg_3A.s3_zone_shares import ZoneSharesInputs, ZoneSharesRunner
from engine.layers.l1.seg_3A.s4_zone_counts import ZoneCountsInputs, ZoneCountsRunner


def _write_yaml(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_receipt(path: Path, *, manifest: str, seed: int | str, parameter_hash: str) -> None:
    payload = {
        "version": "1.0.0",
        "manifest_fingerprint": manifest,
        "parameter_hash": parameter_hash,
        "seed": int(seed),
        "verified_at_utc": "2025-01-01T00:00:00.000000Z",
        "upstream_gates": {
            "segment_1A": {
                "bundle_id": "validation_bundle_1A",
                "bundle_path": "/tmp/validation_1A",
                "flag_path": "/tmp/validation_1A/_passed.flag",
                "sha256_hex": "1" * 64,
                "status": "PASS",
            },
            "segment_1B": {
                "bundle_id": "validation_bundle_1B",
                "bundle_path": "/tmp/validation_1B",
                "flag_path": "/tmp/validation_1B/_passed.flag",
                "sha256_hex": "2" * 64,
                "status": "PASS",
            },
            "segment_2A": {
                "bundle_id": "validation_bundle_2A",
                "bundle_path": "/tmp/validation_2A",
                "flag_path": "/tmp/validation_2A/_passed.flag",
                "sha256_hex": "3" * 64,
                "status": "PASS",
            },
        },
        "catalogue_versions": {},
        "sealed_policy_set": [],
    }
    _write_json(path, payload)


def _dictionary_payload() -> str:
    return """
version: test
datasets:
  - id: s0_gate_receipt_3A
    path: data/layer1/3A/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt_3A.json
    schema_ref: schemas.3A.yaml#/validation/s0_gate_receipt_3A
  - id: sealed_inputs_3A
    path: data/layer1/3A/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_3A.parquet
    schema_ref: schemas.3A.yaml#/validation/sealed_inputs_3A
  - id: s1_escalation_queue
    path: data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest_fingerprint}/
    schema_ref: schemas.3A.yaml#/plan/s1_escalation_queue
  - id: s2_country_zone_priors
    path: data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/
    schema_ref: schemas.3A.yaml#/plan/s2_country_zone_priors
  - id: s3_zone_shares
    path: data/layer1/3A/s3_zone_shares/seed={seed}/fingerprint={manifest_fingerprint}/
    schema_ref: schemas.3A.yaml#/plan/s3_zone_shares
  - id: s4_zone_counts
    path: data/layer1/3A/s4_zone_counts/seed={seed}/fingerprint={manifest_fingerprint}/
    schema_ref: schemas.3A.yaml#/plan/s4_zone_counts
reports:
  - id: segment_state_runs
    path: reports/l1/segment_states/segment_state_runs.jsonl
    schema_ref: schemas.layer1.yaml#/run_report/segment_state_run
"""


def _build_dictionary(tmp: Path) -> Path:
    dictionary_path = tmp / "dictionary.yaml"
    _write_yaml(dictionary_path, _dictionary_payload())
    return dictionary_path


def test_s3_zone_shares_and_s4_counts_end_to_end():
    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        dictionary_path = _build_dictionary(base)
        manifest = "c" * 64
        param_hash = "d" * 64
        seed = 123

        # S0 receipt
        receipt_path = base / f"data/layer1/3A/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt_3A.json"
        _write_receipt(receipt_path, manifest=manifest, seed=seed, parameter_hash=param_hash)

        # S1 escalation queue (two pairs, one non-escalated)
        s1_dir = base / f"data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest}"
        s1_dir.mkdir(parents=True, exist_ok=True)
        s1_df = pl.DataFrame(
            {
                "seed": [seed, seed],
                "manifest_fingerprint": [manifest, manifest],
                "merchant_id": [10, 20],
                "legal_country_iso": ["US", "US"],
                "site_count": [5, 4],
                "zone_count_country": [2, 2],
                "is_escalated": [True, False],
                "decision_reason": ["default", "below_min_sites"],
                "mixture_policy_id": ["mix", "mix"],
                "mixture_policy_version": ["1.0", "1.0"],
                "theta_digest": ["e" * 64, "e" * 64],
                "eligible_for_escalation": [True, False],
                "dominant_zone_share_bucket": [">=50", "0-50"],
                "notes": [None, None],
            }
        )
        s1_df.write_parquet(s1_dir / "part-0.parquet")

        # S2 priors
        s2_dir = base / f"data/layer1/3A/s2_country_zone_priors/parameter_hash={param_hash}"
        s2_dir.mkdir(parents=True, exist_ok=True)
        s2_df = pl.DataFrame(
            {
                "parameter_hash": [param_hash, param_hash],
                "country_iso": ["US", "US"],
                "tzid": ["TZ_A", "TZ_B"],
                "alpha_raw": [0.4, 0.6],
                "alpha_effective": [0.4, 0.6],
                "alpha_sum_country": [1.0, 1.0],
                "prior_pack_id": ["priors", "priors"],
                "prior_pack_version": ["1.0", "1.0"],
                "floor_policy_id": ["floor", "floor"],
                "floor_policy_version": ["1.0", "1.0"],
                "floor_applied": [False, False],
                "bump_applied": [False, False],
                "share_effective": [0.4, 0.6],
                "notes": [None, None],
            }
        )
        s2_df.write_parquet(s2_dir / "part-0.parquet")

        # Run S3
        s3_runner = ZoneSharesRunner()
        s3_result = s3_runner.run(
            ZoneSharesInputs(
                data_root=base,
                manifest_fingerprint=manifest,
                parameter_hash=param_hash,
                seed=seed,
                run_id="run-1",
                dictionary_path=dictionary_path,
            )
        )
        s3_out = pl.read_parquet(s3_result.output_path / "part-0.parquet")
        assert set(s3_out["merchant_id"]) == {10}
        assert s3_out.filter(pl.col("merchant_id") == 10).select(pl.sum("share_drawn"))[0, 0] == pytest.approx(1.0, rel=1e-6)
        assert s3_result.run_report_path.exists()
        assert s3_result.rng_trace_path.exists()

        # Run S4
        s4_runner = ZoneCountsRunner()
        s4_result = s4_runner.run(
            ZoneCountsInputs(
                data_root=base,
                manifest_fingerprint=manifest,
                parameter_hash=param_hash,
                seed=seed,
                dictionary_path=dictionary_path,
            )
        )
        s4_out = pl.read_parquet(s4_result.output_path / "part-0.parquet")
        assert set(s4_out["merchant_id"]) == {10}
        assert s4_out["zone_site_count_sum"].unique().to_list() == [5]
        assert s4_out.select(pl.sum("zone_site_count"))[0, 0] == 5
        assert s4_result.run_report_path.exists()
