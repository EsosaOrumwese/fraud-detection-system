import hashlib
import json
import struct
from pathlib import Path
from typing import Dict, Tuple

import polars as pl
import pytest

from engine.layers.l1.seg_2B.s0_gate.exceptions import S0GateError
from engine.layers.l1.seg_2B.s7_audit import RouterEvidence, S7AuditInputs, S7AuditRunner


SEED = 2025110601
MANIFEST = "c28295891e99fc1307fac8c5b01cce484d81529f7cb943997358b52ac02863f2"
SEG2A_MANIFEST = "cf95dc0ffb781552009e576bdb2016c6d2a3e6c9299c3fe09f3c87655a1534f5"
PARAM_HASH = "7e5feece8844bf9bc38a797114a93f4354d5c540957f0954c5b59d1c5ac72b2f"
S5_RUN_ID = "0123456789abcdef0123456789abcdef"
S6_RUN_ID = "fedcba9876543210fedcba9876543210"
UTC_DAY = "2025-11-09"
UTC_TIMESTAMP = "2025-11-09T00:00:00.000000Z"
SITE_ID = (1 << 32) | 1


def test_s7_audit_reports_router_evidence(tmp_path: Path) -> None:
    runner = S7AuditRunner()
    inputs, _context = _build_inputs(tmp_path)
    result = runner.run(inputs)

    payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert payload["router_evidence"]["s5"]["present"] is True
    assert payload["router_evidence"]["s5"]["selections"] == 1
    assert any(entry["id"] == "V-13" for entry in result.validators)


def test_s7_audit_detects_site_timezone_mismatch(tmp_path: Path) -> None:
    runner = S7AuditRunner()
    inputs, _context = _build_inputs(tmp_path, selection_tz="Etc/GMT+1")
    with pytest.raises(S0GateError):
        runner.run(inputs)


def test_s7_audit_handles_s6_evidence(tmp_path: Path) -> None:
    runner = S7AuditRunner()
    inputs, _context = _build_inputs(tmp_path, include_s6=True)
    result = runner.run(inputs)
    payload = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert payload["router_evidence"]["s6"]["present"] is True
    assert payload["router_evidence"]["s6"]["virtual_arrivals"] == 1
    assert any(entry["id"] == "V-14" for entry in result.validators)


# --------------------------------------------------------------------------- helpers


def _build_inputs(
    tmp_path: Path,
    *,
    selection_tz: str = "Etc/UTC",
    include_s6: bool = False,
) -> Tuple[S7AuditInputs, Dict[str, object]]:
    base = tmp_path / "run"
    base.mkdir(parents=True, exist_ok=True)
    dictionary_path = _write_dictionary(base)
    policies = _stage_policies(base)
    _write_receipt_and_inventory(
        base,
        manifest=MANIFEST,
        seed=SEED,
        parameter_hash=PARAM_HASH,
        policies=policies,
    )
    _write_alias_artifacts(base, seed=SEED, manifest=MANIFEST, alias_policy_digest=policies["alias_layout_policy_v1"]["aggregated"])
    _write_site_weights(base, seed=SEED, manifest=MANIFEST)
    _write_day_surfaces(base, seed=SEED, manifest=MANIFEST)
    _write_site_timezones(base, seed=SEED, seg2a_manifest=SEG2A_MANIFEST)

    s5_paths = _write_s5_evidence(
        base,
        seed=SEED,
        manifest=MANIFEST,
        parameter_hash=PARAM_HASH,
        run_id=S5_RUN_ID,
        tz_group=selection_tz,
    )
    s5_evidence = RouterEvidence(
        run_id=S5_RUN_ID,
        parameter_hash=PARAM_HASH,
        rng_event_group_path=s5_paths["group_dir"],
        rng_event_site_path=s5_paths["site_dir"],
        rng_trace_log_path=s5_paths["trace_path"],
        rng_audit_log_path=s5_paths["audit_path"],
        selection_log_paths=(s5_paths["selection_path"],),
    )

    s6_evidence = None
    if include_s6:
        s6_paths = _write_s6_evidence(
            base,
            seed=SEED,
            manifest=MANIFEST,
            parameter_hash=PARAM_HASH,
            run_id=S6_RUN_ID,
            policy_payload=policies["virtual_edge_policy_v1"]["payload"],
        )
        s6_evidence = RouterEvidence(
            run_id=S6_RUN_ID,
            parameter_hash=PARAM_HASH,
            rng_event_edge_path=s6_paths["edge_dir"],
            rng_trace_log_path=s6_paths["trace_path"],
            rng_audit_log_path=s6_paths["audit_path"],
            edge_log_paths=(s6_paths["edge_log_path"],),
        )

    inputs = S7AuditInputs(
        data_root=base,
        seed=SEED,
        manifest_fingerprint=MANIFEST,
        seg2a_manifest_fingerprint=SEG2A_MANIFEST,
        parameter_hash=PARAM_HASH,
        dictionary_path=dictionary_path,
        s5_evidence=s5_evidence,
        s6_evidence=s6_evidence,
        emit_run_report_stdout=False,
    )
    return inputs, {"base": base}


