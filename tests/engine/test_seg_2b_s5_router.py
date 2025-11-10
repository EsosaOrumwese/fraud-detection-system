import hashlib
import json
from pathlib import Path

import polars as pl

from engine.layers.l1.seg_2B.s5_router import (
    RouterArrival,
    S5RouterInputs,
    S5RouterRunner,
)


def _write_dictionary(path: Path) -> Path:
    payload = """
version: test
catalogue:
  dictionary_version: test
  registry_version: test
datasets:
  - id: s4_group_weights
    path: data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s4_group_weights
  - id: s1_site_weights
    path: data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s1_site_weights
  - id: site_timezones
    path: data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2A.yaml#/egress/site_timezones
  - id: s2_alias_index
    path: data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest_fingerprint}/
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s2_alias_index
  - id: s2_alias_blob
    path: data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest_fingerprint}/
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
logs:
  rng_event_alias_pick_group:
    path: logs/rng/events/alias_pick_group/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/
    partitioning: [seed, parameter_hash, run_id]
  rng_event_alias_pick_site:
    path: logs/rng/events/alias_pick_site/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/
    partitioning: [seed, parameter_hash, run_id]
  rng_audit_log:
    path: logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl
    partitioning: [seed, parameter_hash, run_id]
  rng_trace_log:
    path: logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl
    partitioning: [seed, parameter_hash, run_id]
  s5_selection_log:
    path: data/layer1/2B/s5_selection_log/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}/selection_log.jsonl
    partitioning: [seed, parameter_hash, run_id, utc_day]
"""
    dictionary_path = path / "dictionary.yaml"
    dictionary_path.write_text(payload.strip(), encoding="utf-8")
    return dictionary_path


def _write_policy(path: Path, asset_id: str, payload: dict) -> tuple[Path, str, str]:
    policy_path = path / "policies" / f"{asset_id}.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    raw_digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    aggregated_digest = hashlib.sha256(raw_digest.encode("ascii")).hexdigest()
    return policy_path, raw_digest, aggregated_digest


def _write_receipt_and_inventory(
    base: Path,
    manifest: str,
    seed: int,
    parameter_hash: str,
    route_policy: tuple[Path, str, str],
    alias_policy: tuple[Path, str, str],
) -> None:
    receipt_payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "validation_bundle_path": "bundle",
        "flag_sha256_hex": "f" * 64,
        "verified_at_utc": "2025-11-09T00:00:00.000000Z",
        "sealed_inputs": [
            {"id": "route_rng_policy_v1", "partition": [], "schema_ref": "schemas.2B.yaml#/policy/route_rng_policy_v1"},
            {"id": "alias_layout_policy_v1", "partition": [], "schema_ref": "schemas.2B.yaml#/policy/alias_layout_policy_v1"},
        ],
        "catalogue_resolution": {"dictionary_version": "test", "registry_version": "test"},
        "determinism_receipt": {
            "engine_commit": "deadbeef",
            "policy_ids": ["route_rng_policy_v1", "alias_layout_policy_v1"],
            "policy_digests": [route_policy[2], alias_policy[2]],
        },
    }
    receipt_path = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt_payload, indent=2), encoding="utf-8")
    inventory_payload = [
        {
            "asset_id": "route_rng_policy_v1",
            "version_tag": "test",
            "sha256_hex": route_policy[2],
            "path": route_policy[0].relative_to(base).as_posix(),
            "partition": [],
            "schema_ref": "schemas.2B.yaml#/policy/route_rng_policy_v1",
        },
        {
            "asset_id": "alias_layout_policy_v1",
            "version_tag": "test",
            "sha256_hex": alias_policy[2],
            "path": alias_policy[0].relative_to(base).as_posix(),
            "partition": [],
            "schema_ref": "schemas.2B.yaml#/policy/alias_layout_policy_v1",
        },
    ]
    inventory_path = base / f"data/layer1/2B/sealed_inputs/fingerprint={manifest}/sealed_inputs_v1.json"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory_payload, indent=2), encoding="utf-8")


def _write_alias_artifacts(base: Path, seed: int, manifest: str, alias_policy_digest: str) -> None:
    index_dir = base / f"data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest}"
    blob_dir = base / f"data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest}"
    index_dir.mkdir(parents=True, exist_ok=True)
    blob_dir.mkdir(parents=True, exist_ok=True)
    blob_bytes = b"alias-binary"
    blob_path = blob_dir / "alias.bin"
    blob_path.write_bytes(blob_bytes)
    blob_sha = hashlib.sha256(blob_bytes).hexdigest()
    index_payload = {
        "layout_version": "1.0",
        "endianness": "little",
        "alignment_bytes": 8,
        "quantised_bits": 16,
        "created_utc": "2025-11-09T00:00:00.000000Z",
        "policy_id": "alias_layout_policy_v1",
        "policy_digest": alias_policy_digest,
        "blob_sha256": blob_sha,
        "blob_size_bytes": len(blob_bytes),
        "merchants_count": 1,
        "merchants": [
            {
                "merchant_id": 1,
                "offset": 0,
                "length": 2,
                "sites": 2,
                "quantised_bits": 16,
                "checksum": "0" * 64,
            }
        ],
    }
    (index_dir / "index.json").write_text(json.dumps(index_payload, indent=2), encoding="utf-8")


def _write_s1_site_weights(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["US", "US"],
            "site_order": [1, 2],
            "p_weight": [0.6, 0.4],
        }
    )
    dest = base / f"data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _write_site_timezones(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["US", "US"],
            "site_order": [1, 2],
            "tzid": ["America/New_York", "Europe/London"],
        }
    )
    dest = base / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _write_group_weights(base: Path, seed: int, manifest: str) -> None:
    df = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "utc_day": ["2025-01-01", "2025-01-02"],
            "tz_group_id": ["America/New_York", "Europe/London"],
            "p_group": [1.0, 1.0],
        }
    )
    dest = base / f"data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest}/part-00000.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dest)


