"""Validator for Segment 1B state-6 site jitter."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

import polars as pl
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.prepared import PreparedGeometry

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ..exceptions import err
from ..l0.datasets import (
    TileBoundsPartition,
    TileIndexPartition,
    load_iso_countries,
    load_s5_assignments,
    load_tile_bounds,
    load_tile_index_partition,
    load_world_countries,
)
from ...shared.dictionary import load_dictionary, resolve_dataset_path


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S6 outputs."""

    data_root: Path
    seed: str
    manifest_fingerprint: str
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None
    run_report_path: Optional[Path] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "seed", str(self.seed))
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


class S6SiteJitterValidator:
    """Validate S6 outputs according to the specification."""

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()

        dataset_path = resolve_dataset_path(
            "s6_site_jitter",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
                "parameter_hash": config.parameter_hash,
            },
            dictionary=dictionary,
        )
        if not dataset_path.exists():
            raise err(
                "E601_ROW_MISSING",
                f"s6_site_jitter partition missing at '{dataset_path}'",
            )

        dataset = _read_parquet(dataset_path)
        _validate_sort(dataset)
        _validate_manifest(dataset, config.manifest_fingerprint)
        _ensure_unique_pk(dataset)

        assignments = load_s5_assignments(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        _validate_row_parity(dataset, assignments.frame)

        tile_bounds_partition = load_tile_bounds(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        tile_index_partition = load_tile_index_partition(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        world_countries_partition = load_world_countries(
            base_path=config.data_root,
            dictionary=dictionary,
        )
        iso_table, iso_version = load_iso_countries(
            base_path=config.data_root,
            dictionary=dictionary,
        )

        iso_codes_in_dataset = frozenset(
            dataset.get_column("legal_country_iso").str.to_uppercase().unique().to_list()
        )

        tile_bounds_map = _build_tile_bounds_map(tile_bounds_partition, iso_codes_in_dataset)
        tile_centroid_map = _build_tile_centroid_map(tile_index_partition, iso_codes_in_dataset)
        country_polygons = {
            poly.country_iso: poly for poly in world_countries_partition.polygons
        }

        _validate_iso_codes(dataset, iso_table.codes)

        per_country_sites = _compute_site_counts(
            dataset,
            tile_bounds_map,
            tile_centroid_map,
            country_polygons,
        )

        run_report_path = (
            config.run_report_path
            if config.run_report_path is not None
            else resolve_dataset_path(
                "s6_run_report",
                base_path=config.data_root,
                template_args={
                    "seed": config.seed,
                    "manifest_fingerprint": config.manifest_fingerprint,
                    "parameter_hash": config.parameter_hash,
                },
                dictionary=dictionary,
            )
        )
        run_report = _load_run_report(run_report_path)

        identity_block = run_report.get("identity", {})
        run_id = identity_block.get("run_id")
        if not isinstance(run_id, str) or len(run_id) != 32:
            raise err("E604_PARTITION_OR_IDENTITY", "run report missing valid run_id")

        rng_events, rng_stats, events_dir = _validate_rng_events(
            config,
            dictionary,
            dataset,
            run_id,
        )

        audit_record, audit_path = _validate_rng_audit_log(
            config=config,
            dictionary=dictionary,
            run_id=run_id,
        )
        trace_stats, trace_path = _validate_rng_trace_log(
            config=config,
            dictionary=dictionary,
            run_id=run_id,
            events=rng_events,
            expected_stats=rng_stats,
        )

        determinism_receipt = _validate_determinism_receipt(dataset_path, run_report)

        _validate_run_report_contents(
            run_report,
            config,
            dataset,
            determinism_receipt,
            per_country_sites,
            rng_stats,
            iso_version,
            {
                "dataset_path": dataset_path,
                "rng_event_log": events_dir,
                "rng_audit_log": audit_path,
                "rng_trace_log": trace_path,
            },
        )


def _read_parquet(path: Path) -> pl.DataFrame:
    return (
        pl.scan_parquet(str(path / "*.parquet"))
        .select(
            [
                "merchant_id",
                "legal_country_iso",
                "site_order",
                "tile_id",
                "delta_lat_deg",
                "delta_lon_deg",
                "manifest_fingerprint",
            ]
        )
        .collect()
    )


def _validate_sort(frame: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows()
    if frame.rows() != sorted_rows:
        raise err(
            "E605_SORT_VIOLATION",
            "s6_site_jitter must be sorted by ['merchant_id','legal_country_iso','site_order']",
        )


def _validate_manifest(frame: pl.DataFrame, manifest: str) -> None:
    column = frame.get_column("manifest_fingerprint").str.to_lowercase()
    expected = manifest.lower()
    if not column.eq(expected).all():
        raise err("E604_PARTITION_OR_IDENTITY", "manifest_fingerprint mismatch in dataset rows")


def _ensure_unique_pk(frame: pl.DataFrame) -> None:
    dupes = (
        frame.group_by(["merchant_id", "legal_country_iso", "site_order"])
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
    )
    if dupes.height:
        raise err("E603_DUP_KEY", "duplicate site keys found in s6_site_jitter")


def _validate_row_parity(dataset: pl.DataFrame, assignments: pl.DataFrame) -> None:
    if dataset.height != assignments.height:
        raise err(
            "E601_ROW_MISSING",
            f"s6 rows ({dataset.height}) != s5 rows ({assignments.height})",
        )

    keys = ["merchant_id", "legal_country_iso", "site_order"]
    missing = assignments.select(keys).join(
        dataset.select(keys),
        on=keys,
        how="anti",
    )
    if missing.height:
        raise err(
            "E601_ROW_MISSING",
            "s6 is missing site rows present in s5_site_tile_assignment",
        )

    extra = dataset.select(keys).join(
        assignments.select(keys),
        on=keys,
        how="anti",
    )
    if extra.height:
        raise err("E602_ROW_EXTRA", "s6 contains site rows not present in s5_site_tile_assignment")


def _build_tile_bounds_map(
    partition: TileBoundsPartition, iso_codes: Iterable[str]
) -> Mapping[Tuple[str, int], Mapping[str, float]]:
    bounds: Dict[Tuple[str, int], Dict[str, float]] = {}
    for iso in iso_codes:
        iso_key = str(iso).upper()
        frame = partition.collect_country(iso_key)
        for row in frame.iter_rows(named=True):
            key = (iso_key, int(row["tile_id"]))
            bounds[key] = {
                "min_lon_deg": float(row["min_lon_deg"]),
                "max_lon_deg": float(row["max_lon_deg"]),
                "min_lat_deg": float(row["min_lat_deg"]),
                "max_lat_deg": float(row["max_lat_deg"]),
            }
    return bounds


def _build_tile_centroid_map(
    partition: TileIndexPartition, iso_codes: Iterable[str]
) -> Mapping[Tuple[str, int], Mapping[str, float]]:
    centroids: Dict[Tuple[str, int], Dict[str, float]] = {}
    for iso in iso_codes:
        iso_key = str(iso).upper()
        frame = partition.collect_country(iso_key, columns=("country_iso", "tile_id", "centroid_lon", "centroid_lat"))
        for row in frame.iter_rows(named=True):
            key = (iso_key, int(row["tile_id"]))
            centroids[key] = {
                "lon": float(row["centroid_lon"]),
                "lat": float(row["centroid_lat"]),
            }
    return centroids


def _validate_iso_codes(frame: pl.DataFrame, iso_codes: frozenset[str]) -> None:
    invalid = frame.select(pl.col("legal_country_iso").str.to_uppercase().alias("legal_country_iso")).filter(
        ~pl.col("legal_country_iso").is_in(list(iso_codes))
    )
    if invalid.height:
        raise err("E606_FK_TILE_INDEX", "s6_site_jitter contains ISO codes missing from ingress surface")


def _compute_site_counts(
    dataset: pl.DataFrame,
    bounds_map: Mapping[Tuple[str, int], Mapping[str, float]],
    centroid_map: Mapping[Tuple[str, int], Mapping[str, float]],
    polygons: Mapping[str, object],
) -> Dict[str, Dict[str, object]]:
    per_country: Dict[str, Dict[str, object]] = {}

    for row in dataset.iter_rows(named=True):
        iso = str(row["legal_country_iso"]).upper()
        tile_id = int(row["tile_id"])
        key = (iso, tile_id)

        bounds = bounds_map.get(key)
        centroid = centroid_map.get(key)
        polygon = polygons.get(iso)

        if bounds is None or centroid is None or polygon is None:
            raise err("E606_FK_TILE_INDEX", f"tile bounds or polygon missing for {key}")

        lon = _wrap_longitude(centroid["lon"] + float(row["delta_lon_deg"]))
        lat = centroid["lat"] + float(row["delta_lat_deg"])

        if not _point_inside_pixel(lon, lat, bounds):
            raise err(
                "E607_POINT_OUTSIDE_PIXEL",
                f"reconstructed point ({lon},{lat}) outside pixel bounds for {key}",
            )

        if not _point_inside_country(lon, lat, polygon):
            raise err(
                "E608_POINT_OUTSIDE_COUNTRY",
                f"reconstructed point ({lon},{lat}) outside country for {key}",
            )

        stats = per_country.setdefault(
            iso,
            {
                "sites": 0,
                "rng_events": 0,
                "rng_draws": "0",
                "outside_pixel": 0,
                "outside_country": 0,
            },
        )
        stats["sites"] += 1

    return per_country


def _validate_rng_events(
    config: ValidatorConfig,
    dictionary: Mapping[str, object],
    dataset: pl.DataFrame,
    run_id: str,
) -> Tuple[list[Mapping[str, object]], Dict[str, object], Path]:
    events_dir = resolve_dataset_path(
        "rng_event_in_cell_jitter",
        base_path=config.data_root,
        template_args={
            "seed": config.seed,
            "parameter_hash": config.parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    if not events_dir.exists():
        raise err(
            "E609_RNG_EVENT_COUNT",
            f"rng event partition missing at '{events_dir}'",
        )

    events: list[Mapping[str, object]] = []
    for file in sorted(events_dir.glob("*.jsonl")):
        for line in file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise err("E609_RNG_EVENT_COUNT", f"invalid JSON in RNG log: {exc}") from exc
            events.append(payload)

    if not events:
        raise err("E609_RNG_EVENT_COUNT", "rng event partition contains no events")

    site_keys = {
        (int(row["merchant_id"]), str(row["legal_country_iso"]).upper(), int(row["site_order"]))
        for row in dataset.iter_rows(named=True)
    }

    events_by_site: Dict[Tuple[int, str, int], list[Mapping[str, object]]] = {}
    for event in events:
        key = (
            int(event.get("merchant_id", -1)),
            str(event.get("legal_country_iso", "")).upper(),
            int(event.get("site_order", -1)),
        )
        events_by_site.setdefault(key, []).append(event)

    if set(events_by_site.keys()) != site_keys:
        raise err("E609_RNG_EVENT_COUNT", "rng events do not cover the S6 site keyset exactly")

    seed_int = int(config.seed)
    first_counter: Optional[int] = None
    last_counter: Optional[int] = None
    total_draws = 0
    per_country_events: Dict[str, Dict[str, object]] = {}
    attempt_hist = Counter()
    resample_sites_total = 0
    resample_events_total = 0

    dataset_lookup = {
        (int(row["merchant_id"]), str(row["legal_country_iso"]).upper(), int(row["site_order"])): row
        for row in dataset.iter_rows(named=True)
    }

    for key, site_events in events_by_site.items():
        site_events.sort(key=lambda evt: int(evt.get("attempt_index", 0)))
        _validate_site_events(key, site_events, seed_int, run_id, config, dataset_lookup)
        attempts = len(site_events)
        attempt_hist[attempts] += 1
        if attempts > 1:
            resample_sites_total += 1
            resample_events_total += attempts - 1

        per_country_stats = per_country_events.setdefault(
            key[1],
            {"rng_events": 0, "rng_draws": 0},
        )
        per_country_stats["rng_events"] += len(site_events)
        per_country_stats["rng_draws"] += len(site_events) * 2

        for event in site_events:
            before = _pack_counter(
                event.get("rng_counter_before_hi"),
                event.get("rng_counter_before_lo"),
            )
            after = _pack_counter(
                event.get("rng_counter_after_hi"),
                event.get("rng_counter_after_lo"),
            )
            if after - before != 1:
                raise err("E610_RNG_BUDGET_OR_COUNTERS", "counter delta mismatch for RNG event")
            total_draws += int(event.get("draws", "0"))
            if first_counter is None or before < first_counter:
                first_counter = before
            if last_counter is None or after > last_counter:
                last_counter = after

    events_total = len(events)
    counter_span = (
        0 if first_counter is None or last_counter is None else max(0, last_counter - first_counter)
    )

    if events_total < dataset.height:
        raise err(
            "E609_RNG_EVENT_COUNT",
            "rng events fewer than dataset sites",
        )

    if total_draws != events_total * 2:
        raise err("E610_RNG_BUDGET_OR_COUNTERS", "draws total mismatch with event budget")

    rng_stats = {
        "events_total": events_total,
        "draws_total": total_draws,
        "blocks_total": events_total,
        "counter_span": counter_span,
        "per_country": per_country_events,
        "attempt_histogram": {str(k): v for k, v in attempt_hist.items()},
        "resample_sites_total": resample_sites_total,
        "resample_events_total": resample_events_total,
    }

    return events, rng_stats, events_dir


def _validate_rng_audit_log(
    *,
    config: ValidatorConfig,
    dictionary: Mapping[str, object],
    run_id: str,
) -> Tuple[Mapping[str, object], Path]:
    audit_path = resolve_dataset_path(
        "rng_audit_log",
        base_path=config.data_root,
        template_args={
            "seed": config.seed,
            "parameter_hash": config.parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    if not audit_path.exists():
        raise err("E609_RNG_EVENT_COUNT", f"rng audit log missing at '{audit_path}'")

    lines = [
        line.strip()
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        raise err("E609_RNG_EVENT_COUNT", f"rng audit log '{audit_path}' is empty")
    if len(lines) > 1:
        raise err("E611_LOG_PARTITION_LAW", f"rng audit log '{audit_path}' contains multiple records")
    try:
        record = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise err("E609_RNG_EVENT_COUNT", f"rng audit log '{audit_path}' is not valid JSON") from exc

    seed_int = int(config.seed)
    if int(record.get("seed", -1)) != seed_int:
        raise err("E604_PARTITION_OR_IDENTITY", "rng audit log seed mismatch")
    if str(record.get("run_id", "")) != run_id:
        raise err("E604_PARTITION_OR_IDENTITY", "rng audit log run_id mismatch")
    if str(record.get("parameter_hash", "")).lower() != config.parameter_hash.lower():
        raise err("E604_PARTITION_OR_IDENTITY", "rng audit log parameter_hash mismatch")
    if str(record.get("manifest_fingerprint", "")).lower() != config.manifest_fingerprint.lower():
        raise err("E604_PARTITION_OR_IDENTITY", "rng audit log manifest fingerprint mismatch")
    if record.get("algorithm") != "philox2x64-10":
        raise err("E604_PARTITION_OR_IDENTITY", "rng audit log algorithm mismatch")
    build_commit = record.get("build_commit")
    if not isinstance(build_commit, str) or not build_commit.strip():
        raise err("E604_PARTITION_OR_IDENTITY", "rng audit log build_commit must be a non-empty string")
    ts_utc = record.get("ts_utc")
    if not isinstance(ts_utc, str) or not ts_utc.endswith("Z"):
        raise err("E604_PARTITION_OR_IDENTITY", "rng audit log ts_utc must be an RFC-3339 string")

    return record, audit_path


def _validate_rng_trace_log(
    *,
    config: ValidatorConfig,
    dictionary: Mapping[str, object],
    run_id: str,
    events: Sequence[Mapping[str, object]],
    expected_stats: Mapping[str, object],
) -> Tuple[Mapping[str, int], Path]:
    trace_path = resolve_dataset_path(
        "rng_trace_log",
        base_path=config.data_root,
        template_args={
            "seed": config.seed,
            "parameter_hash": config.parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    if not trace_path.exists():
        raise err("E609_RNG_EVENT_COUNT", f"rng trace log missing at '{trace_path}'")

    lines = [
        line.strip()
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if not lines:
        if expected_stats.get("events_total", 0) != 0:
            raise err("E609_RNG_EVENT_COUNT", f"rng trace log '{trace_path}' is empty")
        return {"events_total": 0, "draws_total": 0, "blocks_total": 0, "counter_span": 0}, trace_path

    records: list[Mapping[str, object]] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise err("E609_RNG_EVENT_COUNT", f"invalid JSON in rng trace log: {exc}") from exc
        records.append(record)

    if len(records) != len(events):
        raise err("E609_RNG_EVENT_COUNT", "rng trace log records do not align with event count")

    seed_int = int(config.seed)
    stream_totals: dict[Tuple[str, str], dict[str, int]] = {}
    first_counter: Optional[int] = None
    last_counter: Optional[int] = None

    for record, event in zip(records, events):
        module = str(record.get("module", ""))
        substream = str(record.get("substream_label", ""))
        if module != str(event.get("module", "")) or substream != str(event.get("substream_label", "")):
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace log module/substream mismatch with events")
        if str(record.get("run_id", "")) != run_id:
            raise err("E604_PARTITION_OR_IDENTITY", "rng trace log run_id mismatch")
        if int(record.get("seed", -1)) != seed_int:
            raise err("E604_PARTITION_OR_IDENTITY", "rng trace log seed mismatch")

        before_lo = int(record.get("rng_counter_before_lo", -1))
        before_hi = int(record.get("rng_counter_before_hi", -1))
        after_lo = int(record.get("rng_counter_after_lo", -1))
        after_hi = int(record.get("rng_counter_after_hi", -1))
        if before_lo != int(event.get("rng_counter_before_lo", -1)) or before_hi != int(event.get("rng_counter_before_hi", -1)):
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace log counter_before mismatch")
        if after_lo != int(event.get("rng_counter_after_lo", -1)) or after_hi != int(event.get("rng_counter_after_hi", -1)):
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace log counter_after mismatch")

        draws_total = int(record.get("draws_total", -1))
        blocks_total = int(record.get("blocks_total", -1))
        events_total = int(record.get("events_total", -1))

        stream_state = stream_totals.setdefault(
            (module, substream), {"events": 0, "blocks": 0, "draws": 0}
        )
        stream_state["events"] += 1
        stream_state["blocks"] += 1
        stream_state["draws"] += 2

        if events_total != stream_state["events"]:
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace events_total not cumulative")
        if blocks_total != stream_state["blocks"]:
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace blocks_total not cumulative")
        if draws_total != stream_state["draws"]:
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace draws_total not cumulative")

        before_u128 = (before_hi << 64) | before_lo
        after_u128 = (after_hi << 64) | after_lo
        if first_counter is None or before_u128 < first_counter:
            first_counter = before_u128
        if last_counter is None or after_u128 > last_counter:
            last_counter = after_u128

    overall_events = sum(state["events"] for state in stream_totals.values())
    overall_blocks = sum(state["blocks"] for state in stream_totals.values())
    overall_draws = sum(state["draws"] for state in stream_totals.values())
    counter_span = (
        0 if first_counter is None or last_counter is None else max(0, last_counter - first_counter)
    )

    if overall_events != expected_stats.get("events_total"):
        raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace events_total mismatch with event log")
    if overall_draws != expected_stats.get("draws_total"):
        raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace draws_total mismatch with event log")
    if overall_blocks != expected_stats.get("blocks_total"):
        raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace blocks_total mismatch with event log")
    if counter_span != expected_stats.get("counter_span"):
        raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng trace counter_span mismatch with event log")

    trace_stats = {
        "events_total": overall_events,
        "draws_total": overall_draws,
        "blocks_total": overall_blocks,
        "counter_span": counter_span,
    }
    return trace_stats, trace_path



def _validate_site_events(
    key: Tuple[int, str, int],
    site_events: Sequence[Mapping[str, object]],
    seed_int: int,
    run_id: str,
    config: ValidatorConfig,
    dataset_lookup: Mapping[Tuple[int, str, int], Mapping[str, object]],
) -> None:
    merchant_id, iso, site_order = key

    dataset_row = dataset_lookup[key]
    delta_lon = float(dataset_row["delta_lon_deg"])
    delta_lat = float(dataset_row["delta_lat_deg"])

    if site_events[0].get("attempt_index") != 1:
        raise err("E609_RNG_EVENT_COUNT", f"site {key} attempt index must start at 1")

    for idx, event in enumerate(site_events, start=1):
        if int(event.get("attempt_index", 0)) != idx:
            raise err("E609_RNG_EVENT_COUNT", f"site {key} attempt indices not contiguous")
        if event.get("module") != "1B.S6.jitter" or event.get("substream_label") != "in_cell_jitter":
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "unexpected module/substream in RNG event")
        if int(event.get("seed", -1)) != seed_int:
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "seed mismatch in RNG event")
        if str(event.get("parameter_hash", "")).lower() != config.parameter_hash.lower():
            raise err("E604_PARTITION_OR_IDENTITY", "parameter_hash mismatch in RNG event")
        if str(event.get("manifest_fingerprint", "")).lower() != config.manifest_fingerprint.lower():
            raise err("E604_PARTITION_OR_IDENTITY", "manifest_fingerprint mismatch in RNG event")
        if str(event.get("run_id", "")) != run_id:
            raise err("E604_PARTITION_OR_IDENTITY", "run_id mismatch in RNG event")
        if int(event.get("blocks", 0)) != 1 or str(event.get("draws", "")) != "2":
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "rng event budget must be blocks=1, draws='2'")
        if float(event.get("sigma_lat_deg", 0.0)) != 0.0 or float(event.get("sigma_lon_deg", 0.0)) != 0.0:
            raise err("E610_RNG_BUDGET_OR_COUNTERS", "sigma fields must be zero in uniform lane")

    accepted = [event for event in site_events if bool(event.get("accepted"))]
    if len(accepted) != 1:
        raise err("E609_RNG_EVENT_COUNT", f"site {key} must have exactly one accepted attempt")

    final_event = accepted[0]
    if not _almost_equal(float(final_event.get("delta_lon_deg", 0.0)), delta_lon):
        raise err("E609_RNG_EVENT_COUNT", "accepted event delta_lon_deg mismatch with dataset")
    if not _almost_equal(float(final_event.get("delta_lat_deg", 0.0)), delta_lat):
        raise err("E609_RNG_EVENT_COUNT", "accepted event delta_lat_deg mismatch with dataset")


def _validate_determinism_receipt(
    dataset_path: Path,
    run_report: Mapping[str, object],
) -> Mapping[str, str]:
    determinism = run_report.get("determinism_receipt")
    if not isinstance(determinism, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report missing determinism_receipt")

    actual_digest = compute_partition_digest(dataset_path)
    if determinism.get("partition_path") != str(dataset_path):
        raise err("E604_PARTITION_OR_IDENTITY", "determinism receipt partition path mismatch")
    if determinism.get("sha256_hex") != actual_digest:
        raise err("E604_PARTITION_OR_IDENTITY", "determinism receipt digest mismatch")
    return determinism


def _validate_run_report_contents(
    run_report: Mapping[str, object],
    config: ValidatorConfig,
    dataset: pl.DataFrame,
    determinism_receipt: Mapping[str, str],
    per_country_sites: Mapping[str, Dict[str, object]],
    rng_stats: Mapping[str, object],
    iso_version: Optional[str],
    artefact_paths: Mapping[str, Path],
) -> None:
    identity = run_report.get("identity")
    if not isinstance(identity, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report missing identity block")
    if identity.get("seed") != config.seed:
        raise err("E604_PARTITION_OR_IDENTITY", "run report seed mismatch")
    if identity.get("manifest_fingerprint") != config.manifest_fingerprint:
        raise err("E604_PARTITION_OR_IDENTITY", "run report manifest mismatch")
    if identity.get("parameter_hash") != config.parameter_hash:
        raise err("E604_PARTITION_OR_IDENTITY", "run report parameter_hash mismatch")

    counts = run_report.get("counts")
    if not isinstance(counts, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report missing counts block")
    if counts.get("sites_total") != dataset.height:
        raise err("E604_PARTITION_OR_IDENTITY", "run report sites_total mismatch")

    rng_block = counts.get("rng")
    if not isinstance(rng_block, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report missing rng counters")
    if int(rng_block.get("events_total", -1)) != rng_stats["events_total"]:
        raise err("E604_PARTITION_OR_IDENTITY", "run report rng events_total mismatch")
    if str(rng_block.get("draws_total")) != str(rng_stats["draws_total"]):
        raise err("E604_PARTITION_OR_IDENTITY", "run report rng draws_total mismatch")
    if int(rng_block.get("blocks_total", -1)) != rng_stats["blocks_total"]:
        raise err("E604_PARTITION_OR_IDENTITY", "run report rng blocks_total mismatch")
    if str(rng_block.get("counter_span")) != str(rng_stats["counter_span"]):
        raise err("E604_PARTITION_OR_IDENTITY", "run report rng counter_span mismatch")
    if int(rng_block.get("resample_sites_total", -1)) != rng_stats["resample_sites_total"]:
        raise err("E604_PARTITION_OR_IDENTITY", "run report rng resample_sites_total mismatch")
    if int(rng_block.get("resample_events_total", -1)) != rng_stats["resample_events_total"]:
        raise err("E604_PARTITION_OR_IDENTITY", "run report rng resample_events_total mismatch")

    attempt_hist_block = rng_block.get("attempt_histogram")
    expected_attempt_hist = rng_stats.get("attempt_histogram", {})
    if not isinstance(attempt_hist_block, Mapping) or {
        str(k): int(v) for k, v in attempt_hist_block.items()
    } != {str(k): int(v) for k, v in expected_attempt_hist.items()}:
        raise err("E604_PARTITION_OR_IDENTITY", "run report attempt_histogram mismatch")

    validation_counters = run_report.get("validation_counters")
    if not isinstance(validation_counters, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report missing validation counters")
    for field in (
        "fk_tile_index_failures",
        "point_outside_pixel",
        "point_outside_country",
        "path_embed_mismatches",
    ):
        if int(validation_counters.get(field, 0)) != 0:
            raise err("E604_PARTITION_OR_IDENTITY", f"run report field '{field}' must be zero on success")

    by_country = run_report.get("by_country")
    if not isinstance(by_country, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report missing by_country block")

    per_country_stats = rng_stats["per_country"]
    for iso, site_stats in per_country_sites.items():
        entry = by_country.get(iso)
        if not isinstance(entry, Mapping):
            raise err("E604_PARTITION_OR_IDENTITY", f"run report missing per-country stats for {iso}")
        if int(entry.get("sites", 0)) != site_stats["sites"]:
            raise err("E604_PARTITION_OR_IDENTITY", f"run report sites mismatch for {iso}")
        rng_entry = per_country_stats.get(iso, {"rng_events": 0, "rng_draws": 0})
        if int(entry.get("rng_events", 0)) != rng_entry["rng_events"]:
            raise err("E604_PARTITION_OR_IDENTITY", f"run report rng_events mismatch for {iso}")
        if entry.get("rng_draws") != str(rng_entry["rng_draws"]):
            raise err("E604_PARTITION_OR_IDENTITY", f"run report rng_draws mismatch for {iso}")
        if int(entry.get("outside_pixel", 0)) != 0 or int(entry.get("outside_country", 0)) != 0:
            raise err("E604_PARTITION_OR_IDENTITY", f"run report outside counters must be zero for {iso}")

    if iso_version:
        ingress_versions = run_report.get("ingress_versions", {})
        if ingress_versions.get("iso3166_canonical_2024") != iso_version:
            raise err("E604_PARTITION_OR_IDENTITY", "run report ingress version mismatch")

    if run_report.get("determinism_receipt") != determinism_receipt:
        raise err("E604_PARTITION_OR_IDENTITY", "run report determinism receipt mismatch")

    artefacts = run_report.get("artefacts")
    if not isinstance(artefacts, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report missing artefacts block")
    for key, path in artefact_paths.items():
        expected_path = str(path)
        if artefacts.get(key) != expected_path:
            raise err("E604_PARTITION_OR_IDENTITY", f"run report artefact '{key}' mismatch")


def _load_run_report(path: Path) -> Mapping[str, object]:
    if not path.exists():
        raise err("E604_PARTITION_OR_IDENTITY", f"s6 run report missing at '{path}'")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err("E604_PARTITION_OR_IDENTITY", f"run report is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise err("E604_PARTITION_OR_IDENTITY", "run report must decode to an object")
    return payload


def _wrap_longitude(value: float) -> float:
    while value > 180.0:
        value -= 360.0
    while value < -180.0:
        value += 360.0
    return value


def _point_inside_pixel(lon: float, lat: float, bounds: Mapping[str, float]) -> bool:
    west = bounds["min_lon_deg"]
    east = bounds["max_lon_deg"]
    south = bounds["min_lat_deg"]
    north = bounds["max_lat_deg"]
    if east < west:
        east += 360.0
        if lon < west:
            lon += 360.0
    epsilon = 1e-9
    return (west - epsilon) <= lon <= (east + epsilon) and (south - epsilon) <= lat <= (north + epsilon)


def _point_inside_country(lon: float, lat: float, polygon: object) -> bool:
    prepared: PreparedGeometry = polygon.prepared  # type: ignore[assignment]
    geometry: BaseGeometry = polygon.geometry  # type: ignore[assignment]
    point = Point(lon, lat)
    return prepared.contains(point) or geometry.touches(point)


def _pack_counter(hi: object, lo: object) -> int:
    return (int(hi) << 64) | int(lo)


def _almost_equal(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


__all__ = ["S6SiteJitterValidator", "ValidatorConfig"]