def _write_dictionary(base: Path) -> Path:
    payload = """
version: test
catalogue:
  dictionary_version: test
  registry_version: test
policies:
  - id: route_rng_policy_v1
    path: policies/route_rng_policy_v1.json
    partitioning: []
    schema_ref: schemas.2B.yaml#/policy/route_rng_policy_v1
  - id: alias_layout_policy_v1
    path: policies/alias_layout_policy_v1.json
    partitioning: []
    schema_ref: schemas.2B.yaml#/policy/alias_layout_policy_v1
  - id: virtual_edge_policy_v1
    path: policies/virtual_edge_policy_v1.json
    partitioning: []
    schema_ref: schemas.2B.yaml#/policy/virtual_edge_policy_v1
datasets:
  - id: s0_gate_receipt_2B
    path: data/layer1/2B/s0_gate_receipt/fingerprint={manifest_fingerprint}/s0_gate_receipt.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/s0_gate_receipt_v1
  - id: sealed_inputs_v1
    path: data/layer1/2B/sealed_inputs/fingerprint={manifest_fingerprint}/sealed_inputs_v1.json
    partitioning: [fingerprint]
    schema_ref: schemas.2B.yaml#/validation/sealed_inputs_v1
  - id: s1_site_weights
    path: data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest_fingerprint}/site_weights.parquet
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
  - id: s3_day_effects
    path: data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest_fingerprint}/s3_day_effects.parquet
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s3_day_effects
  - id: s4_group_weights
    path: data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest_fingerprint}/s4_group_weights.parquet
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/plan/s4_group_weights
  - id: site_timezones
    path: data/layer1/2A/site_timezones/seed={seed}/fingerprint={manifest_fingerprint}/site_timezones.parquet
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2A.yaml#/egress/site_timezones
  - id: s7_audit_report
    path: data/layer1/2B/s7_audit_report/seed={seed}/fingerprint={manifest_fingerprint}/s7_audit_report.json
    partitioning: [seed, fingerprint]
    schema_ref: schemas.2B.yaml#/validation/s7_audit_report_v1
  - id: validation_bundle_2B
    path: data/layer1/2B/validation/fingerprint={manifest_fingerprint}/index.json
    partitioning: [fingerprint]
    schema_ref: schemas.layer1.yaml#/validation/validation_bundle/index_schema
  - id: validation_passed_flag_2B
    path: data/layer1/2B/validation/fingerprint={manifest_fingerprint}/_passed.flag
    partitioning: [fingerprint]
    schema_ref: schemas.layer1.yaml#/validation/passed_flag
"""
    dictionary_path = base / "dictionary.yaml"
    dictionary_path.write_text(payload.strip(), encoding="utf-8")
    return dictionary_path


def _stage_policies(base: Path) -> Dict[str, Dict[str, object]]:
    repo_root = Path(__file__).resolve().parents[2]
    assets = {
        "route_rng_policy_v1": repo_root / "contracts/policies/l1/seg_2B/route_rng_policy_v1.json",
        "alias_layout_policy_v1": repo_root / "contracts/policies/l1/seg_2B/alias_layout_policy_v1.json",
        "virtual_edge_policy_v1": repo_root / "contracts/policies/l1/seg_2B/virtual_edge_policy_v1.json",
    }
    staged: Dict[str, Dict[str, object]] = {}
    for asset_id, src_path in assets.items():
        dest = base / "policies" / src_path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = src_path.read_bytes()
        dest.write_bytes(data)
        raw_digest = hashlib.sha256(data).hexdigest()
        aggregated_digest = hashlib.sha256(raw_digest.encode("ascii")).hexdigest()
        payload = json.loads(dest.read_text(encoding="utf-8"))
        staged[asset_id] = {
            "path": dest,
            "raw": raw_digest,
            "aggregated": aggregated_digest,
            "payload": payload,
        }
    return staged


