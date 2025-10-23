from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from shapely.prepared import prep as prepare_geometry

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    CountryPolygon,
    CountryPolygons,
    IsoCountryTable,
)
from engine.layers.l1.seg_1B.s6_site_jitter.l0.datasets import (
    S5AssignmentPartition,
    TileBoundsPartition,
    TileIndexPartition,
    WorldCountriesPartition,
)
from engine.layers.l1.seg_1B.s6_site_jitter.l1.jitter import JitterOutcome
from engine.layers.l1.seg_1B.s6_site_jitter.l2.materialise import (
    S6RunResult,
    materialise_jitter,
)
from engine.layers.l1.seg_1B.s6_site_jitter.l2.prepare import PreparedInputs
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


def _prepare_inputs(tmp_path: Path) -> PreparedInputs:
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
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "site_order": [1],
            "tile_id": [1],
        }
    )
    assignment_df.write_parquet(assignment_path / "part-00000.parquet")

    tile_bounds_path = tmp_path / f"data/layer1/1B/tile_bounds/parameter_hash={parameter_hash}"
    tile_bounds_path.mkdir(parents=True, exist_ok=True)
    tile_bounds_df = pl.DataFrame(
        {
            "country_iso": ["US"],
            "tile_id": [1],
            "west_lon": [-1.0],
            "east_lon": [1.0],
            "south_lat": [-1.0],
            "north_lat": [1.0],
        }
    )
    tile_bounds_df.write_parquet(tile_bounds_path / "part-00000.parquet")

    tile_index_path = tmp_path / f"data/layer1/1B/tile_index/parameter_hash={parameter_hash}"
    tile_index_path.mkdir(parents=True, exist_ok=True)
    tile_index_df = pl.DataFrame(
        {
            "country_iso": ["US"],
            "tile_id": [1],
            "centroid_lon": [0.0],
            "centroid_lat": [0.0],
        }
    )
    tile_index_df.write_parquet(tile_index_path / "part-00000.parquet")

    world_countries_path = tmp_path / "reference/world_countries.parquet"
    world_countries_path.parent.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame(
        {"country_iso": ["US"]},
        geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        crs="EPSG:4326",
    )
    gdf.to_parquet(world_countries_path, index=False)

    iso_path = tmp_path / "reference/iso3166.parquet"
    _write_parquet(iso_path, pl.DataFrame({"country_iso": ["US"]}))

    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    country_polygons = CountryPolygons(
        {
            "US": CountryPolygon(
                country_iso="US",
                geometry=polygon,
                prepared=prepare_geometry(polygon),
            )
        }
    )

    return PreparedInputs(
        dictionary=dictionary,
        assignments=S5AssignmentPartition(path=assignment_path, frame=assignment_df),
        tile_bounds=TileBoundsPartition(path=tile_bounds_path, frame=tile_bounds_df),
        tile_index=TileIndexPartition(path=tile_index_path, frame=tile_index_df),
        country_polygons=WorldCountriesPartition(path=world_countries_path, polygons=country_polygons),
        iso_table=IsoCountryTable(table=pl.DataFrame({"country_iso": ["US"]})),
        iso_version="2024-12-31",
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        seed=seed,
        data_root=tmp_path,
    )


def _build_outcome(manifest_fingerprint: str, parameter_hash: str, seed: int, run_id: str) -> JitterOutcome:
    frame = pl.DataFrame(
        {
            "merchant_id": [1],
            "legal_country_iso": ["US"],
            "site_order": [1],
            "tile_id": [1],
            "delta_lat_deg": [0.1],
            "delta_lon_deg": [0.2],
            "manifest_fingerprint": [manifest_fingerprint],
        }
    )
    rng_event = {
        "merchant_id": 1,
        "legal_country_iso": "US",
        "site_order": 1,
        "sigma_lat_deg": 0.0,
        "sigma_lon_deg": 0.0,
        "delta_lat_deg": 0.1,
        "delta_lon_deg": 0.2,
        "attempt_index": 1,
        "accepted": True,
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "seed": seed,
        "run_id": run_id,
        "module": "1B.S6.jitter",
        "substream_label": "in_cell_jitter",
        "ts_utc": "2025-10-23T00:00:00.000000Z",
        "rng_counter_before_hi": 0,
        "rng_counter_before_lo": 0,
        "rng_counter_after_hi": 0,
        "rng_counter_after_lo": 1,
        "blocks": 1,
        "draws": "2",
    }
    return JitterOutcome(
        frame=frame,
        rng_events=[rng_event],
        sites_total=1,
        events_total=1,
        outside_pixel=0,
        outside_country=0,
        fk_tile_index_failures=0,
        path_embed_mismatches=0,
        by_country={
            "US": {
                "sites": 1,
                "rng_events": 1,
                "rng_draws": "2",
                "outside_pixel": 0,
                "outside_country": 0,
            }
        },
        counter_span=1,
        first_counter=(0, 0),
        last_counter=(0, 1),
        attempt_histogram={1: 1},
        resample_sites=0,
        resample_events=0,
    )


def test_materialise_and_validate_s6(tmp_path: Path):
    prepared = _prepare_inputs(tmp_path)
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
    assert len(trace_lines) == 1
    trace_record = json.loads(trace_lines[0])
    assert trace_record["events_total"] == 1
    assert trace_record["draws_total"] == 2
    assert trace_record["blocks_total"] == 1

    run_report = json.loads(result.run_report_path.read_text(encoding="utf-8"))
    rng_counts = run_report["counts"]["rng"]
    assert rng_counts["resample_sites_total"] == 0
    assert rng_counts["resample_events_total"] == 0
    assert rng_counts["attempt_histogram"] == {"1": 1}
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
