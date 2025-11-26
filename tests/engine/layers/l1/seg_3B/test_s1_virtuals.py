import json
from pathlib import Path

import polars as pl
import pytest

from engine.layers.l1.seg_3B import S0GateInputs, S0GateRunner, VirtualsInputs, VirtualsRunner
from engine.layers.l1.seg_3A.s0_gate.l0 import compute_index_digest, load_index


def _make_validation_bundle(base: Path, name: str) -> Path:
    bundle_dir = base / name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    artifact = bundle_dir / "artifact.txt"
    artifact.write_text("ok", encoding="utf-8")
    index_payload = [
        {"artifact_id": "index", "path": "index.json"},
        {"artifact_id": "sample", "path": artifact.name},
    ]
    (bundle_dir / "index.json").write_text(json.dumps(index_payload))
    digest = compute_index_digest(bundle_dir, load_index(bundle_dir))
    (bundle_dir / "_passed.flag").write_text(f"sha256_hex = {digest}\n", encoding="utf-8")
    return bundle_dir


def test_s0_and_s1_end_to_end(tmp_path: Path) -> None:
    seed = 2025110601
    manifest_fingerprint = "a" * 64

    # upstream validation bundles
    bundle_1a = _make_validation_bundle(tmp_path, "bundle_1a")
    bundle_1b = _make_validation_bundle(tmp_path, "bundle_1b")
    bundle_2a = _make_validation_bundle(tmp_path, "bundle_2a")
    bundle_3a = _make_validation_bundle(tmp_path, "bundle_3a")

    # minimal upstream egress artefacts
    site_dir = tmp_path / f"data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}"
    site_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "site_order": [0],
            "lon_deg": [0.0],
            "lat_deg": [0.0],
        }
    ).write_parquet(site_dir / "part-0.parquet")

    zone_dir = tmp_path / f"data/layer1/3A/zone_alloc/seed={seed}/fingerprint={manifest_fingerprint}"
    zone_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "tzid": ["America/New_York"],
        }
    ).write_parquet(zone_dir / "part-0.parquet")

    s0_runner = S0GateRunner()
    s0_inputs = S0GateInputs(
        base_path=tmp_path,
        output_base_path=tmp_path,
        seed=seed,
        upstream_manifest_fingerprint=manifest_fingerprint,
        git_commit_hex="0" * 40,
        validation_bundle_1a=bundle_1a,
        validation_bundle_1b=bundle_1b,
        validation_bundle_2a=bundle_2a,
        validation_bundle_3a=bundle_3a,
    )
    s0_outputs = s0_runner.run(s0_inputs)

    s1_runner = VirtualsRunner()
    s1_inputs = VirtualsInputs(
        data_root=tmp_path,
        manifest_fingerprint=s0_outputs.manifest_fingerprint,
        seed=seed,
    )
    s1_result = s1_runner.run(s1_inputs)

    cls_df = pl.read_parquet(s1_result.classification_path / "part-0.parquet")
    settlement_df = pl.read_parquet(s1_result.settlement_path / "part-0.parquet")

    virtuals = cls_df.filter(pl.col("is_virtual") == True)  # noqa: E712
    assert not virtuals.is_empty()
    assert settlement_df.height == virtuals.height
    assert set(settlement_df["merchant_id"].to_list()) == set(virtuals["merchant_id"].to_list())

    # run-report exists and segment-state report appended
    assert s1_result.run_report_path.exists()
    state_report = tmp_path / "reports/l1/segment_states/segment_state_runs.jsonl"
    assert state_report.exists()