def _write_receipt_and_inventory(
    base: Path,
    *,
    manifest: str,
    seed: int,
    parameter_hash: str,
    policies: Dict[str, Dict[str, object]],
) -> None:
    receipt_payload = {
        "segment": "2B",
        "state": "S0",
        "manifest_fingerprint": manifest,
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "validation_bundle_path": "bundle",
        "flag_sha256_hex": "f" * 64,
        "verified_at_utc": UTC_TIMESTAMP,
        "sealed_inputs": [
            {"id": key, "partition": [], "schema_ref": f"schemas.2B.yaml#/policy/{key}"}
            for key in ("route_rng_policy_v1", "alias_layout_policy_v1", "virtual_edge_policy_v1")
        ],
        "catalogue_resolution": {"dictionary_version": "test", "registry_version": "test"},
        "determinism_receipt": {
            "engine_commit": "deadbeef",
            "policy_ids": ["route_rng_policy_v1", "alias_layout_policy_v1", "virtual_edge_policy_v1"],
            "policy_digests": [
                policies["route_rng_policy_v1"]["aggregated"],
                policies["alias_layout_policy_v1"]["aggregated"],
                policies["virtual_edge_policy_v1"]["aggregated"],
            ],
        },
    }
    receipt_path = base / f"data/layer1/2B/s0_gate_receipt/fingerprint={manifest}/s0_gate_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt_payload, indent=2), encoding="utf-8")

    inventory_entries = []
    schema_refs = {
        "route_rng_policy_v1": "schemas.2B.yaml#/policy/route_rng_policy_v1",
        "alias_layout_policy_v1": "schemas.2B.yaml#/policy/alias_layout_policy_v1",
        "virtual_edge_policy_v1": "schemas.2B.yaml#/policy/virtual_edge_policy_v1",
    }
    for asset_id, info in policies.items():
        rel_path = info["path"].relative_to(base).as_posix()
        inventory_entries.append(
            {
                "asset_id": asset_id,
                "version_tag": "test",
                "sha256_hex": info["aggregated"],
                "path": rel_path,
                "partition": [],
                "schema_ref": schema_refs[asset_id],
            }
        )
    inventory_path = base / f"data/layer1/2B/sealed_inputs/fingerprint={manifest}/sealed_inputs_v1.json"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_text(json.dumps(inventory_entries, indent=2), encoding="utf-8")


def _write_alias_artifacts(base: Path, *, seed: int, manifest: str, alias_policy_digest: str) -> None:
    index_dir = base / f"data/layer1/2B/s2_alias_index/seed={seed}/fingerprint={manifest}"
    blob_dir = base / f"data/layer1/2B/s2_alias_blob/seed={seed}/fingerprint={manifest}"
    index_dir.mkdir(parents=True, exist_ok=True)
    blob_dir.mkdir(parents=True, exist_ok=True)
    site_count = 1
    site_order = 1
    threshold = 1 << 16
    alias_order = site_order
    blob = struct.pack("<I", site_count)
    blob += struct.pack("<I", site_order)
    blob += struct.pack("<I", threshold)
    blob += struct.pack("<I", alias_order)
    blob_path = blob_dir / "alias.bin"
    blob_path.write_bytes(blob)
    blob_sha = hashlib.sha256(blob).hexdigest()
    index_payload = {
        "layout_version": "1.0",
        "endianness": "little",
        "alignment_bytes": 8,
        "quantised_bits": 16,
        "created_utc": UTC_TIMESTAMP,
        "policy_id": "alias_layout_policy_v1",
        "policy_digest": alias_policy_digest,
        "blob_sha256": blob_sha,
        "blob_size_bytes": len(blob),
        "merchants_count": 1,
        "merchants": [
            {
                "merchant_id": 1,
                "offset": 0,
                "length": len(blob),
                "sites": site_count,
                "quantised_bits": 16,
                "checksum": "0" * 64,
            }
        ],
    }
    (index_dir / "index.json").write_text(json.dumps(index_payload, indent=2), encoding="utf-8")


def _write_site_weights(base: Path, *, seed: int, manifest: str) -> None:
    path = base / f"data/layer1/2B/s1_site_weights/seed={seed}/fingerprint={manifest}/site_weights.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "site_order": [1],
            "p_weight": [1.0],
        }
    )
    frame.write_parquet(path)


