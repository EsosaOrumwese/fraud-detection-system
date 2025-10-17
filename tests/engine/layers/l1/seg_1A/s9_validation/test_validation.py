import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
import polars as pl
from types import MappingProxyType

from engine.layers.l1.seg_1A.s0_foundations.l0.artifacts import hash_artifact
from engine.layers.l1.seg_1A.s0_foundations.l1.hashing import (
    compute_manifest_fingerprint,
    compute_parameter_hash,
)
from engine.layers.l1.seg_1A.s9_validation import constants as c
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
    git_commit_hex = "1" * 64

    param_file = tmp_path / "config" / "allocation" / "s6_selection_policy.yaml"
    param_file.parent.mkdir(parents=True, exist_ok=True)
    param_file.write_text("policy: test\n", encoding="utf-8")
    param_digest = hash_artifact(param_file, error_prefix="TEST_PARAM")
    param_result = compute_parameter_hash([param_digest])
    parameter_hash = param_result.parameter_hash

    manifest_result = compute_manifest_fingerprint(
        [param_digest],
        git_commit_raw=bytes.fromhex(git_commit_hex),
        parameter_hash_bytes=bytes.fromhex(parameter_hash),
    )
    manifest_fingerprint = manifest_result.manifest_fingerprint

    rng_events: dict[str, pd.DataFrame] = {dataset_id: pd.DataFrame() for dataset_id in c.RNG_EVENT_DATASETS}
    rng_events[c.EVENT_FAMILY_ANCHOR] = pd.DataFrame(
        {
            "ts_utc": ["2025-01-01T00:00:00.000000Z"],
            "seed": [1],
            "parameter_hash": [parameter_hash],
            "manifest_fingerprint": [manifest_fingerprint],
            "run_id": ["run-1"],
            "module": ["1A.s0"],
            "substream_label": ["s0.anchor"],
            "rng_counter_before_lo": [0],
            "rng_counter_before_hi": [0],
            "rng_counter_after_lo": [0],
            "rng_counter_after_hi": [0],
            "blocks": [0],
            "draws": ["0"],
        }
    )
    rng_events[c.EVENT_FAMILY_NB_FINAL] = pd.DataFrame(
        {
            "ts_utc": ["2025-01-01T00:00:01.000000Z"],
            "seed": [1],
            "parameter_hash": [parameter_hash],
            "manifest_fingerprint": [manifest_fingerprint],
            "run_id": ["run-1"],
            "module": ["1A.nb_sampler"],
            "substream_label": ["nb_final"],
            "rng_counter_before_lo": [0],
            "rng_counter_before_hi": [0],
            "rng_counter_after_lo": [0],
            "rng_counter_after_hi": [0],
            "blocks": [0],
            "draws": ["0"],
            "merchant_id": [1],
            "mu": [2.0],
            "dispersion_k": [1.0],
            "n_outlets": [2],
            "nb_rejections": [0],
        }
    )
    rng_events[c.EVENT_FAMILY_SEQUENCE_FINALIZE] = pd.DataFrame(
        {
            "ts_utc": ["2025-01-01T00:00:02.000000Z"],
            "seed": [1],
            "parameter_hash": [parameter_hash],
            "manifest_fingerprint": [manifest_fingerprint],
            "run_id": ["run-1"],
            "module": ["1A.site_id_allocator"],
            "substream_label": ["sequence_finalize"],
            "rng_counter_before_lo": [0],
            "rng_counter_before_hi": [0],
            "rng_counter_after_lo": [0],
            "rng_counter_after_hi": [0],
            "blocks": [0],
            "draws": ["0"],
            "merchant_id": [1],
            "legal_country_iso": ["GB"],
            "site_count": [2],
            "site_order_start": [1],
            "site_order_end": [2],
        }
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

    candidate_path = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "s3_candidate_set"
        / f"parameter_hash={parameter_hash}"
        / "part-00000.parquet"
    )
    counts_path = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "s3_integerised_counts"
        / f"parameter_hash={parameter_hash}"
        / "part-00000.parquet"
    )
    membership_path = (
        tmp_path
        / "data"
        / "layer1"
        / "1A"
        / "s6_membership"
        / "seed=1"
        / f"parameter_hash={parameter_hash}"
        / "part-00000.parquet"
    )
    audit_path = (
        tmp_path
        / "logs"
        / "rng"
        / "audit"
        / "seed=1"
        / f"parameter_hash={parameter_hash}"
        / "run_id=run-1"
        / "rng_audit_log.jsonl"
    )
    trace_path = (
        tmp_path
        / "logs"
        / "rng"
        / "trace"
        / "seed=1"
        / f"parameter_hash={parameter_hash}"
        / "run_id=run-1"
        / "rng_trace_log.jsonl"
    )
    nb_final_path = (
        tmp_path
        / "logs"
        / "rng"
        / "events"
        / "nb_final"
        / "seed=1"
        / f"parameter_hash={parameter_hash}"
        / "run_id=run-1"
        / "part-00000.jsonl"
    )
    sequence_path = (
        tmp_path
        / "logs"
        / "rng"
        / "events"
        / "sequence_finalize"
        / "seed=1"
        / f"parameter_hash={parameter_hash}"
        / "run_id=run-1"
        / "part-00000.jsonl"
    )
    anchor_path = (
        tmp_path
        / "logs"
        / "rng"
        / "events"
        / "core"
        / "seed=1"
        / f"parameter_hash={parameter_hash}"
        / "run_id=run-1"
        / "part-00000.jsonl"
    )

    outlet_frame = pl.DataFrame(
        {
            "merchant_id": [1, 1],
            "legal_country_iso": ["GB", "GB"],
            "site_order": [1, 2],
            "site_id": ["000001", "000002"],
            "final_country_outlet_count": [2, 2],
            "manifest_fingerprint": [manifest_fingerprint, manifest_fingerprint],
            "global_seed": [1, 1],
            "home_country_iso": ["GB", "GB"],
            "single_vs_multi_flag": [True, True],
            "raw_nb_outlet_draw": [2, 2],
        }
    )
    candidate_frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "country_iso": ["GB"],
            "candidate_rank": [0],
            "is_home": [True],
            "reason_codes": [["BASELINE"]],
            "filter_tags": [["ELIGIBLE"]],
            "parameter_hash": [parameter_hash],
        }
    )
    counts_frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "country_iso": ["GB"],
            "count": [2],
            "residual_rank": [1],
            "parameter_hash": [parameter_hash],
        }
    )
    membership_frame = pl.DataFrame(
        {
            "seed": [1],
            "merchant_id": [1],
            "country_iso": ["GB"],
            "parameter_hash": [parameter_hash],
        }
    )

    outlet_frame.write_parquet(outlet_file)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_frame.write_parquet(candidate_path)
    counts_path.parent.mkdir(parents=True, exist_ok=True)
    counts_frame.write_parquet(counts_path)
    membership_path.parent.mkdir(parents=True, exist_ok=True)
    membership_frame.write_parquet(membership_path)

    def _write_jsonl(path: Path, records: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in records.to_dict(orient="records"):
                handle.write(json.dumps(record))
                handle.write("\n")

    audit_df = pd.DataFrame(
        {
            "ts_utc": ["2025-01-01T00:00:00.000000Z"],
            "seed": [1],
            "parameter_hash": [parameter_hash],
            "manifest_fingerprint": [manifest_fingerprint],
            "run_id": ["run-1"],
            "algorithm": ["philox2x64-10"],
            "build_commit": [git_commit_hex],
        }
    )
    trace_df = pd.DataFrame(
        {
            "ts_utc": [
                "2025-01-01T00:00:00.000000Z",
                "2025-01-01T00:00:01.000000Z",
                "2025-01-01T00:00:02.000000Z",
            ],
            "seed": [1, 1, 1],
            "parameter_hash": [parameter_hash, parameter_hash, parameter_hash],
            "manifest_fingerprint": [manifest_fingerprint, manifest_fingerprint, manifest_fingerprint],
            "run_id": ["run-1", "run-1", "run-1"],
            "module": ["1A.s0", "1A.nb_sampler", "1A.site_id_allocator"],
            "substream_label": ["s0.anchor", "nb_final", "sequence_finalize"],
            "rng_counter_before_lo": [0, 0, 0],
            "rng_counter_before_hi": [0, 0, 0],
            "rng_counter_after_lo": [0, 0, 0],
            "rng_counter_after_hi": [0, 0, 0],
            "draws_total": [0, 0, 0],
            "blocks_total": [0, 0, 0],
            "events_total": [1, 1, 1],
        }
    )

    _write_jsonl(audit_path, audit_df)
    _write_jsonl(trace_path, trace_df)
    _write_jsonl(nb_final_path, rng_events[c.EVENT_FAMILY_NB_FINAL])
    _write_jsonl(sequence_path, rng_events[c.EVENT_FAMILY_SEQUENCE_FINALIZE])
    _write_jsonl(anchor_path, rng_events[c.EVENT_FAMILY_ANCHOR])

    bundle_dir = (
        tmp_path
        / "validation_bundle"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    bundle_dir.mkdir(parents=True, exist_ok=True)
    param_log_path = bundle_dir / "param_digest_log.jsonl"
    fingerprint_log_path = bundle_dir / "fingerprint_artifacts.jsonl"
    manifest_path = bundle_dir / "MANIFEST.json"

    def _write_log(path: Path, digests: Sequence[Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for digest in digests:
                handle.write(
                    json.dumps(
                        {
                            "filename": digest.basename,
                            "path": str(digest.path),
                            "size_bytes": digest.size_bytes,
                            "sha256_hex": digest.sha256_hex,
                            "mtime_ns": digest.mtime_ns,
                        }
                    )
                )
                handle.write("\n")

    _write_log(param_log_path, [param_digest])
    _write_log(fingerprint_log_path, [param_digest])
    manifest_path.write_text(
        json.dumps(
            {
                "version": "1A.validation.v1",
                "manifest_fingerprint": manifest_fingerprint,
                "parameter_hash": parameter_hash,
                "git_commit_hex": git_commit_hex,
                "created_utc_ns": 0,
                "artifact_count": 0,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    surfaces = S9InputSurfaces(
        outlet_catalogue=outlet_frame,
        s3_candidate_set=candidate_frame,
        s3_integerised_counts=counts_frame,
        s6_membership=membership_frame,
        nb_final_events=rng_events[c.EVENT_FAMILY_NB_FINAL],
        sequence_finalize_events=rng_events[c.EVENT_FAMILY_SEQUENCE_FINALIZE],
        rng_audit_log=audit_df,
        rng_trace_log=trace_df,
        rng_events=MappingProxyType(rng_events),
    )

    return S9DeterministicContext(
        base_path=tmp_path,
        seed=1,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id="run-1",
        surfaces=surfaces,
        upstream_manifest={
            "git_commit_hex": git_commit_hex,
            "compiler_flags": {
                "rounding": "RNE",
                "fma": False,
                "ftz": False,
                "fast_math": False,
                "blas": "none",
            },
            "artifact_count": 1,
        },
        source_paths={
            c.DATASET_OUTLET_CATALOGUE: (outlet_file,),
            c.DATASET_S3_CANDIDATE_SET: (candidate_path,),
            c.DATASET_S3_INTEGERISED_COUNTS: (counts_path,),
            c.DATASET_S6_MEMBERSHIP: (membership_path,),
            c.AUDIT_LOG_ID: (audit_path,),
            c.TRACE_LOG_ID: (trace_path,),
            c.EVENT_FAMILY_ANCHOR: (anchor_path,),
            c.EVENT_FAMILY_NB_FINAL: (nb_final_path,),
            c.EVENT_FAMILY_SEQUENCE_FINALIZE: (sequence_path,),
        },
        lineage_paths={
            "param_digest_log.jsonl": param_log_path,
            "fingerprint_artifacts.jsonl": fingerprint_log_path,
            "MANIFEST.json": manifest_path,
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
    param_resolved = json.loads((bundle_path / "parameter_hash_resolved.json").read_text(encoding="utf-8"))
    manifest_resolved = json.loads((bundle_path / "manifest_fingerprint_resolved.json").read_text(encoding="utf-8"))

    assert manifest["manifest_fingerprint"] == context.manifest_fingerprint
    assert manifest["artifact_count"] == len(index)
    assert manifest["git_commit_hex"] == "1" * 64
    assert any(entry["artifact_id"] == "MANIFEST" and entry["kind"] == "summary" for entry in index)
    assert all("mime" in entry for entry in index)
    assert summary["decision"] == "PASS"
    assert flag_path is not None
    assert flag_path.exists()
    assert param_resolved.get("files")
    assert manifest_resolved.get("files")

def test_validate_outputs_detects_candidate_schema_violation(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    bad_candidate = context.surfaces.s3_candidate_set.drop('candidate_rank')
    bad_surfaces = replace(context.surfaces, s3_candidate_set=bad_candidate)
    bad_context = replace(context, surfaces=bad_surfaces)

    result = validate_outputs(bad_context)

    assert not result.passed
    assert "E_SCHEMA_INVALID" in result.failures_by_code


def test_validate_outputs_detects_trace_total_mismatch(tmp_path: Path) -> None:
    context = _build_context(tmp_path)
    bad_trace = context.surfaces.rng_trace_log.copy()
    bad_trace.loc[bad_trace["module"] == "1A.nb_sampler", "events_total"] = 2
    bad_surfaces = replace(context.surfaces, rng_trace_log=bad_trace)
    bad_context = replace(context, surfaces=bad_surfaces)

    result = validate_outputs(bad_context)

    assert not result.passed
    assert "E_TRACE_TOTALS_MISMATCH" in result.failures_by_code
