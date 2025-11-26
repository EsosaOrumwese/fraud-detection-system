from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest

from engine.layers.l1.seg_3A.s5_zone_alloc import ZoneAllocInputs, ZoneAllocRunner
from engine.layers.l1.seg_3A.s6_validation import ValidationInputs, ValidationRunner
from engine.layers.l1.seg_3A.s7_bundle import BundleInputs, BundleRunner


def _write_yaml(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _write_json(path: Path, payload) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
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
  - id: s3_zone_shares
    path: data/layer1/3A/s3_zone_shares/seed={seed}/fingerprint={manifest_fingerprint}/
    schema_ref: schemas.3A.yaml#/plan/s3_zone_shares
  - id: s4_zone_counts
    path: data/layer1/3A/s4_zone_counts/seed={seed}/fingerprint={manifest_fingerprint}/
    schema_ref: schemas.3A.yaml#/plan/s4_zone_counts
  - id: s2_country_zone_priors
    path: data/layer1/3A/s2_country_zone_priors/parameter_hash={parameter_hash}/
    schema_ref: schemas.3A.yaml#/plan/s2_country_zone_priors
  - id: zone_alloc
    path: data/layer1/3A/zone_alloc/seed={seed}/fingerprint={fingerprint}/
    schema_ref: schemas.3A.yaml#/egress/zone_alloc
  - id: zone_alloc_universe_hash
    path: data/layer1/3A/zone_universe/fingerprint={manifest_fingerprint}/zone_alloc_universe_hash.json
    schema_ref: schemas.3A.yaml#/validation/zone_alloc_universe_hash
  - id: s6_validation_report_3A
    path: data/layer1/3A/s6_validation_report/fingerprint={manifest_fingerprint}/report.json
    schema_ref: schemas.3A.yaml#/validation/s6_validation_report_3A
  - id: s6_issue_table_3A
    path: data/layer1/3A/s6_issues/fingerprint={manifest_fingerprint}/issues.parquet
    schema_ref: schemas.3A.yaml#/validation/s6_issue_table_3A
  - id: s6_receipt_3A
    path: data/layer1/3A/s6_receipt/fingerprint={manifest_fingerprint}/s6_receipt.json
    schema_ref: schemas.3A.yaml#/validation/s6_receipt_3A
  - id: validation_bundle_3A
    path: data/layer1/3A/validation/fingerprint={manifest_fingerprint}/
    schema_ref: schemas.layer1.yaml#/validation/validation_bundle_index_3A
  - id: _passed.flag_3A
    path: data/layer1/3A/validation/fingerprint={manifest_fingerprint}/_passed.flag_3A
    schema_ref: schemas.layer1.yaml#/validation/passed_flag_3A
reports:
  - id: segment_state_runs
    path: reports/l1/segment_states/segment_state_runs.jsonl
    schema_ref: schemas.layer1.yaml#/run_report/segment_state_run
"""


def _build_dictionary(tmp: Path) -> Path:
    dictionary_path = tmp / "dictionary.yaml"
    _write_yaml(dictionary_path, _dictionary_payload())
    return dictionary_path


def test_s5_zone_alloc_and_s6_validation():
    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        dictionary_path = _build_dictionary(base)
        manifest = "f" * 64
        param_hash = "e" * 64
        seed = 456

        receipt_path = base / f"data/layer1/3A/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt_3A.json"
        _write_receipt(receipt_path, manifest=manifest, seed=seed, parameter_hash=param_hash)

        sealed_dir = base / f"data/layer1/3A/sealed_inputs/fingerprint={manifest}"
        sealed_dir.mkdir(parents=True, exist_ok=True)
        day_effect_path = base / "policies/day_effect_policy_v1.yaml"
        _write_yaml(day_effect_path, "policy_id: day_effect_policy_v1\nversion: 1.0.0\n")
        sealed_df = pl.DataFrame(
            [
                {
                    "manifest_fingerprint": manifest,
                    "owner_segment": "2B",
                    "artefact_kind": "policy",
                    "logical_id": "day_effect_policy_v1",
                    "path": str(day_effect_path),
                    "schema_ref": "schemas.2B.yaml#/policy/day_effect_policy_v1",
                    "sha256_hex": "a" * 64,
                    "role": "day_effect",
                }
            ]
        )
        sealed_df.write_parquet(sealed_dir / "sealed_inputs_3A.parquet")

        s1_dir = base / f"data/layer1/3A/s1_escalation_queue/seed={seed}/fingerprint={manifest}"
        s1_dir.mkdir(parents=True, exist_ok=True)
        s1_df = pl.DataFrame(
            {
                "seed": [seed],
                "manifest_fingerprint": [manifest],
                "merchant_id": [99],
                "legal_country_iso": ["US"],
                "site_count": [3],
                "zone_count_country": [2],
                "is_escalated": [True],
                "decision_reason": ["default"],
                "mixture_policy_id": ["mix"],
                "mixture_policy_version": ["1.0"],
                "theta_digest": ["b" * 64],
                "eligible_for_escalation": [True],
                "dominant_zone_share_bucket": [">=50"],
                "notes": [None],
            }
        )
        s1_df.write_parquet(s1_dir / "part-0.parquet")

        s3_dir = base / f"data/layer1/3A/s3_zone_shares/seed={seed}/fingerprint={manifest}"
        s3_dir.mkdir(parents=True, exist_ok=True)
        s3_df = pl.DataFrame(
            {
                "seed": [seed, seed],
                "fingerprint": [manifest, manifest],
                "merchant_id": [99, 99],
                "legal_country_iso": ["US", "US"],
                "tzid": ["TZ_A", "TZ_B"],
                "share_drawn": [0.6, 0.4],
                "share_sum_country": [1.0, 1.0],
                "alpha_sum_country": [1.0, 1.0],
                "prior_pack_id": ["priors", "priors"],
                "prior_pack_version": ["1.0", "1.0"],
                "floor_policy_id": ["floor", "floor"],
                "floor_policy_version": ["1.0", "1.0"],
                "rng_module": ["m", "m"],
                "rng_substream_label": ["l", "l"],
                "rng_stream_id": ["s", "s"],
                "rng_event_id": [None, None],
                "notes": [None, None],
            }
        )
        s3_df.write_parquet(s3_dir / "part-0.parquet")

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

        s4_dir = base / f"data/layer1/3A/s4_zone_counts/seed={seed}/fingerprint={manifest}"
        s4_dir.mkdir(parents=True, exist_ok=True)
        s4_df = pl.DataFrame(
            {
                "seed": [seed, seed],
                "fingerprint": [manifest, manifest],
                "merchant_id": [99, 99],
                "legal_country_iso": ["US", "US"],
                "tzid": ["TZ_A", "TZ_B"],
                "zone_site_count": [2, 1],
                "zone_site_count_sum": [3, 3],
                "share_sum_country": [1.0, 1.0],
                "fractional_target": [None, None],
                "residual_rank": [1, 2],
                "prior_pack_id": ["priors", "priors"],
                "prior_pack_version": ["1.0", "1.0"],
                "floor_policy_id": ["floor", "floor"],
                "floor_policy_version": ["1.0", "1.0"],
                "alpha_sum_country": [1.0, 1.0],
                "notes": [None, None],
            }
        )
        s4_df.write_parquet(s4_dir / "part-0.parquet")

        s5_runner = ZoneAllocRunner()
        s5_result = s5_runner.run(
            ZoneAllocInputs(
                data_root=base,
                manifest_fingerprint=manifest,
                parameter_hash=param_hash,
                seed=seed,
                dictionary_path=dictionary_path,
            )
        )
        zone_alloc = pl.read_parquet(s5_result.output_path / "part-0.parquet")
        assert zone_alloc.height == 2
        assert set(zone_alloc["zone_site_count"]) == {1, 2}
        assert s5_result.universe_hash_path.exists()
        assert s5_result.run_report_path.exists()

        s6_runner = ValidationRunner()
        s6_result = s6_runner.run(
            ValidationInputs(
                data_root=base,
                manifest_fingerprint=manifest,
                parameter_hash=param_hash,
                seed=seed,
                dictionary_path=dictionary_path,
            )
        )
        bundle_root = s6_result.validation_bundle_path
        assert (bundle_root / "_passed.flag_3A").exists()
        assert (bundle_root / "s6_validation_report_3A.json").exists()
        assert s6_result.receipt_path.exists()

        # S7
        s7_runner = BundleRunner()
        s7_result = s7_runner.run(
            BundleInputs(
                data_root=base,
                manifest_fingerprint=manifest,
                parameter_hash=param_hash,
                seed=seed,
                dictionary_path=dictionary_path,
            )
        )
        assert (s7_result.bundle_path / "index.json").exists()
        assert s7_result.passed_flag_path.exists()