def _write_day_surfaces(base: Path, *, seed: int, manifest: str) -> None:
    s3_path = base / f"data/layer1/2B/s3_day_effects/seed={seed}/fingerprint={manifest}/s3_day_effects.parquet"
    s3_path.parent.mkdir(parents=True, exist_ok=True)
    s3_frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "utc_day": [UTC_DAY],
            "tz_group_id": ["Etc/UTC"],
            "gamma": [0.5],
        }
    )
    s3_frame.write_parquet(s3_path)
    s4_path = base / f"data/layer1/2B/s4_group_weights/seed={seed}/fingerprint={manifest}/s4_group_weights.parquet"
    s4_path.parent.mkdir(parents=True, exist_ok=True)
    s4_frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "utc_day": [UTC_DAY],
            "tz_group_id": ["Etc/UTC"],
            "gamma": [0.5],
            "p_group": [1.0],
            "base_share": [1.0],
        }
    )
    s4_frame.write_parquet(s4_path)


def _write_site_timezones(base: Path, *, seed: int, seg2a_manifest: str) -> None:
    tz_path = base / f"data/layer1/2A/site_timezones/seed={seed}/fingerprint={seg2a_manifest}/site_timezones.parquet"
    tz_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "site_order": [SITE_ID & 0xFFFFFFFF],
            "tzid": ["Etc/UTC"],
        }
    )
    frame.write_parquet(tz_path)


def _write_s5_evidence(
    base: Path,
    *,
    seed: int,
    manifest: str,
    parameter_hash: str,
    run_id: str,
    tz_group: str,
) -> Dict[str, Path]:
    group_dir = base / f"logs/rng/events/alias_pick_group/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}"
    site_dir = base / f"logs/rng/events/alias_pick_site/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}"
    group_dir.mkdir(parents=True, exist_ok=True)
    site_dir.mkdir(parents=True, exist_ok=True)
    group_event = {
        "ts_utc": UTC_TIMESTAMP,
        "run_id": run_id,
        "seed": seed,
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest,
        "module": "2B.router",
        "substream_label": "alias_pick_group",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 1,
        "rng_counter_after_hi": 0,
        "draws": "1",
        "blocks": 1,
        "merchant_id": 1,
        "utc_day": UTC_DAY,
        "tz_group_id": tz_group,
        "p_group": 1.0,
        "selection_seq": 1,
    }
    site_event = {
        "ts_utc": UTC_TIMESTAMP,
        "run_id": run_id,
        "seed": seed,
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest,
        "module": "2B.router",
        "substream_label": "alias_pick_site",
        "rng_counter_before_lo": 1,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 2,
        "rng_counter_after_hi": 0,
        "draws": "1",
        "blocks": 1,
        "merchant_id": 1,
        "utc_day": UTC_DAY,
        "tz_group_id": tz_group,
        "site_id": SITE_ID,
        "alias_offset": 0,
        "selection_seq": 1,
    }
    (group_dir / "part-00000.jsonl").write_text(json.dumps(group_event) + "\n", encoding="utf-8")
    (site_dir / "part-00000.jsonl").write_text(json.dumps(site_event) + "\n", encoding="utf-8")

    selection_dir = base / f"data/layer1/2B/s5_selection_log/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={UTC_DAY}"
    selection_dir.parent.mkdir(parents=True, exist_ok=True)
    selection_dir.mkdir(parents=True, exist_ok=True)
    selection_payload = {
        "seed": seed,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "utc_day": UTC_DAY,
        "utc_timestamp": UTC_TIMESTAMP,
        "merchant_id": 1,
        "tz_group_id": tz_group,
        "site_id": SITE_ID,
        "selection_seq": 1,
        "rng_stream_id": "router_core",
        "ctr_group_hi": 0,
        "ctr_group_lo": 0,
        "ctr_site_hi": 0,
        "ctr_site_lo": 1,
        "manifest_fingerprint": manifest,
        "created_utc": UTC_TIMESTAMP,
    }
    selection_path = selection_dir / "selection_log.jsonl"
    selection_path.write_text(json.dumps(selection_payload) + "\n", encoding="utf-8")

    trace_path = base / f"logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_entries = [
        {
            "ts_utc": UTC_TIMESTAMP,
            "run_id": run_id,
            "seed": seed,
            "module": "2B.router",
            "substream_label": "alias_pick_group",
            "draws_total": 1,
            "blocks_total": 1,
            "events_total": 1,
            "rng_counter_before_lo": 0,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": 1,
            "rng_counter_after_hi": 0,
        },
        {
            "ts_utc": UTC_TIMESTAMP,
            "run_id": run_id,
            "seed": seed,
            "module": "2B.router",
            "substream_label": "alias_pick_site",
            "draws_total": 1,
            "blocks_total": 1,
            "events_total": 1,
            "rng_counter_before_lo": 1,
            "rng_counter_before_hi": 0,
            "rng_counter_after_lo": 2,
            "rng_counter_after_hi": 0,
        },
    ]
    trace_path.write_text("\n".join(json.dumps(entry) for entry in trace_entries) + "\n", encoding="utf-8")
    audit_path = base / f"logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_entry = {
        "ts_utc": UTC_TIMESTAMP,
        "run_id": run_id,
        "seed": seed,
        "manifest_fingerprint": manifest,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": "deadbeef",
    }
    audit_path.write_text(json.dumps(audit_entry) + "\n", encoding="utf-8")
    return {
        "group_dir": group_dir,
        "site_dir": site_dir,
        "selection_path": selection_path,
        "trace_path": trace_path,
        "audit_path": audit_path,
    }


