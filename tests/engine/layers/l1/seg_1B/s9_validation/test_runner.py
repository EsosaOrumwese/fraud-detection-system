import json
import hashlib
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from engine.layers.l1.seg_1B.s9_validation import RunnerConfig, S9ValidationRunner
from engine.layers.l1.seg_1B.s9_validation.loader import load_deterministic_context
from engine.layers.l1.seg_1B.s9_validation.validator import validate_outputs

SEED = 7
PARAMETER_HASH = "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
FINGERPRINT = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
RUN_ID = "run-001"
KEY_COLUMNS = ["merchant_id", "legal_country_iso", "site_order"]


def _dictionary() -> dict:
    return {
        "datasets": {
            "s7_site_synthesis": {
                "path": "data/layer1/1B/s7_site_synthesis/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}"
            },
            "site_locations": {
                "path": "data/layer1/1B/site_locations/seed={seed}/fingerprint={manifest_fingerprint}"
            },
        },
        "logs": {
            "rng_event_site_tile_assign": {
                "path": "logs/rng/events/site_tile_assign/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}"
            },
            "rng_event_in_cell_jitter": {
                "path": "logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}"
            },
            "rng_trace_log": {
                "path": "logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl"
            },
            "rng_audit_log": {
                "path": "logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl"
            },
        },
        "validation": {
            "validation_bundle_1B": {
                "path": "data/layer1/1B/validation/fingerprint={manifest_fingerprint}"
            },
            "validation_passed_flag_1B": {
                "path": "data/layer1/1B/validation/fingerprint={manifest_fingerprint}/_passed.flag"
            },
        },
    }


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path, compression="zstd")


