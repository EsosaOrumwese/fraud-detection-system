import json
from pathlib import Path

import pandas as pd
import polars as pl
from types import MappingProxyType

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
    manifest_fingerprint = "f" * 64
    parameter_hash = "a" * 64

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
    outlet_file.write_bytes(b"")

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
                "parameter_hash": [parameter_hash],
            }
        ),
        s3_integerised_counts=pl.DataFrame(
            {
                "merchant_id": [1],
                "country_iso": ["GB"],
                "count": [2],
                "parameter_hash": [parameter_hash],
            }
        ),
        s6_membership=pl.DataFrame(
            {
                "merchant_id": [1],
                "country_iso": ["GB"],
                "parameter_hash": [parameter_hash],
            }
        ),
        nb_final_events=rng_events[c.EVENT_FAMILY_NB_FINAL],
        sequence_finalize_events=rng_events[c.EVENT_FAMILY_SEQUENCE_FINALIZE],
        rng_audit_log=pd.DataFrame(
            {
                "ts_utc": ["2025-01-01T00:00:00.000000Z"],
                "seed": [1],
                "parameter_hash": [parameter_hash],
                "manifest_fingerprint": [manifest_fingerprint],
                "run_id": ["run-1"],
                "algorithm": ["philox2x64-10"],
                "build_commit": ["abc123"],
            }
        ),
        rng_trace_log=pd.DataFrame(
            {
                "ts_utc": [
                    "2025-01-01T00:00:00.000000Z",
                    "2025-01-01T00:00:01.000000Z",
                    "2025-01-01T00:00:02.000000Z",
                ],
                "seed": [1, 1, 1],
                "parameter_hash": [parameter_hash, parameter_hash, parameter_hash],
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
        ),
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