def _write_s6_evidence(
    base: Path,
    *,
    seed: int,
    manifest: str,
    parameter_hash: str,
    run_id: str,
    policy_payload: dict,
) -> Dict[str, Path]:
    edge_id = policy_payload["default_edges"][0]["edge_id"]
    country_iso = policy_payload["default_edges"][0]["country_iso"]
    geo_meta = policy_payload["geo_metadata"][edge_id]
    edge_dir = base / f"logs/rng/events/cdn_edge_pick/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}"
    edge_dir.mkdir(parents=True, exist_ok=True)
    edge_event = {
        "ts_utc": UTC_TIMESTAMP,
        "run_id": run_id,
        "seed": seed,
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest,
        "module": "2B.virtual_edge",
        "substream_label": "cdn_edge_pick",
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 1,
        "rng_counter_after_hi": 0,
        "draws": "1",
        "blocks": 1,
        "merchant_id": 1,
        "utc_day": UTC_DAY,
        "tz_group_id": "Etc/UTC",
        "site_id": SITE_ID,
        "edge_id": edge_id,
        "ip_country": country_iso,
        "edge_lat": geo_meta["lat"],
        "edge_lon": geo_meta["lon"],
        "selection_seq": 1,
        "is_virtual": True,
    }
    (edge_dir / "part-00000.jsonl").write_text(json.dumps(edge_event) + "\n", encoding="utf-8")

    edge_log_path = base / f"data/layer1/2B/s6_edge_log/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/utc_day={UTC_DAY}/edge_log.jsonl"
    edge_log_path.parent.mkdir(parents=True, exist_ok=True)
    edge_log_entry = {
        "seed": seed,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "utc_day": UTC_DAY,
        "utc_timestamp": UTC_TIMESTAMP,
        "merchant_id": 1,
        "is_virtual": True,
        "tz_group_id": "Etc/UTC",
        "site_id": SITE_ID,
        "edge_id": edge_id,
        "ip_country": country_iso,
        "edge_lat": geo_meta["lat"],
        "edge_lon": geo_meta["lon"],
        "rng_stream_id": "virtual_edge",
        "ctr_edge_hi": 0,
        "ctr_edge_lo": 0,
        "manifest_fingerprint": manifest,
        "created_utc": UTC_TIMESTAMP,
    }
    edge_log_path.write_text(json.dumps(edge_log_entry) + "\n", encoding="utf-8")

    trace_path = base / f"logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_entry = {
        "ts_utc": UTC_TIMESTAMP,
        "run_id": run_id,
        "seed": seed,
        "module": "2B.virtual_edge",
        "substream_label": "cdn_edge_pick",
        "draws_total": 1,
        "blocks_total": 1,
        "events_total": 1,
        "rng_counter_before_lo": 0,
        "rng_counter_before_hi": 0,
        "rng_counter_after_lo": 1,
        "rng_counter_after_hi": 0,
    }
    trace_path.write_text(json.dumps(trace_entry) + "\n", encoding="utf-8")
    audit_path = base / f"logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_entry = {
        "ts_utc": UTC_TIMESTAMP,
        "run_id": run_id,
        "seed": seed,
        "manifest_fingerprint": manifest,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": "deadbeef",
    }
    audit_path.write_text(json.dumps(audit_entry) + "\n", encoding="utf-8")
    return {
        "edge_dir": edge_dir,
        "edge_log_path": edge_log_path,
        "trace_path": trace_path,
        "audit_path": audit_path,
    }
