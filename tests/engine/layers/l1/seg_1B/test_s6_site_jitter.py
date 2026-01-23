from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import polars as pl
from shapely.geometry import Polygon
import pyarrow.dataset as ds

from engine.layers.l1.seg_1B import S6RunnerConfig, S6SiteJitterRunner
from engine.layers.l1.seg_1B.s6_site_jitter.l0.datasets import TileBoundsPartition
from engine.layers.l1.seg_1B.s6_site_jitter.l1.jitter import JitterOutcome
from engine.layers.l1.seg_1B.s6_site_jitter.l2.materialise import (
    S6RunResult,
    materialise_jitter,
)
from engine.layers.l1.seg_1B.s6_site_jitter.l2.prepare import (
    PreparedInputs,
    prepare_inputs,
)
from engine.layers.l1.seg_1B.s6_site_jitter.l3.validator import (
    S6SiteJitterValidator,
    ValidatorConfig,
)


def _build_dictionary() -> dict[str, object]:
    return {
        "datasets": {
            "s5_site_tile_assignment": {
                "path": "data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/"
            },
            "tile_bounds": {
                "path": "data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}/"
            },
            "tile_index": {
                "path": "data/layer1/1B/tile_index/parameter_hash={parameter_hash}/"
            },
            "s6_site_jitter": {
                "path": "data/layer1/1B/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/"
            },
            "s6_run_report": {
                "path": "control/s6_site_jitter/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}/s6_run_report.json"
            },
        },
        "logs": {
            "rng_event_in_cell_jitter": {
                "path": "logs/rng/events/in_cell_jitter/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/"
            },
            "rng_audit_log": {
                "path": "logs/rng/audit/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_audit_log.jsonl"
            },
            "rng_trace_log": {
                "path": "logs/rng/trace/seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/rng_trace_log.jsonl"
            },
        },
        "reference_data": {
            "world_countries": {"path": "reference/world_countries.parquet"},
            "iso3166_canonical_2024": {"path": "reference/iso3166.parquet"},
        },
    }


def _write_parquet(path: Path, frame: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)