def _build_runner_inputs(tmp_path: Path) -> tuple[S5RouterRunner, S5RouterInputs]:
    manifest = "c" * 64
    seg2a_manifest = "d" * 64
    seed = 2025110601
    parameter_hash = "1" * 64
    dictionary = _write_dictionary(tmp_path)
    route_policy_payload = {
        "version_tag": "2025.11",
        "algorithm": "philox2x64-10",
        "substreams": [
            {"id": "router_core", "label": "alias_pick", "max_uniforms": 2},
        ],
    }
    alias_policy_payload = {
        "version_tag": "2025.11",
        "weight_source": {"id": "s1_site_weights", "mode": "column", "column": "p_weight"},
        "floor_spec": {"mode": "absolute", "fallback": "uniform"},
        "normalisation_epsilon": 1e-9,
        "quantised_bits": 16,
        "quantisation_epsilon": 1e-9,
        "layout_version": "1.0",
        "endianness": "little",
        "alignment_bytes": 8,
        "encode_spec": {
            "site_order_bytes": 4,
            "prob_mass_bytes": 4,
            "alias_site_order_bytes": 4,
            "padding_value": "0x00",
            "checksum": {"algorithm": "sha256"},
        },
        "decode_law": "alias",
    }
    route_policy_path, route_digest_raw, route_digest_agg = _write_policy(tmp_path, "route_rng_policy_v1", route_policy_payload)
    alias_policy_path, alias_digest_raw, alias_digest_agg = _write_policy(tmp_path, "alias_layout_policy_v1", alias_policy_payload)
    _write_receipt_and_inventory(
        tmp_path,
        manifest=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
        route_policy=(route_policy_path, route_digest_raw, route_digest_agg),
        alias_policy=(alias_policy_path, alias_digest_raw, alias_digest_agg),
    )
    _write_alias_artifacts(tmp_path, seed=seed, manifest=manifest, alias_policy_digest=alias_digest_raw)
    _write_s1_site_weights(tmp_path, seed, manifest)
    _write_site_timezones(tmp_path, seed, seg2a_manifest)
    _write_group_weights(tmp_path, seed, manifest)
    runner = S5RouterRunner()
    inputs = S5RouterInputs(
        data_root=tmp_path,
        seed=seed,
        manifest_fingerprint=manifest,
        seg2a_manifest_fingerprint=seg2a_manifest,
        parameter_hash=parameter_hash,
        git_commit_hex="abc123",
        dictionary_path=dictionary,
        emit_selection_log=True,
    )
    return runner, inputs


def test_s5_router_runs_with_default_arrivals(tmp_path: Path) -> None:
    runner, inputs = _build_runner_inputs(tmp_path)
    result = runner.run(inputs)

    assert result.run_report_path.exists()
    report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report["component"] == "2B.S5"
    assert report["policy"]["rng_stream_id"] == "router_core"
    assert report["logging"]["selection_log_enabled"] is True
    assert result.selection_log_paths
    selection_log = result.selection_log_paths[0]
    rows = [json.loads(line) for line in selection_log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["merchant_id"] == 1
    assert result.rng_event_group_path is not None
    assert (result.rng_event_group_path / "part-00000.jsonl").exists()
    assert result.virtual_arrivals == ()


def test_s5_router_consumes_arrivals_file(tmp_path: Path) -> None:
    runner, inputs = _build_runner_inputs(tmp_path)
    arrivals_file = tmp_path / "arrivals.jsonl"
    arrivals_file.write_text(
        json.dumps({"merchant_id": 1, "utc_timestamp": "2025-01-02T12:00:00Z"}) + "\n",
        encoding="utf-8",
    )
    arrivals = [RouterArrival.from_payload({"merchant_id": 1, "utc_timestamp": "2025-01-02T12:00:00Z"})]
    custom_inputs = S5RouterInputs(
        data_root=inputs.data_root,
        seed=inputs.seed,
        manifest_fingerprint=inputs.manifest_fingerprint,
        seg2a_manifest_fingerprint=inputs.seg2a_manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        git_commit_hex=inputs.git_commit_hex,
        arrivals=arrivals,
        dictionary_path=inputs.dictionary_path,
        emit_selection_log=False,
    )
    result = runner.run(custom_inputs)
    assert result.selection_log_paths == ()
    report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report["logging"]["selection_log_enabled"] is False
    assert result.virtual_arrivals == ()


def test_s5_router_records_virtual_arrivals(tmp_path: Path) -> None:
    runner, inputs = _build_runner_inputs(tmp_path)
    arrival_payload = {
        "merchant_id": 1,
        "utc_timestamp": "2025-01-01T08:00:00Z",
        "is_virtual": True,
    }
    arrivals = [RouterArrival.from_payload(arrival_payload)]
    custom_inputs = S5RouterInputs(
        data_root=inputs.data_root,
        seed=inputs.seed,
        manifest_fingerprint=inputs.manifest_fingerprint,
        seg2a_manifest_fingerprint=inputs.seg2a_manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        git_commit_hex=inputs.git_commit_hex,
        arrivals=arrivals,
        dictionary_path=inputs.dictionary_path,
        emit_selection_log=False,
    )
    result = runner.run(custom_inputs)
    assert len(result.virtual_arrivals) == 1
    virtual_record = result.virtual_arrivals[0]
    assert virtual_record.merchant_id == 1
    assert virtual_record.is_virtual is True
    assert virtual_record.site_id > 0
    assert virtual_record.tz_group_id