def _write_jsonl(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_json(path, orient="records", lines=True)


def _site_locations_path(base_path: Path) -> Path:
    return (
        base_path
        / "data"
        / "layer1"
        / "1B"
        / "site_locations"
        / f"seed={SEED}"
        / f"fingerprint={FINGERPRINT}"
        / "part-00000.parquet"
    )


def _s7_path(base_path: Path) -> Path:
    return (
        base_path
        / "data"
        / "layer1"
        / "1B"
        / "s7_site_synthesis"
        / f"seed={SEED}"
        / f"fingerprint={FINGERPRINT}"
        / f"parameter_hash={PARAMETER_HASH}"
        / "part-00000.parquet"
    )


def _tile_events_path(base_path: Path) -> Path:
    return (
        base_path
        / "logs"
        / "rng"
        / "events"
        / "site_tile_assign"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "part-00000.jsonl"
    )


def _jitter_events_path(base_path: Path) -> Path:
    return (
        base_path
        / "logs"
        / "rng"
        / "events"
        / "in_cell_jitter"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "part-00000.jsonl"
    )


def _trace_log_path(base_path: Path) -> Path:
    return (
        base_path
        / "logs"
        / "rng"
        / "trace"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "rng_trace_log.jsonl"
    )


def _audit_log_path(base_path: Path) -> Path:
    return (
        base_path
        / "logs"
        / "rng"
        / "audit"
        / f"seed={SEED}"
        / f"parameter_hash={PARAMETER_HASH}"
        / f"run_id={RUN_ID}"
        / "rng_audit_log.jsonl"
    )


def _setup_success_case(base_path: Path) -> dict:
    rows = [
        {"merchant_id": 1, "legal_country_iso": "GB", "site_order": 1, "lon_deg": -0.1, "lat_deg": 51.5},
        {"merchant_id": 1, "legal_country_iso": "GB", "site_order": 2, "lon_deg": -0.11, "lat_deg": 51.51},
    ]
    s7_df = pl.DataFrame(rows)
    s8_df = pl.DataFrame(rows)

    _write_parquet(s7_df, _s7_path(base_path))
    _write_parquet(s8_df, _site_locations_path(base_path))

    tile_events = pd.DataFrame(
        [
            {
                **rows[0],
                "module": "1B.s5_site_tile_assignment",
                "substream_label": "site_tile_assign",
                "blocks": 1,
                "draws": "1",
                "rng_counter_before_lo": 0,
                "rng_counter_before_hi": 0,
                "rng_counter_after_lo": 1,
                "rng_counter_after_hi": 0,
            },
            {
                **rows[1],
                "module": "1B.s5_site_tile_assignment",
                "substream_label": "site_tile_assign",
                "blocks": 1,
                "draws": "1",
                "rng_counter_before_lo": 1,
                "rng_counter_before_hi": 0,
                "rng_counter_after_lo": 2,
                "rng_counter_after_hi": 0,
            },
        ]
    )

    jitter_events = pd.DataFrame(
        [
            {
                **rows[0],
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "blocks": 1,
                "draws": "2",
                "rng_counter_before_lo": 10,
                "rng_counter_before_hi": 0,
                "rng_counter_after_lo": 11,
                "rng_counter_after_hi": 0,
                "sigma_lat_deg": 0.0,
                "sigma_lon_deg": 0.0,
                "delta_lat_deg": 0.001,
                "delta_lon_deg": 0.001,
                "attempt_index": 1,
                "accepted": True,
            },
            {
                **rows[1],
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "blocks": 1,
                "draws": "2",
                "rng_counter_before_lo": 11,
                "rng_counter_before_hi": 0,
                "rng_counter_after_lo": 12,
                "rng_counter_after_hi": 0,
                "sigma_lat_deg": 0.0,
                "sigma_lon_deg": 0.0,
                "delta_lat_deg": 0.002,
                "delta_lon_deg": 0.002,
                "attempt_index": 1,
                "accepted": True,
            },
        ]
    )

    trace_rows = pd.DataFrame(
        [
            {
                "module": "1B.s5_site_tile_assignment",
                "substream_label": "site_tile_assign",
                "events_total": 2,
                "blocks_total": 2,
                "draws_total": "2",
                "rng_counter_after_lo": 2,
                "rng_counter_after_hi": 0,
            },
            {
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "events_total": 2,
                "blocks_total": 2,
                "draws_total": "4",
                "rng_counter_after_lo": 12,
                "rng_counter_after_hi": 0,
            },
        ]
    )

    _write_jsonl(tile_events, _tile_events_path(base_path))
    _write_jsonl(jitter_events, _jitter_events_path(base_path))
    _write_jsonl(trace_rows, _trace_log_path(base_path))

    audit_record = pd.DataFrame(
        [
            {
                "ts_utc": "2025-01-01T00:00:00.000000Z",
                "run_id": RUN_ID,
                "seed": SEED,
                "manifest_fingerprint": FINGERPRINT,
                "parameter_hash": PARAMETER_HASH,
                "algorithm": "philox2x64-10",
                "build_commit": "f" * 64,
            }
        ]
    )
    _write_jsonl(audit_record, _audit_log_path(base_path))

    return _dictionary()


def test_validate_outputs_detects_missing_rows(tmp_path: Path) -> None:
    dictionary = _setup_success_case(tmp_path)
    # Drop a row from S8 to trigger parity failure
    s8_file = _site_locations_path(tmp_path)
    s8_frame = pl.read_parquet(s8_file).filter(pl.col("site_order") == 1)
    _write_parquet(s8_frame, s8_file)

    context = load_deterministic_context(
        base_path=tmp_path,
        seed=SEED,
        parameter_hash=PARAMETER_HASH,
        manifest_fingerprint=FINGERPRINT,
        run_id=RUN_ID,
        dictionary=dictionary,
    )
    result = validate_outputs(context)
    assert not result.passed
    codes = {failure.code for failure in result.failures}
    assert "E901_ROW_MISSING" in codes


def test_runner_persists_bundle_and_flag(tmp_path: Path) -> None:
    dictionary = _setup_success_case(tmp_path)

    runner = S9ValidationRunner()
    outcome = runner.run(
        RunnerConfig(
            base_path=tmp_path,
            seed=SEED,
            parameter_hash=PARAMETER_HASH,
            manifest_fingerprint=FINGERPRINT,
            run_id=RUN_ID,
            dictionary=dictionary,
        )
    )

    assert outcome.result.passed
    bundle_path = outcome.bundle_path
    assert bundle_path.exists()

    flag_path = bundle_path / "_passed.flag"
    assert flag_path.exists()

    index_payload = json.loads((bundle_path / "index.json").read_text(encoding="utf-8"))
    listed_paths = [entry["path"] for entry in index_payload["artifacts"]]
    assert set(listed_paths) == {
        "MANIFEST.json",
        "parameter_hash_resolved.json",
        "manifest_fingerprint_resolved.json",
        "rng_accounting.json",
        "s9_summary.json",
        "egress_checksums.json",
        "index.json",
    }

    # Validate hashing law: concatenate bytes of files in ASCII-lex order listed in index.json
    ascii_order = sorted(listed_paths)
    concatenated = b"".join((bundle_path / path).read_bytes() for path in ascii_order)
    expected_digest = hashlib.sha256(concatenated).hexdigest()
    flag_text = flag_path.read_text(encoding="utf-8").strip()
    assert flag_text == f"sha256_hex = {expected_digest}"

    stage_log = outcome.stage_log_path
    assert stage_log.exists()
    entries = [json.loads(line) for line in stage_log.read_text(encoding="utf-8").splitlines() if line]
    stages = {entry["stage"] for entry in entries}
    assert {"load_inputs", "validate", "persist_bundle"}.issubset(stages)


def test_rng_multi_attempt_jitter(tmp_path: Path) -> None:
    dictionary = _setup_success_case(tmp_path)

    jitter_events = pd.DataFrame(
        [
            {
                "merchant_id": 1,
                "legal_country_iso": "GB",
                "site_order": 1,
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "blocks": 1,
                "draws": "2",
                "rng_counter_before_lo": 10,
                "rng_counter_before_hi": 0,
                "rng_counter_after_lo": 11,
                "rng_counter_after_hi": 0,
                "sigma_lat_deg": 0.0,
                "sigma_lon_deg": 0.0,
                "delta_lat_deg": 0.001,
                "delta_lon_deg": 0.001,
                "attempt_index": 1,
                "accepted": False,
            },
            {
                "merchant_id": 1,
                "legal_country_iso": "GB",
                "site_order": 1,
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "blocks": 1,
                "draws": "2",
                "rng_counter_before_lo": 11,
                "rng_counter_before_hi": 0,
                "rng_counter_after_lo": 12,
                "rng_counter_after_hi": 0,
                "sigma_lat_deg": 0.0,
                "sigma_lon_deg": 0.0,
                "delta_lat_deg": 0.0015,
                "delta_lon_deg": 0.0015,
                "attempt_index": 2,
                "accepted": True,
            },
            {
                "merchant_id": 1,
                "legal_country_iso": "GB",
                "site_order": 2,
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "blocks": 1,
                "draws": "2",
                "rng_counter_before_lo": 12,
                "rng_counter_before_hi": 0,
                "rng_counter_after_lo": 13,
                "rng_counter_after_hi": 0,
                "sigma_lat_deg": 0.0,
                "sigma_lon_deg": 0.0,
                "delta_lat_deg": 0.002,
                "delta_lon_deg": 0.002,
                "attempt_index": 1,
                "accepted": True,
            },
        ]
    )
    _write_jsonl(jitter_events, _jitter_events_path(tmp_path))

    trace_rows = pd.DataFrame(
        [
            {
                "module": "1B.s5_site_tile_assignment",
                "substream_label": "site_tile_assign",
                "events_total": 2,
                "blocks_total": 2,
                "draws_total": "2",
                "rng_counter_after_lo": 2,
                "rng_counter_after_hi": 0,
            },
            {
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "events_total": 3,
                "blocks_total": 3,
                "draws_total": "6",
                "rng_counter_after_lo": 13,
                "rng_counter_after_hi": 0,
            },
        ]
    )
    _write_jsonl(trace_rows, _trace_log_path(tmp_path))

    context = load_deterministic_context(
        base_path=tmp_path,
        seed=SEED,
        parameter_hash=PARAMETER_HASH,
        manifest_fingerprint=FINGERPRINT,
        run_id=RUN_ID,
        dictionary=dictionary,
    )
    result = validate_outputs(context)
    assert result.passed


def test_rng_trace_gap_fails(tmp_path: Path) -> None:
    dictionary = _setup_success_case(tmp_path)

    trace_rows = pd.DataFrame(
        [
            {
                "module": "1B.s5_site_tile_assignment",
                "substream_label": "site_tile_assign",
                "events_total": 2,
                "blocks_total": 2,
                "draws_total": "2",
                "rng_counter_after_lo": 2,
                "rng_counter_after_hi": 0,
            }
        ]
    )
    _write_jsonl(trace_rows, _trace_log_path(tmp_path))

    context = load_deterministic_context(
        base_path=tmp_path,
        seed=SEED,
        parameter_hash=PARAMETER_HASH,
        manifest_fingerprint=FINGERPRINT,
        run_id=RUN_ID,
        dictionary=dictionary,
    )
    result = validate_outputs(context)
    assert not result.passed
    codes = {failure.code for failure in result.failures}
    assert "E907_RNG_BUDGET_OR_COUNTERS" in codes


def test_rng_detects_stray_tile_event(tmp_path: Path) -> None:
    dictionary = _setup_success_case(tmp_path)

    tile_events = pd.read_json(_tile_events_path(tmp_path), orient="records", lines=True)
    stray = tile_events.iloc[0].copy()
    stray["merchant_id"] = 999
    stray["rng_counter_before_lo"] = 2
    stray["rng_counter_after_lo"] = 3
    tile_events = pd.concat([tile_events, stray.to_frame().T], ignore_index=True)
    tile_events.to_json(_tile_events_path(tmp_path), orient="records", lines=True)

    trace_rows = pd.DataFrame(
        [
            {
                "module": "1B.s5_site_tile_assignment",
                "substream_label": "site_tile_assign",
                "events_total": 3,
                "blocks_total": 3,
                "draws_total": "3",
                "rng_counter_after_lo": 3,
                "rng_counter_after_hi": 0,
            },
            {
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "events_total": 2,
                "blocks_total": 2,
                "draws_total": "4",
                "rng_counter_after_lo": 12,
                "rng_counter_after_hi": 0,
            },
        ]
    )
    _write_jsonl(trace_rows, _trace_log_path(tmp_path))

    context = load_deterministic_context(
        base_path=tmp_path,
        seed=SEED,
        parameter_hash=PARAMETER_HASH,
        manifest_fingerprint=FINGERPRINT,
        run_id=RUN_ID,
        dictionary=dictionary,
    )
    result = validate_outputs(context)
    assert not result.passed
    codes = {failure.code for failure in result.failures}
    assert "E907_RNG_BUDGET_OR_COUNTERS" in codes


def test_rng_audit_mismatch(tmp_path: Path) -> None:
    dictionary = _setup_success_case(tmp_path)

    audit_path = _audit_log_path(tmp_path)
    audit_record = pd.read_json(audit_path, orient="records", lines=True)
    audit_record.loc[0, "seed"] = SEED + 1
    audit_record.to_json(audit_path, orient="records", lines=True)

    context = load_deterministic_context(
        base_path=tmp_path,
        seed=SEED,
        parameter_hash=PARAMETER_HASH,
        manifest_fingerprint=FINGERPRINT,
        run_id=RUN_ID,
        dictionary=dictionary,
    )
    result = validate_outputs(context)
    assert not result.passed
    codes = {failure.code for failure in result.failures}
    assert "E907_RNG_BUDGET_OR_COUNTERS" in codes
