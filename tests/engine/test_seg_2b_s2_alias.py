import hashlib
import json
from pathlib import Path

import polars as pl

from engine.layers.l1.seg_2B.s2_alias import S2AliasInputs, S2AliasRunner


def _write_dictionary(path: Path) -> Path:
    payload = """
version: test
catalogue:
  dictionary_version: test
  registry_version: test
datasets:
  - id: s1_site_weights
    path: data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s1_site_weights
  - id: s2_alias_index
    path: data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/index.json
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s2_alias_index
  - id: s2_alias_blob
    path: data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/alias.bin
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/binary/s2_alias_blob
  - id: s0_gate_receipt_2B
    path: data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/s0_gate_receipt_v1
  - id: sealed_inputs_v1
    path: data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/sealed_inputs_v1
policies:
  - id: alias_layout_policy_v1
    path: contracts/policies/l1/seg_2B/alias_layout_policy_v1.json
    schema_ref: schemas.2B.yaml#/policy/alias_layout_policy_v1
"""
    dictionary_path = path / "dictionary.yaml"
    dictionary_path.write_text(payload.strip(), encoding="utf-8")
    return dictionary_path


def _write_s1_weights(base: Path, seed: int, manifest: str) -> Path:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1, 2],
            "legal_country_iso": ["US", "US", "GB"],
            "site_order": [1, 2, 1],
            "p_weight": [0.25, 0.75, 1.0],
            "quantised_bits": [8, 8, 8],
        }
    )
    dest = base / f"data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)
    return dest


def _write_policy(base: Path) -> Path:
    payload = {
        "version_tag": "test",
        "weight_source": {"id": "uniform", "mode": "uniform"},
        "floor_spec": {"mode": "absolute", "value": 0.0, "fallback": "uniform"},
        "cap_spec": {"mode": "none"},
        "normalisation_epsilon": 1e-9,
        "quantised_bits": 8,
        "quantisation_epsilon": 1e-6,
        "tiny_negative_epsilon": 1e-12,
        "layout_version": "alias.v1",
        "endianness": "little",
        "alignment_bytes": 4,
        "encode_spec": {
            "site_order_bytes": 4,
            "prob_mass_bytes": 4,
            "alias_site_order_bytes": 4,
            "padding_value": "0x00",
            "checksum": {"algorithm": "sha256"},
        },
        "decode_law": "walker_vose_integer_grid",
    }
    path = base / "contracts/policies/l1/seg_2B/alias_layout_policy_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_sealed_inventory(base: Path, manifest: str, policy_path: Path) -> list[dict]:
    rows = [
        {
            "asset_id": "alias_layout_policy_v1",
            "version_tag": "2025.11",
            "sha256_hex": _sha256_file(policy_path),
            "path": "contracts/policies/l1/seg_2B/alias_layout_policy_v1.json",
            "partition": [],
            "schema_ref": "schemas.2B.yaml#/policy/alias_layout_policy_v1",
        },
    ]
    dest = base / f"data/layer1/2B/sealed_inputs/fingerprint={manifest}/sealed_inputs_v1.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows


def _write_receipt(
    base: Path,
    seed: int,
    manifest: str,
    sealed_rows: list[dict],
) -> Path:
    payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": str(seed),
        "parameter_hash": "f" * 64,
        "validation_bundle_path": "bundle",
        "flag_sha256_hex": "e" * 64,
        "verified_at_utc": "2025-11-08T00:00:00.000000Z",
        "sealed_inputs": [
            {"id": row["asset_id"], "partition": row["partition"], "schema_ref": row["schema_ref"]}
            for row in sealed_rows
        ],
        "catalogue_resolution": {"dictionary_version": "test", "registry_version": "test"},
        "determinism_receipt": {
            "policy_ids": ["alias_layout_policy_v1"],
            "policy_digests": [
                row["sha256_hex"]
                for row in sealed_rows
                if row["asset_id"] == "alias_layout_policy_v1"
            ],
        },
    }
    dest = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def _sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    sha.update(path.read_bytes())
    return sha.hexdigest()


def test_s2_alias_runner_builds_blob(tmp_path: Path) -> None:
    manifest = "a" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_weights(tmp_path, seed, manifest)
    policy_path = _write_policy(tmp_path)
    sealed_rows = _write_sealed_inventory(tmp_path, manifest, policy_path)
    _write_receipt(tmp_path, seed, manifest, sealed_rows)

    runner = S2AliasRunner()
    result = runner.run(
        S2AliasInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            emit_run_report_stdout=False,
        )
    )

    assert result.index_path.exists()
    assert result.blob_path.exists()
    index_payload = json.loads(result.index_path.read_text(encoding="utf-8"))
    assert index_payload["layout_version"] == "alias.v1"
    assert index_payload["merchants_count"] == 2
    merchants = index_payload["merchants"]
    assert merchants[0]["merchant_id"] == 1
    assert merchants[0]["offset"] % index_payload["alignment_bytes"] == 0
    blob_bytes = result.blob_path.read_bytes()
    assert len(blob_bytes) == index_payload["blob_size_bytes"]
    assert len(blob_bytes) > 0


def test_s2_alias_runner_resume(tmp_path: Path) -> None:
    manifest = "b" * 64
    seed = 2025110601
    dictionary_path = _write_dictionary(tmp_path)
    _write_s1_weights(tmp_path, seed, manifest)
    policy_path = _write_policy(tmp_path)
    sealed_rows = _write_sealed_inventory(tmp_path, manifest, policy_path)
    _write_receipt(tmp_path, seed, manifest, sealed_rows)
    runner = S2AliasRunner()
    runner.run(
        S2AliasInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            emit_run_report_stdout=False,
        )
    )
    resumed = runner.run(
        S2AliasInputs(
            data_root=tmp_path,
            seed=seed,
            manifest_fingerprint=manifest,
            dictionary_path=dictionary_path,
            resume=True,
            emit_run_report_stdout=False,
        )
    )
    assert resumed.resumed is True

