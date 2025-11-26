import json
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest

from engine.layers.l1.seg_3A.s0_gate.l0 import aggregate_sha256, expand_files, hash_files
from engine.layers.l1.seg_3A.s1_escalation import EscalationInputs, EscalationRunner
from engine.layers.l1.seg_3A.s2_priors import PriorsInputs, PriorsRunner


def _write_yaml(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sealed_row(
    *,
    manifest: str,
    logical_id: str,
    path: Path,
    owner_segment: str = "3A",
    artefact_kind: str = "policy",
    schema_ref: str,
    role: str,
    license_class: str = "internal",
) -> dict[str, object]:
    files = expand_files(path)
    digest = aggregate_sha256(hash_files(files, error_prefix=logical_id))
    return {
        "manifest_fingerprint": manifest,
        "owner_segment": owner_segment,
        "artefact_kind": artefact_kind,
        "logical_id": logical_id,
        "path": str(path),
        "schema_ref": schema_ref,
        "role": role,
        "license_class": license_class,
        "sha256_hex": digest,
    }


def _write_receipt(path: Path, *, manifest: str, seed: int | str) -> None:
    payload = {
        "version": "1.0.0",
        "manifest_fingerprint": manifest,
        "parameter_hash": "d" * 64,
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
"""


def _build_dictionary(tmp: Path) -> Path:
    dictionary_path = tmp / "dictionary.yaml"
    _write_yaml(dictionary_path, _dictionary_payload())
    return dictionary_path


def test_s1_escalation_runner_builds_queue():
    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        dictionary_path = _build_dictionary(base)
        manifest = "a" * 64
        seed = 101
        sealed_dir = base / f"data/layer1/3A/sealed_inputs/fingerprint={manifest}"
        sealed_dir.mkdir(parents=True, exist_ok=True)
        mixture_path = base / "policies/zone_mixture_policy.yaml"
        _write_yaml(
            mixture_path,
            """
policy_id: mix
version: 1.0.0
theta_mix: 0.5
rules:
  - metric: min_sites
    threshold: 2
    decision_reason: below_min_sites
  - metric: min_zone_count
    threshold: 2
    decision_reason: single_zone_country
  - metric: share_bucket
    threshold: 0.5
    decision_reason: share_low
    bucket: "0-50"
  - metric: share_bucket
    threshold: 1.0
    decision_reason: share_high
    bucket: ">=50"
""",
        )
        tz_world_path = base / "reference/spatial/tz_world/2025a/tz_world.parquet"
        tz_world_path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame({"country_iso": ["US", "US"], "tzid": ["TZ_A", "TZ_B"]}).write_parquet(
            tz_world_path
        )
        iso_path = base / "reference/iso/iso_canonical/2024-12-31/iso.parquet"
        iso_path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame({"country_iso": ["US"]}).write_parquet(iso_path)

        outlet_dir = base / f"data/layer1/1A/outlet_catalogue/seed={seed}/fingerprint={manifest}"
        outlet_dir.mkdir(parents=True, exist_ok=True)
        outlet_path = outlet_dir / "outlet_catalogue.parquet"
        pl.DataFrame(
            {
                "merchant_id": [1, 1, 2],
                "legal_country_iso": ["US", "US", "US"],
            }
        ).write_parquet(outlet_path)

        sealed_df = pl.DataFrame(
            [
                _sealed_row(
                    manifest=manifest,
                    logical_id="zone_mixture_policy",
                    path=mixture_path,
                    schema_ref="schemas.3A.yaml#/policy/zone_mixture_policy_v1",
                    role="mix",
                ),
                _sealed_row(
                    manifest=manifest,
                    logical_id="tz_world_2025a",
                    path=tz_world_path,
                    owner_segment="ingress",
                    artefact_kind="reference",
                    schema_ref="schemas.ingress.layer1.yaml#/tz_world_2025a",
                    role="tz",
                    license_class="ODbL",
                ),
                _sealed_row(
                    manifest=manifest,
                    logical_id="iso3166_canonical_2024",
                    path=iso_path,
                    owner_segment="ingress",
                    artefact_kind="reference",
                    schema_ref="schemas.ingress.layer1.yaml#/iso3166_canonical_2024",
                    role="iso",
                    license_class="CC-BY-4.0",
                ),
                _sealed_row(
                    manifest=manifest,
                    logical_id="outlet_catalogue",
                    path=outlet_path,
                    owner_segment="1A",
                    artefact_kind="egress",
                    schema_ref="schemas.1A.yaml#/egress/outlet_catalogue",
                    role="catalogue",
                ),
            ]
        )
        sealed_df.write_parquet(sealed_dir / "sealed_inputs_3A.parquet")
        assert (sealed_dir / "sealed_inputs_3A.parquet").exists()
        receipt_path = base / f"data/layer1/3A/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt_3A.json"
        _write_receipt(receipt_path, manifest=manifest, seed=seed)
        assert receipt_path.exists()

        runner = EscalationRunner()
        result = runner.run(
            EscalationInputs(
                data_root=base,
                manifest_fingerprint=manifest,
                seed=seed,
                dictionary_path=dictionary_path,
            )
        )

        out_df = pl.read_parquet(result.output_path / "part-0.parquet").sort("merchant_id")
        assert out_df.shape[0] == 2
        first_row, second_row = out_df.to_dicts()
        assert first_row["site_count"] == 2
        assert first_row["is_escalated"] is True
        assert first_row["decision_reason"] == "default_escalation"
        assert first_row["dominant_zone_share_bucket"] == ">=50"
        assert second_row["is_escalated"] is False
        assert second_row["decision_reason"] == "below_min_sites"
        assert second_row["dominant_zone_share_bucket"] == ">=50"
        assert result.run_report_path.exists()


def test_s2_priors_runner_builds_priors():
    with TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        dictionary_path = _build_dictionary(base)
        manifest = "b" * 64
        param_hash = "c" * 64
        sealed_dir = base / f"data/layer1/3A/sealed_inputs/fingerprint={manifest}"
        sealed_dir.mkdir(parents=True, exist_ok=True)
        prior_path = base / "policies/country_zone_alphas.yaml"
        _write_yaml(
            prior_path,
            """
version: 1.0.0
countries:
  US:
    tzid_alphas:
      - tzid: TZ_A
        alpha: 0.4
      - tzid: TZ_B
        alpha: 0.6
""",
        )
        floor_path = base / "policies/zone_floor_policy.yaml"
        _write_yaml(
            floor_path,
            """
version: 1.0.0
floors:
  - tzid: TZ_A
    floor_value: 0.1
    bump_threshold: 0.0
  - tzid: TZ_B
    floor_value: 0.1
    bump_threshold: 0.0
""",
        )
        tz_world_path = base / "reference/spatial/tz_world/2025a/tz_world.parquet"
        tz_world_path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame({"country_iso": ["US", "US"], "tzid": ["TZ_A", "TZ_B"]}).write_parquet(
            tz_world_path
        )
        sealed_df = pl.DataFrame(
            [
                _sealed_row(
                    manifest=manifest,
                    logical_id="country_zone_alphas",
                    path=prior_path,
                    schema_ref="schemas.3A.yaml#/policy/country_zone_alphas_v1",
                    role="prior",
                ),
                _sealed_row(
                    manifest=manifest,
                    logical_id="zone_floor_policy",
                    path=floor_path,
                    schema_ref="schemas.3A.yaml#/policy/zone_floor_policy_v1",
                    role="floor",
                ),
                _sealed_row(
                    manifest=manifest,
                    logical_id="tz_world_2025a",
                    path=tz_world_path,
                    owner_segment="ingress",
                    artefact_kind="reference",
                    schema_ref="schemas.ingress.layer1.yaml#/tz_world_2025a",
                    role="tz",
                    license_class="ODbL",
                ),
            ]
        )
        sealed_df.write_parquet(sealed_dir / "sealed_inputs_3A.parquet")
        assert (sealed_dir / "sealed_inputs_3A.parquet").exists()
        receipt_path = base / f"data/layer1/3A/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt_3A.json"
        _write_receipt(receipt_path, manifest=manifest, seed=0)
        assert receipt_path.exists()

        runner = PriorsRunner()
        result = runner.run(
            PriorsInputs(
                data_root=base,
                manifest_fingerprint=manifest,
                parameter_hash=param_hash,
                dictionary_path=dictionary_path,
            )
        )

        out_df = pl.read_parquet(result.output_path / "part-0.parquet")
        assert out_df.shape[0] == 2
        assert set(out_df["country_iso"]) == {"US"}
        assert pytest.approx(out_df.filter(pl.col("tzid") == "TZ_A")["share_effective"][0], 1e-6) == 0.4
        assert result.run_report_path.exists()
