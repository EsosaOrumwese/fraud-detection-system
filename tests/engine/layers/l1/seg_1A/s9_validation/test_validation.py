import json
from pathlib import Path

import pandas as pd
import polars as pl
from engine.layers.l1.seg_1A.s9_validation.contexts import (
    S9DeterministicContext,
    S9InputSurfaces,
)
from engine.layers.l1.seg_1A.s9_validation.persist import (
    PersistConfig,
    write_validation_bundle,
)
from engine.layers.l1.seg_1A.s9_validation.validate import validate_outputs


def _build_context(tmp_path: Path) -> S9DeterministicContext:
    manifest_fingerprint = "f" * 64
    parameter_hash = "a" * 64
    surfaces = S9InputSurfaces(
        outlet_catalogue=pl.DataFrame(
            {
                "merchant_id": [1, 1],
                "legal_country_iso": ["GB", "GB"],
                "site_order": [1, 2],
                "site_id": ["000001", "000002"],
                "final_country_outlet_count": [2, 2],
                "manifest_fingerprint": [manifest_fingerprint, manifest_fingerprint],
                "global_seed": [1, 1],
                "home_country_iso": ["GB", "GB"],
            }
        ),
        s3_candidate_set=pl.DataFrame(
            {
                "merchant_id": [1],
                "candidate_rank": [0],
                "country_iso": ["GB"],
                "is_home": [True],
            }
        ),
        s3_integerised_counts=pl.DataFrame(
            {
                "merchant_id": [1],
                "country_iso": ["GB"],
                "count": [2],
            }
        ),
        s6_membership=pl.DataFrame(
            {
                "merchant_id": [1],
                "country_iso": ["GB"],
            }
        ),
        nb_final_events=pd.DataFrame(
            {
                "merchant_id": [1],
                "n_outlets": [2],
            }
        ),
        sequence_finalize_events=pd.DataFrame(
            {
                "merchant_id": [1],
                "legal_country_iso": ["GB"],
                "site_count": [2],
                "site_order_start": [1],
                "site_order_end": [2],
            }
        ),
    )
    outlet_dir = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "outlet_catalogue"
        / "seed=1"
        / f"fingerprint={manifest_fingerprint}"
    )
    outlet_dir.mkdir(parents=True, exist_ok=True)
    outlet_file = outlet_dir / "part-00000.parquet"
    outlet_file.write_bytes(b"")

    return S9DeterministicContext(
        base_path=tmp_path,
        seed=1,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id="run-1",
        surfaces=surfaces,
        upstream_manifest={
            "git_commit_hex": "1" * 64,
            "compiler_flags": {
                "rounding": "RNE",
                "fma": False,
                "ftz": False,
                "fast_math": False,
                "blas": "none",
            },
        },
        source_paths={
            "outlet_catalogue": (outlet_file,),
        },
    )


def test_validate_outputs_records_summary(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    result = validate_outputs(context)

    assert result.passed
    assert result.summary["decision"] == "PASS"
    assert result.summary["counts_source"] == "s3_integerised_counts"
    assert result.summary["membership_source"] == "s6_membership"
    assert result.summary["egress_writer_sort"] is True
    assert result.failures_by_code == {}
    assert result.egress_writer_sort_ok is True


def test_write_validation_bundle_produces_manifest_and_index(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    result = validate_outputs(context)

    bundle_path, flag_path = write_validation_bundle(
        context=context,
        result=result,
        config=PersistConfig(
            base_path=context.base_path,
            manifest_fingerprint=context.manifest_fingerprint,
        ),
    )

    manifest = json.loads((bundle_path / "MANIFEST.json").read_text(encoding="utf-8"))
    index = json.loads((bundle_path / "index.json").read_text(encoding="utf-8"))
    summary = json.loads((bundle_path / "s9_summary.json").read_text(encoding="utf-8"))

    assert manifest["manifest_fingerprint"] == context.manifest_fingerprint
    assert manifest["artifact_count"] == len(index)
    assert manifest["git_commit_hex"] == "1" * 64
    assert {"artifact_id": "MANIFEST", "kind": "summary", "path": "MANIFEST.json"} in index
    assert summary["decision"] == "PASS"
    assert flag_path is not None
    assert flag_path.exists()