def _prepare_inputs(tmp_path: Path) -> tuple[PreparedInputs, S6RunnerConfig]:
    dictionary = _build_dictionary()
    manifest_fingerprint = "f" * 64
    parameter_hash = "abc123"
    seed = "123"

    assignment_path = (
        tmp_path
        / f"data/layer1/1B/s5_site_tile_assignment/seed={seed}/fingerprint={manifest_fingerprint}/parameter_hash={parameter_hash}"
    )
    assignment_path.mkdir(parents=True, exist_ok=True)
    assignment_df = pl.DataFrame(
        {
            "merchant_id": [101, 102, 201],
            "legal_country_iso": ["US", "US", "CA"],
            "site_order": [1, 2, 1],
            "tile_id": [11, 11, 42],
        }
    )
    assignment_df.write_parquet(assignment_path / "part-00000.parquet")

    tile_bounds_path = tmp_path / f"data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}"
    tile_bounds_path.mkdir(parents=True, exist_ok=True)
    tile_bounds_df = pl.DataFrame(
        {
            "country_iso": ["US", "CA"],
            "tile_id": [11, 42],
            "min_lon_deg": [-1.0, 9.0],
            "max_lon_deg": [1.0, 11.0],
            "min_lat_deg": [-1.0, 9.0],
            "max_lat_deg": [1.0, 11.0],
            "centroid_lon_deg": [0.0, 10.0],
            "centroid_lat_deg": [0.0, 10.0],
        }
    )
    tile_bounds_df.write_parquet(tile_bounds_path / "part-00000.parquet")

    tile_index_path = tmp_path / f"data/layer1/1B/tile_index/parameter_hash={parameter_hash}"
    tile_index_path.mkdir(parents=True, exist_ok=True)
    tile_index_df = pl.DataFrame(
        {
            "country_iso": ["US", "CA"],
            "tile_id": [11, 42],
            "centroid_lon": [0.0, 10.0],
            "centroid_lat": [0.0, 10.0],
        }
    )
    tile_index_df.write_parquet(tile_index_path / "part-00000.parquet")

    world_countries_path = tmp_path / "reference/world_countries.parquet"
    world_countries_path.parent.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(
        {"country_iso": ["US", "CA"]},
        geometry=[
            Polygon([(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]),
            Polygon([(9.0, 9.0), (11.0, 9.0), (11.0, 11.0), (9.0, 11.0)]),
        ],
        crs="EPSG:4326",
    )
    gdf.to_parquet(world_countries_path, index=False)

    iso_path = tmp_path / "reference/iso3166.parquet"
    _write_parquet(iso_path, pl.DataFrame({"country_iso": ["US", "CA"]}))

    config = S6RunnerConfig(
        data_root=tmp_path,
        manifest_fingerprint=manifest_fingerprint,
        seed=seed,
        parameter_hash=parameter_hash,
        dictionary=dictionary,
    )
    prepared = prepare_inputs(config)
    return prepared, config


def _build_outcome(manifest_fingerprint: str, parameter_hash: str, seed: int, run_id: str) -> JitterOutcome:
    merchants = [101, 102, 201]
    iso_codes = ["US", "US", "CA"]
    site_orders = [1, 2, 1]
    tile_ids = [11, 11, 42]
    delta_lats = [0.1, -0.05, 0.2]
    delta_lons = [0.2, -0.12, -0.3]
    frame = pl.DataFrame(
        {
            "merchant_id": merchants,
            "legal_country_iso": iso_codes,
            "site_order": site_orders,
            "tile_id": tile_ids,
            "delta_lat_deg": delta_lats,
            "delta_lon_deg": delta_lons,
            "manifest_fingerprint": [manifest_fingerprint] * len(merchants),
        }
    )
    rng_events = []
    draws_per_event = 2
    for idx, (merchant_id, iso, site_order, delta_lat, delta_lon) in enumerate(
        zip(merchants, iso_codes, site_orders, delta_lats, delta_lons, strict=True)
    ):
        rng_events.append(
            {
                "merchant_id": merchant_id,
                "legal_country_iso": iso,
                "site_order": site_order,
                "sigma_lat_deg": 0.0,
                "sigma_lon_deg": 0.0,
                "delta_lat_deg": delta_lat,
                "delta_lon_deg": delta_lon,
                "attempt_index": 1,
                "accepted": True,
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "seed": seed,
                "run_id": run_id,
                "module": "1B.S6.jitter",
                "substream_label": "in_cell_jitter",
                "ts_utc": f"2025-10-23T00:00:0{idx}.000000Z",
                "rng_counter_before_hi": 0,
                "rng_counter_before_lo": idx,
                "rng_counter_after_hi": 0,
                "rng_counter_after_lo": idx + 1,
                "blocks": 1,
                "draws": str(draws_per_event),
            }
        )

    return JitterOutcome(
        frame=frame,
        rng_events=rng_events,
        sites_total=len(merchants),
        events_total=len(merchants),
        outside_pixel=0,
        outside_country=0,
        fk_tile_index_failures=0,
        path_embed_mismatches=0,
        by_country={
            "US": {
                "sites": 2,
                "rng_events": 2,
                "rng_draws": str(2 * draws_per_event),
                "outside_pixel": 0,
                "outside_country": 0,
            },
            "CA": {
                "sites": 1,
                "rng_events": 1,
                "rng_draws": str(draws_per_event),
                "outside_pixel": 0,
                "outside_country": 0,
            },
        },
        counter_span=3,
        first_counter=(0, 0),
        last_counter=(0, len(merchants)),
        attempt_histogram={1: len(merchants)},
        resample_sites=0,
        resample_events=0,
    )


def test_materialise_and_validate_s6(tmp_path: Path):
    prepared, _ = _prepare_inputs(tmp_path)
    run_id = "0123456789abcdef0123456789abcdef"
    outcome = _build_outcome(
        manifest_fingerprint=prepared.manifest_fingerprint,
        parameter_hash=prepared.parameter_hash,
        seed=int(prepared.seed),
        run_id=run_id,
    )

    result: S6RunResult = materialise_jitter(
        prepared=prepared,
        outcome=outcome,
        run_id=run_id,
    )

    assert result.rng_audit_log_path.exists()
    assert result.rng_trace_log_path.exists()
    assert result.rng_log_path.exists()
    assert result.run_report_path.exists()

    audit_lines = [
        line.strip()
        for line in result.rng_audit_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(audit_lines) == 1
    audit_record = json.loads(audit_lines[0])
    assert audit_record["run_id"] == run_id
    assert audit_record["algorithm"] == "philox2x64-10"
    assert audit_record["seed"] == int(prepared.seed)

    trace_lines = [
        line.strip()
        for line in result.rng_trace_log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    trace_records = [json.loads(line) for line in trace_lines]
    assert len(trace_records) == len(outcome.rng_events)
    final_trace = trace_records[-1]
    assert final_trace["events_total"] == len(outcome.rng_events)
    assert final_trace["draws_total"] == 2 * len(outcome.rng_events)
    assert final_trace["blocks_total"] == len(outcome.rng_events)

    run_report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    rng_counts = run_report["counts"]["rng"]
    assert rng_counts["resample_sites_total"] == 0
    assert rng_counts["resample_events_total"] == 0
    assert rng_counts["events_total"] == 3
    assert rng_counts["attempt_histogram"] == {"1": 3}
    artefacts = run_report["artefacts"]
    assert artefacts["rng_audit_log"] == str(result.rng_audit_log_path)
    assert artefacts["rng_trace_log"] == str(result.rng_trace_log_path)

    validator = S6SiteJitterValidator()
    validator.validate(
        ValidatorConfig(
            data_root=tmp_path,
            seed=prepared.seed,
            manifest_fingerprint=prepared.manifest_fingerprint,
            parameter_hash=prepared.parameter_hash,
            dictionary=prepared.dictionary,
            run_report_path=result.run_report_path,
        )
    )


def test_runner_emits_expected_dataset(tmp_path: Path) -> None:
    prepared, config = _prepare_inputs(tmp_path)

    runner = S6SiteJitterRunner()
    result = runner.run(config)

    assert result.dataset_path.exists()
    parquet_files = sorted(result.dataset_path.glob("*.parquet"))
    assert parquet_files, "jitter dataset missing parquet partition"

    dataset = (
        pl.concat([pl.read_parquet(path) for path in parquet_files])
        .sort(["merchant_id", "site_order"])
    )

    assert dataset.height == prepared.assignments.frame.height
    assert set(dataset.columns) == {
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "tile_id",
        "delta_lat_deg",
        "delta_lon_deg",
        "manifest_fingerprint",
    }

    # Manifests are lowercased inside the kernel.
    assert dataset.get_column("manifest_fingerprint").unique().to_list() == [
        prepared.manifest_fingerprint.lower()
    ]

    tile_bounds = pl.read_parquet(next(prepared.tile_bounds.path.glob("*.parquet")))
    bounds_by_tile = {
        int(row["tile_id"]): row for row in tile_bounds.iter_rows(named=True)
    }
    tile_index = pl.read_parquet(next(prepared.tile_index.path.glob("*.parquet")))
    centroid_by_tile = {
        int(row["tile_id"]): (float(row["centroid_lon"]), float(row["centroid_lat"]))
        for row in tile_index.iter_rows(named=True)
    }

    for row in dataset.iter_rows(named=True):
        tile_id = int(row["tile_id"])
        bounds = bounds_by_tile[tile_id]
        centroid_lon, centroid_lat = centroid_by_tile[tile_id]
        delta_lon = float(row["delta_lon_deg"])
        delta_lat = float(row["delta_lat_deg"])

        west_margin = float(bounds["min_lon_deg"]) - centroid_lon
        east_margin = float(bounds["max_lon_deg"]) - centroid_lon
        south_margin = float(bounds["min_lat_deg"]) - centroid_lat
        north_margin = float(bounds["max_lat_deg"]) - centroid_lat

        tol = 1e-9
        assert south_margin - tol <= delta_lat <= north_margin + tol
        assert west_margin - tol <= delta_lon <= east_margin + tol

    run_report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    rng_counts = run_report["counts"]["rng"]
    assert rng_counts["events_total"] == dataset.height
    assert rng_counts["resample_sites_total"] >= 0
    assert rng_counts["resample_events_total"] >= 0

def test_tile_bounds_partition_handles_legacy_schema(tmp_path: Path) -> None:
    """Even old partitions with legacy column names normalise to canonical form."""

    partition_path = tmp_path / "data/layer1/1B/tile_bounds/parameter_hash=legacy"
    partition_path.mkdir(parents=True, exist_ok=True)
    legacy_df = pl.DataFrame(
        {
            "country_iso": ["US"],
            "tile_id": [11],
            "west_lon": [-1.0],
            "east_lon": [1.0],
            "south_lat": [-1.0],
            "north_lat": [1.0],
        }
    )
    file_path = partition_path / "part-00000.parquet"
    legacy_df.write_parquet(file_path)

    partition = TileBoundsPartition(
        path=partition_path,
        file_paths=(file_path,),
        dataset=ds.dataset([str(file_path)], format="parquet"),
    )

    frame = partition.collect_country("US")
    assert frame.columns == [
        "country_iso",
        "tile_id",
        "min_lon_deg",
        "max_lon_deg",
        "min_lat_deg",
        "max_lat_deg",
        "centroid_lon_deg",
        "centroid_lat_deg",
    ]
    assert frame.shape == (1, 8)
    assert frame[0, "min_lon_deg"] == -1.0
    assert frame[0, "max_lat_deg"] == 1.0
