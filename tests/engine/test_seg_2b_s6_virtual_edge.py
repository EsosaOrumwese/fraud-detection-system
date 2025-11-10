import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from engine.layers.l1.seg_2B.shared.runtime import RouterVirtualArrival
from engine.layers.l1.seg_2B.s6_virtual_edge import (
    S6VirtualEdgeInputs,
    S6VirtualEdgeRunner,
)
from engine.layers.l1.seg_2B.s0_gate.exceptions import S0GateError


def _write_dictionary(path: Path, *, include_edge_log: bool = True) -> Path:
    log_section = ""
    if include_edge_log:
        log_section = """
  s6_edge_log:
    path: data/layer1/2B/s6_edge_log/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={utc_day}/edge_log.jsonl
    partitioning: [seed, parameter_hash, run_id, utc_day]
"""
    payload = f"""
version: test
catalogue:
  dictionary_version: test
  registry_version: test
policies:
  - id: route_rng_policy_v1
    path: policies/route_rng_policy_v1.json
    partitioning: []
    schema_ref: schemas.2B.yaml#/policy/route_rng_policy_v1
  - id: virtual_edge_policy_v1
    path: policies/virtual_edge_policy_v1.json
    partitioning: []
    schema_ref: schemas.2B.yaml#/policy/virtual_edge_policy_v1
datasets:
  - id: s0_gate_receipt_2B
    path: data/layer1/2B/s0_gate_receipt/fingerprint={{manifest_fingerprint}}/s0_gate_receipt.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/s0_gate_receipt_v1
  - id: sealed_inputs_v1
    path: data/layer1/2B/sealed_inputs/fingerprint={{manifest_fingerprint}}/sealed_inputs_v1.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/sealed_inputs_v1
logs:
  rng_event_cdn_edge_pick:
    path: logs/rng/events/cdn_edge_pick/seed={{seed}}/parameter_hash={{parameter_hash}}/run_id={{run_id}}/
    partitioning: [seed, parameter_hash, run_id]
    schema_ref: schemas.layer1.yaml#/rng/events/cdn_edge_pick
{log_section}  rng_audit_log:
    path: logs/rng/audit/seed={{seed}}/parameter_hash={{parameter_hash}}/run_id={{run_id}}/rng_audit_log.jsonl
    partitioning: [seed, parameter_hash, run_id]
    schema_ref: schemas.layer1.yaml#/rng/core/rng_audit_log
  rng_trace_log:
    path: logs/rng/trace/seed={{seed}}/parameter_hash={{parameter_hash}}/run_id={{run_id}}/rng_trace_log.jsonl
    partitioning: [seed, parameter_hash, run_id]
    schema_ref: schemas.layer1.yaml#/rng/core/rng_trace_log
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
    *,
    manifest: str,
    seed: int,
    parameter_hash: str,
    route_policy: tuple[Path, str, str],
    edge_policy: tuple[Path, str, str],
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
            {"id": "virtual_edge_policy_v1", "partition": [], "schema_ref": "schemas.2B.yaml#/policy/virtual_edge_policy_v1"},
        ],
        "catalogue_resolution": {"dictionary_version": "test", "registry_version": "test"},
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
            "asset_id": "virtual_edge_policy_v1",
            "version_tag": "test",
            "sha256_hex": edge_policy[2],
            "path": edge_policy[0].relative_to(base).as_posix(),
            "partition": [],
            "schema_ref": "schemas.2B.yaml#/policy/virtual_edge_policy_v1",
        },
    ]
    inventory_path = base / f"data/layer1/2B/sealed_inputs/fingerprint={manifest}/sealed_inputs_v1.json"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory_payload, indent=2), encoding="utf-8")


def _build_runner(tmp_path: Path, *, include_edge_log: bool = True) -> tuple[S6VirtualEdgeRunner, S6VirtualEdgeInputs]:
    manifest = "f" * 64
    seed = 2025110601
    parameter_hash = "e" * 64
    dictionary_path = _write_dictionary(tmp_path, include_edge_log=include_edge_log)
    route_policy_payload = {
        "version_tag": "2025.11",
        "algorithm": "philox2x64-10",
        "substreams": [
            {"id": "virtual_edge", "label": "cdn_edge_pick", "max_uniforms": 1},
        ],
    }
    edge_policy_payload = {
        "version_tag": "2025.11",
        "default_edges": [
            {"edge_id": "iad-us", "country_iso": "US", "weight": 0.6},
            {"edge_id": "dub-ie", "country_iso": "IE", "weight": 0.4},
        ],
        "geo_metadata": {
            "iad-us": {"lat": 38.9, "lon": -77.0},
            "dub-ie": {"lat": 53.3, "lon": -6.2},
        },
    }
    route_policy = _write_policy(tmp_path, "route_rng_policy_v1", route_policy_payload)
    edge_policy = _write_policy(tmp_path, "virtual_edge_policy_v1", edge_policy_payload)
    _write_receipt_and_inventory(
        tmp_path,
        manifest=manifest,
        seed=seed,
        parameter_hash=parameter_hash,
        route_policy=route_policy,
        edge_policy=edge_policy,
    )
    runner = S6VirtualEdgeRunner()
    inputs = S6VirtualEdgeInputs(
        data_root=tmp_path,
        seed=seed,
        manifest_fingerprint=manifest,
        parameter_hash=parameter_hash,
        git_commit_hex="deadbeef",
        dictionary_path=dictionary_path,
        arrivals=(),
        emit_edge_log=include_edge_log,
    )
    return runner, inputs


def _virtual_arrival(selection_seq: int = 1) -> RouterVirtualArrival:
    return RouterVirtualArrival(
        merchant_id=1,
        utc_timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        utc_day="2025-01-01",
        tz_group_id="UTC",
        site_id=1_000_000_001,
        selection_seq=selection_seq,
        is_virtual=True,
    )


def test_s6_virtual_edge_runs_with_virtual_arrival(tmp_path: Path) -> None:
    runner, inputs = _build_runner(tmp_path, include_edge_log=True)
    inputs = S6VirtualEdgeInputs(
        data_root=inputs.data_root,
        seed=inputs.seed,
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        git_commit_hex=inputs.git_commit_hex,
        dictionary_path=inputs.dictionary_path,
        arrivals=(_virtual_arrival(),),
        emit_edge_log=True,
    )
    result = runner.run(inputs)

    assert result.virtual_arrivals == 1
    assert result.rng_event_edge_path is not None
    event_file = result.rng_event_edge_path / "part-00000.jsonl"
    assert event_file.exists()
    payloads = [json.loads(line) for line in event_file.read_text(encoding="utf-8").splitlines()]
    assert payloads[0]["edge_id"] in {"iad-us", "dub-ie"}
    assert result.edge_log_paths
    assert result.edge_log_paths[0].exists()
    report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report["component"] == "2B.S6"
    assert report["diagnostics"]["edge_log_enabled"] is True


def test_s6_virtual_edge_handles_zero_virtual_arrivals(tmp_path: Path) -> None:
    runner, inputs = _build_runner(tmp_path, include_edge_log=False)
    result = runner.run(inputs)
    assert result.virtual_arrivals == 0
    assert result.rng_event_edge_path is None
    report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    assert report["diagnostics"]["virtual_arrivals"] == 0


def test_s6_edge_log_requires_dictionary_registration(tmp_path: Path) -> None:
    runner, inputs = _build_runner(tmp_path, include_edge_log=False)
    inputs = S6VirtualEdgeInputs(
        data_root=inputs.data_root,
        seed=inputs.seed,
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        git_commit_hex=inputs.git_commit_hex,
        dictionary_path=inputs.dictionary_path,
        arrivals=(_virtual_arrival(),),
        emit_edge_log=True,
    )
    try:
        runner.run(inputs)
    except S0GateError as exc:
        assert exc.code == "E_S6_DICTIONARY"
    else:  # pragma: no cover - ensure failure if exception not raised
        raise AssertionError("Expected S0GateError when edge log entry missing")
